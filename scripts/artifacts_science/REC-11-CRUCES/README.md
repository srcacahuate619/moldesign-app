# REC-11-CRUCES

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

El criterio geometrico de agua bloqueante de REC-09 -algun atomo a <=2.6 A de un atomo pesado del ligando CRISTALOGRAFICO- necesita conocer la pose, y el docking de novo no la conoce. Si aun asi capturase el mecanismo, los complejos donde quitar las aguas gana el oraculo en REC-11 estarian enriquecidos en aguas bloqueantes.

## Protocolo

Referencia: `Sin computo: cruza dos artefactos sellados, REC-09/per_complex.jsonl y REC-11/per_complex.jsonl, sobre los mismos 116. Tabla A, sobre los 116: tasa de gana_SIN entre los que tienen al menos un agua bloqueante frente a los que no tienen ninguna, con test exacto de Fisher bilateral. Tabla B, restringida a los 18 discordantes de REC-11: entre los complejos que SI se movieron, la presencia de agua bloqueante predice la DIRECCION del movimiento. Se listan ademas por nombre los complejos rescatados al quitar las aguas que tienen CERO bloqueantes. La implementacion de Fisher es propia y se verifica contra dos casos conocidos antes de usarla. Script: scripts/analisis_rec11cruces_criterio_geometrico.py.`

## Gate

SIN GATE. NO HAY DECISION QUE DEPENDA DE UN UMBRAL, Y ESO ES DELIBERADO. ADVERTENCIA DE PROCEDENCIA, QUE ES LA RAZON DE SER DE ESTE CAMPO: la tabla de contingencia SE INSPECCIONO al proponer este analisis, ANTES de escribir este registro. NO es un prerregistro ciego y no se presenta como tal. En consecuencia los p que produce son DESCRIPTIVOS y no sostienen ninguna afirmacion confirmatoria, por pequenos que salgan. Registrarlo con la etiqueta correcta es preferible a no registrarlo, y es el mismo trato que recibio el desglose por estrato de REC-11. PROHIBIDO: citar el p de la tabla A como evidencia de nada; presentar esto como una refutacion de REC-09, que midio el scoring del CRISTAL y cuyo resultado no se toca -lo que aqui se contrasta es el ALCANCE de su criterio fuera de ese contexto-; usar esto para cambiar la politica de aguas, que la gobierna REC-11 y salio SIN_DIFERENCIA_DETECTABLE; y leer las celdas como estables, porque van de 1 a 7 elementos. Lo que este analisis produce es una HIPOTESIS para un prerregistro futuro, no un resultado.

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `codex/mejora-producto`, commit `edd07507a6a301c299158df075c2e9b66bb0c695`, dirty=True

## Estado

- Creado: 2026-08-23T00:52:11.422356+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-08-23T00:52:12.518288+00:00)
- Finalizado: 2026-08-23T00:52:12.738883+00:00
- Razón de la decisión: MEDICION DESCRIPTIVA POST-HOC. Se registra con esa etiqueta porque la tabla de contingencia se vio ANTES de escribir el registro, al proponer el analisis; decirlo es la unica forma de que el numero que sigue no se lea como lo que no es. LO QUE MIDE: sobre los 116, la tasa de 'quitar las aguas gana el oraculo' es 5 de 26 = 0.1923 entre los complejos con al menos un agua bloqueante por el criterio de 2.6 A de REC-09, y 5 de 90 = 0.0556 entre los que no tienen ninguna. Enriquecimiento 3.46x, Fisher exacto bilateral p = 0.0437 DESCRIPTIVO, que por lo dicho arriba NO se cita. LO QUE MUESTRA, Y NO DEPENDE DEL p: el criterio no basta. CINCO de los DIEZ complejos rescatados al quitar las aguas tienen CERO aguas bloqueantes -10gs, 1d7i, 1ela, 1fh7, 1nje-, o sea la mitad del efecto cae fuera de lo que el criterio ve. Y entre los 18 que SI se movieron, la presencia de agua bloqueante no predice la DIRECCION: p = 0.1516. Un criterio que necesita la pose cristalografica para definirse deja de servir cuando la pose es justamente lo que no se conoce, que es la asimetria que REC-11 declaro al disenarse y la razon de que alli se quitaran TODAS. GO porque el cruce entrega lo que prometia, con su limitacion escrita y su implementacion de Fisher verificada contra dos casos conocidos (0.4857 y 1.0825e-05) antes de usarla. NO refuta REC-09: aquel midio el scoring del CRISTAL y su resultado queda intacto; lo que aqui se acota es el ALCANCE de su criterio fuera de ese contexto. No autoriza cambiar la politica de aguas, que la gobierna REC-11 con SIN_DIFERENCIA_DETECTABLE. Lo que produce es una hipotesis para un prerregistro futuro: un criterio de agua estorbante que no dependa de conocer la pose.
- Hashes de dataset: 2 archivo(s) con SHA-256
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
