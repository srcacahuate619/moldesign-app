"""Repite sólo la geometría de 7UL2 con el método archivado; no cambia la entrega anterior."""
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "investigacion-1.0.4/comprobar_seguimiento_replica.py"


def main():
    spec = importlib.util.spec_from_file_location("seguimiento_archivado", SOURCE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    result = module.geometria_7ul2()
    assert result["ligando"] == "Q6Q" and result["atomos_ligando"] == 42
    ntsr1 = min(s["distancia_minima_A"] for s in result["segmentos"] if s["uniprot"] == "P30989")
    kappa = min(s["distancia_minima_A"] for s in result["segmentos"] if s["uniprot"] == "P41145")
    assert result["desplazamiento_centro_A"] < .001 and ntsr1 < 3.2 and kappa > 22
    (HERE / "d09-geometria.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(f"7UL2: Q6Q, 42 átomos; distancia a NTSR1 {ntsr1:.6f} A, a segmento kappa {kappa:.6f} A")


if __name__ == "__main__":
    main()
