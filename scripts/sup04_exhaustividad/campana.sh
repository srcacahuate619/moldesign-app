#!/usr/bin/env bash
# SUP-04: la campaña entera, brazo a brazo (e8, e32, e16, e8s43), cada fase en dos shards de 4 CPU en paralelo.
# Se detiene en el primer fallo de una fase; es reanudable (los registros terminales no se repiten).
set -u
cd "$(dirname "$0")/../.."
PY=python-embed/python.exe
LOG=scripts/artifacts_science/SUP-04-EXHAUSTIVIDAD-8T69/_work/logs
mkdir -p "$LOG"
fase() {  # brazo fase
  "$PY" -X utf8 scripts/sup04_exhaustividad/medir.py ejecutar --brazo "$1" --fase "$2" --shard 1 --shards 2 > "$LOG/$1-$2-1.log" 2>&1 &
  local a=$!
  sleep 20  # que las dos cápsulas no preparen el receptor a la vez
  "$PY" -X utf8 scripts/sup04_exhaustividad/medir.py ejecutar --brazo "$1" --fase "$2" --shard 2 --shards 2 > "$LOG/$1-$2-2.log" 2>&1 &
  local b=$!
  wait $a; local ra=$?
  wait $b; local rb=$?
  echo "$(date -Is) $1 $2 shard1=$ra shard2=$rb" | tee -a "$LOG/campana.log"
  [ $ra -eq 0 ] && [ $rb -eq 0 ]
}
for brazo in e8 e32 e16; do
  fase "$brazo" pose || exit 1
  fase "$brazo" panel || exit 1
done
fase e8s43 panel || exit 1
echo "$(date -Is) campaña completa" | tee -a "$LOG/campana.log"
