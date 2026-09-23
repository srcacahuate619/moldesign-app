# FEP-02-PDBBIND

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

La integridad del receptor en PDBBind completo (huecos de cadena, sitio entre cadenas, metales, aguas) es comparable a la de los 203 de molflex (83/203 documentables para FEP)

## Protocolo

Referencia: `scripts/analisis_fep_pdbbind.py 02 sobre el script sellado analisis_fep02_receptor.py sin modificar, universo data/pdbbind, contenedor moldesign-science del servidor 192.168.1.64, 3 procesos; réplica previa sobre los 203 contra FEP-02/metrics.json`

## Gate

medición sin gate: se informa la fracción documentable para FEP con los criterios sellados

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `codex/release-hygiene`, commit `52b3768704b39347684a9269b41d380691c72d1d`, dirty=True

## Estado

- Creado: 2026-09-22T22:21:11.903445+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-09-23T02:55:46.932112+00:00)
- Finalizado: 2026-09-23T02:55:47.122305+00:00
- Razón de la decisión: La hipotesis se sostiene: la integridad del receptor en PDBBind es comparable a la de los 203 de molflex. Documentables para FEP 1543/3887 (39.7%) frente a 83/203 (40.9%); con huecos de cadena 43.1% frente a 42.4%; sitio entre cadenas 938/3887 (24.1%) frente a 43/203 (21.2%); con metales 819/3887 (21.1%) frente a 52/203 (25.6%); aguas en el sitio, mediana 11 frente a 10. Es decir: ampliar el universo no mejora la preparacion del receptor; seis de cada diez sistemas necesitan una decision declarada sobre huecos, cadenas, metales o aguas antes de un calculo FEP. Replica previa identica al sello complejo por complejo (203/203). Limitacion principal: 1438 de las 5325 entradas (27%) de la copia local de PDBBind no traen _protein.pdb; el universo efectivo es 3887 y no se ha comprobado que los ausentes sean aleatorios. Solo 2 complejos con cofactores: PDBBind limpia los heteroatomos del receptor (lo documento REC-12), asi que un cofactor ausente es invisible aqui.
- Hashes de assets: 7 archivo(s) con SHA-256

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
