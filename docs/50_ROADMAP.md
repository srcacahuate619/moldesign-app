# Roadmap de MolDesign

Escrito el 2026-08-19. Documento vivo: se actualiza cuando cambia la evidencia, no
cuando cambia el ánimo.

Su función es que no se pierda el hilo. Cada elemento dice **qué**, **por qué** y **qué
lo cancelaría**. Si algo no tiene un porqué que resista una pregunta, no debería estar
aquí.

Complementa a [`49_PROGRAMA_EXPERIMENTAL_CIENTIFICO.md`](49_PROGRAMA_EXPERIMENTAL_CIENTIFICO.md),
que es el registro de lo que ya se midió. Este documento es lo que falta por hacer.

---

## 0. La tesis, corregida por la evidencia

La tesis original era que MolDesign aportaría **mejores modelos**. Ochenta y nueve
experimentos sellados (los que había al escribir esto, el 2026-08-19; el
2026-09-22 son 151) dicen que no, en cinco de seis componentes:

| Componente | Veredicto |
|---|---|
| MolFlex | El generador no visita la región correcta. Cinco palancas probadas, cartera agotada |
| Selector de poses (Ruta C) | No supera a `vina_score`. Cerrada de forma definitiva |
| MolPocket | El bolsillo correcto se genera; el ranking no lo pone primero (8 Å de mediana) |
| MolGraph | Oversmoothing; no mejora EF@1% |
| MolChamb / UMS | El descriptor cuántico no añade nada sobre seis patrones SMARTS |

**La tesis vigente es otra, y sí está sostenida por la evidencia:**

> MolDesign es un pipeline de docking y preparación **auditable, que sabe cuándo no
> confiar en sí mismo**. No gana peleas de benchmark. Dice la verdad sobre lo que sabe, y
> puede demostrarlo.

Lo que la sostiene: `FEP-04` (la abstención calibrada casi duplica la precisión),
`MF-12` (se predice el fallo antes de gastar cómputo), `FND-06` (procedencia completa de
cada pose) y el registro experimental entero como evidencia de validación.

**Destino a largo plazo**: interpretación de variantes de resistencia — dado el mutante
del tumor de un paciente, ¿el fármaco aprobado sigue uniéndose? Es una pregunta
estructural, es clínicamente accionable, y el camino hacia ella **es el mismo** que el de
ser FEP+ ready. Ver §6.

---

## 1. H0 — Estado al cierre del 2026-08-19

| Experimento | Estado | Resultado |
|---|---|---|
| `MF-28` roadmap PRM | **Sellado NO_GO** | El roadmap pierde 23 a 1 contra Vina en el estrato dificil. Lo falsifica en la direccion declarada: el problema no es la estrategia de exploracion |
| `MF-33` ensemble vs conformero unico | **Sellado GO** — defecto **resuelto** el 2026-08-21 | Rigido 1/33, un conformero flexible 12/33, **ensemble flexible 26/33**. `MF-33-A3` levanto el defecto: la magnitud **es citable** |
| `MF-33-A2` paridad de CPU | **Sellado INCONCLUSIVE** — defecto **resuelto** | A2 19/33. `MF-33-A3` lo relee sin cambiar el numero: ese 19 **no era limitacion de conteo de poses**, es el techo de un solo conformero por mucha CPU que se le eche |
| `MF-33-A3` poses y reinicios igualados | **Sellado GO** | **`LA DIVERSIDAD CONFORMACIONAL ES REAL`.** g_B=7, g_A3=0, McNemar p=0.0156. A3 igualo corridas, **261 poses** y CPU (razon 1.196, gasto **20% mas** que B) y aun asi pierde 26 a 19. Y el secundario cierra el caso: **A2 con 9 poses y A3 con 261 dan el mismo 19** — multiplicar por 29 las poses no mueve un complejo |
| `MF-29-EMP` optimo global empirico | **Sellado GO** | Lectura **OBJETIVO**: 3 de 48 mejoran con 64x de presupuesto (0.0625). Mas busqueda del mismo tipo no rinde -83.3 h de CPU contra 4.1 h para mover tres complejos <0.3 kcal/mol, con la sd entre semillas bajando de 0.013 a 0.009: el brazo masivo esta saturado-. Se sello primero INCONCLUSIVE por el testigo de `MF-13`; `MF-29-EMP-COR` lo retiro. `MF-29` sigue ABIERTO |
| `MF-29-EMP-COR` corrigendum del testigo | **Sellado GO** | **El testigo comparaba dos escalas.** `MF-13` puntuaba el cristal como PDBQT rigido (`TORSDOF 0`) y `MF-29-EMP` dockeaba uno flexible con hasta 6 torsiones; Vina divide la afinidad por `(1 + w_rot*N_rot)`. Preparar el **mismo** cristal como flexible lo empeora **1.055 kcal/mol** medianos, que cubre de sobra el deficit de 0.491 que se leia como fallo de busqueda. Corregido, el masivo puntua **mejor** en 36 de 48. 98 segundos de computo |
| `MF-13-ESCALA` ¿arrastra MF-13 el desajuste? | **Sellado GO** | **No.** En 102 de 116 el top-1 que uso `MF-13` viene de `molflex`, que docka `conf{cid}.rigid.pdbqt`: misma escala que su cristal rigido. Restringiendo el mejor dock a poses rigidas el gate queda **identico, 23/33 = 0.6970**, y ni un complejo cambia de veredicto. El `MIXTO` de `MF-13` se sostiene |
| `REC-09` aguas que bloquean el sitio | **Sellado INCONCLUSIVE** | `MIXTO` por tres centesimas (f=2/6=0.3333, corte en 0.30). Pero el mecanismo es real y enorme donde aplica: **`1fkh` pasa de +2.550 a -10.369** quitando **dos** moleculas de agua. 26 de 116 tienen agua bloqueante; el control sale limpio (delta mediano 0.000 en los sanos). `1d7i` y `1ew9` puntuan absurdo con **cero** aguas bloqueantes: su causa es otra |
| `MF-33-CRUCES` quienes son los 7 que no convierten | **Sellado GO** | **De los 7 que el ensemble flexible no convierte, 4 son cristales que puntuan absurdo**: 57.1% contra 4.9% entre los 41 que si. Enriquecimiento de 12x. Ademas, cuenca mas rugosa (frac. que regresa desde 0.5 A: 1.0 contra 0.6667) y mas aguas que **estorban** (0 contra 1 medianos) |
| `REC-12` cofactores no metalicos del sitio | **Sellado INCONCLUSIVE** | **No es medible con la fuente actual.** El `_protein.pdb` de PDBBind viene LIMPIADO: conserva aguas y metales y elimina el resto de heteroatomos. En los 48 disponibles los unicos HETATM son `HOH`, `CA`, `ZN`, `MG`, `HG`, `CU` y un `ACE` de cierre de cadena. **Todos los receptores del programa se construyeron desde una fuente que borra los cofactores, asi que un sitio incompleto por esa via seria invisible.** Exige la entrada original de RCSB: 116 descargas, mismo script |
| `MF-28` roadmap PRM — registro | **Sellado retroactivo** | Tenia resultados completos y ningun `manifest.json`, y el §1 lo daba por sellado desde el 19. Cerrado sin recomputar. La lectura no cambia |
| `REC-11` aguas sobre el docking **de novo** | **Sellado INCONCLUSIVE** el 2026-08-22 | **`SIN_DIFERENCIA_DETECTABLE`.** 116 de 116, cero fallos, 61.27 CPU-h. Cobertura del oraculo: CON aguas **94/116**, SIN aguas **96/116**; `b`=10, `c`=8, McNemar exacto **p=0.814529**, MDE **9.92 pp**. Es la medicion que `docs/51` §5 pedia, y responde con un **tercer** desenlace que aquel parrafo no contemplaba: la politica **se mantiene por inercia**, no confirmada. **Prohibido leerlo como equivalencia.** El secundario top-1 apunta al reves (CON 59 vs SIN 50, p=0.163) y **no tiene gate**: no se cita |
| `REC-05` metales sobre el docking de novo | **Sellado INCONCLUSIVE** el 2026-08-22 | **`SIN_DIFERENCIA_DETECTABLE`.** 29 de 29, 96 atomos de metal retirados. CON 24/29, SIN **25/29**; `b`=2, `c`=1, McNemar **p=1.0**, MDE observado **14.84 pp** —mejor que los 20.6 declarados, porque la discordancia real fue del 10.3%—. `ZN` en solitario (n=21) da lo mismo. **Re-alcanzado antes de correr**: aguas fuera porque `REC-11` no lo autorizo, cofactores fuera porque `REC-12-R1` midio n=2, y el gate por familia declarado inalcanzable con `CA`=7, `MG`=3, `MN`=3, `CU`=2. **Consecuencia de producto**: `preparer.py` borra hoy el 100% de los metales de los 387 targets, y esto mide que sobre 29 y con un conformero **no es detectablemente dañino** — no que sea inocuo |
| `MF-33-B-RET-R1` top-1 sobre el brazo flexible | **Sellado INCONCLUSIVE** el 2026-08-22 | **`NO_LEER_GATES_TECNICOS`.** G1 **perfecto (47/47 = 1.0000)**: reproduce el brazo B sellado dentro de 0.001 A. G0 **falla por UN dock de 970** —`1afl` conf29, Vina rc=1— y el contrato es ITT sin excepcion por tamaño, asi que los bloques cientificos **no se leen**. Fallo caracterizado como **ambiental**: stderr vacio, barra de progreso cortada, y re-ejecutado aislado da rc=0. `MF-33-B-RET-R2` repara ese dock con prerregistro propio. Ver §12.1 quáter |
| `MF-29-EMP-EXT` recuperar los dos expirados | **Sellado GO** el 2026-08-22 | **`OBJETIVO`, y el caso de borde no se materializo.** `1mmr` y `1nm6` no fallaron: **expiraron**: con el plazo en 72000 s las seis corridas terminan (33546.6 a 51275.8 s, todas sobre el `timeout` viejo de 14400). Mejora **uno** —`1mmr` +0.162; `1nm6` −0.011— asi que la union da **4/50 = 0.08**, que sigue siendo `OBJETIVO`. Si hubieran mejorado los **dos**, 5/50 = 0.1000 caia en `MIXTO` y cambiaba una lectura sellada. `MF-29-EMP` **no se re-sella**; la cohorte queda completa en 50 de 50 |

### El defecto abierto de MF-33 y MF-33-A2

> **RESUELTO el 2026-08-21 por `MF-33-A3`. Esta sección no se reescribe: describe
> correctamente el defecto, y lo que cambió es su desenlace.**
> El confundido era real —B conservaba 261 poses de mediana contra 9— pero **no explicaba
> la ventaja**. A3 igualó corridas, poses (261) y CPU (razón 1.196: gastó un 20% *más* que
> B) y aun así perdió **26 a 19**, con `g_B`=7 y `g_A3`=0, McNemar p=0.0156. Y el secundario
> lo cierra: **`A2` con 9 poses y `A3` con 261 dan el mismo 19**. Multiplicar por 29 las
> poses conservadas desde el mismo confórmero no mueve un solo complejo. La etiqueta
> `defecto-abierto` queda levantada y la magnitud de `MF-33` es citable.


La metrica es de **oraculo** —mejor RMSD entre las poses que el brazo **conserva**— y
`num_modes=9` limita las poses escritas **por corrida**, no las buscadas:

| Brazo | Corridas | Poses conservadas |
|---|---:|---:|
| A y A2 | 1 | **9** |
| B | 29 (mediana) | **261** |

B extrae su oraculo de **29x mas muestras** y ganaria aunque la busqueda fuese identica.
Es un artefacto de medicion, no un mecanismo, y suspende la **magnitud** de la
contribucion del ensemble en los dos registros. `MF-33-A3` la mide con poses, reinicios y
CPU igualados, dejando la conformacion de partida como unica diferencia.

**Lo que sobrevive sin reservas:** el brazo C tiene las mismas corridas y poses que B, asi
que **rigido 1/33 contra flexible 26/33** es limpio, y con el el corrigendum de `MF-09`:
su «en 30 de 33 no existe pose <=2 A» midio una limitacion del PROTOCOLO, no del espacio
alcanzable.

### Leccion de metodo de esta serie

Tres gates redactados, dos con la direccion de la comparacion ambigua. El primero se
detecto **antes** del resultado completo y se declaro; el segundo **despues**, y obligo a
tomar la lectura mas estricta —INCONCLUSIVE en vez de GO— aunque el criterio estadistico
se cumpliera (p=0.0391). El tercero, `MF-33-A3-PRE`, define `g_A3` y `g_B` explicitamente.
La regla que queda: **un gate que compara dos brazos nombra cual gana en cada direccion, o
no esta escrito.**

## 2. H1 — Deuda que hay que saldar antes de construir encima

**Por qué esto va primero:** el activo número uno del proyecto es que el registro es
auditable. Cada uno de estos elementos es algo que un revisor hostil encuentra en diez
minutos y que desmonta esa afirmación. Son baratos. No hay excusa.

| # | Qué | Por qué |
|---|---|---|
| 1 | **Volcar los 26 resultados del bloque del 18-08 al doc. 49** | `MF-17`, `MF-20`, `MF-31` y `MF-32` no se mencionan ni una vez en el documento vivo. El registro dice una cosa y el documento otra |
| 2 | ~~Arreglar el contador de `artifacts_science/README.md`~~ — **HECHO el 2026-08-23** | Estaba duplicado (63 + 89) y el segundo descuadraba. Ahora es **derivado** de `build_registro_cientifico.py`, con el comando dentro del propio README, y publica las **seis poblaciones** en vez del cociente `GO`/total, que era engañoso: 139 artefactos = 39 medición, 36 prerregistro, 23 hallazgo, 21 refutación, 11 inconcluso, 9 corrigendum. La única tasa con sentido es **hallazgo 23 contra refutación 21** |
| 3 | **Adoptar el CLA** | Único elemento con fecha de caducidad: el primer PR externo sin CLA congela la licencia para siempre. El archivo ya está escrito |
| 4 | ~~**Licencia de `rescoring/RTMScore/`**~~ — **HECHO 2026-09-01** | MIT upstream incorporada con atribución y gate de empaquetado |
| 5 | **Los 48 papers restantes del registro** | 46 de 94 escritos. Las dos columnas protagonistas están completas; falta `MF-33-A2` y las capas de contexto |
| 6 | ~~**Sacar las credenciales del servidor del código**~~ — **HECHO** (cerrado el 2026-09-22) | Usuario y contraseña en claro en `scripts/remote_docker_runner.py`, commiteados el 2026-08-16. La punta dejó de tenerlos el 2026-08-21 (`3bb3093` la contraseña, `376715b` el host y el usuario) y `scratch/` nunca llegó a versionarse. El historial que la contenía llegó al repositorio público el 2026-09-21; el 2026-09-22 se recreó el repositorio desde `publico` y la caché por SHA dejó de responder. La contraseña filtrada ya no era la vigente: el propietario la había cambiado hacia agosto. Queda como higiene, no como deuda: `PasswordAuthentication no` en el servidor, que ya se usa con llave |

**Qué lo cancela**: nada. Es deuda, no apuesta.

---

## 3. H2 — Cartera H: ser FEP+ ready de verdad

**Por qué es la prioridad de investigación:** es la única cartera con camino abierto, es
**ingeniería y no investigación** —no hay incertidumbre científica en declarar un
tautómero—, y es el puente al destino largo. Todo lo demás está cerrado por reglas de
futilidad.

Estado hoy, medido:

| Auditoría | Listos | Cuello |
|---|---:|---|
| `FEP-01` integridad del ligando | **39/203 (19%)** | 164 de 203 con tautómero ambiguo, **ninguno declarado** |
| `FEP-02` integridad del receptor | **83/203 (41%)** | 86 con huecos de cadena, 43 con el sitio repartido, 52 con metales, mediana de 10 aguas sin documentar |
| `FEP-03` series congenéricas | 91 parejas / 18 dianas | El conjunto se armó para **diversidad**, lo contrario de lo que FEP+ necesita |

Orden de ejecución:

1. **Declarar tautómeros.** ~~Sube `FEP-01` de 19% a >80% de un golpe.~~ **Hecho y medido
   (2026-09-23, `FEP-01-DECL`, GO):** 180/203 (88,7%) *declarados*, pero sólo 39 (19%)
   *resueltos*; 141 quedan en multiestado (mediana de 4 candidatos) y 22 pasan de 32. La
   predicción se cumplía por la letra y era engañosa en la sustancia. Para docking con
   Vina apenas importa; para FEP+ es determinante, porque el tautómero define qué átomos
   donan y cuáles aceptan puentes de hidrógeno. Siguiente: un modelo energético validado
   que descarte candidatos fuera de 2-3 kcal/mol (−RT ln p).
2. **Documentar receptores**: huecos de cadena, cadenas múltiples, metales, aguas
   estructurales frente a desplazables.
3. **Reconstruir la cohorte congenérica desde PDBBind**: pocas dianas con muchos análogos.
   No es un refactor — el conjunto actual tiene 104 dianas para 203 complejos y la mitad
   de los complejos son la única entrada de su diana. El grupo mayor disponible es de 23.
4. **`FEP-05`** export reproducible: SDF/PDB/JSON con hashes, versiones, caja, semillas y
   warnings.
5. **`FEP-06`** dry-run de transferencia — **el más valioso del programa entero ahora
   mismo**. Un tercero reconstruye el paquete sin conocer la sesión. Es la prueba de que
   existe lo que se vende en la vía de cualificación (ver `COMERCIAL.md` §2).

**Horizonte**: 12–18 meses para el conjunto completo; el 80% del valor está en los tres
primeros puntos, que son ~3 meses.

**Qué lo cancela**: nada previsible. Si `FEP-06` fallara —un tercero no puede reconstruir
el paquete— eso no cancela la cartera, la convierte en la única prioridad.

---

## 4. H3 — El primer usuario externo

**Por qué está al mismo nivel que la investigación:** 151 experimentos sellados
(2026-09-22) y **cero usuarios**.
Ese es el riesgo de muerte real del proyecto, no el científico. Una herramienta sin
usuarios muere aunque sea buena, y un usuario con nombre cambia de golpe toda solicitud
de financiación.

1. Identificar 5–10 grupos que hagan preparación estructural y sufran el problema que
   `FEP-01`/`FEP-02` documentan.
2. Ofrecer la auditoría de preparación sobre **sus** estructuras, gratis, a cambio de
   feedback. No se les pide que adopten el pipeline: se les da un informe.
3. Convertir al primero que responda en `FEP-06`.

**Qué lo cancela**: nada. Si tras 20 intentos nadie responde, el problema es el
posicionamiento y hay que revisarlo — eso también es información.

---

## 5. H4 — Producto: entregar confianza, no certeza

**Por qué:** `FEP-04` es el único resultado del programa que un usuario nota. Top-1
acierta 0.330; top-5 acierta 0.465; abstenerse en el 75% menos confiable sube a 0.620. Y
las tres señales son **gratis** — se calculan de poses ya generadas.

1. **Calibrar en `train`, medir en `val`/`test`.** La curva de `FEP-04` es optimista
   porque las señales se observaron sobre los mismos datos donde se midieron. Sin esto no
   es un producto.
2. **Incorporar repeticiones por semilla.** `FND-03` midió rangos de hasta 4 Å por
   complejo entre semillas. Una confianza que ignora eso miente.
3. **Combinar las tres señales.** No se hizo.
4. **Cambiar la interfaz**: dejar de entregar una pose y entregar K con su confianza. Es
   un cambio de diseño, no de investigación.

**Horizonte**: 3–6 meses.

**Qué lo cancela**: si la calibración en `train` no transfiere a `val`/`test`, la
abstención no es un producto y hay que decirlo.

---

## 6. H5 — El puente a medicina de precisión

**Por qué este camino y no otro:** entre predecir una pose y predecir la respuesta de un
paciente hay cuatro saltos —afinidad, engagement in vivo, PK/PD, heterogeneidad clínica—
y cada uno es un campo entero. La interpretación de variantes de resistencia es el único
puente que **no exige cruzarlos todos**, porque sigue siendo una pregunta estructural.

Encaja por cuatro razones concretas:

1. Es estructural: es lo que el stack hace.
2. El método es **ΔΔG de unión por mutación**, que es exactamente adonde lleva ser FEP+
   ready. La ruta corta y la meta larga son la misma ruta.
3. `FEP-04` deja de ser un extra y pasa a ser **requisito**: una herramienta que dice "esta
   variante no la puedo llamar" es clínicamente usable; una que siempre responde, no.
4. Tiene validación retrospectiva disponible: paneles de mutaciones de resistencia
   conocidas con desenlace documentado. Se puede medir sin acercarse a un paciente.

Secuencia, sin fechas porque dependen de colaboradores y no de código:

1. ΔΔG de unión sobre mutaciones conocidas de resistencia (EGFR, ALK, BCR-ABL).
2. Validación retrospectiva contra el desenlace clínico documentado.
3. Colaboración con un grupo clínico.
4. Sólo entonces, y sólo si los tres anteriores salen, plantear vía regulatoria.

**Techo realista declarado**: ser **la capa computacional auditable** que usan grupos
clínicos. No el producto clínico. Eso último exige empresa, equipo regulatorio y socios
clínicos — problema organizativo, no técnico.

---

## 7. H6 — Sostenibilidad

Detalle completo en [`COMERCIAL.md`](COMERCIAL.md). Resumen del orden:

1. Un usuario externo con nombre (H3).
2. `FEP-06` ejecutado — la prueba de que la cualificación existe.
3. Cartera H entregada — hasta entonces no hay producto que cualificar.
4. Primer paquete de cualificación vendido, aunque sea a coste.
5. Consorcio, cuando haya varios interesados y algo que dirigir.

En paralelo y sin esperar a nada: **financiación no comercial** — CZI EOSS, ASAP
Discovery, Open Force Field / MolSSI, Wellcome, NumFOCUS. En todas, el activo diferencial
no es el docking: es el registro con los resultados negativos.

---

## 8. Lo que NO vamos a hacer

Tan importante como la lista de arriba, y con la misma fuerza de regla.

| Prohibido | Por qué |
|---|---|
| `MF-03`, `MF-04`, `MF-05`, `MF-07` | Ajustan parámetros del mismo buscador. Bloqueados hasta que un preregistro declare qué cambia en el **generador** |
| `RS-11`, `RS-12`, `RS-13` | Bloqueados **permanentemente** bajo este diseño. Cualquier reapertura exige denominador en número de complejos (~1,972 según `FND-04`), no más features ni semillas |
| Disparar `D-RC-CONFIRM` | Se usa una sola vez y no hay segundo conjunto. Con el selector empatando o perdiendo, consumirlo destruye el activo |
| Competir en benchmark de pose contra DiffDock / Boltz / Chai | Con una GTX 1660 y un servidor de 4 núcleos sin GPU, no va a ocurrir |
| Cambiar la licencia del código | Incorrecto hoy mientras Open Babel se importe, y prematuro sin un usuario que lo pida. Ver `LICENSING.md` |
| Vender exclusividad sobre un resultado o retrasar un negativo | Es lo único que haría que el registro dejara de valer |

---

## 9. Cómo se decide qué entra aquí

Las reglas ya están en el doc. 49 y se repiten porque son el mecanismo que impide que
este roadmap se convierta en una lista de deseos:

- **Efecto mínimo detectable declarado antes de correr** (§20.9). Si el diseño no puede
  resolver el efecto buscado, se sabe cuando todavía se puede cambiar el diseño.
- **Regla de futilidad por cartera** (§19.1): tres NO_GO consecutivos sobre el mismo
  espacio, el mismo n y la misma unidad de agrupamiento cierran la línea sin nueva
  deliberación.
- **Reabrir exige declarar qué cambió en el denominador.** No basta con una arquitectura,
  una pérdida, una semilla o un peso nuevos.
- **Todo resultado distinto del confirmatorio es exploratorio**, tenga gate preregistrado
  o no.

---

## 10. Revisión

Los dos disparadores de esta revisión —`MF-28` y `MF-29-EMP`— ya cerraron, ambos sellados
el 2026-08-20. `MF-28` NO_GO: la cartera C no se reabre por ahí y H2 se lleva el
presupuesto de atención. `MF-29-EMP` GO con lectura **OBJETIVO**: en el régimen de ≤6
torsiones, subir el presupuesto del mismo buscador está medido y no rinde. El desajuste de escala rígido/flexible que
destapó su corrigendum **no alcanza a `MF-13`**: `MF-13-ESCALA` lo comprobó y su gate no se
mueve, así que el «~70% búsqueda» que el §8 usa sigue en pie. El §12 recoge el estado
operativo mientras tanto.

---

## 11. Ideas apuntadas — no ahora, pero que no se pierdan

Cosas evaluadas y descartadas *para este momento*, con su enlace y el motivo. Existen
para no re-litigarlas dentro de seis meses y para que, si algún día se retoman, se
retomen por donde toca.

### 11.1. Potenciales interatómicos aprendidos (MLIP) — SÍ tiene anclaje

**Fuente:** [Can AI understand a fundamental concept of chemistry? — USC Viterbi, 2026-08](https://viterbischool.usc.edu/news/2026/08/can-ai-understand-a-fundamental-concept-of-chemistry/)
· Nomura, Nakano, Vashishta & Kalia, *Nature Communications*, 2026-08-18.

**Qué es realmente.** No es un modelo entrenado para predecir enlaces: es
**interpretabilidad** de uno que ya existía. Cogieron `Allegro-FM` —un potencial
interatómico aprendido sobre energías y fuerzas cuánticas de 89 elementos— y
construyeron **E3D** (Edge-wise Emergent Energy Decomposition) para repartir su energía
por arista del grafo. El hallazgo: el concepto de enlace **emergió** sin enseñarlo, y las
energías de disociación extraídas de sus internos coinciden con las experimentales.

**Por qué NO se replica con XGBoost.** Dos razones, ninguna de potencia: (a) E3D
descompone sobre aristas de un grafo y un ensemble de árboles sobre features tabulares no
tiene dónde repartir nada; (b) entrenar con energías de enlace destruye el resultado, que
consiste precisamente en que el modelo nunca las vio.

**Lo que sí aplica: la clase de modelo, no el hallazgo.** Un MLIP es la versión mejor del
campo de fuerza que el programa ya probó. Y hay un indicio positivo propio que lo ancla:

> `MF-16-R1` midió que el potencial físico **relajado** ordena mejor que Vina en el
> estrato difícil — rho 0.199 frente a 0.132, delta pareado **+0.107**, mejor en 16 de 25
> — y pierde en control. Es el único indicio de que la física aporta donde Vina es débil.

Puntos de conexión: `MF-16-R1` (rescoring relajado), `RS-04-OOF` (el strain MMFF94s no
tuvo poder de selección) y la relajación de `MF-10`.

**Tres bloqueadores, en orden de gravedad:**

1. **`MF-10` predice el mismo NO_GO para conversión.** Ninguna pose se movió más de
   0.725 Å cuando hacían falta ~1 Å, y eso no es precisión del campo de fuerza: es que
   **la minimización local es local**. Un potencial mejor mueve el mínimo, no cruza
   barreras.
2. **Coste.** La relajación ya costaba ~20 s/pose con MMFF94s; un MLIP es más caro, y hay
   34,302 poses.
3. **Dominio.** Se entrenan mayoritariamente en materiales y moléculas pequeñas; cubrir 89
   elementos no garantiza tratar bien un complejo proteína-ligando solvatado.

**Prueba barata si se retoma:** repetir `MF-16-R1` cambiando sólo el potencial, sobre los
mismos 25+13 complejos donde ya existe la comparación pareada contra Vina. Si no supera el
delta +0.107 que ya dio un campo de fuerza clásico, se cierra sin gastar más. Es un
experimento, no una cartera.

#### Contraparte aplicada: MLIP con embedding electrostático para energía libre

**Fuente:** [Evaluating Electrostatic Embedding MLIP/MM for Relative Binding Free Energy
Calculations](https://arxiv.org/html/2608.13355v1) — Stephen E. Farr y Gianni De
Fabritiis (Acellera Labs / Universitat Pompeu Fabra), arXiv 2608.13355.

Donde la nota anterior es interpretabilidad, ésta es la versión aplicada y con números.
Su tesis: las **cargas fijas** de los campos de fuerza clásicos son el cuello de botella
en predicción de afinidad. Su solución: un MLIP (TensorNet2) que predice cargas RESP
**dependientes de la geometría**, acopladas al entorno MM, entrenado sobre 10^6
conformaciones.

| Resultado | Antes | Después |
|---|---:|---:|
| TYK2, RMSE de ddG frente a GAFF2 | 0.86 | **0.45** kcal/mol |
| TYK2, frente a embedding mecánico | 0.77 | **0.45** kcal/mol |
| CDK2, Thrombin, p38, JNK1 | — | comparable a los clásicos |

**La ganancia está en 1 diana de 5.** En las otras cuatro empata, y ellos no lo presentan
como victoria general.

**Por qué toca a este programa directamente.** `RS-03-PARAM-B` midió lo mismo desde el
otro lado, sobre 115 ligandos con mapeo biyectivo verificado: |dq| mediana 0.0118 e por
átomo, y |dE| de punto único **mediana 24.3 kJ/mol, máxima 216.4** — «del orden de lo que
un rescoring pretende resolver». Es validación externa de una preocupación levantada aquí
con datos propios.

**Está río abajo de donde está el programa.** RBFE asume pose correcta, preparación
limpia y series congenéricas: hoy 19%, 41% y una cohorte armada para diversidad. Este
paper mejora un cálculo que todavía no se puede alimentar. **Es un motivo para terminar
H2, no para abrir un frente nuevo.**

**Inversión estratégica que conviene ver:** si el error de ddG baja de 0.86 a 0.45
kcal/mol, el valor de una buena preparación **sube**. Un método más preciso es más
sensible a los errores de entrada — un tautómero mal declarado importa más con medio
kcal/mol de resolución que con dos. Los 164 tautómeros sin declarar de `FEP-01` valen más
hoy que ayer.

**Su limitación, que es `MF-26` con otro nombre:** «target-dependent performance suggests
single-molecule benchmarks don't predict alchemical accuracy». Una curva medida en una
población no predice otra. Argumento externo a favor de la regla de MDE declarado antes.

### 11.2. Modelos de segmentación (SAM y familia) sobre las seis caras — NO tiene anclaje

**Veredicto: no encaja, y la §18.2 ya lo decía** — «no se usarán fotografías RGB
decorativas; cada vista será un tensor científico multicanal». El valor de esos modelos
está en sus priors preentrenados sobre **fotografías del mundo real**; sobre un tensor de
ocupación atómica esos priors no valen nada y un UNet pequeño propio hace lo mismo más
barato.

La razón de fondo: **la segmentación responde «¿qué píxeles pertenecen a este objeto?», y
aquí ya se conocen los átomos, sus coordenadas y sus elementos.** No hay problema de
percepción que resolver; se empezaría tirando información exacta para recuperar una
aproximación. Agrava además el riesgo 4 de la §18.3 (identidades ambiguas), porque
descartaría los canales que desambiguan.

**Dónde sí encajaría algún día**, por orden de defendibilidad: automatización de
laboratorio si se llega a validación húmeda (detectar cristales en gotas, leer placas) —
ahí sí son fotografías reales; mapas de densidad de crio-EM o cristalografía, que sí son
un problema de percepción genuino aunque volumétrico; minería de figuras de literatura.

**Lo que sí decide la cuestión y no necesita ningún modelo:** el riesgo 1 de la §18.3 —
medir cuánta geometría y cuántos contactos se recuperan con 1, 3 y 6 vistas. Es geometría
pura, cuesta una tarde, y si seis vistas pierden los contactos que importan **ningún**
modelo los recupera y la cartera I se cierra antes de invertir en ella.

### 11.3. Economía de modalidades — lectura, no construcción

**Fuente:** [Lessons from drug revenue life cycles: distributions across modalities and
therapeutic areas](https://www.nature.com/articles/s41587-026-03278-y) · *Nature
Biotechnology*, 2026-08-18. Tras muro de pago; sólo se pudo leer el resumen.

Analiza fármacos aprobados por la FDA y encuentra que los ciclos de ingreso están
repartidos de forma desigual entre **modalidades** y **áreas terapéuticas**, con
implicaciones de política tras la Inflation Reduction Act.

Aplicabilidad técnica: ninguna. Relevancia estratégica: responde la pregunta de **molécula
pequeña frente a biológico** que condiciona el §5 (medicina de precisión) y la
[estructura comercial](COMERCIAL.md). Merece leerse completo si se consigue acceso, antes
de comprometer la meta larga a una modalidad.

---

## 12. Estado al cierre del 2026-08-20 — qué hacer en la siguiente sesión

Escrito para poder retomar sin releer nada. Dos listas: lo que cuesta horas de máquina y
lo que se cierra en minutos.

### 12.1. Experimentos LARGOS pendientes

| # | Experimento | Coste | Estado | Por qué |
|---|---|---|---|---|
| ~~1~~ | **`MF-33-A3`** — **HECHO el 2026-08-21** | 50.9 CPU-h reales · **6.9 h** con 10 workers | **Sellado GO** | Desbloqueo el GO suspendido: `defecto-abierto` levantado en `MF-33` y `MF-33-A2`, magnitud citable |
| 2 | **`MF-33-EXT`** — cobertura del oráculo con generador **flexible** sobre los 116 | **103 CPU-h medidas** · 10.3 h con 10 workers, 25.7 h con los 4 del servidor | **Diseñado y prerregistro SELLADO. Un comando.** Listón heredado del G5 de `MF-02D` (0.90); base rígida **0.7931** —no 0.9310, que es otra métrica—. Registra la curva de cobertura contra presupuesto, así que **no depende de A3 para ejecutarse, sólo para titularse** | `RC-F0-V2-EXT` midió que el **93.9%** del conjunto viene del protocolo rígido. Es el denominador de media docena de conclusiones |
| 3 | ~~`MF-30`~~ — **re-alcanzado el 2026-08-20** | — | **Benchmark opcional, fuera de la cartera** | Ver `MF-30-ALCANCE`. Su gate está **caducado 8.67×** (pedía batir 3/33 cuando el ensemble propio da 26/33); su premisa la contradice PoseBusters 2024 (**Vina 58%, Gold 55%, DiffDock 12%** con validez física); y exige GPU en tiempo de ejecución, que la restricción de producto prohíbe. Tres condiciones de reapertura declaradas |
| 4 | Regeneración completa de la cohorte con docking flexible | Programa, no experimento | **No decidir sin (1)** | Ver §11 y el triaje de los 17 consumidores |

**VENTANA RESERVADA — `MF-33-B-RET`, en cuanto `MF-33-EXT` libere la máquina.**
Prerregistro **sellado** (`MF-33-B-RET-PRE`), ~42.6 CPU-h, ~4.5 h con 10 workers, un comando:

```
MF33BRET_VINA=D:/moldesign-build/tools/vina/vina.exe python scripts/run_mf33bret_top1_flexible.py --workers 10
```

Repite el brazo B **sin tirar las poses**, para medir `top-1`/`top-5` y validez física sobre
el brazo que el paper defiende. Cierra la amenaza T1 del `docs/52`: la métrica del programa es
de **oráculo** y `MF-09` midió que el top-1 acierta **0/33** en el estrato difícil. Las poses
originales no existen —`run_mf28_roadmap.py` las escribió en un `TemporaryDirectory`—.

**El comando de (1):**

```
python scripts/run_mf33a3_reinicios.py --workers 10
```

Lanzarlo con la máquina descansada: son ~90% de CPU sostenido durante 4–6 h.

**Cerrado el 2026-08-20:** `MF-29-EMP` terminó en el servidor tras **34 h** (`Exited (0)`,
contenedor `mf29emp_full`) y está **sellado GO** con lectura `OBJETIVO`. Su testigo se
retiró el mismo día con `MF-29-EMP-COR` —prerregistrado y sellado antes de correr, 98 s de
cómputo—, que midió que comparaba un cristal rígido `TORSDOF 0` contra scores flexibles.
Artefactos descargados y verificados por hash. Lecturas completas en sus `LECTURA.md`.

Queda una sola cosa suya, y es de **baja prioridad**: `1mmr` y `1nm6` expiraron y no
fallaron (3 × el `timeout=14400` en duro de `run_mf29emp_optimo_global.py:146`).
Recuperables por ~12 h de servidor; no cambian la lectura salvo empate improbable.

> **Hecho el 2026-08-22 por `MF-29-EMP-EXT`, sellado GO.** Costó 36.7 h de servidor, no 12.
> El «empate improbable» **no ocurrió**: mejoró uno de los dos, la unión da 4/50 = 0.08 y la
> lectura `OBJETIVO` de `MF-29-EMP` se sostiene sobre la cohorte completa. `MF-29-EMP` no se
> re-selló. Lectura en `scripts/artifacts_science/MF-29-EMP-EXT/LECTURA.md`.

### 12.1bis. Estado al 2026-08-22 — el servidor está libre y la máquina local no

**El servidor terminó sus dos trabajos y está ocioso.** `REC-11` (30.8 h) y
`MF-29-EMP-EXT` (36.7 h) cerraron, se descargaron con SHA-256 verificado contra el remoto y
están sellados en local. En ambos casos el hash del runner coincide con el sellado en su
prerregistro, en local y en el servidor. Ver §1.

> **Superado el 2026-08-22/23.** Este párrafo describía a `MF-33-B-RET-R1` parado en 13 de
> 48. Terminó los 48 y quedó **sellado `INCONCLUSIVE`**; el desenlace está abajo, en §12.1
> quáter. La sección no se reescribe: describía correctamente el estado de ese momento.

**Hueco de contrato detectado, sin arreglar:** ni `run_rec11_aguas_denovo.py` ni
`run_mf29empext_recuperar_expirados.py` escriben `failures.jsonl`, que el §17 del `docs/49`
exige. En los dos casos hubo cero fallos y el archivo se creó vacío al sellar, pero los
próximos runners deben escribirlo aunque esté vacío.

**Deuda que sigue abierta:** `REC-09`, `REC-12`, `MF-29-EMP`, `REC-11` y `MF-29-EMP-EXT` no
tienen sección de resultado en el `docs/49`. Es el mismo punto 3 de §12.2 — el volcado
pendiente al doc. 49 —, ahora con cinco artefactos más.

### 12.1ter. Cerrado el 2026-08-22 en el servidor, mientras R1 corría en local

| Experimento | Decisión | Resultado |
|---|---|---|
| `REC-12-R1` cofactores desde RCSB | **GO** | **`HAY_RECEPTORES_INCOMPLETOS`.** G1 de validez de la fuente **0.9914** contra el 0.0208 con que falló `REC-12`: las 116 entradas de RCSB se bajaron sin una ausencia y **la pregunta era contestable**. 15 de 116 pierden en `rec.pdbqt` un heteroátomo del sitio, pero **15 es cota superior**: el núcleo robusto son **2** —`1gwv` (UDP) y `1lbk` (GSH)—, 11 son ligandos o inhibidores que quizá deban descartarse, y 2 escaparon a las listas (`CL`, `DMF`). Desbloquea el diseño de `REC-05` |
| `REC-11-CRUCES` alcance del criterio de REC-09 | **GO** (medición **post-hoc declarada**) | El criterio de 2.6 Å no basta fuera del cristal: **5 de los 10 complejos rescatados al quitar las aguas tienen CERO bloqueantes** —`10gs` `1d7i` `1ela` `1fh7` `1nje`—, y entre los 18 discordantes no predice la dirección (p=0.152). Hay enriquecimiento de 3.46× con p=0.0437, **que no se cita**: la tabla se vio antes de escribir el registro y está declarado así en el manifest |

**Preparación hecha de paso:** se subieron al servidor los **2308 `conf*.flex.pdbqt`** de los
116 (8.6 MB, hashes verificados). Antes sólo tenía `conf0.flex` y el resto en `.rigid`, que
es exactamente lo que habría hecho `K=1` y vaciado la corrida de `MF-33-B-RET-R1` si se
hubiera lanzado allí.

**Barrido de lo largo pendiente:** en la cartera B —la prioridad de ejecución declarada por
§19.1— quedan `REC-02`, `REC-05` y `REC-06` sin ejecutar, y **ninguno es lanzable hoy**:
`REC-02` exige mapear las predicciones de MolPocket a la cohorte, `REC-06` exige
conformaciones alternativas de receptor que no están curadas, y `REC-05` estaba bloqueado
por lo que `REC-12-R1` acaba de desbloquear.

### 12.1 quáter. Estado al 2026-08-23 — `MF-33-B-RET-R1` cerró, y no se lee

**`MF-33-B-RET-R1`: sellado `INCONCLUSIVE`, lectura `NO_LEER_GATES_TECNICOS`.**

| Gate | Resultado |
|---|---|
| **G0 técnico** | **FALLA.** 48/48 complejos completos, pero **1 fallo** de 970 docks |
| **G1 reproducción** | **PASA perfecto: 47/47 = 1.0000** frente a un mínimo de 0.95 |

El fallo es `1afl` confórmero 29, Vina `returncode 1` a los 154.9 s. El contrato es **ITT** y
no admite excepción por tamaño, así que **los bloques científicos se calcularon pero no se
leen ni se citan**. La tentación de leerlos igualmente por 1 dock de 970 es exactamente lo
que el gate existe para impedir.

**El fallo está caracterizado y no es química:** el stdout muestra que Vina calculó el grid y
empezó a dockear, con la barra de progreso cortada a media altura y **stderr vacío**;
re-ejecutado aislado con el protocolo idéntico termina `rc=0` y nueve poses. El checkpoint se
escribió mientras en la misma máquina corrían PoseBusters, `pytest` y generación de
confórmeros. **Es contención de recursos** — la trampa que §12.3 ya tenía documentada, ahora
con un coste medido: invalidó la lectura de una corrida de 970 docks.

> **Lección operativa, y va a §12.3:** una corrida preregistrada no comparte máquina. Ni con
> tests, ni con diagnósticos, ni con otra corrida. El coste de ignorarlo no es lentitud: es
> un gate perdido.

**`MF-33-B-RET-R2` en curso**, prerregistro sellado (`MF-33-B-RET-R2-PRE`). Reusa verbatim
los 47 checkpoints buenos de R1 con su SHA-256 registrado uno a uno, re-ejecuta **sólo**
`1afl` con el protocolo importado de R1, y recalcula los gates con las reglas selladas sin
tocar ninguna. Tres cosas quedaron declaradas antes de correr:

1. la condición de ejecución es **máquina en reposo**, verificada antes de lanzar;
2. **R2 no es ciego** —al diagnosticar se vieron los bloques científicos de R1— y queda
   prohibido presentarlo como confirmación ciega. Lo que sigue sellado e inamovible es la
   **regla de decisión**; lo que se perdió es la ceguera sobre el desenlace;
3. **un solo intento**: si `1afl` vuelve a fallar, no habrá R3 por repetición.

`MF-33-B-RET-PARTIAL` sigue congelado y sellado `INCONCLUSIVE` en el commit `3bb3093`.

**Y lo que R1 sí demostró aunque falle su gate:** la retención forense —48 checkpoints, 48
`per_pose`, **969 PDBQT crudos** y 1940 logs— es lo que hizo posible diagnosticar el fallo en
minutos. El `MF-33-B-RET` original no guardaba geometría y por eso quedó forense e ilegible.
**R1 justifica su propio diseño en el mismo acto de fallar.**

### 12.1 quinquies. Estado al cierre del 2026-08-23 — y un corrigendum, cerrado

**Cerrados hoy:** `REC-05` (`INCONCLUSIVE`), `MF-33-B-RET-R1` (`INCONCLUSIVE`),
`MF-33-B-RET-R2` (**`GO`**, `EL_CUELLO_SE_DESPLAZA_A_LA_SELECCION`), `MF-33-PB`
(`INCONCLUSIVE`), `PREP-01` (`GO`), `MF-33-MIN` (**cancelado antes de ejecutar**) y
`MF-33-H-COR` (**`GO`**, `CORRECCION_CONFIRMADA`).

> ## ✔ CORRIGENDUM CERRADO — `MF-33-H-COR`, sellado
>
> **La reconstrucción usada para PoseBusters conservaba hidrógenos no presentes en el PDBQT
> en coordenadas cristalográficas incompatibles con la pose dockeada.** Con átomos pesados
> idénticos y los hidrógenos regenerados desde la geometría dockeada y relajados con los
> pesados fijos, la tasa PB-valid pasa de **2.64% a 99.48%** en el brazo flexible (8181 de
> 8224) y de **12.07% a 93.10%** en los top-1 rígidos (216 de 232).
>
> **164/164 trabajos**, salida 0. Las cinco invariantes se cumplen en las **8456** poses:
> desplazamiento pesado máximo **0.0 Å**, cero hidrógenos heredados del cristal, **cero**
> violaciones. La rama histórica de la misma tubería reproduce **complejo a complejo y sin
> una sola discordancia** lo que sellaron `MF-33-PB` y `MF-33-TOP1`, así que la única variable
> que cambia es la reconstrucción. Descarga verificada: 331 archivos, 331 SHA-256 coinciden.
>
> **Invalidado y reemplazado:** 217/8215 = 2.64%; el 97.3% de fallos por `internal_energy`;
> el 8/48 contra 10/48; el 8.62% contra 15.52%; y «la validez física es deficiente», «el
> ensemble no la arregla» y «una minimización post-docking atacaría el problema».
>
> **Tres cosas que hay que decir al citarlo.** (1) El 99.48% es **condicional a una
> reconstrucción canónica de hidrógenos**: el PDBQT es de átomo unido y no trae la geometría
> explícita, así que «el pipeline produce 99.48% de poses físicamente válidas» es incorrecto
> sin esa cláusula. (2) **No hay evidencia interpretable de diferencia entre brazos** —48/48
> contra 47/48 en flexible, p=1.0; 106/116 contra 110/116 en rígido, p=0.289— y eso **no es**
> equivalencia. (3) **No** demuestra exactitud de pose ni unión.
>
> **El defecto también contaminaba `double_bond_flatness`** (598 → 0), no sólo la energía:
> la afirmación previa de que sólo estaba afectada `internal_energy` era incompleta.

### 12.1 sexies. `PROD-PV-H-01` — cerrado, y con él el episodio

**`PROD-PV-H-01` (`GO`) cierra las dos deudas que el corrigendum dejó sobre producción**, en
direcciones distintas y sobre 232 poses.

- **Representación de hidrógenos: sin efecto detectable, y el diseño no tuvo poder para
  detectarlo.** 0 discordantes entre la ruta mixta y la canónica bajo el evaluador oficial —
  pero **las 232 pasan**, así que no hubo un caso discriminante. El `energy_ratio` va de
  −20.3 a 19.1 contra un umbral de 100.0. No se afirma equivalencia general.
- **El proxy energético discrepa, y siempre hacia el falso rechazo:** **33/232 = 14.2%**,
  todas `proxy FALLA → oficial PASA`. **No puede llamarse `internal_energy`.** Consecuencia
  de producto ya aplicada: el escalón degradado sólo emite **REVISIÓN**, nunca FALLA.
- **Hubo que reparar el instrumento antes.** El lector confundía el tipo AutoDock de las
  columnas 77-78 con el símbolo químico y cubría **40/232**, con el fallo **correlacionado
  con la aromaticidad**. Con plantilla química + `index_map` + columnas fijas cubre
  **232/232**. Los 6 casos restantes eran pseudo-átomos de pegado de macrociclo.

**Editorialmente NO abre línea propia:** `NO_PAPER_STANDALONE`, evidencia de producto
incorporable a `MF-33` como nota técnica, suplemento o sección metodológica. Etiquetado en
`_taxonomia.json`.

**Con esto se congela la investigación y se vuelve al MVP.**

**Lo que queda abierto ya no es el rediseño de `MF-33-MIN`**, que se cancela definitivamente:
no hay tensión generalizada que minimizar. Lo que queda es **el residuo**, y es una pregunta
mejor: **43 de 8224** poses flexibles siguen inválidas, concentradas en **siete complejos**
—21 en `1nm6`, 9 en `1mmq`— con fallos **geométricos** (`internal_steric_clash` 23,
`minimum_distance_to_protein` 13, y 7 poses que fallan `bond_angles`, `bond_lengths` e
`internal_energy` siempre juntos). Caracterizar ese subconjunto es barato y localizado.

### 12.2. Victorias rápidas — minutos o menos

Ordenadas por valor, no por esfuerzo. Ninguna necesita cómputo pesado.

1. **Los 48 papers que faltan** (56 de 104 escritos). Cero cómputo. Las dos columnas
   protagonistas están completas; falta el grueso de mediciones y prerregistros.
2. **Los 29 fronterizos de `FEP-02-EXT`** (huecos a 8–15 Å): mirarlos caso por caso para
   repartirlos entre reparar y declarar.
3. **Deuda de H1**, toda de minutos: volcar los 26 resultados del bloque del 18-08 al
   doc. 49; arreglar el contador duplicado y descuadrado de
   `scripts/artifacts_science/README.md`; mantener la atribución MIT de `rescoring/RTMScore/`;
   sacar las credenciales del servidor de `scripts/remote_docker_runner.py` y `scratch/`.
4. **Los 54 tautómeros de `FEP-01-EXT`**, empezando por la serie `1m0n`/`1m0o`/`1m0q`, que
   comparten patrón N/N/O — una decisión para la serie, no tres.

**Cerradas el 2026-08-20:** los dos cruces de `MF-33` (ahora `MF-33-CRUCES`, y con un
tercero que no estaba en la lista: el solape con los cristales absurdos), y la política de
aguas, declarada en `docs/51_POLITICA_DE_AGUAS.md` con `REC-09` como base medida.

**Retirada el 2026-08-20:** el corrigendum de `MF-13` figuró aquí unas horas como
prioridad 1, por suponer que arrastraba el desajuste de escala de `MF-29-EMP-COR`.
`MF-13-ESCALA` lo midió y no lo arrastra. Anotado para que nadie lo vuelva a abrir.

### 12.3. Trampas conocidas de esta máquina

- **`timeout` por debajo del tiempo de un complejo produce síntomas idénticos a un fallo
  real.** Un `BrokenProcessPool` y un exit 0 sin salida fueron ambos plazos míos matando el
  árbol de procesos, no bugs del experimento.
- **`experiment_manifest.py init --force` vacía los skeletons.** Para re-inicializar un
  experimento con resultados: respaldar, `rm -rf` el directorio, `init` limpio, restaurar.
- **`maintain` no puede reparar `dataset_hashes`** por diseño. Si se selló código como
  dataset, ese artefacto no vuelve a validar (`FND-01-SMOKE`).
- **El parser del registro tenía un bucle infinito** con líneas de párrafo que empiezan por
  `|`. Corregido con garantía de avance el 2026-08-20, tras consumir 7.2 GB.
- **Una corrida preregistrada NO comparte máquina.** Ni con tests, ni con diagnósticos, ni
  con otra corrida. El 2026-08-22 la contención con PoseBusters, `pytest` y generación de
  confórmeros mató **un** dock de 970 en `MF-33-B-RET-R1`, y ese único fallo hizo caer su G0
  y dejó ilegibles unos bloques científicos que ya estaban calculados. El coste no es
  lentitud: es un gate perdido y un R2 que ya no puede ser ciego.
- **La prueba técnica va ANTES de sellar el prerregistro, no después.** El 2026-08-23 dos
  prerregistros sellaron scripts rotos y costaron un `-R1-PRE` cada uno (`MF-33-PB`,
  `MF-33-MIN`). Sellar antes de probar **no gana ceguera** —la prueba técnica corre con
  `--limite`, que por contrato produce `NO_LEER_GATES_TECNICOS`— y cuesta un artefacto extra
  cada vez. Orden correcto: escribir el runner → prueba técnica → sellar → ejecutar.
- **Reimplementar lo que un módulo sellado ya resuelve cuesta caro.** Ese mismo día, una
  reimplementación de la llamada a PoseBusters contaba el check `rmsd_` entre los controles
  físicos, lo que habría convertido «validez física» en «válida **y además** acertada». El
  módulo sellado ya lo separaba y lo documentaba en sus líneas 101-108. La regla del §17
  —reusar por composición— aplica también dentro de `scripts/`.
- **El contador del registro se mantiene solo o se pudre.** Se escribió a mano dos veces y
  las dos se pudrieron —llegó a haber dos bloques simultáneos con 63 y 89 artefactos, y el
  segundo descuadraba—. Desde el 2026-08-23 es derivado, con el comando dentro del propio
  `scripts/artifacts_science/README.md`.
