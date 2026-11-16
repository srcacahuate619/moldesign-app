"""Control negativo del comprobador estático de release, con configuración sólo en memoria."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
FILE = ROOT / "scripts/check_release_pipeline.py"
CONFIG = ROOT / "frontend/src-tauri/tauri.conf.json"


def main():
    spec = importlib.util.spec_from_file_location("release_review", FILE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    original = json.loads(CONFIG.read_bytes())
    commands = [c.strip() for c in original["build"]["beforeBuildCommand"].split("&&")]
    with contextlib.redirect_stdout(io.StringIO()):
        module.main()
    read = Path.read_text
    records = []
    for command in commands:
        changed = json.loads(json.dumps(original))
        changed["build"]["beforeBuildCommand"] = " && ".join(c for c in commands if c != command)

        def patched(path, *args, **kwargs):
            if path.resolve() == CONFIG.resolve():
                return json.dumps(changed)
            return read(path, *args, **kwargs)

        detected = False
        with patch.object(Path, "read_text", patched), contextlib.redirect_stdout(io.StringIO()):
            try:
                module.main()
            except RuntimeError:
                detected = True
        records.append({"comando_retirado_en_memoria": command, "omision_detectada": detected})
    assert len(commands) == 16
    assert any(r["comando_retirado_en_memoria"] == "npm run check:evaluation-runtime" and not r["omision_detectada"] for r in records)
    result = {"tipo": "Controles negativos del guardián estático; no ejecuta las puertas ni modifica Tauri",
              "base_sin_mutar_pasa": True, "puertas_declaradas": len(commands), "controles": records}
    (HERE / "b11-cobertura-guardia.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
