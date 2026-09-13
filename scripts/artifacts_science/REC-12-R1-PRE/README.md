# REC-12-R1-PRE

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

La entrada original de RCSB si contiene los heteroatomos que PDBBind elimina, asi que permite medir lo que REC-12 no pudo: si algun receptor del programa tiene el sitio incompleto porque le falta un cofactor no metalico -un NAD, un FAD, un hemo-. REC-12 establecio que el instrumento estaba ciego, no que no hubiera nada que ver.

## Protocolo

Referencia: `Cambio de UNA sola variable frente a REC-12: la fuente de la estructura original pasa de data/pdbbind/<pid>/<pid>_protein.pdb -limpiado por PDBBind- a la entrada de RCSB, https://files.rcsb.org/download/<pid>.pdb. Cohorte: los 116 de MF-13, la misma. El analisis NO se reescribe: scripts/run_rec12r1_cofactores_rcsb.py IMPORTA el modulo sellado scripts/analisis_rec12_cofactores.py y reutiliza sus funciones _hetatm, _todos y _cerca y sus constantes R_SITIO=8.0, TOL=0.5, METALES y AGUAS, como exige el docs/49 seccion 17 -un artefacto sellado se extiende por composicion, nunca se edita-. Por complejo se cuentan los atomos HETATM que no son agua ni metal, que caen a <=8.0 A de un atomo pesado del ligando cristalografico y que no solapan con el propio ligando dentro de 0.5 A; y se marca cuantos de ellos SOBREVIVEN en rec.pdbqt, el receptor preparado que consume todo el programa. AMPLIACION DECLARADA ANTES DE EJECUTAR: sobre la entrada cruda aparecen aditivos de cristalizacion -glicerol, sulfato, PEG, MPD- que en el archivo limpiado no existian, y contarlos como cofactores inflaria el inventario. Por eso la lista ADITIVOS queda escrita en el script ANTES de correr, con 51 especies, y se reportan DOS cuentas por complejo: la bruta y la que excluye aditivos. El gate se lee sobre la segunda. Una especie que no este en la lista cuenta como cofactor, no como aditivo. Sin computo de docking. Contenedor moldesign-lab del servidor, que es donde hay red.`

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

- Creado: 2026-08-22T21:44:50.504822+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-08-22T21:44:51.857035+00:00)
- Finalizado: 2026-08-22T21:44:52.071802+00:00
- Razón de la decisión: Prerregistro sellado ANTES de ejecutar, con el hash del script nuevo y el del modulo sellado de REC-12 que reutiliza. Existe porque REC-12 dejo escrita su propia deuda con el coste: 116 descargas y el mismo analisis sin tocar, siendo el bloqueo de datos y no de metodo. Se declara antes de correr la unica decision de diseno que el cambio de fuente introduce y que podria discutirse despues: la entrada cruda de RCSB trae aditivos de cristalizacion que el archivo limpiado de PDBBind no tenia, asi que la lista ADITIVOS se congela aqui con 51 especies y se reportan las dos cuentas, bruta y neta, leyendo el gate sobre la neta. Se declara tambien que la lectura (3) -ningun receptor pierde cofactores- es un desenlace legitimo y NO un fracaso: cerraria por medicion un punto ciego que hoy solo se puede afirmar por suposicion. Y se prohibe de antemano el error de interpretacion mas probable, que es leer 'hay un cofactor cerca' como 'el sitio lo necesita'.
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
