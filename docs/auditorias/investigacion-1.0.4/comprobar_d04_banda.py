"""Recuenta el veredicto D-04 excluyendo ambos extremos de la banda decimal."""
import json
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EXP = ROOT / "scripts/artifacts_science/DEC-104-D04-CHEMBL"
LOW, HIGH = Decimal("7.1"), Decimal("7.7")


def main():
    rows = [json.loads(line, parse_float=Decimal) for line in (EXP / "per_complex.jsonl").read_text().splitlines()]
    values = json.loads((EXP / "metrics.json").read_text(), parse_float=Decimal)["candidatos"]
    result = {}
    for key, new in values.items():
        usable = [r for r in rows if r["clase"] == key and not r["ajuste"] and not LOW <= r["pka"] <= HIGH]
        correct = lambda pka, r: (pka > Decimal("7.4")) == (r["pka"] > Decimal("7.4"))
        result[key] = {
            "n": len(usable), "correctos_tabla": sum(correct(r["tabla"], r) for r in usable),
            "correctos_mediana": sum(correct(new, r) for r in usable),
        }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
