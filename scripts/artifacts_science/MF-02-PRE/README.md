# MF-02-PRE

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

La falta de pose buena en 38 de 116 complejos de train se descompone en techo conformacional (el ensemble ETKDG nunca tuvo la conformacion bioactiva) y fallo de aplicacion/busqueda del generador; medirlos por separado decide donde esta la palanca

## Protocolo

Referencia: `MF-02-PRE/PREREGISTRO.md refina MF-02 del doc 49 seccion 8; MF-02A ejecutado y declarado como condicion de partida (precedente REC-07 seccion 6); MF-02A-EXT en contenedor Ubuntu; MF-02B con Vina local`

## Gate

MF-02A y MF-02A-EXT son mediciones sin gates. MF-02B: G1 validez >=95%, G2 recuperacion >=10 de 38 con A8, G3 no regresion de la union, G4 determinismo, G5 coste descriptivo

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `99b630cbf1723ef7b616dd6b89d15b37d0345c37`, dirty=True

## Estado

- Creado: 2026-08-17T22:36:05.090540+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-08-17T22:36:05.777946+00:00)
- Finalizado: 2026-08-17T22:36:28.123755+00:00
- Razón de la decisión: Prerregistro maestro sellado antes de ejecutar MF-02A-EXT y MF-02B. Declara como condicion de partida dos mediciones ya hechas: (1) la descomposicion obligatoria del doc 49 seccion 9, calculada por primera vez — cobertura del oraculo 67.2% en train y 87.2% en test, precision condicional 61.5% y 61.0%, de modo que toda la diferencia de Top-1 entre train y test la explica el generador y no el selector, y en 38 de 116 complejos no existe pose que seleccionar; (2) MF-02A, el techo conformacional del ensemble ETKDG, que satura entre 60 y 90 conformeros: pasar de 30 a 150 compra 2.6 puntos, y de los 38 sin cobertura 32 YA tienen la conformacion disponible con n_conf=30, solo 1 se rescata con 150 y 5 tienen techo duro. Ademas el grupo sin cobertura tiene MEJOR disponibilidad conformacional que el cubierto (84% vs 74%): la disponibilidad conformacional no discrimina. Tercera condicion declarada: MolFlex solo se aplico a 13 de los 116 complejos, y en el caso de calibracion 1nki —listado sin cobertura, mejor pose del dataset 2.067 A— el pipeline congelado entrega hoy 0.199 A en 6.4 s. Queda prohibido concluir del eje conformacional nada sobre el selector y usar la disponibilidad conformacional como filtro de cohortes futuras sin declararlo.
- Hashes de dataset: 1 archivo(s) con SHA-256
- Hashes de binarios: 1 archivo(s) con SHA-256
- Hashes de assets: 6 archivo(s) con SHA-256

## Mantenimiento del sello

- 2026-08-17T22:38:54.204477+00:00: `scripts/run_mf02a_conf_ceiling.py` `6be14e7f→b7de78ec` — Se anadio el flag --all-pdbbind al runner de MF-02A para poder correr la cohorte extendida MF-02A-EXT declarada en el PRE seccion 4. No cambia el metodo ni ningun criterio: mismo ensemble ETKDG seed 42 prune 0.4, mismo RMSD alineado GetBestRMS, misma curva acumulada; solo cambia de donde se lee la lista de pids. (commit a09b770c206bf8ef5d34df55814340e1c50e397b)

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
