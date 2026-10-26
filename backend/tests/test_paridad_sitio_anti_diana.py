"""
Paridad del sitio anti-diana entre la ruta manual y la automática (AMP-03).

La auditoría ampliada (2026-09-30) lo midió en vivo: la selectividad MANUAL
sobre hERG (`5VA1`) resolvía el sitio multicadena contra el catálogo
(`site_chains: ["A","B","C","D"]`), mientras que la AUTOMÁTICA en segundo
plano terminaba `status: "ok"` con `site_chains: null` y una sola cadena —
el panel de seguridad cardíaca acoplaba contra MEDIA cavidad y devolvía un
número sobre un bolsillo que no existe.

La causa era de cableado, no de ciencia: `run_selectivity_panel` ya resuelve
el sitio contra el catálogo cuando recibe el `repository` — la ruta manual
(`pro_features.py`) se lo entrega — pero el subprocess de la ruta automática
(`selectivity_subprocess.py`) lo llamaba sin él, y el panel caía al fallback
monomérico `chain="A"`.

Este archivo fija las tres piezas:

1. **El contrato del panel** (el que la ruta manual ya cumplía): con
   repositorio, la anti-diana multicadena se prepara con TODAS sus cadenas y
   la caja curada del panel.
2. **El cableado del subprocess** (el defecto AMP-03): la ruta automática le
   entrega su repositorio al panel.
3. **La anti-diana del usuario** (síntoma gemelo del mismo cableado): con
   repositorio, una anti-diana subida se resuelve del catálogo en vez de
   desaparecer como «desconocida».
"""

from __future__ import annotations

import sys
import uuid
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest

from services.docking.selectivity import (
    ANTI_TARGET_PANEL,
    seleccionar_anti_dianas,
    run_selectivity_panel,
)

#: hERG (KCNH2): la anti-diana cardíaca del panel, sitio de cuatro cadenas.
HERG = next(t for t in ANTI_TARGET_PANEL if t["pdb_id"] == "5VA1")

#: El protocolo válido del panel: repite los parámetros de la corrida principal.
PROTOCOLO = {"engine": "vina", "exhaustiveness": 8, "num_poses": 9, "seed": 42}


class _RepoConCatalogo:
    """Repositorio falso: sólo sabe de 5VA1 y de la anti-diana del usuario."""

    def __init__(self, _db=None) -> None:
        pass

    async def get_target_by_pdb_id(self, pdb_id):
        pid = str(pdb_id).strip().upper()
        if pid == "5VA1":
            # La fila del catálogo: el sitio declarado con sus cuatro cadenas.
            return SimpleNamespace(
                pdb_id="5VA1",
                site_chains=["A", "B", "C", "D"],
                grid_center_x=None, grid_center_y=None, grid_center_z=None,
                grid_size_x=None, grid_size_y=None, grid_size_z=None,
            )
        if pid == "USR_MIA":
            return SimpleNamespace(
                pdb_id="USR_MIA", name="Anti-diana propia",
                chain="B", affinity_threshold=-6.5,
            )
        return None


# ── 1. El contrato del panel: el sitio se resuelve contra el catálogo ──


@pytest.mark.asyncio
async def test_el_panel_resuelve_el_sitio_multicadena_con_repositorio(monkeypatch):
    """La ruta manual ya cumplía esto; ahora es el contrato de ambas.

    La fila del panel trae la caja curada del bolsillo tóxico; la composición
    del sitio la manda el catálogo. El docking debe recibir las CUATRO
    cadenas de hERG, no `chain="A"` con `site_chains=None`.
    """
    import services.docking.vina_service as vina

    capturados: list[dict] = []

    async def _dock(**kwargs):
        capturados.append(kwargs)
        return SimpleNamespace(best_affinity=-6.0, poses=[SimpleNamespace()])

    monkeypatch.setattr(vina, "run_vina_docking", _dock)

    resultado = await run_selectivity_panel(
        smiles="CCO",
        smiles_hash="hash-prueba",
        on_target_pdb="1ABC",
        on_target_affinity=-8.0,
        anti_targets=["5VA1"],
        repository=_RepoConCatalogo(),
        docking_protocol=PROTOCOLO,
    )

    # La fila del resultado declara lo mismo que registra la ruta manual:
    # site_chains resueltos y procedencia de la caja.
    herg = next(r for r in resultado.off_targets if r["pdb_id"] == "5VA1")
    assert herg["status"] == "ok"
    assert herg["site_chains"] == ["A", "B", "C", "D"]
    assert herg["procedencia_caja"] == "panel"

    # Y el acoplamiento recibió el sitio completo, no el fallback monomérico.
    assert len(capturados) == 1
    assert capturados[0]["site_chains"] == ["A", "B", "C", "D"]
    assert capturados[0]["target_center"] == tuple(HERG["center"])


# ── 2. El cableado del subprocess: la ruta automática también ─────────


def test_el_subprocess_le_entrega_su_repositorio_al_panel(monkeypatch, capsys):
    """AMP-03, el defecto de cableado: llamar `main()` del subprocess y
    comprobar que el panel recibe un repositorio VIVO, no `None`.

    Sin él, `dock_one` caía al fallback (`at.get("chain", "A")`,
    `site_chains=None`) y el panel automático acoplaba media cavidad con
    `status: "ok"` — un número de seguridad sobre un bolsillo inexistente.

    El test es síncrono a propósito: `main()` arranca su propio bucle con
    `asyncio.run()`, como hace el proceso real.
    """
    import services.docking.selectivity as panel
    import services.docking.selectivity_subprocess as sub
    import core.database as base_datos
    import db.repository as repositorio_modulo

    capturado: dict = {}

    async def _panel_falso(**kwargs):
        capturado.update(kwargs)
        return panel.SelectivityResult(
            on_target_affinity=-8.0,
            on_target_pdb="1ABC",
            off_targets=[dict(HERG, affinity=-6.0, poses=1, status="ok")],
            selectivity_ratio=2.0,
            delta_delta_g_kcal=0.4,
            safety_flags=[],
            execution_time_s=1.0,
        )

    class _DbFalso:
        async def commit(self) -> None:
            pass

    @asynccontextmanager
    async def _sesion_falsa():
        yield _DbFalso()

    class _RepoFalso:
        def __init__(self, db) -> None:
            self.db = db

        async def set_selectivity_results(self, **_kwargs) -> None:
            return None

    monkeypatch.setattr(panel, "run_selectivity_panel", _panel_falso)
    monkeypatch.setattr(sub, "veredicto_de_margen", lambda _d: "margen_prueba")
    monkeypatch.setattr(base_datos, "get_db_session", _sesion_falsa)
    monkeypatch.setattr(base_datos, "flush_with_retry", _flush_falsa)
    monkeypatch.setattr(repositorio_modulo, "Repository", _RepoFalso)

    molecule_id = str(uuid.uuid4())
    monkeypatch.setattr(
        sys,
        "argv",
        ["selectivity_subprocess.py", molecule_id, "CCO", "hash", "1ABC",
         "-8.0", "2", "5VA1"],
    )

    codigo = sub.main()

    assert codigo == 0
    # EL REPOSITORY: sin él no hay catálogo, no hay site_chains y no hay
    # anti-dianas del usuario. Es la diferencia que la auditoría midió.
    assert capturado.get("repository") is not None, (
        "el subprocess llamó al panel sin repositorio: la anti-diana "
        "multicadena cae al fallback monomérico (AMP-03)"
    )


async def _flush_falsa(_db) -> None:
    return None


# ── 3. La anti-diana del usuario: mismo cableado, síntoma gemelo ──────


@pytest.mark.asyncio
async def test_con_repositorio_la_anti_diana_del_usuario_se_resuelve():
    """`seleccionar_anti_dianas` con repositorio: la anti-diana subida sale
    del catálogo con su umbral. Es lo que la ruta automática hereda ahora;
    sin repositorio quedaba listada como «desconocida» y el cociente se
    calculaba con menos cobertura de la que el usuario marcó."""
    elegidas, desconocidas = await seleccionar_anti_dianas(
        ["USR_MIA"], _RepoConCatalogo()
    )
    assert [t["pdb_id"] for t in elegidas] == ["USR_MIA"]
    assert desconocidas == []
    assert elegidas[0]["affinity_threshold"] == -6.5
