# MF-29-EMP-EXT-PRE

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

1mmr y 1nm6 no fallaron en el brazo masivo de MF-29-EMP: expiraron. Con un plazo suficiente completan sus tres semillas a exh=512 y la cohorte queda en 50 de 50.

## Protocolo

Referencia: `Extension de cobertura de MF-29-EMP, no re-sellado. Protocolo IDENTICO al brazo masivo de MF-29-EMP -conf0.flex.pdbqt, mismo receptor, caja 25 A, num_modes 9, exh=512, semillas {42,7,13}, --cpu 1- salvo que el timeout deja de ser la constante 14400 en duro y pasa a parametro, con 72000 s por defecto. El brazo de produccion NO se recomputa: se reusan los valores ya medidos en MF-29-EMP (1mmr -6.608, 1nm6 -8.724). Contenedor moldesign-lab del servidor. Script: scripts/run_mf29empext_recuperar_expirados.py.`

## Gate

Union de los 48 ya leidos mas los recuperados, con los umbrales de MF-29-EMP SIN TOCAR: f = fraccion donde min(exh=512) < min(exh=8) - 0.10; >=0.30 BUSQUEDA, <0.10 OBJETIVO, intermedio MIXTO. CASO DE BORDE DECLARADO ANTES DE CORRER, que es la razon de escribir este prerregistro: hoy son 3 de 48 = 0.0625; si ninguno mejora 3/50 = 0.0600 OBJETIVO; si uno mejora 4/50 = 0.0800 OBJETIVO; si los DOS mejoran 5/50 = 0.1000 y eso es MIXTO, porque la regla dice < 0.10 para OBJETIVO y 0.1000 no es menor que 0.10. Ese tercer desenlace CAMBIARIA la lectura de MF-29-EMP y queda escrito antes de mirar. PROHIBIDO: mover el umbral de 0.10 si cae el caso de borde; re-sellar MF-29-EMP, que queda leido sobre 48 con su limitacion declarada; leer nada de esto como certificado, porque MF-29 sigue ABIERTO.

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `78861c5b5c0b9722effe6a2cba123cb425bb5a72`, dirty=True

## Estado

- Creado: 2026-08-20T20:02:02.456529+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-08-20T20:02:05.035081+00:00)
- Finalizado: 2026-08-20T20:02:05.544192+00:00
- Razón de la decisión: Prerregistro sellado ANTES de ejecutar, con el hash del script. Existe por una sola razon: el caso de borde. Recuperar dos complejos de una cohorte de 50 parece trivial, pero con 3 de 48 = 0.0625 basta con que los DOS mejoren para dar 5 de 50 = 0.1000, y la regla de MF-29-EMP dice < 0.10 para OBJETIVO, asi que 0.1000 cae en MIXTO y cambiaria una lectura ya sellada. Escribirlo antes de mirar es lo unico que impide discutir el umbral despues. La probabilidad a priori es baja -3 de 48 mejoraron y la ganancia maxima de toda la cohorte es 0.282- pero no es cero. Se declara ademas que esto NO re-sella MF-29-EMP: aquel queda leido sobre 48 con su limitacion declarada, y esta es una extension con registro propio, como REC-08-EXT o FEP-02-EXT. El unico cambio de protocolo es el plazo, que pasa de constante en duro a parametro; la justificacion esta medida en el failures.jsonl de MF-29-EMP -43200.4 y 43200.6 s, tres veces 14400- y en que el brazo de produccion de estos dos tardo 569 y 736 s por semilla a exh=8, unas diez veces la media de la cohorte.
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
