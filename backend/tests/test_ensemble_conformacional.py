"""
El ensemble conformacional: qué amplía, qué conserva y qué no promete.

Lo que protegen, en orden de gravedad:

1. **K=1 no cambia NADA.** Es el protocolo por defecto y el de todas las
   corridas anteriores. Si existir el ensemble alterase el camino de una sola
   conformación, habríamos cambiado en silencio la ciencia de cada evaluación
   ya hecha.

2. **La procedencia por pose sobrevive al agrupado.** Sin ella, la pose 1 podría
   venir de la conformación 3 y la 2 de la 17 sin que nada lo dijera, y el
   lector no podría distinguir robustez de ambigüedad.

3. **La traza de reproducibilidad sobrevive.** Versión del motor, semilla y hash
   del receptor. Si el agrupado los perdiera, el dossier los declararía «no
   informado» y la validación física se abstendría: el ensemble habría roto de
   rebote todo el aparato de procedencia.

4. **Una conformación que falla no se lleva a las demás por delante.**

5. **No se promete lo que la medición no dice.** El ensemble amplía cobertura;
   el aviso que emite no puede afirmar que mejore el top-1.
"""

from __future__ import annotations

import pytest

from chem.conformer_ensemble import (
    CONFORMEROS_MAXIMO,
    CONFORMEROS_POR_DEFECTO,
    conformer_path_de,
    hash_de_conformero,
    normalizar_k,
)
from core.models import DockingPose, DockingResult
from services.docking.ensemble import agrupar_poses, run_ensemble_docking


def _pose(rank: int, afinidad: float) -> DockingPose:
    return DockingPose(rank=rank, affinity=afinidad, rmsd_lb=0.0, rmsd_ub=0.0)


def _resultado(afinidades: list[float], **extra) -> DockingResult:
    poses = [_pose(i + 1, a) for i, a in enumerate(afinidades)]
    return DockingResult(
        best_affinity=poses[0].affinity,
        poses=poses,
        parsing_source="sdf",
        **extra,
    )


# ── 1. K=1 es el camino de siempre ───────────────────────────────────


class TestElDefectoNoCambia:
    def test_el_defecto_es_una_sola_conformacion(self):
        assert CONFORMEROS_POR_DEFECTO == 1

    def test_la_conformacion_cero_usa_las_rutas_de_siempre(self):
        """
        Con K=1 el `.sdf`, el `.pdbqt` y la caché de docking caen donde caían.

        Si el índice 0 llevara sufijo, cada corrida por defecto perdería los
        aciertos de caché que ya tenía y volvería a acoplar lo ya acoplado.
        """
        assert hash_de_conformero("abc123", 0) == "abc123"
        assert conformer_path_de("abc123", 0) == "ligands/abc123/conformer.sdf"

    def test_las_demas_conformaciones_se_aislan_en_su_propia_cache(self):
        assert hash_de_conformero("abc123", 7) == "abc123__c07"
        assert conformer_path_de("abc123", 7) == "ligands/abc123__c07/conformer.sdf"
        # Y no colisionan entre sí.
        derivados = {hash_de_conformero("abc123", i) for i in range(30)}
        assert len(derivados) == 30

    @pytest.mark.parametrize(
        "entrada,esperado",
        [(None, 1), (0, 1), (-5, 1), (1, 1), (30, 30), ("8", 8), ("x", 1), (9999, CONFORMEROS_MAXIMO)],
    )
    def test_un_k_imposible_cae_al_defecto_en_vez_de_reventar(self, entrada, esperado):
        """Un parámetro mal escrito degrada el protocolo; no tumba la corrida."""
        assert normalizar_k(entrada) == esperado


# ── 2 y 3. Lo que el agrupado tiene que conservar ────────────────────


class TestLaPiscinaConservaLoQueImporta:
    def test_cada_pose_recuerda_de_que_conformacion_salio(self):
        entregadas = agrupar_poses(
            [(0, _resultado([-8.0, -7.0])), (3, _resultado([-9.5, -6.0]))],
            num_poses=4,
        )

        # Ordenadas por afinidad, no por conformación.
        assert [p.affinity for p in entregadas] == [-9.5, -8.0, -7.0, -6.0]
        # Y cada una sabe de dónde vino.
        assert [p.conformer_index for p in entregadas] == [3, 0, 0, 3]

    def test_el_rank_se_renumera_sobre_la_piscina(self):
        """
        Cada corrida traía su propio rank 1. Sin renumerar habría K poses con
        rank 1, y el «top-1» dejaría de significar nada.
        """
        entregadas = agrupar_poses(
            [(0, _resultado([-8.0, -7.0])), (1, _resultado([-9.0, -6.0]))],
            num_poses=4,
        )
        assert [p.rank for p in entregadas] == [1, 2, 3, 4]

    def test_el_orden_es_estable_ante_empates(self):
        """
        Dos poses con la MISMA afinidad tienen que salir siempre en el mismo
        orden, o el paquete reproducible dejaría de serlo.
        """
        entrada = [(2, _resultado([-8.0])), (0, _resultado([-8.0])), (1, _resultado([-8.0]))]
        primera = agrupar_poses(entrada, num_poses=3)
        segunda = agrupar_poses(entrada, num_poses=3)

        assert [p.conformer_index for p in primera] == [0, 1, 2]
        assert [p.conformer_index for p in primera] == [p.conformer_index for p in segunda]

    def test_se_entregan_solo_las_num_poses_pedidas(self):
        entregadas = agrupar_poses(
            [(i, _resultado([-9.0 + i, -8.0 + i, -7.0 + i])) for i in range(5)],
            num_poses=9,
        )
        assert len(entregadas) == 9

    @pytest.mark.asyncio
    async def test_la_traza_de_reproducibilidad_sobrevive_al_agrupado(self):
        """
        Si el agrupado perdiera versión, semilla y hash del receptor, el dossier
        los declararía «no informado» y la validación física se abstendría por
        RECEPTOR_SIN_HUELLA. El ensemble habría roto el aparato de procedencia
        sin tocar una línea de él.
        """
        async def dock(smiles_hash, smiles=None):
            return _resultado(
                [-9.0, -8.0],
                vina_version="1.2.5",
                vina_random_seed=42,
                receptor_sha256="a" * 64,
                receptor_path=f"runs/receptors/{'a' * 64}.pdbqt",
                poses_file_path=f"runs/docking/{smiles_hash}/poses.sdf",
                execution_time_s=3.0,
            )

        resultado = await run_ensemble_docking(
            smiles="CCO",
            conformeros=[{"indice": i, "smiles_hash": f"h__c{i}"} for i in range(3)],
            num_poses=4,
            dock_una=dock,
        )

        assert resultado.vina_version == "1.2.5"
        assert resultado.vina_random_seed == 42
        assert resultado.receptor_sha256 == "a" * 64
        assert resultado.receptor_path.endswith(".pdbqt")
        # No se atribuye a la piscina el SDF de la primera conformación.
        assert resultado.poses_file_path is None
        # El tiempo SÍ se suma: son tres corridas de verdad.
        assert resultado.execution_time_s == 9.0


    @pytest.mark.asyncio
    async def test_la_piscina_no_hereda_el_sdf_de_una_sola_conformacion(self):
        """
        El `.sdf` de UNA corrida no describe la piscina.

        Cada corrida de Vina escribe su propio archivo de poses, con SUS nueve
        poses en SU orden. Las entregadas salen de mezclar K corridas y
        reordenar por afinidad: apuntar al archivo de la primera pondría en el
        paquete unas coordenadas y en el dossier otras, y el lector no tendría
        cómo saber cuáles describen lo que está leyendo.

        Los bloques PDBQT por pose SÍ sobreviven, y son la fuente exacta.
        """
        async def dock(smiles_hash, smiles=None):
            resultado = _resultado([-9.0, -8.0])
            return resultado.model_copy(
                update={"poses_file_path": f"ligands/{smiles_hash}/poses.sdf"}
            )

        resultado = await run_ensemble_docking(
            smiles="CCO",
            conformeros=[{"indice": i, "smiles_hash": f"h__c{i:02d}"} for i in range(3)],
            num_poses=4,
            dock_una=dock,
        )

        assert resultado.poses_file_path is None
        # Y las poses entregadas vienen de más de una conformación, que es
        # justo lo que hace inservible el archivo de una sola.
        assert len({p.conformer_index for p in resultado.poses}) > 1


# ── 4. Degradación ───────────────────────────────────────────────────


class TestDegradacion:
    @pytest.mark.asyncio
    async def test_una_conformacion_que_falla_no_se_lleva_a_las_demas(self):
        async def dock(smiles_hash, smiles=None):
            if smiles_hash.endswith("c01"):
                raise RuntimeError("Vina reventó en esta conformación")
            return _resultado([-9.0, -8.0])

        resultado = await run_ensemble_docking(
            smiles="CCO",
            conformeros=[{"indice": i, "smiles_hash": f"h__c{i:02d}"} for i in range(3)],
            num_poses=4,
            dock_una=dock,
        )

        assert len(resultado.poses) == 4
        # La que falló no aporta poses…
        assert 1 not in {p.conformer_index for p in resultado.poses}
        # …y se dice, con su motivo.
        assert any("conformación 1" in a for a in resultado.scientific_warnings)

    @pytest.mark.asyncio
    async def test_si_ninguna_acopla_se_propaga_el_fallo(self):
        """
        Una molécula sin NINGUNA pose no es cobertura reducida: es una
        evaluación sin docking, y fingir lo contrario produciría un dossier
        sobre un acoplamiento que no ocurrió.
        """
        async def dock(smiles_hash, smiles=None):
            raise RuntimeError("sin Vina")

        with pytest.raises(RuntimeError, match="Ninguna conformación"):
            await run_ensemble_docking(
                smiles="CCO",
                conformeros=[{"indice": i, "smiles_hash": f"h__c{i}"} for i in range(3)],
                num_poses=4,
                dock_una=dock,
            )


# ── 5. No se promete lo que la medición no dice ──────────────────────


class TestLoQueNoSePromete:
    @pytest.mark.asyncio
    async def test_el_aviso_declara_cobertura_y_niega_mejora_del_top1(self):
        async def dock(smiles_hash, smiles=None):
            return _resultado([-9.0, -8.0, -7.0])

        resultado = await run_ensemble_docking(
            smiles="CCO",
            conformeros=[{"indice": i, "smiles_hash": f"h__c{i}"} for i in range(4)],
            num_poses=9,
            dock_una=dock,
        )

        aviso = next(a for a in resultado.scientific_warnings if "Ensemble" in a)
        # El denominador, dicho en voz alta.
        assert "4 de 4" in aviso
        assert "12 poses candidatas" in aviso
        # Y la limitación que mide el experimento, sin adornos.
        assert "cobertura" in aviso
        assert "no mejora" in aviso and "top-1" in aviso

    @pytest.mark.asyncio
    async def test_ninguna_afinidad_se_altera_al_agrupar(self):
        """El ensemble reordena y renumera. No toca una sola energía."""
        async def dock(smiles_hash, smiles=None):
            return _resultado([-9.25, -8.5])

        resultado = await run_ensemble_docking(
            smiles="CCO",
            conformeros=[{"indice": i, "smiles_hash": f"h__c{i}"} for i in range(2)],
            num_poses=4,
            dock_una=dock,
        )

        assert sorted(p.affinity for p in resultado.poses) == [-9.25, -9.25, -8.5, -8.5]
        assert resultado.best_affinity == -9.25


# ── El registro declara el protocolo ─────────────────────────────────


def test_la_etapa_declara_el_parametro_y_su_defecto():
    from services.pipeline.registry import STAGE_REGISTRY

    conformer = STAGE_REGISTRY["conformer"]
    assert conformer.params.get("conformers") == 1
    # Y la descripción dice qué compra y qué no, donde el usuario la lee.
    assert "cobertura" in conformer.description
    assert "top-1" in conformer.description


# ── El protocolo forma parte de la identidad del caso ────────────────


class TestLaHuellaDistingueElProtocolo:
    """
    Dos corridas con distinto K NO son la misma corrida, y la huella tiene que
    decirlo. Pero añadir la clave siempre habría cambiado el fingerprint de
    todos los casos ya guardados, y el producto los habría declarado «corrida
    anterior»: los inputs no cambiaron, cambió el formato del documento.
    """

    def _documento(self, **extra):
        from services.docking.preflight import canonical_input_document

        base = dict(
            smiles_for_hash="CCO",
            target_pdb_id="7e2y",
            chain="A",
            grid_center=(1.0, 2.0, 3.0),
            grid_size=(20.0, 20.0, 20.0),
            custom_hotspots=["A:TYR123"],
            docking_engine="vina",
            exhaustiveness=32,
            num_poses=9,
            seed=42,
            source_sha256="a" * 64,
            prepared_sha256="b" * 64,
        )
        base.update(extra)
        return canonical_input_document(**base)

    def test_el_confomero_unico_no_altera_la_huella_historica(self):
        """
        Es la garantía de compatibilidad: un caso guardado antes de existir el
        parámetro tiene que seguir teniendo su misma huella.
        """
        sin_parametro = self._documento()
        con_k1 = self._documento(conformers=1)
        assert sin_parametro == con_k1
        assert "conformers" not in sin_parametro

    def test_un_ensemble_produce_una_huella_distinta(self):
        assert self._documento(conformers=1) != self._documento(conformers=30)
        assert '"conformers":30' in self._documento(conformers=30)

    def test_dos_k_distintos_son_dos_corridas_distintas(self):
        assert self._documento(conformers=10) != self._documento(conformers=30)


def test_el_preflight_publica_el_protocolo_en_la_configuracion_efectiva():
    """
    El control vive con exhaustividad y semilla porque es lo mismo: se congela
    con el caso, se hashea y se imprime en el dossier. Un botón aparte dejaría
    comparar, dentro de una cohorte, una molécula con confórmero único contra
    otra con ensemble — y esa diferencia de protocolo se leería como diferencia
    química.
    """
    import inspect

    from services.docking import preflight

    fuente = inspect.getsource(preflight._effective_configuration)
    assert '"conformers"' in fuente
    # Y junto a los demás parámetros de protocolo, no en otra sección.
    assert fuente.index('"num_poses"') < fuente.index('"conformers"')
