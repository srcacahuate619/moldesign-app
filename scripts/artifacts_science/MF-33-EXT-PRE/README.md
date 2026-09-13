# MF-33-EXT-PRE

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

La cobertura del oraculo del programa esta medida sobre un conjunto de poses que en un 93.9% viene del protocolo RIGIDO (RC-F0-V2-EXT). Dockeando FLEXIBLES los mismos conformeros, MF-33 vio pasar el estrato dificil de 1/33 a 26/33; si ese salto se sostiene sobre los 116 de train, el denominador de media docena de conclusiones del programa esta mal puesto.

## Protocolo

Referencia: `Mismo metodo que el brazo B de MF-33, distinto alcance: los 116 de train en vez de los 48 de la cohorte, como REC-08-EXT extendio a REC-08. Por complejo, dockear TODOS los conf*.flex.pdbqt del ensemble ETKDG ya en disco con los parametros del brazo de control de MF-28 -de donde MF-33 reuso su brazo B-: exhaustiveness=8, num_modes=9, seed=42, caja 25 A, --cpu 1. Metrica rmsd_pose_pocket, RMSD de pesados en el marco del pocket SIN alineamiento, seccion 5.1 del doc 49. Los conformeros NO se regeneran. Script: scripts/run_mf33ext_cobertura_flexible.py. COSTE MEDIDO, no estimado: el brazo B de MF-33 consumio 42.6 CPU-h en 48 complejos -mediana 2548 s, maximo 11391 s, 970 docks-, que extrapolado a 116 son ~103 CPU-h: 10.3 h con 10 workers, 25.7 h con los 4 nucleos del servidor.`

## Gate

PRIMARIA: cobertura = fraccion de los 116 con oraculo <= 2.0 A por la metrica de pocket. EL LISTON NO SE ELIGE AQUI: es el 0.90 del gate G5 de MF-02D, declarado antes que este experimento y ya usado para sellar aquel NO_GO. LA LINEA BASE ES 0.7931 Y NO 0.9310: MF-02D reporto cobertura_despues=108/116=0.9310 con otra metrica, pero su gate G5 sobre la metrica de pocket -que es la primaria- dio 0.7931 y fallo el liston; por eso esta NO_GO. DOS LECTURAS ESCRITAS ANTES: (1) cobertura >= 0.90 => EL GENERADOR FLEXIBLE ALCANZA EL LISTON que el rigido no alcanzo, y la regeneracion completa de la cohorte queda JUSTIFICADA con su coste de re-sellado; (2) cobertura < 0.90 => NO ALCANZA EL LISTON, se reporta la diferencia contra 0.7931 como magnitud descriptiva y la regeneracion no queda justificada por esta via. SECUNDARIO: curva de cobertura contra presupuesto, registrando el oraculo acumulado tras 1..K corridas en ORDEN DE INDICE DE CONFORMERO -no ordenado por calidad, que seria informacion de oraculo inexistente en produccion-. Existe porque MF-33-A3 esta midiendo si la ventaja del brazo B era diversidad conformacional o conteo de poses: si fue diversidad el titular es la cobertura final, si fue conteo el titular es la cobertura al presupuesto de poses del protocolo rigido, que la curva da sin recomputar. ASI QUE ESTE EXPERIMENTO NO DEPENDE DE A3 PARA EJECUTARSE, SOLO PARA TITULARSE. PROHIBIDO: mover el liston de 0.90; usar el 0.9310 como linea base; leer esto como evaluacion de selector, que MF-02D declaro fuera de alcance y aqui se mantiene; leerlo como que el techo de cobertura sea del generador, porque MF-33-CRUCES midio que 4 de los 7 que el ensemble no convierte son cristales que puntuan absurdo y REC-09 que al menos dos lo son por aguas bloqueantes: parte del techo es PREPARACION y este experimento no los separa.

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `9e385a7f2cef002fb1ca16352534966841a1d116`, dirty=True

## Estado

- Creado: 2026-08-20T20:52:32.878546+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-08-20T20:52:34.349381+00:00)
- Finalizado: 2026-08-20T20:52:34.663851+00:00
- Razón de la decisión: Prerregistro sellado ANTES de ejecutar, con el hash del script. Deja el experimento listo para lanzar con un comando cuando haya nucleos: ~103 CPU-h medidos y no estimados, extrapolados del consumo real del brazo B de MF-33. Tres decisiones de diseno que se toman aqui y no despues. PRIMERA, el liston se hereda: 0.90 sale del gate G5 de MF-02D y no de mirar estos datos. SEGUNDA, la linea base es 0.7931 y no 0.9310, porque la primaria de MF-02D es la metrica de pocket y es la que fallo su gate; confundirlas convertiria un NO_GO en un aparente exito. TERCERA, la curva de cobertura contra presupuesto se registra desde el principio para que el experimento se pueda leer con cualquiera de las dos respuestas que MF-33-A3 esta a punto de dar: si la ventaja del ensemble era diversidad conformacional, el titular es la cobertura final; si era conteo de poses, el titular es la cobertura a presupuesto igualado, que la curva da sin recomputar nada. Por eso no depende de A3 para ejecutarse, solo para titularse, y puede lanzarse en cuanto se liberen nucleos. Se declara ademas el limite que hoy es mas facil de olvidar: MF-33-CRUCES midio que 4 de los 7 complejos que el ensemble no convierte son cristales que puntuan absurdo, y REC-09 que al menos dos lo son por aguas que el pipeline conserva y el ligando desplaza. Parte del techo de cobertura es PREPARACION y no generador, y este experimento no los separa.
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
