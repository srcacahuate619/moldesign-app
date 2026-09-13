#!/usr/bin/env python3
"""¿Los activos del benchmark coordinan el zinc, y falta gente en el recuento?

Auditoría barata sobre el checkpoint existente. No ejecuta docking nuevo.

═══════════════════════════════════════════════════════════════════════════
LAS TRES PREGUNTAS
═══════════════════════════════════════════════════════════════════════════

1. **¿Coordinan?** Para CADA activo —no una muestra— la distancia del zinc al
   átomo donante (N/O/S) más cercano de su pose. La coordinación de Zn²⁺ está
   en 1.9–2.4 Å; aquí se cuentan ≤2.8 Å como coordinación y ≤4.0 Å como
   entorno, que son umbrales generosos para geometrías de docking.

2. **¿Falta gente?** Cuántos registros no tienen pose, cuántos tienen pose y no
   features, y cuántos están completos — POR CLASE. Si las pérdidas se
   concentran en una clase, el AUC de casos completos está sesgado.

3. **¿Cuánto pesa la pérdida?** El AUC del perfil se recalcula sobre casos
   completos, y se acompaña de un ANÁLISIS DE SENSIBILIDAD: una lectura ITT que
   imputa a cada registro perdido el peor valor posible para su clase. Ese
   segundo número **no es un AUC corregido** — es un límite inferior bajo la
   imputación más adversa, y sirve para medir fragilidad, no para estimar qué
   habrían puntuado los ausentes.

═══════════════════════════════════════════════════════════════════════════
LO QUE ESTE ARTEFACTO NO PERMITE
═══════════════════════════════════════════════════════════════════════════

**No hay oráculo sobre el ensemble.** Cada registro guarda UN solo `MODEL`: el
checkpoint conservó la pose top-1 y descartó el resto. Así que no se puede
distinguir «el ligando nunca alcanza el zinc» de «lo alcanza en otra pose y el
scoring eligió mal». Esa distinción exige volver a acoplar, y por eso se
declara ausente en vez de simularse.

Uso:

    python scripts/auditar_coordinacion_zinc.py 1o86
    python scripts/auditar_coordinacion_zinc.py 1gkc --json informe.json
"""

from __future__ import annotations

import argparse
import json
import math
import statistics as st
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "backend"))

for _flujo in (sys.stdout, sys.stderr):
    try:
        _flujo.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):  # pragma: no cover
        pass

from services.pipeline.protocols.m5.zinc import (  # noqa: E402
    PERFILES, ums_desde_smiles, vina_normalizada,
)

DIANAS = {
    "1gkc": {"estructura": "data/1gkc.pdb",
             "checkpoint": "data/benchmark_checkpoint_mmp9.json", "perfil": "1GKC"},
    "1o86": {"estructura": "data/1O86_clean.pdb",
             "checkpoint": "data/benchmark_checkpoint_ace.json", "perfil": "1O86"},
}

_DONANTES = {"N", "O", "S"}
_COORDINACION = 2.8
_ENTORNO = 4.0


def zincs_de(ruta: Path) -> list[tuple[float, float, float]]:
    puntos = []
    with ruta.open(encoding="utf-8", errors="replace") as f:
        for linea in f:
            if (linea.startswith("HETATM") and len(linea) >= 78
                    and linea[76:78].strip().upper() == "ZN"):
                puntos.append((float(linea[30:38]), float(linea[38:46]),
                               float(linea[46:54])))
    return puntos


def modelos_de(pose: str) -> list[list[tuple]]:
    """Separa por MODEL. Hoy siempre devuelve 0 o 1: el ensemble no se guardó."""
    modelos, actual = [], []
    for linea in pose.splitlines():
        if linea.startswith("MODEL"):
            actual = []
        elif linea.startswith("ENDMDL"):
            if actual:
                modelos.append(actual)
            actual = []
        elif linea.startswith(("ATOM", "HETATM")):
            try:
                p = (float(linea[30:38]), float(linea[38:46]), float(linea[46:54]))
            except ValueError:
                continue
            tipo = linea[77:79].strip().upper() if len(linea) >= 78 else ""
            actual.append((p, tipo[:1] if tipo else ""))
    if actual:
        modelos.append(actual)
    return modelos


def distancia_donante(modelo, zincs) -> float | None:
    donantes = [p for p, e in modelo if e in _DONANTES]
    if not donantes or not zincs:
        return None
    return min(math.dist(z, p) for z in zincs for p in donantes)


def auc(pares: list[tuple[float, int]]) -> float | None:
    """AUC por el estadístico de Mann-Whitney, con empates a media.

    Se implementa aquí y no se importa para que el número no dependa de la
    misma cadena de código que se está auditando.
    """
    pos = [s for s, y in pares if y == 1]
    neg = [s for s, y in pares if y == 0]
    if not pos or not neg:
        return None
    ordenado = sorted(pares, key=lambda t: t[0])
    rangos, i = {}, 0
    while i < len(ordenado):
        j = i
        while j + 1 < len(ordenado) and ordenado[j + 1][0] == ordenado[i][0]:
            j += 1
        medio = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            rangos[k] = medio
        i = j + 1
    suma_pos = sum(rangos[k] for k, (_, y) in enumerate(ordenado) if y == 1)
    n1, n0 = len(pos), len(neg)
    return (suma_pos - n1 * (n1 + 1) / 2.0) / (n1 * n0)


def auditar(clave: str) -> dict:
    cfg = DIANAS[clave]
    perfil = PERFILES[cfg["perfil"]]
    zincs = zincs_de(RAIZ / cfg["estructura"])
    datos = json.loads((RAIZ / cfg["checkpoint"]).read_text(encoding="utf-8"))
    registros = datos["results"]

    clases = {"activos": [], "decoys": []}
    completitud = {
        c: {"total": 0, "sin_pose": 0, "con_pose_sin_features": 0, "completos": 0}
        for c in clases
    }
    modelos_por_registro: list[int] = []
    puntuables_completos: list[tuple[float, int]] = []
    puntuables_itt: list[tuple[float, int]] = []

    for registro in registros:
        activo = bool(registro.get("is_active"))
        clase = "activos" if activo else "decoys"
        completitud[clase]["total"] += 1

        modelos = modelos_de(registro.get("pose_pdbqt") or "")
        modelos_por_registro.append(len(modelos))

        vina = registro.get("vina_score")
        xgb = registro.get("prob")
        smiles = registro.get("smiles") or ""
        ums = ums_desde_smiles(smiles) if smiles else None

        if not modelos:
            completitud[clase]["sin_pose"] += 1
        elif not registro.get("features"):
            completitud[clase]["con_pose_sin_features"] += 1
        else:
            completitud[clase]["completos"] += 1

        # ── Coordinación, sobre TODOS los activos ────────────────────
        if modelos:
            top1 = distancia_donante(modelos[0], zincs)
            oraculo = min(
                (d for d in (distancia_donante(m, zincs) for m in modelos)
                 if d is not None),
                default=None,
            )
            clases[clase].append({
                "smiles": smiles[:80],
                "top1": round(top1, 2) if top1 is not None else None,
                "oraculo": round(oraculo, 2) if oraculo is not None else None,
                "n_poses": len(modelos),
            })

        # ── Score del perfil, para el AUC ────────────────────────────
        completo = (
            modelos and registro.get("features")
            and vina is not None and xgb is not None and ums is not None
        )
        if completo:
            score = (
                perfil.peso_vina * vina_normalizada(vina, perfil.vina_reference_max)
                + perfil.peso_xgb * float(xgb)
                + perfil.peso_ums * float(ums)
            )
            puntuables_completos.append((score, int(activo)))
            puntuables_itt.append((score, int(activo)))
        else:
            # ITT conservador: al perdido se le da el peor valor para su clase.
            # Un activo perdido se supone el peor de todos; un decoy perdido, el
            # mejor. Es el escenario que más castiga al AUC.
            puntuables_itt.append((0.0 if activo else 1.0, int(activo)))

    def resumen(items: list[dict], campo: str) -> dict | None:
        valores = [i[campo] for i in items if i.get(campo) is not None]
        if not valores:
            return None
        return {
            "n": len(valores),
            "minima": round(min(valores), 2),
            "mediana": round(st.median(valores), 2),
            "maxima": round(max(valores), 2),
            f"coordinando_{_COORDINACION}A": sum(1 for v in valores if v <= _COORDINACION),
            f"en_el_entorno_{_ENTORNO}A": sum(1 for v in valores if v <= _ENTORNO),
        }

    auc_completos = auc(puntuables_completos)
    auc_itt = auc(puntuables_itt)

    informe = {
        "diana": cfg["perfil"],
        "protocol_id": perfil.protocol_id,
        "formula": perfil.formula,
        "zincs_en_la_estructura": len(zincs),
        "ensemble": {
            "modelos_por_registro": {
                "min": min(modelos_por_registro), "max": max(modelos_por_registro),
            },
            "hay_oraculo": max(modelos_por_registro) > 1,
            "nota": (
                "El checkpoint guarda UN solo MODEL por registro: conservó la pose "
                "top-1 y descartó el resto. Sin ensemble no se puede distinguir «el "
                "ligando nunca alcanza el zinc» de «lo alcanza en otra pose y el "
                "scoring eligió mal». El oráculo coincide con top-1 por construcción."
            ) if max(modelos_por_registro) <= 1 else None,
        },
        "coordinacion": {
            "definicion": (
                "distancia del zinc al átomo donante (N/O/S) más cercano de la pose"
            ),
            "activos_top1": resumen(clases["activos"], "top1"),
            "activos_oraculo": resumen(clases["activos"], "oraculo"),
            "decoys_top1": resumen(clases["decoys"], "top1"),
        },
        "completitud_por_clase": completitud,
        "auc_del_perfil": {
            "casos_completos": round(auc_completos, 4) if auc_completos else None,
            "n_completos": len(puntuables_completos),
            "limite_inferior_itt_adverso": round(auc_itt, 4) if auc_itt else None,
            "n_itt": len(puntuables_itt),
            "delta": (round(auc_completos - auc_itt, 4)
                      if auc_completos and auc_itt else None),
            "nota": (
                "ANÁLISIS DE SENSIBILIDAD, no un AUC corregido. Imputa al registro "
                "perdido el peor valor de su clase —0.0 a un activo, 1.0 a un decoy—, "
                "que es el escenario más adverso posible. Es un LÍMITE INFERIOR bajo "
                "esa imputación: mide la fragilidad ante los ausentes y NO estima qué "
                "puntuación habrían obtenido realmente."
            ),
        },
    }

    # ── Veredicto sobre la coordinación ──────────────────────────────
    activos = informe["coordinacion"]["activos_oraculo"]
    if not activos:
        informe["veredicto_coordinacion"] = "SIN_ACTIVOS_EVALUABLES"
    elif activos[f"en_el_entorno_{_ENTORNO}A"] == 0:
        informe["veredicto_coordinacion"] = "NINGUN_TOP1_DE_ACTIVO_COORDINA"
    elif activos[f"coordinando_{_COORDINACION}A"] == 0:
        informe["veredicto_coordinacion"] = "SOLO_ENTORNO_SIN_COORDINACION"
    else:
        informe["veredicto_coordinacion"] = "HAY_COORDINACION"
    return informe


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("diana", choices=sorted(DIANAS))
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()

    informe = auditar(args.diana)
    print(json.dumps(informe, indent=2, ensure_ascii=False))
    if args.json:
        args.json.write_text(
            json.dumps(informe, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
