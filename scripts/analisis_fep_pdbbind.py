#!/usr/bin/env python3
r"""FEP-01/02/03 sobre PDBBind completo, sin tocar los scripts sellados.

**Tipo: medición.** Auditoría del material en disco. Sin docking.

# Por qué un envoltorio y no una bandera

FEP-01, FEP-02 y FEP-03 se sellaron el 2026-08-19 con el SHA-256 de su script
en el manifiesto: cambiarles un byte invalida el sello. Sus universos estaban
fijados a los 203 complejos de `molflex_*_v2`, un conjunto armado para
maximizar la diversidad de dianas, que es lo contrario de lo que necesita
FEP+. El propio FEP-03 lo dejó escrito: «PDBBind las tiene».

Este archivo importa esos módulos, sustituye su universo (`MATS`) y su
directorio de salida (`OUT_DIR`), y llama a su `main()` sin modificarlo. Los
trabajos se reparten con `fork` (Linux), así que los procesos hijos heredan las
constantes sustituidas. **En Windows (`spawn`) no funcionaría**: por eso el
script se niega a correr allí, ni siquiera con `--workers 1`.

# Réplica antes que extensión

`--universo molflex` corre lo mismo que se selló, en el entorno nuevo y hacia
un directorio aparte. Con `--comparar-con` se contrasta el `resumen` contra las
métricas selladas. Si no coincide, la extensión no vale: diferiría por el
entorno (otra versión de RDKit, otro sistema), no por los datos.

# FEP-03 sobre PDBBind: el MCS se reparte y se reanuda

El script sellado calcula el MCS de cada pareja en serie y sólo escribe al
final. Antes de medir se temió que sobre PDBBind fueran días (peor caso: cada
pareja agotando su timeout de 10 s). Medido el 2026-09-22 en el servidor: 30 100
MCS en 24,7 minutos con 3 procesos, 163 cancelados por timeout. Se conserva el
reparto porque un único shard (el de los grupos de 66 y 64) tardó 20 minutos él
solo, y sin shards un corte ahí lo perdía todo. Aquí:

- fase 1 (agrupación por secuencia) usa las funciones y umbrales originales;
- fase 2 enumera las parejas en orden determinista y las reparte en shards;
  cada shard se escribe entero, con nombre propio, y **nunca se reescribe**:
  reanudar es saltar los que ya están (ver la regla de artefactos por shard);
- fase 3 agrega con los mismos campos que FEP-03 y alguno más.

**Prefiltro exacto, declarado antes de mirar.** Si |n_a − n_b| > 10, la
perturbación n_a + n_b − 2·mcs es ≥ |n_a − n_b| > 10 y la pareja no puede ser
apta. Esas parejas se cuentan, pero su MCS no se calcula. El número de parejas
aptas no cambia; las medianas de cobertura y perturbación se calculan sobre las
parejas evaluadas y se declaran así.

# Uso

    python scripts/analisis_fep_pdbbind.py 01 --universo molflex --salida R/FEP-01 \
        --comparar-con scripts/artifacts_science/FEP-01/metrics.json
    python scripts/analisis_fep_pdbbind.py 02 --universo pdbbind --salida R/FEP-02-PDBBIND
    python scripts/analisis_fep_pdbbind.py 03 --universo pdbbind --salida R/FEP-03-PDBBIND \
        --solo-grupos          # cuántas parejas hay, antes de gastar días
    python scripts/analisis_fep_pdbbind.py 03 --universo pdbbind --salida R/FEP-03-PDBBIND \
        --reanudar             # fase 2 y 3; se puede cortar y volver a lanzar

Exit code: 0 = terminado (y réplica coincidente si se pidió), 1 = no.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
import sys
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))

# La consola de Windows usa cp1252: un carácter fuera de esa tabla convierte un
# informe en un traceback DESPUÉS de haber hecho el trabajo. Ver salida_consola.
try:
    from salida_consola import consola_utf8
except ImportError:  # pragma: no cover - en el servidor puede no viajar el ayudante
    def consola_utf8() -> None:
        for _flujo in (sys.stdout, sys.stderr):
            _reconfigurar = getattr(_flujo, "reconfigure", None)
            if _reconfigurar is not None:
                try:
                    _reconfigurar(encoding="utf-8", errors="replace")
                except (ValueError, OSError):
                    pass

consola_utf8()

MODULOS = {
    "01": "analisis_fep01_integridad",
    "02": "analisis_fep02_receptor",
    "03": "analisis_fep03_congenericas",
}
IDS = {"molflex": "FEP-0{}-REPLICA", "pdbbind": "FEP-0{}-PDBBIND"}


def _sha256(ruta: Path) -> str:
    return hashlib.sha256(ruta.read_bytes()).hexdigest()


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat()


def _cargar(auditoria: str, universo: str, salida: Path, limite: int | None):
    modulo = importlib.import_module(MODULOS[auditoria])
    if universo == "pdbbind":
        modulo.MATS = {"pdbbind": modulo.PDBBIND}
    if limite:
        # Sólo para pruebas de humo: un universo recortado a los primeros N.
        recortado = salida / "_universo_recortado"
        for split, origen in modulo.MATS.items():
            destino = recortado / split
            destino.mkdir(parents=True, exist_ok=True)
            for pid in sorted(p.name for p in origen.iterdir() if p.is_dir())[:limite]:
                (destino / pid).mkdir(exist_ok=True)
                mapa = origen / pid / pid / "index_map.json"
                if mapa.is_file():
                    (destino / pid / pid).mkdir(exist_ok=True)
                    (destino / pid / pid / "index_map.json").write_bytes(mapa.read_bytes())
        modulo.MATS = {split: recortado / split for split in modulo.MATS}
    modulo.OUT_DIR = salida
    return modulo


def _salida_nueva(salida: Path, reanudar: bool) -> None:
    """Nunca se reusa un directorio de salida: ya destruyó 102 resultados de RS-03-PARAM-B."""
    if salida.exists() and any(salida.iterdir()) and not reanudar:
        raise SystemExit(f"✗ {salida} ya tiene contenido; elige otra salida (o --reanudar en 03)")
    salida.mkdir(parents=True, exist_ok=True)


def _anotar_metricas(salida: Path, auditoria: str, universo: str, limite: int | None) -> dict[str, Any]:
    ruta = salida / "metrics.json"
    metricas = json.loads(ruta.read_text(encoding="utf-8"))
    sellado = RAIZ / "scripts" / f"{MODULOS[auditoria]}.py"
    metricas["experiment_id_original"] = metricas.get("experiment_id")
    metricas["experiment_id"] = IDS[universo].format(auditoria[-1])
    metricas["universo"] = universo if not limite else f"{universo} (recortado a {limite})"
    metricas["envoltorio"] = {
        "script": "scripts/analisis_fep_pdbbind.py",
        "sha256": _sha256(Path(__file__)),
        "script_sellado": f"scripts/{MODULOS[auditoria]}.py",
        "sha256_sellado": _sha256(sellado),
    }
    if auditoria == "01" and universo == "pdbbind":
        # `listo_para_fep` exige el mapping biyectivo de index_map.json, que es un
        # artefacto de NUESTRA preparación de docking y no existe en PDBBind: el
        # sellado daría 0 listos por construcción. Se añade aparte la cifra con
        # los dos criterios que sí aplican, y la original se deja como está.
        with open(salida / "per_complex.jsonl", encoding="utf-8") as fh:
            filas = [json.loads(linea) for linea in fh if linea.strip()]
        ok = [f for f in filas if "tautomero_ambiguo" in f]
        metricas["resumen_sin_mapping"] = {
            "criterio": "no estereo_indefinido y no tautomero_ambiguo (el mapping no aplica a PDBBind)",
            "n_evaluados": len(ok),
            "listos_sin_criterio_de_mapping": sum(
                1 for f in ok if not f.get("estereo_indefinido") and not f.get("tautomero_ambiguo")),
            "tautomero_ambiguo": sum(1 for f in ok if f.get("tautomero_ambiguo")),
            "estereo_indefinido": sum(1 for f in ok if f.get("estereo_indefinido")),
        }
    ruta.write_text(json.dumps(metricas, ensure_ascii=False, indent=1) + "\n",
                    encoding="utf-8", newline="\n")
    return metricas


def comparar(metricas: dict[str, Any], referencia: Path) -> list[str]:
    sellado = json.loads(referencia.read_text(encoding="utf-8"))
    ref, obt = sellado.get("resumen", {}), metricas.get("resumen", {})
    if not ref or not obt:
        return [f"sin bloque «resumen» que comparar (sellado: {bool(ref)}, obtenido: {bool(obt)})"]
    return [f"{clave}: sellado={ref.get(clave)!r} obtenido={obt.get(clave)!r}"
            for clave in sorted(set(ref) | set(obt)) if ref.get(clave) != obt.get(clave)]


# ── FEP-03 sobre PDBBind ─────────────────────────────────────────────────

_MOLS: dict[str, Any] = {}


def _mol(pid: str, pdbbind: Path):
    if pid not in _MOLS:
        from rdkit import Chem
        m = Chem.MolFromMolFile(str(pdbbind / pid / f"{pid}_ligand.sdf"))
        _MOLS[pid] = Chem.RemoveAllHs(m) if m is not None else None
    return _MOLS[pid]


def _shard(args: tuple[int, list[tuple[str, str]], str, float, int, float]) -> tuple[int, list[dict[str, Any]]]:
    indice, parejas, pdbbind, timeout, pert_max, cob_min = args
    from rdkit import RDLogger
    from rdkit.Chem import rdFMCS
    RDLogger.DisableLog("rdApp.*")
    base = Path(pdbbind)
    salida = []
    for pid_a, pid_b in parejas:
        a, b = _mol(pid_a, base), _mol(pid_b, base)
        na, nb = a.GetNumAtoms(), b.GetNumAtoms()
        registro: dict[str, Any] = {"pid_a": pid_a, "pid_b": pid_b, "n_a": na, "n_b": nb}
        if abs(na - nb) > pert_max:
            registro.update({"prefiltrada": True, "apta_fep": False})
            salida.append(registro)
            continue
        t0 = time.time()
        cancelado = False
        try:
            r = rdFMCS.FindMCS([a, b], timeout=timeout,
                               ringMatchesRingOnly=True, completeRingsOnly=True)
            ncomun, cancelado = r.numAtoms, bool(r.canceled)
        except Exception as exc:  # noqa: BLE001 - paridad con el sellado, pero sin silencio
            # El sellado hace ncomun = 0 y sigue. Se conserva por paridad, y se
            # deja escrito: un except amplio ya convirtió fallos reales en
            # «no disponible» en este proyecto.
            ncomun = 0
            registro["error_mcs"] = type(exc).__name__
        menor = min(na, nb)
        cob = ncomun / menor if menor else 0.0
        pert = (na - ncomun) + (nb - ncomun)
        registro.update({
            "prefiltrada": False, "mcs": ncomun, "cobertura_mcs": round(cob, 3),
            "perturbacion": pert, "apta_fep": bool(cob >= cob_min and pert <= pert_max),
            "mcs_cancelado": cancelado, "t_mcs_s": round(time.time() - t0, 3),
        })
        salida.append(registro)
    return indice, salida


def _grupos(modulo, salida: Path, workers: int) -> dict[str, Any]:
    ruta = salida / "grupos.json"
    if ruta.is_file():
        return json.loads(ruta.read_text(encoding="utf-8"))
    pids = sorted(p.name for s, m in modulo.MATS.items() for p in m.iterdir() if p.is_dir())
    t0 = time.time()
    jobs = [{"pid": p, "split": "pdbbind"} for p in pids]
    with ProcessPoolExecutor(max_workers=workers) as ex:
        secs = list(ex.map(modulo._sec_job, jobs, chunksize=32))
    secs = [s for s in secs if s["len_sec"] >= 30]
    print(f"  {len(secs)} de {len(pids)} con secuencia utilizable ({round(time.time() - t0)} s)", flush=True)

    # Agrupación idéntica a la sellada: Jaccard de k-meros sobre el menor, union-find.
    km = {s["pid"]: modulo._kmers(s["sec"]) for s in secs}
    padre = {s["pid"]: s["pid"] for s in secs}

    def find(x):
        while padre[x] != x:
            padre[x] = padre[padre[x]]
            x = padre[x]
        return x

    orden = [s["pid"] for s in secs]
    for i in range(len(orden)):
        a = km[orden[i]]
        if not a:
            continue
        for j in range(i + 1, len(orden)):
            b = km[orden[j]]
            if not b:
                continue
            if len(a & b) / min(len(a), len(b)) >= modulo.UMBRAL_SEC:
                ra, rb = find(orden[i]), find(orden[j])
                if ra != rb:
                    padre[ra] = rb
    grupos: dict[str, list[str]] = defaultdict(list)
    for p in orden:
        grupos[find(p)].append(p)
    resultado = {
        "n_pdbbind": len(pids),
        "n_complejos": len(secs),
        "grupos": sorted((sorted(v) for v in grupos.values()), key=lambda g: (-len(g), g[0])),
        "duracion_s": round(time.time() - t0, 1),
    }
    ruta.write_text(json.dumps(resultado, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    return resultado


def fep03_pdbbind(salida: Path, workers: int, tam_shard: int, solo_grupos: bool, limite: int | None) -> int:
    modulo = _cargar("03", "pdbbind", salida, limite)
    from rdkit import RDLogger
    RDLogger.DisableLog("rdApp.*")
    t0 = time.time()
    print(f"[FEP-03-PDBBIND] fase 1: agrupación por secuencia ({workers} procesos)", flush=True)
    info = _grupos(modulo, salida, workers)
    multi = [g for g in info["grupos"] if len(g) >= 2]

    validos = [p for g in multi for p in g if _mol(p, modulo.PDBBIND) is not None]
    validos_set = set(validos)
    parejas: list[tuple[str, str]] = []
    prefiltrables = 0
    for g in multi:
        ms = [p for p in g if p in validos_set]
        for i in range(len(ms)):
            for j in range(i + 1, len(ms)):
                parejas.append((ms[i], ms[j]))
                if abs(_mol(ms[i], modulo.PDBBIND).GetNumAtoms()
                       - _mol(ms[j], modulo.PDBBIND).GetNumAtoms()) > modulo.PERTURBACION_MAX:
                    prefiltrables += 1
    shards = [parejas[k:k + tam_shard] for k in range(0, len(parejas), tam_shard)]
    resumen_fase1 = {
        "n_pdbbind": info["n_pdbbind"], "n_complejos": info["n_complejos"],
        "n_dianas_distintas": len(info["grupos"]), "dianas_con_2_o_mas": len(multi),
        "tamano_grupo_max": max((len(g) for g in info["grupos"]), default=0),
        "n_parejas": len(parejas), "n_parejas_prefiltradas": prefiltrables,
        "n_parejas_con_mcs": len(parejas) - prefiltrables, "n_shards": len(shards),
        "grupos_mayores": [len(g) for g in multi[:15]],
    }
    (salida / "fase1.json").write_text(json.dumps(resumen_fase1, ensure_ascii=False, indent=1) + "\n",
                                       encoding="utf-8", newline="\n")
    print(json.dumps(resumen_fase1, ensure_ascii=False, indent=1), flush=True)
    if solo_grupos:
        return 0

    carpeta = salida / "pares"
    carpeta.mkdir(exist_ok=True)
    pendientes = [i for i in range(len(shards)) if not (carpeta / f"shard_{i:05d}.jsonl").is_file()]
    print(f"[FEP-03-PDBBIND] fase 2: {len(pendientes)} de {len(shards)} shards pendientes", flush=True)
    t2 = time.time()
    hechos = 0
    with ProcessPoolExecutor(max_workers=workers) as ex:
        futuros = [ex.submit(_shard, (i, shards[i], str(modulo.PDBBIND), modulo.MCS_TIMEOUT,
                                      modulo.PERTURBACION_MAX, modulo.COBERTURA_MCS))
                   for i in pendientes]
        for futuro in as_completed(futuros):
            indice, registros = futuro.result()
            final = carpeta / f"shard_{indice:05d}.jsonl"
            temporal = final.with_suffix(".tmp")
            with open(temporal, "w", encoding="utf-8", newline="\n") as fh:
                fh.writelines(json.dumps(r, ensure_ascii=False) + "\n" for r in registros)
            os.replace(temporal, final)
            hechos += 1
            transcurrido = time.time() - t2
            eta = transcurrido / hechos * (len(pendientes) - hechos)
            print(f"  shard {indice:05d} listo | {hechos}/{len(pendientes)} | "
                  f"{round(transcurrido / 60, 1)} min | ETA {round(eta / 3600, 2)} h", flush=True)

    print("[FEP-03-PDBBIND] fase 3: agregado", flush=True)
    registros: list[dict[str, Any]] = []
    for i in range(len(shards)):
        with open(carpeta / f"shard_{i:05d}.jsonl", encoding="utf-8") as fh:
            registros.extend(json.loads(linea) for linea in fh if linea.strip())
    if len(registros) != len(parejas):
        raise SystemExit(f"✗ {len(registros)} registros para {len(parejas)} parejas: faltan shards")
    grupo_de = {p: k for k, g in enumerate(multi) for p in g}
    evaluadas = [r for r in registros if not r["prefiltrada"]]
    aptas = [r for r in registros if r["apta_fep"]]
    por_diana: dict[int, dict[str, Any]] = {}
    for r in aptas:
        k = grupo_de[r["pid_a"]]
        d = por_diana.setdefault(k, {"grupo": k, "n_miembros": len(multi[k]), "n_parejas_aptas": 0,
                                     "ligandos_en_parejas_aptas": set()})
        d["n_parejas_aptas"] += 1
        d["ligandos_en_parejas_aptas"].update((r["pid_a"], r["pid_b"]))
    series = sorted(
        ({**d, "ligandos_en_parejas_aptas": sorted(d["ligandos_en_parejas_aptas"]),
          "n_ligandos_conectados": len(d["ligandos_en_parejas_aptas"]),
          "ejemplo": multi[d["grupo"]][0]} for d in por_diana.values()),
        key=lambda d: (-d["n_ligandos_conectados"], -d["n_parejas_aptas"]))
    resumen = {
        **{k: resumen_fase1[k] for k in ("n_complejos", "n_dianas_distintas", "dianas_con_2_o_mas",
                                         "tamano_grupo_max")},
        "complejos_en_dianas_multiples": sum(len(g) for g in multi),
        "n_parejas_evaluadas": len(evaluadas),
        "n_parejas_prefiltradas": len(registros) - len(evaluadas),
        "n_parejas_aptas_fep": len(aptas),
        "dianas_con_serie_congenerica": len(por_diana),
        "cobertura_mcs_mediana_evaluadas": round(median(r["cobertura_mcs"] for r in evaluadas), 3)
        if evaluadas else None,
        "perturbacion_mediana_evaluadas": int(median(r["perturbacion"] for r in evaluadas))
        if evaluadas else None,
        "n_mcs_cancelados_por_timeout": sum(1 for r in evaluadas if r.get("mcs_cancelado")),
    }
    metricas = {
        "experiment_id": "FEP-03-PDBBIND",
        "tipo": "auditoria (sin docking)",
        "timestamp": _ahora(),
        "duration_seconds": round(time.time() - t0, 2),
        "universo": "pdbbind" if not limite else f"pdbbind (recortado a {limite})",
        "umbrales_declarados": {"identidad_secuencia_kmer": modulo.UMBRAL_SEC,
                                "cobertura_mcs": modulo.COBERTURA_MCS,
                                "perturbacion_max_atomos": modulo.PERTURBACION_MAX,
                                "mcs_timeout_s": modulo.MCS_TIMEOUT},
        "prefiltro": ("exacto: |n_a - n_b| > perturbacion_max implica perturbacion > max; no cambia "
                      "las aptas. Las medianas son sobre las parejas evaluadas, no sobre todas."),
        "resumen": resumen,
        "envoltorio": {"script": "scripts/analisis_fep_pdbbind.py", "sha256": _sha256(Path(__file__)),
                       "script_sellado": "scripts/analisis_fep03_congenericas.py",
                       "sha256_sellado": _sha256(RAIZ / "scripts" / "analisis_fep03_congenericas.py")},
        "limitacion": ("la agrupacion por k-meros no distingue mutantes puntuales (que para FEP+ SI "
                       "serian dianas distintas) y puede unir isoformas; el MCS con timeout puede ser "
                       "suboptimo. Ambos sesgos SOBREESTIMAN las parejas: la cifra es una COTA SUPERIOR"),
    }
    (salida / "metrics.json").write_text(json.dumps(metricas, ensure_ascii=False, indent=1) + "\n",
                                         encoding="utf-8", newline="\n")
    (salida / "series.json").write_text(json.dumps(series, ensure_ascii=False, indent=1) + "\n",
                                        encoding="utf-8", newline="\n")
    print(json.dumps(resumen, ensure_ascii=False, indent=1), flush=True)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("auditoria", choices=sorted(MODULOS))
    ap.add_argument("--universo", choices=("molflex", "pdbbind"), required=True)
    ap.add_argument("--salida", type=Path, required=True)
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 4) - 1))
    ap.add_argument("--comparar-con", type=Path, help="metrics.json sellado para la réplica")
    ap.add_argument("--limite", type=int, help="prueba de humo: sólo los primeros N complejos")
    ap.add_argument("--tam-shard", type=int, default=2000, help="parejas por shard (sólo 03 pdbbind)")
    ap.add_argument("--solo-grupos", action="store_true", help="03 pdbbind: para tras la fase 1")
    ap.add_argument("--reanudar", action="store_true", help="03 pdbbind: salta los shards escritos")
    args = ap.parse_args()

    if os.name == "nt":
        # Ni siquiera con --workers 1: el script sellado usa ProcessPoolExecutor
        # igualmente, y en Windows el hijo arranca con spawn y relee su universo
        # original. Mediría los 203 creyendo medir PDBBind.
        raise SystemExit("✗ en Windows los procesos hijos no heredan el universo sustituido; "
                         "corre en Linux (el contenedor moldesign-science del servidor)")
    # Explícito: con forkserver o spawn (el defecto de Python 3.14 en Linux) los
    # hijos reimportarían el módulo sellado y medirían su universo original.
    import multiprocessing
    multiprocessing.set_start_method("fork", force=True)

    _salida_nueva(args.salida, args.reanudar and args.auditoria == "03")
    if args.auditoria == "03" and args.universo == "pdbbind":
        return fep03_pdbbind(args.salida, args.workers, args.tam_shard, args.solo_grupos, args.limite)

    modulo = _cargar(args.auditoria, args.universo, args.salida, args.limite)
    sys.argv = [modulo.__file__, "--workers", str(args.workers)]
    codigo = modulo.main()
    metricas = _anotar_metricas(args.salida, args.auditoria, args.universo, args.limite)
    if args.comparar_con:
        diferencias = comparar(metricas, args.comparar_con)
        if diferencias:
            print("\n✗ LA RÉPLICA NO REPRODUCE EL SELLO:")
            for d in diferencias:
                print(f"  - {d}")
            return 1
        print(f"\n✓ réplica idéntica al resumen sellado de {args.comparar_con}")
    return codigo or 0


if __name__ == "__main__":
    sys.exit(main())
