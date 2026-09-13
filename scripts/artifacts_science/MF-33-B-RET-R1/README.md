# MF-33-B-RET-R1

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

La repeticion completa del brazo B MF-33, con retencion forense, reproduce su oraculo sellado y permite distinguir ganancia de generacion de ganancia entregada por score Vina.

## Protocolo

Referencia: `Ver prerregistro sellado MF-33-B-RET-R1-PRE, anterior a esta corrida. Repeticion tecnica completa de 48 complejos: exh8, 9 modos, seed42, caja25A, cpu1; sin rescoring; retencion PDBQT/log/per-pose/checkpoint.`

## Gate

G0: 48/48 sin fallos; G1: oraculo ENSEMBLE reproduce B sellado dentro 0.001A en >=95%; primario McNemar top1/top5/oraculo con lectura exacta de MF-33-B-RET-PRE.

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `codex/mejora-producto`, commit `8d69c5533ac20e01c74e73f1030341d1bc05e6fb`, dirty=True

## Estado

- Creado: 2026-08-23T05:56:10.346802+00:00
- Status: finished
- Decisión: INCONCLUSIVE
- Sellado: sí (2026-08-23T05:56:13.091985+00:00)
- Finalizado: 2026-08-23T05:56:13.233263+00:00
- Razón de la decisión: G0 TECNICO FALLA Y POR TANTO LA LECTURA PRIMARIA ES NO_LEER_GATES_TECNICOS, que es exactamente lo que el prerregistro ordena. 48 de 48 complejos completos, pero UN fallo: 1afl conformero 29, Vina returncode 1 a los 154.9 s. El contrato dice que un fallo de Vina, parseo o mapeo es ITT -se registra y hace fallar G0-, sin excepcion por tamano. G1 PASA Y DE FORMA PERFECTA: 47 de 47 = 1.0000 contra un minimo de 0.95. El oraculo ENSEMBLE reproduce el rmsd_min del brazo B sellado de MF-33 dentro de 0.001 A en todos los complejos leibles. La repeticion con retencion forense es fiel al original. CARACTERIZACION DEL FALLO, que es diagnostico y no cambia el gate: el stdout de 1afl/conf29 muestra que Vina calculo el grid y empezo a dockear, con la barra de progreso cortada a media altura y stderr VACIO. Re-ejecutado aislado con el protocolo identico, ese mismo dock termina con rc=0 y nueve poses. No es un fallo de quimica ni del conformero: el proceso murio. El checkpoint se escribio a las 17:36, mientras en la misma maquina se ejecutaban PoseBusters, pytest y generacion de conformeros; es contencion de recursos, la trampa que el propio registro ya tenia documentada -un plazo o una muerte de proceso producen sintomas identicos a un fallo real-. INCONCLUSIVE es la unica decision compatible con el contrato. Los bloques cientificos SE CALCULARON y estan en metrics.json porque el runner los escribe siempre, pero NO SE LEEN NI SE CITAN: el prerregistro condiciona su lectura a que G0 y G1 pasen los dos. ADVERTENCIA DE PROCEDENCIA PARA CUALQUIER R2, y hay que escribirla ahora: al diagnosticar el fallo se vieron los bloques cientificos de este metrics.json. Un R2 que repare el unico dock afectado NO puede presentarse como confirmacion ciega. Lo que SIGUE siendo ciego es la REGLA DE DECISION, que quedo escrita en MF-33-B-RET-PRE y MF-33-B-RET-R1-PRE antes de todo esto y no se puede mover; lo que se perdio es la ceguera sobre el desenlace, y eso se declara en vez de disimularse. Retencion completa conservada y verificada por conteo: 48 checkpoints, 48 per_pose, 969 PDBQT crudos -970 docks menos el que fallo- y 1940 logs. Esa retencion es lo que permite que el diagnostico de arriba exista, y es la razon de ser de este R1 frente al MF-33-B-RET original, que no guardaba geometria.
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
