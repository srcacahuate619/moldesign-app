"""Guardas editoriales existentes sobre registro temporal, sin tocar frontend.

La integración en la app queda para el revisor: este encargo no cambia producto.
Se ejecutan los ocho tests existentes contra el registro científico candidato.
"""
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "scripts/artifacts_science/FEP-09-SENSIBILIDAD"
OUT = ROOT / "tmp/fep09-editorial-registry"


class CandidateRegistry:
    def pytest_collection_modifyitems(self, items):
        for item in items:
            if item.module.__name__.endswith("test_registro_cientifico"):
                item.module.PUBLICADO = OUT


def main():
    import pytest
    spec = importlib.util.spec_from_file_location("fep09_registry_builder", ROOT / "scripts/build_registro_cientifico.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    index, papers = module.construir()
    (OUT / "papers").mkdir(parents=True, exist_ok=True)
    (OUT / "index.json").write_text(json.dumps(index, ensure_ascii=False)+"\n", encoding="utf-8", newline="\n")
    for ident, paper in papers.items():
        (OUT / "papers" / f"{ident}.json").write_text(json.dumps(paper, ensure_ascii=False)+"\n", encoding="utf-8", newline="\n")
    assert "FEP-09-SENSIBILIDAD" in papers, "El registro candidato no incluye el paper nuevo"
    assert any(e["id"] == "FEP-09-SENSIBILIDAD" for e in index["experimentos"]), "El registro candidato no incluye el experimento"
    code = pytest.main([str(ROOT / "backend/tests/test_registro_cientifico.py"), "-q"], plugins=[CandidateRegistry()])
    print("Alcance: ocho guardas existentes, registro temporal; frontend instalado sin regenerar")
    return int(code)


if __name__ == "__main__":
    raise SystemExit(main())
