# MF-10

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

Una minimizacion local dentro del bolsillo con un force field bien parametrizado (amber14 + Sage 2.2.1 + cargas NAGL) acerca la pose dockeada a la conformacion bioactiva

## Protocolo

Referencia: `MF-10-PRE/PREREGISTRO.md; contenedor moldesign-lab; 878 poses top-20 por score de 48 complejos; proteina restringida k=100 kcal/mol/A2, ligando libre, 500 iteraciones`

## Gate

G1 capacidad, G2 >=95% con energia finita, G3 mediana de delta RMSD negativa, G4 >=5 poses de la banda 2-3 A cruzan el umbral

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `23ac6d11cfadfdbd1d98de59392ebdaa66539cee`, dirty=True

## Estado

- Creado: 2026-08-18T20:19:47.812518+00:00
- Status: finished
- Decisión: NO_GO
- Sellado: sí (2026-08-18T20:19:48.388835+00:00)
- Finalizado: 2026-08-18T20:19:48.523152+00:00
- Razón de la decisión: Cero complejos convertidos. Las 9 poses que cruzan 2.0 A pertenecen a 7 complejos que YA tenian una pose bajo el umbral antes de relajar, y 8 de las 9 son del estrato CONTROL. G2 falla (81.3%) por un fallo de PREPARACION concentrado en 9 complejos que fallaron 20/20 con el mismo error de plantilla de OpenMM en cortes de cadena; no informa sobre el campo de fuerza. G3 falla con mediana +0.007 A. La magnitud cierra el argumento: ninguna pose se mueve mas de 0.725 A y solo 11 de 714 pasan de 0.5 A, frente al ~1 A necesario. La prediccion declarada cuadro sin residuo: 67 poses en la banda, 3 perdidas por parametrizacion, 64 medidas. La merma de cohorte NO sesga hacia el NO_GO: los 8 complejos COLOCACION perdidos estaban mas lejos de convertir (4.450 A frente a 4.024 A). Auditoria previa al sello en AUDITORIA.md: seis riesgos descartados -incluida la consistencia de la metrica antes/despues, con discrepancia maxima de 0.0005 A- y dos controles ausentes ejecutados como MF-10-CAL, que confirman que el instrumento tenia resolucion (suelo 0.401 A) y que el minimizador estaba convergido (0.061 A de mejora al multiplicar el presupuesto por 20). Es la ultima palanca sin probar de la hipotesis original del maintainer, y responde que no.
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
