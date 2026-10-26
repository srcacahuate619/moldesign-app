"""Run the MET-01-R1 producer distributed with its scientific artifact."""
from pathlib import Path
import runpy
import sys
sys.dont_write_bytecode=True
runpy.run_path(str(Path(__file__).resolve().parent/'artifacts_science/MET-01-R1-ION-DEL-SITIO/source/met01r1.py'),run_name='__main__')
