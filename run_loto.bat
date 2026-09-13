@echo off
cd /d D:\moldesign-build
python scripts\loto_exact_rescore.py > data\molchamb_loto\loto_rescore.log 2>&1
