"""Reconstruye el censo de ChEMBL y prueba las propuestas sobre especies de MolDesign."""

import argparse
import ast
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path
from statistics import median

from rdkit import Chem
from scipy.stats import beta

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
N_CATION = "[NX4+;!H0;!$(N[a]);!$(N~[N,O,S,P]);!$(N-[C,S,P]=[O,N,S])]"
N_NEUTRO = "[NX3+0;!$(N[a]);!$(N~[N,O,S,P]);!$(N-[C,S,P]=[O,N,S])]"
MORFO = "1[CX4;R1][CX4;R1][OX2;H0;R1][CX4;R1][CX4;R1]1"
MORFO_ALQUILO = "1(-[CX4;!R])[CX4;R1][CX4;R1][OX2;H0;R1][CX4;R1][CX4;R1]1"
GUARDA = Chem.MolFromSmarts("[CX3](=O)[OX1-]")


def patrones(neutro):
    n = N_NEUTRO if neutro else N_CATION
    n_alquilo = "[NX3+0;H0;R1;!$(N[a])]" if neutro else "[NX4+;H1;R1;!$(N[a])]"
    n_h = "[NX3+0;H1;R1;!$(N[a])]" if neutro else "[NX4+;H2;R1;!$(N[a])]"
    return {
        "aminoester": [f"{n}-[CX4]-[CX3](=[OX1])-[OX2;H0]-[#6]"],
        "aminocetona": [f"{n}-[CX4]-[CX3H0](=[OX1])-[#6]", f"{n}-[CX4]-[CX3H1](=[OX1])"],
        "alquilmorfolina": [n_alquilo + MORFO_ALQUILO],
        "morfolina_nh": [n_h + MORFO],
        "propargilamina": [f"{n}-[CX4]-[CX2]#[CX2]"],
        "sulfona_beta": [f"{n}-[CX4]-[CX4]-[SX4](=[OX1])(=[OX1])-[#6]"],
        "aminoamida": [f"{n}-[CX4]-[CX3](=[OX1])-[#7]"],
        "oxetano_beta": [f"{n}-[CX4;R1]1[CX4;R1][OX2;H0;R1][CX4;R1]1"],
    }


def compilar(neutro=False):
    compiled = {name: [Chem.MolFromSmarts(s) for s in options] for name, options in patrones(neutro).items()}
    assert all(q is not None for options in compiled.values() for q in options)
    return compiled


def coincidencias(smiles, compiled, neutro=False):
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        raise ValueError(f"SMILES inválido: {smiles}")
    if not neutro and mol.HasSubstructMatch(GUARDA):
        return set()
    return {name for name, options in compiled.items() if any(mol.HasSubstructMatch(q) for q in options)}


def controles_versionados():
    path = ROOT / "backend/tests/test_especie_en_revision.py"
    test = ast.parse(path.read_bytes())
    dictionaries = {}
    for node in test.body:
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
            if name in {"CORRECTAS_VERIFICADAS", "ERRORES_CONFIRMADOS", "AMINAS_CON_ATRACTOR_ACOPLADAS"}:
                dictionaries[name] = ast.literal_eval(node.value)
    expected = {"CORRECTAS_VERIFICADAS": 17, "ERRORES_CONFIRMADOS": 2, "AMINAS_CON_ATRACTOR_ACOPLADAS": 5}
    assert {name: len(rows) for name, rows in dictionaries.items()} == expected
    for group, rows in dictionaries.items():
        for name, value in rows.items():
            smiles = value[0] if group == "ERRORES_CONFIRMADOS" else value
            yield dict(nombre=name, smiles_ensayado=smiles, smiles_acoplado=smiles, esperadas=[], origen=group)
    for node in test.body:
        if isinstance(node, ast.FunctionDef) and node.name in {
            "test_controles_negativos", "test_amina_con_atractor_controles_negativos",
        }:
            pairs = ast.Expression(node.decorator_list[0].args[1])
            controls = eval(compile(pairs, str(path), "eval"), {"__builtins__": {}}, dictionaries)
            for name, smiles in controls:
                yield dict(nombre=name, smiles_ensayado=smiles, esperadas=[], origen=node.name)


def medir_controles(medidas, compiled):
    inputs = json.loads((HERE / "fronteras.json").read_text(encoding="utf-8"))
    rows = list(controles_versionados())
    for name, smiles, expected in inputs:
        rows.append(dict(nombre=name, smiles_ensayado=smiles, esperadas=expected,
                         origen="control estructural construido"))
    seen = set()
    for row in medidas:
        smiles = row["smiles_catión_objetivo"]
        name = row["compuesto"]
        if not smiles or name in seen:
            continue
        seen.add(name)
        rows.append(dict(nombre=name, smiles_ensayado=smiles, smiles_acoplado=row["smiles_preparado"],
                         esperadas=row["patrones_esperados"], origen="compuesto con fuente",
                         nivel=row["nivel"]))
    for row in rows:
        row["observadas"] = sorted(coincidencias(row["smiles_ensayado"], compiled))
        docked = row.get("smiles_acoplado")
        if docked and not docked.startswith("ERROR:"):
            row["observadas_en_especie_acoplada"] = sorted(coincidencias(docked, compiled))
    measures = {}
    for name in compiled:
        measures[name] = {
            kind: sum((name in r["esperadas"], name in r["observadas"]) == pair for r in rows)
            for kind, pair in {"vp": (True, True), "vn": (False, False), "fp": (False, True), "fn": (True, False)}.items()
        }
    return rows, measures


def medir_chembl(path):
    sys.path.insert(0, str(HERE.parent / "investigacion-1.0.4"))
    from medir_d04 import ARCHIVE, reference_data, sha

    data, _ = reference_data(path)
    expected = {row["id_anonimo"]: row for row in map(json.loads, (ARCHIVE / "per_complex.jsonl").read_bytes().splitlines())}
    assert len(data) == len(expected) == 2345
    compiled = compilar(neutro=True)
    matches = {name: [] for name in compiled}
    for smiles, row in data.items():
        key = sha(smiles.encode())
        assert row == {k: v for k, v in expected[key].items() if k != "id_anonimo"}
        if row["centro"] != "base" or row["clase"] != "amina_alifatica":
            continue
        for branch in coincidencias(smiles, compiled, neutro=True):
            matches[branch].append({"id_anonimo": key, "pka": row["pka"], "fila_sdf": row["mediciones"][0]["fila_sdf"]})
    return {name: sorted(rows, key=lambda r: r["id_anonimo"]) for name, rows in matches.items()}


def preparar_medidas():
    """Usa la misma preparación del producto en serie y sin redocking."""
    sys.path.insert(0, str(ROOT / "backend"))
    from chem.conformer import _construir_conformero

    source = json.loads((HERE / "medidas.json").read_text(encoding="utf-8"))
    prepared = {}
    output = []
    for compound in source["compuestos"]:
        name, smiles, cation, expected, studies = compound
        try:
            if smiles and smiles not in prepared:
                prepared[smiles] = _construir_conformero(smiles, ph=7.4)["canonical_smiles"]
        except Exception as error:
            prepared[smiles] = f"ERROR: {type(error).__name__}: {error}"
        for branch, source_id, pka, locator in studies:
            record = source["fuentes"][source_id]
            output.append(dict(
                compuesto=name, clase=branch, smiles_neutro=smiles, smiles_preparado=prepared.get(smiles, ""),
                smiles_catión_objetivo=cation, patrones_esperados=expected, pka=pka,
                temperatura_c=record["T"], fuerza_ionica=record["I"], metodo=record["metodo"],
                fuente_id=source_id, origen_independiente=record.get("grupo", source_id),
                fuente=record["url"], localizador=locator, nivel=record["nivel"],
            ))
    return output


def clasificar_fronteras():
    from chem.ionizacion import _explorar_centros

    parents = {
        "N-alquilmorfolina": "CN1CCOCC1",
        "morfolina_NH": "N1CCOCC1",
        "N-arilmorfolina": "c1ccccc1N1CCOCC1",
        "N-acilmorfolina": "CC(=O)N1CCOCC1",
        "morfolina_fusionada": "CN1CC2OCC1CCC2",
        "tiomorfolina": "N1CCSCC1",
        "oxetan-3-ilamina": "NC1COC1",
        "oxazolidina": "CN1CCOC1",
    }
    return {name: {"smiles": smiles, "centros": _explorar_centros(Chem.MolFromSmiles(smiles))[0]}
            for name, smiles in parents.items()}


def primaria(medidas, branches):
    by_branch = defaultdict(lambda: defaultdict(list))
    sources = defaultdict(set)
    for row in medidas:
        if row["nivel"] == "A":
            branch = row["clase"]
            family = next((name for name in ("propargilamina", "sulfona_beta") if branch.startswith(name + "_")), branch)
            for group in {branch, family}:
                by_branch[group][row["compuesto"]].append(row["pka"])
                sources[group].add(row["origen_independiente"])
    report = {}
    for branch in branches:
        values = [median(pkas) for pkas in by_branch[branch].values()]
        n = len(values)
        group_count = len(sources[branch])
        affected = sum(pka <= 8.9 for pka in values)
        band = sum(5.9 <= pka <= 8.9 for pka in values)
        stats = dict(n=n, fuentes_independientes=group_count, banda=band, hasta_8_9=affected, decision="INCONCLUSIVE")
        if values:
            stats.update(rango=[min(values), max(values)], mediana=median(values),
                         IC95_banda=[0 if band == 0 else beta.ppf(.025, band, n - band + 1),
                                     1 if band == n else beta.ppf(.975, band + 1, n - band)])
        if n >= 3 and group_count >= 2:
            if stats["mediana"] <= 8.9 and 3 * affected >= 2 * n:
                stats["decision"] = "GO"
            elif stats["mediana"] > 8.9 and 3 * affected < 2 * n:
                stats["decision"] = "NO_GO"
        report[branch] = stats
    return report


def save(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sdf", type=Path)
    parser.add_argument("--censo", action="store_true", help="Sólo valida el SDF y emite las coincidencias")
    options = parser.parse_args()
    census = medir_chembl(options.sdf)
    save(HERE / "censo-chembl.json", census)
    if options.censo:
        return
    measures = preparar_medidas()
    compiled = compilar()
    control, metrics = medir_controles(measures, compiled)
    with (HERE / "pka-por-clase.csv").open("w", encoding="utf-8", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=list(measures[0]))
        writer.writeheader()
        writer.writerows(measures)
    save(HERE / "controles.json", control)
    all_branches = set(compiled) | {row["clase"] for row in measures}
    save(HERE / "resultados.json", {
        "patrones_SMARTS": patrones(False), "controles": metrics, "primaria": primaria(measures, sorted(all_branches)),
        "centros_P4": clasificar_fronteras(),
        "chembl25": {branch: {"n": len(rows), "hasta_8_9": sum(row["pka"] <= 8.9 for row in rows),
                             "banda": sum(5.9 <= row["pka"] <= 8.9 for row in rows)}
                     for branch, rows in census.items()},
    })


if __name__ == "__main__":
    main()
