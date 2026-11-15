"""Regenera las comprobaciones adicionales de la respuesta a la réplica."""

import argparse
import asyncio
import gzip
import hashlib
import json
import math
import sys
from contextlib import redirect_stdout
from pathlib import Path
from statistics import median
from types import SimpleNamespace
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SCIENCE = ROOT / "scripts" / "artifacts_science"


def rows(experiment):
    path = SCIENCE / experiment / "per_complex.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def tiempos_8hfi():
    runs = rows("DEC-104-D06-8HFI")
    output = {}
    for arm in ("e8", "e8s43", "e16", "e32"):
        successful = [row for row in runs if row["brazo"] == arm and row["estado"] == "SUCCESS"]
        parents = [row for row in successful if row["pki"] is not None]

        def times(cohort):
            return [sum(attempt["segundos"] for attempt in row["intentos"]) for row in cohort]

        output[arm] = {
            "n_padres": len(parents), "n_redocking": len(successful) - len(parents),
            "mediana_s_padres": median(times(parents)),
            "mediana_s_todas": median(times(successful)),
        }
    return output


def negativos_ums():
    negative = [row for row in rows("DEC-104-D08-REPLAY") if row["familia_esperada"] is None]
    scope = {"sulfonamida", "hidroxamico", "tiol"}
    return {
        arm: {
            "sin_las_tres_familias": sum(not scope.intersection(row[arm]) for row in negative),
            "sin_ninguna_familia": sum(not row[arm] for row in negative),
            "otros_grupos": {row["smiles"]: row[arm] for row in negative if row[arm]},
        }
        for arm in ("antes", "despues")
    }


def geometria_7ul2():
    panel = ROOT / "backend" / "data" / "anti_dianas_bowes44.json"
    entry = next(row for row in json.loads(panel.read_text(encoding="utf-8"))["dianas"] if row.get("pdb_id") == "7UL2")
    pdb = ROOT / "data" / "targets" / "7UL2.pdb.gz"
    lines = gzip.decompress(pdb.read_bytes()).decode("ascii").splitlines()
    segments = [line.split() for line in lines if line.startswith("DBREF ") and line.split()[2] == entry["chain"]]
    heavy = [line for line in lines if line[21:22] == entry["chain"] and line[16:17] in {" ", "A"}
             and line[76:78].strip() not in {"H", "D", ""}]
    ligand = [line for line in heavy if line.startswith("HETATM") and line[17:20].strip() == entry["site_ligand"]]

    def coordinates(line):
        return tuple(float(line[offset:offset + 8]) for offset in (30, 38, 46))

    xyz = [coordinates(line) for line in ligand]
    center = [sum(axis) / len(xyz) for axis in zip(*xyz, strict=True)]
    contacts = []
    for _, _, _, lower, upper, _, uniprot, *_ in segments:
        atoms = [line for line in heavy if line.startswith("ATOM  ") and int(lower) <= int(line[22:26]) <= int(upper)]
        distance, nearest = min((math.dist(coordinates(line), point), line) for line in atoms for point in xyz)
        contacts.append({"uniprot": uniprot, "residuos_pdb": [int(lower), int(upper)], "atomos_modelados": len(atoms),
                         "distancia_minima_A": distance, "residuo_mas_cercano": nearest[17:27].strip()})
    return {"deposito": "7UL2", "sha256_pdb_gz": hashlib.sha256(pdb.read_bytes()).hexdigest(),
            "ligando": entry["site_ligand"], "atomos_ligando": len(xyz), "centro_calculado": center,
            "centro_panel": entry["center"], "desplazamiento_centro_A": math.dist(center, entry["center"]),
            "segmentos": contacts}


def sensibilidad_clopidogrel():
    data = json.loads((HERE / "resultados.json").read_text(encoding="utf-8"))["D04"]["clopidogrel"]
    logp = data["logp_crippen"]
    return [
        {"pka": pka, "logd_modelo": logp - math.log10(1 + 10 ** (pka - 7.4)),
         "fraccion_protonada": 1 / (1 + 10 ** (7.4 - pka))}
        for pka in (data["producto"]["pka"], 4.55)
    ]


def sonda_chai():
    import gemmi
    from services.dossier.preparacion_confianza import campo_de_confianza
    from services.targets import prediccion
    from services.targets.conversion_mmcif import mmcif_a_pdb

    fixture = ROOT / "backend" / "tests" / "data" / "receptores_propios" / "chai_cdk2_apo_recortado.cif"
    original = fixture.read_text(encoding="utf-8")
    document = gemmi.cif.read_string(original)
    first = document[0].find("_ma_qa_metric_local.", ["label_seq_id", "metric_value"])[0]
    previous = float(first[1])
    first[1] = "51"

    def analyze(text):
        conversion = mmcif_a_pdb(text, "x.cif")
        chains = {chain["original"]: chain["pdb"] for chain in conversion.informe["cadenas"]}
        details, values = prediccion.analizar("mmcif", text, conversion.pdb, chains)
        site = prediccion.confianza_del_sitio(values, conversion.pdb, (0, 0, 0), (20, 20, 20))
        field, _ = campo_de_confianza({**details, "sitio": site})
        label = {"fuente": details["fuente"], "lectura": details["convencion"].get("lectura"),
                 "verificada": details["convencion"]["verificada"], "afirma_calfa": "es el valor del Cα" in field.valor}
        return conversion.pdb, values, label

    pdb0, values0, label0 = analyze(original)
    pdb1, values1, label1 = analyze(document.as_string())
    return {"valor_local_original": previous, "valor_local_modificado": 51,
            "pdb_identico": pdb0 == pdb1, "mapa_local_distinto": values0 != values1,
            "original": label0, "modificado": label1}


async def sonda_alertas():
    from services.docking import selectivity, vina_service

    async def dock(**_):
        return SimpleNamespace(best_affinity=-7.2, poses=[object()])

    result = {}
    for flag in (False, True):
        async def targets(*_):
            return ([{"pdb_id": "7UL2", "name": "OPRK1", "chain": "R", "risk": "disforia",
                      "affinity_threshold": -7.0, "sitio_adjudicado": flag}], [])

        with patch.object(selectivity, "seleccionar_anti_dianas", targets), patch.object(vina_service, "run_vina_docking", dock):
            output = await selectivity.run_selectivity_panel(
                "CCO", "sintetico", "1ABC", -8.0, anti_targets=["7UL2"],
                docking_protocol={"engine": "vina", "exhaustiveness": 8, "num_poses": 9, "seed": 42},
            )
        result[str(flag).lower()] = {"alerta": any(text.startswith("ALERTA") for text in output.safety_flags),
                                     "margen_kcal": output.delta_delta_g_kcal, "peor_anti_diana": output.peor_anti_diana}
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--producto", action="store_true", help="Sondas sintéticas sobre el árbol de trabajo")
    args = parser.parse_args()
    report = {"D04_clopidogrel": sensibilidad_clopidogrel(), "D06_tiempos": tiempos_8hfi(),
              "D08_negativos": negativos_ums(), "D09_7UL2": geometria_7ul2()}
    if args.producto:
        sys.path.insert(0, str(ROOT / "backend"))
        with redirect_stdout(sys.stderr):
            report["D01_convencion"] = sonda_chai()
            with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
                report["D09_alerta_simulada"] = runner.run(sonda_alertas())
    print(json.dumps(report, indent=2))
