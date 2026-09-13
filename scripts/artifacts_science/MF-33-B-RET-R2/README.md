# MF-33-B-RET-R2

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

El unico fallo de MF-33-B-RET-R1 fue ambiental y no quimico, asi que re-ejecutar ese solo dock con el protocolo identico completa la corrida y permite leer los gates que R1 dejo bloqueados. Si vuelve a fallar, la hipotesis es falsa: el fallo no era ambiental y el problema esta en el complejo o en el protocolo.

## Protocolo

Referencia: `Ver prerregistro sellado MF-33-B-RET-R2-PRE, anterior a esta corrida. Reparacion minima, una sola variable: se re-ejecuta UN complejo. scripts/run_mf33bret_r2.py IMPORTA scripts/run_mf33bret_r1.py -sellado como asset de MF-33-B-RET-R1- y reutiliza su funcion analizar, su _block y sus constantes EXH=8, NUM_MODES=9, SEED=42, BOX=25.0, UMBRAL_A=2.0, G1_TOL=0.001 y G1_MIN=0.95. El protocolo es identico POR CONSTRUCCION y no por copia, segun el docs/49 seccion 17. PASOS: (1) reusar VERBATIM los 47 checkpoints buenos de R1, registrando el sha256 de cada uno en el metrics; (2) re-ejecutar SOLO 1afl y sus 30 conformeros; (3) recalcular G0, G1 y los bloques con las MISMAS reglas selladas. No se toca ningun umbral, ninguna regla de lectura ni el artefacto R1, que queda sellado e intacto. El reuso de artefactos sellados de una corrida previa sin recomputarlos es el mismo patron que MF-29-EMP-EXT aplico con el brazo de produccion de MF-29-EMP. CONDICION DE EJECUCION declarada porque es la causa del fallo que se repara: la maquina debe estar en reposo. R1 murio por contencion con PoseBusters, pytest y generacion de conformeros corriendo encima. Verificado antes de lanzar: sin procesos vina, python ni pytest vivos, 17.2 GB de RAM libre de 31.9.`

## Gate

LOS GATES NO CAMBIAN Y NO PUEDEN CAMBIAR. Son los sellados en MF-33-B-RET-PRE y MF-33-B-RET-R1-PRE: G0 tecnico exige 48 de 48 complejos completos y CERO fallos; G1 exige que el oraculo ENSEMBLE reproduzca el rmsd_min del brazo B sellado de MF-33 dentro de 0.001 A en al menos el 95% de los complejos. Con G0 y G1 aprobados, McNemar exacto bilateral sobre top-1, top-5 y oraculo, y la lectura es: (1) LA_VENTAJA_LLEGA_AL_USUARIO si mejoran oraculo Y top-1 con p<0.05; (2) EL_CUELLO_SE_DESPLAZA_A_LA_SELECCION si mejora oraculo pero no top-1; (3) SIN_EFECTO_EN_LA_ENTREGA en los demas casos. Si G0 o G1 falla, NO_LEER_GATES_TECNICOS. ADVERTENCIA DE PROCEDENCIA, Y ES LA RAZON DE SER DE ESTE CAMPO: al diagnosticar el fallo de R1 se vieron sus bloques cientificos. ESTE R2 NO ES UNA CONFIRMACION CIEGA y queda PROHIBIDO presentarlo como tal en el paper o en cualquier material. Lo que sigue siendo ciego es la REGLA DE DECISION, escrita y sellada antes de todo esto; lo que se perdio es la ceguera sobre el desenlace, y se declara en vez de disimularse. UN SOLO INTENTO. Si 1afl vuelve a fallar, G0 vuelve a fallar, la lectura vuelve a ser NO_LEER_GATES_TECNICOS y NO habra un R3 por la via de repetir: haria falta un diseno distinto y un prerregistro nuevo que declare que cambio. Escribir esto antes es lo unico que impide que la reparacion degenere en repetir hasta que salga, que es la forma mas facil de fabricar un resultado sin darse cuenta. PROHIBIDO ademas: modificar, re-sellar o reinterpretar MF-33-B-RET-R1, que queda INCONCLUSIVE; reparar cualquier complejo que no sea 1afl; y tratar los 47 checkpoints reusados como si se hubieran recomputado.

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `codex/mejora-producto`, commit `8d69c5533ac20e01c74e73f1030341d1bc05e6fb`, dirty=True

## Estado

- Creado: 2026-08-23T07:18:17.147852+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-08-23T07:18:18.184024+00:00)
- Finalizado: 2026-08-23T07:18:18.357129+00:00
- Razón de la decisión: LOS DOS GATES PASAN. G0 tecnico: 48 de 48 complejos completos y CERO fallos. G1: 48 de 48 = 1.0000 contra un minimo de 0.95, o sea que el oraculo ENSEMBLE reproduce el rmsd_min del brazo B sellado de MF-33 dentro de 0.001 A en TODOS los complejos. LA HIPOTESIS DE LA REPARACION SE CONFIRMA. El fallo de R1 era ambiental: 1afl completo sus 30 conformeros con 267 poses y CERO fallos en 4432 s, frente a los 9095 s que tardo en R1 compitiendo con PoseBusters, pytest y generacion de conformeros en la misma maquina. La mitad de tiempo sin contencion. Un solo intento, como se declaro. LECTURA PREREGISTRADA: EL_CUELLO_SE_DESPLAZA_A_LA_SELECCION, la rama (2) de las tres escritas antes. Sobre los 48: el oraculo pasa de 26 a 41 -b=15, c=0, McNemar exacto p=6.1e-05, +31.25 pp-; el top-5 de 26 a 35 -b=9, c=0, p=0.0039, +18.75 pp-; y el top-1 de 20 a 24 -b=7, c=3, p=0.34375, +8.33 pp, NO SIGNIFICATIVO-. En COLOCACION el patron es el mismo y mas marcado: oraculo 12 a 26 (p=0.000122), top-5 12 a 21 (p=0.0039), top-1 9 a 14 (p=0.1797, no significativo). LA CIFRA QUE CUENTA LA HISTORIA es el margen de seleccion, o sea los complejos donde el brazo CONTIENE una pose correcta y no la entrega en top-1: pasa de 6 a 17 sobre los 48, y de 3 a 12 en COLOCACION. El ensemble casi TRIPLICA los casos en los que la respuesta esta ahi y el selector no la elige. QUE SIGNIFICA, Y ES LO QUE VA AL PAPER: la ventaja del ensemble es enorme en generacion -cero derrotas pareadas en oraculo y en top-5- y NO LLEGA con significacion a la unica pose que el usuario recibe. El ensemble no resuelve el problema: lo CONVIERTE de problema de generacion en problema de seleccion. Esa es la respuesta a la amenaza T1 del docs/52 sobre el brazo flexible, y contesta que la metrica de oraculo del programa sobreestima lo que el pipeline entrega. ADVERTENCIA DE PROCEDENCIA, DECLARADA ANTES DE CORRER Y QUE DEBE VIAJAR CON EL RESULTADO: este R2 NO ES CIEGO. Al diagnosticar el fallo de R1 se vieron sus bloques cientificos, que son los mismos numeros salvo por 1afl. Lo que si permanecio sellado e inamovible es la REGLA DE DECISION, escrita en MF-33-B-RET-PRE y MF-33-B-RET-R1-PRE antes de todo esto. Queda PROHIBIDO presentar este resultado como confirmacion ciega en el paper o en cualquier material. RETENCION: los 47 complejos reusados conservan su geometria cruda en MF-33-B-RET-R1, cuyo checkpoint por complejo esta hasheado uno a uno en el metrics de este artefacto; aqui solo viven los 30 PDBQT de 1afl, que es lo unico recomputado. Es el patron de reuso sin recomputo que MF-29-EMP-EXT establecio. GO porque el experimento entrego la cantidad primaria sobre la cohorte completa, con los dos gates aprobados y sin mover ningun umbral.
- Hashes de dataset: 2 archivo(s) con SHA-256
- Hashes de assets: 2 archivo(s) con SHA-256

## Flujo de trabajo

1. `init`: crea este directorio con `manifest.json` prellenado y skeletons vacíos.
2. Ejecutar el experimento: escribir `metrics.json`, `per_complex.jsonl` y `failures.jsonl`.
3. `validate`: verifica `manifest.json` contra `manifest.schema.json`.
4. `seal`: registra los SHA-256 de datasets/modelos/binarios/assets y congela el manifest.
5. `finish`: escribe la decisión (GO/NO_GO/INCONCLUSIVE), la razón y la duración.
6. `maintain`: documenta de forma auditada los assets sellados que cambian tras el sello.

Después del `seal`, `validate` falla si cualquier archivo sellado cambia o desaparece.

## Inmutabilidad post-seal

- No se permite volver a sellar un experimento ya sellado (protege el cegamiento FND-05).
- `finish` y `maintain` son las únicas operaciones que modifican `manifest.json` después del sellado.
- `maintain` solo actualiza `assets_hashes` y registra cada cambio en `seal_maintenance`; datasets/modelos/binarios son inmutables.
- El README.md regenerado por `seal`/`finish`/`maintain` es la excepción documentada a la regla anterior.
- Los artefactos de producción permanecen fuera de este árbol (docs/49, sección 17).

## Archivos

- `manifest.json`: registro único del experimento (config, hashes, código, ambiente, salida).
- `metrics.json`: métricas agregadas del experimento.
- `per_complex.jsonl`: una línea JSON por complejo evaluado.
- `failures.jsonl`: una línea JSON por fallo.
- `README.md`: este archivo.
