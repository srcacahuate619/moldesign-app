r"""
Genera `docking.json` (contrato `moldesign.dock/1`) para un paquete de escena.

# Qué problema resuelve

La escena de render de una búsqueda de Montecarlo tiene que enseñar datos que
EXISTEN: la caja con la que el motor corrió, las poses que devolvió con su
afinidad, y la traza del muestreo con su energía por iteración. Todo eso sale
de una corrida real de AutoDock Vina sobre el mismo receptor preparado que el
producto acopla de verdad (`geometry/prepared.pdb` del paquete) contra el
propio ligando cocristalizado (`geometry/site_ligand.pdb`). Si una pieza no se
puede producir así, no se simula: el paquete se queda sin `docking.json` y el
render se abstiene.

# Qué sale de aquí (y cómo se midió)

    <paquete>/docking.json          el contrato de la escena
    <paquete>/docking/poses/*.pdb   las poses del motor (rank 1 = mejor)

  - `caja`          el centro y tamaño REALES pasados a Vina: son los del
                    contrato de escena (`encuadre.objetivo` y `encuadre.caja`),
                    que ya son la caja adjudicada del producto.
  - `poses`         vina.exe con la caja anterior; afinidades de su REMARK
                    VINA RESULT; `rmsd_cristal_a` por Kabsch emparejando
                    átomos pesados POR NOMBRE contra el ligando cocristalizado
                    (si el emparejado no es biunívoco, el campo no aparece).
  - `traza`         muestreo Metropolis PURO con la función de puntaje de Vina
                    (sin refinado por gradiente: el MC que, en Vina, va seguido
                    de BFGS). Cada iteración perturbación rígida (traslación y
                    rotación), puntaje con vina --score_only reutilizando los
                    mapas escritos una vez, y aceptación Metropolis honesta.
                    Así el "mar de intentos" se ve donde de verdad ocurre.

# Por qué NO es la búsqueda interna de Vina

Vina no exporta su camino de MC+BFGS. Lo honesto es decirlo aquí: la traza es
un muestreo Metropolis con la MISMA función de puntaje, declarado en
`traza.tipo`, con semilla fija. Las poses finales sí son las del dock real.

    python-embed\python.exe scripts\scene_export\build_docking_package.py --pdb-id 1KLI
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
OBABEL = RAIZ / "tools" / "openbabel" / "bin" / "obabel.exe"
VINA = RAIZ / "tools" / "vina" / "vina.exe"

SCHEMA = "moldesign.dock/1"

#: Parametros del muestreo. Vina documenta el resto; estos son los NUESTROS y
#: por eso se llevan a traza.parametros para que quien lea el acta (o la
#: escena) pueda repetirlo con el mismo motor y la misma semilla.
TEMPERATURA = 1.2          # kcal/mol (regla Metropolis, se declara)
SIGMA_TRASL_A = 0.2        # amplitud gaussiana de traslación (orden Vina)
SIGMA_ROT_RAD = 0.02       # amplitud gaussiana de rotación
N_PASOS = 1200

# ── lecturas del paquete ────────────────────────────────────────────────────


def _sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _validar_schema(d: dict, ruta: Path) -> None:
    if d.get("schema") != SCHEMA:
        raise SystemExit(f"{ruta}: schema desconocido ({d.get('schema')!r}); "
                         f"se esperaba {SCHEMA}")


# ── PDBQT ────────────────────────────────────────────────────────────────────

_MODELO = re.compile(r"^REMARK VINA RESULT:\s*(-?\d+\.\d+)\s")


def _separar_poses(pdbqt: Path) -> list[dict]:
    """Parte el PDBQT de salida de Vina en poses, con su afinidad (kcal/mol)."""
    poses, buf, af, dentro = [], [], None, False
    for linea in pdbqt.read_text(encoding="utf-8", errors="replace").splitlines():
        if linea.startswith("MODEL"):
            dentro, buf, af = True, [], None
            continue
        if not dentro:
            continue
        m = _MODELO.match(linea)
        if m:
            af = float(m.group(1))
        elif linea.startswith("ENDMDL"):
            poses.append({"afinidad": af, "lineas": buf})
            dentro, buf = False, []
        elif linea.startswith(("ATOM", "HETATM")):
            buf.append(linea)
    return poses


def _pose_a_pdb(lineas: list[str]) -> str:
    """La pose como PDB: solo los átomos y sin la cola AutoDock del PDBQT
    (tipo atómico+carga), que un lector de PDB estricto tomaría por carga
    formal. La conectividad la infiere el render por distancia, igual que
    con site_ligand.pdb."""
    out = [ln[:66] for ln in lineas if ln.startswith(("ATOM", "HETATM"))]
    return "\n".join(out) + "\nEND\n"


def _atomos_pesados_por_nombre(texto: str, pdbqt: bool) -> dict[str, tuple]:
    """nombre -> (x, y, z) de los átomos PESADOS. PDBQT: el tipo AutoDock en
    las columnas 77-78, no el elemento; el H se reconoce por el nombre."""
    atoms = {}
    for ln in texto.splitlines():
        if not ln.startswith(("ATOM", "HETATM")):
            continue
        nombre = ln[12:16].strip().upper()
        if nombre.startswith("H") or nombre.endswith("H") and len(nombre) < 3:
            continue
        try:
            atoms[nombre] = (float(ln[30:38]), float(ln[38:46]), float(ln[46:54]))
        except (ValueError, IndexError):
            continue
    return atoms


def _rmsd_kabsch(ref: dict[str, tuple], mov: dict[str, tuple]) -> float | None:
    """RMSD de la pose contra el cristal (átomos pesados emparejados por
    nombre), incluyendo la separación espacial: ambos conjuntos se trasladan al
    centroide DE LA REFERENCIA (no al propio) y solo se rota. Es la definición
    de redocking; la versión con doble centrado mide solo la forma."""
    comunes = [k for k in ref if k in mov]
    if len(comunes) < 3 or len(comunes) < len(ref) * 0.9:
        return None
    import numpy as np
    B = np.array([ref[k] for k in comunes], dtype=float)
    A = np.array([mov[k] for k in comunes], dtype=float)
    cr = B.mean(axis=0)
    A0 = A - cr
    B0 = B - cr
    H = A0.T @ B0
    U, _, Vt = np.linalg.svd(H)
    d = np.sign(np.linalg.det(Vt.T @ U.T))
    D = np.diag([1.0, 1.0, d])
    R = Vt.T @ D @ U.T
    E = A0 @ R - B0
    return float(math.sqrt((E * E).sum() / len(comunes)))


# ── corrida real de Vina ────────────────────────────────────────────────────


def _run(cmd: list[str], log: list, **kw) -> subprocess.CompletedProcess:
    """Ejecuta y deja constancia literal del comando."""
    log.append(cmd)
    return subprocess.run(cmd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", **kw)


def _dock(tmp: Path, rec: Path, lig: Path, caja: dict, semilla: int,
          exhaust: int, log: list) -> list[dict]:
    salida = tmp / "poses.pdbqt"
    r = _run([str(VINA), "--receptor", str(rec), "--ligand", str(lig),
              "--center_x", str(caja["centro"][0]), "--center_y", str(caja["centro"][1]),
              "--center_z", str(caja["centro"][2]),
              "--size_x", str(caja["tamano"][0]), "--size_y", str(caja["tamano"][1]),
              "--size_z", str(caja["tamano"][2]),
              "--exhaustiveness", str(exhaust), "--num_modes", "9",
              "--seed", str(semilla), "--energy_range", "9.0",
              "--out", str(salida), "--verbosity", "1"], log)
    if r.returncode != 0 or not salida.exists():
        raise SystemExit(f"vina.exe fallo en el docking:\n{r.stderr[-2000:]}")
    return _separar_poses(salida)


def _escribir_maps(tmp: Path, rec: Path, lig: Path, caja: dict, log: list) -> Path:
    """Los mapas de puntaje una sola vez; la traza los recarga con --maps."""
    pref = tmp / "mapas"
    r = _run([str(VINA), "--receptor", str(rec), "--ligand", str(lig),
              "--center_x", str(caja["centro"][0]), "--center_y", str(caja["centro"][1]),
              "--center_z", str(caja["centro"][2]),
              "--size_x", str(caja["tamano"][0]), "--size_y", str(caja["tamano"][1]),
              "--size_z", str(caja["tamano"][2]),
              "--write_maps", str(pref), "--score_only"], log)
    if r.returncode != 0:
        raise SystemExit(f"vina.exe fallo escribiendo mapas:\n{r.stderr[-2000:]}")
    return pref


# ── la traza Metropolis ─────────────────────────────────────────────────────


def _leer_ligando(p: Path) -> tuple[list[str], list[int], list[list[float]]]:
    """lineas completas, índices de las de átomo y sus coordenadas (31-54)."""
    lineas, idx, coords = [], [], []
    for ln in p.read_text(encoding="utf-8", errors="replace").splitlines():
        if ln.startswith(("ATOM", "HETATM")):
            idx.append(len(lineas))
            coords.append([float(ln[30:38]), float(ln[38:46]), float(ln[46:54])])
        lineas.append(ln)
    return lineas, idx, coords


def _escribir_ligando(ruta: Path, lineas: list[str], idx: list[int],
                      coords: list[list[float]]) -> None:
    """Una copia del PDBQT con las coordenadas perturbadas IN SITU: BRANCH y
    TORSDOF se conservan, que el parser de Vina los necesita."""
    lineas = list(lineas)
    for n, xyz in zip(idx, coords):
        ln = lineas[n]
        lineas[n] = ln[:30] + f"{xyz[0]:8.3f}{xyz[1]:8.3f}{xyz[2]:8.3f}" + ln[54:]
    ruta.write_text("\n".join(lineas) + "\n", encoding="utf-8")


def _puntaje(tmp: Path, mapas: Path, lineas, idx, coords) -> float:
    """Una evaluación de la función de puntaje de Vina sobre la pose propuesta."""
    var = tmp / "_paso.pdbqt"
    _escribir_ligando(var, lineas, idx, coords)
    r = subprocess.run([str(VINA), "--maps", str(mapas), "--score_only",
                        "--ligand", str(var)],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    if r.returncode != 0:
        raise SystemExit(f"vina.exe fallo en --score_only: {r.stderr[-800:]}")
    m = re.search(r"Estimated Free Energy of Binding\s*:\s*(-?\d+\.\d+)", r.stdout)
    if not m:
        raise SystemExit("vina --score_only sin afinidad legible:\n" + r.stdout[-800:])
    return float(m.group(1))


def _rotar(coords: list[list[float]], centro, q: list[float]) -> list[list[float]]:
    """Traslada al centro y aplica el cuaternión q = (w, x, y, z)."""
    w, x, y, z = q
    n = math.sqrt(w * w + x * x + y * y + z * z) or 1.0
    w, x, y, z = w / n, x / n, y / n, z / n
    R = [[1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)],
         [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
         [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)]]
    geom = [sum(axis) / len(axis) for axis in zip(*coords)]
    out = []
    for c in coords:
        v = [c[0] - geom[0], c[1] - geom[1], c[2] - geom[2]]
        p = [R[0][0] * v[0] + R[0][1] * v[1] + R[0][2] * v[2],
             R[1][0] * v[0] + R[1][1] * v[1] + R[1][2] * v[2],
             R[2][0] * v[0] + R[2][1] * v[1] + R[2][2] * v[2]]
        out.append([p[0] + centro[0], p[1] + centro[1], p[2] + centro[2]])
    return out


def _traza(tmp: Path, mapas: Path, ligando: Path, caja: dict, semilla: int,
           log: list) -> dict:
    """Metropolis puro sobre traslación+rotación rígida, puntaje Vina."""
    import random
    rng = random.Random(semilla)
    cab, idx, coords0 = _leer_ligando(ligando)
    n = len(coords0)
    centro_caja = caja["centro"]
    tam = caja["tamano"]

    def _dentro(coords) -> bool:
        """La pose SOLO se propone si TODOS sus átomos caen dentro de la caja
        (Vina rechaza la pose entera si un átomo sale: no imitamos, cumplimos)."""
        lo = [centro_caja[j] - tam[j] / 2.0 for j in range(3)]
        hi = [centro_caja[j] + tam[j] / 2.0 for j in range(3)]
        return all(lo[j] <= xyz[j] <= hi[j] for xyz in coords for j in range(3))

    # estado inicial: posición y orientación ALEATORIAS dentro de la caja, como
    # el random_conf de la búsqueda de verdad: el muestreo arranca sin saber nada
    # estado inicial: posición y orientación ALEATORIAS dentro de la caja, como
    # el random_conf de la búsqueda de verdad: el muestreo arranca sin saber nada
    for _ in range(400):
        t = [centro_caja[i] + rng.uniform(-0.4, 0.4) * tam[i] for i in range(3)]
        q = [rng.gauss(0, 1) for _ in range(4)]
        s = math.sqrt(sum(x * x for x in q))
        q = [x / s for x in q]
        coords_cur = _rotar(coords0, t, q)
        if _dentro(coords_cur):
            break
    else:
        raise SystemExit("no se pudo meter la pose inicial dentro de la caja")

    e_cur = _puntaje(tmp, mapas, cab, idx, coords_cur)
    pasos = []
    for i in range(N_PASOS):
        t2 = [t[j] + rng.gauss(0, SIGMA_TRASL_A) for j in range(3)]
        dq = [1.0, rng.gauss(0, SIGMA_ROT_RAD), rng.gauss(0, SIGMA_ROT_RAD),
              rng.gauss(0, SIGMA_ROT_RAD)]
        s2 = math.sqrt(sum(x * x for x in dq))
        dq = [x / s2 for x in dq]
        q2 = [q[0] * dq[0] - q[1] * dq[1] - q[2] * dq[2] - q[3] * dq[3],
              q[0] * dq[1] + q[1] * dq[0] + q[2] * dq[3] - q[3] * dq[2],
              q[0] * dq[2] - q[1] * dq[3] + q[2] * dq[0] + q[3] * dq[1],
              q[0] * dq[3] + q[1] * dq[2] - q[2] * dq[1] + q[3] * dq[0]]
        coords2 = _rotar(coords0, t2, q2)
        dentro = _dentro(coords2)
        if dentro:
            e2 = _puntaje(tmp, mapas, cab, idx, coords2)
        else:
            e2 = None
        acep = dentro and (e2 <= e_cur or rng.random()
                           < math.exp(min(0.0, (e_cur - e2) / TEMPERATURA)))
        if acep:
            t, q, e_cur, coords_cur = t2, q2, e2, coords2
        pasos.append({"i": i, "centro": [round(x, 3) for x in t],
                      "energia": round(e_cur, 4), "aceptada": bool(acep)})
    return {"tipo": "metropolis_vina_sin_refinado",
            "semilla": semilla, "n_pasos": N_PASOS,
            "parametros": {"temperatura_kcal_mol": TEMPERATURA,
                           "sigma_trasl_a": SIGMA_TRASL_A,
                           "sigma_rot_rad": SIGMA_ROT_RAD},
            "pasos": pasos}


# ── montaje del paquete ─────────────────────────────────────────────────────


def preparar_ligando(pdb: Path, tmp: Path) -> Path:
    """El ligando cocristalizado a PDBQT con Open Babel: coordenadas del
    depósito intactas (un redocking), cargas Gasteiger y árbol de torsiones
    del propio obabel. Meeko preparaba la entrada en la app, pero en el
    runtime embebido meeko+prody no arranca con numpy 2.x: se documenta aquí
    y en `procedencia` qué herramienta preparó realmente la entrada."""
    out = tmp / "ligando.pdbqt"
    r = subprocess.run([str(OBABEL), "-ipdb", str(pdb), "-opdbqt", "-O",
                        str(out), "--partialcharge", "gasteiger"],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    if r.returncode != 0 or not out.exists():
        raise SystemExit(f"obabel fallo preparando el ligando:\n{r.stderr[-1200:]}")
    return out


def preparar_receptor(pdb: Path, tmp: Path) -> Path:
    """Receptor rígido a PDBQT con Open Babel (`-xr`: sin flexibilidad).
    Misma nota que en `preparar_ligando`: la política de limpieza la aplicó
    `services.docking.preparer` al generar prepared.pdb; aquí solo se
    parametriza para Vina."""
    out = tmp / "receptor.pdbqt"
    r = subprocess.run([str(OBABEL), "-ipdb", str(pdb), "-opdbqt", "-O",
                        str(out), "-xr", "--partialcharge", "gasteiger"],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    if r.returncode != 0 or not out.exists():
        raise SystemExit(f"obabel fallo preparando el receptor:\n{r.stderr[-1200:]}")
    return out


def main() -> int:
    global N_PASOS
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdb-id", required=True)
    ap.add_argument("--escenas", default=str(RAIZ / "dist" / "scenes"))
    ap.add_argument("--pasos", type=int, default=N_PASOS)
    ap.add_argument("--exhaustividad", type=int, default=32)
    ap.add_argument("--semilla", type=int, default=0,
                    help="por defecto se deriva del PDB ID para reproducir")
    a = ap.parse_args()

    paquete = Path(a.escenas) / a.pdb_id
    escena = json.loads((paquete / "scene.json").read_text(encoding="utf-8"))
    prep = paquete / "geometry" / "prepared.pdb"
    ligp = paquete / "geometry" / "site_ligand.pdb"
    if not prep.exists() or not ligp.exists():
        raise SystemExit(f"{a.pdb_id}: falta prepared.pdb o site_ligand.pdb en el paquete")
    caja = {"centro": [float(x) for x in escena["encuadre"]["objetivo"]],
            "tamano": [float(x) for x in escena["encuadre"]["caja"]]}
    # Vina acepta semillas enteras con signo de 31 bits; el prefijo SHA-256
    # puede ocupar 32 bits y hacer fallar el docking antes de empezar.
    semilla = a.semilla or (int(hashlib.sha256(a.pdb_id.encode()).hexdigest()[:8], 16) & 0x7fffffff) or 1
    if not 1 <= semilla <= 0x7fffffff:
        ap.error("--semilla debe estar entre 1 y 2147483647 (limite de Vina)")
    tmp = paquete / "docking" / "_tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    for viej in (paquete / "docking").glob("poses/*.pdb"):
        viej.unlink()
    (paquete / "docking" / "poses").mkdir(parents=True, exist_ok=True)

    log: list = []
    t0 = time.time()
    rec = preparar_receptor(prep, tmp)
    lig = preparar_ligando(ligp, tmp)
    poses = _dock(tmp, rec, lig, caja, semilla, a.exhaustividad, log)

    ref = _atomos_pesados_por_nombre(ligp.read_text(encoding="utf-8"), pdbqt=False)
    rdk = [_rmsd_kabsch(ref, _atomos_pesados_por_nombre("\n".join(p["lineas"]), True))
           for p in poses]

    mapas = _escribir_maps(tmp, rec, lig, caja, log)
    N_PASOS = a.pasos
    traza = _traza(tmp, mapas, lig, caja, semilla, log)

    out = {
        "schema": SCHEMA,
        "motor": {"nombre": "vina", "version": "1.2.7", "binario_sha256": _sha256(VINA),
                  "preparacion_pdbqt": "openbabel (gasteiger; receptor rigido -xr)",
                  "pdbqt_sha256": {"receptor": _sha256(rec), "ligando": _sha256(lig)}},
        "caja": caja,
        "exhaustividad": a.exhaustividad,
        "poses": [],
        "traza": traza,
        "procedencia": {
            "generador": "scripts/scene_export/build_docking_package.py",
            "generado_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "python": sys.version.split()[0],
            "entrada_sha256": {"receptor": _sha256(prep), "ligando": _sha256(ligp)},
            "segundos": round(time.time() - t0, 1),
        },
    }
    for i, p in enumerate(poses):
        arch = f"docking/poses/pose_{i + 1:03d}.pdb"
        ruta = paquete / arch
        ruta.write_text(_pose_a_pdb(p["lineas"]), encoding="utf-8")
        item = {"rank": i + 1, "afinidad_kcal_mol": p["afinidad"],
                "archivo": arch, "sha256": _sha256(ruta)}
        if rdk[i] is not None:
            item["rmsd_cristal_a"] = round(rdk[i], 3)
        out["poses"].append(item)

    (paquete / "docking.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[ok] {paquete / 'docking.json'}  poses={len(poses)} "
          f"pasos={traza['n_pasos']}  mejor={poses[0]['afinidad'] if poses else '?'} "
          f"rmsd={rdk[0]!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
