# Validación de MM-GBSA para bromo y yodo: hipótesis

**Estado: EN MARCHA.** Escrito el 2026-09-23. El propietario investigó las
hipótesis (informe de búsqueda profunda del 2026-09-23, «Viabilidad científica
de MolDesign 1.0.2», fuera del repositorio) y sus conclusiones están en cada
apartado «Notas del propietario». Cada hipótesis se prerregistra
(`scripts/experiment_manifest.py init`) antes de lanzarla. **Nada de lo que
hay aquí está medido salvo lo que dice «medido»**; lo demás son conjeturas con
su forma de refutarlas. Las cifras que el informe cita de fuentes externas
(licencia de FreeSolv, número de moléculas) se verifican antes de usarlas.

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

Ya hay 24 topologías de Br/I en el servidor (`~/moldesign-fep/halogenos_trabajo/`),
de las 55 de la medida LCPO.
Las afinidades válidas son sólo las de Fase A: lo que el índice local añadió
desde BindingDB está emparejado por diana, no por ligando (FEP-03-PDBBIND).

---

## 1. Qué significa «validado», para todas las hipótesis

Se fija antes de ajustar nada:

1. **Particiones sin fuga, según el problema** (corregido con las notas del
   propietario: «por diana» no es una regla universal):
   - problemas **del ligando** (LCPO, solvatación, H1-H4, H6, H10): grupos por
     **scaffold de Bemis-Murcko + entorno químico del halógeno** (arilo /
     alifático). En FreeSolv no hay diana.
   - problemas **de unión** (H7-H9): por **diana o serie congenérica**.
   - 60 % entrenamiento, 20 % validación, 20 % prueba sellada. La prueba no se
     mira hasta fijar los parámetros. La semilla y la asignación se sellan una
     vez y se reutilizan en todas las hipótesis.
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
   topologías. **Entorno congelado durante la campaña:** OpenMM 8.5.2 (el que
   viaja), RDKit 2025.09.6 (la de los sellos FEP), la build de AmberTools del
   contenedor `moldesign-science` como referencia; AmberTools26 sólo como
   reproducción posterior e independiente.
6. **Tres resultados, no dos:** PASA, FALLA e INDETERMINADO. Un dato que falta,
   un cálculo que expira o un dominio sin validar es INDETERMINADO, nunca un
   resultado químico.
7. **Por capas y en orden:** implementación (H5) → superficie (H1/H2) → polar
   (H3/H4) → dominio (H6) → unión (H7-H9). Un parámetro no se ajusta contra
   afinidades mientras una capa anterior esté abierta: es la vía por la que un
   radio compensa el error de otro término.

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

**Prerregistrada el 2026-09-23 como `MMGBSA-H1-LCPO-BONDI`**
(`backend/audits/lcpo_bri_h1.py`). Universo: los 122 ligandos de PDBBind con
Br o I (121 de geometría posible), con las particiones selladas en
`MMGBSA-PARTICIONES-BRI-V1`: 83 grupos de scaffold; validación 20 Br + 6 I
átomos, prueba 27 Br + 13 I. Gate: los criterios de arriba, el sesgo como IC95
del error medio con signo dentro de ±2,81 Å², y «no empeorar a los vecinos»
como comparación pareada con el respaldo de Amber (≤ +0,5 Å² de cota superior;
0,0025 kcal/mol por átomo). Un piloto de 5 ligandos, declarado, mostró que un
umbral absoluto para los vecinos fallaba en los tres brazos por igual; por eso
se volvió al «no empeorar» del apartado 1.

**Resultado, medido el 2026-09-23 (sellado): NO_GO.** 117 de 121 ligandos
medidos (4 fallos que no son del halógeno, abajo).

| brazo H1 (Cl publicado + Bondi) | validación | prueba |
|---|---|---|
| Br: mediana / p90 / IC95 del sesgo (Å²) | 0,70 / 6,90 / [−3,14, −0,40] | 3,40 / 9,44 / [−3,03, +3,35] |
| I: mediana / p90 / IC95 del sesgo (Å²) | 4,71 / 6,49 / [−5,82, −1,32] | 4,57 / 5,36 / [−4,81, −1,33] |

- **El yodo lo refuta con la firma que se había anticipado:** un sesgo
  negativo sistemático que **crece con el radio**. Con r = 1,8 el mismo
  conjunto de coeficientes se equivoca menos que con el Bondi de 1,98 en las
  tres particiones (prueba: mediana 3,62, media −2,95). La forma funcional del
  cloro no se traslada a una esfera mayor.
- El bromo pasa mediana y p90 en validación, pero no el sesgo, y en prueba
  falla los tres: la calidad depende mucho del scaffold (el IC de prueba va de
  −3 a +3).
- **Los vecinos no empeoran:** con H1 los átomos que solapan con Br/I mejoran
  0,20-0,23 Å² frente al respaldo de Amber, en las tres particiones.
- El respaldo de Amber (`C_sp2_2`) sigue fuera por 24-31 Å².
- **Cuatro fallos que no son del halógeno:** tres `=CH2` vinílicos terminales
  para los que el OpenMM 8.5.2 que viaja **no tiene parámetro LCPO** (el
  MM-GBSA candidato no puede puntuar hoy un alqueno terminal), y un alquino
  terminal al que el SDF de PDBBind le quitó el H.

Siguiente, según el orden declarado: H2 con H10.

**Notas del propietario (informe 2026-09-23):** «prometedora», la más
prometedora de 1.0.2. Se prueba **sin ajuste**. Que Bondi publicara esos radios
como radios de van der Waals no dice que sirvan para LCPO: eso es justo lo que
se falsa. Criterios añadidos: Br e I pasan **por separado**; el sesgo con signo
tiene un IC bootstrap al 95 % compatible con cero; partición por scaffold y
entorno; y ningún elemento que ya pasaba (C, N, O, S, F, Cl) empeora.

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

**Prerregistrada el 2026-09-23 como `MMGBSA-H2-LCPO-AJUSTE`** (con H10), en
`backend/audits/lcpo_bri_h2.py`. El radio queda en el de Bondi: define la esfera
cuya SASA se aproxima, así que no tiene objetivo ajustarlo. El área LCPO de un
átomo es lineal en sus propios P1-P4, de modo que el ajuste es un mínimo
cuadrado exacto sobre los términos que calcula la implementación validada.

**Cambio de criterio, declarado antes de ajustar con datos reales.** Un piloto
**sólo de entrenamiento** mostró que los cuatro términos están casi alineados
(número de condición ~1e4): CV de P3 94 % en Br y 997 % en I, mientras el área
predicha varía < 1 Å² entre remuestreos. Con un objetivo sintético sin ruido
(el área del Cl publicado) el CV de P3 del I sigue en 303 %. Un CV < 20 % en
cada coeficiente no puede cumplirse y no mide el ajuste; se sustituye por CV de
P1 < 20 % y desviación del área predicha ≤ 1 Å². Y se añaden dos brazos
—completo (P1-P4) y reducido (P1, P2 con P3, P4 del Cl)—, elegidos en
validación con una regla de parsimonia fijada antes (el reducido salvo que el
completo mejore la mediana más de 0,5 Å²); la prueba sólo confirma.

**Resultado, medido el 2026-09-23 (sellado): NO_GO, 2 de 4 casos fallan.**

| | brazo elegido en validación | validación | prueba |
|---|---|---|---|
| Br | reducido: P1 0,962, P2 −0,391 (casi los del Cl) | **pasa** (mediana 0,94, p90 4,85) | falla (mediana 2,96, p90 9,70, IC del sesgo [−1,6, +4,0]) |
| I | completo (el reducido daba 5,9 en validación) | falla sólo el sesgo (IC [−3,07, +0,66], 6 átomos) | **pasa** (mediana 1,83, p90 4,04) |

H10: el Br generaliza entre scaffolds (0,94 frente a 1,70 en una partición
aleatoria); el I falla por 0,05 Å² sobre el margen, con 8 átomos.

**Diagnóstico exploratorio, después del sello (no elige nada):** la cola del Br
en prueba aparece con cualquier juego de coeficientes (H1: p90 9,44; completo:
9,83), así que no la arregla ajustar P1-P4. Sus errores positivos grandes son
**anillos polibromados** —4 o 5 Br en el mismo anillo: 1zoh, 2oxd, 2oxx,
5owl, 5cqu, 1e4h, la familia de inhibidores de CK2 tipo TBB—, donde dos Br
vecinos en orto se solapan más de lo que la aproximación por pares de LCPO
representa. Los negativos grandes son Br únicos muy rodeados (2h4k, 2qbp). En
conjunto, **el error crece con el enterramiento** (Spearman entre |error| y
fracción expuesta −0,46, p = 4e-7). Dos consecuencias:

1. Una regla de dominio («nada de Br/I vecinos en un anillo») sería razonable,
   pero ya no se puede validar con la prueba de PDBBind, que se ha mirado. Para
   validarla hace falta un conjunto nuevo; como LCPO es una aproximación
   geométrica, sirven confórmeros generados de moléculas con Br/I que no estén
   en PDBBind.
2. En un complejo, el halógeno suele quedar **enterrado en el bolsillo**, justo
   donde LCPO se equivoca más. Antes de seguir ajustando LCPO conviene medir la
   alternativa: calcular el término no polar del MM-GBSA de reemplazo con una
   SASA numérica al puntuar (el MM-GBSA del producto sigue siendo el legacy;
   el término no polar del reemplazo aún no está decidido). Ver H12.

**Notas del propietario (informe 2026-09-23):** viable para Br, más arriesgada
para I por el tamaño de muestra. Bootstrap de 100 a 1000 remuestreos **por
scaffold**, no por átomo; los parámetros se congelan antes de abrir la prueba,
y la mejora en prueba tiene que ser coherente con la de validación.

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

**Notas del propietario (informe 2026-09-23):** «plausible, no demostrada».
**Un radio de van der Waals y un radio efectivo de Born no son lo mismo**:
Bondi es un candidato físico, no un valor correcto a priori. Cambios al plan:

- **Dos niveles de referencia.** Primero GBn2 contra una referencia de
  continuo —PBSA de AmberTools sobre exactamente las mismas geometrías— para
  aislar el radio de la conformación; después FreeSolv como prueba
  termodinámica externa. No se convierte una sola energía estática GB+SA en
  «ΔG de hidratación» sin controlar conformaciones.
- **Brazos, fijados antes de medir:** A = respaldo actual (1,5 Å); B = Bondi
  (Br 1,85, I 1,98); C = malla alrededor de B, sólo en entrenamiento; D = C +
  apantallamiento; E = D + α, β, γ, sólo si D aporta una mejora robusta.
- **Criterios:** el MAE de Br/I baja ≥ 20 % frente al respaldo en validación;
  el IC bootstrap al 95 % de MAE_nuevo − MAE_respaldo queda por debajo de cero;
  los controles (F, Cl y no halogenados de propiedades parecidas) empeoran
  ≤ 0,2 kcal/mol; y se confirma en la prueba sellada. Son márgenes propuestos
  para MolDesign, no límites de GBn2.
- **FreeSolv:** filtrar Z = 35 y 53 con RDKit y congelar la versión. El
  informe dice que los datos son CC-BY 4.0 «en la medida en que los autores
  pueden otorgarla» y que hay 642 moléculas: **verificar en el repositorio de
  FreeSolv antes de descargar nada**.

**Límite de la malla, leído en el código el 2026-09-23 (no en el informe):**
GBn y GBn2 interpolan la integral del cuello en una tabla de radios de 1,0 a
2,0 Å, y OpenMM rechaza cualquier radio fuera de ese intervalo («Radii must be
between 1 and 2 Angstroms for neck lookup»; `customgbforces.py`). El Bondi del
yodo (1,98 Å) está en el borde: **la malla C no puede pasar de 2,0 Å** sin
cambiar de modelo GB.

**Segunda ronda de notas del propietario (2026-09-23).** Bondi (1964) confirma
Br 1,85 e I 1,98 Å; Rowland-Taylor y Mantina no dan alternativas independientes
para Br/I. Los radios PB optimizados con punto extra para el agujero σ
(Fortuna y Costa 2021, DOI 10.1021/acs.jcim.1c00177: Br 2,3-2,8 Å, I 2,5-3,1 Å)
son parámetros de cavidad de otro modelo electrostático y **no caben en GBn2**,
cuya tabla del cuello sólo admite 1-2 Å; HCT/OBC no tienen esa tabla, pero
habría que recalibrarlos. FreeSolv v0.52 (DOI 10.5281/zenodo.1161245): datos
CC BY 4.0 y código MIT (verificado en el repositorio), 25 moléculas con Br (21
sólo Br) y 12 con I, incertidumbre mediana 0,6 kcal/mol. MNSol tiene licencia
comercial de pago y no se usa. Una guía que acompañaba al informe decía que
FreeSolv es MIT o CC0 y que ejecutar sander viola la GPL: las dos cosas son
falsas (ejecutar no es distribuir), y se descartó como fuente.

**Prerregistrada el 2026-09-23 como `MMGBSA-H3-FREESOLV-RADIOS`**
(`backend/audits/freesolv_h3.py`), con el diseño del informe y una salvaguarda
contra la compensación: el término no polar (γ·SASA + b, FreeSASA) se ajusta
**sólo con las moléculas sin halógeno**, y los brazos A (1,5 Å) y B (Bondi) no
ajustan nada en Br ni en I. Curación declarada: FreeSolv escribe los 37 nitro de
sus SDF como `N(–O⁻)(–O⁻)`; se corrigen a `[N+](=O)[O-]` y los 37 recuperan el
InChIKey del SMILES.

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

**Notas del propietario (informe 2026-09-23):** «excelente hipótesis nula:
limita grados de libertad y sobreajuste». Es la comparación D/E frente a B/C
de H3.

### H5 — Implementación: OpenMM y sander coinciden para Br e I en GBn2

**Enunciado.** Con la misma topología, OpenMM reproduce a sander en energía
(≤ 0,001 kcal/mol tras la conversión de constantes documentada) y en fuerzas
(≤ 0,001 kcal/mol/Å), sin el término de superficie.

**Por qué.** Es la precondición de todo lo demás: separa un error de
implementación de uno de física. Para el Cl ya coincidía.

**Cómo se mide.** El procedimiento de `backend/audits/amber_openmm_reference.py`
sobre las topologías de Br e I que ya existen, con `vacuum` y `GBn2_no_SA`.
Herramienta: `backend/audits/gbn2_paridad_halogenos.py`. Son **24**, no 22: el
22 contaba sólo los ligandos con un único tipo de halógeno (2ax9 y 5aol llevan
Br y F). Las 31 de F y Cl se miden como control.

**Criterio.** 24/24 dentro de tolerancia.

**La refuta.** Cualquier caso fuera de tolerancia se atribuye antes de seguir,
como se hizo con el cloro.

**Coste.** Minutos. **Es la primera que conviene lanzar.**

**Notas del propietario (informe 2026-09-23):** «muy viable y debe ser
primero»: separa errores de implementación de errores de física. Misma prmtop,
mismas coordenadas, sin minimizar, sin término de superficie, OpenMM en
`Reference`. Si falla uno, no se pasa a parametrizar.

**Piloto (3 ligandos, 2026-09-23, antes del prerregistro) y cambio de
criterio declarado antes de la corrida completa.** 1e4h (5 Br) y 2ax9 (Br + F)
pasan con residuos de 4e-8 y 2e-6 kcal/mol. **1c5n (I) no pasa en GBn2**
(9,9e-3 kcal/mol; el vacío sí pasa), pero los átomos con más error de fuerza
son el **S** y sus vecinos, no el I. En la tabla GBn2 de OpenMM el azufre es
el único elemento con apantallamiento negativo (−0,703469; que Amber use el
mismo valor no está leído en su fuente, sólo es coherente con lo que sigue).
Prueba decisiva: el mismo prmtop con el número atómico del S cambiado a 34 (sin
parámetros GBn2 propios en ningún programa) recupera la paridad en ambos a la
vez (8,3e-7 kcal/mol). Por eso el gate queda así, fijado antes de ver las 55:
una topología de Br/I pasa si pasa en las dos condiciones **o** si lleva S, el
vacío pasa y el desacuerdo desaparece con el S genérico. Un fallo que no se
atribuya así es un NO GO. El OpenMM de esta máquina (el Python que se entrega)
reproduce al de Linux en 3,6e-15 kcal/mol sobre las mismas topologías; se
exige < 1e-6.

**Lo que el piloto abre y no es de halógenos:** si el S discrepa, lo hace
también en las metioninas y cisteínas de cualquier receptor. Es un pendiente de
la puerta 3 de `MMGBSA_VALIDATION.md`, no de este documento.

**Resultado, medido el 2026-09-23 (`MMGBSA-H5-GBN2-PARIDAD`, sellado): NO_GO
por la letra del gate, 23/24.**

| | topologías | pasan directas | con S, atribuidas al S | sin atribuir |
|---|---:|---:|---:|---:|
| Br o I | 24 | 19 | 4/4 | **1 (5mlj)** |
| control F / Cl | 31 | 23 | 8/8 | 0 |

- Las 19 directas: residuo ≤ 2e-6 kcal/mol, fuerza ≤ 1,1e-4 kcal/mol/Å. Br e
  I reciben en los dos programas radio 1,5 Å, apantallamiento 0,5 y α, β, γ
  por defecto, y calculan lo mismo con ellos.
- **5mlj no es el bromo:** el SDF de PDBBind trae el H22 a 0,259 Å de C13
  (ángulo C13–C17–H22 = 1,2°). Toda la diferencia de vacío (3,88 kcal/mol) está
  en el término de ángulo. El gate no preveía una geometría imposible y no se
  cambia después de medir: se repite como `MMGBSA-H5-R1` con un filtro de
  validez geométrica declarado antes.
- **El azufre en GBn2 discrepa hasta 11,24 kcal/mol** (2weg, una sulfonamida;
  4,87 en 5eij, con dos S), y siempre desaparece con el S genérico. Con cargas
  AM1-BCC, más polarizadas que las Gasteiger de estas topologías, puede ser
  mayor. No bloquea Br/I; sí la puerta 3 (receptores con Met y Cys).
- **Windows reproduce a Linux:** el OpenMM del Python que se entrega da lo
  mismo que el del servidor en 110/110 comparaciones con las mismas entradas
  (8,5e-14 kcal/mol, 1,6e-13 kcal/mol/Å).

**Réplica con filtro geométrico (`MMGBSA-H5-R1`, sellada): GO.** Filtro
declarado antes de medir: dos átomos a < 0,5 Å o un ángulo de valencia < 30°
hacen la topología INDETERMINADA. Marca dos de 55, y en las dos el SDF de
PDBBind **añade un H a un carbono sp2 halogenado** (5mlj con Br, 6gnp con Cl).

| | pasan | fallan | indeterminadas |
|---|---:|---:|---:|
| Br o I (24) | 23 | 0 | 1 (5mlj) |
| control F / Cl (31) | 30 | 0 | 1 (6gnp) |

Con el H sobrante recolocado (perpendicular al plano), 5mlj coincide en
6,0e-6 kcal/mol y 6gnp en 6e-9: el fallo de H5 queda atribuido entero a la
geometría. **Conclusión con su límite:** con los mismos parámetros (radio
1,5 Å, apantallamiento 0,5, α, β, γ por defecto) OpenMM y sander calculan lo
mismo para Br e I, así que H1-H4 pueden atribuir un error a la física y no a
la implementación. No dice que esos parámetros sean buenos. Y deja dos cosas
para el resto de la campaña: la curación de H1 aplica el mismo filtro, y el
producto debería abstenerse ante un H sobre un carbono sp2 (pendiente).

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

**Notas del propietario (informe 2026-09-23):** «muy razonable». Publicar
primero «Br/I aromático, validado dentro del dominio» y **rechazar
explícitamente** los alifáticos es más defendible que fingir universalidad. El
backend no debe preguntar sólo «¿puedo calcularlo?» sino «¿está dentro del
dominio validado?»: un conjunto de parámetros versionado
(`moldesign-mmgbsa-halogen-v1`, con dominio, fuente del LCPO y fuente del radio
GB por elemento), cada átomo de Br/I declara qué parámetro recibió y por qué, y
**ningún respaldo silencioso**. Los códigos de error propuestos
(`MMGBSA_HALOGEN_OUT_OF_DOMAIN`, `MMGBSA_PARAMETER_SET_MISSING`) se conservan en
informe y registro; el usuario lee la explicación en su idioma.

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

**Notas del propietario (informe 2026-09-23):** necesaria, porque es el uso
real del producto. Vina con semilla, exhaustividad, caja y versión
registradas; la medida se repite en las poses top-1 estructuralmente
aceptables. Recordatorio propio: la evidencia sellada del ensemble es exh=8 y
el producto corre 32; aquí se usa la del producto.

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

**Notas del propietario (informe 2026-09-23):** «plausible, pero debe medirse
y no asumirse».

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

**Notas del propietario (informe 2026-09-23):** correcta como pregunta y
«probablemente subpotenciada». La métrica es ordenación **dentro** de series,
nunca correlación global mezclando dianas; si no hay suficientes
comparaciones Br/I frente a F/Cl, H9 queda INDETERMINADA. Eso es mejor ciencia
que una conclusión sacada de 12 yodados.

### H10 — Generalización química: lo que vale entre scaffolds vale fuera de ellos

**Enunciado.** Un parámetro ajustado en H2 o H3 que generaliza por scaffold
(entrenamiento y prueba sin scaffolds compartidos) no pierde más que el
margen de H1 frente a su error dentro de los scaffolds de entrenamiento.

**Por qué.** Propuesta del informe: evita la fuga química en H2 y H3. Un
parámetro que sólo funciona en los scaffolds que vio es un parámetro de esos
scaffolds.

**Cómo se mide.** Error de validación con partición por scaffold frente a una
partición aleatoria por molécula, con los mismos datos.

**La refuta.** Un error por scaffold claramente mayor que el aleatorio: los
parámetros han memorizado familias químicas.

**Coste.** Nulo aparte: es la misma corrida de H2/H3 con dos particiones.

### H12 — El término no polar del reemplazo se calcula con una SASA numérica, no con LCPO

**Enunciado.** Para puntuar poses ya minimizadas, una SASA numérica
(Shrake-Rupley o Lee-Richards) con radios de Bondi da el término no polar de
Br e I —y del resto de elementos— sin parámetros por elemento, con un coste
asumible para el producto, y elimina la clase de error que H1 y H2 midieron
(solapes de esferas grandes y átomos enterrados).

**Por qué.** Nueva, tras H2. LCPO existe para dar fuerzas analíticas durante
una dinámica; el MM-GBSA de MolDesign puntúa estructuras fijas. Si la
minimización se hace con GB y el término de superficie se añade al final, no
hace falta derivar la superficie.

**Cómo se mide.** (a) Coste: tiempo de una SASA numérica de receptor, ligando y
complejo con la precisión necesaria (la malla que da < 0,1 Å² por átomo), en
el Python que se entrega. (b) Qué cambia: ΔG_SA de unión con LCPO frente a SASA
numérica en complejos de PDBBind con y sin Br/I. (c) Si la minimización sin
término de superficie cambia la pose de forma apreciable.

**Viabilidad, medida el 2026-09-23 (exploratoria, sin sellar).** La RDKit
2025.09.6 del Python que se entrega trae `rdFreeSASA` (FreeSASA, algoritmo de
Lee-Richards): no hace falta ninguna dependencia nueva. Con los radios de Bondi
y H a 0 (la convención de LCPO), en el ligando de 1zoh (4 Br, el peor caso de
H2) da 437,80 Å² frente a 438,09 de la SASA exacta a 50 000 puntos, con
≤ 0,43 Å² por átomo (los cuatro Br: 65,9/66,1, 59,3/59,7, 60,6/60,4,
59,7/59,6), en menos de 1 ms; el receptor entero (11 582 átomos), en 0,22 s.
LCPO se equivocaba en esos Br en +10 a +12 Å².

**Notas del propietario (segunda ronda).** FreeSASA es MIT: puede viajar como
componente separado de un producto PolyForm NC conservando su aviso (hoy la
RDKit que viaja lo lleva enlazado y el aviso falta: pendiente). MMPBSA.py usa
LCPO por defecto y admite `molsurf=1` (verificado en el `input_parser.py` del
contenedor). No hay en la literatura un error de LCPO medido para Br o I: lo
midieron H1 y H2. Si se cambia de LCPO a FreeSASA, γ debe recalibrarse.

**H12a, medida el 2026-09-23 (`MMGBSA-H12A-FREESASA`, sellada): NO_GO por la
letra del gate.** Por átomo, FreeSASA frente a la SASA exacta en 3088 átomos:
mediana 0,14 Å², p95 **0,55** (tope 0,5) y máximo **1,22** (tope 1,0); Br p95
0,64, I p95 0,55; 0,55 ms por ligando. El techo lo pone la resolución por
defecto de Lee-Richards, que la RDKit no expone. No se reformula el gate: un
criterio energético diseñado después de ver los datos pasaría por
construcción. Como caracterización: el error es unas 20 veces menor que el de
fondo de LCPO y que el de LCPO en Br/I, y en energía no llega a 0,01 kcal/mol
por átomo. La elección para el producto se apoya en esa comparación y en H3,
que usa FreeSASA dentro del modelo completo.

**Criterio de la parte en complejos (H12b).** Por fijar.

**Coste.** Bajo en cálculo; el trabajo es de diseño del protocolo.

### H13 — OpenMM calcula el GBn2 de Amber también con azufre

**Enunciado.** Reescribir las expresiones GBn2 de OpenMM con las ramas de
`egb.F90` hace que OpenMM reproduzca a sander también con S, sin romper lo
que ya coincidía.

**Por qué.** H5 encontró hasta 11,24 kcal/mol de desacuerdo en toda topología
con S. La fuente de Amber (AmberClassic `src/msander/egb.F90`, leída el
2026-09-23) lo explica: `sj = fs(j)` lleva el signo del apantallamiento, el del
S es negativo, `dij > four*sj` se cumple siempre y Amber usa **siempre** su
serie de Taylor para el S; OpenMM evalúa la integral cerrada. Además Amber
corta en `rgbmax` (25 Å con igb=8) y OpenMM no. El informe del propietario
(2026-09-23) coincide: Amber es la referencia porque GBn2 se parametrizó con
ese código, y cita el issue #1491 de OpenMM (NaN con `igb=8`).

**Cómo se mide.** `backend/audits/gbn2_azufre_amber_h13.py` con
`apply_amber_gbn2_descreening` (protocolo candidato, no producción) sobre las
55 topologías y dos péptidos ff14SB con Met y Cys, uno de 56 Å.

**Piloto (5 casos, declarado).** ACE-Met-Cys-NME: OpenMM 8.5.2 se separa de
sander **0,92 kcal/mol**; con las ramas de Amber, 1,6e-6. 2weg: 11,2 → 1,6e-6.
Sin S (1e4h) no cambia (4e-8). Sin rgbmax, el péptido largo deja 4,1e-3: hacen
falta las dos piezas.

**Resultado, medido el 2026-09-23 (`MMGBSA-H13-AZUFRE-AMBER`, sellado): GO.**

| | casos | pasan sin la corrección | pasan con ella | residuo máximo antes → después |
|---|---:|---:|---:|---|
| con S | 14 | 0 | 14 | 11,24 → 1,3e-5 kcal/mol |
| sin S, geometría posible | 41 | 41 | 41 | 2,0e-5 → 2,0e-5 |
| péptidos ff14SB con Met y Cys | 2 | 0 | 2 | 0,92 → 1,6e-6 |

El OpenMM de Windows reproduce al de Linux en 57/57 (7e-14). **Consecuencia:**
el MM-GBSA candidato sobre OpenMM no calculaba el GBn2 parametrizado en
cuanto había una metionina o una cisteína —es decir, en casi cualquier
receptor—; con `apply_amber_gbn2_descreening` sí. Queda como prueba de
regresión con el runtime embebido (`backend/tests/test_gbn2_azufre_como_amber.py`,
referencia en `backend/audits/amber_reference_azufre/`). No conecta nada a producción.

### H11 — El agujero σ no se arregla con radios

**Enunciado.** Si, con H1-H5 superadas, queda un error de Br/I concentrado en
geometrías de enlace de halógeno (C–X···aceptor casi lineal), su origen es
electrostático —el agujero σ, que las cargas puntuales no representan— y **no
debe corregirse moviendo radios** GB ni coeficientes LCPO.

**Por qué.** Propuesta del informe. Los halógenos pesados tienen una
distribución de carga anisótropa; hay campos de fuerza que la modelan con un
punto de carga extra. Ajustar un radio hasta que la afinidad «salga bien»
escondería esa carencia detrás de un parámetro compensatorio.

**Cómo se mide.** Dos conjuntos de estrés que **no se usan para ajustar**:
complejos bromados de CK2 (los del estudio con σ-hole explícito) y la lisozima
T4 con iodobenceno e iodopentafluorobenceno. Error residual frente al ángulo
C–X···aceptor.

**Criterio.** Sin correlación con la geometría de enlace de halógeno → no hay
evidencia de un problema de σ-hole con estos datos. Con correlación → se
declara como límite del dominio y se abre para 1.0.3 o después; **no** se
implementa un punto extra en 1.0.2.

**Coste.** Bajo en cálculo; el trabajo es identificar las estructuras (las
referencias concretas del informe están por localizar).

---

## 3. Orden propuesto

1. **H5** (minutos): si la implementación no coincide, nada más tiene sentido.
   **Cerrada, GO** (`MMGBSA-H5-R1`, tras un NO_GO de H5 por una entrada
   imposible).
2. **H1** (minutos): **cerrada, NO_GO** (el yodo, con sesgo que crece con el
   radio). Por tanto **H2** (horas), con **H10** en la misma corrida:
   **cerrada, NO_GO** (el Br falla en prueba por anillos polibromados; el I
   falla por poco el sesgo en validación). Antes de otra ronda de LCPO, **H12**.
3. **H3 y H4**: primero contra PBSA en las mismas geometrías, después FreeSolv.
4. **H6**: declarar el dominio.
5. **H7, H8, H9 y H11**: sistemas completos y poses, en la semana de servidor.

## 4. Decisiones

Tomadas por el propietario (informe 2026-09-23):

- Particiones por scaffold + entorno para el ligando y por diana/serie para la
  unión; 60/20/20.
- Referencia polar en dos niveles: PBSA, después FreeSolv (licencia por
  verificar).
- El alifático queda fuera hasta que datos externos lo validen (H6).
- Si H9 no es medible, queda INDETERMINADA; no se fuerza una conclusión.
- Si Br/I no pasa, sigue desactivado **sin bloquear 1.0.2**.

- Particiones de los ligandos de PDBBind con Br/I selladas el 2026-09-23
  (`MMGBSA-PARTICIONES-BRI-V1`, semilla 20260923). FreeSolv tendrá las suyas.

Pendientes:

- Localizar las estructuras de los conjuntos de estrés de H11.

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
- 2026-09-23 — notas del propietario (informe de búsqueda profunda) en cada
  hipótesis; particiones por scaffold para el ligando; PBSA antes de FreeSolv;
  brazos y criterios de H3; límite de 1-2 Å de la tabla del cuello de GBn2;
  H10 y H11 nuevas; H5 son 24 topologías, con su piloto y el gate declarado
  antes de la corrida completa.
- 2026-09-23 — H5 sellada (NO_GO 23/24 por 5mlj) y su réplica R1 con filtro
  geométrico (GO 23/23 evaluables). El azufre discrepa en GBn2 hasta
  11,24 kcal/mol.
- 2026-09-23 — particiones selladas y H1 sellada: NO_GO.
- 2026-09-23 — H2 sellada (NO_GO), diagnóstico exploratorio de la cola del Br y H12 nueva.
- 2026-09-23 — segunda ronda de notas del propietario (radios, FreeSolv, término no
  polar, azufre, H11); H13 nueva y sellada: GO.
