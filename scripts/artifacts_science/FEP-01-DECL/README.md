# FEP-01-DECL

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

Declarar el tautomero con tres estados (RESUELTO_UNICO, MULTIESTADO_REQUERIDO, NO_RESUELTO; backend/chem/declaracion_tautomeros.py) sube la fraccion de ligandos listos de FEP-01 sobre los 203 complejos de molflex por encima del 80%, como predicen docs/50_ROADMAP.md (seccion 3) y AGENTS.md (de 19% a mas del 80%), si el criterio de tautomero pasa de 'un solo tautomero enumerable' a 'tautomero declarado' (estado distinto de NO_RESUELTO).

## Protocolo

Referencia: `scripts/analisis_fep01_declaracion.py. Para cada complejo de los per_complex sellados de FEP-01 (203) y FEP-01-PDBBIND (5325) se lee data/pdbbind/<pid>/<pid>_ligand.sdf con Chem.MolFromMolFile (la misma lectura que FEP-01) y se declara con declarar_tautomeros (RDKit, tautomerRemoveSp3Stereo=False, tope 32 como FEP-01). Estereoquimica y atom mapping se toman tal cual de los sellos, sin volver a medir. Listo = sin estereo indefinido, mapping biyectivo que cubre los pesados, y tautomero declarado. Se informa aparte cuantos listos lo son solo por MULTIESTADO_REQUERIDO (declarado no es resuelto) y, para PDBBind, la variante sin mapping (no hay index_map). Prueba tecnica previa con --limite 5, que por contrato no lee el gate. Maquina local, Python del sistema con RDKit 2025.09.6.`

## Gate

GO si en los 203 de FEP-01 la fraccion de listos con el criterio 'tautomero declarado' (con mapping) es >= 0.80. NO_GO si es menor. PDBBind se informa sin gate. La fraccion de listos solo por tautomero unico y la de listos solo por multiestado declarado se informan siempre, junto a la decision.

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 0
- Git: rama `codex/release-hygiene`, commit `60437c04a7cc64e0685ceac221b5ce4113bb22a9`, dirty=True

## Estado

- Creado: 2026-09-23T23:33:10.497030+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-09-23T23:39:52.203584+00:00)
- Finalizado: 2026-09-23T23:40:05.740910+00:00
- Razón de la decisión: GO por la letra del gate: en los 203 de FEP-01, 180 (88.7%) quedan listos con el criterio 'tautomero declarado' (umbral 80%), como predecia el roadmap. La lectura que importa es la descomposicion: solo 39 (19.2%, los mismos 39 del sello) tienen un unico tautomero; 141 estan listos SOLO porque su multiestado quedo declarado (varios candidatos, ninguno descartado con evidencia), y 22 siguen NO_RESUELTO porque la enumeracion llega al tope de 32 (los 164 ambiguos del sello son 142 multiestado + 22 no resueltos). La estereoquimica bloquea 1. Declarado no es resuelto: un paquete con varios tautomeros exige a quien calcula tratarlos todos, o elegir uno con evidencia que hoy no hay (sin modelo de poblaciones validado). Los multiestado tienen mediana de 4 candidatos (2 a 31). PDBBind, sin gate, sobre las 4641 entradas legibles del sello: 1003 unico, 3187 multiestado, 451 no resuelto; sin el criterio de mapping (no hay index_map) 4143 listos (89.3%), de ellos 985 por tautomero unico (21.2%) frente a 989 del sello: 4 cambian porque el sello uso el enumerador por defecto y aqui se conserva la estereoquimica sp3 (tautomerRemoveSp3Stereo=False); en los 203 coinciden 39/39. 0 fallos. Siguiente: un modelo energetico validado para descartar candidatos fuera de 2-3 kcal/mol, y que el paquete FEP-05 lleve todos los candidatos con su id.
- Hashes de assets: 8 archivo(s) con SHA-256

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
