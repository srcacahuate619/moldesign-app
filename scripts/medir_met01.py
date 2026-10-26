"""Run the byte-preserved MET-01 producer distributed with its scientific artifact."""
from pathlib import Path
import runpy
import sys
sys.dont_write_bytecode=True
runpy.run_path(str(Path(__file__).resolve().parent/'artifacts_science/MET-01-ION-DEL-SITIO/source/met01.py'),run_name='__main__')
