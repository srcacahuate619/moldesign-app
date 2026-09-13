# MF-08

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

El fallo de cobertura esta dominado por colocacion; apretar la caja reduce el margen de deslizamiento del ligando dentro del bolsillo y debe recuperar poses, con la caja adaptativa por ligando como mejor brazo

## Protocolo

Referencia: `MF-08-PRE-R1 sellado (e6c551f); molflex congelado salvo BOX_SIZE parcheado dentro del worker; B25 reutiliza el material sellado de MF-02D`

## Gate

G1 validez >=95%, G2 B_ADAPT recupera >=7 de 33, G3 monotonia en el margen de deslizamiento, G4 B_ADAPT pierde <=1 del control

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `2cbd932fc94543a08b8886ba4281a19693c765f2`, dirty=True

## Estado

- Creado: 2026-08-18T04:39:22.444892+00:00
- Status: finished
- Decisión: NO_GO
- Sellado: sí (2026-08-18T04:39:23.306407+00:00)
- Finalizado: 2026-08-18T04:39:42.488816+00:00
- Razón de la decisión: Falla G2: la caja adaptativa recupera 3 de los 33 dominados por colocacion frente a los 7 exigidos, cuando la prediccion declarada era que dejaria el subsitio fuera en 21 de 33. Excluir el decoy era necesario pero no suficiente, y asi estaba dicho, pero la brecha entre lo abordable y lo convertido es mucho mayor de lo anticipado. DEFECTO DE DISENO QUE SE DECLARA: la cohorte se definio como los complejos que fallan bajo B25, de modo que B25=0/33 es TAUTOLOGICO y no una medicion, lo que invalida parcialmente el gate G3 de monotonia por incluir un punto fijo por construccion; debi excluir B25 del gate o definir la cohorte con un criterio independiente del brazo de referencia. La decision NO_GO no depende de ese defecto: G2 falla por si solo y no tiene sesgo de seleccion. RESULTADO LIMPIO sobre los tres brazos que no intervinieron en seleccionar la cohorte: la mediana del oraculo es monotona en el margen de deslizamiento -3.18 A con B_ADAPT (margen 2.83), 3.224 con B20 (3.62), 4.004 con B30 (8.6)-, de modo que el mecanismo EXISTE y va en la direccion predicha, mejorando 0.82 A de B30 a B_ADAPT, pero es insuficiente por un orden de magnitud: esas poses estan a 3.18 A y necesitan bajar de 2.0, y no hay caja menor que probar porque B_ADAPT ya es el minimo que contiene al ligando con margen de solvatacion. Dos hallazgos utiles para produccion: apretar la caja NO rompe nada (15/15 del control en los cuatro brazos, cero regresion) y es 23 por ciento mas barato (425 s frente a 554 s), aunque el ahorro solo es cobrable si antes se resuelve la precision del centro, porque REC-03 midio el top-1 de MolPocket a 8 A de mediana del ligando. Consecuencia: el fallo de colocacion no es espacio para deslizarse; queda MF-02F, que da mas intentos en vez de menos espacio.
- Hashes de dataset: 1 archivo(s) con SHA-256
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
