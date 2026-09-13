# MF-29-EMP-PRE

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

En complejos de <=6 torsiones el optimo que Vina alcanza a exhaustiveness=8 ES su optimo global. Si un presupuesto 64x encuentra scores estrictamente mejores, el fallo restante es de BUSQUEDA; si no los encuentra, el optimo global de la funcion no es la pose nativa y el fallo es de OBJETIVO.

## Protocolo

Referencia: `doc 49 seccion 20.11(b), METODO SUSTITUIDO: la jerarquia de Lasserre se declara NO IMPLEMENTABLE en este hardware (ver decision_rationale) y se sustituye por cota superior empirica del minimo global por presupuesto masivo. Cohorte: 48 complejos con n_torsiones<=6 de los 116 de MF-24. Brazos: exh=8 semillas {42,1,2,3,4} y exh=512 semillas {42,7,13}, num_modes=9, caja 25 A, receptor y caja identicos al docking v2. Tercer testigo REUSADO de MF-13 (score_cristal_local), sin recomputo.`

## Gate

DESCRIPTIVO, sin umbral de decision. Cantidad primaria: fraccion de complejos donde min(score exh=512) < min(score exh=8) - delta, con delta=0.10 kcal/mol declarado ANTES como ruido numerico. REGLA DE LECTURA PREREGISTRADA: >=0.30 => BUSQUEDA subotima incluso en baja dimension; <0.10 => la busqueda satura y el fallo restante es de OBJETIVO; 0.10-0.30 => MIXTO.

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `642f32466cd6cf422e8f99d2af550a360d30d754`, dirty=False

## Estado

- Creado: 2026-08-19T04:19:56.866053+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-08-20T20:16:26.619344+00:00)
- Finalizado: 2026-08-20T20:16:27.062327+00:00
- Razón de la decisión: Prerregistro de MF-29-EMP, sellado RETROACTIVAMENTE el 2026-08-20 al detectarse en el barrido del registro que habia quedado en status created y decision PENDING. Procedencia verificable y anterior a la corrida: su manifest.json se commiteo el 2026-08-19 a las 00:44 en 9117a17, y MF-29-EMP arranco despues y cerro el 2026-08-20 tras 34 h. Contenido sin modificar. IMPORTANTE PARA EL REGISTRO: al sellar MF-29-EMP se cito su docstring como prerregistro, porque este artefacto no se localizo entonces; el prerregistro formal es ESTE, y coincide con aquel en lo que decide -cantidad primaria, delta=0.10 declarado antes como ruido numerico, y la regla de lectura >=0.30 BUSQUEDA, <0.10 OBJETIVO, intermedio MIXTO-. La lectura sellada de MF-29-EMP no cambia: 3 de 48 = 0.0625 sigue siendo OBJETIVO bajo esta regla.
- Hashes de dataset: 1 archivo(s) con SHA-256
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
