"""SCI-B-039: todo metrics.json con un experiment_id distinto del manifest está declarado."""
import json
from pathlib import Path

ART = Path(__file__).resolve().parents[1] / "artifacts_science"
DECL = json.loads((Path(__file__).resolve().parents[1] / "identidad_de_metricas.json").read_text(encoding="utf-8"))


def discrepancias(base: Path) -> dict:
    out = {}
    for man in sorted(base.glob("*/manifest.json")):
        met = man.parent / "metrics.json"
        if not met.exists():
            continue
        try:
            m = json.loads(met.read_text(encoding="utf-8-sig") or "{}")
        except json.JSONDecodeError:
            continue
        mid = m.get("experiment_id") if isinstance(m, dict) else None
        exp = json.loads(man.read_text(encoding="utf-8-sig"))["experiment_id"]
        if mid and mid != exp:
            out[exp] = mid
    return out


def test_el_detector_ve_una_discrepancia(tmp_path):
    d = tmp_path / "X-EXT"
    d.mkdir()
    (d / "manifest.json").write_text('{"experiment_id": "X-EXT"}', encoding="utf-8")
    (d / "metrics.json").write_text('{"experiment_id": "X"}', encoding="utf-8")
    assert discrepancias(tmp_path) == {"X-EXT": "X"}


def test_todas_las_discrepancias_estan_declaradas():
    reales = discrepancias(ART)
    declaradas = {k: v["metrics_experiment_id"] for k, v in DECL["heredados"].items()}
    assert reales == declaradas
