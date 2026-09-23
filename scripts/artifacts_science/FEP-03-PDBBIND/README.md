# FEP-03-PDBBIND

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

PDBBind completo contiene dianas con series congenéricas suficientes para una cohorte FEP (pocas dianas con muchos análogos), a diferencia de los 203 de molflex (91 parejas aptas en 18 dianas, grupo mayor de 23)

## Protocolo

Referencia: `scripts/analisis_fep_pdbbind.py 03: fase 1 con _sec_job/_kmers y umbrales del sellado analisis_fep03_congenericas.py (k-meros 8, Jaccard sobre el menor >= 0.90); fase 2 MCS RDKit con los mismos parámetros (timeout 10 s, ringMatchesRingOnly, completeRingsOnly, RemoveAllHs) repartido en shards de 2000 parejas que no se reescriben; umbrales declarados antes: cobertura MCS >= 0.70 y perturbación <= 10. Prefiltro exacto declarado antes de mirar: |n_a - n_b| > 10 no se calcula porque no puede ser apta; las medianas se informan sobre las evaluadas. Contenedor moldesign-science del servidor 192.168.1.64, 3 procesos, compartido con la VM de QA. Réplica previa sobre los 203 contra FEP-03/metrics.json`

## Gate

medición: se informan parejas aptas y dianas con serie; la elección de la cohorte congenérica es una decisión aparte y posterior

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `codex/release-hygiene`, commit `52b3768704b39347684a9269b41d380691c72d1d`, dirty=True

## Estado

- Creado: 2026-09-22T22:21:12.290262+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-09-23T06:31:56.074075+00:00)
- Finalizado: 2026-09-23T06:31:56.245393+00:00
- Razón de la decisión: La hipotesis se sostiene: PDBBind contiene series congenericas utilizables para FEP, a diferencia de los 203 de molflex. 3299 parejas aptas (cobertura MCS >= 0.70 y perturbacion <= 10, umbrales del sello) en 313 dianas, frente a 91 en 18; 28 dianas con 10 o mas ligandos conectados por parejas aptas y 12 con 20 o mas. Replica previa sobre los 203: resumen identico al sello y 486/487 parejas identicas; la que cambia (1ezq-1ksn, MCS 1 -> 27 atomos, ninguna apta) muestra que el MCS con timeout depende de la carga de la maquina. Sensibilidad declarada antes de correr: los 163 MCS cortados a 10 s se repitieron con 300 s; el MCS crecio en 47, 32 siguen cortados, 0 errores, y NINGUNA pareja cambio de veredicto (23 aptas antes y despues): el recuento no depende del timeout. Un primer intento de la sensibilidad fue invalido (timeout float, ArgumentError en las 163) y se conserva como evidencia. Limitaciones: cota superior por la agrupacion por k-meros (no distingue mutantes puntuales); universo efectivo 3887 de 5325 porque la copia local de PDBBind no trae _protein.pdb en 1438 entradas. Para elegir cohorte, las afinidades anadidas desde BindingDB al INDEX local estan emparejadas por diana y no sirven; con las de Fase A, la cohorte recomendada es galectina-3 (6qln-6qlu, 7 ligandos de un solo articulo, ChemMedChem 2019).
- Hashes de assets: 40 archivo(s) con SHA-256

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
