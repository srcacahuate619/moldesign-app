# FEP-08-CONTROL-POSITIVO

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

Control positivo del auditor de readiness: aplicadas sin modificar las funciones selladas de FEP-01 y FEP-02 al protein-ligand-benchmark de OpenFF (preparado por expertos para RBFE), (a) el receptor documentable de FEP-02 (sin huecos de numeracion y sitio en una sola cadena) es al menos 20 puntos mas frecuente que en PDBBind (39.7%, FEP-02-PDBBIND), porque depende de la preparacion; y (b) la fraccion de ligandos con un unico tautomero enumerable no se aleja mas de 15 puntos de la de PDBBind (21.6%, FEP-01-DECL), porque depende de la quimica y no de quien preparo la molecula.

## Protocolo

Referencia: `scripts\analisis_fep08_control_positivo.py sobre openforcefield\protein-ligand-benchmark (clon del commit fd88824f9114244f95a14b485e6d6c96c1de716d, datos CC BY 4.0, codigo MIT) en E;C:\Program Files\Git\MolDesign-science\openff-plb. Las funciones _analizar de analisis_fep01_integridad.py y analisis_fep02_receptor.py se cargan sin modificar y se les sustituye el directorio de datos por una copia con el formato de PDBBind (receptor; 01_protein\crd\protein.pdb; sitio definido con el primer ligando de 02_ligands\ligands.sdf; ligandos uno por uno). Declaracion de tautomeros con backend\chem\declaracion_tautomeros.py sobre la lectura de FEP-01 (MolFromMolFile). Sin atom mapping (no hay index_map). Prueba tecnica previa con --limite 1 (cdk2), que por contrato no lee el gate.`

## Gate

GO si (a) la fraccion de receptores documentables de OpenFF es >= 0.597 (39.7% + 20 puntos) y (b) la fraccion de ligandos RESUELTO_UNICO esta en [0.066, 0.366] (21.6% +- 15 puntos). NO_GO si falla cualquiera de las dos. Se informan siempre huecos, sitio entre cadenas, estereo indefinido y si el tautomero de los curadores coincide con el canonico de RDKit.

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 0
- Git: rama `codex/release-hygiene`, commit `0405b13edc1db9ccf240857eb4582579c14e75af`, dirty=True

## Estado

- Creado: 2026-09-23T23:44:07.679154+00:00
- Status: created
- Decisión: PENDING

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
