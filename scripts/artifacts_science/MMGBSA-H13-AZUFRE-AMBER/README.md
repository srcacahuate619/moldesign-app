# MMGBSA-H13-AZUFRE-AMBER

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

Reescribir las expresiones GBn2 de OpenMM 8.5.2 con las ramas de Amber egb.F90 (corte y cola de rgbmax=25 A, serie de Taylor para dij>4*sj -siempre para el S, cuyo radio apantallado es negativo-, integral cerrada en el resto y tope de 1/30 A^-1 del radio inverso) hace que OpenMM reproduzca a sander en GBn2 sin superficie, tambien con azufre, sin romper lo que ya coincidia.

## Protocolo

Referencia: `backend/audits/gbn2_azufre_amber_h13.py con apply_amber_gbn2_descreening de backend/services/chemistry/amber_compatibility.py, sobre las 55 topologias de lcpo_halogenos.py (12 con S) y dos peptidos ff14SB con Met y Cys construidos con tleap (ACE MET CYS NME; y uno de 17 residuos de 56 A de extension, que ejercita rgbmax). Servidor: OpenMM y sander (contenedor moldesign-science); esta maquina: OpenMM del runtime que se entrega sobre copias con el mismo SHA-256. Fuente de las ramas: AmberClassic src/msander/egb.F90 leido el 2026-09-23. Piloto previo de 5 casos (1c5n, 1e4h, 2weg y los dos peptidos) declarado: con la correccion pasan los 5; el brazo diagnostico sin rgbmax deja 4.1e-3 kcal/mol en el peptido largo.`

## Gate

GO si, con la correccion y rgbmax=25 A, todas las topologias de geometria posible (regla de MMGBSA-H5-R1) y los dos peptidos pasan en GBn2_no_SA frente a sander (residuo tras la conversion de constantes < 0.001 kcal/mol y fuerza convertida < 0.001 kcal/mol/A), no hay fallos de ejecucion, uno de los peptidos supera 25 A de extension, y OpenMM de Windows reproduce al de Linux con la correccion (< 1e-6) en todas las comparaciones con las mismas entradas. El brazo sin rgbmax es diagnostico y no entra en el gate. Cualquier otro fallo: NO_GO.

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `codex/release-hygiene`, commit `6ea4cecaaed8354637c045d85734b1e59cc7e4fb`, dirty=True

## Estado

- Creado: 2026-09-23T19:15:27.002838+00:00
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
