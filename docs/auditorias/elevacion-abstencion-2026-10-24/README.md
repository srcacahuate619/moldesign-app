# Abstención de la elevación 2D → 3D (2026-10-24)

## Qué decide el umbral

La elevación se abstiene cuando, de media, los átomos tendrían que moverse más
de **un enlace** para que la geometría coincidiera con el dibujo. Es una media
(RMS, con los estereocentros y sus vecinos ×10), no el desplazamiento de cada
átomo: con la razón por debajo de 1, un átomo suelto puede moverse más.

    razón = desajuste mediano (3 semillas) / longitud media de enlace del dibujo
    fiel  = razón ≤ 1,0          (`UMBRAL_ENLACES`, `backend/chem/elevacion.py`)

El umbral de un enlace se fijó **antes** de mirar la cola de la distribución.
Es una decisión de diseño con una justificación geométrica, no una cifra medida
contra un experimento: no hay un valor «correcto» de desajuste que se pueda
comprobar. Lo que se midió es cuántas moléculas quedan a cada lado.

## Conjunto medido (167 moléculas)

- 147 SMILES neutros de los paneles congelados de `scripts/artifacts_science`
  (solo lectura): CAL-8HFI-01 (57) y CAL-D-01-R4 (90), sin repetidos.
- 20 moléculas conocidas escritas a mano (validadas con RDKit), para tener
  variedad de tamaño y de flexibilidad.

Límites del conjunto: son dos series congéneres (inhibidores de NET y de VMAT2)
más moléculas sueltas. Sólo tres pasan de 34 átomos pesados (imatinib 37, atorvastatina 41
y una de 35); el paclitaxel no entró porque su SMILES escrito a mano no
era válido. La cifra no dice nada de moléculas grandes.

Poses reales de Moldex (registro top-1 de corridas Vina y fixtures de Meeko):
razón entre 0,34 y 0,58 en los tres casos medidos (dossier 1.0.2, paracetamol,
exaltólida). Ninguna se abstiene.

## Resultados

| Estadística | > 1 | > 0,75 | mediana | p95 |
|---|---:|---:|---:|---:|
| Producto antes del cambio (semilla 42, recorte por tamaño) | 2 | 21 | 0,41 | 0,85 |
| Mediana de 3 semillas, 16 candidatos (medida) | 1 | 29 | 0,35 | 0,88 |
| **Producto final: mediana de 3 semillas, recorte por tamaño** | **1** | **30** | **0,37** | **0,88** |

El producto final se midió llamando a `modelo_desde_conformador` tal como queda
(`validacion/validacion.jsonl`). Único caso que se abstiene: imatinib, con
razón 1,057.

Seis moléculas quedan entre 0,9 y 1,0, además de imatinib. La distribución no tiene un hueco
cerca de 1 enlace, así que la decisión por molécula es frágil: un cambio de
semilla puede moverla. Eso se declara en el código y en la interfaz no se
muestra como una certeza.

## Por qué no se usa una sola semilla

Con la semilla 42 y el recorte por tamaño, imatinib sale a 1,95 enlaces. Con
16 candidatos, las semillas 1, 2 y 3 dan 1,06, 1,06 y 1,56. Con 4, 8, 16, 32 y
64 candidatos (`convergencia.jsonl`) la mediana se estabiliza en unos 25 px
(≈ 1,03 enlaces) y la dispersión entre semillas cae al crecer el muestreo.

Por eso el criterio pasa a ser la **mediana de tres semillas**, no la mejor
vista ni una semilla. La vista que se muestra sigue siendo la mejor de todos los
candidatos.

**Desviación del criterio previo.** La estadística fijada antes de medir era el
cálculo de producto con semilla 42. Se cambió después de ver que esa cifra
depende de la semilla. El umbral (1 enlace) no cambió. La cifra que lo justifica
ahora es la del producto final.

## Moléculas grandes (35–51 átomos pesados), medido después

El conjunto de arriba casi no tenía moléculas grandes. `validar_grandes.py` toma
todas las de 35 a 150 átomos pesados que traen los CSV y JSONL de
`scripts/artifacts_science` (fragmento mayor, sin repetidos): 37, de FND-02 (27),
FEP-09-R1 (5), CAL-D-01-R4 (3) y MET-01-R1 (2). Ninguna pasa de 51. Se llamó a
`modelo_desde_conformador` tal como queda en `6485a6b3` (8 candidatos por
semilla en este tamaño) y, aparte, con cada semilla sola (`grandes.jsonl`).

| | n | > 1 | > 0,75 | mediana | p95 | máx. |
|---|---:|---:|---:|---:|---:|---:|
| 167 del conjunto original | 167 | 1 | 30 | 0,37 | 0,88 | 1,06 |
| **35–51 átomos pesados** | **37** | **16** | **25** | **0,92** | **1,35** | **2,12** |

- **El umbral de un enlace no se comporta igual con el tamaño.** En las
  grandes se abstienen 16 de 37 (43 %), frente a 1 de 167. La mediana pasa de
  0,37 a 0,92 enlaces. Es lo esperable: cuanto más larga y flexible la
  molécula, más se aleja cualquier conformador 3D de un dibujo plano y
  extendido. La abstención dice algo real (levantar el dibujo de esas moléculas
  movería mucho los átomos), pero en este tamaño deja de ser la excepción.
- **La decisión es frágil.** 10 de 37 quedan entre 0,9 y 1,1, y en 6 la
  decisión cambia según la semilla (con la mediana de tres, el resultado de
  arriba).
- **Coste:** 4,0 s de mediana y 7,6 s como máximo con tres semillas.
- **Energía:** el conformador elegido queda una mediana de 11,3 kcal/mol (MMFF,
  fase gas) por encima del más bajo encontrado: 29 de 37 por encima de 5 y 20
  por encima de 10. Se declara en el visor desde `6485a6b3`; no cambia la
  elección.
- **Lo que no se midió:** poses reales de Moldex de este tamaño (las tres
  medidas tenían razón 0,34–0,58 y eran pequeñas), ni moléculas de más de 51
  átomos pesados.

No se cambia el umbral a la vista de estos datos: escoger uno nuevo después de
mirar la distribución sería ajustarlo a la muestra.

### Decisiones (2026-10-24, con el propietario)

1. **Moldex enseña la pose en 3D aunque no se levante** (`3ea0aa92`). La
   abstención cubre la animación del dibujo a la pose, no la pose, que es
   evidencia de la corrida. Antes la ficha se quedaba en 2D.
2. **16 candidatos por semilla de 31 a 60 átomos pesados**, con un criterio
   fijado antes de medir: pasar a 16 si la abstención bajaba al menos 5 de 37 y
   la mediana no pasaba de 8 s (`candidatos_grandes.py`,
   `candidatos_grandes.jsonl`):

   | candidatos | > 1 | razón mediana | s (mediana) | s (máx.) | ΔE mediana |
   |---:|---:|---:|---:|---:|---:|
   | 8 | 16/37 | 0,92 | 4,0 | 7,6 | 11,3 |
   | 16 | **8/37** | 0,81 | 7,5 | 15,1 | 11,5 |

   Se cumplen las dos condiciones. La vista «Escrita» enseña primero una
   semilla, así que la espera hasta ver algo es menor que esa mediana. ΔE no
   mejora: buscar más candidatos encuentra otros mejor alineados con el dibujo,
   no otros de menor energía. De 52 a 60 átomos no se midió.

## Coste

El criterio multiplica por tres el muestreo del conformador. Medido con el
producto final sobre las 167: media 1,7 s para 20 átomos o menos, 5,7 s para
21–30 (la franja más común) y 3,9 s para 31–45; máximo 16 s (4-20, 30 átomos).
Antes, con una semilla y el mismo recorte, la misma franja tenía media 1,3 s y máximo 2,3 s. Es el precio de una cifra estable.

## Reproducir

    python medir_desajuste.py <carpeta>     # moleculas.jsonl, poses.jsonl (lento)
    python convergencia.py <carpeta>        # convergencia.jsonl (lento)
    python validar_abstencion.py <carpeta>  # validación del producto final
    python analizar_desajuste.py <carpeta>  # cuantiles, cortes y robustez

Ejecutar con el Python embebido (`D:\moldesign-build\python-embed\python.exe`),
con RDKit y el backend en el árbol del worktree. Los scripts leen los paneles de
`scripts/artifacts_science` sin escribir en ellos.
