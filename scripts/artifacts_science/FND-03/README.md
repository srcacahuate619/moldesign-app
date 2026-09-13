# FND-03

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

El baseline es estable entre ejecuciones: la varianza por semilla de Vina es pequena frente a los efectos medidos por el programa

## Protocolo

Referencia: `FND-03/README; contenedor moldesign-lab; 48 complejos x 5 semillas (42-46), exh=8, mismo conformero que MF-25 para que la comparacion sea directa`

## Gate

medicion de control de ruido; se reporta sd, rango y estabilidad del veredicto <=2 A

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `6bae87c3cda6de687a37b19f2b7dd219cd53e053`, dirty=True

## Estado

- Creado: 2026-08-19T03:52:53.009329+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-08-19T03:52:53.864648+00:00)
- Finalizado: 2026-08-19T03:52:54.062796+00:00
- Razón de la decisión: P0 declarado desde el inicio del programa y sin artefacto hasta hoy; era el hueco que la auditoria adversarial MF-32 identifico como el mas grave. Resultado: sd mediana 0.283 A en COLOCACION y 0.011 A en CONTROL. El error estandar de la mediana sobre 33 complejos es 0.049 A, de modo que los efectos del programa -MF-08 -0.82, MF-02F -0.79, MF-25 -0.784- son 15.8x ese error y SOBREVIVEN al control de ruido a nivel agregado. Pero la distribucion es muy asimetrica: p75 = 0.962 A, p90 = 1.422 A, rango maximo 4.022 A, y 14 de 33 complejos superan sd 0.5 A. Consecuencia doble y de signo opuesto: (a) ningun complejo cambia su veredicto <=2 A entre semillas, asi que las conclusiones binarias del programa -"3 de 33", "0 conversiones"- son estables y no artefactos de la semilla 42; (b) con rangos de hasta 4 A, cualquier afirmacion sobre un complejo INDIVIDUAL basada en una sola corrida es poco fiable, lo que obliga a que la confianza por complejo de FEP-04 incorpore repeticiones. En CONTROL la sd es 25x menor: donde el paisaje coopera Vina es casi determinista, donde no, tira los dados.
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
