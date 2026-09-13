@echo off
REM ACE benchmark - unbuffered via cmd
cd /d D:\moldesign-build
echo Start: %date% %time% > D:\moldesign-build\data\molchamb_loto\ace_benchmark_v2.log
python -u scripts/benchmark_ef_vina.py --target 1o86 --workers 4 --exhaust 8 >> D:\moldesign-build\data\molchamb_loto\ace_benchmark_v2.log 2>nul
echo End: %date% %time% >> D:\moldesign-build\data\molchamb_loto\ace_benchmark_v2.log
