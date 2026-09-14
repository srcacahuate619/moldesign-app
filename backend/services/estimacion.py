r"""Cuánto va a tardar esta corrida, dicho ANTES de pulsar «Evaluar».

# Por qué existía uno y no servía

`core/hardware.py` ya traía `estimate_evaluation_time()`, pero: (a) no lo
importaba nadie —`ProConfigPanel` es código muerto— y (b) su modelo era una
tabla de tres casos sobre los núcleos físicos y nada más:

    base = 45;  if cores >= 8: base = 25;  elif cores >= 4: base = 35

Medido el 2026-09-14 sobre 1WBM, mismo ligando y misma caja, sólo cambiando
cuántos núcleos se le daban a Vina:

    12 núcleos   36.2 s        exhaustiveness 8
     8 núcleos   34.2 s
     4 núcleos   55.2 s        la tabla decía 35
     2 núcleos  102.7 s        la tabla decía 45  ← 2.3x por debajo
    12 núcleos  101.9 s        exhaustiveness 32  ← la tabla lo ignora

Lo que la tabla no veía es lo que más manda: **la exhaustiveness triplica el
tiempo** (3.0x de 8 a 32) y los núcleos escalan por tandas. La caja apenas pesa
(1.25x al pasar de 22.5³ a 30³ Å, que es 2.37x de volumen).

# El modelo, y por qué es el que es

`exhaustiveness` en Vina es el NÚMERO DE BÚSQUEDAS Monte Carlo independientes.
Se reparten entre los hilos disponibles, así que el tiempo va por tandas:

    tandas = max(1, ceil(exhaustiveness / cpu))
    segundos ≈ segundos_por_tanda * tandas * factor_caja

Se ve en los datos: con 8 núcleos y exhaustiveness 8 (una tanda) son 34 s, y con
12 núcleos y exhaustiveness 32 (tres tandas) son 102 s — tres veces. Y por eso
darle a Vina más núcleos que exhaustiveness no compra nada: 12 y 8 dan el mismo
número.

# Lo que NO se modela, a propósito

**El tamaño del ligando.** Es sabido que Vina tarda más con más enlaces
rotables, pero aquí sólo se midió UN ligando. Aplicar un factor que no se ha
medido sería inventar un número con aspecto de medida, que es exactamente lo
que este producto no hace. En su lugar, un ligando atípico ENSANCHA EL RANGO: se
declara la incertidumbre en vez de fingir precisión.

**La velocidad de la máquina del usuario.** Las constantes de arriba son de la
máquina donde se midió. En otra son otras, y no hay forma de saberlo sin correr
algo. Por eso la primera estimación es ancha y honesta —lo dice—, y a partir de
la primera corrida terminada se CALIBRA con lo observado en ese equipo.
"""

from __future__ import annotations

import json
import math
import statistics
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from utils.logger import get_logger

log = get_logger(__name__)

# ── Constantes medidas ──────────────────────────────────────────────────────
#
# Todas del 2026-09-14, sobre el runtime empaquetado: 1WBM (proteasa del VIH,
# multicadena), caja 30³ Å, ligando de 40 átomos pesados, Vina 1.2.

#: Segundos de UNA tanda de búsquedas. Mediana de las cinco medidas; el rango
#: observado fue 25.7-36.2, que es la dispersión que hereda la banda.
SEGUNDOS_POR_TANDA = 34.0

#: Volumen de caja de referencia, en Å³. El de 1WBM, con el que se midió.
VOLUMEN_REFERENCIA = 27000.0

#: Cómo pesa la caja. De 11391 a 27000 Å³ (2.37x) el tiempo subió 1.25x:
#: ln(1.25)/ln(2.37) = 0.26. Es débil porque el volumen afecta al mapa de
#: rejilla, no a la búsqueda.
EXPONENTE_CAJA = 0.26

#: Preparar un receptor que todavía no lo está. Medido: 8.79 s en frío contra
#: 0.05 s en caliente. Se paga UNA vez por receptor y por eso se declara aparte:
#: es justo la diferencia que hizo que una primera corrida pareciera rota.
SEGUNDOS_PREPARAR_RECEPTOR = 8.8

#: El resto del proceso que no es acoplar: validar, propiedades, confórmeros,
#: rescoring. Medido como diferencia entre la evaluación completa y el docking.
SEGUNDOS_TUBERIA_FIJOS = 6.0

#: Vina se mata a los 600 s por acoplamiento (`vina_service.py`). Una estimación
#: por encima no es lentitud: es un fallo seguro, y hay que decirlo ANTES.
TIMEOUT_DOCKING_S = 600.0

#: Ligando de referencia, en enlaces rotables. Fuera de esta banda no se cambia
#: la estimación —no se midió— pero se ensancha el rango.
ROTABLES_TIPICOS = (0, 10)

#: Cuántas observaciones hacen falta para fiarse del historial por encima del
#: modelo. Con menos, la mediana de una muestra diminuta engaña más que ayuda.
MINIMO_PARA_CALIBRAR = 3

#: Cuántas se conservan. Las viejas dejan de describir la máquina de hoy.
MAXIMO_OBSERVACIONES = 60


@dataclass(frozen=True)
class Banda:
    """Un rango de segundos y en qué se apoya."""

    minimo: float
    maximo: float


def _fichero_de_calibracion() -> Path:
    from utils.local_storage import data_dir

    return data_dir() / "calibracion" / "docking.json"


def _leer_observaciones() -> list[dict[str, Any]]:
    ruta = _fichero_de_calibracion()
    try:
        if not ruta.is_file():
            return []
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        return datos.get("observaciones", []) if isinstance(datos, dict) else []
    except (OSError, ValueError):
        # Un fichero de calibración ilegible no puede tumbar una evaluación: se
        # pierde la calibración, no el producto.
        return []


def registrar_docking(
    *,
    segundos: float,
    cpu: int,
    exhaustiveness: int,
    volumen_caja: float,
    atomos_pesados: int | None = None,
) -> None:
    """Anota lo que tardó un acoplamiento REAL en esta máquina.

    Es lo que convierte la estimación de una tabla en una medida. Se llama al
    terminar cada acoplamiento; un fallo al escribir no interrumpe nada.
    """
    if segundos <= 0 or cpu <= 0 or exhaustiveness <= 0:
        return
    tandas = max(1, math.ceil(exhaustiveness / cpu))
    muestra = {
        "cuando": time.time(),
        "segundos": round(float(segundos), 2),
        "cpu": int(cpu),
        "exhaustiveness": int(exhaustiveness),
        "volumen_caja": round(float(volumen_caja), 1),
        "tandas": tandas,
        # Lo que de verdad se calibra: cuánto cuesta una tanda AQUÍ, ya
        # descontado el reparto entre núcleos y el tamaño de la caja.
        "segundos_por_tanda": round(
            float(segundos) / tandas / _factor_caja(volumen_caja), 2
        ),
        **({"atomos_pesados": int(atomos_pesados)} if atomos_pesados else {}),
    }
    try:
        ruta = _fichero_de_calibracion()
        ruta.parent.mkdir(parents=True, exist_ok=True)
        observaciones = [*_leer_observaciones(), muestra][-MAXIMO_OBSERVACIONES:]
        ruta.write_text(
            json.dumps({"observaciones": observaciones}, indent=2),
            encoding="utf-8",
        )
    except OSError as exc:
        log.warning("calibracion_no_escrita", error=str(exc)[:120])


def _factor_caja(volumen: float) -> float:
    if volumen <= 0:
        return 1.0
    return (volumen / VOLUMEN_REFERENCIA) ** EXPONENTE_CAJA


def _segundos_por_tanda_observados() -> tuple[float, float, int] | None:
    """`(p25, p75, n)` de lo observado en esta máquina, o `None` si hay poco."""
    muestras = [
        float(o["segundos_por_tanda"])
        for o in _leer_observaciones()
        if isinstance(o.get("segundos_por_tanda"), (int, float))
        and o["segundos_por_tanda"] > 0
    ]
    if len(muestras) < MINIMO_PARA_CALIBRAR:
        return None
    muestras.sort()
    def cuantil(q: float) -> float:
        return muestras[min(len(muestras) - 1, int(len(muestras) * q))]
    # Con pocas muestras los cuantiles se pegan; se abre un mínimo del 15% para
    # no prometer una precisión que tres corridas no sostienen.
    p25, p75 = cuantil(0.25), cuantil(0.75)
    mediana = statistics.median(muestras)
    p25 = min(p25, mediana * 0.85)
    p75 = max(p75, mediana * 1.15)
    return p25, p75, len(muestras)


def estimar_corrida(
    *,
    cpu: int,
    exhaustiveness: int,
    conformers: int = 1,
    volumen_caja: float = VOLUMEN_REFERENCIA,
    receptor_preparado: bool = True,
    rotables_del_ligando: int | None = None,
    anti_targets: int = 0,
    docks_en_paralelo: int = 1,
    usa_mmgbsa: bool = False,
    gpu_cuda: bool = False,
    gpu_opencl: bool = False,
    ligandos: int = 1,
) -> dict[str, Any]:
    """Estima una corrida: una molécula, un ensemble o una cohorte entera.

    `ligandos` es lo que separa los tres casos: 1 para una evaluación, N para
    una cohorte de Batch. Todo lo demás se comparte, porque el coste por ligando
    es el mismo; lo que cambia es cuántos se pagan y cuántos caben a la vez.
    """
    cpu = max(1, int(cpu))
    exhaustiveness = max(1, int(exhaustiveness))
    conformers = max(1, int(conformers))
    ligandos = max(1, int(ligandos))

    tandas = max(1, math.ceil(exhaustiveness / cpu))
    factor_caja = _factor_caja(volumen_caja)

    observado = _segundos_por_tanda_observados()
    if observado is not None:
        p25, p75, n = observado
        base_min, base_max = p25, p75
        apoyo = "historial"
        detalle_apoyo = (
            f"Calibrado con {n} acoplamiento{'s' if n != 1 else ''} "
            "que ya se ejecutaron en este equipo."
        )
    else:
        # Sin historial las constantes son de OTRA máquina. La banda tiene que
        # decirlo con su anchura, no sólo con una nota al pie.
        base_min, base_max = SEGUNDOS_POR_TANDA * 0.6, SEGUNDOS_POR_TANDA * 2.2
        apoyo = "modelo"
        detalle_apoyo = (
            "Todavía no hay corridas terminadas en este equipo, así que esto sale "
            "de un modelo medido en otra máquina. Se ajustará solo en cuanto "
            "termine la primera."
        )

    por_acoplamiento_min = base_min * tandas * factor_caja
    por_acoplamiento_max = base_max * tandas * factor_caja

    # Un ligando lejos de lo típico no cambia el centro —no se midió— pero sí
    # la confianza. Ensanchar es declarar que no se sabe; multiplicar sería
    # inventar.
    ligando_atipico = (
        rotables_del_ligando is not None
        and not (ROTABLES_TIPICOS[0] <= rotables_del_ligando <= ROTABLES_TIPICOS[1])
    )
    if ligando_atipico:
        por_acoplamiento_max *= 2.0

    etapas: list[dict[str, Any]] = []

    # Los acoplamientos: un confórmero es un acoplamiento más.
    acoplamientos_por_ligando = conformers * (1 + max(0, int(anti_targets)))
    paralelos = max(1, min(int(docks_en_paralelo), acoplamientos_por_ligando * ligandos))
    total_acoplamientos = acoplamientos_por_ligando * ligandos
    oleadas = math.ceil(total_acoplamientos / paralelos)

    dock_min = por_acoplamiento_min * oleadas
    dock_max = por_acoplamiento_max * oleadas
    etapas.append({
        "etapa": "Acoplamiento",
        "segundos_min": round(dock_min),
        "segundos_max": round(dock_max),
        "nota": (
            f"{total_acoplamientos} acoplamiento{'s' if total_acoplamientos != 1 else ''}"
            + (f" en {oleadas} tanda{'s' if oleadas != 1 else ''} de {paralelos}" if paralelos > 1 else "")
            + f" · exhaustiveness {exhaustiveness} sobre {cpu} núcleo{'s' if cpu != 1 else ''}"
        ),
    })

    total_min = dock_min
    total_max = dock_max

    # El resto de la tubería, por ligando.
    tuberia = SEGUNDOS_TUBERIA_FIJOS * ligandos
    etapas.append({
        "etapa": "Preparación del ligando y análisis",
        "segundos_min": round(tuberia),
        "segundos_max": round(tuberia * 2),
        "nota": "Validación, propiedades, confórmeros y rescoring.",
    })
    total_min += tuberia
    total_max += tuberia * 2

    # El coste de UNA vez. Es lo único aquí que se sabe sin modelo: o el
    # `.pdbqt` está en disco o no está.
    unica_vez: dict[str, Any] | None = None
    if not receptor_preparado:
        unica_vez = {
            "etapa": "Preparar el receptor",
            "segundos_min": round(SEGUNDOS_PREPARAR_RECEPTOR),
            "segundos_max": round(SEGUNDOS_PREPARAR_RECEPTOR * 3),
            "nota": (
                "Este receptor aún no está preparado en este equipo. Se hace una "
                "sola vez: las siguientes corridas contra él se lo saltan."
            ),
        }
        total_min += SEGUNDOS_PREPARAR_RECEPTOR
        total_max += SEGUNDOS_PREPARAR_RECEPTOR * 3

    if usa_mmgbsa:
        if gpu_cuda:
            gbsa_min, gbsa_max, nota = 15.0, 30.0, "Acelerado por GPU CUDA."
        elif gpu_opencl:
            gbsa_min, gbsa_max, nota = 30.0, 60.0, "GPU OpenCL."
        else:
            gbsa_min, gbsa_max, nota = 120.0, 300.0, "Sin GPU: corre en CPU y es lento."
        etapas.append({
            "etapa": "MM-GBSA",
            "segundos_min": round(gbsa_min * ligandos),
            "segundos_max": round(gbsa_max * ligandos),
            "nota": nota,
        })
        total_min += gbsa_min * ligandos
        total_max += gbsa_max * ligandos

    avisos: list[str] = []
    if por_acoplamiento_max > TIMEOUT_DOCKING_S:
        avisos.append(
            f"Con esta configuración un solo acoplamiento podría superar el límite de "
            f"{int(TIMEOUT_DOCKING_S)} segundos y la corrida fallaría. Baja la "
            "exhaustiveness o usa una caja más pequeña."
        )
    if ligando_atipico and rotables_del_ligando is not None:
        avisos.append(
            f"Este ligando tiene {rotables_del_ligando} enlaces rotables, fuera de lo "
            "habitual. El tiempo real puede irse bastante por encima."
        )
    if tandas > 1 and cpu < exhaustiveness:
        avisos.append(
            f"Tu equipo tiene {cpu} núcleo{'s' if cpu != 1 else ''} y la exhaustiveness "
            f"es {exhaustiveness}: las búsquedas van en {tandas} tandas. Bajarla a {cpu} "
            "haría la corrida más rápida sin cambiar el receptor ni la caja."
        )

    return {
        "segundos_min": round(total_min),
        "segundos_max": round(total_max),
        "apoyo": apoyo,
        "detalle_apoyo": detalle_apoyo,
        "etapas": etapas,
        "una_vez": unica_vez,
        "avisos": avisos,
        "ligandos": ligandos,
    }
