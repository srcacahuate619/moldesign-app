"""
Cohortes: la unidad comparable del cribado.

Una COHORTE no es «un montón de moléculas». Es un conjunto declarado que se
evalúa **bajo un único receptor y una única configuración científica**, para que
las filas se puedan comparar entre sí. Ese es el requisito que el Batch
histórico no impone —permite `ALL`, mezcla receptores y filtra por su cuenta— y
por el que sus salidas no son comparables aunque se presenten en una tabla.

Este paquete cubre SÓLO la comprobación previa (Sprint 5A):

    schemas.py      contrato de entrada (`CohortStudy`) y de salida
    parser.py       ingesta que NO descarta filas
    fingerprint.py  identidad reproducible de la cohorte
    preflight.py    orquestación pura: leer, normalizar, declarar
    taxonomy.py     códigos estables de estado, bloqueo y aviso

No ejecuta docking, no persiste, no llama a ML ni a servicios externos, y no
produce ningún score.
"""
