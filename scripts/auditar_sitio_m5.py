#!/usr/bin/env python3
"""¿El benchmark que validó un perfil M5-Zn acopló donde dice que acopló?

═══════════════════════════════════════════════════════════════════════════
LA CAJA DE VINA ES UN CUBO, NO UNA ESFERA
═══════════════════════════════════════════════════════════════════════════

La primera versión de este script comparaba la distancia euclídea al centro
con el semilado de la caja:

    math.dist(punto, centro) > 12.5     # MAL

Eso trata el cubo como la esfera inscrita en él y rechaza puntos
perfectamente válidos. El radio hasta una esquina del cubo de 25 Å es
√(12.5²·3) = 21.65 Å, no 12.5.

El criterio correcto es POR EJE:

    |Δx| ≤ sx/2  ∧  |Δy| ≤ sy/2  ∧  |Δz| ≤ sz/2

El error tuvo consecuencias. Con él, ACE/1O86 «tenía el 75.8 % de sus poses
fuera de la caja»; con el criterio correcto, la nube entera cae dentro por los
tres ejes (Δ = −7.67, +6.73, +8.36 para el centroide medio). La invalidación de
ACE no se sostenía: era un artefacto de comparar contra una esfera inexistente.

MMP9/1GKC sí falla el criterio correcto —su zinc catalítico está a Δz = −17.34,
fuera por el eje Z— pero ese es otro asunto, y hubo que medirlo bien para
saberlo.

═══════════════════════════════════════════════════════════════════════════
LO QUE ESTE SCRIPT NO HACE, Y ANTES DECÍA HACER
═══════════════════════════════════════════════════════════════════════════

**No reconstruye la caja.** El promedio de una nube de poses NO es el centro de
la rejilla: las poses se acumulan donde el scoring encuentra mínimos, no
uniformemente alrededor del centro. Lo que se calcula es el `centroide_medio_de_
poses`, que es una descripción de dónde acabaron los ligandos, y nada más.

**No confunde el centroide con la molécula.** La ocupación real se mide sobre
los ÁTOMOS de cada pose, no sobre su centro de masas.

**No confunde cercanía con coordinación.** Para saber si una pose interactúa
con el zinc hay que medir la distancia del metal al átomo DONANTE más cercano
—N, O o S—, no a un centroide. Y se estratifica por actividad: exigirle
quelación a un decoy no tiene sentido.

**No usa la completitud como prueba de sitio.** Que a un registro le falte la
pose o las features es un problema de integridad del artefacto, y se informa
aparte.

Uso:

    python scripts/auditar_sitio_m5.py 1gkc
    python scripts/auditar_sitio_m5.py 1o86 --json informe.json
"""

from __future__ import annotations

import argparse
import hashlib
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

DIANAS = {
    "1gkc": {
        "nombre": "MMP9",
        "protocol_id": "M5_ZN_MMP9_1GKC_V1",
        "estructura": "data/1gkc.pdb",
        "checkpoint": "data/benchmark_checkpoint_mmp9.json",
        "centro_declarado": (53.25, 22.51, 129.72),
        "fuentes_del_centro": (
            "scripts/benchmark_ef_vina.py::TARGETS['1gkc']",
            "data/multitarget/mmp9/metadata.json",
        ),
    },
    "1o86": {
        "nombre": "ACE",
        "protocol_id": "M5_ZN_ACE_1O86_V1",
        "estructura": "data/1O86_clean.pdb",
        "checkpoint": "data/benchmark_checkpoint_ace.json",
        "centro_declarado": (43.82, 38.24, 46.71),
        "fuentes_del_centro": ("scripts/benchmark_ef_vina.py::TARGETS['1o86']",),
    },
}

#: Tamaño de la caja por eje. `benchmark_ef_vina.py` usa `curated_box or 25` y
#: ninguna de las tres dianas está en `curated_targets.csv`. Es un supuesto
#: DECLARADO: los logs del benchmark no registran la caja efectiva, así que
#: sólo se puede afirmar «compatible con 25 Å», no «se usó 25 Å».
CAJA = (25.0, 25.0, 25.0)

_METALES = {"ZN", "FE", "MG", "MN", "CA", "CU", "NI", "CO", "CD"}
_NO_LIGANDO = {"HOH", "WAT", "SO4", "PO4", "GOL", "EDO", "PEG", "ACT", "CL",
               "NA", "K", "MES", "TRS", "NAG", "BMA", "MAN", "FUC"} | _METALES
#: Átomos que pueden coordinar un catión metálico.
_DONANTES = {"N", "O", "S"}
#: Coordinación de Zn²⁺: típicamente 1.9–2.4 Å. Se usa 2.8 como umbral generoso
#: —incluye geometrías subóptimas de docking— y 4.0 como «en el entorno».
_UMBRAL_COORDINACION = 2.8
_UMBRAL_ENTORNO = 4.0


def sha256(ruta: Path) -> str:
    d = hashlib.sha256()
    with ruta.open("rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            d.update(b)
    return d.hexdigest()


def delta_por_eje(punto, centro) -> list[float]:
    return [round(p - c, 2) for p, c in zip(punto, centro)]


def dentro_de_la_caja(punto, centro, tamano=CAJA) -> bool:
    """EL criterio. Un cubo se comprueba eje a eje, nunca por radio."""
    return all(abs(p - c) <= t / 2.0 for p, c, t in zip(punto, centro, tamano))


def _situar(punto, centro, tamano=CAJA) -> dict:
    return {
        "coordenadas": [round(v, 2) for v in punto],
        "delta_por_eje": delta_por_eje(punto, centro),
        "dentro_de_la_caja": dentro_de_la_caja(punto, centro, tamano),
        "distancia_euclidea": round(math.dist(punto, centro), 2),
    }


def leer_heteroatomos(ruta: Path) -> dict:
    residuos: dict = {}
    with ruta.open(encoding="utf-8", errors="replace") as f:
        for linea in f:
            if not linea.startswith("HETATM") or len(linea) < 78:
                continue
            try:
                p = (float(linea[30:38]), float(linea[38:46]), float(linea[46:54]))
            except ValueError:
                continue
            clave = (linea[17:20].strip(), linea[21], linea[22:26].strip())
            residuos.setdefault(clave, []).append((p, linea[76:78].strip().upper()))
    return residuos


def atomos_de_la_pose(pose: str) -> list[tuple[tuple[float, float, float], str]]:
    """Coordenadas y elemento de cada átomo. PDBQT: tipo AutoDock en 78-79."""
    atomos = []
    for linea in pose.splitlines():
        if not linea.startswith(("ATOM", "HETATM")):
            continue
        try:
            p = (float(linea[30:38]), float(linea[38:46]), float(linea[46:54]))
        except ValueError:
            continue
        tipo = linea[77:79].strip().upper() if len(linea) >= 78 else ""
        # `OA`, `NA`, `SA` son tipos de AutoDock: aceptores de puente de H.
        # Su primer carácter es el elemento.
        atomos.append((p, tipo[:1] if tipo else ""))
    return atomos


def auditar(clave: str, maximo: int) -> dict:
    cfg = DIANAS[clave]
    estructura = RAIZ / cfg["estructura"]
    checkpoint = RAIZ / cfg["checkpoint"]
    centro = cfg["centro_declarado"]

    informe: dict = {
        "diana": cfg["nombre"],
        "protocol_id": cfg["protocol_id"],
        "criterio": (
            "inclusión POR EJE en un cubo: |Δx|≤sx/2 ∧ |Δy|≤sy/2 ∧ |Δz|≤sz/2. "
            "La distancia euclídea se informa como referencia y NO decide: "
            "usarla equivale a comparar contra la esfera inscrita, que descarta "
            "las esquinas del volumen real."
        ),
        "estructura": {"ruta": cfg["estructura"], "sha256": sha256(estructura)},
        "checkpoint": {"ruta": cfg["checkpoint"], "sha256": sha256(checkpoint)},
        "caja": {
            "centro_declarado": list(centro),
            "tamano_supuesto": list(CAJA),
            "limites_por_eje": {
                eje: [round(centro[i] - CAJA[i] / 2, 2), round(centro[i] + CAJA[i] / 2, 2)]
                for i, eje in enumerate("xyz")
            },
            "fuentes_del_centro": list(cfg["fuentes_del_centro"]),
            "advertencia": (
                "El tamaño es un SUPUESTO: los logs del benchmark no registran la "
                "caja efectiva. Sólo se puede afirmar compatibilidad con 25 Å."
            ),
        },
    }

    residuos = leer_heteroatomos(estructura)

    # ── Metales ──────────────────────────────────────────────────────
    metales = []
    for (nombre, cadena, num), atomos in residuos.items():
        elemento = (atomos[0][1] or nombre.upper())
        if elemento in _METALES and len(atomos) == 1:
            metales.append({
                "elemento": elemento, "cadena": cadena, "residuo": num,
                **_situar(atomos[0][0], centro),
            })
    metales.sort(key=lambda m: m["distancia_euclidea"])
    informe["metales"] = metales
    zincs = [m for m in metales if m["elemento"] == "ZN"]

    # ── Ligando cristalográfico ──────────────────────────────────────
    candidatos = sorted(
        ((k, v) for k, v in residuos.items() if k[0] not in _NO_LIGANDO and len(v) >= 8),
        key=lambda kv: -len(kv[1]),
    )
    ligandos = []
    for (nombre, cadena, num), atomos in candidatos[:4]:
        puntos = [p for p, _ in atomos]
        c = tuple(st.mean(x) for x in zip(*puntos))
        ligandos.append({
            "residuo": nombre, "cadena": cadena, "numero": num,
            "n_atomos": len(atomos),
            "centroide": _situar(c, centro),
            "atomos_dentro_de_la_caja": sum(
                1 for p in puntos if dentro_de_la_caja(p, centro)
            ),
        })
    informe["ligandos_cristalograficos"] = ligandos
    if not ligandos:
        informe["nota_ligando"] = (
            "El archivo de estructura no conserva ningún ligando cristalográfico, "
            "así que el bolsillo del inhibidor NO se puede usar como referencia "
            "independiente. Hace falta el complejo original para completar esta "
            "comprobación."
        )

    # ── Poses: átomos, no centroides ─────────────────────────────────
    datos = json.loads(checkpoint.read_text(encoding="utf-8"))
    registros = datos["results"]
    paso = max(1, len(registros) // maximo)

    centroides, sin_pose, sin_features = [], 0, 0
    dentro_todos, dentro_parcial, fuera = 0, 0, 0
    extremos = [[math.inf, -math.inf] for _ in range(3)]
    contactos: dict[str, list[float]] = {"activos": [], "decoys": []}
    zinc_puntos = [tuple(z["coordenadas"]) for z in zincs]

    for registro in registros[::paso]:
        atomos = atomos_de_la_pose(registro.get("pose_pdbqt") or "")
        if not atomos:
            sin_pose += 1
            continue
        if not registro.get("features"):
            sin_features += 1

        puntos = [p for p, _ in atomos]
        centroides.append(tuple(st.mean(x) for x in zip(*puntos)))
        for p in puntos:
            for i in range(3):
                extremos[i][0] = min(extremos[i][0], p[i])
                extremos[i][1] = max(extremos[i][1], p[i])

        n_dentro = sum(1 for p in puntos if dentro_de_la_caja(p, centro))
        if n_dentro == len(puntos):
            dentro_todos += 1
        elif n_dentro:
            dentro_parcial += 1
        else:
            fuera += 1

        # Distancia del zinc al átomo DONANTE más cercano de esta pose.
        if zinc_puntos:
            donantes = [p for p, e in atomos if e in _DONANTES]
            if donantes:
                d = min(math.dist(z, p) for z in zinc_puntos for p in donantes)
                grupo = "activos" if registro.get("is_active") else "decoys"
                contactos[grupo].append(d)

    informe["poses"] = {
        "registros_totales": len(registros),
        "muestreadas": len(registros[::paso]),
        "con_pose": len(centroides),
        "paso_de_muestreo": paso,
        "ocupacion_por_atomo": {
            eje: [round(extremos[i][0], 1), round(extremos[i][1], 1)]
            for i, eje in enumerate("xyz")
        } if centroides else None,
        "poses_con_todos_sus_atomos_dentro": dentro_todos,
        "poses_parcialmente_dentro": dentro_parcial,
        "poses_enteramente_fuera": fuera,
    }
    if centroides:
        medio = tuple(st.mean(x) for x in zip(*centroides))
        informe["centroide_medio_de_poses"] = {
            **_situar(medio, centro),
            "advertencia": (
                "NO es una reconstrucción del centro de la caja. Las poses se "
                "acumulan donde el scoring encuentra mínimos, no uniformemente "
                "alrededor del centro."
            ),
        }

    # ── Interacción real con el zinc ─────────────────────────────────
    def resumen(ds: list[float]) -> dict | None:
        if not ds:
            return None
        return {
            "n": len(ds),
            "minima": round(min(ds), 2),
            "mediana": round(st.median(ds), 2),
            "coordinando_2.8A": sum(1 for d in ds if d <= _UMBRAL_COORDINACION),
            "en_el_entorno_4.0A": sum(1 for d in ds if d <= _UMBRAL_ENTORNO),
        }

    informe["interaccion_con_el_zinc"] = {
        "definicion": (
            "distancia mínima entre cualquier zinc de la estructura y el átomo "
            "donante (N/O/S) más cercano de la pose. NO es la distancia al "
            "centroide del ligando."
        ),
        "activos": resumen(contactos["activos"]),
        "decoys": resumen(contactos["decoys"]),
        "nota": (
            "Se estratifica porque exigirle coordinación a un decoy no tiene "
            "sentido: lo informativo es si los ACTIVOS la alcanzan."
        ),
    }

    # ── Completitud del artefacto: problema aparte ───────────────────
    informe["completitud_del_artefacto"] = {
        "registros_sin_pose": sin_pose,
        "registros_con_pose_y_sin_features": sin_features,
        "nota": (
            "Es un problema de INTEGRIDAD del checkpoint, independiente de dónde "
            "se acopló. Rompe la correspondencia uno a uno entre predicción y "
            "geometría, pero no dice nada sobre el sitio."
        ),
    }

    # ── Veredicto ────────────────────────────────────────────────────
    problemas, reservas = [], []
    if not zincs:
        problemas.append("la estructura no trae ningún ion de zinc")
    else:
        dentro = [z for z in zincs if z["dentro_de_la_caja"]]
        if not dentro:
            peor = min(zincs, key=lambda z: max(abs(v) for v in z["delta_por_eje"]))
            ejes = ", ".join(
                f"Δ{eje}={peor['delta_por_eje'][i]:+.2f}"
                for i, eje in enumerate("xyz")
                if abs(peor["delta_por_eje"][i]) > CAJA[i] / 2
            )
            problemas.append(
                f"NINGÚN zinc cae dentro de la caja declarada. El más próximo "
                f"({peor['elemento']} {peor['cadena']}{peor['residuo']}) queda fuera "
                f"por {ejes}, con semilado {CAJA[0] / 2}"
            )
    if metales and not metales[0]["elemento"] == "ZN" and metales[0]["dentro_de_la_caja"]:
        reservas.append(
            f"el metal más próximo al centro es {metales[0]['elemento']} "
            f"{metales[0]['cadena']}{metales[0]['residuo']} a "
            f"{metales[0]['distancia_euclidea']} Å, y sí está dentro de la caja"
        )
    for lig in ligandos:
        if not lig["centroide"]["dentro_de_la_caja"]:
            problemas.append(
                f"el ligando cristalográfico {lig['residuo']} "
                f"{lig['cadena']}{lig['numero']} tiene su centroide fuera de la "
                f"caja (Δ={lig['centroide']['delta_por_eje']}), y sólo "
                f"{lig['atomos_dentro_de_la_caja']}/{lig['n_atomos']} átomos dentro"
            )
            break
    if not ligandos:
        reservas.append(
            "sin ligando cristalográfico en el archivo no se puede comprobar el "
            "bolsillo del inhibidor"
        )
    activos = informe["interaccion_con_el_zinc"]["activos"]
    if activos and activos["coordinando_2.8A"] == 0:
        reservas.append(
            f"ningún activo muestreado coloca un donante a ≤{_UMBRAL_COORDINACION} Å "
            f"del zinc (mínima observada: {activos['minima']} Å)"
        )
    if sin_pose or sin_features:
        reservas.append(
            f"integridad del checkpoint: {sin_pose} registros sin pose y "
            f"{sin_features} con pose y sin features"
        )

    informe["problemas"] = problemas
    informe["reservas"] = reservas
    informe["veredicto"] = (
        "SITIO_INCORRECTO" if problemas
        else "PROCEDENCIA_INCOMPLETA" if reservas
        else "SITIO_COMPATIBLE"
    )
    return informe


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("diana", choices=sorted(DIANAS))
    parser.add_argument("--maximo", type=int, default=600,
                        help="Poses a muestrear, repartidas por todo el checkpoint.")
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()

    informe = auditar(args.diana, args.maximo)
    print(json.dumps(informe, indent=2, ensure_ascii=False))
    if args.json:
        args.json.write_text(
            json.dumps(informe, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return 0 if informe["veredicto"] == "SITIO_COMPATIBLE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
