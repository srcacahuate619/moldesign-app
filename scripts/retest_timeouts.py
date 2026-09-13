"""Re-test: los 6 primeros complejos que fallaron por timeout en el run Fase B.

Hipótesis a verificar: la causa del timeout NO es el tamaño del complejo sino
oversubscription de CPU — cada Vina autodetecta 12 cores (--cpu 0) y con 6
workers simultáneos compiten 72 hilos por 12 cores. Con --cpu 2, 6 workers
usan exactamente los 12 cores.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "rescoring" / "scripts"))
import redock_pdbbind as rp  # noqa: E402


def work_one(pid: str, vina_cpu: int) -> tuple[str, str, float]:
    d = Path("data/pdbbind", pid)
    w = Path(tempfile.mkdtemp())
    rec = str(w / "r.pdbqt")
    lig = str(w / "l.pdbqt")
    if not rp.prepare_receptor_pdbqt(str(d / f"{pid}_protein.pdb"), rec):
        return pid, "prep_rec_fail", 0.0
    if not rp.prepare_ligand_pdbqt(str(d / f"{pid}_ligand.sdf"), lig):
        return pid, "prep_lig_fail", 0.0
    c = rp.find_binding_center(str(d / f"{pid}_ligand.sdf"))
    if c is None:
        return pid, "center_fail", 0.0
    out = str(w / "o.pdbqt")
    t0 = time.time()
    rr = subprocess.run(
        ["tools/vina/vina.exe", "--receptor", rec, "--ligand", lig,
         "--center_x", str(c[0]), "--center_y", str(c[1]), "--center_z", str(c[2]),
         "--size_x", "25", "--size_y", "25", "--size_z", "25",
         "--exhaustiveness", "8", "--num_modes", "9",
         "--cpu", str(vina_cpu), "--out", out],
        capture_output=True, text=True, timeout=400,
    )
    return pid, f"rc={rr.returncode}", time.time() - t0


def main() -> None:
    fails = sorted(json.loads(
        Path("data/pdbbind/vina_redock_cache/redock_failures.json").read_text()
    ))[:6]
    print(f"re-test {len(fails)} fallidos con --cpu 2, 6 workers simultáneos:")
    t0 = time.time()
    results = []
    with ProcessPoolExecutor(max_workers=6) as ex:
        futs = {ex.submit(work_one, p, 2): p for p in fails}
        for f in as_completed(futs):
            try:
                results.append(f.result())
            except Exception as e:  # noqa: BLE001
                results.append((futs[f], f"EXC:{type(e).__name__}", 0.0))
    for pid, status, dt in sorted(results):
        print(f"  {pid}: {status} {dt:.1f}s")
    print(f"TOTAL: {time.time() - t0:.1f}s para {len(fails)} complejos simultáneos")


if __name__ == "__main__":
    main()
