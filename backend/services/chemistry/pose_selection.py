"""
Selector de pose como EVIDENCIA: recomienda, no sustituye.

# Qué desacopla este módulo

`pose_selector v0.6` vivía dentro de `ModelManager.load_models()`, es decir:
sólo existía si el pipeline de RESCORING se cargaba, y se apagaba con los
ajustes de rescoring. Eso ataba una recomendación geométrica al camino de
XGBoost, que este producto sacó del camino obligatorio.

Aquí se carga el selector **directamente desde sus artefactos**, sin
`ModelManager`, sin `rescore()` y sin la etapa `xgb`. La única dependencia
compartida es `xgboost` como librería —el selector ES un `XGBRanker`—, que no
es lo mismo que reactivar el rescoring XGBoost como etapa requerida.

# La regla que gobierna el contrato

**La pose principal sigue siendo Vina top-1.** El selector emite una
recomendación con su confianza y su procedencia; nada la aplica en silencio.

    status=selected     hay recomendación, y se dice cuál y con qué margen
    status=abstained    el margen no llega al umbral: NO hay recomendación
    status=unavailable  el modelo no está, o la evaluación es anterior
    status=error        el selector falló

En los tres últimos casos la referencia es `vina_top1`, etiquetada como
**fallback** — no como un éxito del selector.

# Si la pose sugerida falla los controles físicos

No se elige otra automáticamente. Se declara `physical_review` y se listan las
alternativas que SÍ pasan, sin seleccionarlas. Elegir la siguiente por el
producto sería inventar una decisión que nadie tomó, y el selector no fue
entrenado para eso.

# Lo que este módulo NO toca

Ni afinidades, ni orden de poses, ni scores del rescoring, ni umbrales, ni
features, ni el modelo. La validación física tampoco cambia los scores del
selector: se leen juntos y se declaran juntos, pero no se contaminan.
"""

from __future__ import annotations

import hashlib
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from utils.logger import get_logger

log = get_logger(__name__)

#: Versión del contrato persistido. Aditiva.
POSE_SELECTION_SCHEMA_VERSION = 1

#: Contrato de esta etapa. Cambiarlo invalida la comparabilidad de lo guardado.
POSE_SELECTION_CONTRACT = "pose_selection/v1"

# ── Estados ──────────────────────────────────────────────────────────

STATUS_SELECTED = "selected"
STATUS_ABSTAINED = "abstained"
STATUS_UNAVAILABLE = "unavailable"
STATUS_ERROR = "error"

STATUSES = (STATUS_SELECTED, STATUS_ABSTAINED, STATUS_UNAVAILABLE, STATUS_ERROR)

#: Estrategia de referencia del producto. NO cambia en este sprint.
STRATEGY_VINA_TOP1 = "vina_top1"
#: Estrategia cuando el selector sí recomienda. Sigue siendo una recomendación.
STRATEGY_SELECTOR = "pose_selector_v06"

# ── Razones (estables) ───────────────────────────────────────────────

MODELO_AUSENTE = "MODELO_AUSENTE"
SIN_POSES = "SIN_POSES"
SIN_PDBQT_DE_POSE = "SIN_PDBQT_DE_POSE"
RECEPTOR_NO_DISPONIBLE = "RECEPTOR_NO_DISPONIBLE"
SELECTOR_FALLO = "SELECTOR_FALLO"
MARGEN_BAJO_UMBRAL = "MARGEN_BAJO_UMBRAL"
UNA_SOLA_POSE = "UNA_SOLA_POSE"
SELECCION_AUSENTE = "SELECCION_AUSENTE"

REASONS = (
    MODELO_AUSENTE, SIN_POSES, SIN_PDBQT_DE_POSE, RECEPTOR_NO_DISPONIBLE,
    SELECTOR_FALLO, MARGEN_BAJO_UMBRAL, UNA_SOLA_POSE, SELECCION_AUSENTE,
)

#: Estado físico de la pose sugerida frente a los controles oficiales.
FISICO_PASA = "passed"
FISICO_FALLA = "failed"
FISICO_REVISION = "review"
FISICO_NO_EVALUADO = "not_evaluated"


def _sha256_de(ruta: Path) -> str | None:
    try:
        return hashlib.sha256(ruta.read_bytes()).hexdigest()
    except OSError:
        return None


def rutas_de_artefactos() -> tuple[Path | None, Path | None]:
    """
    Dónde están el booster y su meta.

    Se respetan las variables de entorno que ya registra
    `services/rescoring_bridge.py` —es el registro central de paths del
    producto— pero NO se importa `ModelManager` ni se carga el rescoring. Se
    reutiliza la configuración, no el pipeline.
    """
    modelo = os.environ.get("RESCORING_POSE_SELECTOR_MODEL_PATH")
    meta = os.environ.get("RESCORING_POSE_SELECTOR_META_PATH")
    if not modelo or not meta:
        try:
            from services.rescoring_bridge import get_artifact_defaults, get_sidecar_dir

            defectos = get_artifact_defaults()
            artefactos = get_sidecar_dir() / "artifacts"
            modelo = modelo or str(artefactos / defectos["RESCORING_POSE_SELECTOR_MODEL_PATH"])
            meta = meta or str(artefactos / defectos["RESCORING_POSE_SELECTOR_META_PATH"])
        except Exception:                                      # noqa: BLE001
            return None, None
    return Path(modelo), Path(meta)


def _abstencion(status: str, razon: str, detalle: str, **extra: Any) -> dict[str, Any]:
    """
    Contrato sin recomendación. La referencia es Vina top-1, como FALLBACK.

    Se etiqueta así a propósito: un `vina_top1` porque el selector no habló no
    es lo mismo que un `vina_top1` elegido, y presentarlos igual convertiría
    una ausencia de recomendación en una recomendación.
    """
    return {
        "version_schema": POSE_SELECTION_SCHEMA_VERSION,
        "contract": POSE_SELECTION_CONTRACT,
        "status": status,
        "strategy": STRATEGY_VINA_TOP1,
        "strategy_is_fallback": True,
        "vina_top1_rank": extra.pop("vina_top1_rank", None),
        "selected_pose_rank": None,
        "confidence": None,
        "abstained": status == STATUS_ABSTAINED,
        "abstention_reason": razon,
        "detail": detalle,
        "pose_scores": [],
        "model": None,
        "inputs": {},
        "warnings": [],
        "suggested_pose_physical_status": None,
        # `None`, no `False`: sin recomendación no hay pose sugerida que
        # revisar, y decir `False` se leería como «revisada y en orden». La
        # clave existe en los cuatro estados para que un lector no tenga que
        # preguntar antes si puede preguntar.
        "physical_review": None,
        "physically_valid_alternatives": [],
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        **extra,
    }


def seleccion_ausente() -> dict[str, Any]:
    """
    Lo que se devuelve por una evaluación ANTERIOR a esta etapa.

    `unavailable`, no `error` y no `abstained`: nadie ejecutó el selector, así
    que no hay ni recomendación ni abstención que declarar. Presentarlo como
    error convertiría un hueco histórico en un fallo.
    """
    contrato = _abstencion(
        STATUS_UNAVAILABLE,
        SELECCION_AUSENTE,
        "Esta evaluación es anterior a la etapa de selección de pose. No se "
        "ejecutó el selector: no es que se abstuviera, es que no existía.",
    )
    # Sin hora de evaluación, y a propósito. Fechar con `now()` una etapa que
    # NO corrió inventa un dato, y además haría que dos lecturas del mismo
    # resultado antiguo devolvieran contratos distintos: suficiente para mover
    # el hash de un dossier sin que nada hubiera cambiado. Este sustituto es
    # una lectura, no una medición.
    contrato["evaluated_at"] = None
    return contrato


def pose_selection_para_lectura(guardado: Any) -> dict[str, Any]:
    """
    Lo que un lector recibe por `pose_selection`. NUNCA `None`.

    En la base de datos la columna sí es NULL para todo lo anterior a esta
    etapa —la migración es aditiva y no reescribe historia—, pero un `None`
    cruzando la API obliga a cada cliente a inventarse qué significa, y las
    tres respuestas posibles («no evaluada», «se abstuvo», «falló») no son
    intercambiables. Aquí se resuelve una sola vez: un resultado antiguo abre
    como `unavailable` con su razón, y la referencia declarada como fallback.

    Lo que la etapa sí escribió se devuelve TAL CUAL. Esta función normaliza
    la ausencia; no reinterpreta lo medido.
    """
    if isinstance(guardado, dict) and guardado:
        return guardado
    return seleccion_ausente()


def _campo(pose: Any, nombre: str, defecto: Any) -> Any:
    if isinstance(pose, dict):
        return pose.get(nombre, defecto)
    return getattr(pose, nombre, defecto)


def _estado_fisico_por_rank(structural_evidence: dict[str, Any] | None) -> dict[int, str]:
    """
    `rank -> estado físico` según la evidencia de P0-A.

    Se LEE, no se recalcula: la validación física ya corrió y su veredicto es
    el que vale. Recalcularlo aquí abriría la puerta a dos respuestas distintas
    sobre la misma pose.
    """
    if not isinstance(structural_evidence, dict):
        return {}
    salida: dict[int, str] = {}
    for entrada in structural_evidence.get("poses") or []:
        rank = entrada.get("rank")
        if isinstance(rank, int):
            salida[rank] = str(entrada.get("status") or FISICO_NO_EVALUADO)
    return salida


def build_pose_selection(
    *,
    poses: list[Any],
    receptor_pdb_path: str | Path | None,
    structural_evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Recomendación de pose, con su procedencia y su abstención. NUNCA lanza.

    `receptor_pdb_path` tiene que ser un PDB legible: el extractor de features
    lo necesita para las distancias al receptor. Se le pasa el MISMO receptor
    que se acopló, materializado por la etapa de validación física.
    """
    vina_top1 = None
    if poses:
        ordenadas = sorted(poses, key=lambda p: _campo(p, "rank", 10**6))
        vina_top1 = _campo(ordenadas[0], "rank", None)
    else:
        ordenadas = []

    if not ordenadas:
        return _abstencion(STATUS_UNAVAILABLE, SIN_POSES,
                           "La evaluación no conservó ninguna pose.")

    bloques = [_campo(p, "pdbqt_block", None) for p in ordenadas]
    if any(not b for b in bloques):
        return _abstencion(
            STATUS_UNAVAILABLE, SIN_PDBQT_DE_POSE,
            "Alguna pose no conservó su bloque PDBQT; el selector necesita las "
            "coordenadas de TODAS para comparar entre ellas.",
            vina_top1_rank=vina_top1,
        )

    if not receptor_pdb_path or not Path(receptor_pdb_path).exists():
        return _abstencion(
            STATUS_UNAVAILABLE, RECEPTOR_NO_DISPONIBLE,
            "No hay un PDB legible del receptor de esta corrida; sin él no se "
            "pueden extraer las distancias que el selector usa.",
            vina_top1_rank=vina_top1,
        )

    modelo_path, meta_path = rutas_de_artefactos()
    if not modelo_path or not meta_path or not modelo_path.exists() or not meta_path.exists():
        return _abstencion(
            STATUS_UNAVAILABLE, MODELO_AUSENTE,
            "El modelo del selector de pose no está en este runtime. La "
            "referencia sigue siendo Vina top-1.",
            vina_top1_rank=vina_top1,
        )

    modelo_info = {
        "name": None,
        "version": None,
        "model_path": modelo_path.name,
        "model_sha256": _sha256_de(modelo_path),
        "meta_sha256": _sha256_de(meta_path),
        "abstention_threshold": None,
    }

    try:
        from services.rescoring_bridge import get_sidecar_dir  # registra sys.path

        get_sidecar_dir()
        from pose_selector.selector import UMBRAL_ABSTENCION_DEFECTO, PoseSelector

        selector = PoseSelector(str(modelo_path), str(meta_path))
        modelo_info["abstention_threshold"] = float(selector.abstention_threshold)
        modelo_info["name"] = selector.nombre_modelo
        modelo_info["version"] = str((selector.meta or {}).get("modelo") or selector.nombre_modelo)
        if selector.load_error:
            return _abstencion(
                STATUS_UNAVAILABLE, MODELO_AUSENTE, selector.load_error,
                vina_top1_rank=vina_top1, model=modelo_info,
            )

        afinidades = [float(_campo(p, "affinity", 0.0)) for p in ordenadas]
        resultado, motivo = selector.seleccionar_pose(
            pose_blocks=list(bloques),
            vina_scores=afinidades,
            target_pdb_path=str(receptor_pdb_path),
        )
    except Exception as exc:                                   # noqa: BLE001
        log.warning("pose_selector_fallo_no_fatal", error=str(exc)[:200])
        return _abstencion(
            STATUS_ERROR, SELECTOR_FALLO,
            f"El selector lanzó {type(exc).__name__}. La referencia sigue siendo "
            f"Vina top-1.",
            vina_top1_rank=vina_top1, model=modelo_info,
        )

    if resultado is None:
        return _abstencion(
            STATUS_ERROR, SELECTOR_FALLO,
            f"El selector no pudo evaluar estas poses: {motivo}",
            vina_top1_rank=vina_top1, model=modelo_info,
        )

    # ── Hay salida del selector ──────────────────────────────────────
    # `selected_pose_rank` del selector es un índice 0-based sobre la lista que
    # se le pasó; se traduce al `rank` REAL de la pose para que el contrato
    # hable el mismo idioma que el resto del producto.
    indice = int(resultado["selected_pose_rank"])
    rank_sugerido = _campo(ordenadas[indice], "rank", indice + 1)
    abstenido = bool(resultado["pose_abstained"])
    confianza = float(resultado["pose_confidence"])
    scores = [
        {"rank": _campo(p, "rank", i + 1), "score": float(s)}
        for i, (p, s) in enumerate(zip(ordenadas, resultado["pose_scores"]))
    ]

    fisicos = _estado_fisico_por_rank(structural_evidence)
    estado_fisico = fisicos.get(rank_sugerido)

    # Alternativas que PASAN los controles oficiales. Se listan, no se eligen:
    # el selector no fue entrenado para escoger «la siguiente que pase», y
    # hacerlo por él sería inventar una decisión que nadie tomó.
    #
    # DOC 71, DEFECTO E2. La exclusión de `rank_sugerido` es correcta cuando el
    # selector SÍ recomendó algo: esa pose es la recomendación, no una
    # alternativa a sí misma. Pero cuando se ABSTIENE, `rank_sugerido` es la
    # candidata que descartó —lo que el contrato llama `would_have_suggested_
    # rank`— y no hay recomendación de la que sea alternativa.
    #
    # Excluirla ahí la hacía desaparecer de las DOS listas a la vez: no era la
    # recomendada, porque no hubo ninguna, y tampoco figuraba entre las
    # físicamente válidas aunque hubiera pasado los controles. Es el síntoma que
    # reportó la VM: «la pose #2 supera los controles y es la que el selector
    # habría elegido, pero se excluye de las alternativas».
    #
    # Se excluye sólo si hubo recomendación.
    def _alternativas(excluir: int | None) -> list[dict[str, Any]]:
        return [
            {"rank": r, "physical_status": e}
            for r, e in sorted(fisicos.items())
            if e == FISICO_PASA and r != excluir
        ]

    alternativas = _alternativas(rank_sugerido)

    if abstenido:
        contrato = _abstencion(
            STATUS_ABSTAINED,
            UNA_SOLA_POSE if len(ordenadas) == 1 else MARGEN_BAJO_UMBRAL,
            (
                "Una sola pose: no hay margen que medir, así que no hay "
                "recomendación."
                if len(ordenadas) == 1
                else f"El margen entre la primera y la segunda ({confianza:.6f}) no "
                f"llega al umbral de abstención "
                f"({modelo_info['abstention_threshold']}). El selector no "
                f"recomienda."
            ),
            vina_top1_rank=vina_top1,
            model=modelo_info,
        )
        # La abstención conserva TODO lo medido: los scores, la confianza y el
        # rank que habría sugerido. Tirarlos obligaría a recalcular para poder
        # auditar por qué se abstuvo.
        contrato.update({
            "confidence": confianza,
            "pose_scores": scores,
            "warnings": list(resultado.get("warnings") or []),
            "suggested_pose_physical_status": estado_fisico,
            # Sin recomendación no hay nada de lo que excluirse.
            "physically_valid_alternatives": _alternativas(None),
            "inputs": _inputs(ordenadas, receptor_pdb_path, structural_evidence),
            "would_have_suggested_rank": rank_sugerido,
        })
        return contrato

    # ── Recomendación ────────────────────────────────────────────────
    # `strategy` pasa a nombrar al selector, PERO la pose principal del producto
    # sigue siendo Vina top-1: este contrato es evidencia, no una sustitución.
    return {
        "version_schema": POSE_SELECTION_SCHEMA_VERSION,
        "contract": POSE_SELECTION_CONTRACT,
        "status": STATUS_SELECTED,
        "strategy": STRATEGY_SELECTOR,
        "strategy_is_fallback": False,
        "vina_top1_rank": vina_top1,
        "selected_pose_rank": rank_sugerido,
        "confidence": confianza,
        "abstained": False,
        "abstention_reason": None,
        "detail": (
            f"El selector recomienda la pose {rank_sugerido} con un margen de "
            f"{confianza:.6f}. Es una RECOMENDACIÓN: la pose principal del "
            f"producto sigue siendo la {vina_top1} de Vina."
        ),
        "pose_scores": scores,
        "model": modelo_info,
        "inputs": _inputs(ordenadas, receptor_pdb_path, structural_evidence),
        "warnings": list(resultado.get("warnings") or []),
        "suggested_pose_physical_status": estado_fisico,
        # Si la sugerida NO pasa los controles, se declara revisión y se
        # muestran las que sí pasan — sin elegir ninguna.
        #
        # `None` —nadie midió esta pose— TAMBIÉN es revisión. Dar por buena una
        # pose cuyo estado físico no se conoce sería afirmar lo que no se
        # comprobó, que es exactamente lo que la etapa anterior existe para
        # impedir. Sólo un `passed` explícito evita la revisión.
        "physical_review": estado_fisico != FISICO_PASA,
        "physically_valid_alternatives": alternativas,
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
    }


def _inputs(poses, receptor_pdb_path, structural_evidence) -> dict[str, Any]:
    """Con qué se alimentó el selector. Procedencia, no adorno."""
    return {
        "n_poses": len(poses),
        "pose_ranks": [_campo(p, "rank", None) for p in poses],
        "vina_affinities": [_campo(p, "affinity", None) for p in poses],
        "pose_pdbqt_source": "docking_poses[].pdbqt_block",
        "receptor_source": str(Path(receptor_pdb_path).name) if receptor_pdb_path else None,
        "structural_evidence_contract": (
            (structural_evidence or {}).get("version_schema")
            if isinstance(structural_evidence, dict)
            else None
        ),
    }


def build_pose_selection_for_run(
    *,
    poses: list[Any],
    target_pdb_id: str | None,
    receptor_sha256: str | None,
    receptor_bytes: bytes | None = None,
    structural_evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Orquestación para el pipeline: resuelve el receptor y llama al selector.

    Reutiliza EXACTAMENTE la resolución de receptor de la etapa de validación
    física —bytes congelados en cohortes, objeto del catálogo sólo si su
    SHA-256 coincide—. Si allí no hay veredicto por el receptor, aquí tampoco:
    dos etapas que discrepan sobre qué receptor se usó serían peor que una que
    se abstiene.

    NUNCA lanza. Cualquier fallo se convierte en `unavailable` o `error` con la
    referencia en `vina_top1` marcada como fallback.
    """
    receptor = None
    pdb = None
    try:
        from services.chemistry.pose_physical_validity import receptor_como_pdb
        from services.chemistry.structural_evidence import resolver_receptor

        receptor = resolver_receptor(
            target_pdb_id=target_pdb_id,
            receptor_sha256_esperado=receptor_sha256,
            receptor_bytes=receptor_bytes,
        )
        if receptor.razon is not None or receptor.path is None:
            return _abstencion(
                STATUS_UNAVAILABLE, RECEPTOR_NO_DISPONIBLE,
                "No se pudo usar el receptor exacto de esta corrida "
                f"({receptor.razon}); el selector no opina sobre otro.",
                vina_top1_rank=_campo(poses[0], "rank", None) if poses else None,
            )
        pdb = receptor_como_pdb(receptor.path)
        if pdb is None:
            return _abstencion(
                STATUS_UNAVAILABLE, RECEPTOR_NO_DISPONIBLE,
                "El receptor de esta corrida no se pudo convertir a PDB legible.",
                vina_top1_rank=_campo(poses[0], "rank", None) if poses else None,
            )
        return build_pose_selection(
            poses=poses,
            receptor_pdb_path=pdb,
            structural_evidence=structural_evidence,
        )
    except Exception as exc:                                   # noqa: BLE001
        log.warning("pose_selection_fallo_no_fatal", error=str(exc)[:200])
        return _abstencion(
            STATUS_ERROR, SELECTOR_FALLO,
            f"La etapa de selección lanzó {type(exc).__name__}. El acoplamiento "
            f"de esta evaluación NO se ve afectado.",
        )
    finally:
        if pdb is not None and receptor is not None and receptor.path is not None:
            try:
                if Path(pdb).resolve() != Path(receptor.path).resolve():
                    Path(pdb).unlink(missing_ok=True)
            except OSError:
                pass
        if receptor is not None:
            receptor.cerrar()
