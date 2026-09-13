#!/usr/bin/env python3
"""Launch ACE benchmark - capture stdout only, discard stderr."""
import subprocess, sys, os

os.chdir(r"D:\moldesign-build")
log_path = r"D:\moldesign-build\data\molchamb_loto\ace_benchmark_v3.log"

cmd = [
    sys.executable, "-u",
    r"scripts\benchmark_ef_vina.py",
    "--target", "1o86",
    "--workers", "4",
    "--exhaust", "8",
]

with open(log_path, "w") as log:
    log.write(f"Start: {__import__('datetime').datetime.now()}\n")
    log.flush()
    result = subprocess.run(cmd, stdout=log, stderr=subprocess.DEVNULL, text=True)
    log.write(f"\nEnd: {__import__('datetime').datetime.now()}\n")
    log.write(f"Return code: {result.returncode}\n")
