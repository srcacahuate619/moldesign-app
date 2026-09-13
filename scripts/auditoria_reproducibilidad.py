#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""auditoria_reproducibilidad.py — FND-08: ¿puede un tercero reconstruir el registro?

`FEP-06` pide que un tercero reconstruya el paquete de transferencia sin conocer la
sesión. Ese experimento depende de `FEP-05`, que todavía no existe. Pero hay una pregunta
anterior, que **no** depende de nada y que tiene que responderse antes de que ningún
tercero mire nada:

> ¿El registro experimental se sostiene por sí solo?

Esta auditoría lo comprueba mecánicamente sobre los artefactos sellados. Cuesta segundos y
no toca ningún dato: sólo lee.

Los cuatro criterios
--------------------
  G1  **Integridad del sello.** Todo artefacto sellado valida: los hashes de lo que sello
      siguen coincidiendo con lo que hay en disco.
  G2  **Consistencia del recuento.** Si el artefacto declara un `n_complejos`, ese numero
      coincide con las filas de su registro por complejo.
  G3  **Existencia del dato crudo.** Todo artefacto con resultados tiene al menos un
      archivo de datos no vacio, de modo que sus cifras sean verificables sin re-ejecutar.
  G4  **Trazabilidad del codigo.** El script que produjo el resultado esta hasheado en el
      sello, no solo mencionado en prosa.

Por que un fallo aqui es el resultado util
------------------------------------------
Una auditoria que pasa al primer intento normalmente significa que no miro lo suficiente.
Los defectos que encuentre son baratos de arreglar ahora y caros de descubrir cuando los
encuentre otro.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ART = PROJECT_ROOT / "scripts" / "artifacts_science"

# El contrato de la seccion 17 declara `per_complex.jsonl`, pero el programa ha usado al
# menos ocho nombres distintos para lo mismo -corridas, cohort, parejas, brazo_a/b,
# union_candidates...-. Un tercero al que se le dice que busque `per_complex.jsonl` no
# encuentra esos datos. Se audita por tanto CUALQUIER .jsonl con contenido, y aparte se
# registra si el nombre canonico esta o no, que es la no conformidad real.
CANONICO = "per_complex.jsonl"
EXCLUIDOS = {"failures.jsonl"}


def _filas(p: Path) -> int:
    if not p.exists():
        return 0
    return sum(1 for l in p.read_text(encoding="utf-8", errors="replace").splitlines()
               if l.strip())


def _n_declarado(met: Any) -> Optional[int]:
    if not isinstance(met, dict):
        return None
    for k in ("n_complejos", "n_complexes", "n_targets", "n"):
        if isinstance(met.get(k), int):
            return met[k]
    return None


def auditar(d: Path) -> Dict[str, Any]:
    man = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
    r: Dict[str, Any] = {"id": man["experiment_id"], "decision": man.get("decision")}

    # G1 — integridad del sello
    p = subprocess.run([sys.executable, str(PROJECT_ROOT / "scripts" / "experiment_manifest.py"),
                        "validate", man["experiment_id"]],
                       capture_output=True, text=True, cwd=str(PROJECT_ROOT))
    r["G1_valida"] = p.returncode == 0
    if not r["G1_valida"]:
        r["G1_detalle"] = " ".join(p.stdout.split())[:300]

    # G2 — consistencia del recuento
    mj = d / "metrics.json"
    met = None
    if mj.exists() and mj.stat().st_size > 20:
        try:
            met = json.loads(mj.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            r["metrics_ilegible"] = True
    n_dec = _n_declarado(met)
    crudos = {p.name: _filas(p) for p in sorted(d.glob("*.jsonl"))
              if p.name not in EXCLUIDOS}
    r["crudos"] = {k: v for k, v in crudos.items() if v > 0}
    n_crudo = max(crudos.values()) if crudos else 0
    r["n_declarado"] = n_dec
    r["n_crudo_max"] = n_crudo
    # no conformidad de nombre: hay dato, pero no bajo el nombre que el contrato declara
    r["nombre_canonico_vacio"] = bool(r["crudos"] and _filas(d / CANONICO) == 0)
    # G2 se evalua contra el fichero CANONICO. Comparar contra el mayor .jsonl seria
    # incorrecto: varios artefactos llevan ficheros auxiliares (cohortes, parejas, brazos)
    # con mas filas que complejos. Si el canonico esta vacio, G2 no aplica y el problema
    # queda registrado como no conformidad de nombre.
    n_canon = _filas(d / CANONICO)
    if n_dec is None or n_canon == 0:
        r["G2_consistente"] = None
    else:
        r["G2_consistente"] = (n_canon == n_dec)
    r["n_canonico"] = n_canon

    # G3 — existencia del dato crudo (solo exigible si hay resultados)
    tiene_resultados = met is not None
    r["G3_dato_crudo"] = (n_crudo > 0) if tiene_resultados else None

    # G4 — trazabilidad del codigo
    hashes: Dict[str, str] = {}
    for k in ("dataset_hashes", "model_hashes", "binary_hashes", "assets_hashes"):
        v = man.get(k)
        if isinstance(v, dict):
            hashes.update(v)
    scripts = [k for k in hashes if k.endswith(".py")]
    r["scripts_hasheados"] = scripts
    r["G4_codigo_trazable"] = (len(scripts) > 0) if tiene_resultados else None
    # y ademas: los ficheros hasheados que ya no existen
    r["hashes_a_ficheros_ausentes"] = [k for k in hashes
                                       if not (PROJECT_ROOT / k).exists()]
    return r


def main() -> int:
    ap = argparse.ArgumentParser(description="FND-08: auditoria de reproducibilidad del registro")
    ap.add_argument("--salida", default=str(ART / "FND-08"))
    args = ap.parse_args()
    out = Path(args.salida)
    out.mkdir(parents=True, exist_ok=True)

    filas: List[Dict[str, Any]] = []
    for d in sorted(ART.iterdir()):
        if not d.is_dir() or not (d / "manifest.json").exists():
            continue
        man = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
        if not man.get("sealed"):
            continue
        filas.append(auditar(d))
        print(f"  {filas[-1]['id']:20s} G1={filas[-1]['G1_valida']} "
              f"G2={filas[-1]['G2_consistente']} G3={filas[-1]['G3_dato_crudo']} "
              f"G4={filas[-1]['G4_codigo_trazable']}", flush=True)

    with open(out / "per_complex.jsonl", "w", encoding="utf-8", newline="\n") as fh:
        for r in filas:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    def cuenta(clave):
        aplica = [r for r in filas if r.get(clave) is not None]
        pasan = [r for r in aplica if r[clave]]
        return {"aplica_a": len(aplica), "pasan": len(pasan),
                "fallan": [r["id"] for r in aplica if not r[clave]]}

    g1, g2, g3, g4 = (cuenta("G1_valida"), cuenta("G2_consistente"),
                      cuenta("G3_dato_crudo"), cuenta("G4_codigo_trazable"))
    huerfanos = {r["id"]: r["hashes_a_ficheros_ausentes"]
                 for r in filas if r["hashes_a_ficheros_ausentes"]}
    no_canonico = [r["id"] for r in filas if r.get("nombre_canonico_vacio")]

    metrics = {
        "experiment_id": "FND-08",
        "tipo": "auditoria de reproducibilidad, solo lectura",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "n_artefactos_sellados": len(filas),
        "G1_integridad_del_sello": g1,
        "G2_consistencia_del_recuento": g2,
        "G3_existencia_de_dato_crudo": g3,
        "G4_trazabilidad_del_codigo": g4,
        "hashes_a_ficheros_ausentes": huerfanos,
        "dato_crudo_fuera_del_nombre_canonico": {
            "criterio": f"tiene .jsonl con contenido pero {CANONICO} vacio o ausente",
            "n": len(no_canonico), "ids": no_canonico},
        "nota": ("G2 y G3 solo aplican a artefactos con metrics.json; los prerregistros y "
                 "los documentales no declaran resultados y quedan fuera del denominador."),
    }
    (out / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=1),
                                      encoding="utf-8", newline="\n")
    print()
    for nom, g in (("G1 integridad del sello", g1), ("G2 consistencia del recuento", g2),
                   ("G3 existencia de dato crudo", g3), ("G4 trazabilidad del codigo", g4)):
        print(f"{nom:32s} {g['pasan']}/{g['aplica_a']}"
              + (f"   FALLAN: {', '.join(g['fallan'])}" if g["fallan"] else ""))
    if huerfanos:
        print(f"\nhashes que apuntan a ficheros ausentes: {huerfanos}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
