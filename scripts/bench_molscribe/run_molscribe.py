"""MolScribe sobre figuras reales: ¿cuántas estructuras salen exactas, y sirve su confianza?

La función que se evalúa: el investigador pega una figura de un artículo o una
patente y la aplicación le propone el SMILES para que lo confirme en el editor.
Dos cosas deciden si vale la pena:

  1. el acierto exacto (SMILES canónico, sin distinguir cis/trans: la métrica
     `canon_smiles` del artículo), con el evaluador del propio MolScribe;
  2. si su `confidence` separa aciertos de fallos. Si filtrar por confianza alta
     no sube el acierto, la señal no sirve para decir «revisa esta», que es lo
     que el producto necesitaría.

El checkpoint se carga con `weights_only=True` (sin ejecutar código del pickle),
permitiendo sólo `argparse.Namespace`.

Uso (venv aparte, nunca el Python del producto):
  venv-molscribe/Scripts/python.exe -I run_molscribe.py --codigo <clon> --ckpt <pth> \
      --datos <dir con real/> --salida res.json [--por-conjunto acs=0,CLEF=200,USPTO=200]
"""
import argparse
import csv
import json
import random
import sys
import time
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--codigo", required=True)
    ap.add_argument("--ckpt", required=True)
    ap.add_argument("--datos", required=True)
    ap.add_argument("--salida", required=True)
    ap.add_argument("--por-conjunto", default="acs=0,CLEF=200,USPTO=200", help="0 = todas las imágenes")
    ap.add_argument("--semilla", type=int, default=42)
    a = ap.parse_args()

    sys.path.insert(0, a.codigo)
    import torch  # noqa: E402

    torch.serialization.add_safe_globals([argparse.Namespace])
    torch.set_num_threads(8)
    from molscribe import MolScribe  # noqa: E402
    from molscribe.evaluate import convert_smiles_to_canonsmiles  # noqa: E402

    t0 = time.perf_counter()
    modelo = MolScribe(a.ckpt, device=torch.device("cpu"))
    carga_s = time.perf_counter() - t0

    datos = Path(a.datos)
    rng = random.Random(a.semilla)
    filas = []
    for spec in a.por_conjunto.split(","):
        nombre, n = spec.split("=")
        with open(datos / "real" / f"{nombre}.csv", encoding="utf-8") as f:
            casos = list(csv.DictReader(f))
        if int(n) and int(n) < len(casos):
            casos = rng.sample(casos, int(n))
        rutas = [str(datos / c["file_path"]) for c in casos]
        t1 = time.perf_counter()
        preds = modelo.predict_image_files(rutas, return_confidence=True)
        s_por_imagen = (time.perf_counter() - t1) / len(rutas)
        oro, _ = convert_smiles_to_canonsmiles([c["SMILES"] for c in casos], ignore_cistrans=True, num_workers=1)
        hip, _ = convert_smiles_to_canonsmiles([p.get("smiles") or "" for p in preds], ignore_cistrans=True,
                                               num_workers=1)
        for c, p, g, h in zip(casos, preds, oro, hip):
            filas.append({"conjunto": nombre, "imagen": c["file_path"], "oro": c["SMILES"], "pred": p.get("smiles"),
                          "confianza": p.get("confidence"), "exacta": bool(g) and g == h})
        ok = sum(f["exacta"] for f in filas if f["conjunto"] == nombre)
        print(f"{nombre}: {ok}/{len(casos)} exactas ({100 * ok / len(casos):.1f}%), {s_por_imagen:.2f} s/imagen", flush=True)

    # Calibración: acierto por cuartil de confianza.
    con = sorted((f for f in filas if f["confianza"] is not None), key=lambda f: f["confianza"])
    cuartiles = []
    for i in range(4):
        trozo = con[i * len(con) // 4:(i + 1) * len(con) // 4]
        if trozo:
            cuartiles.append({"cuartil": i + 1, "n": len(trozo), "conf_min": round(trozo[0]["confianza"], 3),
                              "acierto": round(sum(f["exacta"] for f in trozo) / len(trozo), 3)})
    print("acierto por cuartil de confianza (1 = la más baja):",
          ", ".join(f"Q{c['cuartil']} {100 * c['acierto']:.0f}% (conf>={c['conf_min']})" for c in cuartiles))
    json.dump({"carga_s": round(carga_s, 1), "cuartiles": cuartiles, "filas": filas},
              open(a.salida, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
