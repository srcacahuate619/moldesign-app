@echo off
cd /d D:\moldesign-build
python scripts\benchmark_ef_vina.py --target 1gkc --workers 4 > data\molchamb_loto\benchmark_mmp9.log 2>&1
