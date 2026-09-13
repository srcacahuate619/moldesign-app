# MF-29-EMP-EXT

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

1mmr y 1nm6 no fallaron en el brazo masivo de MF-29-EMP: expiraron. Con un plazo suficiente completan sus tres semillas a exh=512 y la cohorte queda en 50 de 50.

## Protocolo

Referencia: `Ver prerregistro sellado MF-29-EMP-EXT-PRE, anterior a esta corrida y con el hash del script. Extension de cobertura de MF-29-EMP, no re-sellado. Protocolo IDENTICO al brazo masivo de MF-29-EMP -conf0.flex.pdbqt, mismo receptor, caja 25 A, num_modes 9, exh=512, semillas {42,7,13}, --cpu 1- salvo que el timeout deja de ser la constante 14400 en duro y pasa a parametro, con 72000 s por defecto. El brazo de produccion NO se recomputa: se reusan los valores ya medidos en MF-29-EMP (1mmr -6.608, 1nm6 -8.724). Contenedor moldesign-lab del servidor. Script: scripts/run_mf29empext_recuperar_expirados.py.`

## Gate

Union de los 48 ya leidos mas los recuperados, con los umbrales de MF-29-EMP SIN TOCAR: f = fraccion donde min(exh=512) < min(exh=8) - 0.10; >=0.30 BUSQUEDA, <0.10 OBJETIVO, intermedio MIXTO. CASO DE BORDE DECLARADO ANTES DE CORRER, que es la razon de escribir este prerregistro: hoy son 3 de 48 = 0.0625; si ninguno mejora 3/50 = 0.0600 OBJETIVO; si uno mejora 4/50 = 0.0800 OBJETIVO; si los DOS mejoran 5/50 = 0.1000 y eso es MIXTO, porque la regla dice < 0.10 para OBJETIVO y 0.1000 no es menor que 0.10. Ese tercer desenlace CAMBIARIA la lectura de MF-29-EMP y queda escrito antes de mirar. PROHIBIDO: mover el umbral de 0.10 si cae el caso de borde; re-sellar MF-29-EMP, que queda leido sobre 48 con su limitacion declarada; leer nada de esto como certificado, porque MF-29 sigue ABIERTO.

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `3bb30935f8a23310f9b98311fc6d2395d285c720`, dirty=True

## Estado

- Creado: 2026-08-22T20:31:34.071008+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-08-22T20:32:07.250675+00:00)
- Finalizado: 2026-08-22T20:32:37.209452+00:00
- Razón de la decisión: Los dos complejos que expiraron en MF-29-EMP se recuperan con el plazo parametrizado a 72000 s: recuperados 2 de 2, ninguno sin lectura. Las seis corridas cayeron entre 33546.6 s (1mmr s42) y 51275.8 s (1nm6 s7), TODAS por encima del timeout antiguo de 14400 s en duro, lo que confirma medido lo que el prerregistro afirmaba: 1mmr y 1nm6 no fallaron, expiraron. 1mmr mejora -produccion -6.608 contra masivo -6.77, ganancia 0.162 por encima del ruido declarado de 0.10- y 1nm6 no -produccion -8.724 contra masivo -8.713, ganancia -0.011-. La union con los 48 de MF-29-EMP da 4 de 50 = 0.08, que por la regla heredada SIN TOCAR -<0.10 OBJETIVO- es OBJETIVO. El caso de borde que motivo escribir este prerregistro NO se materializo: habria hecho falta que los DOS mejorasen para dar 5 de 50 = 0.1000 y caer en MIXTO. La lectura de MF-29-EMP no cambia y aquel NO se re-sella: queda leido sobre 48 con su limitacion declarada, y esto es una extension con registro propio, como REC-08-EXT o FEP-02-EXT. GO porque el experimento entrego la cantidad primaria preregistrada sobre la cohorte completa, con el unico cambio de protocolo declarado antes -el plazo- y sin mover ningun umbral despues de mirar. Limites: el brazo de produccion se reuso sin recomputar, tal como se declaro; los tiempos son orientativos porque el servidor puede estar compartido; y esto no certifica optimalidad global, MF-29 sigue ABIERTO. Artefactos producidos en el contenedor del servidor y descargados con sha256 verificado contra el remoto; el hash del runner coincide con el sellado en MF-29-EMP-EXT-PRE tanto en local como en el servidor.
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
