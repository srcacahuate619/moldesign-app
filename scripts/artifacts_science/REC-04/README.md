# REC-04

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

El pipeline toma decisiones de protonacion en silencio, y eso es la causa numero uno de fallo en un paquete FEP+

## Protocolo

Referencia: `auditoria sin docking sobre los 116 de train: hidrogenos del receptor, residuos titulables en el sitio, carga formal del ligando y grupos ionizables por SMARTS`

## Gate

auditoria sin gates; dimensiona el hueco, no lo corrige

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `6bae87c3cda6de687a37b19f2b7dd219cd53e053`, dirty=True

## Estado

- Creado: 2026-08-19T03:53:15.751082+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-08-19T03:53:16.521290+00:00)
- Finalizado: 2026-08-19T03:53:16.734048+00:00
- Razón de la decisión: Parte sin computo de REC-04 e insumo de FEP-01/FEP-02. Hallazgo de partida: el provenance del pipeline declara receptor.protonation = "pdb_original", es decir NO se toma ninguna decision de protonacion, se hereda la del fichero de PDBBind. Receptor mejor de lo temido: los 116 traen hidrogenos y solo 17 tienen una histidina en el sitio (mediana de titulables en sitio: 1). Ligando: 87 de 116 tienen grupo ionizable y 64 llegan con carga formal 0 pese a contener acidos carboxilicos, aminas o amidinas que a pH 7.4 estarian ionizados. Mas frecuentes: amina secundaria (42), acido carboxilico (33), amina primaria (31), fosfato/sulfato (17), amidina/guanidina (16). Para docking con Vina es casi inocuo -su funcion apenas ve los hidrogenos-; para FEP+ es descalificante, porque cambia la carga neta del sistema. Limitacion: los SMARTS de ionizables son heuristica gruesa, no un predictor de pKa; los 64 son CANDIDATOS a revision, no errores confirmados. Y no se mide el efecto sobre el ranking: eso es REC-04 completo y exige re-dockear.
- Hashes de assets: 1 archivo(s) con SHA-256

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
