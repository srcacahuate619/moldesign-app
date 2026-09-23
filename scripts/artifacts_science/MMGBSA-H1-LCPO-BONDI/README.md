# MMGBSA-H1-LCPO-BONDI

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

Los coeficientes LCPO P1-P4 del Cl publicado (Weiser, Shenkin y Still 1999) con el radio de Bondi (Br 1.85 A, I 1.98 A), sin ningun ajuste, aproximan la SASA numericamente exacta de los atomos de Br y de I dentro del error de fondo de LCPO, sin sesgo mayor que ese error y sin empeorar a los atomos vecinos respecto del respaldo de Amber.

## Protocolo

Referencia: `backend/audits/lcpo_bri_h1.py (sha sellado en MMGBSA-PARTICIONES-BRI-V1) sobre los 121 ligandos de geometria posible de esa seleccion: parametrizar con AmberTools (GAFF2, cargas Gasteiger, mbondi3; la funcion de lcpo_halogenos.py sin modificar) en el contenedor moldesign-science, medir con OpenMM 8.5.2 y Shrake-Rupley a 50000 puntos por atomo, resumir por las particiones selladas. Brazos: H1 (Cl publicado + Bondi), respaldo de Amber C_sp2_2 (control negativo) y Cl publicado con r=1.8 (diagnostico). Piloto previo de 5 ligandos declarado en el docstring: llevo a reformular el criterio de vecinos como comparacion pareada (el documento decia 'no empeorar'); los criterios 1 y 2 no se tocaron.`

## Gate

Por separado para Br y para I, en validacion y en prueba, con el brazo H1: (1) mediana |error| <= 2.81 A2 y p90 <= 7.25 A2; (2) IC bootstrap 95% (1000 remuestreos de grupos de scaffold, semilla 20260923) del error medio con signo dentro de +-2.81 A2; (3) en los atomos pesados que solapan con un Br o un I, cota superior del IC95 de la media pareada |error H1| - |error respaldo Amber| <= +0.5 A2. Menos de 5 atomos de un elemento en una particion: INDETERMINADO. GO si los cuatro casos (Br/I x validacion/prueba) pasan; NO_GO si alguno falla; INCONCLUSIVE si alguno es indeterminado y ninguno falla.

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 20260923
- Git: rama `codex/release-hygiene`, commit `27b2917fca0963cff2520dc4be25507e59017a1d`, dirty=True

## Estado

- Creado: 2026-09-23T18:16:52.053578+00:00
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
