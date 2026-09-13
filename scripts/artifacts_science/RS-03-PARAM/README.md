# RS-03-PARAM

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

La parametrizacion OpenFF Sage + NAGL congelado sobre los 116 ligandos train es una base fisica correcta -cobertura, determinismo, carga, cero fallback- que reemplaza el tipado heuristico de molchamb_v2.py como base de cargas del programa.

## Protocolo

Referencia: `AGREGACION declarada en RS-03-PARAM-PRE y anunciada por RS-03-PARAM-A -'Siguiente: RS-03-PARAM-B y luego RS-03-PARAM (agregacion)'- que nunca se ejecuto. SIN COMPUTO NUEVO: verifica los once requisitos primarios de la seccion 4 del PREREGISTRO maestro contra los artefactos sellados A y B, y emite la decision que el contrato define. Fuente A: RS-03-PARAM-A, que evaluo y sello los once. Fuente B: RS-03-PARAM-B, referencia AM1-BCC estratificada.`

## Gate

Los once requisitos primarios del contrato congelado (seccion 4 del PRE maestro): version y SHA de Sage/NAGL, cero descargas en ejecucion, carga formal del ligando sanitizado, |suma q - formal| <= 1e-4, mapeo biyectivo con atom_order_hash, cero fallback silencioso, cobertura global >=95%, cobertura >=90% por estrato, energia finita y serializable al 100%, determinismo <=1e-6, y fallos clasificados por quimica nunca convertidos en energia cero. ASIMETRIA DECLARADA EN EL CONTRATO Y NO INTRODUCIDA AQUI: AM1-BCC es referencia estratificada y NO verdad absoluta, y queda PROHIBIDO seleccionar NAGL mirando RMSD o Top-1. B CARACTERIZA, NO DECIDE: una divergencia grande documenta, no reprueba. Reprobar exigiria que A fallara un requisito primario, o un experimento de rendimiento que el contrato prohibe usar aqui.

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `60f010fa445e1d4cb9cf8a265f637f33b97e16e9`, dirty=True

## Estado

- Creado: 2026-08-20T05:12:08.921290+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-08-20T05:12:32.356057+00:00)
- Finalizado: 2026-08-20T05:12:32.567235+00:00
- Razón de la decisión: LA DECISION QUE A Y B ALIMENTABAN, EJECUTADA POR FIN. RS-03-PARAM-A la anuncio en su propio sello -'Siguiente: RS-03-PARAM-B y luego RS-03-PARAM (agregacion)'- y RS-03-PARAM-B la exigio con una prohibicion explicita: 'PROHIBIDO concluir sobre NAGL desde B: la decision es de RS-03-PARAM agregando A y B contra el contrato del PRE maestro'. La agregacion nunca se ejecuto y el contrato quedo sin cerrar durante semanas mientras el resto del programa daba por hecha su conclusion. VEREDICTO: los once requisitos primarios PASAN, evaluados y sellados por A -cobertura global 100% y 100% en los seis estratos, determinismo 2.78e-17 frente a un limite de 1e-6, |suma q - formal| maximo 1e-15 frente a 1e-4, mapeo biyectivo con atom_order_hash, cero fallback silencioso, energia finita y serializable en el 100%, y version y SHA del modelo NAGL de produccion registrados-. DECISION DEL CONTRATO: ACEPTAR NAGL como base de cargas, en sustitucion del tipado heuristico de molchamb_v2.py. LA ASIMETRIA QUE HACE VALIDA ESTA DECISION NO SE INTRODUJO AQUI: viene del contrato congelado, que declara AM1-BCC como referencia estratificada y NO verdad absoluta, y que PROHIBE seleccionar NAGL mirando RMSD o Top-1. B caracteriza y no decide. Eso importa porque B encontro divergencia sustancial -|dq| mediana 0.0118 e por atomo, y |dE| de punto unico con mediana 24.3 kJ/mol y maxima 216.4, del orden de lo que un rescoring pretende resolver- y sin la asimetria declarada de antemano habria sido tentador leer esa divergencia como un suspenso. No lo es: documenta un limite, no reprueba el metodo. Reprobarlo exigiria que A fallara un requisito primario, o un experimento de RENDIMIENTO que el contrato prohibe usar en esta decision. CAVEAT QUE VIAJA CON LA ACEPTACION: aceptar NAGL como base de cargas NO significa que las diferencias con AM1-BCC sean irrelevantes. Son del tamano del efecto que un rescoring quiere medir, divergen mas en azufre y fosforo y crecen con tamano y flexibilidad, es decir justo donde el programa trabaja. Cualquier experimento de rescoring fisico debe declarar que juego de cargas usa y por que. Sin computo nuevo: lectura de dos artefactos sellados.
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
