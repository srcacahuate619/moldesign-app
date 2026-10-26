# FEP-09-R1 — prerregistro

Fijado el 2026-10-11, antes de la primera corrida, en el commit que añade este documento y
`scripts/artifacts_science/FEP-09-R1/registered_conditions.json`. Lo escribe Claude, a petición
del propietario, sobre el experimento de Sol `FEP-09-SENSIBILIDAD` (INCONCLUSIVE), integrado
en `9719c005`.

## Por qué hay un R1

FEP-09 midió la pestaña Preparación con un defecto dentro: **P01**. La comprobación del origen
no reconocía la receta de los receptores propios, así que las 127 auditorías del camino B se
midieron desde la caja (`entorno.referencia` NO_EVALUADO en 127 de 127). P01 está arreglado en
`f0e64086`. Las conclusiones de FEP-09 que pueden depender de la referencia son tres:

1. **Huecos en el sitio (15/15, la única categoría con GO).** Un corte es crítico según su
   distancia al ligando si se pudo medir, y a la caja si no. El GO de FEP-09 se obtuvo con la
   caja.
2. **Agua puente y protonación del sitio (límites L03 y L04).** En la revisión de FEP-09 escribí
   que P01 los confundía. Leyendo el código ahora creo que no:
   - L03: el agua se borra **antes** de subir el archivo, así que no está en el origen ni en
     `species_diff`, se mida desde donde se mida;
   - L04: en el camino B, `receptor.protonacion` es rutinaria por diseño
     (`RUTINA_PROTONACION_USUARIO`), haya o no una His junto al ligando.

   Eso es una lectura del código, no una medida, y R1 la mide.
3. **Cadena del sitio ausente (L01, n=1)** depende de las distancias al ligando.

Además, la estereoquímica quedó con n=3, por debajo del mínimo de 8 que pide el gate.

## Qué se mide

Lo mismo que FEP-09, salvo lo que se declara aquí:

- **Producto:** `ee2d6c78`, que es `f0e64086` (P01) más el arreglo de Evaluación de los
  caminos B y C. Ese arreglo no toca Preparación: cambia el aviso de aguas, el supuesto del
  dossier, los archivos del visor y las interacciones.
- **Condiciones:** camino B (`respetar`), Vina 1.2.7, exhaustividad 8, 9 poses, semilla 42,
  pH 7,4 y un confórmero. El modo tautomérico no se fuerza; el efectivo es «entrada», el que
  la API aplica por defecto desde `039d9858`. FEP-09 lo llamó «canónico» por error.
- **Inventario:** los 127 casos de FEP-09, idénticos byte a byte (RDKit 2025.09.6, el mismo
  que FEP-09), más 36 nuevos de estereoquímica:
  - por diana, hasta 3 ligandos con algún estereocentro asignado, en el orden del SDF;
  - cada ligando nuevo lleva su línea base (`<diana>__baseline_estereo__<registro>`) y su
    variante, que borra la asignación del primer estereocentro, como en FEP-09;
  - receptor, cadena y caja son los de la diana en FEP-09.

  Resultado: **n=21 en 7 dianas** (cdk8, eg5, hif2a, p38, shp2, thrombin, tyk2).
- **Arnés:** `fep09_inputs.describe`, `fep09_run.run_case` y `fep09_analyze.analyze` sin
  cambios (sellados en FEP-09), envueltos por `scripts/fep09r1_inputs.py`, `fep09r1_run.py`,
  `fep09r1_register.py` y `fep09r1_analyze.py`.
- **Ejecución:** tres cápsulas de QA (agentes 6, 7 y 8; Vina con 4 núcleos) desde el worktree
  `.worktrees/fep09r1`, congelado en el commit de este prerregistro. Sol corre MET-01 a la vez
  en la cápsula 1: la carga cambia los tiempos, no los resultados de Vina con semilla fija.
- **Piloto:** `cdk2__baseline__0`, `cdk8__baseline_estereo__1` y `cdk8__estereo_sin_asignar__1`.
  Va aparte y no entra en las tasas.

## Gate (idéntico al de FEP-09)

- **Detección:** una variante cuenta si sube el riesgo de su requisito esperado respecto a su
  línea base, con el mínimo de FEP-09. Por ejemplo, `receptor.huecos` tiene que llegar a
  ABSTENCIÓN. Una alerta ya presente en la base no cuenta.
- **Categoría declarada con n≥8:** límite inferior del IC exacto bilateral 95 % de
  Clopper–Pearson ≥ 0,5, y falsa alarma de la renumeración inocua ≤ 0,10.
- **Categorías con n<8:** INCONCLUSIVE.
- **Global:** NO_GO si alguna declarada falla; GO sólo si todas pasan; si no, INCONCLUSIVE.
- **Parada:** si fallan más del 30 % de las corridas por infraestructura.

**La decisión global será INCONCLUSIVE por construcción.** «Tautómero minoritario» y «especie
del ligando» siguen con n=0, porque no hay poblaciones ni pKa independientes, y R1 no las
añade. El resultado de R1 son las decisiones por categoría y las lecturas de abajo.

## Lo que añade el análisis (preregistrado)

1. **Referencia:** estado de `entorno.referencia` en cada auditoría.
2. **Frente a FEP-09:** para cada caso común, la clasificación de su requisito esperado en los
   dos experimentos.
3. **Estereoquímica por diana:** los 21 casos son 3 por diana, así que se publica también cómo
   se reparten las detecciones.

## Predicciones

Se publican aciertos y fallos. No cambian el gate.

| # | Predicción |
|---|---|
| P1 | `entorno.referencia` REGISTRADO en todas las auditorías (FEP-09: 0 de 127). |
| P2 | `hueco_en_el_sitio`: GO otra vez (≥ 12 de 15), ahora midiendo desde el ligando. |
| P3 | `agua_puente_retirada`: 0 de 9. Es un límite de alcance, no un efecto de P01. |
| P4 | `protonacion_del_sitio`: 0 de 5. Es rutinaria por diseño en el camino B. |
| P5 | `estereo_sin_asignar`: GO (≥ 16 de 21). |
| P6 | Falsa alarma de la renumeración ≤ 0,10. |

## Potencia, calculada antes de medir

Con la misma función de Clopper–Pearson del analizador:

| Categoría | n | k mínimo para GO | P(GO) si la sensibilidad real es 0,7 | 0,8 | 0,9 | 0,95 |
|---|---:|---:|---:|---:|---:|---:|
| `hueco_en_el_sitio` | 15 | 12 | 0,297 | 0,648 | 0,944 | 0,995 |
| `estereo_sin_asignar` | 21 | 16 | 0,363 | 0,769 | 0,986 | 1,000 |

## Reglas

1. No se cambia el producto ni el arnés durante la medición. Si algo hubiera que cambiar,
   va como desviación declarada en `protocol_deviations.json`, nunca en silencio.
2. El sello lleva los binarios con rutas `tools/vina/…` y `python-embed/…`, enlazadas en el
   worktree, no `../../`.
3. Nada fuera de `scripts/` y `docs/`, salvo regenerar el registro científico al cerrar.
4. Los datos de OpenFF no se copian: hashes y resultados (CC BY 4.0, Hahn et al., LiveCoMS
   2022).
5. Se mantienen las reglas de honestidad de FEP-09: todo número con su condición, nada de
   generalizar a «problemas reales», nada de «FEP-ready» ni «compatible con FEP+».
