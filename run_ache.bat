@echo off
cd /d D:\moldesign-build
python scripts\benchmark_ef_vina.py --target 1gpk --workers 4 > data\molchamb_loto\benchmark_ache.log 2>&1
