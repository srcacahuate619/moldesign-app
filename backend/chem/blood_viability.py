import gc
import threading
import time
from pathlib import Path
from typing import Dict, Any, List

from core.models import PhysicochemicalProperties
from utils.logger import get_logger

logger = get_logger(__name__)

# Disponibilidad de los modelos, comprobada SIN ejecutarlos.
#
# EL FALLO QUE ARREGLA. Aqui habia dos `try: from admet_ai import ADMETModel` /
# `from tabpfn import TabPFNClassifier` a nivel de modulo. Ninguno de los dos
# nombres se usaba: cuando de verdad hacen falta se vuelven a importar dentro
# de `get_admet_model()` y de la deteccion de toxicidad. Servian solo para
# decidir si escribir un warning.
#
# El precio era el arranque entero de la aplicacion. `api.main` importa
# `chem.router` -> `chem.properties` -> este modulo, asi que ese import se
# ejecutaba SIEMPRE, antes de atender la primera peticion, y arrastraba:
#
#     torch 12,4 s | chemprop->lightning->torchmetrics->transformers ~6 s
#     astartes->aimsim->matplotlib 2,1 s | descriptastorus->xarray 1,1 s
#
# Medido con `python -X importtime` sobre el runtime empaquetado: de los 51,7 s
# de imports del backend, este bloque explicaba cerca de 28.
#
# `find_spec` contesta la misma pregunta -esta instalado?- leyendo los metadatos
# del paquete, sin ejecutar su `__init__`. Cuesta microsegundos. El modelo se
# sigue cargando igual de perezosamente que antes, en el primer uso real.
import importlib.util


def _paquete_instalado(nombre: str) -> bool:
    """True si el paquete se puede importar, sin llegar a importarlo."""
    try:
        return importlib.util.find_spec(nombre) is not None
    except (ImportError, ValueError):
        return False


_ADMET_MODEL = None

if not _paquete_instalado("admet_ai"):
    logger.warning("admet-ai not installed. Blood viability will use mock predictions.")

if not _paquete_instalado("tabpfn"):
    logger.warning("tabpfn not installed. Custom toxicity flags will be empty.")

# ── Descarga por inactividad de ADMET-AI ────────────────────────────────────
#
# ═══════════════════════════════════════════════════════════════════════════
# EL CANDADO NO ERA REENTRANTE, Y EL HILO SE COLGABA CON ÉL EN LA MANO
# ═══════════════════════════════════════════════════════════════════════════
#
# Lo que había:
#
#     _admet_idle_lock = threading.Lock()
#
#     def unload_admet_model():
#         with _admet_idle_lock:        # (2) intenta tomarlo otra vez
#             ...
#
#     def _idle_check_loop():
#         while True:
#             time.sleep(60)
#             with _admet_idle_lock:    # (1) lo toma
#                 if idle > _admet_idle_timeout:
#                     unload_admet_model()   # -> (2)
#
# `threading.Lock` NO es reentrante: el mismo hilo que lo tiene se bloquea al
# pedirlo de nuevo. Reproducido: llamar a `unload_admet_model()` con el candado
# tomado no vuelve nunca.
#
# El efecto no es que el modelo no se descargue —que también—, es peor. El hilo
# se queda colgado PARA SIEMPRE con el candado en la mano, y `_start_idle_timer`
# también lo pide. Como `get_admet_model()` llama a `_start_idle_timer()` en cada
# uso, la secuencia completa es:
#
#     minuto 0    se carga el modelo, arranca el temporizador
#     minuto 5    el temporizador decide descargar -> se cuelga con el candado
#     después     CUALQUIER predicción ADMET se bloquea para siempre
#
# Es decir: cinco minutos de inactividad y la primera evaluación siguiente cuelga
# la petición indefinidamente. La memoria tampoco se liberaba nunca.
#
# ═══════════════════════════════════════════════════════════════════════════
# LO QUE SE CAMBIA
# ═══════════════════════════════════════════════════════════════════════════
#
# 1. `RLock`. Es lo que el código ya suponía al llamarse a sí mismo. Con él, la
#    llamada anidada funciona y el hilo sale del bucle como estaba escrito.
#
# 2. El bucle DECIDE dentro del candado y ACTÚA fuera. Sostener un candado
#    mientras se libera un modelo de PyTorch y se llama a `gc.collect()` —cientos
#    de milisegundos— bloquea a cualquiera que pida una predicción en ese rato.
#    El `RLock` haría que funcione; sacar el trabajo fuera hace que además no
#    estorbe.
#
# 3. La espera de inactividad sube de 5 a 30 minutos, y se puede configurar.
#    Cargar ADMET-AI cuesta unos 20 s medidos sobre el runtime empaquetado. Con
#    cinco minutos, una sesión de evaluaciones espaciadas —mirar un resultado,
#    pensar, lanzar la siguiente— paga esa recarga varias veces. Media hora cubre
#    esa pauta de trabajo y sigue devolviendo la memoria a un equipo que se dejó
#    la aplicación abierta.
#
# 4. No se descarga con una predicción en curso. `_admet_en_uso` cuenta las que
#    hay dentro; con el contador por encima de cero, el temporizador espera. Sin
#    esto, el modelo puede desaparecer entre `get_admet_model()` y `predict()`.
import os

_last_admet_use: float = 0.0


def _timeout_por_configuracion() -> float:
    """Minutos de inactividad antes de soltar el modelo. 30 por defecto.

    `MOLDESIGN_ADMET_IDLE_MINUTOS=0` desactiva la descarga: es la elección
    correcta en un equipo con memoria de sobra donde el usuario prefiere no
    pagar nunca los 20 s.
    """
    try:
        minutos = float(os.environ.get("MOLDESIGN_ADMET_IDLE_MINUTOS", "30"))
    except ValueError:
        return 30.0 * 60.0
    return max(0.0, minutos) * 60.0


_admet_idle_timeout: float = _timeout_por_configuracion()

#: Cada cuánto mira el temporizador. Nunca más de un minuto, para que un timeout
#: corto configurado a mano siga siendo aproximadamente lo que se pidió.
_INTERVALO_VIGILANCIA: float = 60.0

_admet_idle_thread: threading.Thread | None = None
#: Reentrante A PROPÓSITO: `_idle_check_loop` lo tiene tomado cuando decide, y
#: el código que se llamaba desde ahí volvía a pedirlo. Ver el bloque de arriba.
_admet_idle_lock = threading.RLock()
#: Predicciones en curso. Con esto por encima de cero no se descarga nada.
_admet_en_uso: int = 0


def get_admet_model():
    """Carga perezosa del modelo ADMET para optimizar RAM."""
    global _ADMET_MODEL, _last_admet_use
    if _ADMET_MODEL is None:
        try:
            from admet_ai import ADMETModel
            import platform
            workers = 0 if platform.system() == "Windows" else None
            _ADMET_MODEL = ADMETModel(num_workers=workers)
            logger.info("admet_model_loaded")
        except Exception as e:
            logger.error(f"Error loading ADMETModel: {e}")
            return None
    _last_admet_use = time.time()
    _start_idle_timer()
    return _ADMET_MODEL


def unload_admet_model():
    """Liberar RAM de ADMET-AI + PyTorch.

    No hace nada si hay una predicción en curso: el modelo desaparecería entre
    `get_admet_model()` y `predict()`.
    """
    global _ADMET_MODEL, _tabpfn_classifier, _tabpfn_loaded
    with _admet_idle_lock:
        if _admet_en_uso > 0:
            logger.debug("admet_unload_pospuesto", en_uso=_admet_en_uso)
            return
        if _ADMET_MODEL is not None:
            del _ADMET_MODEL
            _ADMET_MODEL = None
        if _tabpfn_classifier is not None:
            del _tabpfn_classifier
            _tabpfn_classifier = None
            _tabpfn_loaded = False
    # Fuera del candado: liberar PyTorch y recolectar cuesta cientos de ms, y
    # sostener el candado ahí bloquea a quien pida una predicción mientras tanto.
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except ImportError:
        pass
    gc.collect()
    logger.info("admet_model_unloaded")


def _start_idle_timer():
    global _admet_idle_thread
    if _admet_idle_timeout <= 0:
        return  # descarga desactivada por configuración
    with _admet_idle_lock:
        if _admet_idle_thread is not None and _admet_idle_thread.is_alive():
            return
        _admet_idle_thread = threading.Thread(target=_idle_check_loop, daemon=True)
        _admet_idle_thread.start()


def _idle_check_loop():
    """Decide dentro del candado, actúa fuera."""
    while True:
        time.sleep(min(_INTERVALO_VIGILANCIA, max(1.0, _admet_idle_timeout)))
        with _admet_idle_lock:
            if _ADMET_MODEL is None:
                return
            if _admet_en_uso > 0:
                continue
            if time.time() - _last_admet_use <= _admet_idle_timeout:
                continue
        unload_admet_model()
        return


class _EnUso:
    """Marca una predicción en curso para que no le quiten el modelo debajo."""

    def __enter__(self):
        global _admet_en_uso
        with _admet_idle_lock:
            _admet_en_uso += 1
        return self

    def __exit__(self, *_excepcion):
        global _admet_en_uso, _last_admet_use
        with _admet_idle_lock:
            _admet_en_uso -= 1
            _last_admet_use = time.time()
        return False


# ── Cache de predicciones ADMET por SMILES ──────────────────────────────────
# Mismo SMILES = mismos resultados. Evita recalcular.
# El cache se limpia al reiniciar el backend (aceptable para desktop).
# LRU-bound: máximo 500 entradas para evitar crecimiento ilimitado en sesiones largas.
_admet_cache: Dict[str, Dict[str, Any]] = {}
_ADMET_CACHE_MAX_SIZE = 500

# ── Cache del clasificador TabPFN (entrenado en control_toxics.csv) ────────
_tabpfn_classifier = None
_tabpfn_loaded = False
#: "evaluado" | "fallo" | "no_evaluado". Lo consulta el llamador para que la
#: interfaz pueda distinguir «TabPFN no encontró nada» de «TabPFN no corrió».
_tabpfn_estado = "no_evaluado"


def predict_admet_ai(smiles: str) -> Dict[str, Any]:
    """Predice propiedades ADMET usando el ensamble Chemprop de ADMET-AI."""
    # Cache hit: mismo SMILES, resultado instantaneo
    if smiles in _admet_cache:
        logger.debug("admet_cache_hit", smiles=smiles[:30])
        return _admet_cache[smiles].copy()

    model = get_admet_model()
    if not model:
        # NO mock values — return None/empty so downstream code knows data is missing
        logger.warning("admet_model_not_available", smiles=smiles[:30])
        return {
            "Solubility": None,
            "PPB": None,
            "BBB": None,
            "BBB_prob": None,
            "HIA": None,
            "hERG": None,
            "hERG_prob": None,
            "Clearance": None,
            "CYP3A4_Inh": None,
            "CYP2D6_Inh": None,
            "CYP2C9_Inh": None,
            "CYP3A4_Sub": None,
            "CYP2D6_Sub": None,
            "CYP2C9_Sub": None,
        }

    try:
        # La API de ADMET-AI v2 recibe un string o una lista de strings directamente.
        # Pasar un DataFrame causa que itere sobre los nombres de columnas ("smiles"),
        # resultando en un error de parsing y un posterior error torch.cat().
        #
        # `_EnUso` impide que el temporizador de inactividad descargue el modelo
        # entre `get_admet_model()` y este `predict`.
        with _EnUso():
            res = model.predict(smiles)

        # ══════════════════════════════════════════════════════════════════
        # UNA CLAVE QUE FALTA NO ES UNA PREDICCIÓN FAVORABLE
        # ══════════════════════════════════════════════════════════════════
        #
        # Auditoría del 2026-09-04. `_col` devolvía un `default` cuando la clave
        # no estaba, y CADA default era el valor benigno:
        #
        #     PPB       90      BBB   1 (permeable)   HIA  1 (absorbida)
        #     hERG      0 (no bloquea)                Clearance 10
        #     CYP*      0 (ni inhibe ni es sustrato)
        #
        # Una salida de ADMET que sólo trajera solubilidad —porque cambió el
        # nombre de una cabeza, porque el modelo se reentrenó, porque la
        # predicción falló a medias— salía convertida en un perfil ADMET
        # completo y limpio. Y ADMET-AI v2 está reentrenado y NO reproduce v1,
        # así que un cambio de esquema no es hipotético.
        #
        # Ahora una clave ausente es `None`, que es lo que significa. Los
        # llamadores ya saben tratar `None` como «no se midió»: el bloque de
        # arriba lo hace cuando el modelo entero no está.
        #
        # `_faltantes` se registra una vez por predicción para que un cambio de
        # esquema del modelo se vea en el log en vez de disolverse en valores
        # plausibles.
        _faltantes: list[str] = []

        def _col(data, *keys, default=None):
            for k in keys:
                if k in data:
                    return data[k]
            _faltantes.append(keys[0])
            return default

        def _num(data, *keys):
            """Float o None. Nunca un número inventado."""
            valor = _col(data, *keys)
            if valor is None:
                return None
            try:
                return float(valor)
            except (TypeError, ValueError):
                return None

        # ══════════════════════════════════════════════════════════════════
        # `int()` TRUNCA. ADMET-AI DEVUELVE PROBABILIDADES.
        # ══════════════════════════════════════════════════════════════════
        #
        # Las cabezas de clasificación de ADMET-AI no devuelven 0/1: devuelven
        # P(clase positiva) en [0, 1]. Medido sobre el modelo empaquetado, con
        # aspirina (`CC(=O)Oc1ccccc1C(=O)O`):
        #
        #     BBB_Martins  0.658      int() -> 0
        #     HIA_Hou      0.960      int() -> 0
        #     hERG         0.021      int() -> 0
        #
        # `int(0.96)` es 0. Como NINGUNA probabilidad llega jamás a 1.0
        # exacto, TODAS las banderas de clasificación valían 0 siempre, para
        # toda molécula, desde que existe este archivo. Consecuencias medidas:
        #
        #     BBB   siempre «no permeable»  ← el síntoma que se reportó
        #     HIA   siempre «baja», y en el MPO de más abajo eso fija
        #           S_hia = 0.5 para todo el mundo: la viabilidad sanguínea
        #           salía deprimida por un factor constante
        #     hERG  nunca se dispara, así que S_tox nunca penaliza
        #     CYP   ninguna alerta de inhibición o sustrato, nunca
        #
        # Lo peor no es el número: es que el panel enseñaba «✗ No permeable»
        # en rojo —una afirmación— donde el modelo había dicho 0.658, que es
        # lo contrario. Con una molécula tan conocida como la aspirina el
        # error se ve; con una molécula nueva, no lo habría visto nadie.
        #
        # El umbral es 0.5, que es la binarización estándar de estas cabezas
        # (entrenadas con BCE sobre TDC). Se escribe en una constante para que
        # cambiarlo sea una decisión y no un descuido.
        UMBRAL_CLASIFICACION = 0.5

        def _clase(data, *keys) -> int | None:
            """Probabilidad -> etiqueta binaria. `None` si la cabeza no vino.

            Antes tenía un `default` y ese default era siempre la etiqueta
            benigna, así que una cabeza ausente se convertía en «no bloquea
            hERG», «sí absorbe», «no inhibe CYP». Ahora la ausencia se propaga.
            """
            valor = _num(data, *keys)
            if valor is None:
                return None
            return 1 if valor >= UMBRAL_CLASIFICACION else 0

        result = {
            "Solubility": _num(res, "Solubility_AqSolDB", "ESOL", "Solubility"),
            "PPB":        _num(res, "PPBR_AZ", "PPB"),
            "BBB":        _clase(res, "BBB_Martins", "BBB"),
            # La probabilidad CRUDA, por el mismo motivo que en hERG: el
            # consenso de BBB pesa la confianza del modelo, y una etiqueta
            # binaria hace que 0.51 y 0.98 pesen igual. Ver `chem/bbb_consenso.py`.
            "BBB_prob":   _num(res, "BBB_Martins", "BBB"),
            "HIA":        _clase(res, "HIA_Hou", "HIA"),
            "hERG":       _clase(res, "hERG"),
            # La probabilidad CRUDA, además de la etiqueta. `S_tox` la usa de
            # forma continua: binarizar en 0.5 y aplicar después un factor fijo
            # daba un salto de más del doble entre p=0.49 y p=0.51, que el
            # modelo no distingue.
            "hERG_prob":  _num(res, "hERG"),
            "Clearance":  _num(res, "Clearance_Hepatocyte_AZ", "Clearance"),
            "CYP3A4_Inh": _clase(res, "CYP3A4_Veith"),
            "CYP2D6_Inh": _clase(res, "CYP2D6_Veith"),
            "CYP2C9_Inh": _clase(res, "CYP2C9_Veith"),
            "CYP3A4_Sub": _clase(res, "CYP3A4_Substrate_CarbonMangels"),
            "CYP2D6_Sub": _clase(res, "CYP2D6_Substrate_CarbonMangels"),
            "CYP2C9_Sub": _clase(res, "CYP2C9_Substrate_CarbonMangels"),
        }
        if _faltantes:
            # Una cabeza que falta es un cambio de esquema del modelo, no un
            # detalle. ADMET-AI v2 está reentrenado y no reproduce v1: si el
            # nombre de una salida cambia, esto lo dice en vez de rellenarlo.
            logger.warning(
                "admet_cabezas_ausentes",
                claves=sorted(set(_faltantes)),
                disponibles=sorted(res.keys())[:20],
                efecto="esos campos quedan en None, no se sustituyen por un valor típico",
            )
        # LRU eviction: si excedemos el límite, borrar la entrada más antigua
        if len(_admet_cache) >= _ADMET_CACHE_MAX_SIZE:
            oldest = next(iter(_admet_cache))
            del _admet_cache[oldest]
        _admet_cache[smiles] = result.copy()
        return result
    except Exception as e:
        logger.error(f"ADMET-AI prediction failed: {e}")
        return {
            "Solubility": None, "PPB": None, "BBB": None, "BBB_prob": None,
            "HIA": None,
            "hERG": None, "hERG_prob": None, "Clearance": None,
            "CYP3A4_Inh": None, "CYP2D6_Inh": None, "CYP2C9_Inh": None,
            "CYP3A4_Sub": None, "CYP2D6_Sub": None, "CYP2C9_Sub": None,
        }

def predict_tabpfn_custom_toxicity(properties: PhysicochemicalProperties) -> List[str]:
    """
    In-context learning tabular classifier.
    Checks descriptors against custom internal knowledge base (PAINS, Patents).
    """
    alerts = []

    # Reglas locales heurísticas rápidas
    if properties.tpsa > 140:
        alerts.append("High TPSA (Custom Rule)")
    if properties.sa_score > 6:
        alerts.append("Hard to synthesize (SA > 6)")

    # ═════════════════════════════════════════════════════════════════════
    # TabPFN nunca ha clasificado nada
    # ═════════════════════════════════════════════════════════════════════
    #
    # Auditoría del 2026-09-04. Tres defectos encadenados:
    #
    #   1. `properties.logp` NO EXISTE. El campo se llama `log_p`
    #      (`core/models.py`). Cada llamada lanzaba
    #
    #          AttributeError: 'PhysicochemicalProperties' object has no
    #          attribute 'logp'
    #
    #      capturada por el `except` de abajo, que sólo escribe un warning.
    #      Es decir: TabPFN nunca llegó a predecir, en ninguna corrida.
    #   2. `_tabpfn_loaded = True` se ponía ANTES de cargar y ajustar. Si la
    #      carga fallaba, la bandera quedaba en True y no se reintentaba nunca,
    #      con `_tabpfn_classifier` en None para siempre.
    #   3. Que fallara no salía por ninguna parte: la función devuelve la misma
    #      lista de alertas heurísticas tanto si TabPFN dijo «nada» como si no
    #      llegó a mirar, y la interfaz pintaba «✓ Sin alertas … identificadas
    #      por TabPFN» en verde. Un modelo que no corrió no es un visto bueno.
    #
    # Se arreglan los tres. El estado va en `_tabpfn_estado`, que el llamador
    # persiste para que la interfaz pueda decir «no se evaluó» en vez de
    # inventar un aprobado.
    global _tabpfn_estado
    _tabpfn_estado = "no_evaluado"
    try:
        global _tabpfn_classifier, _tabpfn_loaded

        if not _tabpfn_loaded:
            data_path = Path("backend/chem/control_toxics.csv")
            if not data_path.exists():
                data_path = Path("chem/control_toxics.csv")

            if data_path.exists():
                from tabpfn import TabPFNClassifier
                import pandas as pd
                import numpy as np

                df = pd.read_csv(data_path)
                feature_cols = ["mw", "logp", "tpsa", "hbd", "hba", "rotatable_bonds"]
                if all(col in df.columns for col in feature_cols) and "toxic" in df.columns:
                    X_train = df[feature_cols].values
                    y_train = df["toxic"].values
                    _tabpfn_classifier = TabPFNClassifier(device="cpu")
                    _tabpfn_classifier.fit(X_train, y_train)
                    # La bandera SÓLO después de que carga y ajuste terminen.
                    # Puesta antes, un fallo de carga se volvía permanente.
                    _tabpfn_loaded = True
                    logger.info("TabPFN classifier loaded and cached", samples=len(X_train))

        if _tabpfn_classifier is not None:
            import numpy as np
            X_query = np.array([[
                properties.molecular_weight,
                # `log_p`, no `logp`. El nombre equivocado hacía que esta línea
                # lanzara AttributeError en TODAS las llamadas.
                properties.log_p,
                properties.tpsa,
                properties.hbd,
                properties.hba,
                properties.rotatable_bonds
            ]])
            pred = _tabpfn_classifier.predict(X_query)[0]
            _tabpfn_estado = "evaluado"
            if pred == 1:
                alerts.append("TabPFN Alert: High Toxicity (Custom KB)")
    except Exception as e:
        _tabpfn_estado = "fallo"
        # WARNING y no debug: es un componente que la interfaz anuncia por su
        # nombre. Si no corrió, alguien tiene que poder saberlo.
        logger.warning(
            "tabpfn_no_clasifico",
            error=f"{type(e).__name__}: {e}"[:200],
            efecto="las alertas mostradas son sólo las heurísticas locales",
        )

    # Forzamos una limpieza de RAM como se solicitó para TabPFN en el plan secuencial
    gc.collect()
    return alerts


def _rampa_descendente(x: float, uno_hasta: float, cero_desde: float) -> float:
    """1.0 hasta `uno_hasta`, 0.0 desde `cero_desde`, recta en medio."""
    if x <= uno_hasta:
        return 1.0
    if x >= cero_desde:
        return 0.0
    return (cero_desde - x) / (cero_desde - uno_hasta)


def _joroba(
    x: float, cero_hasta: float, uno_desde: float, uno_hasta: float, cero_desde: float
) -> float:
    """0 → 1 → 0. Es la forma del término de TPSA en Wager et al."""
    if x <= cero_hasta:
        return 0.0
    if x < uno_desde:
        return (x - cero_hasta) / (uno_desde - cero_hasta)
    if x <= uno_hasta:
        return 1.0
    if x >= cero_desde:
        return 0.0
    return (cero_desde - x) / (cero_desde - uno_hasta)


def _calculate_cns_mpo(
    mw: float, logp: float, tpsa: float, hbd: int, hba: int, smiles: str | None = None
) -> float:
    """
    CNS MPO de Pfizer — seis términos de deseabilidad, cada uno en [0, 1].
    Ref: Wager, Hou, Verhoest, Villalobos, *ACS Chem. Neurosci.* 1 (2010) 435.

    ═══════════════════════════════════════════════════════════════════════
    LAS RAMPAS, QUE ANTES NO ERAN LAS DEL ARTÍCULO
    ═══════════════════════════════════════════════════════════════════════

    Dos correcciones anteriores dejaron bien los términos de pKa y de cLogD
    (ver `chem/ionizacion.py`). Los otros cuatro seguían siendo escalones
    inventados, con el artículo citado encima. Lo que decía el código frente a
    lo que dice Wager:

                    aquí antes                    Wager et al.
        MW          1.0 en todo 150-500           1.0 hasta 360, 0 en 500
        cLogP       1.0 en todo 1.0-5.0           1.0 hasta 3.0, 0 en 5.0
        TPSA        1.0 por debajo de 90          0 en 20, 1.0 en 40-90, 0 en 120
        HBD         1.0 por debajo de 3           1.0 hasta 0.5, 0 en 3.5
        cLogD       1.0 en todo 1.0-4.0           1.0 hasta 2.0, 0 en 4.0
        pKa         (ya correcto)                 1.0 hasta 8.0, 0 en 10.0

    La diferencia no es cosmética. Las funciones de Wager son **monótonas
    decrecientes** en MW, cLogP y cLogD: no penalizan por abajo. El código
    anterior castigaba la lipofilia baja —a la cafeína, con logP −1.03, le daba
    0.0 en cLogP y 0.0 en cLogD— cuando la cafeína es el ejemplo de manual de
    molécula que entra al cerebro. Con las rampas del artículo la cafeína saca
    6.00 sobre 6, que es lo que el método dice de ella.

    Y en el otro extremo, la meseta de 150 a 500 en MW y de 1 a 5 en logP daba
    el punto entero a moléculas que Wager ya está penalizando: diazepam pasa de
    6.00 a 4.98, sertralina de 5.01 a 2.54.

    ═══════════════════════════════════════════════════════════════════════
    ESTE NÚMERO YA NO DECIDE LA PERMEABILIDAD
    ═══════════════════════════════════════════════════════════════════════

    Era una de las capas del consenso de BBB. Medido sobre 46 fármacos con
    veredicto clínico conocido, la ruta del MPO no añade un solo acierto y sí un
    falso positivo (dopamina: MPO 4.27, y el modelo entrenado decía 0.463). Los
    autores lo presentan como una función de deseabilidad para priorizar dentro
    de una serie, no como un clasificador, y así se comporta al medirlo.

    Se sigue calculando y se sigue mostrando porque informa —enseña qué término
    penaliza a una molécula concreta—, pero el veredicto lo da
    `chem/bbb_consenso.py`. `hba` se conserva en la firma para los llamadores
    antiguos y para el respaldo sin SMILES; el MPO de Pfizer no lo usa.

    `smiles` es opcional: sin él no se pueden calcular ni el pKa ni el cLogD, y
    se declara el respaldo en cada término.
    """
    from chem.ionizacion import analizar_ionizacion, desirabilidad_pka

    estado = analizar_ionizacion(smiles, logp) if smiles else None

    # 1. MW: 1.0 hasta 360 Da, 0.0 desde 500.
    score = _rampa_descendente(mw, 360.0, 500.0)

    # 2. cLogP: 1.0 hasta 3.0, 0.0 desde 5.0. Monótona: no penaliza por abajo.
    score += _rampa_descendente(logp, 3.0, 5.0)

    # 3. TPSA: joroba con la meseta en 40-90 Å². El extremo bajo también resta,
    #    y es el único término del MPO que lo hace.
    score += _joroba(tpsa, 20.0, 40.0, 90.0, 120.0)

    # 4. HBD: 1.0 hasta 0.5 donadores, 0.0 desde 3.5.
    score += _rampa_descendente(hbd, 0.5, 3.5)

    # 5. pKa del centro más básico. Sin SMILES no hay centro que reconocer: se
    #    conserva el término de HBA que ocupaba este sitio antes de la
    #    corrección, para no mover el score de los llamadores que no lo pasan.
    if estado is not None:
        score += desirabilidad_pka(estado.pka_mas_basico)
    elif hba < 7:
        score += 1.0
    else:
        score += max(0.0, 1.0 - (hba - 7) * 0.15)

    # 6. cLogD a pH 7.4 por Henderson-Hasselbalch. Sin SMILES, el
    #    desplazamiento fijo anterior, con su limitación ya declarada.
    logd = estado.logd if estado is not None and estado.logd is not None else logp - 0.5
    score += _rampa_descendente(logd, 2.0, 4.0)

    return round(score, 2)


def calculate_blood_viability(smiles: str, properties: PhysicochemicalProperties) -> PhysicochemicalProperties:
    """ÍNDICE HEURÍSTICO de perfil sanguíneo. No es un pronóstico farmacológico.

    ═════════════════════════════════════════════════════════════════════
    QUÉ MIDE Y QUÉ NO
    ═════════════════════════════════════════════════════════════════════

    Auditoría del 2026-09-04. El número que devuelve esta función se llamaba
    «viabilidad sanguínea» y se presentaba, en la interfaz y en el certificado,
    como si dijera si una molécula es viable en sangre. No lo dice.

    Lo que hace es la media geométrica de tres factores:

        índice = (S_sol * S_hia * S_tox) ** (1/3) * 100

        S_sol   escalón de solubilidad: 1.0 si logS > −4, 0.2 si logS < −6,
                lineal en medio. Los dos cortes son de manual, no ajustados.
        S_hia   1.0 si el clasificador de absorción dice sí, 0.5 si no.
                El 0.5 es una constante elegida a mano.
        S_tox   (1 − p_hERG), acotado a 0.05, multiplicado por 0.8 por cada
                alerta del clasificador de toxicidad.

    Tres cantidades de naturaleza distinta —una concentración, una etiqueta
    binaria y una probabilidad— combinadas con constantes que no salen de
    ningún ajuste contra datos clínicos de este proyecto. La media geométrica
    hace que un factor bajo domine, que es una elección de diseño razonable y
    tampoco está validada.

    Sirve para PRIORIZAR dentro de una serie y para ver qué término penaliza a
    una molécula concreta. No sirve para afirmar que una molécula sobrevive en
    sangre, y en particular `S_tox` no incorpora el margen Cmax,libre/IC50, que
    es lo que decide el riesgo de hERG de verdad.

    Se conserva el nombre del campo (`blood_viability_score`) porque está en el
    esquema y en corridas selladas; lo que cambia es que la interfaz ya no lo
    llama «viabilidad» a secas y este docstring dice de qué está hecho.
    """
    # 1. Predicciones ADMET (Deep Learning)
    admet_preds = predict_admet_ai(smiles)

    # Si ADMET no esta disponible, marcar como no disponible sin valores falsos
    if admet_preds.get("Solubility") is None:
        logger.warning("admet_unavailable_skipping", smiles=smiles[:30])
        properties.blood_viability_score = None
        properties.blood_bbb_permeable = None
        properties.blood_bbb_motivo = None
        properties.blood_cns_mpo = None
        properties.blood_hia_permeable = None
        properties.blood_solubility_logs = None
        properties.blood_ppb_category = None
        properties.blood_systemic_reactivity = []
        return properties

    # 2. Predicciones TabPFN (Custom Data)
    tabpfn_alerts = predict_tabpfn_custom_toxicity(properties)

    # --- CYP METABOLISM ALERTS ---
    cyp_alerts = []
    if admet_preds.get("CYP3A4_Inh") == 1:
        cyp_alerts.append("Inhibidor CYP3A4")
    if admet_preds.get("CYP2D6_Inh") == 1:
        cyp_alerts.append("Inhibidor CYP2D6")
    if admet_preds.get("CYP2C9_Inh") == 1:
        cyp_alerts.append("Inhibidor CYP2C9")

    if admet_preds.get("CYP3A4_Sub") == 1:
        cyp_alerts.append("Sustrato CYP3A4")
    if admet_preds.get("CYP2D6_Sub") == 1:
        cyp_alerts.append("Sustrato CYP2D6")
    if admet_preds.get("CYP2C9_Sub") == 1:
        cyp_alerts.append("Sustrato CYP2C9")

    # --- ASIGNACIÓN DE PROPIEDADES INFORMATIVAS ---
    properties.blood_solubility_logs = admet_preds["Solubility"]

    # ═════════════════════════════════════════════════════════════════════
    # Permeabilidad de la barrera hematoencefálica
    # ═════════════════════════════════════════════════════════════════════
    #
    # La decisión vive en `chem/bbb_consenso.py`, entera y como función pura.
    # Aquí sólo se le pasan los números y se guarda lo que contesta.
    #
    # POR QUÉ SE SACÓ DE AQUÍ. Estaban ochenta líneas de reglas encadenadas
    # dentro de una función que necesita ADMET-AI cargado para ejecutarse una
    # sola vez. No se podía probar sin el modelo, así que no se probaba: por eso
    # la condición central pudo vivir con la precedencia mal puesta —un
    # `or admet_bbb == 1` suelto que saltaba por encima de todos los filtros—
    # hasta que alguien lo leyó a mano. Ahora la decisión se prueba contra 46
    # fármacos con veredicto clínico conocido y sin cargar un solo modelo.
    from chem.bbb_consenso import decidir_bbb

    n_aro = None
    try:
        from rdkit import Chem
        from rdkit.Chem import rdMolDescriptors

        _mol = Chem.MolFromSmiles(smiles)
        if _mol is not None:
            n_aro = rdMolDescriptors.CalcNumAromaticRings(_mol)
    except Exception:  # noqa: BLE001 — sin RDKit la capa 2b no se aplica, y se dice
        logger.debug("bbb_anillos_aromaticos_no_disponibles", smiles=smiles[:30])

    decision = decidir_bbb(
        smiles,
        p_modelo=admet_preds.get("BBB_prob"),
        mw=properties.molecular_weight,
        logp=properties.log_p,
        tpsa=properties.tpsa,
        hbd=properties.hbd,
        hba=properties.hba,
        ppb=admet_preds.get("PPB"),
        anillos_aromaticos=n_aro,
    )
    properties.blood_bbb_permeable = decision.permeable
    properties.blood_bbb_motivo = decision.motivo

    # El CNS MPO ya no decide (ver `_calculate_cns_mpo`), pero se muestra: deja
    # ver qué término penaliza a la molécula cuando el veredicto sorprende.
    properties.blood_cns_mpo = _calculate_cns_mpo(
        mw=properties.molecular_weight,
        logp=properties.log_p,
        tpsa=properties.tpsa,
        hbd=properties.hbd,
        hba=properties.hba,
        smiles=smiles,
    )

    logger.info(
        "bbb_decidido",
        permeable=decision.permeable,
        capa=decision.capa,
        p_modelo=decision.p_modelo,
        cns_mpo=properties.blood_cns_mpo,
    )

    properties.blood_hia_permeable = bool(admet_preds["HIA"])
    properties.blood_systemic_reactivity = tabpfn_alerts + cyp_alerts
    # Con qué derecho se muestra esa lista. `predict_tabpfn_custom_toxicity`
    # deja el estado en el módulo; sin él, una lista vacía se pintaba como
    # visto bueno aunque el clasificador no hubiera corrido.
    properties.blood_tabpfn_estado = _tabpfn_estado

    ppb = admet_preds["PPB"]
    if ppb > 99.0:
        properties.blood_ppb_category = "extreme"
    elif ppb > 90.0:
        properties.blood_ppb_category = "high"
    else:
        properties.blood_ppb_category = "low"

    # --- MPO (OPTIMIZACIÓN MULTIPARAMÉTRICA) ---
    # Calculamos factores de supervivencia (S_factor) de 0.0 a 1.0

    # S_sol: Solubilidad. Si logS < -6 (inviable), cae a 0.2. Si > -4, perfecto (1.0).
    logS = properties.blood_solubility_logs
    if logS >= -4.0:
        S_sol = 1.0
    elif logS <= -6.0:
        S_sol = 0.2
    else:
        # Interpolación lineal entre -6 y -4
        S_sol = 0.2 + 0.8 * ((logS - (-6.0)) / 2.0)

    # S_hia: Absorción. Si no se absorbe, S = 0.5.
    S_hia = 1.0 if properties.blood_hia_permeable else 0.5

    # ══════════════════════════════════════════════════════════════════════
    # S_tox: hERG, con la probabilidad y no con una bandera
    # ══════════════════════════════════════════════════════════════════════
    #
    # LO QUE HABÍA:
    #
    #     if admet_preds["hERG"] == 1:
    #         S_tox *= 0.1   # Paro cardíaco casi seguro
    #
    # Tres cosas mal, y la tercera es la que hace daño.
    #
    # 1. EL COMENTARIO. «Paro cardíaco casi seguro» no es lo que predice ese
    #    modelo. El bloqueo de hERG eleva el riesgo de prolongación del QTc y,
    #    en el extremo, de torsades de pointes; el desenlace clínico depende
    #    del margen entre la concentración plasmática libre y la IC50, que
    #    aquí no se conoce ni se puede conocer. La frase acabó orientando el
    #    número.
    #
    # 2. EL ESCALÓN. Un modelo que devuelve P(bloqueo) se binarizaba en 0.5 y
    #    después se aplicaba un factor fijo. Dos moléculas con p = 0.49 y
    #    p = 0.51 —indistinguibles para el modelo— recibían índices de
    #    viabilidad que se diferencian en un factor de más de dos.
    #
    # 3. LA MAGNITUD. Colapsar al 10 % es una constante que nadie calibró.
    #    Una auditoría externa propuso subirla a 0.5 llamándola «factor de
    #    seguridad calibrado»: sería igual de arbitraria, con la diferencia de
    #    que el nombre sugeriría que hay una calibración detrás. Cambiar una
    #    constante sin justificar por otra sin justificar, y presentarla como
    #    rigor, es peor que dejar la primera.
    #
    # LO QUE SE HACE. Se usa la probabilidad tal cual, de forma continua y
    # monótona, sin escalón ni constante mágica:
    #
    #     S_tox_hERG = 1 − p        p = P(bloqueo de hERG) según ADMET-AI
    #
    # Es la elección más simple que respeta lo único que el modelo sabe: su
    # propia probabilidad. Con p = 0.02 (aspirina) apenas mueve el índice; con
    # p = 0.95 lo reduce a la vigésima parte, que es donde el 0.1 anterior
    # quería estar. Y no hay ningún punto en el que un cambio de milésima en la
    # predicción produzca un salto en el resultado.
    #
    # LO QUE SIGUE SIN SABERSE, y por eso se declara arriba en el panel: este
    # índice NO incorpora el margen Cmax,libre/IC50, que es lo que decide el
    # riesgo clínico real. Un valor bajo aquí señala una molécula a mirar, no
    # una molécula peligrosa.
    S_tox = 1.0
    herg_prob = admet_preds.get("hERG_prob")
    if herg_prob is not None:
        S_tox *= max(0.05, 1.0 - float(herg_prob))
    elif admet_preds.get("hERG") == 1:
        # Corridas o modelos que sólo entregan la etiqueta: se conserva un
        # factor, pero moderado, y sin fingir que la etiqueta es una medida.
        S_tox *= 0.5
    if len(tabpfn_alerts) > 0:
        S_tox *= (0.8 ** len(tabpfn_alerts)) # Penalización progresiva

    # Geometric Mean de 3 parámetros
    viability = (S_sol * S_hia * S_tox) ** (1/3)
    properties.blood_viability_score = float(viability * 100)

    logger.info(f"Blood Viability calculated: {properties.blood_viability_score:.2f} (S_sol={S_sol:.2f}, S_hia={S_hia:.2f}, S_tox={S_tox:.2f})")

    return properties
