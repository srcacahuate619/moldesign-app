# Dónde guardan el pLDDT Boltz-2 y Chai-1: archivos reales (2026-11-14/15)

**Qué es.** Una verificación de formato, como la que se hizo con AlphaFold DB el 2026-10-09, y no un experimento sellado.
[`prediccion.py`](../../../backend/services/targets/prediccion.py) sólo lee el pLDDT de una fuente cuya convención se
haya comprobado con un archivo real, y hasta ahora no había ningún archivo de Boltz ni de Chai-1. Este acta reúne lo que
salió al generarlos en Colab y compararlos con el pLDDT que devuelve el propio modelo. **No cambia el producto**: lo que
haya que cambiar se decide aparte.

## Dónde está cada cosa

| Qué | Dónde |
|---|---|
| Cuaderno, análisis y lector del producto | [`scripts/colab_plddt/`](../../../scripts/colab_plddt/), con sus pruebas en [`test_colab_plddt.py`](../../../scripts/tests/test_colab_plddt.py) |
| Procedencia de cada ejecución: GPU, versiones, órdenes, semillas, SHA-256 de los pesos y sondas | [`procedencia_ejecucion_1.json`](procedencia_ejecucion_1.json) y [`procedencia_ejecucion_2.json`](procedencia_ejecucion_2.json) |
| Análisis con el criterio, estructura a estructura | [`analisis.json`](analisis.json) y su resumen [`CONVENCION.md`](CONVENCION.md) |
| Qué dice hoy el producto de cada archivo | [`linea_base_producto.json`](linea_base_producto.json) |
| Tamaño y SHA-256 de los 167 archivos del archivo completo (195 MB) | [`manifiesto.json`](manifiesto.json) |
| El archivo completo: CIF, PDB, npz, MSA, registros y el zip de la primera ejecución | `F:\Backups\moldesign-evidencia\2026-11-15-colab-plddt-boltz-chai\` (fuera del repositorio) |
| Recortes que usan las pruebas del backend (residuos 1-90 de un PDB de Boltz, un mmCIF de Boltz y uno de Chai-1), con sus hashes y los de sus originales | `backend/tests/data/receptores_propios/boltz_*`, `chai_*` y `boltz_chai_procedencia.json`, escritos por [`recortar_fixtures.py`](../../../scripts/colab_plddt/recortar_fixtures.py) |

Para comprobar que el archivo completo es el que se cita (código 0 si no falta, cambia ni sobra nada):

```
python-embed\python.exe -I scripts\colab_plddt\manifiesto_evidencia.py verificar F:\Backups\moldesign-evidencia\2026-11-15-colab-plddt-boltz-chai docs\auditorias\convencion-plddt-boltz-chai-2026-11-15\manifiesto.json
```

El `analisis.json` y el `CONVENCION.md` que hay **dentro** del archivo son los de la primera ejecución, porque en la
segunda la celda de análisis se cayó. Los de esta carpeta se regeneraron en local sobre el archivo, con el módulo de
`69626e13` (la huella va en `analisis.json → regenerado`).

## Las dos ejecuciones

| | Ejecución 1 | Ejecución 2 |
|---|---|---|
| Cuándo (UTC) | 2026-11-14 23:51 → 2026-11-15 00:03 | 2026-11-15 00:49 → 01:12 (pesos medidos); el análisis se cayó |
| GPU | NVIDIA L4, 23 034 MiB, controlador 580.82.07 | la misma |
| Boltz | 2.2.1 (la última de PyPI en ese momento), torch 2.15.0+cu132; 5 de 5 corridas (72–169 s) | no se repitió |
| Chai-1 | 0.6.1, torch 2.6.0+cu124; 0 de 3 corridas | 0.6.1 fijada; 3 de 3 corridas (248–615 s), 5 muestras cada una |
| Qué falló | pandas no pudo importar pyarrow 26.0.1 al guardar el MSA | la sonda mostró la causa: «pyarrow requires NumPy 2.0 or newer, found 1.26.4»; con `pyarrow<22` (21.0.0) funciona. Después, el análisis se cayó al redondear los booleanos de `scores.npz` (arreglado en `69626e13`) |

**Casos.** CDK2 humana (P24941, 298 aa), sin ligando y con el ligando de cdk2 del benchmark de OpenFF que envió
FEP-09-R1. NET humano (P23975, 617 aa), la misma proteína que el fixture de AlphaFold DB. Secuencias de UniProt 2026_04.
Semilla 42 y servidor MSA de ColabFold. La referencia `AF-P23975-F1-model_v6.cif` tiene el mismo SHA-256 que el original
del que salen los fixtures del producto.

## Criterio, fijado antes de ejecutar

Una convención queda verificada para un grupo (herramienta y formato) si se cumplen dos condiciones. El grupo tiene al
menos dos estructuras terminadas. Y en todas ellas un mismo campo del archivo reproduce el pLDDT del modelo (el
`plddt_*.npz` de Boltz y el tensor `plddt` de `run_inference` en Chai-1). Tiene que hacerlo con una sola escala y sin
superar el redondeo con que el archivo escribe el número. El control frente a AlphaFold DB no forma parte del criterio.

## Resultado

| Grupo | Estructuras | Campo que reproduce el pLDDT del modelo | Escala | Lo que no lo reproduce |
|---|---:|---|---|---|
| Boltz 2.2.1, mmCIF | 3 | `_ma_qa_metric_local` y el factor B, que es el mismo en todos los átomos del residuo | 0–100, 3 decimales | — |
| Boltz 2.2.1, PDB | 2 | el factor B, uno por residuo | 0–100, 2 decimales | — |
| Chai-1 0.6.1, mmCIF | 15 | la **media por residuo** del factor B, que va **por átomo** | 0–100, 3 decimales | `_ma_qa_metric_local` y el factor B del Cα: se apartan hasta 19 puntos |

- La diferencia máxima con el modelo es la del redondeo del archivo: 0,0005 con 3 decimales y 0,005 con 2.
- **Ligando.** En Boltz cada átomo lleva su pLDDT, y la fila del ligando en `_ma_qa_metric_local` es su media (93,960
  frente a 93,961). En Chai-1, el ligando no figura en `_ma_qa_metric_local`.
- **Control frente a AlphaFold DB (NET, 617 residuos).** ρ de Spearman = 0,74 con Boltz y 0,78–0,80 con las cinco
  muestras de Chai-1.
- **`aggregate_score` de Chai-1.** Sale 0,19 sin ligando y 0,93 con él, y en las 15 muestras coincide con
  0,2·pTM + 0,8·ipTM, con una diferencia máxima de 0,00006. Sin segunda cadena, ipTM vale 0, así que el 0,19 no indica una mala predicción: el pTM es de 0,96.

## Lo que declara cada archivo

| | Boltz 2.2.1 | Chai-1 0.6.1 |
|---|---|---|
| ¿Dice quién lo generó? | **No.** `_entry.id model`, título vacío y sin `_software` | **Sí.** `_struct.title 'Chai-1 predicted structure'` |
| Diccionario | ModelCIF 1.4.6 | ModelCIF 1.4.9 |
| Métrica local | `_ma_qa_metric` de tipo `pLDDT` y modo `local` | la misma |
| Nombre del ligando | `LIG1` en el mmCIF, `LIG` en el PDB | `LIG2` |
| PDB | **sin ninguna cabecera**: sólo ATOM, HETATM, CONECT y END | no lo escribe |

## Qué dice hoy el producto

Se pasaron todos los archivos por `prediccion.analizar`, el mismo código que lee una subida de receptor propio:

- **Los 18 mmCIF** (3 de Boltz y 15 de Chai-1) se leen como «ModelCIF»: el pLDDT se toma de `_ma_qa_metric_local`, en
  escala 0–100, y queda rotulado «convención de esta fuente sin verificar». La regla «pLDDT < 70 junto al sitio» se les
  aplica. **No es cierto que salgan «no disponible»**, como dicen AGENTS.md y el docstring de `prediccion.py`.
- **Los 2 PDB de Boltz** se dan por estructuras experimentales (NO_APLICA, «no declara método»): su pLDDT no se lee y la
  regla del sitio no salta nunca.
- **Con Chai-1, el producto lee el pLDDT del Cα**, que suele ser más alto que la media del residuo. Es la muestra 0 de cada
  caso:

| Caso | Diferencia Cα − media (mediana y máximo) | Residuos < 70 que ve el producto | Residuos < 70 según el modelo |
|---|---|---:|---:|
| CDK2 sin ligando | +1,0 y +18,0 | 9 | 21 |
| CDK2 con ligando | +0,7 y +19,1 | 3 | 9 |
| NET | +2,1 y +13,5 | 72 | 76 |

Cuál de las dos cifras debe usar la regla es una decisión científica, no un error de lectura. AlphaFold 2 define su pLDDT
por residuo como el lDDT del Cα predicho, y de ahí viene el umbral de 70; esa definición no se cotejó aquí con la fuente
primaria. El tensor por residuo de Chai-1, en cambio, es la media de todos los átomos.

## Límites

- Sólo dos proteínas, un ligando y una semilla. Las conclusiones valen para estas versiones exactas (Boltz 2.2.1 y
  chai_lab 0.6.1); otra versión puede escribir el archivo de otra forma.
- En la ejecución 2, el entorno de Chai-1 no es el que resolvió uv: se cambió a pyarrow 21.0.0 para poder guardar el
  MSA. Queda declarado en `procedencia_ejecucion_2.json → instalacion → chai → parquet`.
- Lo del PDB de Boltz sale de dos archivos. No se generó nada con AlphaFold 3.
- No se midió si la regla de 70 acierta. Ese experimento está propuesto y pendiente (S18 de SUPUESTOS-01).
