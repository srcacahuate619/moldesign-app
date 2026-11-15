# Encargo: ampliar «especie en revisión» (D-04) — investigación científica

**Fecha del encargo:** 2026-11-15
**Commit anclado:** `ffddd7e9` (rama `codex/release-hygiene`, sin empujar)
**Para:** un modelo o investigador dedicado a esta tarea. No hace falta contexto de ninguna conversación previa.
**Idioma de los entregables:** castellano.
**Plan de implementación (lo hace otra persona, con tu entrega):** [`docs/auditorias/plan-d04-especie-en-revision-2026-11-15.md`](../auditorias/plan-d04-especie-en-revision-2026-11-15.md)

## 0. Qué se te pide, en una frase

Decir, con evidencia verificable, **cuáles entornos químicos de una amina deben pasar a «especie en revisión»** (hoy el producto les da un pKa que
no les corresponde) y **con qué patrón se reconocen sin dar falsas alarmas**. Cuatro candidatos: α-aminoéster (y α-aminocetona), N-alquilmorfolina,
propargilamina y β-sulfona.

**No se te pide** implementar nada, ni cambiar la tabla de pKa, ni tocar `scripts/artifacts_science/` (sellado). Propones; el cambio y sus pruebas
los hace otra persona. Un resultado negativo («esta clase no merece revisión») es una respuesta válida y tan útil como un positivo.

## 1. Lo que el producto hace hoy (léelo antes de investigar)

MolDesign es una aplicación de escritorio que acopla ligandos con AutoDock Vina y conserva la evidencia de cada corrida. Su regla de oro:
**cuando no sabe, lo dice** y no inventa un número. El tema de este encargo es una de esas declaraciones.

- **Qué se acopla.** [`backend/chem/ionizacion.py`](../../backend/chem/ionizacion.py) (líneas 109–160) reconoce el centro ionizable por SMARTS y aplica
  **el pKa representativo de su clase**. Para toda amina alifática (`amina_alifatica`, línea 123) ese pKa es **9,8**. A pH 7,4 la amina sale protonada
  (catión) y esa es la especie que se acopla; de ahí salen también LogD y CNS-MPO. La tabla **no calcula pKa**: lo asigna por clase.
- **El problema.** Un grupo atractor próximo baja el pKa varias unidades y la clase no lo ve. Ya está medido en el caso del nitrilo en α
  (dimetilaminoacetonitrilo, pKa 4,2, sale catión) y de la morfolina (MES 6,15; MOPSO 6,95).
- **Lo que ya existe como respuesta.** [`backend/chem/especie_en_revision.py`](../../backend/chem/especie_en_revision.py) **no cambia lo acoplado**: sólo
  **declara**. Si el ligando pertenece a una clase cuya especie la tabla no resuelve, la «Especie acoplada» pasa de «registrada» a «**revisar**», con un
  motivo escrito. Hoy marca cuatro: dos centros básicos a ≤ 3 enlaces, N-sulfonil-piperazina, ácido enólico vinílogo y **amina con atractor** (CF₃/CHF₂ en β,
  nitrilo en α o β; sobre la especie acoplada, con N protonado). Lee su cabecera y sus SMARTS (líneas 78–230).
- **Quién lo lee.** El dossier (`backend/services/dossier/model.py`, líneas 660–747: el estado del campo «especie»), Preparación y el panel de elevación
  3D (`backend/chem/elevacion.py`, líneas 385–409). **Revisar no bloquea ni cambia ningún score.**
- **Criterio vecino que ya usa el producto.** `backend/services/dossier/preparacion.py:1037`, `UMBRAL_PKA = 1.5`: si algún grupo ionizable tiene
  |pKa − pH| ≤ 1,5 se pide revisión porque hay dos microespecies pobladas. Cualquier criterio nuevo debería ser coherente con éste o explicar por qué no.

## 2. Lo que ya se sabe (con su fuente)

| Hecho | Fuente | Estado de la evidencia |
|---|---|---|
| NO_GO de «el producto acopla la especie dominante para toda amina que la clase reconoce»: 3 aminas de nivel A con pKa ≤ 7,1 salen catión | `git show 665a473b:docs/auditorias/AMINA-PKA-01.md` (código y datos en el mismo commit, `scripts/amina_pka_01/`; registro previo en `fd2189bd`) | Conjunto dirigido de 20 puntuados, **no** una tasa del producto. Varias cifras se extrajeron por resúmenes y no se cotejaron con primarios (lo dice la cabecera de `conjunto.json`) |
| Error de 9,8 − pKa medido por estrato: normal n=10 MAE 0,69 sesgo +0,32; bencílica n=2 0,79; α-amida n=4 1,85; con atractor n=4 3,39 | [`docs/auditorias/investigacion-1.0.4/D04.md`](../auditorias/investigacion-1.0.4/D04.md) | Las mismas cifras de AMINA-PKA-01 reanalizadas |
| Con ChEMBL25 (2 345 compuestos con una sola clase reconocida), la mediana ajustada de `amina_alifatica` baja el MAE en 0,51 [0,18–0,88] (n eval. 241) con pKa candidato 8,3 | [`D04-ChEMBL-tabla.md`](../auditorias/investigacion-1.0.4/D04-ChEMBL-tabla.md), `scripts/artifacts_science/DEC-104-D04-CHEMBL/` | **Sustituir 9,8 por 8,3 no cambia el estado de carga a pH 7,4** (139/193 en ambos casos, comprobado). Por eso la recomendación es declarar, no cambiar la tabla |
| No hay un pKa experimental verificado del clopidogrel. SPARC 4,61; ChemAxon 4,77–5,14; el «4,55» procede de un documento del patrocinador (FDA sNDA 20-839/S-019) y de la monografía canadiense, que no son dos mediciones independientes | `AMINA-PKA-01.md`, `D04.md` | Sin incertidumbre ni fuerza iónica declaradas |
| Un modelo (Gemini) propuso SMARTS y valores para cuatro clases | [`docs/auditorias/segunda-opinion-gemini-1.0.4-2026-11-15.md`](../auditorias/segunda-opinion-gemini-1.0.4-2026-11-15.md), §D-04 (≈ líneas 183–205) | **Las citas web no están verificadas.** Los SMARTS se probaron aquí y se comportan como dice, salvo que el de la morfolina también casa con la morfolina **sin sustituir**, y que el α-nitrilo ya lo cubre el motivo vigente |

**Esto es lo que hay que confirmar o corregir.** No tomes ningún valor de esta tabla ni de la segunda opinión como cierto: cítalo desde su fuente primaria o
márcalo «no verificado».

## 3. Las cuatro clases candidatas

Las fórmulas son hipótesis de partida, **no** conclusiones. Los pKa que aparecen entre paréntesis salen de la memoria de quien escribe este encargo y
**hay que verificarlos**.

| # | Clase | Idea química | Compuestos de partida (valores a verificar) |
|---|---|---|---|
| 1 | **α-aminoéster y α-aminocetona/aldehído** | N–CX4–C(=O)–O/C: el carbonilo a un carbono del N baja la basicidad | Éster etílico de glicina (≈ 7,7); clopidogrel (≈ 4,5–5, discutido); aminocetonas como el bupropión. Control negativo: β-aminoéster (metilfenidato, ≈ 8,9), zwitterión −COO⁻, α-aminoamida |
| 2 | **N-alquilmorfolina** (¿y morfolina NH?) | El O del anillo, a dos enlaces del N, baja ≈ 1–2 unidades | N-metilmorfolina (≈ 7,4); morfolina (≈ 8,4); morfolinas de fármacos (gefitinib); MES (6,15 a 20 °C) y MOPS (≈ 7,15) |
| 3 | **Propargilamina** | N–CX4–C≡C: el alquino en β baja ≈ 2 unidades | Propargilamina (≈ 8,2); rasagilina y selegilina (≈ 7,3–7,5); pargilina (≈ 6,6) |
| 4 | **β-sulfona** | N–C–C–SO₂: la sulfona en β es fuertemente atractora | Tiomorfolina-1,1-dióxido; 2-(metilsulfonil)etilamina; sulfonas cíclicas |

Considera además, como **zona gris informativa**, la **α-aminoamida** (lidocaína ≈ 7,9, bupivacaína ≈ 8,1: siguen siendo mayoritariamente cationes, pero con
17–26 % de neutro que afecta a LogD) y el **oxetano en β** (oxetan-3-il-amina). Decide con evidencia si entran o se quedan fuera.

## 4. Preguntas que debes responder

Cada respuesta con su evidencia, su fuente y su nivel (ver §6).

**P1. ¿Cuál es el pKa experimental de cada clase?** Por clase, una tabla compuesto × pKa × temperatura × fuerza iónica × método × fuente primaria
(DOI o PMID, con la frase o la tabla exacta) × nivel de evidencia. ¿Cuántos compuestos hay con medida primaria? ¿Qué fracción cae en la zona
|pKa − 7,4| ≤ 1,5, o sea entre 5,9 y 8,9?

**P2. ¿Cuándo una clase merece «revisión»?** Propón un criterio **antes de mirar los datos de la clase** y regístralo. Punto de partida: una clase entra si
la mediana de sus pKa medidos queda a ≤ 1,5 unidades de 7,4, o si más de la mitad de sus compuestos con medida primaria caen en esa banda. Defiende
o cambia ese umbral con argumentos; considera que la regla no cambia la especie acoplada, sólo la declara incierta, así que **pecar por exceso de alarmas
tiene un coste distinto al de callar**.

**P3. ¿Qué patrón SMARTS reconoce cada clase?** Sobre **la especie acoplada** (con N protonado, `[NX4+;!H0;!$(N[a])]`), porque el producto sólo marca cuando
ESA amina quedó protonada. Debe: casar los positivos; **no** casar zwitteriones (−COO⁻), β-aminoésteres, aminas ordinarias, anilinios ni los controles
negativos del repositorio (ver §5). Informa, por patrón, sensibilidad y especificidad sobre tus controles, **y los falsos positivos que provocaría
en moléculas con otros grupos** (el de la morfolina, por ejemplo, casa con la morfolina NH; el del atractor ya cubre α-nitrilo).

**P4. ¿Qué pasa con la morfolina sin sustituir y con los anillos fusionados?** La morfolina NH (≈ 8,4) queda a 0,5 de la banda de 8,9. ¿Entra?
¿Y la morfolina N-arilo? (la clase `amina_alifatica` excluye el N unido a un aromático con `!$(N[a])`, así que la tabla no la ve como base alifática y
ese caso queda fuera del alcance de esta regla; confírmalo). ¿Y la tiomorfolina, el oxetano y la oxazolidina?

**P5. ¿Cuántos compuestos con pKa medido caen en cada patrón?** Con tus patrones, cuenta sobre el conjunto ChEMBL25 que ya está procesado en el
repositorio: [`scripts/artifacts_science/DEC-104-D04-CHEMBL/per_complex.jsonl`](../../scripts/artifacts_science/DEC-104-D04-CHEMBL/per_complex.jsonl)
(2 345 compuestos con un solo centro reconocido: pKa, clase de la tabla y andamio neutro; el procedimiento exacto para bajar el SDF fuente, su licencia y sus
hashes están en [`D04-ChEMBL-registro.md`](../auditorias/investigacion-1.0.4/D04-ChEMBL-registro.md) y `procedencia.json`). Es una fuente de partida muy
barata para P1, pero **mide el SDF de ChEMBL25, no el producto**, mezcla fuentes y no declara T ni I: sus valores son de nivel B como máximo. **No
hace falta contar las series MolFlex ni 8T69**: eso lo hace quien implemente (plan, fase 4).

**P6. ¿Qué texto ve la persona que usa el producto?** Cada motivo de `especie_en_revision.py` tiene un texto en castellano (dos líneas) que **cita un
ejemplo de la literatura y dice explícitamente que no es la molécula de la persona** («ejemplo de la literatura, no esta molécula: …»). Propón el texto de
cada clase con su ejemplo y su cifra citada, en el mismo estilo que `_AMINA_CON_ATRACTOR`.

**P7. ¿Qué no se puede afirmar?** Lista lo que la evidencia no sostiene (por ejemplo, la cifra de un compuesto con una sola fuente, o la ausencia de
medida primaria para el clopidogrel). El producto se define por saber cuándo no confiar en un número: una conclusión honesta que diga «no hay
suficiente» vale más que una tabla completa con huecos rellenados.

## 5. Cómo se te va a comprobar (y qué te conviene dejar listo)

Quien reciba tu entrega:

1. repite **tres cifras al azar** desde tus scripts;
2. comprueba **el 10 % de tus citas** contra su fuente (una cita que no se pueda comprobar cuenta como no hecha);
3. ejecuta tus SMARTS contra los controles que ya fija `backend/tests/test_especie_en_revision.py`: `ERRORES_CONFIRMADOS` (2),
   `CORRECTAS_VERIFICADAS` (17: albendazol, clorfeniramina, diclofenaco, haloperidol, imipramina, ketoconazol, propranolol, verapamilo, ciprofloxacino, celecoxib,
   losartán…), `AMINAS_CON_ATRACTOR_ACOPLADAS` (5) y los controles negativos del mismo archivo, más los tuyos. **Ninguna molécula de
   `CORRECTAS_VERIFICADAS` debe pasar a «revisar»**; si propones que alguna lo haga, justifícalo caso a caso;
4. mira que cada compuesto de control tenga su **SMILES de la especie acoplada** (protonada, tal como la acoplaría el producto), no sólo el nombre.

## 6. Reglas de método

Valen las de la parte 1 de [`docs/auditorias/decisiones-pendientes-1.0.4-2026-11-14.md`](../auditorias/decisiones-pendientes-1.0.4-2026-11-14.md). En resumen:

1. **Registro previo.** Antes de mirar los datos, escribe y firma con hash: la pregunta, la cohorte y por qué esa, el criterio de entrada (P2), los patrones y la
   regla de decisión (GO, NO_GO, INCONCLUSIVE) con su potencia. Lo que cambies después es una enmienda fechada y el resultado queda marcado como no
   confirmatorio.
2. **Procedencia de cada dato.** Origen (URL o identificador), versión, fecha de descarga, licencia y SHA-256. La compilación de la IUPAC (Zheng et al.,
   v2.3d) es **CC BY-NC 4.0**: no la copies al repositorio; ChEMBL25 sí se puede usar. Si no se puede guardar un dato, guarda el identificador y el
   procedimiento exacto para bajarlo.
3. **Niveles de evidencia** (los de AMINA-PKA-01): **A** medida primaria con temperatura y fuerza iónica; **B** compilación o monografía que cita su
   primario; **C** cálculo (SPARC, ChemAxon…) o documento de patrocinador. Sólo A cuenta para decidir; B y C se enseñan aparte.
4. **Los números se citan con su condición** (T, I, método, versión). Un pKa sin temperatura es un número a medias.
5. **Hechos separados de la recomendación.** Una tabla para lo medido, un párrafo aparte para lo que recomiendas.
6. **Se publican los resultados negativos e inconcluyentes**, con su potencia: con 4 compuestos por clase no se concluye una tasa.
7. **Qué no se toca.** `scripts/artifacts_science/` (sellado), la tabla `CENTROS` de `ionizacion.py`, las rutas de `scripts/retenidos_del_publico.txt`, la clave del reto
   FEP-06-HUM (fuera del repositorio). Nada se empuja a ningún repositorio.
8. **Intérprete.** Lo que ejecutes con RDKit, hazlo con `python-embed` 3.11.9 (el que se distribuye; RDKit 2025.09.6); si usas otro, decláralo como desviación.
9. **Escalera de coste.** Primero lo que se resuelve leyendo; después cálculo barato (RDKit, SMARTS); no se espera ni se autoriza ningún cómputo pesado.

## 7. Qué debes entregar

Una carpeta nueva `docs/auditorias/investigacion-d04-2026-11-15/` (no dentro de `investigacion-1.0.4/`, cuyo manifiesto hashea cada archivo) con:

1. `INFORME.md`: una o dos páginas. Pregunta, **recomendación en una frase por clase** (entra / no entra / entra como informativa), evidencia en tabla,
   riesgos y qué dato cambiaría la conclusión.
2. `pka-por-clase.csv`: compuesto, clase, SMILES **neutro** y **de la especie acoplada**, pKa, T, I, método, fuente (DOI/PMID), cita literal, nivel.
3. `controles.json`: los controles positivos y negativos listos para convertirse en pruebas (nombre, SMILES acoplado, clase esperada o «ninguna», nivel).
4. `patrones.md`: los SMARTS definitivos con su sensibilidad y especificidad, y los falsos positivos que se conocen.
5. `textos.md`: el motivo en castellano de cada clase aceptada (P6).
6. `PROTOCOLO.md` con su `.sha256`, `manifiesto.json` con los hashes y los scripts que regeneran cada cifra.
7. `NO-VERIFICADO.md`: todo lo que citaste de memoria o no pudiste cotejar con su fuente primaria.

**Antes de empezar,** si algo de este encargo no se puede cumplir (no puedes acceder a una fuente, una instrucción se contradice con otra), dilo en el
registro previo en vez de resolverlo en silencio.
