# MF-02F

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

En MolFlex cada conformero es una corrida de docking independiente, de modo que n_conf es tambien el numero de reinicios de busqueda; subir de K30 a K90 debe recuperar complejos cuyo fallo es de colocacion

## Protocolo

Referencia: `MF-02F-PRE sellado (f31823c); prefijos anidados de un unico ensemble de 90; K30 = material sellado de MF-02D`

## Gate

G1 validez >=95%, G2 K90 recupera >=3 de 33 sobre K30 (umbral derivado de D-MF-HARD-CURVE), G3 saturacion informativa, G5 anidamiento exacto

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `6faec4dc2455a0adc16bf510b633c7a90ab3a5d5`, dirty=True

## Estado

- Creado: 2026-08-18T06:33:16.134904+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-08-18T06:33:16.967739+00:00)
- Finalizado: 2026-08-18T06:33:36.358505+00:00
- Razón de la decisión: Pasa G2 por el MINIMO EXACTO: K90 recupera 3 de los 33 dominados por colocacion y el gate preregistrado exigia 3. Un solo complejo menos habria sido NO_GO, y con n=3 sobre 33 el intervalo de confianza no soporta ninguna afirmacion de tamano de efecto. Tres advertencias que acompanan al GO: (1) K30=0/33 es TAUTOLOGICO porque la cohorte se definio como los complejos que fallan con la configuracion base, mismo defecto que en MF-08 y arrastrado al reutilizar la cohorte; (2) el dosis-respuesta no es suave: duplicar de 29 a 58 conformeros no recupero NADA y movio la mediana 0.08 A, mientras pasar de 58 a 86 recupero 3 y la movio 0.70 A, y con estos n no se distingue un mecanismo con umbral del ruido de muestreo; (3) el coste se duplica (601 s por complejo) para recuperar el 9 por ciento de una cohorte dificil. Los conjuntos recuperados por MF-08 (1d7i, 1ew9, 1l83) y por MF-02F (1ela, 1fkg, 1mu8) son DISJUNTOS, pero eso NO es evidencia de complementariedad: la probabilidad de que dos conjuntos de 3 extraidos de 33 sean disjuntos por azar es 0.744, de modo que el solapamiento vacio es el resultado esperado bajo independencia. Sumarlos a 6 esta ademas prohibido por el prerregistro. La convergencia si es informativa: dos intervenciones ortogonales sobre la misma cohorte mejoran la mediana del oraculo 0.82 y 0.79 A respectivamente y ambas convierten exactamente 3; las poses se quedan en torno a 3 A y necesitan bajar de 2.0. Restringir la geometria y triplicar el presupuesto de muestreo chocan contra el mismo techo, lo que apunta a que el factor limitante no es la caja ni el numero de intentos, sino la funcion de puntuacion o el espacio que el generador explora. Este GO NO justifica subir K a 90 en produccion.
- Hashes de dataset: 2 archivo(s) con SHA-256
- Hashes de binarios: 1 archivo(s) con SHA-256
- Hashes de assets: 7 archivo(s) con SHA-256

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
