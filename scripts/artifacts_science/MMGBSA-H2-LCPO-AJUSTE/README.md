# MMGBSA-H2-LCPO-AJUSTE

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

Con el radio de Bondi fijo (Br 1.85, I 1.98 A), reajustar por minimos cuadrados los coeficientes LCPO por elemento, solo con los atomos de entrenamiento de MMGBSA-PARTICIONES-BRI-V1, aproxima la SASA exacta de Br y de I dentro del error de fondo en validacion y en prueba, con prediccion estable entre remuestreos (H2); y lo que se aprende no depende de haber visto los mismos scaffolds (H10).

## Protocolo

Referencia: `backend/audits/lcpo_bri_h2.py: etapa bases (terminos LCPO por atomo con P unitarios sobre las topologias de MMGBSA-H1, SASA exacta a 50000 puntos; guardian: con los P del Cl publicado reconstruye el area de H1 a 5e-5 A2) y etapa ajustar. Dos brazos: completo (P1-P4) y reducido (P1, P2; P3 y P4 del Cl publicado); por elemento se elige en validacion el reducido salvo que el completo baje la mediana de validacion mas de 0.5 A2; la prueba solo confirma. Cambio declarado respecto del documento: el criterio CV<20% en cada coeficiente se sustituye por CV(P1)<20% y DE bootstrap del area predicha <=1 A2, porque en un piloto SOLO de entrenamiento los terminos estan casi alineados (numero de condicion ~1e4; CV de P3 94% en Br y 997% en I) y con un objetivo sintetico sin ruido el CV de P3 del I sigue en 303%.`

## Gate

Por elemento (Br, I), para el brazo elegido en validacion, en validacion y en prueba: mediana |error| <= 2.81 A2, p90 <= 7.25 A2, IC95 bootstrap por scaffold del error medio con signo dentro de +-2.81 A2, CV bootstrap de P1 < 20% (1000 remuestreos de grupos de entrenamiento) y mediana de la DE bootstrap del area predicha en validacion <= 1.0 A2. Menos de 5 atomos: INDETERMINADO. GO si los cuatro casos pasan; NO_GO si alguno falla; INCONCLUSIVE si alguno es indeterminado sin fallos. H10, veredicto aparte: mediana de validacion por scaffold <= la de una particion aleatoria por molecula (semilla sellada, 60/20/20) + 1.0 A2.

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 20260923
- Git: rama `codex/release-hygiene`, commit `30df834bc9fe85e8978be5159452220335627019`, dirty=True

## Estado

- Creado: 2026-09-23T18:31:10.510228+00:00
- Status: finished
- Decisión: NO_GO
- Sellado: sí (2026-09-23T18:32:51.181913+00:00)
- Finalizado: 2026-09-23T18:32:51.350946+00:00
- Razón de la decisión: NO_GO: 2 de 4 casos fallan. Br (brazo reducido elegido en validacion; P1 0.962, P2 -0.391, casi los del Cl publicado): validacion PASA (mediana 0.94, p90 4.85, IC95 del sesgo [-2.57,-0.46], CV P1 1.9%, DE de prediccion 0.64 A2) y prueba FALLA (mediana 2.96, p90 9.70, IC95 [-1.60,3.98]); la cola de prueba aparece con cualquier juego de coeficientes (H1: p90 9.44; completo: 9.83), asi que no la resuelve reajustar P1-P4. I (brazo completo elegido: el reducido daba mediana de validacion 5.91): prueba PASA (mediana 1.83, p90 4.04, IC95 [-2.68,0.53]) y validacion FALLA solo por el sesgo (IC95 [-3.07,0.66], 6 atomos). H10: Br PASA (validacion por scaffold 0.94 frente a 1.70 aleatoria); I FALLA por 0.05 A2 sobre el margen (2.59 frente a 1.54, 8 atomos). Los coeficientes sueltos no estan identificados (CV de P3 del I 1402%), la prediccion si (DE <= 0.74 A2). Siguiente: diagnostico exploratorio de la cola del Br, sin reusar la prueba para elegir nada.
- Hashes de assets: 10 archivo(s) con SHA-256

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
