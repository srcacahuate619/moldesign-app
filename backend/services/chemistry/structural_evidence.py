"""
Evidencia estructural de una evaluación: conectar la validación al flujo real.

# Qué añade este módulo, y qué NO

`pose_physical_validity.evaluar_pose_fisica` ya sabía emitir un veredicto sobre
UNA pose. Lo que faltaba era el puente hacia producción: de dónde salen el
receptor exacto, la plantilla química y el mapa atómico de una corrida real, y
dónde se guarda el resultado para que no haya que recalcularlo.

Este módulo **no cambia ni un umbral científico**. Ni reordena poses, ni toca la
afinidad, ni interviene en el selector. Sólo recoge lo que la corrida produjo,
se lo da al validador tal cual, y persiste lo que éste conteste.

# El receptor tiene que ser EL de la corrida, o no hay veredicto

El `.pdbqt` preparado del catálogo es mutable: repreparar el receptor lo
reescribe con el mismo nombre. Validar contra «el que hay ahora» produciría un
veredicto sobre un receptor que no es el que se acopló.

Por eso el docking devuelve el SHA-256 de lo que usó, y aquí se comprueba antes
de validar:

    · cohorte  → `cohort_runs.receptor_prepared_bytes`, que es inmutable;
    · caso     → el objeto del catálogo, **sólo si su hash coincide**.

Si no coincide, o no está, se emite `not_evaluated` con la razón. Nunca se
sustituye por otro receptor.

# La plantilla y el mapa NO se infieren

La química no puede salir de los tipos AutoDock (`A` es carbono aromático, `NA`
nitrógeno aceptor). Meeko escribe en el propio PDBQT dos REMARK que sí son
declaraciones:

    REMARK SMILES        <smiles de la molécula preparada>
    REMARK SMILES IDX    <serial_pdbqt> <indice_smiles> ...

Vina los copia a las poses de salida. De ahí salen plantilla e `index_map`, y
los dos vienen del MISMO artefacto, así que son consistentes por construcción.

Si los REMARK no están, se pasa el SMILES canónico de la molécula como ruta de
respaldo **declarada** (el lector la marca `plantilla_heuristica`), y si tampoco
hay SMILES, se abstiene. En ningún caso se adivina el grafo.

# Degradación

Ninguna clase de fallo aquí puede tumbar el docking. Una evaluación con
`structural_evidence.stage_status == "not_evaluated"` sigue siendo una
evaluación completada: la etapa se declara no evaluada, con su razón, y el
resultado científico del acoplamiento se conserva intacto.
"""

from __future__ import annotations

import hashlib
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from utils.logger import get_logger

log = get_logger(__name__)

#: Versión del contrato persistido. Aditiva: subir sólo con nota de
#: compatibilidad, y los lectores tienen que tolerar versiones menores.
STRUCTURAL_EVIDENCE_SCHEMA_VERSION = 1

#: Estrategia de pose principal EN ESTE SPRINT. El selector llega después; el
#: campo existe desde ya para que su llegada no obligue a migrar nada.
POSE_STRATEGY_VINA_TOP1 = "vina_top1"

#: Estados de la etapa. Mismo vocabulario que el de una pose, a propósito:
#: quien lea uno entiende el otro.
STAGE_PASSED = "passed"
STAGE_FAILED = "failed"
STAGE_REVIEW = "review"
STAGE_NOT_EVALUATED = "not_evaluated"

# ── Razones de abstención (estables) ─────────────────────────────────

SIN_POSES = "SIN_POSES"
SIN_PDBQT_DE_POSE = "SIN_PDBQT_DE_POSE"
RECEPTOR_AUSENTE = "RECEPTOR_AUSENTE"
RECEPTOR_NO_COINCIDE = "RECEPTOR_NO_COINCIDE"
RECEPTOR_SIN_HUELLA = "RECEPTOR_SIN_HUELLA"
SIN_PLANTILLA = "SIN_PLANTILLA"
#: El PDBQT trae hidrogenos polares declarados en `REMARK H PARENT` y el mapa de
#: `SMILES IDX` no los cubre. NO se resuelve adivinando a que atomo pertenecen:
#: la convencion de indices de Meeko para esos parents no esta verificada contra
#: la libreria en este entorno, y colocar un hidrogeno en el atomo equivocado
#: seria exactamente la inferencia quimica que este contrato prohibe.
MAPA_SIN_HIDROGENOS_POLARES = "MAPA_SIN_HIDROGENOS_POLARES"
VALIDADOR_NO_DISPONIBLE = "VALIDADOR_NO_DISPONIBLE"
EVIDENCIA_AUSENTE = "EVIDENCIA_AUSENTE"

ABSTENTION_REASONS = (
    SIN_POSES,
    SIN_PDBQT_DE_POSE,
    RECEPTOR_AUSENTE,
    RECEPTOR_NO_COINCIDE,
    RECEPTOR_SIN_HUELLA,
    SIN_PLANTILLA,
    MAPA_SIN_HIDROGENOS_POLARES,
    VALIDADOR_NO_DISPONIBLE,
    EVIDENCIA_AUSENTE,
)

_REMARK_SMILES = re.compile(r"^REMARK\s+SMILES\s+(?!IDX)(\S.*)$", re.MULTILINE)
_REMARK_IDX = re.compile(r"^REMARK\s+SMILES\s+IDX\s+(.*)$", re.MULTILINE)
#: Meeko declara aparte los hidrogenos polares que SI escribe en el PDBQT. Sus
#: seriales no aparecen en `SMILES IDX` porque no son atomos del SMILES de
#: partida, y por eso el lector no los encuentra en el mapa.
_REMARK_H_PARENT = re.compile(r"^REMARK\s+H\s+PARENT\s*(.*)$", re.MULTILINE)


def _sha256(datos: bytes) -> str:
    return hashlib.sha256(datos).hexdigest()


def seriales_de_hidrogeno_polar(pose_pdbqt: str) -> set[int]:
    """
    Seriales que Meeko DECLARA como hidrogenos polares en `REMARK H PARENT`.

    Se leen de la declaracion del preparador, no de los tipos AutoDock. Sirven
    para decir con precision por que un mapa no cubre todos los seriales, en vez
    de reportar un generico «serial ausente» que no le dice a nadie que hacer.
    """
    seriales: set[int] = set()
    for bloque in _REMARK_H_PARENT.findall(pose_pdbqt or ""):
        campos = bloque.split()
        # Pares `<indice_del_padre_en_el_SMILES> <serial_del_H_en_el_PDBQT>`,
        # el mismo orden que `SMILES IDX`. Comprobado sobre salida real: para
        # el paracetamol, `4 11 9 13` declara que el serial 11 es el H del
        # atomo 4 -el N de la amida- y el 13 el del atomo 9 -el O del fenol-.
        # Solo se toma el SERIAL: colocar el hidrogeno en el atomo del padre
        # exige asumir que ese padre tiene exactamente uno, y esa suposicion no
        # se hace aqui.
        for i in range(0, len(campos) - 1, 2):
            try:
                seriales.add(int(campos[i + 1]))
            except ValueError:
                continue
    return seriales


# ── Plantilla e index_map, sin inferir química ───────────────────────


def extraer_plantilla_y_mapa(pose_pdbqt: str) -> tuple[Any, list[tuple[int, int]] | None, str]:
    """
    Plantilla química e `index_map` desde los REMARK que escribe Meeko.

    Devuelve `(mol, index_map, procedencia)`. `procedencia` nombra de dónde
    salió cada cosa para que quede en la evidencia; no es decorativo: es la
    diferencia entre «la química la declaró el preparador» y «la dedujo alguien».

    Los pares de `REMARK SMILES IDX` van en el orden `serial indice serial
    indice…`. Un número impar de campos, un valor no entero o un SMILES que
    RDKit no lee dejan `index_map` en `None`: se prefiere la ruta de respaldo
    declarada antes que un mapa a medias.
    """
    try:
        from rdkit import Chem
    except ImportError:
        return None, None, "rdkit_no_disponible"

    m_smiles = _REMARK_SMILES.search(pose_pdbqt or "")
    if not m_smiles:
        return None, None, "sin_remark_smiles"
    smiles = m_smiles.group(1).strip()
    plantilla = Chem.MolFromSmiles(smiles)
    if plantilla is None:
        return None, None, "remark_smiles_ilegible"

    # El lector necesita un conformero sobre el que ESCRIBIR las coordenadas del
    # PDBQT. Se crea vacio (ceros) y NO es una coordenada inventada que pueda
    # llegar a la salida: el lector rechaza la pose si algun atomo PESADO se
    # queda sin coordenada del archivo, y elimina los hidrogenos que no la
    # traen en vez de dejarles la de la plantilla. Todo lo que sobrevive tiene
    # coordenada del PDBQT y solo del PDBQT.
    if plantilla.GetNumConformers() == 0:
        from rdkit.Chem import AllChem  # noqa: PLC0415
        from rdkit.Geometry import Point3D  # noqa: PLC0415

        conf = AllChem.Conformer(plantilla.GetNumAtoms())
        for i in range(plantilla.GetNumAtoms()):
            conf.SetAtomPosition(i, Point3D(0.0, 0.0, 0.0))
        plantilla.AddConformer(conf, assignId=True)

    pares: list[tuple[int, int]] = []
    for bloque in _REMARK_IDX.findall(pose_pdbqt or ""):
        campos = bloque.split()
        if len(campos) % 2 != 0:
            return plantilla, None, "remark_idx_impar"
        try:
            valores = [int(c) for c in campos]
        except ValueError:
            return plantilla, None, "remark_idx_no_entero"
        # ORDEN DEL FORMATO: `<indice_en_el_SMILES> <serial_en_el_PDBQT>`, y no
        # al reves. Se comprobo sobre salidas REALES de Meeko en este
        # repositorio: para `CC(=O)Nc1ccc(O)cc1` los indices usados son 1..11
        # -los once atomos pesados- y los seriales 1..10 y 12; leerlo al reves
        # produce un indice 12 que no existe en una molecula de once atomos, y
        # el lector se abstiene sin poder decir por que.
        #
        # `index_map` del lector es `serial -> indice(0-based)`, asi que se
        # invierte aqui y se pasa el indice a base 0.
        pares.extend((valores[i + 1], valores[i] - 1) for i in range(0, len(valores), 2))

    if not pares:
        return plantilla, None, "remark_smiles_sin_idx"

    # ── Hidrogenos polares declarados ────────────────────────────────
    # Meeko escribe en el PDBQT los H polares y los declara aparte, con SU
    # ATOMO PADRE. Sin ellos en el mapa, el lector se abstiene y toda molecula
    # con un OH o un NH se queda sin veredicto — que en un catalogo de farmacos
    # es casi todo.
    #
    # Se cierra usando la DECLARACION, no una inferencia: se anaden hidrogenos
    # explicitos a la plantilla y se asigna cada serial al H del padre que Meeko
    # nombro. **Si ese padre tiene mas de un hidrogeno, se ABANDONA el mapa**:
    # elegir cual seria exactamente la suposicion quimica que este contrato
    # prohibe, y una abstencion cuesta menos que un veredicto sobre la molecula
    # equivocada.
    padres = _pares_h_parent(pose_pdbqt)
    if padres:
        plantilla_con_h, extra, ok = _mapear_hidrogenos_polares(Chem, plantilla, padres)
        if not ok:
            return plantilla, pares, "meeko_remark_smiles_idx_sin_h_polares"
        return plantilla_con_h, [*pares, *extra], "meeko_remark_smiles_idx_con_h_polares"

    return plantilla, pares, "meeko_remark_smiles_idx"


def _pares_h_parent(pose_pdbqt: str) -> list[tuple[int, int]]:
    """`(indice_del_padre_0based, serial_del_H)` tal como los declara Meeko."""
    salida: list[tuple[int, int]] = []
    for bloque in _REMARK_H_PARENT.findall(pose_pdbqt or ""):
        campos = bloque.split()
        for i in range(0, len(campos) - 1, 2):
            try:
                salida.append((int(campos[i]) - 1, int(campos[i + 1])))
            except ValueError:
                continue
    return salida


def _mapear_hidrogenos_polares(Chem, plantilla, padres):
    """
    Plantilla con H explicitos y las entradas de mapa de los H polares.

    Devuelve `(plantilla, entradas, ok)`. `ok=False` en cuanto algo no se puede
    afirmar sin suponer: un padre fuera de rango, un padre sin hidrogenos, o un
    padre con MAS DE UNO —donde no hay forma de saber cual escribio Meeko—.
    """
    try:
        con_h = Chem.AddHs(Chem.Mol(plantilla))
    except Exception:                                          # noqa: BLE001
        return plantilla, [], False

    from rdkit.Chem import AllChem  # noqa: PLC0415
    from rdkit.Geometry import Point3D  # noqa: PLC0415

    if con_h.GetNumConformers() == 0:
        conf = AllChem.Conformer(con_h.GetNumAtoms())
        for i in range(con_h.GetNumAtoms()):
            conf.SetAtomPosition(i, Point3D(0.0, 0.0, 0.0))
        con_h.AddConformer(conf, assignId=True)

    entradas: list[tuple[int, int]] = []
    usados: set[int] = set()
    for indice_padre, serial in padres:
        if not 0 <= indice_padre < con_h.GetNumAtoms():
            return plantilla, [], False
        hidrogenos = [
            v.GetIdx()
            for v in con_h.GetAtomWithIdx(indice_padre).GetNeighbors()
            if v.GetAtomicNum() == 1 and v.GetIdx() not in usados
        ]
        # Cero: la declaracion no cuadra con la plantilla. Mas de uno: no hay
        # forma de saber cual es. En ambos casos se abandona.
        if len(hidrogenos) != 1:
            return plantilla, [], False
        usados.add(hidrogenos[0])
        entradas.append((serial, hidrogenos[0]))
    return con_h, entradas, True


# ── Receptor exacto, o abstención ────────────────────────────────────


class ReceptorParaValidar:
    """Ruta legible del receptor de ESTA corrida, o la razón por la que no la hay."""

    def __init__(self, path: Path | None, sha256: str | None, razon: str | None,
                 fuente: str, _tmp: Any = None):
        self.path = path
        self.sha256 = sha256
        self.razon = razon
        self.fuente = fuente
        self._tmp = _tmp

    def cerrar(self) -> None:
        if self._tmp is not None:
            self._tmp.cleanup()
            self._tmp = None


def resolver_receptor(
    *,
    target_pdb_id: str | None,
    receptor_sha256_esperado: str | None,
    receptor_bytes: bytes | None = None,
) -> ReceptorParaValidar:
    """
    Materializa el receptor **que se acopló**, o explica por qué no puede.

    `receptor_bytes` es el camino fuerte y lo usan las cohortes: la corrida
    congeló esos bytes al abrirse y no dependen de nada mutable.

    Sin ellos se recurre al objeto del catálogo, y entonces el hash NO es un
    adorno: si no coincide con el que registró el docking, el receptor se
    repreparó desde entonces y validar contra él daría un veredicto sobre otra
    estructura. Se abstiene.
    """
    if receptor_bytes:
        real = _sha256(bytes(receptor_bytes))
        if receptor_sha256_esperado and real != receptor_sha256_esperado:
            return ReceptorParaValidar(
                None, real, RECEPTOR_NO_COINCIDE,
                "cohort_runs.receptor_prepared_bytes",
            )
        # `ignore_cleanup_errors`: en Windows no se puede borrar un archivo que
        # alguien tenga abierto, y aqui dentro corren procesos hijos -Meeko, Vina,
        # Open Babel- mas el antivirus escaneando lo recien escrito. Sin esto, la
        # limpieza puede levantar PermissionError DESPUES de que el trabajo haya
        # terminado bien, y tirar una corrida completa por no poder borrar un
        # temporal. Dejar un archivo suelto es mucho mejor que perder el resultado.
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True, prefix="moldesign_pv_")
        destino = Path(tmp.name) / "receptor.pdbqt"
        destino.write_bytes(bytes(receptor_bytes))
        return ReceptorParaValidar(destino, real, None,
                                   "cohort_runs.receptor_prepared_bytes", tmp)

    if not target_pdb_id:
        return ReceptorParaValidar(None, None, RECEPTOR_AUSENTE, "sin_receptor_declarado")

    try:
        from utils.file_handlers import StoragePath
        from utils.local_storage import path_for

        ruta = path_for(StoragePath.target_prepared(target_pdb_id))
    except Exception:
        return ReceptorParaValidar(None, None, RECEPTOR_AUSENTE, "almacenamiento_no_resuelto")

    if not ruta.exists():
        return ReceptorParaValidar(None, None, RECEPTOR_AUSENTE,
                                   f"targets/{target_pdb_id}/prepared.pdbqt")
    real = _sha256(ruta.read_bytes())
    if not receptor_sha256_esperado:
        # El docking no registró qué receptor usó. No se supone que sea éste:
        # se dice que no se puede afirmar, que es distinto.
        return ReceptorParaValidar(None, real, RECEPTOR_SIN_HUELLA,
                                   f"targets/{target_pdb_id}/prepared.pdbqt")
    if real != receptor_sha256_esperado:
        return ReceptorParaValidar(None, real, RECEPTOR_NO_COINCIDE,
                                   f"targets/{target_pdb_id}/prepared.pdbqt")
    return ReceptorParaValidar(ruta, real, None, f"targets/{target_pdb_id}/prepared.pdbqt")


# ── Construcción de la evidencia ─────────────────────────────────────


def _abstencion_de_etapa(razon: str, detalle: str, **extra: Any) -> dict[str, Any]:
    """
    Etapa sin veredicto. **No es una pose inválida**, y el texto lo dice.

    Es la distinción que este producto no puede perder: `not_evaluated` describe
    lo que le pasó al validador, nunca a la molécula.
    """
    return {
        "version_schema": STRUCTURAL_EVIDENCE_SCHEMA_VERSION,
        "stage_status": STAGE_NOT_EVALUATED,
        "reason_code": razon,
        "detail": detalle,
        "pose_strategy": POSE_STRATEGY_VINA_TOP1,
        "primary_pose_rank": None,
        "poses_produced": 0,
        "poses_evaluated": 0,
        "coverage": None,
        "receptor_sha256": None,
        "validation_engine": None,
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "poses": [],
        **extra,
    }


def evidencia_ausente() -> dict[str, Any]:
    """
    Lo que se devuelve por una evaluación ANTERIOR a este contrato.

    Un resultado viejo no tiene evidencia estructural porque nadie la calculó,
    no porque su pose fallara. Presentarlo como error convertiría un hueco
    histórico en una acusación sobre moléculas que nunca se validaron.
    """
    return _abstencion_de_etapa(
        EVIDENCIA_AUSENTE,
        "Esta evaluación es anterior a la validación geométrica/física en producción. "
        "No se validó ninguna pose: no es que fallara, es que no se evaluó.",
    )


def _estado_de_etapa(estados: list[str]) -> str:
    """
    Estado de la etapa a partir de la pose PRINCIPAL y del resto.

    Manda la principal: es la que el producto presenta. Si la principal pasa
    pero otra falla, la etapa queda en `review` — hay una señal que el lector
    tiene que ver, y esconderla detrás de un `passed` sería elegir por él.
    """
    if not estados:
        return STAGE_NOT_EVALUATED
    principal = estados[0]
    if principal == STAGE_FAILED:
        return STAGE_FAILED
    if principal == STAGE_NOT_EVALUATED:
        return STAGE_NOT_EVALUATED
    if principal == STAGE_PASSED and any(e == STAGE_FAILED for e in estados[1:]):
        return STAGE_REVIEW
    return principal


def build_structural_evidence(
    *,
    poses: list[Any],
    target_pdb_id: str | None,
    receptor_sha256: str | None,
    smiles: str | None = None,
    receptor_bytes: bytes | None = None,
    max_poses: int | None = None,
) -> dict[str, Any]:
    """
    Evidencia estructural de TODAS las poses conservadas.

    Se validan todas —no sólo la top-1— porque el selector va a llegar y no debe
    obligar a recalcular ni a perder lo ya medido. La pose principal de este
    sprint sigue siendo la de Vina, y así se declara en `pose_strategy`.

    NUNCA lanza. Cualquier fallo del validador se convierte en una abstención
    declarada: el docking de esta evaluación ya terminó y sigue siendo válido.
    """
    if not poses:
        return _abstencion_de_etapa(SIN_POSES, "La evaluación no conservó ninguna pose.")

    ordenadas = sorted(poses, key=lambda p: _campo(p, "rank", 10**6))
    if max_poses is not None:
        ordenadas = ordenadas[:max_poses]

    receptor = resolver_receptor(
        target_pdb_id=target_pdb_id,
        receptor_sha256_esperado=receptor_sha256,
        receptor_bytes=receptor_bytes,
    )
    try:
        from services.chemistry.pose_physical_validity import evaluar_pose_fisica
    except Exception as exc:  # noqa: BLE001
        receptor.cerrar()
        return _abstencion_de_etapa(
            VALIDADOR_NO_DISPONIBLE,
            f"El validador de poses no se pudo importar ({type(exc).__name__}).",
            poses_produced=len(poses),
        )

    evidencia_poses: list[dict[str, Any]] = []
    motores: set[str] = set()
    try:
        for pose in ordenadas:
            evidencia_poses.append(
                _evaluar_una(pose, receptor, smiles, evaluar_pose_fisica, motores)
            )
    finally:
        receptor.cerrar()

    estados = [p["status"] for p in evidencia_poses]
    evaluadas = sum(1 for e in estados if e != STAGE_NOT_EVALUATED)
    return {
        "version_schema": STRUCTURAL_EVIDENCE_SCHEMA_VERSION,
        "stage_status": _estado_de_etapa(estados),
        "reason_code": None if evaluadas else (receptor.razon or SIN_PDBQT_DE_POSE),
        "detail": None,
        "pose_strategy": POSE_STRATEGY_VINA_TOP1,
        "primary_pose_rank": _campo(ordenadas[0], "rank", None),
        "poses_produced": len(poses),
        "poses_evaluated": evaluadas,
        # Cobertura con denominador dicho en voz alta: cuántas de las que la
        # corrida conservó recibieron un veredicto de verdad.
        "coverage": round(evaluadas / len(poses), 6) if poses else None,
        "receptor_sha256": receptor.sha256,
        "receptor_source": receptor.fuente,
        "validation_engine": sorted(motores)[0] if len(motores) == 1 else sorted(motores) or None,
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "poses": evidencia_poses,
    }


def _campo(pose: Any, nombre: str, defecto: Any) -> Any:
    if isinstance(pose, dict):
        return pose.get(nombre, defecto)
    return getattr(pose, nombre, defecto)


def _evaluar_una(pose, receptor, smiles, evaluar, motores) -> dict[str, Any]:
    """Una pose. Toda excepción se convierte en abstención, nunca se propaga."""
    rank = _campo(pose, "rank", None)
    afinidad = _campo(pose, "affinity", None)
    bloque = _campo(pose, "pdbqt_block", None)

    base = {
        "rank": rank,
        "observed_vina_affinity_kcal_mol": afinidad,
        "status": STAGE_NOT_EVALUATED,
        "label": "NO EVALUADA",
        "engine": None,
        "checks": [],
        "checks_que_fallan": [],
        "detail": None,
        "reason_code": None,
        "canonicalization_invariants": None,
        "provenance": {},
    }

    if not bloque:
        return {**base, "reason_code": SIN_PDBQT_DE_POSE,
                "detail": "La pose no conservó su bloque PDBQT; no hay coordenadas que validar."}

    plantilla, index_map, procedencia_plantilla = extraer_plantilla_y_mapa(bloque)
    provenance = {
        "pose_pdbqt": "docking_poses[].pdbqt_block",
        "template": procedencia_plantilla,
        "index_map": "meeko_remark_smiles_idx" if index_map else "ausente",
        "receptor": receptor.fuente,
    }

    if receptor.razon is not None:
        # Sin el receptor EXACTO no se corre la batería intermolecular. Se dice
        # cuál falta y por qué, en vez de validar contra otro.
        return {**base, "reason_code": receptor.razon,
                "detail": ("No se pudo usar el receptor exacto de esta corrida "
                           f"({receptor.razon}); no se emite veredicto geométrico."),
                "provenance": provenance}

    if plantilla is None and not smiles:
        return {**base, "reason_code": SIN_PLANTILLA,
                "detail": ("Sin plantilla química ni SMILES declarados. La química no se "
                           "deduce de los tipos AutoDock."),
                "provenance": provenance}

    # El diagnóstico preliminar conserva una ruta legible incluso si el
    # evaluador se abstiene antes de construir el veredicto completo. Debe usar
    # la misma representación canónica que producción; mezclar aquí la ruta
    # histórica volvería a publicar invariantes de otra molécula.
    diagnostico_lector: dict[str, Any] = {}
    ruta_lector = None
    try:
        from services.chemistry.pose_physical_validity import leer_pose_pdbqt_canonica

        lectura = leer_pose_pdbqt_canonica(
            bloque, plantilla=plantilla, index_map=index_map, smiles=smiles
        )
        diagnostico_lector = dict(lectura.diagnostico or {})
        ruta_lector = lectura.ruta
    except Exception:                                          # noqa: BLE001
        diagnostico_lector = {}

    try:
        veredicto = evaluar(
            pose_pdbqt=bloque,
            smiles=smiles,
            receptor_path=receptor.path,
            plantilla=plantilla,
            index_map=index_map,
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("validacion_de_pose_fallo", rank=rank, error=str(exc)[:200])
        return {**base, "reason_code": VALIDADOR_NO_DISPONIBLE,
                "detail": f"El validador lanzó {type(exc).__name__} sobre esta pose.",
                "provenance": provenance}

    motor = veredicto.get("motor")
    if motor:
        motores.add(str(motor))

    # Diagnostico PRECISO cuando el mapa no cubre todos los seriales. «Serial
    # ausente» no le dice a nadie que hacer; «el mapa no cubre los hidrogenos
    # polares que Meeko declaro» si, y ademas identifica la unica ruta donde
    # este contrato todavia no puede garantizar la canonicalizacion.
    razon = veredicto.get("motivo")
    if razon == "serial_ausente_o_indice_fuera_de_rango":
        polares = seriales_de_hidrogeno_polar(bloque)
        cubiertos = {s for s, _ in (index_map or [])}
        if polares and not polares.issubset(cubiertos):
            razon = MAPA_SIN_HIDROGENOS_POLARES
    return {
        "rank": rank,
        "observed_vina_affinity_kcal_mol": afinidad,
        "status": veredicto.get("status", STAGE_NOT_EVALUATED),
        "label": veredicto.get("label", "NO EVALUADA"),
        "engine": motor,
        "checks": veredicto.get("checks", []),
        "checks_que_fallan": veredicto.get("checks_que_fallan", []),
        "detail": veredicto.get("detail"),
        "reason_code": razon,
        # Sólo viajan comprobaciones realmente medidas. Las de lectura y las de
        # canonicalización son distintas y se fusionan de forma explícita.
        "canonicalization_invariants": _invariantes_de({
            "diagnostico_lector": {
                **diagnostico_lector,
                **(veredicto.get("diagnostico_lector") or {}),
            },
            "canonicalization_invariants": (
                veredicto.get("canonicalization_invariants") or {}
            ),
        }),
        "provenance": {**provenance,
                       "reader_route": veredicto.get("ruta_lector") or ruta_lector},
    }


def _invariantes_de(veredicto: dict[str, Any]) -> dict[str, Any] | None:
    """
    Las invariantes de lectura y canonicalización que sí fueron medidas.

    Se seleccionan por nombre en vez de volcar el diagnóstico entero: el
    diagnóstico lleva también contadores de depuración, y mezclarlos con las
    invariantes haría que un lector confundiera un dato de traza con una
    comprobación superada.

    El desplazamiento pesado y ``n_h_heredados`` proceden de la molécula ya
    canonicalizada, no de constantes ni de una inferencia sobre el lector.
    """
    diag = veredicto.get("diagnostico_lector") or {}
    canon = veredicto.get("canonicalization_invariants") or {}
    if not isinstance(diag, dict):
        diag = {}
    if not isinstance(canon, dict):
        canon = {}
    nombres = (
        "mapa_biyectivo",
        "carga_formal_identica",
        "n_enlaces_pesados_identico",
        "n_atomos_pesados_identico",
        "smiles_isomerico_identico",
        "n_coordenadas_aplicadas",
        "h_sin_coordenada_eliminados",
        "n_atomos_en_pdbqt",
        "pseudoatomos_de_pegado_descartados",
        "h_polares_declarados_descartados",
    )
    seleccion = {k: diag[k] for k in nombres if k in diag}
    nombres_canonicos = (
        "desplazamiento_pesado_max_A",
        "pesados_invariantes",
        "smiles_isomerico_identico",
        "carga_formal_identica",
        "n_enlaces_pesados_identico",
        "n_atomos_pesados_identico",
        "n_h_heredados",
        "n_h_canonicos",
    )
    seleccion.update({k: canon[k] for k in nombres_canonicos if k in canon})
    return seleccion or None
