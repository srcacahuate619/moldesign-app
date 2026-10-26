"""
Las reservas del receptor se agrupan con su recuento (CAS-07).

La auditoría lo midió en vivo (caso de 40 corridas): ensemble-M01 conservaba
**64 avisos** — 30 `RECEPTOR_PROTONACION_DECLARADA` y 30
`SITIO_DESOLVATADO` — mientras la misma molécula en corrida única tenía
cinco. No son 30 receptores distintos ni 30 decisiones independientes sobre
las aguas: es el mismo receptor acoplado 30 veces, y cada conformación
arrastraba una copia de sus reservas al fusionar
(`ensemble.py::avisos.extend`, línea 234).

Impacto medido por la auditoría: sobrecarga de lectura, el bloque de
incertidumbres del PDF crecía hasta reventar la composición (lo corrigió
CAS-06) y la información «se conserva, pero no se comunica de manera útil
para revisar un caso repetidamente».

# La regla

Un aviso estructurado idéntico que aparece en cada conformación se emite
UNA vez, con su recuento. Lo que no es común — un fallo de acoplamiento, una
conformación sin poses, un aviso exclusivo de una conformación — viaja como
siempre, porque no es una repetición.
"""

from __future__ import annotations

import pytest

from core.models import DockingPose, DockingResult
from services.avisos import Severidad, aviso
from services.docking.ensemble import run_ensemble_docking

#: Las dos reservas del receptor que la auditoría contó 30 veces.
PROTONACION = aviso(
    "RECEPTOR_PROTONACION_DECLARADA",
    Severidad.PRECAUCION,
    "Plantillas de histidina de Meeko: HIS57=HIE. El microestado experimental no está validado.",
)
DESOLVATACION = aviso(
    "SITIO_DESOLVATADO",
    Severidad.PRECAUCION,
    "Se retiraron 10 aguas estructurales a ≤6 Å del sitio antes de acoplar.",
)

NOTA_EN_CAJA = aviso(
    "LIGANDO_EXCEDE_CAJA",
    Severidad.PRECAUCION,
    "Un átomo del ligando queda a más de 4 Å del borde de la caja.",
)


def _pose(rank: int, afinidad: float) -> DockingPose:
    return DockingPose(rank=rank, affinity=afinidad, rmsd_lb=0.0, rmsd_ub=0.0)


def _miembro(afinidad: float, avisos: list) -> DockingResult:
    return DockingResult(
        best_affinity=afinidad,
        poses=[_pose(1, afinidad)],
        parsing_source="sdf",
        scientific_warnings=avisos,
    )


def _conformeros(k: int) -> list[dict]:
    return [{"indice": i, "smiles_hash": f"h{i}"} for i in range(k)]


async def _ensemble(conformeros, dock):
    return await run_ensemble_docking(
        smiles="O=C(O)c1ccccc1",
        conformeros=conformeros,
        num_poses=9,
        dock_una=dock,
    )


def _avisos_del_resultado(resultado) -> list:
    return list(resultado.scientific_warnings or [])


def _mensajes_estructurados(resultado) -> list[str]:
    return [
        a["mensaje"]
        for a in _avisos_del_resultado(resultado)
        if isinstance(a, dict)
    ]


# ── 1. La reproducción de la auditoría ────────────────────────────────


@pytest.mark.asyncio
async def test_las_reservas_del_receptor_aparecen_una_vez_con_su_recuento():
    """El mismo receptor acopló 30 veces; sus reservas no son 30 decisiones.

    Antes: 30 copias idénticas de cada reserva (60 avisos, más los del
    propio ensemble). Ahora: una copia, con el recuento que dice qué son.
    """
    async def dock(smiles_hash, smiles=None):
        return _miembro(-6.0, [dict(PROTONACION), dict(DESOLVATACION)])

    resultado = await _ensemble(_conformeros(30), dock)
    mensajes = _mensajes_estructurados(resultado)

    protonacion = [m for m in mensajes if "HIS57=HIE" in m]
    assert len(protonacion) == 1, (
        f"la reserva de protonación aparece {len(protonacion)} veces: "
        "el mismo receptor no genera 30 decisiones"
    )
    assert "Aviso idéntico en las 30 conformaciones que acoplaron" in protonacion[0]

    desolvatacion = [m for m in mensajes if "aguas estructurales" in m]
    assert len(desolvatacion) == 1
    assert "Aviso idéntico en las 30 conformaciones que acoplaron" in desolvatacion[0]


@pytest.mark.asyncio
async def test_el_aviso_exclusivo_de_una_conformacion_no_se_anota():
    """Lo que NO es común no lleva recuento: es una incidencia particular."""
    async def dock(smiles_hash, smiles=None):
        avisos = [dict(PROTONACION)]
        if smiles_hash == "h3":
            avisos.append(dict(NOTA_EN_CAJA))
        return _miembro(-6.0, avisos)

    resultado = await _ensemble(_conformeros(10), dock)
    mensajes = _mensajes_estructurados(resultado)

    en_caja = [m for m in mensajes if "borde de la caja" in m]
    assert len(en_caja) == 1
    # Una sola conformación lo produjo: sin recuento, tal cual.
    assert "Aviso idéntico" not in en_caja[0]
    assert "Repetido" not in en_caja[0]


@pytest.mark.asyncio
async def test_un_aviso_de_varias_conformaciones_declara_cuantas():
    """Repetido en algunas —no todas—: el recuento parcial también se dice."""
    async def dock(smiles_hash, smiles=None):
        avisos = [dict(PROTONACION)]
        if smiles_hash in {"h0", "h1", "h2", "h3", "h4"}:
            avisos.append(dict(NOTA_EN_CAJA))
        return _miembro(-6.0, avisos)

    resultado = await _ensemble(_conformeros(30), dock)
    mensajes = _mensajes_estructurados(resultado)

    en_caja = [m for m in mensajes if "borde de la caja" in m]
    assert len(en_caja) == 1
    assert "(Repetido en 5 de 30 conformaciones.)" in en_caja[0]


# ── 2. Las incidencias particulares viajan como siempre ──────────────


@pytest.mark.asyncio
async def test_los_fallos_particulares_de_cada_conformacion_viajan_iguales():
    """La conformación que no acopló se declara una vez, sin agrupar.

    Y el recuento de las reservas del sistema habla de las que SÍ acoplaron:
    el denominador honesto, igual que el resumen del ensemble.
    """
    async def dock(smiles_hash, smiles=None):
        if smiles_hash == "h1":
            raise RuntimeError("sin Vina")
        return _miembro(-6.0, [dict(PROTONACION)])

    resultado = await _ensemble(_conformeros(5), dock)
    avisos = _avisos_del_resultado(resultado)

    fallos = [a for a in avisos if isinstance(a, str) and "conformación 1" in a]
    assert len(fallos) == 1
    # El fallo va tal cual: no es una repetición y no se le inventa recuento.
    assert "Aviso idéntico" not in fallos[0]

    protonacion = [
        a["mensaje"] for a in avisos
        if isinstance(a, dict) and "HIS57=HIE" in a["mensaje"]
    ]
    assert len(protonacion) == 1
    assert "Aviso idéntico en las 4 conformaciones que acoplaron" in protonacion[0]


@pytest.mark.asyncio
async def test_el_resumen_del_ensemble_viaja_unico_y_sin_anotar():
    """El denominador del propio ensemble no es una reserva repetida: se
    agrega después de agrupar y viaja una vez, tal cual."""
    async def dock(smiles_hash, smiles=None):
        return _miembro(-6.0, [dict(PROTONACION)])

    resultado = await _ensemble(_conformeros(6), dock)
    resumen = [
        a for a in _avisos_del_resultado(resultado)
        if isinstance(a, str) and a.startswith("Ensemble conformacional")
    ]
    assert len(resumen) == 1
    assert "Aviso idéntico" not in resumen[0]
