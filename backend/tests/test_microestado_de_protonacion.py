"""Cuál de los microestados de dimorphite-dl se acopla, y por qué el mismo siempre.

Auditoría de backend del 2026-09-04, §2.4. `chem/conformer.py` se quedaba con
`protonated_list[0]`. Dos defectos, y el segundo no estaba en la auditoría:

1. **`[0]` no es el estado fisiológico.** La lista no viene ordenada por
   población. Al propranolol —amina secundaria, pKa ≈ 9.5, más del 99 %
   protonada a pH 7.4— le tocaba a veces la forma neutra; a la histidina, un
   imidazolato con la amina sin protonar, dos especies que a 7.4 no coexisten.

2. **`[0]` no es el mismo entre corridas.** Ejecutando el mismo SMILES en cinco
   procesos separados, `protonate_smiles` devolvió la lista en otro orden cada
   vez: cuatro `[0]` distintos para la lisina, tres para la histidina.

El segundo es el grave. El SMILES elegido se canoniza y se vuelve a hashear, y
ese hash nombra el archivo del conformer y la entrada de caché del
acoplamiento. Una molécula podía producir dos hashes, dos conformeros y dos
afinidades en dos corridas, con el caso enseñando el SMILES del usuario en las
dos. Es exactamente la clase de divergencia silenciosa que este producto existe
para detectar.

`chem/ionizacion.elegir_microestado` compara los recuentos de carga formal de
cada candidato con los centros que la tabla de pKa por clase predice ionizados a
pH 7.4, y desempata por orden alfabético del SMILES —una propiedad de la
molécula— en vez de por la posición en la lista.

Las especies esperadas de abajo son de manual de química medicinal, no ajustadas
a esta implementación.
"""

from __future__ import annotations

import pytest

from chem.ionizacion import cargas_esperadas_a_ph, elegir_microestado

dimorphite_dl = pytest.importorskip(
    "dimorphite_dl",
    reason="sin dimorphite-dl no hay microestados que elegir; la corrida cae a la forma neutra",
)


def _microestados(smiles: str) -> list[str]:
    return list(
        dimorphite_dl.protonate_smiles(smiles, ph_min=7.4, ph_max=7.4, precision=1.0)
    )


# (nombre, SMILES neutro, cationes esperados, aniones esperados)
CASOS = [
    ("propranolol", "CC(C)NCC(O)COc1cccc2ccccc12", 1, 0),
    ("histidina", "N[C@@H](Cc1c[nH]cn1)C(O)=O", 1, 1),
    ("lisina", "NCCCC[C@H](N)C(O)=O", 2, 1),
    ("gaba", "NCCCC(O)=O", 1, 1),
    ("aspirina", "CC(=O)Oc1ccccc1C(=O)O", 0, 1),
]


@pytest.mark.parametrize("nombre,smiles,cationes,aniones", CASOS)
def test_los_centros_esperados_son_los_de_manual(
    nombre: str, smiles: str, cationes: int, aniones: int
):
    """La cuenta de centros ionizados a pH 7.4, antes de elegir nada.

    La lisina es el caso que obliga a contar por instancia y no por clase: tiene
    DOS aminas alifáticas, y a pH 7.4 las dos están protonadas.
    """
    assert cargas_esperadas_a_ph(smiles) == (cationes, aniones), (
        f"{nombre}: la tabla de clases dejó de predecir el estado esperado"
    )


@pytest.mark.parametrize("nombre,smiles,cationes,aniones", CASOS)
def test_el_microestado_elegido_tiene_las_cargas_del_estado_fisiologico(
    nombre: str, smiles: str, cationes: int, aniones: int
):
    from rdkit import Chem

    elegido, criterio = elegir_microestado(smiles, _microestados(smiles))
    mol = Chem.MolFromSmiles(elegido)
    assert mol is not None, f"{nombre}: el microestado elegido no se puede leer"

    positivos = sum(1 for a in mol.GetAtoms() if a.GetFormalCharge() > 0)
    negativos = sum(1 for a in mol.GetAtoms() if a.GetFormalCharge() < 0)

    assert (positivos, negativos) == (cationes, aniones), (
        f"{nombre}: se acoplaría {elegido} (+{positivos}/-{negativos}) cuando a "
        f"pH 7.4 se espera +{cationes}/-{aniones}. Criterio: {criterio}"
    )


@pytest.mark.parametrize("nombre,smiles,_c,_a", CASOS)
def test_la_eleccion_no_depende_del_orden_en_que_venga_la_lista(
    nombre: str, smiles: str, _c: int, _a: int
):
    """El desempate tiene que ser una propiedad de la molécula, no de la corrida.

    Es la prueba del defecto 2. Se baraja la lista a mano —incluida la vuelta
    del revés— porque reproducir el barajado real de dimorphite exigiría lanzar
    procesos; el efecto sobre esta función es el mismo.
    """
    microestados = _microestados(smiles)
    if len(microestados) < 2:
        pytest.skip(f"{nombre} sólo tiene un microestado: no hay orden que alterar")

    referencia, _ = elegir_microestado(smiles, microestados)

    for permutacion in (
        list(reversed(microestados)),
        microestados[1:] + microestados[:1],
        sorted(microestados),
        sorted(microestados, reverse=True),
    ):
        elegido, _ = elegir_microestado(smiles, permutacion)
        assert elegido == referencia, (
            f"{nombre}: reordenar la lista cambió el microestado elegido "
            f"({referencia} -> {elegido}). El hash de la molécula dejaría de ser "
            "reproducible entre corridas."
        )


def test_sin_centros_reconocidos_se_conserva_el_primero_y_se_dice():
    """La cafeína no tiene centro ionizable: no hay nada que comparar."""
    smiles = "CN1C=NC2=C1C(=O)N(C)C(=O)N2C"
    assert cargas_esperadas_a_ph(smiles) is None

    microestados = _microestados(smiles)
    elegido, criterio = elegir_microestado(smiles, microestados)

    assert elegido == microestados[0]
    assert criterio["criterio"] == "primero_de_la_lista", (
        "Sin centros reconocidos el criterio tiene que declararse como tal, no "
        "aparentar una decisión que no se tomó."
    )


def test_una_lista_vacia_no_rompe_la_corrida():
    """dimorphite puede no devolver nada; eso no puede tumbar el acoplamiento."""
    elegido, criterio = elegir_microestado("CCO", [])
    assert elegido == "CCO"
    assert criterio["criterio"] == "sin_microestados"


@pytest.mark.asyncio
async def test_el_conformer_registra_con_que_criterio_eligio():
    """El dossier tiene que poder decir por qué se acopló esta especie."""
    from chem.conformer import generate_conformer

    resultado = await generate_conformer("NCCCC[C@H](N)C(O)=O")
    protonacion = resultado["estado_del_ligando"]["protonacion"]

    assert protonacion["aplicada"] is True
    seleccion = protonacion["seleccion"]
    assert seleccion["criterio"] == "cargas_esperadas_ph_7.4"
    assert seleccion["cationes_esperados"] == 2
    assert seleccion["aniones_esperados"] == 1
    assert seleccion["desajuste"] == 0, (
        "Se acopló un microestado que no coincide con el estado esperado y "
        "nadie lo notó: revisa el criterio antes que esta prueba."
    )
