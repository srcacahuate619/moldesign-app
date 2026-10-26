"""MET-02-R1-SEMILLA: el brazo de la regla en dos niveles, repetido con el lector de coordenadas arreglado (`f7c46736`).

MET-02-SEMILLA quedó INCONCLUSIVE porque en 5E92 y 9GKV el lector tomaba la carga de la columna 79 como parte del elemento y la
regla nueva no veía el metal. Este R1 repite sólo el brazo nuevo, con el mismo panel y las mismas semillas, y lo compara con el
brazo «antes» ya sellado en MET-02 (mismas poses si Vina es determinista: se comprueba).

Uso:  python-embed\\python.exe scripts\\met02\\met02r1.py congelar
      python-embed\\python.exe scripts\\met02\\met02r1.py ejecutar <capsula> <semilla> [<semilla> ...]
      python-embed\\python.exe scripts\\met02\\met02r1.py analizar
"""
from __future__ import annotations

import json
import shutil
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import met02_semillas as base  # noqa: E402

MET02 = base.EXP
base.EXP = base.RAIZ / "scripts" / "artifacts_science" / "MET-02-R1-SEMILLA"
base.ENTRADA = base.EXP / "entrada"
base.TRABAJO = base.EXP / "_work"
COMMIT = "f7c46736"
base.BRAZOS = {"r1": {"repo": Path(r"D:\moldesign-worktrees\metales"), "commit": COMMIT, "capsula": 9}}


def cmd_congelar() -> int:
    if (base.ENTRADA / "panel.json").exists():
        raise SystemExit("ya congelado: no se sobrescribe")
    base.ENTRADA.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(MET02 / "entrada" / "panel.json", base.ENTRADA / "panel.json")
    protocolo = {
        "experimento": "MET-02-R1-SEMILLA", "creado": base._ahora(), "semillas": list(base.SEMILLAS),
        "repite": "MET-02-SEMILLA (INCONCLUSIVE, 01cfdbca): sólo el brazo de la regla en dos niveles",
        "commit": COMMIT, "cambio_respecto_de_MET-02": "el lector de coordenadas quita la carga de la columna 79 del elemento",
        "panel": {"origen": "scripts/artifacts_science/MET-02-SEMILLA/entrada/panel.json",
                  "sha256": base._sha((base.ENTRADA / "panel.json").read_bytes())},
        "configuracion": "la de MET-02: un caso, exhaustividad 8, 9 poses, Vina 1.2.7, 4 CPU por proceso, cápsula de API aislada",
        "comparador": "brazo «antes» sellado en MET-02-SEMILLA (861f6a0e)",
        "hipotesis": {
            "H2": "Ninguna entrada primaria cambia de estado de metales con la semilla.",
            "H3": "En las entradas del inventario el estado es ABSTENCION si el inventario dice que el ligando coordina algún ion y "
                  "REVISAR si no.",
            "H4": "La pose top-1 coincide con la del brazo «antes» de MET-02 en ≥ 95 % de los pares (entrada, semilla).",
        },
        "decision": {"GO": "H2, H3 sin ninguna discrepancia no explicada por una diferencia declarada del criterio, H4, y ≥ 30 "
                           "entradas primarias evaluables.",
                     "NO_GO": "alguna entrada primaria cambia de estado con la semilla, o una discrepancia de H3 sin explicar.",
                     "INCONCLUSIVE": "en cualquier otro caso."},
        "no_dice": "si abstenerse o revisar es la decisión correcta para cada metal; ni nada de la calidad del docking.",
    }
    base._escribir(base.ENTRADA / "protocolo.json", protocolo)
    print("congelado R1")
    return 0


def cmd_ejecutar(capsula: int, semillas: list[int]) -> int:
    base.SEMILLAS = tuple(semillas)
    base.BRAZOS["r1"]["capsula"] = capsula
    return base.cmd_ejecutar("r1")


def cmd_analizar() -> int:
    panel = base._leer(base.ENTRADA / "panel.json")
    semillas = (42, 7, 13, 101, 2026)

    def fila(directorio: Path, pdb: str, s: int):
        p = directorio / f"{pdb}_{s}.json"
        return base._leer(p) if p.exists() else None

    r1_dir, antes_dir = base.TRABAJO / "r1" / "corridas", MET02 / "_work" / "antes" / "corridas"
    por_entrada, pares, iguales = [], 0, 0
    for e in panel:
        r1 = [fila(r1_dir, e["pdb"], s) for s in semillas]
        antes = [fila(antes_dir, e["pdb"], s) for s in semillas]
        ok = all(f and f["resultado"] == "auditada" for f in r1 + antes)
        x = {"pdb": e["pdb"], "evaluable": ok, "coordinado_en_el_inventario": e["coordinado_en_el_inventario"]}
        if ok:
            estados = [f["metales"]["estado"] for f in r1]
            x.update(estados=estados, cambia_con_la_semilla=len(set(estados)) > 1,
                     primaria=all(f["cristal_en_la_referencia"] for f in r1),
                     estados_antes=[f["metales"]["estado"] for f in antes])
            for a, b in zip(antes, r1):
                pares += 1
                iguales += a["pose_top1_sha256"] == b["pose_top1_sha256"]
            if e["coordinado_en_el_inventario"] is not None:
                x["h3_esperado"] = "ABSTENCION" if e["coordinado_en_el_inventario"] else "REVISAR"
                x["h3_coincide"] = set(estados) == {x["h3_esperado"]}
        por_entrada.append(x)
    ev = [x for x in por_entrada if x["evaluable"]]
    prim = [x for x in ev if x["primaria"]]
    h3 = [x for x in prim if "h3_esperado" in x]
    m = {"entradas": len(panel), "evaluables": len(ev), "primarias": len(prim),
         "H2_cambian_con_la_semilla": {"k": sum(x["cambia_con_la_semilla"] for x in prim), "n": len(prim),
                                       "ic95": base._cp(sum(x["cambia_con_la_semilla"] for x in prim), len(prim))},
         "H3_coincide_con_el_inventario": {"k": sum(x["h3_coincide"] for x in h3), "n": len(h3),
                                           "discrepancias": [x["pdb"] for x in h3 if not x["h3_coincide"]]},
         "H4_pose_top1_igual_a_MET02_antes": {"k": iguales, "n": pares, "fraccion": round(iguales / pares, 4) if pares else None},
         "estados_r1": dict(Counter(s for x in ev for s in x["estados"])),
         "cambios_respecto_de_antes": {x["pdb"]: f"{x['estados_antes'][0]} → {x['estados'][0]}" for x in ev
                                       if x["estados_antes"][0] != x["estados"][0]}}
    base._escribir(base.TRABAJO / "metricas_borrador.json", m)
    base._escribir(base.TRABAJO / "por_entrada_borrador.json", por_entrada)
    print(json.dumps(m, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["congelar"]:
        raise SystemExit(cmd_congelar())
    if a[:1] == ["ejecutar"] and len(a) >= 3:
        raise SystemExit(cmd_ejecutar(int(a[1]), [int(s) for s in a[2:]]))
    if a[:1] == ["analizar"]:
        raise SystemExit(cmd_analizar())
    raise SystemExit(__doc__)
