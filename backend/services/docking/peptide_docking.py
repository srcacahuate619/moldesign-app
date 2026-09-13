"""Ejecución de docking peptídico aislada del dispatcher local de jobs."""

from __future__ import annotations

from typing import Any

from chem.conformer import _mol_to_sdf_string
from chem.properties import calculate_properties
from core.config import get_settings
from core.database import get_db_session
from db.repository import Repository
from utils.cache import cache
from services.avisos import Severidad, aviso
from utils.logger import get_logger

log = get_logger(__name__)
settings = get_settings()


async def run_peptide_docking_helper(
    task_id: str,
    smiles: str,
    target_pdb_id: str,
    peptide_docking_engine: str,
    grid_center: list[float] | None = None,
    grid_size: list[float] | None = None,
) -> Any:
    """Ejecuta la ruta peptídica y cae a Vina si el proveedor no responde."""
    from core.models import DockingPose, DockingResult
    from utils.file_handlers import StoragePath, download_pdb_from_rcsb
    from utils.local_storage import exists, read_text, write_text
    from utils.refinement import refine_receptor_peptide_complex
    from rdkit import Chem

    async with get_db_session() as db:
        repository = Repository(db)
        # EVAL-SCI-001: el receptor pedido o ninguno.
        from services.targets.resolution import resolve_execution_target

        target = await resolve_execution_target(repository, db, target_pdb_id)

        # El registro de la molécula lleva SU receptor. Sin el `target_pdb_id`
        # explícito, la molécula quedaba archivada contra el receptor base
        # mientras el plegado y el acoplamiento corrían contra otro: la
        # procedencia persistida contradecía a la corrida.
        molecule = await repository.create_or_get_molecule(
            smiles=smiles, target_pdb_id=target.pdb_id
        )
        properties = calculate_properties(smiles)

        # La sesión se cierra abajo; capturar los atributos evita objetos ORM
        # expired/detached durante la ejecución pesada fuera de la transacción.
        _tgt_pdb_id = target.pdb_id
        _tgt_chain = target.chain
        _mol_smiles_hash = str(molecule.smiles_hash)

    log.info({"event": "routing_to_level_3_peptide_helper", "task_id": task_id, "engine": peptide_docking_engine})
    await cache.set_job_progress(task_id, 40, "peptide_folding")

    raw_path = StoragePath.target_raw(_tgt_pdb_id)
    temp_pdb_path = ""
    pdb_content = ""
    try:
        if await exists(raw_path):
            pdb_content = await read_text(raw_path)
        else:
            pdb_content = await download_pdb_from_rcsb(_tgt_pdb_id)
            await write_text(raw_path, pdb_content)

        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".pdb", delete=False, mode="w", encoding="utf-8") as temp_pdb:
            temp_pdb.write(pdb_content)
            temp_pdb_path = temp_pdb.name
    except Exception as e:
        log.warning("No se pudo preparar PDB temporal del target para Nivel 3", error=str(e))

    # ENG-002. Un motor descargable que está instalado se enciende aquí, porque
    # el investigador ya lo eligió: pedirle además que lo arranque a mano sería
    # exigirle dos gestos para una sola decisión. Encender es idempotente y
    # cuesta segundos si ya está sirviendo.
    #
    # Lo que NO hace: descargar. Bajar 8.4 GB dentro de una corrida, sin avisar y
    # sin poder cancelarlo, no es algo que decida el pipeline.
    try:
        from services.motores import sidecar_de

        sc = sidecar_de(peptide_docking_engine)
        if sc is not None and not sc.responde():
            estado = sc.estado()
            if estado.estado == "instalado_apagado":
                await cache.set_job_progress(task_id, 40, "peptide_engine_starting")
                import anyio

                await anyio.to_thread.run_sync(sc.encender)
            elif estado.estado == "no_instalado":
                raise RuntimeError(estado.motivo or f"{peptide_docking_engine} no está instalado")
    except RuntimeError:
        raise
    except Exception as exc:  # noqa: BLE001 — encender es una mejora, no un requisito
        log.warning("no se pudo encender el motor descargable",
                    motor=peptide_docking_engine, error=str(exc))

    ml_res = None
    try:
        if peptide_docking_engine == "colabfold" and temp_pdb_path:
            from services.colabfold.service import get_colabfold_service
            ml_res = await get_colabfold_service().predict(temp_pdb_path, smiles)
        elif peptide_docking_engine == "esmfold-experimental" and temp_pdb_path:
            from services.esmfold_pro.service import get_esmfold_pro_service
            ml_res = await get_esmfold_pro_service().predict(
                temp_pdb_path, smiles, grid_center=grid_center, grid_size=grid_size
            )
        elif temp_pdb_path:
            from services.esmfold.service import get_esmfold_service
            ml_res = await get_esmfold_service().predict(
                temp_pdb_path, smiles, grid_center=grid_center, grid_size=grid_size
            )
    finally:
        if temp_pdb_path:
            import os
            try:
                os.unlink(temp_pdb_path)
            except Exception:
                pass

    scientific_warnings = []
    peptide_transfer_manifest = getattr(ml_res, "transfer_manifest", None) if ml_res else None
    if ml_res and ml_res.poses:
        sdf_parts = []
        for p in ml_res.poses:
            peptide_sdf = getattr(p, "ligand_sdf", None)
            peptide_pdb = getattr(p, "ligand_pdb", None) or getattr(p, "complex_pdb", "")
            # El SDF transferido conserva el grafo quimico del SMILES y las
            # coordenadas de Vina. No lo sustituyas por el conversor PDB,
            # que pierde enlaces y terminales (OXT).
            if peptide_sdf:
                mol_pep = Chem.MolFromMolBlock(peptide_sdf, sanitize=False, removeHs=False)
            else:
                if settings.peptide_refinement_enabled and pdb_content:
                    try:
                        peptide_pdb = refine_receptor_peptide_complex(pdb_content, peptide_pdb)
                    except Exception as re_err:
                        log.warning("Fallo inesperado al llamar refine_receptor_peptide_complex", error=str(re_err))
                mol_pep = Chem.MolFromPDBBlock(peptide_pdb, sanitize=False)
            if mol_pep:
                try:
                    Chem.SanitizeMol(mol_pep)
                except Exception:
                    pass
                mol_pep.SetProp("SMILES", smiles)
                mol_pep.SetProp("_Name", f"Pose_{p.rank}")
                sdf_parts.append(_mol_to_sdf_string(mol_pep, smiles))

        sdf_content = "".join(sdf_parts)
        poses_path = StoragePath.docking_poses(_mol_smiles_hash, _tgt_pdb_id)
        await write_text(poses_path, sdf_content)

        # ═══════════════════════════════════════════════════════════════
        # LA AFINIDAD DE VINA, O NINGUNA. NUNCA UNA CONFIANZA DISFRAZADA.
        # ═══════════════════════════════════════════════════════════════
        #
        # Aquí vivía la conversión que `docs/74_...` §7.3 manda quitar antes de
        # tocar nada más. Lo que hacía, medido de punta a punta:
        #
        #   1. El sidecar leía `REMARK VINA RESULT`, calculaba
        #      `conf = 1 - |afinidad|/15` —con el comentario «más negativo =
        #      mejor» encima, haciendo lo contrario— y TIRABA la afinidad.
        #   2. Aquí se reconvertía con `max(-12.0, min(-4.0, -1.5*conf))`.
        #
        #   Vina real   conf    afinidad persistida
        #      −2.0     0.867          −4.0
        #      −6.0     0.600          −4.0
        #     −12.0     0.200          −4.0
        #
        #   `-1.5*conf` con conf en [0.1, 1.0] vale entre −1.5 y −0.15, y todos
        #   esos valores son mayores que −4.0, así que `min(-4.0, ·)` devolvía
        #   −4.0 SIEMPRE. No «casi siempre»: siempre. Toda corrida peptídica
        #   reportaba −4.0 kcal/mol con independencia del resultado real.
        #
        # Ahora: si Vina corrió, se usa su número tal cual. Si no corrió, NO se
        # fabrica uno — la corrida entrega estructura, y lo dice.
        poses = []
        sin_afinidad = 0
        solo_plegado = 0
        for p_pose in ml_res.poses:
            afinidad = getattr(p_pose, "vina_affinity_kcal_mol", None)
            origen = getattr(p_pose, "origen", "desconocido")
            if origen == "folded_structure_only":
                solo_plegado += 1
            if afinidad is None:
                sin_afinidad += 1
                continue
            rmsd = getattr(p_pose, "rmsd", None)
            poses.append(DockingPose(
                rank=p_pose.rank,
                affinity=float(afinidad),
                rmsd_lb=rmsd if rmsd is not None else 0.0,
                rmsd_ub=rmsd if rmsd is not None else 0.0,
            ))

        plddt = ml_res.best_confidence
        if peptide_docking_engine == "colabfold":
            detalle_confianza = (
                f"ipTM de interfaz: {ml_res.best_iptm:.2f}"
                if ml_res.best_iptm is not None else "ipTM no reportado"
            )
        else:
            detalle_confianza = (
                f"confianza estructural (pLDDT/100): {plddt:.2f}"
                if plddt is not None else "confianza estructural no reportada"
            )

        if poses:
            best_affinity = poses[0].affinity
            scientific_warnings.append(aviso(
                "PEPTIDO_PLEGADO_Y_ACOPLADO", Severidad.PRECAUCION,
                f"Ruta peptídica ({peptide_docking_engine}): la estructura del "
                f"péptido la predijo el modelo y el acoplamiento lo hizo "
                f"AutoDock Vina. La afinidad reportada es la de Vina, sin "
                f"transformar. La {detalle_confianza} describe el PLEGADO, no "
                f"la unión, y no se convierte a kcal/mol. Resultado "
                f"exploratorio: no hay benchmark de poses ni de repetibilidad "
                f"para este protocolo.",
            ))
        if not poses:
            # ── Estructura sí, acoplamiento no ────────────────────────────
            #
            # `DockingResult` exige `best_affinity: float` y al menos una pose,
            # y hace bien: un resultado de acoplamiento sin afinidad no es un
            # resultado de acoplamiento. Antes se cumplía ese contrato
            # rellenándolo con −4.0.
            #
            # Ahora se cae al mismo camino que cuando el motor peptídico no
            # responde: Vina sobre la caja declarada, con `MOTOR_SUSTITUIDO`
            # en CRÍTICA. Eso produce una afinidad REAL en vez de una
            # inventada, y si no hay caja declarada la corrida falla, que es
            # lo que ya hacía ese camino.
            scientific_warnings.append(aviso(
                "PEPTIDO_SIN_ACOPLAMIENTO", Severidad.CRITICA,
                f"Ruta peptídica ({peptide_docking_engine}): se obtuvo la "
                f"estructura plegada pero NINGUNA pose pasó por un motor de "
                f"acoplamiento ({solo_plegado} estructuras sin acoplar, "
                f"{sin_afinidad} conformaciones sin afinidad). No se fabrica "
                f"una afinidad: antes se devolvía −4.0 kcal/mol en este caso. "
                f"La {detalle_confianza} describe el plegado, no la unión.",
            ))
            ml_res = None  # fuerza el camino de sustitución de más abajo

        elif sin_afinidad:
            scientific_warnings.append(aviso(
                "PEPTIDO_POSES_PARCIALES", Severidad.PRECAUCION,
                f"{sin_afinidad} de {len(ml_res.poses)} conformaciones no "
                f"pasaron por el acoplamiento y se descartaron del resultado "
                f"en vez de entrar con una afinidad inventada.",
            ))

        if poses:
            docking = DockingResult(
                best_affinity=best_affinity,
                poses=poses,
                poses_file_path=poses_path,
                parsing_source="sdf",
                vina_version="AutoDock Vina 1.2.7",
                vina_random_seed=42,
                scientific_warnings=scientific_warnings,
                peptide_transfer_manifest=getattr(ml_res, "transfer_manifest", None),
            )
            return docking

    # Dos motivos distintos llegan aquí: el servicio no respondió, o respondió
    # con estructura pero sin ninguna pose acoplada. El aviso de arriba ya dijo
    # cuál fue; este mensaje no puede afirmar el primero cuando fue el segundo.
    if ml_res is None and any(
        getattr(a, "codigo", None) == "PEPTIDO_SIN_ACOPLAMIENTO"
        for a in scientific_warnings
    ):
        msg = "el modelo plegó la estructura pero ninguna pose pasó por acoplamiento"
    else:
        msg = ml_res.error if ml_res else "Sin respuesta del servicio"
    log.warning("Fallo en Nivel 3, cayendo a Vina estándar", error=msg)

    # ENG-001. Sin caja no hay fallback. La versión anterior usaba (20, 30, 28) y
    # 30 Å cuando no le pasaban `grid_center`/`grid_size`: eso no es un resultado
    # degradado, es un docking en un sitio arbitrario del receptor presentado como
    # el resultado del caso. Un motor que no está disponible tiene que fallar.
    if not grid_center or not grid_size:
        raise RuntimeError(
            f"El motor peptídico '{peptide_docking_engine}' no respondió ({msg}) y el caso "
            "no declara caja de docking, así que no hay dónde acoplar con Vina. "
            "Configura el servicio o elige AutoDock Vina con una caja definida."
        )

    # CRITICA: el motor que corrió no es el que se pidió, y la pose no es
    # comparable con la que habría producido el motor pedido. Este es el aviso
    # que el clasificador por subcadenas pintaba del mismo azul que «las
    # afinidades se extrajeron del stdout».
    scientific_warnings.append(aviso(
        "MOTOR_SUSTITUIDO", Severidad.CRITICA,
        f"MOTOR SUSTITUIDO: se pidió '{peptide_docking_engine}' y ese servicio no está "
        f"disponible en esta instalación ({msg}). La pose NO viene de un modelo de "
        "plegamiento: la produjo AutoDock Vina con exhaustividad reducida (4) sobre la "
        "caja declarada en el caso. No compares este resultado con uno plegado.",
    ))

    from services.docking.vina_service import run_vina_docking

    cx, cy, cz = grid_center[0], grid_center[1], grid_center[2]
    sx, sy, sz = grid_size[0], grid_size[1], grid_size[2]

    docking = await run_vina_docking(
        smiles_hash=_mol_smiles_hash,
        target_pdb_id=_tgt_pdb_id,
        target_chain=_tgt_chain,
        target_center=(cx, cy, cz),
        target_size=(sx, sy, sz),
        hotspots=[],
        exhaustiveness=4,
        num_poses=5,
    )
    docking.scientific_warnings.extend(scientific_warnings)
    docking.peptide_transfer_manifest = peptide_transfer_manifest
    return docking
