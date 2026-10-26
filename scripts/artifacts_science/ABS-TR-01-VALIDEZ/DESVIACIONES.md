# Desviaciones respecto del registro previo

## 1. El validador del producto rechaza un ligando antes del preflight (durante `congelar`)

Al congelar los microestados, el validador del producto rechazó el SMILES del CCD de **COH** (1DIY, protoporfirina
de cobalto): «AutoDock Vina no tiene parámetros confiables para estos elementos» (Co). La sonda de microestados se
detenía en esa excepción.

Cambio del arnés, antes de generar ninguna salida de Preparación: los SMILES que rechaza el validador se anotan
(`rechazo_del_validador` en `sistemas.json`) y no pasan por la sonda de microestados, y un 400/409/422 del
preflight cuenta como **detenerse en la entrada**, igual que un bloqueo técnico del preflight, que es lo que el
registro ya llama DETENER. No cambia ningún umbral, ni la referencia, ni los sistemas.
