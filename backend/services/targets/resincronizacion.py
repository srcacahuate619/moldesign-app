"""Lleva las correcciones del catalogo a una base que ya existe.

# El problema, dicho con la linea que lo causa

`_auto_seed_curated_targets_if_empty` siembra desde `curated_targets.json`
**solo si la base tiene diez objetivos o menos**, y dentro del bucle salta
cualquier `pdb_id` que ya exista::

    if len(existing_targets) > 10:
        return
    ...
    if existing:
        continue

Eso convierte el catalogo en algo que se escribe UNA VEZ, en el primer arranque,
y nunca mas. Todo lo que se corrigio despues -las 50 cadenas de `c8a50da`, los
siete rescates, las once cajas recentradas, los nueve hotspots rederivados, las
367 resoluciones recuperadas, los cuatro campos del sitio- **no ha llegado a
ninguna maquina que haya abierto la aplicacion alguna vez**, incluida la VM donde
se hizo la primera evaluacion completa.

Las columnas nuevas si aparecen -el chequeo de esquema hace `ALTER TABLE ADD
COLUMN` al arrancar- pero llegan VACIAS, asi que la tarjeta diria «Sitio sin
medir» para los 385.

# Que se sincroniza, y que no se toca nunca

La linea divisoria no es tecnica sino de propiedad: **el catalogo describe la
estructura; el usuario produce el resto.**

    DEL CATALOGO       identidad y quimica del receptor: nombre, descripcion,
                       cadena, caja, familia, organismo, resolucion, hotspots y
                       su procedencia, composicion del sitio, cofactores,
                       umbrales.

    DEL USUARIO        lo que su maquina calculo o decidio: si el receptor esta
                       preparado y donde, la calibracion local -`spearman_rho`,
                       `calibration_date`-, si lo marco como caliente, y todo lo
                       de blockchain.

Sobreescribir una calibracion local seria borrar trabajo del usuario para poner
un `null`, que es exactamente lo que este modulo existe para evitar en la otra
direccion.

# Sobre que filas actua

Solo sobre las que el catalogo posee: ni privadas, ni de comunidad, ni variantes
de preparacion. Un receptor que el usuario subio no aparece en el JSON, y
tocarlo -o retirarlo por no estar- seria destruir lo suyo.

# Por que invalida el receptor preparado

Si cambia la cadena, las cadenas del sitio o la caja, el `.pdbqt` que hay en
disco describe OTRA cosa. Servirlo seria acoplar contra el receptor viejo con la
anotacion nueva, que es peor que cualquiera de los dos por separado. Se marca
como no preparado y se vuelve a preparar en la siguiente corrida.

# Por que se ejecuta sola

Porque el defecto es precisamente que nada llegaba. Una sincronizacion que hay
que lanzar a mano no habria arreglado la VM. Es idempotente y no destruye nada:
se salta entera si la huella del catalogo no cambio.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from sqlalchemy import text

from utils.logger import get_logger

log = get_logger(__name__)


#: Campos que el catalogo posee y que se sobrescriben. `hotspots` va aparte
#: porque necesita el saneado historico de formatos.
CAMPOS_DEL_CATALOGO: tuple[str, ...] = (
    "name",
    "description",
    "chain",
    "grid_center_x",
    "grid_center_y",
    "grid_center_z",
    "grid_size_x",
    "grid_size_y",
    "grid_size_z",
    "requires_cns",
    "structural_family",
    "therapeutic_family",
    "organism",
    "resolution",
    "affinity_threshold",
    "specificity_floor",
    "cofactors_whitelist",
    "is_anti_target",
    "anti_target_risk",
    "site_chains",
    "site_chain_atoms",
    "site_evidence",
    "site_ligand",
    "hotspots_source",
)

#: Cambiar cualquiera de estos deja obsoleto el `.pdbqt` que haya en disco.
CAMPOS_QUE_INVALIDAN_LA_PREPARACION: frozenset[str] = frozenset({
    "chain", "site_chains",
    "grid_center_x", "grid_center_y", "grid_center_z",
    "grid_size_x", "grid_size_y", "grid_size_z",
})


def sanear_hotspots(crudo: Any) -> list | None:
    """Los tres formatos historicos del campo, a uno solo.

    El JSON del catalogo ha guardado los hotspots como lista, como cadena JSON
    y como cadena doblemente serializada -el bug del doble escape que documenta
    `_auto_seed_curated_targets_if_empty`-. Se normalizan aqui para no repetir
    esa logica en dos sitios que puedan divergir.

    Devuelve una lista cruda o `None`. **Nunca una cadena**: la columna es JSON
    y su serializador ya hace `json.dumps`; meterle un texto lo serializa dos
    veces.
    """
    if isinstance(crudo, list):
        return crudo or None
    if not isinstance(crudo, str):
        return None
    texto = crudo.strip()
    if not texto or texto in ("null", "[]"):
        return None
    try:
        primero = json.loads(texto)
    except (json.JSONDecodeError, TypeError):
        return None
    if isinstance(primero, str):
        try:
            segundo = json.loads(primero)
        except (json.JSONDecodeError, TypeError):
            return None
        return segundo if isinstance(segundo, list) and segundo else None
    return primero if isinstance(primero, list) and primero else None


def huella_del_catalogo(ruta: Path) -> str:
    """SHA-256 del archivo. Si no cambia, no hay nada que sincronizar."""
    return hashlib.sha256(ruta.read_bytes()).hexdigest()


async def _huella_registrada(db) -> str | None:
    await db.execute(text(
        "CREATE TABLE IF NOT EXISTS catalog_meta ("
        " catalog_sha256 TEXT NOT NULL,"
        " applied_at TEXT NOT NULL,"
        " targets_actualizados INTEGER NOT NULL DEFAULT 0"
        ")"
    ))
    fila = (await db.execute(text("SELECT catalog_sha256 FROM catalog_meta LIMIT 1"))).fetchone()
    return fila[0] if fila else None


async def _sellar_huella(db, huella: str, actualizados: int) -> None:
    from datetime import datetime, timezone

    ahora = datetime.now(timezone.utc).isoformat()
    existe = (await db.execute(text("SELECT 1 FROM catalog_meta LIMIT 1"))).fetchone()
    if existe:
        await db.execute(
            text("UPDATE catalog_meta SET catalog_sha256=:h, applied_at=:t, "
                 "targets_actualizados=:n"),
            {"h": huella, "t": ahora, "n": actualizados},
        )
    else:
        await db.execute(
            text("INSERT INTO catalog_meta (catalog_sha256, applied_at, targets_actualizados) "
                 "VALUES (:h, :t, :n)"),
            {"h": huella, "t": ahora, "n": actualizados},
        )


def es_del_catalogo(target) -> bool:
    """Una fila que el catalogo posee: ni privada, ni de comunidad, ni variante."""
    return (
        not bool(getattr(target, "is_private", False))
        and not bool(getattr(target, "is_community", False))
        and getattr(target, "preparation_parent_id", None) is None
    )


def diferencias(target, fila: dict) -> dict[str, tuple[Any, Any]]:
    """Los campos del catalogo cuyo valor en la base no coincide con el JSON."""
    cambios: dict[str, tuple[Any, Any]] = {}
    for campo in CAMPOS_DEL_CATALOGO:
        if campo not in fila:
            continue
        nuevo = fila[campo]
        actual = getattr(target, campo, None)
        # Los flotantes de la caja se comparan con tolerancia: el JSON guarda
        # tres decimales y SQLite devuelve el float completo.
        if isinstance(nuevo, float) or isinstance(actual, float):
            try:
                if actual is not None and nuevo is not None and abs(float(actual) - float(nuevo)) < 1e-6:
                    continue
            except (TypeError, ValueError):
                pass
        if actual != nuevo:
            cambios[campo] = (actual, nuevo)

    nuevos_hotspots = sanear_hotspots(fila.get("hotspots"))
    if nuevos_hotspots is not None and (target.hotspots or None) != nuevos_hotspots:
        cambios["hotspots"] = (target.hotspots, nuevos_hotspots)
    return cambios


async def resincronizar_catalogo(db, ruta_json: Path) -> dict[str, Any]:
    """Aplica el catalogo a la base. Idempotente y no destructiva.

    Devuelve un resumen con lo que cambio, para que el arranque lo registre.
    """
    from core.models import TargetORM
    from sqlalchemy import select

    if not ruta_json.is_file():
        return {"estado": "sin_catalogo"}

    huella = huella_del_catalogo(ruta_json)
    if await _huella_registrada(db) == huella:
        return {"estado": "al_dia", "sha256": huella[:12]}

    filas = {
        (f.get("pdb_id") or "").upper(): f
        for f in json.loads(ruta_json.read_text(encoding="utf-8"))
        if f.get("pdb_id")
    }

    existentes = (await db.execute(select(TargetORM))).scalars().all()
    actualizados: list[dict[str, Any]] = []
    invalidados: list[str] = []
    retirados: list[str] = []
    nuevos = 0

    for target in existentes:
        if not es_del_catalogo(target):
            continue
        pdb = (target.pdb_id or "").upper()
        fila = filas.get(pdb)
        if fila is None:
            # Estaba en el catalogo y ya no. NO se borra: puede haber
            # evaluaciones colgando de el, y borrar el trabajo de alguien para
            # limpiar una tabla no es una operacion que este modulo deba hacer.
            # Se marca, y `list_targets` lo saca del catalogo publico.
            if getattr(target, "retired_reason", None) is None:
                target.retired_reason = (
                    "Retirado del catalogo curado: ver docs/auditorias/"
                    "receptores_retirados.json"
                )
                retirados.append(pdb)
            continue

        cambios = diferencias(target, fila)
        if not cambios:
            continue
        for campo, (_antes, despues) in cambios.items():
            setattr(target, campo, despues)
        if CAMPOS_QUE_INVALIDAN_LA_PREPARACION & set(cambios):
            # El `.pdbqt` en disco describe otra cosa. Servirlo seria acoplar
            # contra el receptor viejo con la anotacion nueva.
            target.is_prepared = False
            target.prepared_file_path = None
            invalidados.append(pdb)
        actualizados.append({
            "pdb_id": pdb,
            "campos": sorted(cambios),
            # Se registra el valor anterior de la cadena y la caja porque son
            # los que cambian el resultado del docking.
            "antes": {
                c: cambios[c][0] for c in cambios
                if c in CAMPOS_QUE_INVALIDAN_LA_PREPARACION
            },
        })

    # Objetivos del catalogo que la base no tiene: una base sembrada antes de
    # que existieran. Se anaden.
    presentes = {(t.pdb_id or "").upper() for t in existentes}
    for pdb, fila in filas.items():
        if pdb in presentes:
            continue
        target = TargetORM(
            pdb_id=pdb,
            name=(fila.get("name") or pdb).strip(),
            chain=(fila.get("chain") or "A").strip() or "A",
            description=fila.get("description", ""),
            grid_center_x=fila.get("grid_center_x", 0.0),
            grid_center_y=fila.get("grid_center_y", 0.0),
            grid_center_z=fila.get("grid_center_z", 0.0),
            grid_size_x=fila.get("grid_size_x", 20.0),
            grid_size_y=fila.get("grid_size_y", 20.0),
            grid_size_z=fila.get("grid_size_z", 20.0),
            requires_cns=fila.get("requires_cns", False),
            structural_family=fila.get("structural_family"),
            organism=fila.get("organism"),
            resolution=fila.get("resolution"),
            hotspots=sanear_hotspots(fila.get("hotspots")),
            hotspots_source=fila.get("hotspots_source"),
            site_chains=fila.get("site_chains"),
            site_chain_atoms=fila.get("site_chain_atoms"),
            site_evidence=fila.get("site_evidence"),
            site_ligand=fila.get("site_ligand"),
            affinity_threshold=fila.get("affinity_threshold"),
            specificity_floor=fila.get("specificity_floor"),
            cofactors_whitelist=fila.get("cofactors_whitelist"),
            is_anti_target=fila.get("is_anti_target", False),
            anti_target_risk=fila.get("anti_target_risk"),
        )
        db.add(target)
        nuevos += 1

    await _sellar_huella(db, huella, len(actualizados))
    await db.commit()

    resumen = {
        "estado": "aplicado",
        "sha256": huella[:12],
        "actualizados": len(actualizados),
        "anadidos": nuevos,
        "retirados": retirados,
        "preparacion_invalidada": invalidados,
        "detalle": actualizados[:50],
    }
    log.info(
        "catalogo_resincronizado",
        sha256=huella[:12],
        actualizados=len(actualizados),
        anadidos=nuevos,
        retirados=len(retirados),
        preparacion_invalidada=len(invalidados),
    )
    return resumen
