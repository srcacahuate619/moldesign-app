# MF-33-PB-PRE

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

El ensemble de conformeros no solo encuentra mas poses correctas: entrega una pose top-1 fisicamente mas valida que el conformero unico. La alternativa es que solo produzca MAS poses sin mejorar la fisica de la que finalmente elige, en cuyo caso la ventaja del ensemble no llega a la unica pose que el usuario recibe.

## Protocolo

Referencia: `Sin computo de docking: se evaluan poses YA RETENIDAS. El material son las 8215 poses que MF-33-B-RET-R1 conservo en 969 PDBQT crudos sobre 48 complejos. Ese claim -C10 del docs/52- figuraba como BLOQUEADO porque las poses se habian borrado en la corrida original; la retencion forense de R1 lo desbloquea. PoseBusters en configuracion REDOCK, no dock, y la eleccion no es libre: aqui SI existe el ligando cristalografico, y redock es ademas la configuracion con la que MF-33-TOP1 midio el protocolo rigido. Usar dock daria numeros que parecen comparables y no lo son. PAREADO PERFECTO. Por complejo, dos brazos que salen del MISMO artefacto: SINGLE son las poses del conformero 0; ENSEMBLE son todas. Mismo complejo, mismo receptor, mismo cristal, misma corrida. La pose se reconstruye reusando el mapeo de molflex sobre el cristal -que ya tiene los ordenes de enlace correctos- en vez de re-perceptualizar desde el PDBQT, porque re-perceptualizar perderia aromaticidad y haria basura los controles intramoleculares. ORDEN DE EVALUACION declarado: dentro de cada complejo se evaluan primero los top-1 y top-5 de cada brazo -las cantidades con gate- y despues el resto, con checkpoint por complejo. Si la corrida se interrumpe, los complejos completados siguen respondiendo la pregunta primaria. Contenedor moldesign-lab del servidor con posebusters 0.6.5, la MISMA version que el entorno local. Script: scripts/run_mf33pb_validez_fisica.py.`

## Gate

PRIMARIA: fraccion de complejos cuyo top-1 pasa la bateria completa de PoseBusters, pareada por complejo, con b = ENSEMBLE pasa y SINGLE no, y c = SINGLE pasa y ENSEMBLE no. McNemar exacto bilateral de estadistica_fnd04. TRES LECTURAS ESCRITAS ANTES: (1) p<0.05 con b>c => EL_ENSEMBLE_ENTREGA_MAS_VALIDO, y la ventaja del ensemble alcanza tambien a la fisica de lo entregado; (2) p<0.05 con c>b => EL_ENSEMBLE_ENTREGA_MENOS_VALIDO, que seria un hallazgo serio y contrario a la hipotesis -mas poses pero peor fisica en la elegida- y obligaria a revisar como se presenta el ensemble en el paper; (3) p>=0.05 => SIN_DIFERENCIA_DETECTABLE, sin leerlo como equivalencia y declarando el limite de potencia. EFECTO MINIMO DETECTABLE DECLARADO ANTES: con n=48, el MDE pareado es de 11.85 pp si la discordancia sale del 10%, 16.77 pp si sale del 20% y 20.53 pp si sale del 30%; y con c=0 el McNemar exacto exige b>=6 para p<0.05. Diferencias menores NO son resolubles con esta cohorte y se reportaran como no concluyentes, nunca como tendencia. SECUNDARIO descriptivo y SIN gate: la misma tabla sobre top-5; la tasa de validez del CONJUNTO de poses, no solo de la entregada; y el recuento de que controles fallan mas. PROHIBIDO: comparar la tasa de aqui con el 8.62% / 15.52% de MF-33-TOP1 como si fueran la misma cantidad -aquello fue sobre el protocolo RIGIDO y sobre 116 complejos, esto sobre el FLEXIBLE y sobre 48-; comparar con la configuracion `dock` que corre en produccion, que tiene menos controles; leer validez fisica como acierto de docking, porque una pose puede ser fisicamente impecable y estar en el sitio equivocado; y leer SIN_DIFERENCIA_DETECTABLE como equivalencia.

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `codex/mejora-producto`, commit `8d69c5533ac20e01c74e73f1030341d1bc05e6fb`, dirty=True

## Estado

- Creado: 2026-08-23T06:29:46.050341+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-08-23T06:29:46.795649+00:00)
- Finalizado: 2026-08-23T06:29:46.948191+00:00
- Razón de la decisión: Prerregistro sellado ANTES de ejecutar, con el hash del script. Este SI es ciego, y conviene decirlo porque el anterior de esta serie no lo era: nadie ha medido la validez fisica sobre el brazo flexible, ni yo ni nadie, y la pregunta pareada single contra ensemble no se ha mirado. La rama (2) -que el ensemble entregue poses MENOS validas- esta escrita en serio y no como formalidad: es un desenlace posible, seria contrario a la hipotesis, y obligaria a cambiar como el manuscrito presenta el ensemble. Existe porque C10 dejo de estar bloqueado. Figuraba en el docs/52 como imposible -las poses se borraron- y la retencion forense de MF-33-B-RET-R1 lo desbloqueo. Es la segunda vez que ese R1 justifica su diseno en el mismo acto de fallar su gate. El MDE se calcula ANTES con la biblioteca de FND-04 y se declara en cuatro formas -11.85, 16.77 y 20.53 pp segun la discordancia, mas b>=6 con c=0- para que ninguna diferencia pequena se pueda leer despues como tendencia. Es la leccion de RS-14 y el mismo trato que recibieron REC-11 y REC-05. Se prohibe de antemano el error mas probable, que es comparar esta tasa con el 8.62 / 15.52% de MF-33-TOP1: aquello es protocolo rigido sobre 116 y esto es flexible sobre 48. Y se declara que 47 de los 48 complejos tienen poses byte-identicas a las que tendra MF-33-B-RET-R2, asi que solo 1afl habra que recalcularlo cuando aquel cierre.
- Hashes de dataset: 2 archivo(s) con SHA-256
- Hashes de assets: 1 archivo(s) con SHA-256

## Mantenimiento del sello

- 2026-09-24T04:04:31.316162+00:00: `scripts/run_mf33pb_validez_fisica.py` `46aa1048→dac9b5ae` — Activo cambiado despues del sello: scripts/run_mf33pb_validez_fisica.py es un modulo o documento vivo que se sello como asset (regla 4 de las reglas de metodo: no sellar un modulo de produccion vivo). El resultado sellado se produjo con la version anterior, cuyo hash queda en previous_hash; la version actual es la del commit f007411. Se registra el 2026-09-23, antes de la auditoria externa, para que validar_sellos.py distinga este cambio declarado de una corrupcion. No cambia ninguna cifra ni decision del experimento. (commit f007411)

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
