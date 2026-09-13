# MF-08-PRE-R1

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

Lo que la caja recorta es MARGEN DE DESLIZAMIENTO del ligando dentro del bolsillo, no un sitio competidor lejano; por eso la cobertura debe ser monotona en ese margen y la caja adaptativa por ligando (dimension + 4 A) debe ser el mejor brazo

## Protocolo

Referencia: `MF-08-PRE-R1/PREREGISTRO.md; sustituye a MF-08-PRE sin ejecutar; brazo B_ADAPT tomado de moldesign-app/docs/propuestas_de_mejora.md seccion 3 (julio 2026, anterior a estos resultados)`

## Gate

G1 validez >=95%, G2 B_ADAPT recupera >=7 de 33, G3 monotonia B_ADAPT>=B20>=B25>=B30 en el margen de deslizamiento, G4 B_ADAPT pierde <=1 del control, G5 determinismo

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `ac242eec7e01597c472454d0a347aa69ca467383`, dirty=True

## Estado

- Creado: 2026-08-18T02:13:41.995210+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-08-18T02:13:42.990409+00:00)
- Finalizado: 2026-08-18T02:13:43.270753+00:00
- Razón de la decisión: Sustituye a MF-08-PRE antes de ejecutarlo. El brazo adaptativo sale de la biblioteca del proyecto original (moldesign-app/docs/propuestas_de_mejora.md seccion 3, julio 2026): el mismo criterio fisico que MF-08-PRE derivo de forma independiente para descartar la caja de 15 A, pero mejor operacionalizado como lado por ligando en vez de fijo. El orden temporal importa: el criterio es anterior a los resultados, asi que incorporarlo no es ajustar el diseno mirando el desenlace. B_ADAPT excluye el subsitio en 21 de 33 frente a 19 de B20, no deja ningun ligando fuera, y ademas los 4 complejos excluidos a priori por no caber en 20 A si caben. G3 gana poder al pasar de tres a cuatro puntos ordenados por una variable fisica continua, el margen de deslizamiento (2.83 < 3.62 < 6.12 < 8.6 A). Se reformula el mecanismo con honestidad: los desplazamientos medidos son de 3 a 6 A, que no es acoplarse en otro sitio sino deslizarse dentro del mismo bolsillo; y se registran dos hipotesis alternativas REFUTADAS con datos antes de ejecutar -cofactores ausentes (16% de fallos vs 29% de cubiertos) y copia simetrica en multimero (30% vs 41%)-.
- Hashes de dataset: 1 archivo(s) con SHA-256
- Hashes de binarios: 1 archivo(s) con SHA-256
- Hashes de assets: 4 archivo(s) con SHA-256

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
