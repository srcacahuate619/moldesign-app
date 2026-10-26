"""Mide el desajuste entre el dibujo 2D y la geometría 3D alineada (elevacion/v1).

Dos conjuntos, sólo lectura:
  1. Moléculas: SMILES de los paneles congelados de CAL-8HFI-01 y CAL-D-01-R4
     (ligandos reales de ChEMBL y de patente) más unas pocas moléculas conocidas
     escritas a mano (validadas con RDKit).
  2. Poses: registros de SDF de corridas Vina reales (dossier de cierre 1.0.2 y
     fixtures de Meeko), con el SMILES de entrada de cada caso.

Se llama a las funciones de PRODUCTO (`modelo_desde_conformador`, `modelo_desde_pose`)
para que la cifra sea la que ve el usuario. Uso:
    python medir_desajuste.py <carpeta_de_salida>
"""
import csv
import json
import pathlib
import sys
import time

import numpy as np
from rdkit import Chem
from rdkit.Chem import rdMolDescriptors

RAIZ = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RAIZ / "backend"))
from chem import elevacion as el  # noqa: E402

CIENCIA = RAIZ / "scripts" / "artifacts_science"
SALIDA = pathlib.Path(sys.argv[1])
SALIDA.mkdir(parents=True, exist_ok=True)

PANELES = [
    ("CAL-8HFI-01 panel_congelado", CIENCIA / "CAL-8HFI-01" / "entrada" / "panel_congelado.csv"),
    ("CAL-D-01-R4 panel_congelado", CIENCIA / "CAL-D-01-R4-VMAT2-8T69" / "entrada" / "panel_congelado.csv"),
]

CONOCIDAS = {
    "aspirina": "CC(=O)Oc1ccccc1C(=O)O",
    "ibuprofeno": "CC(C)Cc1ccc(cc1)C(C)C(=O)O",
    "cafeina": "Cn1cnc2c1c(=O)n(C)c(=O)n2C",
    "paracetamol": "CC(=O)Nc1ccc(O)cc1",
    "diazepam": "CN1C(=O)CN=C(c2ccccc2)c2cc(Cl)ccc21",
    "warfarina": "CC(=O)CC(c1ccccc1)c1c(O)c2ccccc2oc1=O",
    "imatinib": "Cc1ccc(NC(=O)c2ccc(CN3CCN(C)CC3)cc2)cc1Nc1nccc(-c2cccnc2)n1",
    "sildenafilo": "CCCc1nn(C)c2c(=O)[nH]c(-c3cc(S(=O)(=O)N4CCN(C)CC4)ccc3OCC)nc12",
    "nicotina": "CN1CCCC1c1cccnc1",
    "dopamina": "NCCc1ccc(O)c(O)c1",
    "lidocaina": "CCN(CC)CC(=O)Nc1c(C)cccc1C",
    "atorvastatina": "CC(C)c1n(CC[C@@H](O)C[C@@H](O)CC(=O)O)c(-c2ccccc2)c(C(=O)Nc2ccccc2)c1-c1ccc(F)cc1",
    "pentadecanolido": "O=C1CCCCCCCCCCCCCO1",
    "ciclohexano": "C1CCCCC1",
    "bifenilo": "c1ccc(-c2ccccc2)cc1",
    "naftaleno": "c1ccc2ccccc2c1",
    "antraceno": "c1ccc2cc3ccccc3cc2c1",
    "acido_palmitico": "CCCCCCCCCCCCCCCC(=O)O",
    "glucosa": "OC[C@H]1OC(O)[C@H](O)[C@@H](O)[C@@H]1O",
    "colesterol": "CC(C)CCCC(C)C1CCC2C1(CCC3C2CC=C4C3(CCC(C4)O)C)C",
}


def longitud_de_enlace_px(smiles):
    """Longitud media de enlace del dibujo, en px del lienzo de 300 px."""
    mol = Chem.MolFromSmiles(smiles)
    dibujo = el.dibujo_2d(mol)
    a, _, _ = el._mapa_al_lienzo(dibujo.plano, dibujo.lienzo)
    longitudes = [
        float(np.linalg.norm(dibujo.plano[b.GetBeginAtomIdx()] - dibujo.plano[b.GetEndAtomIdx()]))
        for b in mol.GetBonds()
    ]
    return a * float(np.mean(longitudes)) if longitudes else float("nan")


def moleculas():
    vistos = {}
    for origen, ruta in PANELES:
        with open(ruta, encoding="utf-8-sig", newline="") as f:
            for fila in csv.DictReader(f):
                mol = Chem.MolFromSmiles(fila["smiles"].strip())
                if mol is None:
                    continue
                can = Chem.MolToSmiles(mol)
                # Una molécula que aparece en los dos paneles cuenta una vez.
                vistos.setdefault(can, {"id": fila.get("padre", ""), "origen": origen, "smiles": can})
    for nombre, smi in CONOCIDAS.items():
        mol = Chem.MolFromSmiles(smi)
        assert mol is not None, nombre
        can = Chem.MolToSmiles(mol)
        vistos.setdefault(can, {"id": nombre, "origen": "conocida (SMILES escrito a mano)", "smiles": can})
    return list(vistos.values())


def medir_molecula(m):
    smi = m["smiles"]
    mol = Chem.MolFromSmiles(smi)
    fila = dict(m)
    fila["pesados"] = mol.GetNumAtoms()
    fila["enlaces_rotables"] = rdMolDescriptors.CalcNumRotatableBonds(mol)
    fila["anillos"] = rdMolDescriptors.CalcNumRings(mol)
    fila["carga"] = Chem.GetFormalCharge(mol)
    fila["estereo_declarado"] = len(Chem.FindMolChiralCenters(mol, includeUnassigned=False, useLegacyImplementation=False))
    try:
        fila["enlace_px"] = round(longitud_de_enlace_px(smi), 3)
    except Exception as exc:  # noqa: BLE001 - se registra, no se oculta
        fila["error"] = f"dibujo: {type(exc).__name__}: {exc}"
        return fila
    try:
        inicio = time.time()
        defecto = el.modelo_desde_conformador(smi)
        fila["segundos"] = round(time.time() - inicio, 2)
        fila["candidatos_defecto"] = defecto["conformador"]["candidatos"]
        fila["desajuste_defecto"] = defecto["desajuste_px"]
        fila["campo"] = defecto["conformador"]["campo_de_fuerza"]
        # Mismo número de candidatos (16) para todas, con tres semillas: separa la
        # forma de la molécula del azar del muestreo y del recorte por tamaño.
        fila["desajuste_16"] = {}
        for semilla in (1, 2, 3):
            fila["desajuste_16"][str(semilla)] = el.modelo_desde_conformador(
                smi, conformadores=16, semilla=semilla
            )["desajuste_px"]
    except el.ElevacionNoDisponible as exc:
        fila["error"] = f"no disponible: {exc}"
    except Exception as exc:  # noqa: BLE001
        fila["error"] = f"{type(exc).__name__}: {exc}"
    return fila


def registros(ruta):
    texto = ruta.read_text(encoding="utf-8").replace("\r\n", "\n")
    bloques = [b for b in texto.split("$$$$\n") if b.strip()]
    return [b + "$$$$\n" for b in bloques]


def poses():
    dossier = RAIZ / "docs" / "verificacion" / "cierre-1-0-2" / "dossier-en" / (
        "moldesign_case_350e8d04-4273-41f5-b818-72ab44f3c95e_run_27c62c96-a89"
    )
    fixtures = RAIZ / "backend" / "tests" / "fixtures" / "meeko_export"
    casos = [
        ("dossier 1.0.2, 9 poses", dossier / "inputs" / "ligand_input.sdf", dossier / "outputs" / "poses.sdf"),
        ("paracetamol, fixture Meeko", fixtures / "paracetamol_9_poses.sdf", fixtures / "paracetamol_9_poses.sdf"),
        ("exaltolida macrociclo, fixture Meeko", fixtures / "exaltolida_conformero_de_entrada.sdf", fixtures / "exaltolida_macrociclo.sdf"),
    ]
    filas = []
    for nombre, ruta_entrada, ruta_poses in casos:
        smi_entrada = Chem.MolToSmiles(Chem.MolFromMolBlock(registros(ruta_entrada)[0].split("$$$$")[0], removeHs=True))
        bl = enlace = None
        try:
            enlace = longitud_de_enlace_px(smi_entrada)
        except Exception as exc:  # noqa: BLE001
            print("ERROR dibujo", nombre, exc)
        for i, registro in enumerate(registros(ruta_poses), start=1):
            fila = {"caso": nombre, "registro": i, "smiles_entrada": smi_entrada, "enlace_px": enlace}
            try:
                modelo = el.modelo_desde_pose(smi_entrada, registro)
                fila["desajuste"] = modelo["desajuste_px"]
                fila["afinidad"] = modelo["pose"]["afinidad_kcal_mol"]
                fila["estereo_invertidos"] = len(modelo["pose"]["estereo"]["invertidos"])
                fila["carga_smiles"] = modelo["pose"]["especie"]["carga_smiles"]
                fila["carga_acoplada"] = modelo["pose"]["especie"]["carga_acoplada"]
            except el.ElevacionNoDisponible as exc:
                fila["error"] = f"no disponible: {exc}"
            except Exception as exc:  # noqa: BLE001
                fila["error"] = f"{type(exc).__name__}: {exc}"
            filas.append(fila)
    return filas


if __name__ == "__main__":
    lista = moleculas()
    print(f"moleculas: {len(lista)}", flush=True)
    with open(SALIDA / "moleculas.jsonl", "w", encoding="utf-8") as f:
        for i, m in enumerate(lista, start=1):
            fila = medir_molecula(m)
            f.write(json.dumps(fila, ensure_ascii=False) + "\n")
            f.flush()
            if i % 20 == 0:
                print(f"  {i}/{len(lista)}", flush=True)
    with open(SALIDA / "poses.jsonl", "w", encoding="utf-8") as f:
        for fila in poses():
            f.write(json.dumps(fila, ensure_ascii=False) + "\n")
    print("listo", flush=True)
