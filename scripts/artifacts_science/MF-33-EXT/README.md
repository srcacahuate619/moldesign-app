# MF-33-EXT

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

La cobertura del oraculo del programa esta medida sobre un conjunto de poses que en un 93.9% viene del protocolo RIGIDO. Dockeando FLEXIBLES los mismos conformeros sobre los 116 de train, esa cobertura sube, y el denominador de media docena de conclusiones esta mal puesto.

## Protocolo

Referencia: `Ver prerregistro sellado MF-33-EXT-PRE. Mismo metodo que el brazo B de MF-33, distinto alcance: los 116 de train. Todos los conf*.flex.pdbqt con los parametros del brazo de control de MF-28: exh=8, num_modes=9, seed=42, caja 25 A, --cpu 1. Metrica rmsd_pose_pocket sin alineamiento. Los conformeros NO se regeneran. Corrio en la maquina local con 10 workers, 12.76 h, ~107 CPU-h.`

## Gate

PRIMARIA: cobertura = fraccion de los 116 con oraculo <= 2.0 A. LISTON HEREDADO del gate G5 de MF-02D: 0.90. LINEA BASE 0.7931 y NO 0.9310 -MF-02D reporto las dos, pero su primaria es la metrica de pocket y es la que fallo su gate-. DOS LECTURAS: cobertura >= 0.90 EL GENERADOR FLEXIBLE ALCANZA EL LISTON y la regeneracion queda JUSTIFICADA; < 0.90 NO ALCANZA. SECUNDARIO: curva de cobertura contra presupuesto en orden de indice de conformero.

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `22193cfdfcf710fda66261a98cc025774bf913d8`, dirty=True

## Estado

- Creado: 2026-08-21T15:10:04.996418+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-08-21T15:10:05.526488+00:00)
- Finalizado: 2026-08-21T15:44:17.891256+00:00
- Razón de la decisión: EL GENERADOR FLEXIBLE ALCANZA EL LISTON: cobertura 107 de 116 = 0.9224, por encima del 0.90 heredado del gate G5 de MF-02D. Linea base rigida 0.7931: +12.93 puntos porcentuales. LO QUE SIGNIFICA PARA EL REGISTRO: MF-02D esta sellado NO_GO precisamente porque su G5 -cobertura con la metrica de pocket, la primaria- dio 0.7931 y no alcanzo el liston. El mismo liston, la misma cohorte y la misma metrica, con generador FLEXIBLE: 0.9224. El material que el programa usa como denominador estaba por debajo del liston que el propio programa se puso. LA REGENERACION DE LA COHORTE QUEDA JUSTIFICADA por la regla preregistrada, con la advertencia de que justificarla no es ejecutarla. COMPROBACION DE CONSISTENCIA NO PLANIFICADA Y PERFECTA: en COLOCACION da 26 de 33, EXACTAMENTE el brazo B de MF-33 sobre esos mismos complejos. Mismo protocolo y semilla, debia reproducir y reproduce. POR ESTRATO: COLOCACION 26/33 = 0.7879 con oraculo mediano 1.184; CONTROL 15/15 = 1.0 con 1.01; RESTO 66/68 = 0.9706 con 0.889. NUEVE COMPLEJOS NO SE CUBREN CON NINGUN K: 1afl, 1bq4, 1d7i, 1d9i, 1dgm, 1elb, 1ew8, 1fkh, 1jq8. Siete estan en la cohorte de 48 y dos -1bq4, 1elb- no. CORRECCION IMPORTANTE SOBRE COMO SE HA CONTADO ESTA CONVERGENCIA, Y ES UN ERROR MIO REPETIDO: la version anterior de esta razon hablaba de TRES lineas independientes senalando el mismo conjunto. SON DOS. Que los siete no convertidos de MF-33-CRUCES esten todos dentro de G3 NO es convergencia independiente: MF-33-CRUCES define no convertido como que el brazo B no alcanza <=2 A sobre esos 48, y G3 dentro de los 48 es que el ensemble de MF-33-EXT no cubre. ES EL MISMO PROTOCOLO SOBRE LOS MISMOS COMPLEJOS, y de hecho MF-33-EXT reproduce el brazo B exactamente -26/33-. Ese solape de 7 sobre 7 es REPRODUCCION, no evidencia nueva. LA LINEA GENUINAMENTE INDEPENDIENTE ES REC-09, que midio el scoring del cristal y no el docking, y su enriquecimiento es fuerte y ahora medido: de los 6 complejos con cristal absurdo, 4 estan en G3 -el 67%- contra 5 de 110 entre los no marcados -el 4.5%-. Enriquecimiento de 14.7x, Fisher exacto unilateral p=2.45e-04. AFIRMACION DEFENDIBLE, y no mas: los fallos residuales tras un muestreo conformacional extenso estan ENRIQUECIDOS en complejos senalados de forma independiente por diagnosticos de preparacion y puntuacion. Eso argumenta contra el muestreo conformacional adicional como UNICA explicacion del conjunto de fallos residuales. NO afirma que la preparacion cause los nueve fallos, ni niega que otro muestreador pudiera recuperarlos: dice que esta intervencion causal sobre el muestreo llego practicamente a su limite y los mismos casos siguen apareciendo por otra via. LIMITES: el oraculo es cota superior de lo alcanzable y no prediccion, no evalua selector; los conformeros no se regeneran; y parte del techo puede ser preparacion y no generador, que es justo lo que sugieren los nueve.
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
