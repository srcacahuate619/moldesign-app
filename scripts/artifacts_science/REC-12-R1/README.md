# REC-12-R1

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

La entrada original de RCSB si contiene los heteroatomos que PDBBind elimina, asi que permite medir lo que REC-12 no pudo: si algun receptor del programa tiene el sitio incompleto porque le falta un cofactor no metalico -un NAD, un FAD, un hemo-. REC-12 establecio que el instrumento estaba ciego, no que no hubiera nada que ver.

## Protocolo

Referencia: `Ver prerregistro sellado REC-12-R1-PRE, anterior a esta corrida y con el hash de los dos scripts. Cambio de UNA sola variable frente a REC-12: la fuente de la estructura original pasa de data/pdbbind/<pid>/<pid>_protein.pdb -limpiado por PDBBind- a la entrada de RCSB, https://files.rcsb.org/download/<pid>.pdb. Cohorte: los 116 de MF-13, la misma. El analisis NO se reescribe: scripts/run_rec12r1_cofactores_rcsb.py IMPORTA el modulo sellado scripts/analisis_rec12_cofactores.py y reutiliza sus funciones _hetatm, _todos y _cerca y sus constantes R_SITIO=8.0, TOL=0.5, METALES y AGUAS, como exige el docs/49 seccion 17 -un artefacto sellado se extiende por composicion, nunca se edita-. Por complejo se cuentan los atomos HETATM que no son agua ni metal, que caen a <=8.0 A de un atomo pesado del ligando cristalografico y que no solapan con el propio ligando dentro de 0.5 A; y se marca cuantos de ellos SOBREVIVEN en rec.pdbqt, el receptor preparado que consume todo el programa. AMPLIACION DECLARADA ANTES DE EJECUTAR: sobre la entrada cruda aparecen aditivos de cristalizacion -glicerol, sulfato, PEG, MPD- que en el archivo limpiado no existian, y contarlos como cofactores inflaria el inventario. Por eso la lista ADITIVOS queda escrita en el script ANTES de correr, con 51 especies, y se reportan DOS cuentas por complejo: la bruta y la que excluye aditivos. El gate se lee sobre la segunda. Una especie que no este en la lista cuenta como cofactor, no como aditivo. Sin computo de docking. Contenedor moldesign-lab del servidor, que es donde hay red.`

## Gate

G1 DE VALIDEZ DE LA FUENTE, el mismo que fallo en REC-12 y con el mismo minimo: fraccion de complejos cuya estructura original contiene algun HETATM que no sea agua ni metal, en cualquier parte de la estructura; minimo 0.05. En REC-12 dio 0.0208 y por eso aquel inventario NO SE LEYO. TRES LECTURAS ESCRITAS ANTES DE MIRAR: (1) G1 falla => LA_FUENTE_TAMPOCO_SIRVE, el inventario no se lee y el punto ciego sigue abierto con otra fuente por encontrar; (2) G1 pasa y hay al menos un complejo con cofactor no aditivo en el sitio que rec.pdbqt NO conserva => HAY_RECEPTORES_INCOMPLETOS, con la lista nominal de pids, y es un defecto de especificacion MEDIDO, del mismo tipo que REC-08-EXT y REC-09 destaparon; (3) G1 pasa y cero complejos con cofactor perdido => NINGUN_RECEPTOR_PIERDE_COFACTORES, y el punto ciego queda cerrado POR MEDICION y no por suposicion, que es lo que hoy no se puede decir. SECUNDARIO descriptivo y SIN gate: de los cristales que REC-09 marco absurdos y que no tienen ninguna agua bloqueante -1d7i y 1ew9-, cuantos tienen un cofactor en el sitio. PROHIBIDO: leer la presencia de un cofactor cerca del sitio como prueba de que el sitio lo necesita; el experimento establece que el receptor preparado no lo tiene, no que le haga falta. PROHIBIDO cambiar ningun receptor ni re-sellar ningun artefacto a partir de esto: lo que autoriza es disenar REC-05 -ablacion por familia-, que hoy esta bloqueado justamente porque los cofactores son invisibles. PROHIBIDO tratar la unidad asimetrica depositada como la assembly biologica: esa cuestion la gobierna REC-08 y aqui no se toca. PROHIBIDO mover la lista ADITIVOS despues de ver el resultado.

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `cd0d4152e9c9bd683cde92dc2794d63a4d9cfe06`, dirty=True

## Estado

- Creado: 2026-08-22T21:48:31.053214+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-08-22T21:48:33.096233+00:00)
- Finalizado: 2026-08-22T21:48:33.332006+00:00
- Razón de la decisión: G1 DE VALIDEZ DE LA FUENTE PASA Y NO POR POCO: 115 de 116 = 0.9914, contra el 0.0208 con que fallo REC-12 sobre el _protein.pdb limpiado de PDBBind. Las 116 entradas de RCSB se descargaron sin una sola ausencia. Eso solo ya cierra lo que REC-12 dejo abierto: la pregunta ERA contestable y el instrumento estaba ciego, no vacio el objeto. LECTURA PREREGISTRADA: HAY_RECEPTORES_INCOMPLETOS, la rama (2). En 15 de 116 complejos hay al menos un HETATM que no es agua, ni metal, ni figura en la lista ADITIVOS congelada antes de correr, que cae a <=8.0 A del ligando cristalografico y que NO sobrevive en el rec.pdbqt que consume todo el programa: 1alw 1apv 1bty 1c5o 1c5p 1d7j 1dgm 1f4g 1fd0 1gwv 1hpx 1igb 1jao 1jaq 1lbk. EL 15 ES UNA COTA SUPERIOR, NO UN RECUENTO DE COFACTORES FUNCIONALES, y esto se declara aqui y no se corrige moviendo la lista, que el prerregistro prohibe expresamente. Al desglosar las especies: (a) NUCLEO ROBUSTO, 2 complejos con cofactor funcional de verdad: UDP en 1gwv y GSH -glutation- en 1lbk; (b) 11 complejos cuya especie es un ligando o inhibidor, no un cofactor -BEN, benzamidina, en 1bty 1c5o 1c5p; KNI, 41 atomos, en 1hpx; y ISA BUQ TP4 254 IPO 0D3 01S-, donde descartarlos en la preparacion puede ser lo CORRECTO si son segundas copias del propio ligando, cosa que este analisis no distingue; (c) 2 complejos cuya especie escapo a las listas por un hueco declarado: DMF -un disolvente- en 1apv, y CL -un cloruro- en 1dgm, que no esta en el conjunto METALES del modulo sellado de REC-12. La lectura de existencia se sostiene aunque se retiren (b) y (c): UDP y GSH bastan para que la rama (2) sea la correcta. SECUNDARIO PREREGISTRADO, respuesta limpia en negativo: de los 6 cristales que REC-09 marco absurdos, los dos que no tienen ninguna agua bloqueante -1d7i y 1ew9- tampoco tienen ningun cofactor en el sitio. Esta via NO los explica y la pregunta abierta de REC-09 sigue abierta. GO porque el gate se leyo tal como se escribio, sobre la cohorte completa y con la fuente que el prerregistro nombro, y porque entrega lo que autorizaba: la lista nominal con la que se puede disenar REC-05, hoy bloqueado precisamente porque los cofactores eran invisibles. PROHIBIDO, y se repite aqui: esto establece que el receptor preparado no tiene esas especies, NO que el sitio las necesite. No cambia ningun receptor ni re-sella ningun artefacto. Limite adicional: la entrada de RCSB es la unidad asimetrica depositada y no la assembly biologica, cuestion que gobierna REC-08. Ejecutado en el contenedor moldesign-lab del servidor; artefactos descargados con sha256 verificado contra el remoto, y los dos scripts coinciden byte a byte con lo sellado en REC-12-R1-PRE en local y en el servidor.
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
