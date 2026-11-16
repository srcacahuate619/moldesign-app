# Decisiones pendientes de MolDesign 1.0.4: guía para delegar su investigación

| Campo | Registro |
|---|---|
| Fecha | 2026-11-14 |
| Código de referencia | `77aeb737`, rama `codex/release-hygiene`, sin empujar |
| Para quién | Quien reciba un encargo de investigación; el propietario decide y registra |
| Fuentes | [Acta de la auditoría científica](auditoria-cientifica-1.0.4-2026-11-13.md) · [Estado de 1.0.4](../versions/1.0.4_cambios.md) · [AGENTS.md](../../AGENTS.md) · [Acta de la convención del pLDDT](convencion-plddt-boltz-chai-2026-11-15/README.md) |

Este documento no decide nada. Convierte cada decisión abierta en una pregunta que alguien ajeno al proyecto puede investigar y
cuya respuesta se puede comprobar sin fiarse de quien la da. Cada ficha dice qué se decide, qué ya está medido (con su fuente),
qué opciones hay, qué evidencia las separaría y qué debe entregar el investigador.

La entrega de investigación de este encargo se consulta en [Investigación de las decisiones de 1.0.4](investigacion-1.0.4/README.md).
El [estado del cierre](cierre-investigacion-1.0.4-2026-11-15.md) incorpora la ampliación de D-04, la contrarréplica de hERG y la comprobación de los requisitos de B-11.
La [revisión final del 15 de noviembre](revision-final-1.0.4-2026-11-15.md) revisa individualmente las diez D, hERG y las doce B, y sustituye las recomendaciones anteriores donde las corrige. Incluye sondas reproducibles; no equivale a implementación ni aceptación del instalador.

## Cómo leerlo

- **Parte 1.** Reglas que valen para todos los encargos.
- **Parte 2.** Mapa de las diez decisiones que necesitan investigación, con un orden sugerido.
- **Parte 3.** Una ficha por decisión.
- **Parte 4.** Lo que está pendiente pero no necesita investigación nueva: una pregunta, lo que se sabe y el valor por defecto.
- **Parte 5.** Lo que este documento no sabe.

Ninguna de las decisiones de las partes 2 y 3 figura como bloqueante en el registro de 1.0.4: cada una tiene su límite declarado en
[1.0.4_cambios.md](../versions/1.0.4_cambios.md), en [AGENTS.md](../../AGENTS.md) o en el acta. Es una lectura de esos documentos, no una autorización del propietario.
Lo que sí bloquea la versión está en la parte 4 (B-11).

---

## Parte 1. Reglas comunes de todo encargo

Salen de cómo se ha trabajado hasta ahora (experimentos sellados, GO/NO_GO/INCONCLUSIVE, auditorías externas con validador de
citas). Un encargo que las incumpla no sirve de base para decidir.

1. **Línea base fija.** Se trabaja sobre un commit concreto (el de la cabecera, o el que el propietario indique) y con el
   intérprete que se distribuye (`python-embed`, Python 3.11.9), no con el de desarrollo. Cualquier paso que corra en otra
   plataforma (Linux, CUDA, Colab) se declara como desviación, con el motivo.
2. **Registro previo.** Antes de mirar ningún resultado se escribe y se firma con hash: la pregunta, la cohorte y por qué esa,
   los brazos, la métrica, la regla de decisión (GO, NO_GO, INCONCLUSIVE) y la potencia. Lo que se cambie después es una
   enmienda con fecha, y el resultado queda marcado como no confirmatorio. Los sellos del repositorio se escriben con
   [`scripts/sellar_experimento.py`](../../scripts/sellar_experimento.py) y se comprueban con
   [`scripts/validar_sellos.py`](../../scripts/validar_sellos.py) `--check`; los artefactos ya sellados de `scripts/artifacts_science/` no se editan.
3. **Procedencia de cada dato.** Origen (URL o identificador), versión, fecha de descarga, licencia y SHA-256. Los datos brutos se
   conservan fuera del repositorio y su manifiesto, dentro (como en el [acta del pLDDT](convencion-plddt-boltz-chai-2026-11-15/manifiesto.json)).
   Sin licencia que permita guardarlos, se guarda el identificador y el procedimiento exacto para descargarlos.
4. **Cada afirmación del informe con cita verificable:** archivo y línea con el commit, o DOI/PMID con la frase exacta. Una cita
   que no se pueda comprobar cuenta como no hecha. Lo leído en memoria y no verificado se rotula así.
5. **Se publican los resultados negativos y los inconcluyentes,** con su potencia. Ejemplo del estilo exigido: «con n = 57, una ρ
   verdadera de 0,3 sólo se detectaría el 62 % de las veces» ([CAL-8HFI-01](../papers/CAL-8HFI-01.md)). Inconcluyente no es un fracaso;
   disfrazarlo de GO sí lo es.
6. **Los números se citan con su condición** (versión, protocolo, semilla, caja). Un número sin condición no entra al informe.
7. **Qué no se toca ni se mira.** La clave del reto FEP-06-HUM (fuera del repositorio) y las rutas de
   [`scripts/retenidos_del_publico.txt`](../../scripts/retenidos_del_publico.txt); nada se empuja a ningún repositorio público; los datos de PDBbind no se
   redistribuyen. Quien investiga no implementa en el producto: propone, y el cambio lo hace y lo prueba otra persona.
8. **Entrega** (la misma para todas las fichas):
   - un informe de decisión de una o dos páginas: pregunta, recomendación en una frase, evidencia en tabla (identificador, fuente,
     hash), efecto de cada opción en el producto, riesgos y qué dato cambiaría la conclusión;
   - la carpeta de evidencia con manifiesto de hashes y los scripts que regeneran cada cifra;
   - el coste de implementar cada opción: archivos que toca, pruebas que habría que añadir y qué hashes de receta, corridas doradas
     o instantáneas de dossier cambian;
   - los hechos separados de la recomendación.
9. **Cómo se comprueba.** Quien reciba la entrega repite al azar tres cifras desde los scripts, comprueba el 10 % de las citas contra
   su fuente y corre `validar_sellos.py --check`. El modelo de este control es el validador antifabricación del encargo
   SUPUESTOS-01 (comprueba cada cita literal contra el commit).
10. **Escalera de coste.** Primero lo que se resuelve leyendo (documentación, código, datos ya archivados), después lo que se
    resuelve con cálculo barato, y sólo al final lo que pide GPU o decenas de horas de CPU. Vina no corre en Colab: es trabajo de
    CPU, y la sesión se corta.

---

## Parte 2. Mapa de decisiones con investigación

| ID | Decisión | Evidencia que falta | Cómputo | Orden |
|---|---|---|---|---:|
| **D-01** | Qué cifra lee la regla de confianza con Chai-1 y si se nombra la herramienta que el archivo declara | Documental, más una comprobación empírica corta | Lectura; GPU opcional | 1 |
| **D-09** | Cómo tratar las antidianas y las entradas del catálogo cuyo sitio no está adjudicado | Literatura, con adjudicación por pares | Ninguno | 2 |
| **D-02** | Si la regla «pLDDT < 70 junto al sitio» predice un docking peor, y con qué parámetros | Experimento de redocking con registro previo | CPU local; GPU para un brazo | 3 |
| **D-04** | Si la tabla de pKa por clase se sustituye o se acota con pKa medidos | Datos públicos y error por clase | Ninguno | 4 |
| **D-03** | Si la receta del catálogo debe retirar todas las aguas | Experimento de redocking con criterio de «agua estructural» | CPU, decenas de horas | 5 |
| **D-06** | Si la exhaustividad por defecto sigue siendo 8 | Más series con Ki, sobre el diseño de SUP-04 | CPU | 6 |
| **D-05** | Cuánto invertir en metales: coordinación en interacciones, validación física, ampliar M5 | Inventario y un piloto | CPU | 7 |
| **D-08** | Si la cobertura de UMS se extiende a formas aniónicas | Controles positivos y negativos | Ninguno | 8 |
| **D-07** | Qué hacer con el índice compuesto `total_score` | Inventario de consumidores; sin ciencia nueva | Ninguno | 9 |
| **D-10** | Si ESMFold se valida o se deja rotulado como experimental | Piloto de cuatro brazos | CPU, unas 60 h | 10 |

El orden sugerido pone primero lo que se resuelve leyendo (D-01, D-09, D-04), después lo que cierra una cadena ya empezada (D-02
continúa el trabajo del pLDDT) y deja para el final lo que cuesta días de CPU o cambia hashes de receta (D-03, D-10). D-02 está en
pausa por decisión del propietario (2026-11-15, nota interna); no se arranca sin su confirmación.

---

## Parte 3. Fichas

### D-01 · Confianza (pLDDT) con Chai-1, y nombrar la herramienta

**Decisión.** Dos preguntas acopladas. (1) Con un mmCIF de Chai-1, ¿qué cifra lee la regla de Preparación? (2) Cuando el archivo se
nombra a sí mismo, ¿el dossier nombra la herramienta?

**Por qué importa.** El producto lee hoy el pLDDT del Cα de Chai-1 y no la media por residuo; la regla ve menos residuos bajos que el
modelo (9 frente a 21 en CDK2 sin ligando). Un sitio con residuos bajos según la media por residuo podría no avisar si el Cα de esos residuos supera 70. No se ha medido con qué frecuencia ocurre.

**Lo que ya se sabe** ([acta](convencion-plddt-boltz-chai-2026-11-15/README.md), Boltz 2.2.1 y chai_lab 0.6.1, dos proteínas, un ligando, una semilla):
- En Chai-1, el factor B va por átomo; su media por residuo vale el tensor del modelo ×100 en 15 de 15 estructuras. El campo
  `_ma_qa_metric_local`, que es el que lee el producto, no coincide con ese tensor (hasta 19 puntos) y sí con el Cα.
- Residuos < 70 que ve el producto frente a los que cuenta el modelo: CDK2 sin ligando 9 frente a 21; CDK2 con ligando 3 frente a 9; NET 72 frente a 76.
- Chai-1 se nombra a sí mismo en `_struct.title`; el producto lo rotula «estructura predicha (ModelCIF)» con la convención «sin verificar».
  Boltz no se nombra en ningún campo.
- El umbral 70 viene de la definición de AlphaFold 2 (lDDT del Cα predicho). El acta dice que **esa definición no se cotejó con la fuente primaria**.
- De AlphaFold 3 no se ha generado ningún archivo.

**Opciones.**
- **A.** Mantener el Cα y rotularlo como tal.
- **B.** Leer la media por residuo del factor B cuando el archivo se identifica como Chai-1.
- **C.** Abstenerse con Chai-1 hasta que D-02 mida si la regla acierta.
- **D.** Calcular las dos y pedir revisión si cualquiera cruza 70.
- Para (2): nombrar la herramienta cuando el archivo la declara, o seguir con «ModelCIF» genérico.
  El registro actual la enuncia en una línea («si se nombra la fuente cuando el archivo la declara»); este brief la interpreta así. Confirmarlo con el propietario antes de empezar.

**Evidencia que decide.**
1. Documental, con cita literal: qué cantidad define el umbral 70 en el artículo de AlphaFold 2 y en la documentación de AlphaFold DB, y qué documenta Chai-1 para su tensor y para el campo local del mmCIF.
2. Empírica, sólo si la documental no zanja: sobre estructuras experimentales posteriores al corte de entrenamiento de Chai-1 (confirmar ese corte
   en la fuente), ¿qué lectura separa mejor los residuos bien de los mal predichos? Fijar antes el margen de equivalencia entre las dos lecturas.
   Si no se demuestra diferencia, gana la que marca más residuos (la más conservadora) y se declara.

**Cómo conseguirla y coste.** La parte documental es lectura (0 UC). Los archivos de las dos ejecuciones ya existen, con 167 hashes en el
[manifiesto](convencion-plddt-boltz-chai-2026-11-15/manifiesto.json). La empírica pide nuevas corridas de Chai-1 en GPU; las anteriores tardaron 12 minutos en
una L4 para tres casos. Antes de gastar nada, comprobar si la cohorte de D-02 ya la cubre.

**Entregables propios.** Una tabla «lectura × caso × residuos < 70 × lDDT local frente al experimental», y qué pruebas de
[`test_prediccion_fuente_declarada.py`](../../backend/tests/test_prediccion_fuente_declarada.py) cambiarían con cada opción.

**No tocar.** La lectura de AlphaFold DB (verificada) ni la de Boltz-2 (verificada en 2.2.1). Un cambio en
[`prediccion.py`](../../backend/services/targets/prediccion.py) lo hace otra persona con recortes reales como fixtures.

---

### D-09 · Antidianas y entradas sin sitio adjudicado

**Decisión.** Qué hacer con las entradas del catálogo cuyo sitio de unión de referencia no está adjudicado, y con las antidianas
cuyo sitio cristalográfico no se sabe si es el farmacológicamente relevante.

**Por qué importa.** El redocking del sitio cristalográfico no adjudica por sí solo la relevancia de una antidiana para una reacción
adversa (acta, S2-7). Una antidiana con el sitio equivocado produce una lectura de seguridad que no significa lo que parece.

**Lo que ya se sabe.**
- 109 de las 381 entradas no declaran ligando del cristal (`site_ligand`); el catálogo tiene 380 de Demostración y una Verificada (8T69).
- [SUP-05](../papers/SUP-05-CORTES-DEL-SITIO.md): mover ±1 Å el corte de los huecos (8 Å) cambia 8 de 272 entradas, y el de las especies junto al sitio (6 Å), 18 de 272. Quedó
  INCONCLUSIVE: se pedían 300 medibles. Son lecturas, no decisiones.
- Panel [Bowes-44](../../backend/data/anti_dianas_bowes44.json), medido el 2026-11-14 sobre el JSON: 38 de las 44 dianas llevan `sitio_adjudicado: false` (la caja sale del ligando cocristalizado; el propio
  archivo dice que el redocking confirma ese sitio, no que sea el farmacológicamente relevante), 2 llevan `true` (HTR2B con 7SRQ y KCNH2 con 5VA1) y 4 no traen el campo porque no tienen estructura utilizable (CHRNA4, PTGS1, MAOA y una sin gen).
- La [anti-diana 5-HT2B](anti_diana_5ht2b_2026-10-04.md) es un caso ya estudiado, y la adjudicación de HTR2B figura en `anti-diana-5ht2b-2026-10-05.json`.

**Opciones.** A. Dejar el estado actual y declararlo. B. Adjudicar con literatura las 38 con `false` (en el orden de riesgo que fije el propietario) y buscar una estructura utilizable para las 4 sin ella.
C. Exigir adjudicación para que una antidiana muestre veredicto.

**Evidencia que decide.** Para cada antidiana, una ficha con: reacción adversa asociada y su evidencia (PMID), mecanismo (inhibición,
agonismo, bloqueo del canal), sitio relevante (ortostérico, alostérico, poro), si el ligando del cristal ocupa ese sitio, y un
nivel de confianza en una escala fijada antes. **Dos revisores independientes** y se publica el desacuerdo.

**Cómo conseguirla y coste.** Literatura, sin cómputo. Hasta 42 fichas (las 38 con `false` y las 4 sin estructura); el propietario puede acotarlas a las dianas que el panel por defecto ya usa.

**Entregables propios.** La tabla de adjudicación, con la propuesta de valores para `sitio_adjudicado`; no se edita el JSON del producto.

---

### D-02 · Calibrar la regla de confianza para estructuras predichas

> **En pausa.** El propietario la dejó pendiente el 2026-11-15 («no lo prepares todavía»). Este brief es para cuando la reactive.

**Decisión.** Si la regla «algún residuo del sitio con pLDDT < 70, a ≤ 6 Å de la caja, pide revisión» acierta, y con qué parámetros.

**Por qué importa.** Ambos inventarios de supuestos (SUPUESTOS-01) la dan por no medida (S18 de la semilla y tres entradas del inventario de Sol).
Hoy la revisión no bloquea nada, pero es lo único que dice a un usuario si su modelo predicho es de fiar junto a la cavidad.

**Lo que ya se sabe.**
- Constantes: `UMBRAL_REVISION = 70.0` y `MARGEN_SITIO_A = 6.0` en [`prediccion.py`](../../backend/services/targets/prediccion.py) (líneas 49 y 53); la regla es `n_bajo_70 > 0` en
  [`preparacion_confianza.py`](../../backend/services/dossier/preparacion_confianza.py) (línea 175). Revisión, no bloqueo.
- El acta del pLDDT [«No se midió si la regla de 70 acierta»](convencion-plddt-boltz-chai-2026-11-15/README.md).
- Propuesta del 2026-11-14 (nota interna, sin copia en el repositorio): cohorte de las entradas con `site_ligand` (272 según SUP-05; unas 219 con el sitio en una sola cadena, menos las 13 que no se preparan:
  **recontar**); brazos cristal, AlphaFold DB (modelos ya publicados) y Boltz-2 sin ligando; acoplar con el Vina del producto en local; acierto = centroide ≤ 4 Å y RMSD ≤ 2 Å; sólo deciden las entradas posteriores al corte de entrenamiento de cada predictor.

**Opciones.** A. Mantener y declararla «sin medir». B. Ajustar umbral y margen. C. Cambiar la regla (por ejemplo, fracción de residuos bajos, o pLDDT medio del bolsillo, o añadir el error esperado alineado). D. Retirarla.

**Evidencia que decide.** Sensibilidad y especificidad de la regla actual y de las variantes (umbral 50, 60, 70, 80; margen 4, 6, 8 Å; «alguno» frente a «fracción»)
para predecir el fallo del docking, con intervalos y con el número de entradas posteriores al corte que lo sostienen. Regla de decisión escrita antes. Si la cohorte posterior al corte no da potencia, el resultado es INCONCLUSIVE y la respuesta honesta es «sin medir».

**Cómo conseguirla y coste.** Vina con el binario del producto, en local o en el servidor, con 5 semillas; sólo el brazo Boltz-2 pide GPU. Dependencia de D-01 si se incluye Chai-1 como cuarto brazo.

**Entregables propios.** La cohorte con su criterio de inclusión y hash; el corte de entrenamiento de cada predictor con su fuente; la lista de entradas decisivas.

**No tocar.** El catálogo (`receptor_sha256`); los sellos de `scripts/artifacts_science/`.

---

### D-04 · pKa por clase frente a pKa medidos

**Decisión.** Si la tabla de pKa por clase química se sustituye, se acota o se declara tal cual.

**Por qué importa.** La tabla por clase decide la especie que se acopla y alimenta LogD y CNS-MPO. La clase `amina_alifatica` asigna pKa ≈ 9,8
en [`ionizacion.py`](../../backend/chem/ionizacion.py) (líneas 49 y 126); para aminas α a un nitrilo y para morfolinas los casos medidos de abajo salen catión con pKa de 4 a 7.

**Lo que ya se sabe** (el informe AMINA-PKA-01 vive en otra rama: commits `fd2189bd`, el registro previo, y `665a473b`, el informe, de
`claude/interesting-mccarthy-c62de3`, como `docs/auditorias/AMINA-PKA-01.md` con su código en `scripts/amina_pka_01/`; no está en esta rama y hay que traerlo antes de delegar):
- NO_GO de «el producto acopla la dominante para toda amina que la clase reconoce»: dimetilaminoacetonitrilo (4,2), MES (6,15) y MOPSO (6,95) salen catión.
  15 de 15 protonadas de nivel A, bien; réplica 17 de 17. Conjunto dirigido de 27, no una tasa del producto.
- No hay un pKa experimental verificado del clopidogrel (SPARC 4,61, ChemAxon 4,8 a 5,1, un «4,55» sin fuente).
- Hoy `chem/especie_en_revision.py` ya declara REVISAR para el nitrilo α. Propuesta A del informe: dos SMARTS más y un guardián, sin cambiar lo acoplado. B (cambiar la tabla): sin recomendar.
- El propietario adelantó la opción A a 1.0.4 el 2026-11-15. La [investigación ampliada](investigacion-d04-2026-11-15/INFORME.md) prueba cuatro entornos y distingue las dos propuestas que pasan el criterio de las que quedan inconcluyentes. [Plan](plan-d04-especie-en-revision-2026-11-15.md)
- La [revisión final de D-04](revision-final-1.0.4-2026-11-15.md#2-d-04--acotar-los-avisos-a-la-evidencia-y-corregir-el-estado-de-carga) acota los dos patrones admitidos a la evidencia y corrige «fracción neutra» por nitrógeno sin protonar. Para implementar o presentar, usar esta propuesta corregida; el informe y el manifiesto anteriores conservan su alcance histórico. Implementada el 2026-11-15 con esos patrones (`0097c15a`).

**Opciones.** A. Declarar más clases como «especie en revisión» sin tocar la tabla. B. Sustituir el valor de las clases malas por medidos. C. Reemplazar la tabla por un predictor validado.

**Evidencia que decide.** El error de la tabla por clase frente a pKa experimentales, **por clase**, con el número de compuestos y la fuente de cada
valor; cuántas decisiones de especie (neutra o catión) cambian en el conjunto de 203 de MolFlex y en la serie de 8T69; y el efecto sobre LogD y CNS-MPO.

**Cómo conseguirla y coste.** Sin cómputo pesado. Primero: licencia y términos de la compilación pública; si no permite guardarla, el procedimiento exacto.

**Entregables propios.** Tabla clase × n × error absoluto medio × sesgo, con el criterio de qué clases se aceptan; lista de compuestos cuyo veredicto cambia.

---

### D-03 · Aguas del sitio: ¿retirar todas?

**Decisión.** Si la receta del catálogo sigue retirando todas las aguas, conserva un subconjunto definido o lo decide cada receptor.

**Por qué importa.** La receta retira todas y no está medido. Un agua puente que media una interacción conocida desaparece sin que Preparación lo advierta.

**Lo que ya se sabe.**
- [REC-11](../papers/REC-11.md): conservar todas frente a retirar todas, 116 complejos, oráculo RMSD de bolsillo ≤ 2 Å. CON cubre 94 y SIN 96 (0,8103 frente a 0,8276); discordancias 8 y 10;
  McNemar exacto bilateral p = 0,8145; MDE de 9,92 puntos. INCONCLUSIVE. El cruce descriptivo posterior (REC-11-CRUCES) no habilita un cambio de producto.
- [FEP-09-R1](../papers/FEP-09-R1.md): Preparación **no detecta** el agua puente retirada (0 de 9 casos plantados).
- Aplazado a 1.0.5 (2026-10-26).
- Cambiar la receta cambia el hash de receta del catálogo entero y, con él, corridas doradas e instantáneas: precedente de la plantilla NDP, que el propietario descartó por ese coste.

**Opciones.** A. Mantener «retirar todas» y declararlo en el dossier. B. Conservar las aguas que cumplan un criterio estructural. C. Campo por receptor en el catálogo.

**Evidencia que decide.** El criterio de «agua estructural» debe estar escrito **antes**: qué la define (contactos polares con el ligando del cristal y con la proteína,
conservación entre estructuras, factor B), con su fuente. Después, redocking con y sin ese subconjunto en complejos donde la literatura documente aguas puente conservadas. Con 116 complejos y 18 discordancias no se resuelven efectos menores de 10 puntos: calcular la potencia **antes** de elegir la cohorte.

**Cómo conseguirla y coste.** Decenas de horas de CPU con el Vina del producto. No en Colab.

**Entregables propios.** El criterio con su fuente, la cohorte con la razón de cada inclusión, la potencia calculada y el efecto sobre los hashes de receta.

---

### D-06 · Exhaustividad por defecto

**Decisión.** Si el valor por defecto de la exhaustividad sigue en 8, sube, o se aconseja por caso.

**Por qué importa.** El 8 es el valor por defecto de Vina; un texto lo llamó «sweet spot validado» sin una medida. Subirlo aumenta el tiempo de cada corrida.

**Lo que ya se sabe** ([SUP-04](../papers/SUP-04-EXHAUSTIVIDAD-8T69.md), 8T69, 89 Ki, semilla 42 salvo la prueba de ruido): INCONCLUSIVE.
- Subir de 8 a 32 da Δρ = +0,043 (IC 95 % de −0,006 a +0,116): no excluye el cero ni cabe en ±0,10.
- Cambiar sólo la semilla mueve ρ en −0,025.
- La pose del cristal sale 5 de 5 con 8, 16 y 32; 85 de 89 padres quedan a menos de 0,1 kcal/mol.
- Es una sola serie.

**Opciones.** A. Mantener 8 y declararlo como el valor por defecto de Vina, no como validado. B. Subir el defecto. C. Aconsejar por tamaño del ligando o por caja.

**Evidencia que decide.** Más series con Ki publicados (por ejemplo, la de 8HFI de [CAL-8HFI-01](../papers/CAL-8HFI-01.md)) con el mismo diseño de SUP-04, el margen de equivalencia ±0,10 de ρ fijado antes y el
coste en tiempo por corrida medido en la misma máquina.

**Cómo conseguirla y coste.** CPU con el Vina del producto. El calendario lo marca el número de series.

**Entregables propios.** ρ por exhaustividad y serie con IC, ruido de semilla, tiempo por corrida.

---

### D-05 · Metales: cuánto invertir

**Decisión.** Entre tres caminos: (a) declarar los límites tal cual, (b) añadir la coordinación metálica a las interacciones y la validación física, (c) ampliar M5 a más metales además del zinc.

**Por qué importa.** Vina no tiene término de coordinación. En 41 de las 381 entradas hay un ion a 6 Å o menos del ligando del cristal; en 35 el propio ligando lo coordina.
La preparación retira el ion y Preparación se abstiene o pide revisión, pero lo acoplado no lo modela.

**Lo que ya se sabe.**
- [MET-01-R1](../papers/MET-01-R1-ION-DEL-SITIO.md) (NO_GO): con el Vina del producto, conservar el ion no mejora la reproducción de la pose del cristal (28 pares; 0 a favor de conservar, 3 a favor de retirar; p = 0,25). No demuestra daño ni equivalencia.
- [MET-02-R1](../papers/MET-02-R1-SEMILLA.md) (GO): la regla de dos niveles de Preparación no cambia con la semilla.
- M5-Zn cubre tres PDB, ninguno del catálogo; ningún perfil devuelve VALIDATED; los benchmarks de MMP9 y ACE están en revisión ([corrigendum](../77_CORRIGENDUM_SITIO_DEL_BENCHMARK_M5_ZN.md)).
- La huella de ProLIF no incluye la coordinación metálica; añadir `MetalDonor` y `MetalAcceptor` cambia la huella y las corridas doradas.
- PoseBusters no mira los iones que Meeko escribe como `ATOM`; `pose_physical_validity.py` está sellado.
- Dirección del propietario (2026-10-11): M5 es la solución propia para el zinc y puede ampliarse; no se ha hecho.

**Evidencia que decide.** (1) Qué fracción de los receptores que sube un usuario real lleva metal junto al sitio: hoy no hay usuarios externos, así que es un
supuesto; el inventario de los 381 da el techo. (2) Qué evidencia publicada hay de que un término de coordinación (por ejemplo AutoDock4Zn) mejora la pose o el orden en sistemas como los del catálogo. (3) Un piloto en 6 entradas.

**Cómo conseguirla y coste.** Inventario y literatura sin cómputo; piloto con CPU.

**Entregables propios.** Prevalencia por metal; evidencia publicada con cita; coste de implementación de cada camino, con los hashes y goldens que cambian.

---

### D-08 · Cobertura de UMS en formas aniónicas

**Decisión.** Si la señal `ums_warhead` se extiende a formas aniónicas o se declara su cobertura tal cual.

**Lo que ya se sabe** (según el acta, S2-1; verificar en el código antes de medir): sulfonamida, hidroxamato y tiol neutros dan `ums_warhead = 0,8833` y sus aniones explícitos `0`; el ejecutor
toma el SMILES de entrada; los SMARTS están fijados por manifiesto, así que un cambio exige versionar el protocolo. La sonda no demostró cambio de docking ni del ranking M4.

**Opciones.** A. Declarar la cobertura en la interfaz y no tocar. B. Extender con controles positivos y negativos y versionar.

**Evidencia que decide.** Un conjunto de control con formas neutras y aniónicas de cada familia, y moléculas que no deben activarla; sensibilidad y especificidad antes y después; efecto en el orden de M4.

**Coste.** Sin cómputo pesado. **No tocar:** los SMARTS fijados por manifiesto hasta que se versione el protocolo.

---

### D-07 · El índice compuesto `total_score`

**Decisión.** Congelarlo como legado rotulado (como está), retirarlo de las salidas, o versionar una fórmula nueva.

**Lo que ya se sabe.**
- [SUP-02](../papers/SUP-02-TOTAL-SCORE.md) (NO_GO): no ordena mejor que Vina (8T69: ρ 0,397 frente a 0,392; 8HFI: 0,03 frente a 0,13). Desde 1.0.4, sólo Moldex lo enseña, rotulado «índice compuesto heredado».
- Las dos opiniones del acta recomiendan **no** cambiar la fórmula: el techo de 90 (S1-3.1) y la transformación de la afinidad (S1-3.2) ya estaban en la base 1.0.3; el parche literal dejaría el máximo en 66,67; cualquier fórmula nueva necesita versión propia y conservar las corridas históricas.
- `check:goldens` y las corridas históricas dependen del valor actual.

**Evidencia que decide.** Este no pide ciencia nueva: pide un **inventario de consumidores** (campos de la API, PDF, dossier, MolChat, Moldex, goldens) con el efecto de retirarlo en cada uno, y la lista de lo que seguiría
mostrando el valor histórico sin rótulo. Una fórmula nueva sólo se justifica con más series que el par de SUP-02.

**Coste.** Lectura de código y búsqueda; sin cómputo. **No tocar:** `backend/scoring/` hasta que el propietario decida.

---

### D-10 · ESMFold: validar o dejar rotulado

**Decisión.** Si se invierte en validar la ruta de péptidos con ESMFold o se mantiene rotulada experimental y «sin validar».

**Lo que ya se sabe.** AGENTS.md: carga y sirve poses; no está probado que sean buenas. El propietario decidió (2026-10-07) no validarla en la estación.
Hay un plan de cuatro brazos (nota interna, sin copia en el repositorio): A, Vina desde un conformero de RDKit; B, la ruta ESMFold actual; C, ESMFold con el esqueleto rígido; D, la conformación del cristal con el esqueleto rígido (techo alcanzable).
Cohorte propuesta: LEADS-PEP (53 complejos de 3 a 12 residuos) más unos 20 publicados después del corte de entrenamiento de ESMFold (corte «mayo de 2020», dicho de memoria: **confirmar**). Hipótesis a probar primero: la preparación del péptido deja libres las torsiones del
esqueleto y Vina las sortea, con lo que el plegado no condicionaría el resultado. La decisión de transferencia está en [docs/76](../76_DECISION_TRANSFERENCIA_ESMFOLD_A_LIGANDO_V1.md).

**Evidencia que decide.** Si B se distingue de A (RMSD top-1 y mejor de 9, fnat, validez física con el protocolo de hidrógenos de MF-33-H-COR, por longitud), con repetibilidad por semillas, AUC del pLDDT como detector de éxito y controles negativos.
Una caída a Vina cuenta como fallo de ESMFold. Criterios fijados antes de correr nada.

**Cómo conseguirla y coste.** Unas 60 h de CPU con el Vina del producto (2 a más de 5 minutos por péptido) y unos 6 o 7 días de trabajo. No en Colab. El laboratorio Linux del propietario no respondía por SSH el 2026-10-22.

---

## Parte 4. Pendientes que no necesitan investigación nueva

Cada fila lleva una pregunta, lo que se sabe y un valor por defecto. En B-1 a B-6 el valor por defecto es el que recomiendan las dos opiniones del acta. En B-7 a B-10 es una propuesta de este documento, sin respaldo en el acta: está marcada «(propuesta)». B-11 y B-12 no son decisiones sobre ciencia.

| ID | Pregunta | Lo que se sabe | Por defecto |
|---|---|---|---|
| B-1 | ¿Se corrige la documentación del selector de pose (el umbral 2,0 de `RMSD/√3` equivale a ~3,46 Å)? (S2-3) | Identidad algebraica confirmada por las dos opiniones; el entrenamiento y la inferencia comparten la convención | Corregir el texto, conservar la fórmula del modelo congelado |
| B-2 | ¿Se corrige la tensión del conformador de entrada en el ensemble? (S2-6) | El informe no demuestra que sumar la energía inicial mejore el orden | Conservar el orden por Vina; una corrección pide un protocolo nuevo |
| B-3 | ¿Se amplía la cobertura de boro y selenio? (S3-1) | Bortezomib: `not_evaluated/MMFF_NO_PARAMETRIZA`; ebselen falla antes, en Meeko | Conservar la abstención; medir antes de ampliar |
| B-4 | ¿Se mantienen los caps desactivados? (S3-2) | Con caps activos, PDBFixer fusionó la cadena D con la A en 6SX5 y se perdió parte de la cavidad | Mantener `apply_caps=False` |
| B-5 | ¿Se aclaran las constantes térmicas (RT a 310,15 K frente a RT·ln 10 a ~298 K)? (S3-3) | Diferencia de significado, no de valor | Aclarar al tocar esas salidas |
| B-6 | ¿Se limpian los componentes sin montar, entre ellos `SARTable.tsx`? (S3-4) | Confirmado por referencias estáticas | Cambio de mantenimiento aparte, con comprobación de imports, pruebas y guardas de traducción |
| B-7 | ¿Qué dice la política de privacidad sobre el modelo local por defecto? | La web describe Qwen2.5 1.5B; el registro de proveedores de MolChat parte sin proveedor activo por defecto | (propuesta) Alinear el texto con lo que hace el producto |
| B-8 | ¿Qué se hace con los `logs/vina.log` anteriores al 2026-10-25 (rutas de usuario) y con `run/reproduce.md`, que remite a un verificador que no viaja? | Quitar las rutas cambiaría el `log_sha256`, y eso cambia el contrato del paquete ([docs/56](../56_DOSSIER_REPRODUCIBLE_CONTRACT.md)) | (propuesta) Conservar los bytes de las corridas antiguas, como ya hace el registro de 1.0.4 |
| B-9 | ¿Se quita ProDy de `python-embed`? | Sólo lo usa un script de desarrollo; quitarlo cambia el lockfile y el SBOM | (propuesta) Decidirlo con el build final, porque cambia el lockfile y el SBOM del runtime |
| B-10 | ¿Se archivan o se retiran los worktrees y ramas conservados (`D:\cr4`, `D:\mr1`, `receptores-20261008`, `innovafest`, `molchat-lab`, `sol/contexto-ensayo-*`, `codex/receptores-curacion-20261008-wip`)? | Datos ignorados que no se recuperan, o trabajo sin integrar | (propuesta) Mirar qué contiene cada uno y decidir uno a uno; los datos ignorados no se recuperan después de retirarlos |
| B-11 | **¿Cuándo se construye y se envía el instalador final de 1.0.4?** | Faltan el build con las 16 puertas, el humo de escritorio, la VM, WACK y Partner Center | **Es lo único de esta guía que bloquea la versión** |
| B-12 | ¿Quién cierra las verificaciones que sólo faltan por mirar? | La etiqueta «Demostración» renderizada en un fotograma de Molcy; el recorrido completo del comparador de poses con dos corridas reales; MolChat en una instalación limpia y su rollback; el título completo del depósito en el catálogo y la interfaz | Tareas de ejecución, no de decisión |

---

## Parte 5. Lo que este documento no sabe

- Las fichas D-05, D-08, B-1 a B-6 se apoyan en lo que dice el [acta](auditoria-cientifica-1.0.4-2026-11-13.md) del código, no en una relectura propia de cada archivo. Quien las reciba debe comprobarlo antes de medir.
- Algunas cifras vienen de notas internas que no están en el repositorio (la cohorte de 219 de D-02, el plan de cuatro brazos de D-10, el estado de pausa de D-02, el informe AMINA-PKA-01 en su rama). Cada una está marcada; antes de delegarla, el propietario debe confirmarla o añadir la nota al repositorio.
- Los inventarios de SUPUESTOS-01 (50 entradas de la semilla y 303 del inventario de Sol, en `E:\SUPUESTOS-01\`) contienen supuestos sin medir que **no** se han convertido aquí en fichas: la banda de selectividad de ±2 kcal/mol, el filtro de poses que aprueba choques sin receptor, el proxy de tensión sin calibrar, los revisores LLM como referencia sin validar contra expertos (el reto FEP-06-HUM abierto es la validación humana de ese punto, cierra el 2026-12-06 o con 20 revisiones admitidas).
- No se ha medido cuánto cuesta cada ficha en dinero ni en semanas de una persona; las cifras de coste son de cómputo y vienen de las notas citadas.
- No se ha pedido a nadie que revise este documento.

## Cómo se registra la decisión

Cuando el propietario decida una ficha, se añade una fila al [registro de decisiones del acta](auditoria-cientifica-1.0.4-2026-11-13.md#registro-de-decisiones) con la opción elegida, la fecha, el informe de decisión
enlazado y el commit que la implementa; la carpeta de evidencia se archiva fuera del repositorio con su manifiesto de hashes. Si la decisión es «dejar como está», también se registra, con el límite declarado.
