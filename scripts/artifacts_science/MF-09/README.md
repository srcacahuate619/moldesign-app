# MF-09

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

Tras agotar las palancas geometricas, separar las dos causas del fallo de colocacion: si entre todas las poses generadas no existe ninguna a <=2 A el problema es de muestreo y ningun selector puede arreglarlo; si existe pero el score no la elige, hay margen de seleccion

## Protocolo

Referencia: `Medicion sobre el material sellado de MF-02D + MF-02F, sin computo nuevo ni parametros libres; umbral 2.0 A y rmsd_pose_pocket heredados de la linea`

## Gate

Sin gates de aceptacion: es una medicion descriptiva

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `a9934a2008dd1909b4945d9ada5e1a2ed5851766`, dirty=True

## Estado

- Creado: 2026-08-18T06:41:50.204809+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-08-18T06:41:50.841527+00:00)
- Finalizado: 2026-08-18T06:41:51.007186+00:00
- Razón de la decisión: Medicion descriptiva sin gates de aceptacion, declarada como tal: lee el material sellado de MF-02D y MF-02F sin computo nuevo ni parametros libres. RESPUESTA: es MUESTREO, no puntuacion. En 30 de los 33 complejos dominados por colocacion NO EXISTE ninguna pose a <=2 A entre una mediana de 751 candidatas, de modo que ningun selector puede elegir algo que no esta; el top-1 por score acierta en 0 y solo 2 complejos aciertan mirando las 20 mejores. Eso cierra la linea geometrica: ni la caja, ni los reinicios, ni el score son el factor limitante en esa cohorte — el generador no visita la region correcta con 86 conformeros, 9 modos y tres tamanos de caja probados. HALLAZGO COLATERAL DE MAS VALOR: en el control cubierto la historia es la opuesta. Los 15 tienen pose buena, el top-1 por score acierta en 7 y el top-5 en 14, de modo que hay un MARGEN DE SELECCION de 8 de 15 complejos donde la pose correcta esta disponible y el score no la pone primera pero si entre las cinco primeras. El Spearman entre score y RMSD es 0.483 en el control frente a 0.186 en la cohorte dificil: el score ordena razonablemente donde hay senal y es casi ciego donde no. Esto es la descomposicion cobertura por precision condicional de la seccion 9 medida por primera vez A NIVEL DE POSE, y reparte el esfuerzo al reves de como venia haciendose: mejorar el generador donde falla y el selector donde hay material, en vez de medir al selector sobre complejos que el generador nunca cubrio. Incidencia registrada: la primera version del analisis leia solo el directorio de MF-02F y perdia la mitad de las poses; corregida, el oraculo mediano coincide exactamente con el que MF-02F reporto por su propia via, y esa coincidencia verifica la union.
- Hashes de dataset: 2 archivo(s) con SHA-256
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
