# Validación de MM-GBSA para bromo y yodo: hipótesis

**Estado: BORRADOR PARA INVESTIGAR.** Escrito el 2026-09-23. El propietario
investiga cada hipótesis, completa su apartado «Notas» y decide el orden. Sólo
entonces se prerregistra cada una (`scripts/experiment_manifest.py init`) y se
lanza en el servidor. **Nada de lo que hay aquí está medido salvo lo que dice
«medido»**; lo demás son conjeturas con su forma de refutarlas.

Objetivo: que MolDesign pueda puntuar con MM-GBSA ligandos con Br e I usando
**parámetros propios validados**, no rechazarlos ni copiar un respaldo que ya
sabemos que falla. MM-GBSA sigue `EXPERIMENTAL_NOT_ENABLED`, así que este
trabajo no bloquea 1.0.2. Contexto completo en
[`../backend/audits/MMGBSA_VALIDATION.md`](../backend/audits/MMGBSA_VALIDATION.md).

---

## 0. Punto de partida

### Término no polar (LCPO), medido el 2026-09-23 en 55 ligandos cristalográficos

Error frente a la SASA numéricamente exacta. El fondo (784 átomos pesados no
halógenos) tiene mediana 2,81 Å² y p90 7,25 Å².

| | qué usa hoy | mediana \|error\| |
|---|---|---:|
| OpenMM 8.5.2 (el que viaja) con Br o I | **no tiene parámetros: lanza excepción** | — |
| Amber (sander) con Br o I | respaldo de carbono `C_sp2_2`, r = 1,7 Å | Br 24,6 · I 28,8 Å² |
| diagnóstico: coeficientes del Cl publicado, r = 1,8 Å | — | Br 3,3 · I 1,9 Å² |
| F (Amber y OpenMM, entrada `F`) | — | 1,8 Å² |
| Cl publicado (Weiser, Shenkin y Still 1999) | — | 1,8 Å² |

El respaldo de Amber falla sobre todo por la **clase de conectividad**:
`C_sp2_2` es un carbono con dos vecinos pesados y un halógeno tiene uno.

### Término polar (GBn2), leído en el código y en las topologías el 2026-09-23

- GBn2 sólo tiene parámetros α, β, γ propios para **H, C, N, O y S** (y P en
  ácidos nucleicos). F, Cl, Br e I reciben los valores por defecto
  `[1.0, 0.8, 4.851]` (`customgbforces.py`, `GBSAGBn2Force._default_atom_params`).
- Apantallamiento GBn2: F 0,5 y los demás el valor por defecto, 0,5. Las
  topologías de tleap con `mbondi3` llevan `screen` 0,88 para F y 0,8 para Cl,
  Br e I.
- **Radio GB:** tleap con `mbondi3` asigna **1,5 Å a Br y a I**, el valor por
  defecto (el mismo que al F y al O), y 1,7 Å al Cl. `_mbondi3_radii` de OpenMM
  hace lo mismo. El radio de van der Waals de Bondi es de unos 1,85 Å para Br
  y 1,98 Å para I (verificar la fuente).
- Consecuencia probable, **no medida**: con un radio de Born menor, la
  autoenergía de solvatación sale mayor en valor absoluto, y la penalización de
  desolvatación de un Br o un I se sobreestima.

### Datos disponibles (PDBBind local, ligandos que RDKit lee)

| | ligandos | átomos | dianas distintas | con afinidad de Fase A | unidos a arilo |
|---|---:|---:|---:|---:|---:|
| Br | 89 | 114 | 64 | 23 | 109 de 114 |
| I | 33 | 40 | 19 | 12 | 39 de 40 |

Ya hay 22 topologías de Br/I en el servidor (`~/moldesign-fep/halogenos_trabajo/`).
Las afinidades válidas son sólo las de Fase A: lo que el índice local añadió
desde BindingDB está emparejado por diana, no por ligando (FEP-03-PDBBIND).

---

## 1. Qué significa «validado», para todas las hipótesis

Se fija antes de ajustar nada:

1. **Particiones por diana**, nunca por ligando: entrenamiento, validación y
   prueba sin ninguna diana compartida. La prueba no se mira hasta fijar los
   parámetros.
2. **Tres referencias distintas, cada una para lo suyo:**
   - geométrica: la SASA exacta, para LCPO;
   - termodinámica: energías libres de hidratación experimentales, para la
     solvatación completa (GB + SA);
   - de unión: afinidades de Fase A, sólo para la ordenación final.
3. **Ningún parámetro se elige por su resultado en la prueba.** Es la misma
   regla que impide copiar el respaldo de Amber para el Cl.
4. **No se degrada lo que ya funciona:** los errores de C, N, O, S, F y Cl no
   pueden empeorar.
5. Se registran la versión de OpenMM, AmberTools y RDKit, y los hashes de las
   topologías.

---

## 2. Hipótesis

### H1 — LCPO: los coeficientes del Cl publicado con el radio de Bondi bastan para Br e I

**Enunciado.** Usar los coeficientes P1–P4 del Cl publicado con radios de
1,85 Å (Br) y 1,98 Å (I) aproxima la SASA exacta dentro del error de fondo, sin
reajustar nada.

**Por qué lo creemos.** Con r = 1,8 Å esos coeficientes ya dan 3,3 y 1,9 Å²
(medido). La forma funcional de un halógeno terminal parece transferible; lo
que falta es el radio.

**Cómo se mide.** `backend/audits/lcpo_halogenos.py` con un brazo nuevo por
elemento: coeficientes del Cl y radio de Bondi. Sobre los 122 ligandos con Br
o I y sus particiones por diana.

**Criterio.** Mediana |error| ≤ 2,81 Å² y p90 ≤ 7,25 Å² en validación y en
prueba.

**La refuta.** Un error sistemático con signo (media lejos de 0) o que crece
con el radio.

**Coste.** Unos minutos: la herramienta ya existe.

**Notas del propietario:** _pendiente_

### H2 — LCPO: si H1 falla, basta con reajustar P1–P4 por elemento

**Enunciado.** Un ajuste por mínimos cuadrados de P1–P4 para Br y para I,
contra la SASA exacta del conjunto de entrenamiento, generaliza a validación y
prueba.

**Por qué.** Es como se obtuvieron los parámetros originales de LCPO.

**Cómo se mide.** Ajuste en entrenamiento. Estabilidad de los coeficientes por
bootstrap (100 remuestreos). Error en validación y prueba.

**Criterio.** El de H1 en validación y prueba, y coeficientes con coeficiente
de variación < 20% entre remuestreos.

**La refuta.** Error de prueba mucho mayor que el de entrenamiento
(sobreajuste) o coeficientes inestables.

**Coste.** Horas: la SASA exacta con 50 000 puntos es lo caro.

**Notas del propietario:** _pendiente_

### H3 — GB: el radio de 1,5 Å sobreestima la desolvatación de Br e I

**Enunciado.** Con radios de Born derivados de Bondi (Br ≈ 1,85, I ≈ 1,98 Å)
el error de la energía libre de hidratación calculada (GBn2 + LCPO) frente a
la experimental baja para moléculas con Br e I, sin empeorar el resto.

**Por qué.** El radio actual es el valor por defecto, no un parámetro elegido
para estos elementos. Un radio pequeño hace mayor la autoenergía de Born.

**Cómo se mide.** Un conjunto de hidratación experimental con compuestos
bromados y yodados, por ejemplo FreeSolv (Mobley y Guthrie, 2014; **verificar
la licencia** antes de redistribuir nada). Se compara ΔG_hid calculado frente
a experimental con el radio por defecto, el de Bondi y un barrido en la
partición de entrenamiento.

**Criterio.** El error absoluto medio de Br/I baja de forma significativa
(bootstrap) y el de las moléculas sin Br/I no sube.

**La refuta.** Que el radio por defecto dé igual o menos error, o que el mejor
radio salga muy lejos de cualquier valor físico. Eso indicaría que el radio
está compensando otra carencia, por ejemplo cargas puntuales incapaces de
representar el agujero σ del halógeno.

**Coste.** Bajo en cálculo; el trabajo es curar el conjunto experimental.

**Notas del propietario:** _pendiente_

### H4 — GB: una vez corregido el radio, los α, β, γ y el apantallamiento por defecto bastan

**Enunciado.** El error de H3 no mejora de forma significativa ajustando
además el apantallamiento o α, β, γ.

**Por qué.** GBn2 se ajustó para proteínas (H, C, N, O, S). Para los
halógenos quizá baste el radio, y cada parámetro más es un grado de libertad
que sobreajustar.

**Cómo se mide.** Análisis de sensibilidad sobre la partición de
entrenamiento: variar `screen` y α, β, γ con el radio de H3 fijo. Informar la
mejora en validación.

**Criterio.** Mejora < 10% del error de H3 → se aceptan los valores por
defecto.

**La refuta.** Mejora grande y estable en validación: habría que ajustarlos, y
declararlo.

**Coste.** Horas.

**Notas del propietario:** _pendiente_

### H5 — Implementación: OpenMM y sander coinciden para Br e I en GBn2

**Enunciado.** Con la misma topología, OpenMM reproduce a sander en energía
(≤ 0,001 kcal/mol tras la conversión de constantes documentada) y en fuerzas
(≤ 0,001 kcal/mol/Å), sin el término de superficie.

**Por qué.** Es la precondición de todo lo demás: separa un error de
implementación de uno de física. Para el Cl ya coincidía.

**Cómo se mide.** El procedimiento de `backend/audits/amber_openmm_reference.py`
sobre las 22 topologías de Br e I que ya existen, con `vacuum` y `GBn2_no_SA`.

**Criterio.** 22/22 dentro de tolerancia.

**La refuta.** Cualquier caso fuera de tolerancia se atribuye antes de seguir,
como se hizo con el cloro.

**Coste.** Minutos. **Es la primera que conviene lanzar.**

**Notas del propietario:** _pendiente_

### H6 — Dominio: un solo juego de parámetros por elemento para Br e I en arilo; el alifático queda fuera

**Enunciado.** Br e I unidos a un aromático se describen con un juego por
elemento. Los alifáticos (5 átomos de Br y 1 de I en PDBBind) no se pueden
validar y el producto debe abstenerse con ellos.

**Por qué.** No hay datos para validar el alifático, y validar con 5 átomos
sería un número sin condición.

**Cómo se mide.** Error de H1/H2 estratificado por entorno. Revisar si FreeSolv
aporta bromoalcanos y yodoalcanos suficientes para H3.

**Criterio.** Si con datos externos el alifático cae dentro del fondo con el
mismo juego, se amplía el dominio. Si no, abstención declarada en
`mmgbsa_contrato`.

**Coste.** Bajo.

**Notas del propietario:** _pendiente_

### H7 — Poses: lo validado en cristales vale en poses acopladas

**Enunciado.** El error de LCPO con los parámetros nuevos, medido sobre las
poses de Vina de esos mismos ligandos, sigue dentro del fondo.

**Por qué.** El producto puntúa poses acopladas, no cristales. Una geometría
peor puede cambiar la oclusión.

**Cómo se mide.** Acoplar los ligandos de la partición de prueba con el
protocolo del producto y repetir la medida de H1/H2 en la pose top-1 y en las
que PoseBusters acepta.

**Criterio.** Mediana dentro del fondo en las poses válidas.

**Coste.** Horas a un día de Vina en el servidor, según exhaustividad.

**Notas del propietario:** _pendiente_

### H8 — Orden de magnitud: el radio GB pesa más que LCPO

**Enunciado.** En ΔG de unión, cambiar el radio GB de Br/I (H3) mueve el
resultado al menos diez veces más que corregir LCPO (H1/H2).

**Por qué.** El error LCPO del respaldo son unos 25 Å² × 0,005 ≈ 0,12 kcal/mol
por átomo. Un radio de Born 0,35-0,5 Å más pequeño puede mover la autoenergía
de un átomo cargado en kcal/mol. No medido.

**Cómo se mide.** Descomponer el ΔG de unión MM-GBSA de los complejos de la
partición de prueba en los tres subsistemas, con cada corrección por separado.

**Criterio.** Informar el cociente; si es ≥ 10, el trabajo se concentra en H3/H4.

**Coste.** Horas: sistemas completos receptor-ligando, puerta 3 de MM-GBSA.

**Notas del propietario:** _pendiente_

### H9 — Unión: con parámetros validados, Br e I no ordenan peor que Cl y F

**Enunciado.** Dentro de series congenéricas, la correlación de rangos
(Spearman) entre MM-GBSA y la afinidad de Fase A de los ligandos con Br o I no
es peor que la de sus análogos con Cl o F.

**Por qué.** Es la pregunta de producto: poder puntuar Br e I sin que sean
ciudadanos de segunda.

**Cómo se mide.** Series de FEP-03-PDBBIND que tengan a la vez análogos con
Br/I y con Cl/F y afinidad de Fase A. **Contarlas antes de prometer nada**: con
23 Br y 12 I con afinidad, puede que no alcance. Si no alcanza, H9 queda
declarada como no medible con estos datos.

**Criterio.** Diferencia de ρ dentro del intervalo de bootstrap.

**La refuta.** Br/I sistemáticamente peor. En ese caso se estudia el agujero σ,
que ni GB ni LCPO representan.

**Coste.** Depende de H7 y H8.

**Notas del propietario:** _pendiente_

---

## 3. Orden propuesto

1. **H5** (minutos): si la implementación no coincide, nada más tiene sentido.
2. **H1** (minutos) y, sólo si falla, **H2** (horas).
3. **H3 y H4** (el trabajo es curar el conjunto de hidratación): probablemente
   lo que más importa, según H8.
4. **H6**: declarar el dominio.
5. **H7, H8 y H9**: sistemas completos y poses, en la semana de servidor.

## 4. Lo que el propietario debe decidir antes de lanzar

- La fuente de energías de hidratación experimentales y su licencia (H3).
- Las particiones por diana y la semilla (se fijan una vez y se sellan).
- Si el alifático queda fuera (H6) o se busca más dato.
- Qué hacer si H9 no es medible con los datos disponibles.

## 5. Referencias a revisar

- Weiser, Shenkin y Still (1999), el artículo de LCPO: qué elementos
  parametrizaron y con qué conjunto.
- Nguyen, Roe y Simmerling (2013), GBn2: qué elementos ajustaron y contra qué.
- Mongan et al. (2007), GBn.
- Bondi (1964), radios de van der Waals.
- Manual de Amber: radios `mbondi`/`mbondi2`/`mbondi3` para halógenos y el
  mensaje `Using carbon SA parms`.
- Mobley y Guthrie (2014), FreeSolv (y su licencia).
- Literatura sobre el agujero σ de los halógenos y los modelos implícitos (H9).

## 6. Registro de cambios de este documento

- 2026-09-23 — primera versión: punto de partida medido y nueve hipótesis.
