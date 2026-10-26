---
titulo: "Con el origen reconocido, Preparación detecta los huecos del sitio y la estereoquímica sin asignar"
entradilla: "FEP-09 repetido sobre el producto con P01 arreglado: las 163 auditorías miden desde el ligando y no desde la caja. Los huecos del sitio siguen en 15 de 15, la estereoquímica sube a 21 de 21 y la falsa alarma baja a cero. El agua puente y la protonación del sitio siguen siendo límites de alcance, no efectos de P01."
---

**INCONCLUSIVE, como estaba previsto.** El gate global exige que pasen todas las categorías
declaradas, y «tautómero minoritario» y «especie del ligando» siguen con n=0: no hay
poblaciones ni pKa independientes con que sembrarlas. De las que sí se pueden medir, las dos
declaradas pasan el gate: **huecos en el sitio, 15 de 15**, y **estereoquímica sin asignar,
21 de 21**. Se completaron 163 auditorías, sin rechazos antes de Preparación y sin fallos de
infraestructura.

## Por qué se repitió

[FEP-09](FEP-09-SENSIBILIDAD.md) midió la pestaña Preparación con un defecto dentro, P01: la
comprobación del origen no reconocía la receta de los receptores propios. Por eso sus 127
auditorías del camino B se midieron desde la caja. P01 se arregló en `f0e64086`.

El mismo día se arregló en la pestaña Evaluación un error de la misma familia (aguas,
interacciones y archivos del visor). Ese arreglo no toca Preparación. R1 repite FEP-09 sobre el
producto con los dos arreglos, `ee2d6c78`, y amplía la estereoquímica, que se había quedado con
n=3.

## Qué se midió

- **Lo mismo que FEP-09:** camino B (`respetar`), Vina 1.2.7, exhaustividad 8, 9 poses,
  semilla 42, pH 7,4, un confórmero. Las mismas 15 dianas del benchmark de OpenFF (commit
  `fd88824f`) y los mismos 127 casos, idénticos byte a byte.
- **Arnés:** el de Sol sin cambios (`fep09_inputs`, `fep09_run`, `fep09_analyze`), envuelto
  por `scripts/fep09r1_*.py`.
- **Modo tautomérico:** no se forzó. El efectivo fue «entrada» en las 163, como declara esta
  vez el prerregistro.
- **Estereoquímica:** 36 casos nuevos. Por diana, hasta tres ligandos con algún estereocentro
  asignado, en el orden del SDF; cada uno con su línea base y una variante que borra la
  asignación del primer centro. Eso da n=21 en 7 dianas.
- **Ejecución:** tres cápsulas de QA con Vina limitado a 4 núcleos y árbol limpio, en 43 min.
  En paralelo corría otro experimento (MET-01) en una cuarta cápsula.

El [prerregistro](../auditorias/FEP-09-R1-prerregistro.md) se fijó en `68d36882`, antes de la
primera corrida, con el gate, seis predicciones y la potencia. No hubo desviaciones.

## Qué salió

| Categoría | n | FEP-09 | R1 | IC 95 % (R1) | Decisión / alcance |
|---|---:|---:|---:|---|---|
| hueco_en_el_sitio | 15 | 15 | **15** | [0,782; 1,000] | GO |
| estereo_sin_asignar | 21 (FEP-09: 3) | 3 | **21** | [0,839; 1,000] | GO |
| tautomero_minoritario | 0 | — | — | no estimable | INCONCLUSIVE |
| especie_del_ligando | 0 | — | — | no estimable | INCONCLUSIVE |
| agua_puente_retirada | 9 | 0 | 0 | [0,000; 0,336] | límite |
| protonacion_del_sitio | 5 | 0 | 0 (5 saturadas) | [0,000; 0,522] | límite |
| cadena_del_sitio_ausente | 1 | 0 | 0 (saturada) | [0,000; 0,975] | límite |
| metal_o_cofactor_retirado | 1 | 0 | 0 | [0,000; 0,975] | límite |
| tautomero_alternativo_proxy | 13 | 13 | 13 | [0,753; 1,000] | proxy |
| especie_opuesta_proxy | 7 | 1 | 1 | [0,004; 0,579] | proxy |

Los 15 huecos se detectan ahora midiendo desde el ligando, no desde la caja. En cdk2, por
ejemplo, el corte LEU 78 → PHE 82 queda a 3,11 Å del ligando, y Preparación se abstiene.

En la estereoquímica, las 7 dianas dan 3 de 3. El IC trata los 21 casos como independientes,
pero son tres ligandos por diana. El requisito lee el ligando y no el receptor, así que el
agrupamiento pesa poco, aunque existe.

| Control | FEP-09 | R1 |
|---|---|---|
| `entorno.referencia` REGISTRADO | 0 de 127 | **163 de 163** |
| Falsa alarma (renumeración inocua) | 4 de 555 (0,72 %) | **0 de 585** |
| Acuerdo entre líneas base repetidas | 99,55 % (5 cambios en `procedencia.commit`) | **100 %** (1170 comparaciones) |
| Cambios no previstos en los cortes lejanos | 2 de 370 | **0 de 390** |
| Mismo `receptor_sha256` en las tres bases de cada diana | 15 de 15 | 15 de 15 |

La falsa alarma y el ruido de FEP-09 venían de `procedencia.commit`, que pasaba de REGISTRADO
a NO_DISPONIBLE porque el arnés se editaba durante la medición. R1 corrió desde un worktree
congelado, así que ese factor desaparece. Es el mismo factor de confusión que FEP-09 declaró,
no una mejora del producto.

## Predicciones, antes y después

| # | Predicción preregistrada | Resultado |
|---|---|---|
| P1 | `entorno.referencia` REGISTRADO en todas | 163 de 163 ✔ |
| P2 | Huecos: GO otra vez (≥ 12 de 15) | 15 de 15 ✔ |
| P3 | Agua puente: 0 de 9, límite de alcance | 0 de 9 ✔ |
| P4 | Protonación del sitio: 0 de 5, rutinaria por diseño | 0 de 5 ✔ (las 5 saturadas) |
| P5 | Estereoquímica: GO (≥ 16 de 21) | 21 de 21 ✔ |
| P6 | Falsa alarma ≤ 0,10 | 0 ✔ |

**P3 y P4 corrigen lo que escribí al revisar FEP-09.** Dije que P01 confundía esos dos
límites; no era así. El resultado no cambia caso por caso entre los dos experimentos.

- **Agua puente:** se borra antes de subir el archivo. La auditoría sólo ve una cifra
  distinta, «1 conservada» en la base frente a «0» en la variante de cdk2, y no tiene manera
  de saber que faltaba un agua.
- **Protonación:** en el camino B es la del usuario. Preparación la pide revisar en toda
  corrida, así que la línea base ya está en REVISAR y una His cambiada no puede subir el
  riesgo.

Lo que P01 sí podía cambiar era la referencia de los huecos, y el resultado se mantiene
midiendo desde el ligando.

Los únicos cambios colaterales son ecos del propio defecto. Las variantes de estereoquímica
añaden `LIGANDO_REVISION_QUIMICA` en la comprobación previa (21 casos), y algunas variantes
cambian la regla de selección de la pose.

## Qué no dice

- No mide la fracción de problemas reales de preparación que MolDesign detecta: los defectos
  los sembramos nosotros sobre un benchmark preparado por expertos.
- No demuestra transferencia a FEP, compatibilidad con FEP+ ni energía libre.
- No valida poblaciones tautoméricas, pKa individuales ni la protonación del receptor.
- No audita la interfaz, WebView2, el runtime empaquetado ni el instalador.
- No atribuye errores a los autores del benchmark; los estados químicos proxy están fuera
  del gate.

## Reproducción

Manifiesto, inventario, condiciones registradas, resultados por caso, métricas y la evidencia
de cada corrida están en `scripts/artifacts_science/FEP-09-R1/`. Para repetirlo:

1. una cápsula de QA desde el commit del prerregistro;
2. `python scripts/fep09r1_run.py --capsule DIR --shard N`, con N = 0, 1 y 2;
3. `python scripts/fep09r1_analyze.py --merge`.

Datos CC BY 4.0 de OpenFF, atribuidos a
[Hahn et al., LiveCoMS 2022](https://doi.org/10.33011/livecoms.4.1.1497); las estructuras no
se copian al repositorio.
