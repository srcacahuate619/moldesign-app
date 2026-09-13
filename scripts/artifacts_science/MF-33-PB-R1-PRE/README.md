# MF-33-PB-R1-PRE

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

El ensemble de conformeros no solo encuentra mas poses correctas: entrega una pose top-1 fisicamente mas valida que el conformero unico. La alternativa es que solo produzca MAS poses sin mejorar la fisica de la que finalmente elige, en cuyo caso la ventaja del ensemble no llega a la unica pose que el usuario recibe.

## Protocolo

Referencia: `IDENTICO al de MF-33-PB-PRE, que se reproduce aqui sin cambios, salvo la correccion de implementacion descrita en la razon de decision. Sin computo de docking: se evaluan poses YA RETENIDAS. El material son las 8215 poses que MF-33-B-RET-R1 conservo en 969 PDBQT crudos sobre 48 complejos. Ese claim -C10 del docs/52- figuraba como BLOQUEADO porque las poses se habian borrado en la corrida original; la retencion forense de R1 lo desbloquea. PoseBusters en configuracion REDOCK, no dock, y la eleccion no es libre: aqui SI existe el ligando cristalografico, y redock es ademas la configuracion con la que MF-33-TOP1 midio el protocolo rigido. Usar dock daria numeros que parecen comparables y no lo son. PAREADO PERFECTO. Por complejo, dos brazos que salen del MISMO artefacto: SINGLE son las poses del conformero 0; ENSEMBLE son todas. Mismo complejo, mismo receptor, mismo cristal, misma corrida. La pose se reconstruye reusando el mapeo de molflex sobre el cristal -que ya tiene los ordenes de enlace correctos- en vez de re-perceptualizar desde el PDBQT, porque re-perceptualizar perderia aromaticidad y haria basura los controles intramoleculares. ORDEN DE EVALUACION declarado: dentro de cada complejo se evaluan primero los top-1 y top-5 de cada brazo -las cantidades con gate- y despues el resto, con checkpoint por complejo. Si la corrida se interrumpe, los complejos completados siguen respondiendo la pregunta primaria. Contenedor moldesign-lab del servidor con posebusters 0.6.5, la MISMA version que el entorno local. Script: scripts/run_mf33pb_validez_fisica.py. CAMBIO DE IMPLEMENTACION, NO DE PROTOCOLO: el runner ya no llama a PoseBusters por su cuenta; REUSA scripts/posebusters_metrica.py, que se sella aqui como asset. Ese modulo separa el check `rmsd_` de los controles fisicos, construye el cristal con hidrogenos y llama a la API en la forma correcta. Las tres cosas estaban mal en la version anterior.`

## Gate

PRIMARIA: fraccion de complejos cuyo top-1 pasa la bateria completa de PoseBusters, pareada por complejo, con b = ENSEMBLE pasa y SINGLE no, y c = SINGLE pasa y ENSEMBLE no. McNemar exacto bilateral de estadistica_fnd04. TRES LECTURAS ESCRITAS ANTES: (1) p<0.05 con b>c => EL_ENSEMBLE_ENTREGA_MAS_VALIDO, y la ventaja del ensemble alcanza tambien a la fisica de lo entregado; (2) p<0.05 con c>b => EL_ENSEMBLE_ENTREGA_MENOS_VALIDO, que seria un hallazgo serio y contrario a la hipotesis -mas poses pero peor fisica en la elegida- y obligaria a revisar como se presenta el ensemble en el paper; (3) p>=0.05 => SIN_DIFERENCIA_DETECTABLE, sin leerlo como equivalencia y declarando el limite de potencia. EFECTO MINIMO DETECTABLE DECLARADO ANTES: con n=48, el MDE pareado es de 11.85 pp si la discordancia sale del 10%, 16.77 pp si sale del 20% y 20.53 pp si sale del 30%; y con c=0 el McNemar exacto exige b>=6 para p<0.05. Diferencias menores NO son resolubles con esta cohorte y se reportaran como no concluyentes, nunca como tendencia. SECUNDARIO descriptivo y SIN gate: la misma tabla sobre top-5; la tasa de validez del CONJUNTO de poses, no solo de la entregada; y el recuento de que controles fallan mas. PROHIBIDO: comparar la tasa de aqui con el 8.62% / 15.52% de MF-33-TOP1 como si fueran la misma cantidad -aquello fue sobre el protocolo RIGIDO y sobre 116 complejos, esto sobre el FLEXIBLE y sobre 48-; comparar con la configuracion `dock` que corre en produccion, que tiene menos controles; leer validez fisica como acierto de docking, porque una pose puede ser fisicamente impecable y estar en el sitio equivocado; y leer SIN_DIFERENCIA_DETECTABLE como equivalencia. NADA DE ESTE GATE CAMBIA respecto a MF-33-PB-PRE: se reproduce palabra por palabra. Lo unico que cambia es la implementacion que lo calcula, y el motivo esta en la razon de decision. LA CEGUERA SE CONSERVA: con la version defectuosa no se leyo ningun resultado -las 261 poses de la unica prueba tecnica salieron todas como no evaluadas por RuntimeError-, y esa prueba se lanzo con `--limite`, que por contrato produce NO_LEER_GATES_TECNICOS y nunca una decision.

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `codex/mejora-producto`, commit `8d69c5533ac20e01c74e73f1030341d1bc05e6fb`, dirty=True

## Estado

- Creado: 2026-08-23T06:34:44.472599+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-08-23T06:34:45.299622+00:00)
- Finalizado: 2026-08-23T06:34:45.461760+00:00
- Razón de la decisión: Prerregistro sellado ANTES de ejecutar. Existe porque MF-33-PB-PRE sello un script con DOS defectos de implementacion, y un prerregistro sellado no se puede re-sellar: la unica salida limpia es declarar el defecto y volver a preregistrar con el arreglo. PRIMER DEFECTO, visible: la llamada a PoseBusters fallaba entera. En la prueba tecnica las 261 poses del unico complejo evaluado salieron con RuntimeError, en 3.5 segundos. Si se hubiera lanzado la corrida completa sin probar, habrian sido entre tres y seis horas de servidor para devolver 48 complejos de nada. SEGUNDO DEFECTO, invisible y mucho peor: la version anterior contaba el check `rmsd_` del config `redock` entre los controles fisicos. Eso habria convertido la cantidad medida de 'la pose es fisicamente valida' en 'la pose es valida Y ADEMAS esta a menos de 2 A', que es precisamente lo que el gate de MF-33-PB-PRE prohibe leer. Habria producido un numero plausible, publicable y equivocado. El modulo sellado posebusters_metrica.py ya separaba las dos cosas y lo documentaba en sus lineas 101-108; la version defectuosa lo ignoro y reimplemento. La leccion es la regla del docs/49 seccion 17 que ya gobierna los assets sellados: reusar por composicion, no reimplementar. LA CEGUERA SE CONSERVA INTACTA y por eso este R1 SI es ciego, a diferencia de MF-33-B-RET-R2: no se leyo ningun resultado con la version defectuosa porque no produjo ninguno, y la prueba que la destapo se lanzo con `--limite`, que por contrato fuerza NO_LEER_GATES_TECNICOS. El gate se reproduce palabra por palabra desde MF-33-PB-PRE, incluidos el MDE declarado y las tres lecturas.
- Hashes de dataset: 2 archivo(s) con SHA-256
- Hashes de assets: 2 archivo(s) con SHA-256

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
