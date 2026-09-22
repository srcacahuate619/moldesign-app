#!/bin/sh
# Lanzador de las auditorías FEP sobre PDBBind en el servidor.
#
# De lo barato a lo caro. Cada paso escribe en su propio directorio de
# resultados/ (nunca se reusa uno) y `set -e` detiene la cadena al primer
# fallo: una réplica que no reproduce su sello invalida la extensión.
#
#   sh lanzar.sh replicas     # FEP-01/02/03 sobre los 203, contra los sellos (minutos)
#   sh lanzar.sh extension    # FEP-01 y FEP-02 sobre PDBBind (decenas de minutos)
#   sh lanzar.sh grupos       # FEP-03 fase 1: cuántas parejas hay (minutos)
#   sh lanzar.sh mcs          # FEP-03 fases 2 y 3 (horas o días; reanudable)
#
# Se ejecuta DENTRO del contenedor moldesign-science, con /work = ~/moldesign-fep.
set -eu
cd /work
W="${WORKERS:-3}"
log() { echo "[$(date -u +%FT%TZ)] $*"; }

case "${1:-}" in
  replicas)
    for n in 1 2 3; do
      log "réplica FEP-0$n sobre los 203"
      python scripts/analisis_fep_pdbbind.py "0$n" --universo molflex \
        --salida "resultados/FEP-0$n-REPLICA" --workers "$W" \
        --comparar-con "scripts/artifacts_science/FEP-0$n/metrics.json"
    done ;;
  extension)
    for n in 1 2; do
      log "FEP-0$n-PDBBIND"
      python scripts/analisis_fep_pdbbind.py "0$n" --universo pdbbind \
        --salida "resultados/FEP-0$n-PDBBIND" --workers "$W"
    done ;;
  grupos)
    log "FEP-03-PDBBIND fase 1"
    python scripts/analisis_fep_pdbbind.py 03 --universo pdbbind \
      --salida resultados/FEP-03-PDBBIND --workers "$W" --solo-grupos ;;
  mcs)
    log "FEP-03-PDBBIND fases 2 y 3"
    python scripts/analisis_fep_pdbbind.py 03 --universo pdbbind \
      --salida resultados/FEP-03-PDBBIND --workers "$W" --reanudar ;;
  *)
    echo "uso: sh lanzar.sh {replicas|extension|grupos|mcs}" >&2
    exit 2 ;;
esac
log "FIN $1"
