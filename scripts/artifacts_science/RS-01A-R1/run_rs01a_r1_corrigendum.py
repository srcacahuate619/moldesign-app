# -*- coding: utf-8 -*-
"""run_rs01a_r1_corrigendum.py — RS-01A-R1: corrigendum estadistico del p de
McNemar de RS-01A.

Bug formal confirmado por el maintainer: la version ejecutada de RS-01A
multiplico por 2 el pvalue de scipy.stats.binomtest(...), que YA es
bilateral. Consecuencia sobre el artefacto sellado de RS-01A
(scripts/artifacts_science/RS-01A/metrics.json, sha
c6f4a2ef98d9646ba2850efb52f101b16ea6cc7be32fe3010ee61513edbaeb46):

    a1.pareado.mcnemar: b=4, c=0 -> p_antiguo 0.25  -> p_corregido 0.125
    a2.pareado.mcnemar: b=3, c=1 -> p_antiguo 1.0   -> p_corregido 0.625

Este script SOLO LEE el metrics.json sellado del padre (verificado por
sha256), reproduce el calculo corregido y escribe los artefactos de
RS-01A-R1. El sello historico de RS-01A NO se modifica (ningun archivo del
padre se toca). Ningun gate ni decision de RS-01A cambia.

Determinismo: salidas sin timestamps; dos corridas producen bytes identicos.

Uso:
    python scripts/artifacts_science/RS-01A-R1/run_rs01a_r1_corrigendum.py
"""
from __future__ import annotations

import builtins
import hashlib
import json
import sys
from pathlib import Path

# ───────────────────────── auditoria de archivos abiertos ──────────────────
_ORIGINAL_OPEN = builtins.open
_ABIERTOS_REPO: set[str] = set()


def _open_auditado(archivo, *args, **kwargs):
    try:
        p = Path(str(archivo)).resolve()
        try:
            rel = p.relative_to(PROJECT_ROOT.resolve())
            _ABIERTOS_REPO.add(str(rel).replace("\\", "/"))
        except ValueError:
            pass
    except Exception:
        pass
    return _ORIGINAL_OPEN(archivo, *args, **kwargs)


builtins.open = _open_auditado

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent

R_PARENT_METRICS = (PROJECT_ROOT / "scripts" / "artifacts_science" / "RS-01A"
                    / "metrics.json")
OUT_DIR = Path(__file__).resolve().parent

SHA_PARENT_SELLADO = "c6f4a2ef98d9646ba2850efb52f101b16ea6cc7be32fe3010ee61513edbaeb46"

COMMIT_SELLO_RS01A = "2943a38"

CORREGIR = [
    # (ruta en el metrics del padre, p_antiguo esperado)
    (("a1", "pareado", "mcnemar"), 0.25),
    (("a2", "pareado", "mcnemar"), 1.0),
]


def configurar_salida() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def sha256_archivo(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for bloque in iter(lambda: fh.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def p_mcnemar_corregido(b: int, c: int) -> float:
    """Formula CORREGIDA: binomtest(...).pvalue ya es bilateral."""
    from scipy.stats import binomtest
    n_discordantes = b + c
    if n_discordantes == 0:
        return 1.0
    return float(binomtest(min(b, c), n_discordantes, 0.5).pvalue)


def extraer(metrics: dict, ruta: tuple) -> dict:
    nodo = metrics
    for clave in ruta:
        nodo = nodo[clave]
    return nodo


def main() -> int:
    configurar_salida()
    print("== RS-01A-R1: corrigendum estadistico del p de McNemar de RS-01A ==",
          flush=True)

    sha_real = sha256_archivo(R_PARENT_METRICS)
    if sha_real != SHA_PARENT_SELLADO:
        raise SystemExit("ERROR: metrics.json de RS-01A no coincide con su "
                         "sha sellado; sello historico comprometido")
    print(f"  padre verificado (sha256): {sha_real[:16]}... OK", flush=True)

    padre = json.loads(R_PARENT_METRICS.read_text(encoding="utf-8"))

    correcciones = []
    for ruta, p_antiguo_esperado in CORREGIR:
        bloque = extraer(padre, ruta)
        b = int(bloque["b_orig_hit_dedup_miss"])
        c = int(bloque["c_orig_miss_dedup_hit"])
        n = int(bloque["n_discordantes"])
        p_antiguo = float(bloque["p_valor_exacto_bilateral"])
        if b + c != n:
            raise SystemExit(f"ERROR: {'.'.join(ruta)} b+c != n_discordantes")
        if abs(p_antiguo - p_antiguo_esperado) > 1e-9:
            raise SystemExit(f"ERROR: {'.'.join(ruta)} p_antiguo "
                             f"{p_antiguo} != esperado {p_antiguo_esperado}")
        p_corregido = p_mcnemar_corregido(b, c)
        correcciones.append({
            "bloque": ".".join(ruta),
            "b_orig_hit_dedup_miss": b,
            "c_orig_miss_dedup_hit": c,
            "n_discordantes": n,
            "p_antiguo": round(p_antiguo, 6),
            "p_corregido": round(p_corregido, 6),
        })
        print(f"  {'.'.join(ruta)}: b={b} c={c} p {round(p_antiguo, 6)} "
              f"-> {round(p_corregido, 6)}", flush=True)

    esperados = {("a1", "pareado", "mcnemar"): 0.125,
                 ("a2", "pareado", "mcnemar"): 0.625}
    for corr in correcciones:
        esperado = esperados.get(tuple(corr["bloque"].split(".")))
        if esperado is not None and abs(corr["p_corregido"] - esperado) > 5e-7:
            raise SystemExit(f"ERROR: p corregido de {corr['bloque']} "
                             f"no reproduce {esperado}")

    metrics = {
        "experimento": "RS-01A-R1",
        "tipo": "CORRIGENDUM ESTADISTICO",
        "padre": {
            "experimento": "RS-01A",
            "commit_sello": COMMIT_SELLO_RS01A,
            "metrics_sha256": SHA_PARENT_SELLADO,
            "nota": ("el sello historico de RS-01A NO se modifica; este "
                     "corrigendum vive en RS-01A-R1 y solo reexpresa el "
                     "p de McNemar"),
        },
        "bug": ("mcnemar_hits multiplicaba por 2 el pvalue de "
                "scipy.stats.binomtest(...), que YA es bilateral"),
        "fix": ("se elimina el factor 2: p = binomtest(min(b,c), b+c, "
                "0.5).pvalue; 0 pares discordantes -> p = 1.0"),
        "correcciones": correcciones,
        "que_no_cambia": ("ningun gate ni decision de RS-01A cambia: A0 "
                          "sigue reproduciendo el historico; A1 sigue "
                          "observando -4 hits Top-1 con 0 recuperaciones; la "
                          "mediana pareada sigue 0.000 A; el contrafactual "
                          "de los 31 empates sigue siendo sensible al "
                          "desempate de fuente. El GO procedimental del "
                          "sello historico permanece intacto."),
        "verificacion": {
            "p_b4_c0_reproducido": bool(any(
                abs(corr["p_corregido"] - 0.125) < 5e-7
                for corr in correcciones)),
            "padre_sha_ok": True,
        },
        "archivos_abiertos_repo": sorted(_ABIERTOS_REPO),
        "garantia_cuarentena": ("solo se lee el metrics.json sellado del "
                                "padre (verificado por sha) y se escriben "
                                "los artefactos de RS-01A-R1; cero acceso a "
                                "val/test/CONFIRM"),
        "determinismo": ("salidas sin timestamps ni aleatoriedad; dos "
                         "corridas producen bytes identicos"),
    }

    # ── auditoria de cuarentena: whitelist ──
    whitelist = {
        "scripts/artifacts_science/RS-01A/metrics.json",
        "scripts/artifacts_science/RS-01A-R1/run_rs01a_r1_corrigendum.py",
        "scripts/artifacts_science/RS-01A-R1/metrics.json",
        "scripts/artifacts_science/RS-01A-R1/failures.jsonl",
    }
    fuera = sorted(p for p in _ABIERTOS_REPO
                   if p not in whitelist and "__pycache__" not in p
                   and not p.endswith(".pyc")
                   and not p.startswith("python-embed/"))
    if fuera:
        raise SystemExit("ERROR: archivos fuera del whitelist abiertos: "
                         + "; ".join(fuera))

    with open(OUT_DIR / "metrics.json", "w", encoding="utf-8",
              newline="\n") as fh:
        fh.write(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n")
    with open(OUT_DIR / "failures.jsonl", "w", encoding="utf-8",
              newline="\n") as fh:
        fh.write("")
    print("  salidas escritas en", OUT_DIR)
    print(f"  sha metrics={sha256_archivo(OUT_DIR / 'metrics.json')[:16]}...")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
