# MF-29-EMP-COR

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

El deficit del testigo de MF-29-EMP es un artefacto de escala torsional: MF-13 puntuo el cristal como PDBQT RIGIDO (TORSDOF 0, sin penalizacion) y MF-29-EMP dockeo conf0.flex.pdbqt FLEXIBLE, y Vina divide la afinidad por (1 + w_rot * N_rot). Preparar el cristal con la MISMA flexibilidad debe eliminar el deficit o dejarlo por debajo del ruido.

## Protocolo

Referencia: `Ver prerregistro sellado MF-29-EMP-COR-PRE, anterior a esta corrida. Repite MF-13 cambiando UNA SOLA COSA: escribe el flex_str de molflex.escribir_pdbqt en vez del rigid_str. Mismo tipado de Meeko, mismo rec.pdbqt, misma caja de 25 A, misma semilla 42, mismo --score_only y --local_only con re-puntuacion de la pose relajada. Contenedor moldesign-lab del servidor con vina 1.2.7, el mismo de MF-13 y MF-29-EMP. Cohorte: los 48 con lectura en MF-29-EMP.`

## Gate

G1 TORSDOF del cristal flexible == el de conf0.flex.pdbqt en >=95%; G2 deriva mediana de --local_only <=2.0 A. PRIMARIA: f = fraccion donde score_cristal_local_FLEX < score_min(masivo) - 0.10. f<=0.30 ARTEFACTO DE ESCALA; f>=0.70 EL TESTIGO SOBREVIVE; intermedio MIXTO.

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `83079e9e5f67e1e912037345395e458cb6f91039`, dirty=True

## Estado

- Creado: 2026-08-20T19:40:20.293210+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-08-20T19:40:42.545312+00:00)
- Finalizado: 2026-08-20T19:40:42.897115+00:00
- Razón de la decisión: Lectura ARTEFACTO DE ESCALA por la regla preregistrada en MF-29-EMP-COR-PRE, sellada antes de correr. Los dos gates de validez pasan primero: G1 = 1.0, el TORSDOF del cristal flexible coincide con el de conf0.flex.pdbqt en los 48 de 48, asi que es la misma molecula preparada igual; G2 = 0.3425 A de deriva mediana del --local_only, practicamente identica a los 0.322 A que derivo el rigido en MF-13, asi que el relajado sigue siendo el cristal y no se fue a otro sitio. PRIMARIA: f = 4 de 48 = 0.0833, dentro de la banda <=0.30. El testigo de MF-29-EMP era un artefacto de la escala torsional y no un fallo de busqueda. LA MAGNITUD DEL ARTEFACTO, MEDIDA: preparar el MISMO cristal como flexible en vez de rigido lo empeora 1.055 kcal/mol de mediana -hasta 3.895- porque paga la penalizacion que el TORSDOF 0 no pagaba. Eso cubre de sobra el deficit de 0.491 que el testigo leia. Corregida la escala, el deficit mediano se invierte a -0.406: el brazo masivo puntua MEJOR que el cristal relajado en 36 de 48, y solo 4 -1k9s +1.011, 1add +0.550, 1ax0 +0.537, 1flr +0.280- conservan ventaja para el cristal. La aritmetica previa lo habia anticipado -el modelo con w_rot=0.05846 predecia 1.367 de artefacto contra 0.491 observado- y la medicion la confirma sin depender de ella. CONSECUENCIA REGISTRADA EN MF-29-EMP: su testigo deja de ser instrumento valido, la cantidad primaria masivo-vs-produccion queda sola, y su lectura OBJETIVO se sostiene; su decision pasa de INCONCLUSIVE a GO por esta via y no por haber movido ningun umbral. Tambien queda anulado el confusor del confórmero que MF-29-EMP habia declarado: no hace falta, porque el deficit que se le iba a atribuir no existe. HALLAZGO LATERAL, no preregistrado y por tanto exploratorio: 1ew8 puntua +1.714 preparado flexible, positivo. MF-13 ya lo habia senalado -junto a 1fkh- como sistema probablemente mal montado por su -2.181 rigido; verlo cruzar a positivo refuerza esa hipotesis y no la establece. LIMITES: no reabre la cantidad primaria de MF-29-EMP, que no la toca ningun resultado de aqui; no certifica optimalidad global y MF-29 sigue ABIERTO; cohorte de 48 y no 50 porque el brazo masivo de 1mmr y 1nm6 expiro.
- Hashes de dataset: 3 archivo(s) con SHA-256
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
