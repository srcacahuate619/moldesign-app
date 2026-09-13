# 72 — Primera tanda del sello del catálogo: los que acoplaban contra el vacío

**Fecha:** 2026-09-02
**Antecede:** `71_HALLAZGO_CADENA_RECEPTOR_Y_PENDIENTES.md`
**Herramientas:** `scripts/triaje_receptores_al_vacio.py`,
`scripts/aplicar_rescates_mecanicos.py`, `scripts/anotar_sitio_en_catalogo.py`
**Estado:** aplicado y verificado. Deuda restante declarada y acotada por prueba.
**Al cierre:** 380 de 385 receptores pasan el expediente (§13). Ingesta automática al 100% (§14) y C1 cerrado (§15).

---

## 0. El objetivo, dicho antes de los números

Los 387 receptores que entrega la aplicación son la base del producto: tienen
que sostener el sello al derecho y al revés. **Eso no significa «los 387 son
perfectos».** Significa que cada uno tiene una decisión con evidencia adjunta, y
que el que no la tenga sale del catálogo. Un catálogo con un asterisco no tiene
sello.

Este documento registra la primera tanda: lo que estaba averiado y se pudo
arreglar hoy, lo que sigue averiado y por qué, y lo que ahora se declara al
usuario en vez de callarse.

---

## 1. Lo que se encontró al mirar de cerca

El doc 71 dejó el catálogo en `OK 280 · MULTICADENA 98 · REVISAR 9`. Ese
recuento por clase esconde lo importante: dentro de esos 107 sin resolver había
un subconjunto que **no esperaba una decisión científica, sino una reparación**.

**25 receptores donde la cadena declarada aportaba el 0% de los átomos de la
caja de docking.** `preparer.py` conserva esa cadena, la cadena no tiene nada
dentro de la caja, y Vina acopla contra espacio vacío y devuelve una afinidad
igualmente. Es el modo de fallo A del doc 71 —el de 1IAS— vivo en 25 sitios.

### El dato que explica los 25 de una vez

> **En ninguno de los 25 hay un solo hotspot que nombre la cadena declarada.**
> Cero de 25.

Los hotspots vienen con prefijo de cadena (`Q:TYR66`) y son una anotación
independiente. Que nunca coincidan no es casualidad: **el campo `chain` no está
mal anotado en estos receptores, está sin anotar.** 23 de los 25 declaran `"A"`,
que es exactamente el `default="A"` de `TargetORM.chain`. La distancia mediana
de esa cadena al centro de la caja es de 34 Å, y llega a 115,7 Å en 7T9I: la
cadena declarada está al otro lado del complejo.

El respaldo de `vina_service.py:963` —que empareja hotspots por nombre y número
ignorando la cadena— es lo que mantuvo esto invisible. Peor: `list_targets`
resuelve las coordenadas de los hotspots filtrando por `t.chain`, así que en
estos casos buscaba `TYR66` en una cadena donde ese residuo es otro. El doc 71 lo
llamó «un segundo defecto, de procedencia»; con los números delante es el mismo
defecto visto desde otra capa.

---

## 2. El triaje: qué trabajo hace falta para cada uno

`scripts/triaje_receptores_al_vacio.py` cruza tres evidencias —el ligando
co-cristalizado, el volumen en la caja y los hotspots ya anotados— y separa
cuatro situaciones. **Ninguna clase dice «irrecuperable»:** ese veredicto exige
mirar la estructura y no le corresponde a un script.

| clase | n | qué hace falta |
|---|---:|---|
| `RESCATE_MECANICO` | 7 | cambiar la cadena declarada. Aplicado hoy |
| `RESCATE_MULTICADENA` | 3 | el receptor multicadena en el contrato de preparación |
| `REVISAR_LA_CAJA` | 14 | la sospecha recae sobre el grid, no sobre la cadena |
| `CONTRADICCION` | 1 | dos anotaciones independientes se contradicen |

**Por qué `REVISAR_LA_CAJA` es la clase más poblada y por qué no se tocó.** En
esos 14 no hay ligando co-cristalizado dentro de la caja (o el más cercano está
lejos del centro: 15,9 Å en 7ZYJ). Cambiar la cadena ahí produciría un objetivo
que *parece* arreglado sobre un centro que quizá esté mal puesto. Tres de ellos
—8J47, 9RAW, 9RAX— son anillos de diez subunidades con la caja sobre el eje de
simetría, y ninguna cadena llega al 15% del sitio: no es una laguna de la
medida, es la forma de la estructura.

---

## 3. Lo aplicado: 7 rescates mecánicos

**La regla, y en qué se aparta de la de `c8a50da`:**

| | umbral de volumen | evidencia |
|---|---|---|
| `c8a50da` (30 casos) | una cadena ≥90% | ligando co-cristalizado |
| esta tanda (7 casos) | una cadena ≥80% | ligando **Y** la mayoría de los hotspots |

Se baja el umbral porque se añade una tercera evidencia independiente. No es el
mismo criterio más flojo: es otro criterio, con más apoyo. Los siete tienen
entre 10 y 14 de sus 15 hotspots en la cadena sugerida.

```
3GPJ  A → H    'H' concentra el 83% del sitio, 11/15 hotspots      (la anterior a 20,2 Å)
3HYE  A → H    'H' concentra el 89% del sitio, 14/15 hotspots      (la anterior a 20,3 Å)
5CZ6  A → H    'H' concentra el 81% del sitio, 11/15 hotspots      (la anterior a 20,3 Å)
5I3T  C → A    'A' concentra el 82% del sitio, 10/12 hotspots      (la anterior a 34,5 Å)
5Z2R  F → A    'A' concentra el 81% del sitio, 13/15 hotspots      (la anterior a 60,2 Å)
6HW5  A → H    'H' concentra el 83% del sitio, 12/15 hotspots      (la anterior a 19,3 Å)
6HW7  A → H    'H' concentra el 89% del sitio, 12/15 hotspots      (la anterior a 19,9 Å)
```

Verificado volviendo a correr el repaso: **de 25 receptores acoplando contra el
vacío a 18.** Cada cambio queda con su valor anterior y su evidencia en
`docs/auditorias/cadena_receptor_decisiones_tanda2.json`; volver atrás es leer
ese archivo.

---

## 4. Lo que ahora se declara al usuario

Hasta hoy el catálogo guardaba `chain` —la cadena que se **prepara**— y nada
más. Ahora guarda también, medido sobre el PDB del RCSB, **qué cadenas forman el
sitio y con qué evidencia se sabe**:

```json
"site_chains":      ["H", "I"],
"site_chain_atoms": {"H": 49, "I": 5},
"site_evidence":    "cocrystal_ligand",
"site_ligand":      "SY2"
```

**El hecho, no la política.** El modo de preparación se *deriva* de
`site_chains`; no se anota. Una política congelada en la tabla obligaría a
reanotar 387 filas el día que cambie el umbral, y nadie sabría con qué criterio
se puso cada una.

Sobre los 387:

| | n |
|---|---:|
| sitio de una sola cadena | 286 |
| sitio de dos cadenas | 86 |
| de tres | 12 |
| de diez (anillos, caja sobre el eje) | 3 |
| **evidencia: ligando co-cristalizado** | **273** |
| **evidencia: sólo volumen en la caja** | **114** |

> **No confundir estos 101 con los 101 del doc 71.** Aquel contaba los objetivos
> que pierden ≥20% de los átomos de la **caja** al conservar una sola cadena;
> éste cuenta los sitios formados por más de una cadena. Hoy son 99 y 101, con
> 91 en común. Coinciden casi en tamaño y no son la misma población: medir
> volumen perdido no es medir quién forma el sitio.

### Por qué `site_evidence` llega hasta la tarjeta

Son dos afirmaciones de fuerza muy distinta. Las cadenas que contactan un
ligando cristalizado a ≤4,5 Å es lo que miraría un cristalógrafo. Contar átomos
dentro de la caja no distingue el bolsillo de la vecindad. Presentar las dos
igual sería afirmar de más en 114 casos, y el investigador tiene derecho a saber
cuál de las dos lo respalda. La tarjeta lo dice con todas sus letras: **«Sin
ligando co-cristalizado»**.

### Cómo se nombra en la interfaz

Se nombran las cadenas, no se cuentan: `Cadena A`, `Interfaz B·A`, y a partir de
cuatro, `Interfaz de 10 cadenas`. Un biólogo escribe «interfaz A/B»; no existe
una palabra genérica para «varias». Y la `R` de 7E2Y no significa «receptor»: es
el identificador que puso quien depositó la estructura, igual que la `A` de los
otros 325.

El chip se tiñe de ámbar sólo cuando el sitio lo forman varias cadenas y la
preparación conserva una: ahí es donde el número que el usuario va a leer sale
mal. La evidencia débil se dice en el texto, no en el color — son dos avisos
distintos y no deben compartir canal.

Un receptor sin anotación —subido por el usuario, o anterior al campo— dice
**«Sitio sin medir»**, nunca «Cadena A». Suponer monómero es justo el error que
este documento corrige.

### De paso: 367 resoluciones

La tarjeta mostraba «Resolución: N/A» en el 95% de los casos. Los 387 archivos
locales traen su resolución en el `REMARK 2`: no faltaba el dato, se perdía al
ingerir. Recuperado en el mismo recorrido de archivos, sin red.

---

## 5. La deuda que queda, acotada por una prueba

`backend/tests/test_catalogo_sitio_de_union.py` fija el invariante del doc 71:
**la cadena que se prepara tiene que formar el sitio.** Hoy hay **21 receptores**
donde no es así —los 18 que siguen acoplando contra el vacío, más 6KE5, 6MVV y
8F6U, donde la declarada aporta algo pero no llega al 15% del sitio—.

No se ocultan tras un umbral holgado: se listan por nombre. La prueba falla si
aparece uno nuevo, **y también si uno se arregla y nadie actualiza la lista**. Un
recuento que sólo puede bajar es un cierre.

---

## 6. Lo que este trabajo NO alcanza todavía

**Un catálogo corregido no llega a una máquina instalada.**
`_auto_seed_curated_targets_if_empty` (`backend/api/main.py:551`) siembra desde
`curated_targets.json` **sólo si la base tiene 10 targets o menos**, y dentro del
bucle salta cualquier `pdb_id` que ya exista. Es decir:

- las 50 correcciones de cadena de `c8a50da` **no han llegado** a ninguna
  instalación anterior, incluida la VM donde se hizo la primera evaluación;
- los 7 rescates de hoy y los cuatro campos del sitio, tampoco.

Las columnas nuevas sí aparecen —el chequeo de esquema hace `ALTER TABLE ADD
COLUMN` al arrancar— pero llegan vacías, y la interfaz dirá «Sitio sin medir»
para los 387.

**Hace falta una resincronización del catálogo**, sellada por versión, que
actualice los campos que el catálogo posee sin tocar receptores privados, de
comunidad ni variantes de preparación. Es la diferencia entre arreglado en el
repositorio y arreglado en el producto.

> **Hecha.** Ver §21.

---

## 7. Orden que sigue

1. **La resincronización del catálogo.** Sin ella nada de esto llega al usuario.
2. **El radio derivado de la caja**, con el invariante como prueba: ningún átomo
   dentro de la caja +4 Å puede perderse al recortar. Mide 12 Å fijo perdía el
   42% de esos átomos en 1TW7.
3. **Los 14 de `REVISAR_LA_CAJA`**, que es una revisión de grid y no de cadena.
4. **Los 3 de `RESCATE_MULTICADENA`**, cuando el receptor multicadena entre en el
   contrato, con el corrigendum del doc 71 §2.3.
5. **4YNQ**, el único con dos anotaciones peleadas: sólo tiene 3 hotspots
   anotados y ninguna herramienta puede arbitrar con eso.

---

## 8. Segunda tanda: la procedencia de los hotspots, y dos bajas

### 8.1 El hallazgo que cambia la premisa

Al ir a marcar los hotspots re-anotados «como nuestros» para distinguirlos de
los «oficiales del PDB», resultó que **no hay hotspots oficiales del PDB en este
catálogo**. `backend/scripts/recure_targets.py` corrió `discover_pocket_from_pdb`
sobre los 387 y minó, para cada uno, «los 15 residuos más cercanos al ligando
holo» detectado automáticamente. De ahí que la mediana del catálogo sea
exactamente 15 hotspots.

Eso obliga a marcar en las dos direcciones:

- marcar sólo los re-derivados sugeriría que los otros 376 son oficiales, y no
  lo son;
- no marcar nada dejaría creer que todos tienen el mismo respaldo, y tampoco.

Por eso `hotspots_source` se escribe en **los 385**, y el tooltip de cada
tarjeta empieza diciendo que ningún hotspot procede del RCSB. El chip visible se
reserva para los nueve que cambiamos, que es donde la anotación difiere de la
que el receptor traía.

### 8.2 Los 15 no eran un problema: eran tres

| situación | n | qué se hizo |
|---|---:|---|
| la caja está sobre un ligando que sí se une | **9** | re-anotados desde ese ligando |
| la caja no está sobre ningún ligando (6,2–15,9 Å) | 5 | **no se tocan**: el defecto es del grid |
| el ligando apenas toca la proteína | 1 | **no se toca**: no sirve de testigo |

**Por qué re-anotar los 9 es lo correcto y no una licencia.** La caja es el
contrato —es lo que Vina muestrea—, así que los hotspots tienen que describir el
sitio de la caja. En 2VE3 los hotspots heredados describían el sitio del **hemo**
mientras la caja está centrada en el **ácido retinoico**: dos bolsillos distintos
de la misma proteína, y el dossier nombraba el que no se estaba sondeando.

**Por qué NO los otros 6.** En 4JZD, 6MEO, 6VU4, 7ZYJ y 8WGR el heteroátomo más
cercano al centro está entre 6,2 y 15,9 Å: re-anotar ahí sería *fabricar*
hotspots para un sitio que nadie eligió. Y 6SXG merece mención aparte: su ligando
es OHT —4-hidroxitamoxifeno, un fármaco de verdad— pero sólo toca **dos**
residuos. Un ligando que apenas roza la proteína está en la superficie o
parcialmente ocupado; el nombre invita a creer lo contrario.

### 8.3 Dos bajas del catálogo

```
2ONV   péptido GGVVIA de fibra amiloide     36 átomos,  6 residuos, caja de 22 Å
5TXJ   péptido IFAEDV de amiloide-beta      98 átomos, 12 residuos, caja de 22 Å
```

No son receptores: son cristales de hexapéptido de estudios de cremallera
estérica. La mediana del catálogo son 669 átomos dentro de la caja. **387 → 385.**

Su fila completa queda en `docs/auditorias/receptores_retirados.json`: retirar
del catálogo no es borrar la evidencia, y reponer uno es copiar `fila_completa`
de vuelta.

### 8.4 Estado

| | expediente |
|---|---|
| antes de esta sesión | — |
| tras la primera tanda | 328 de 387 |
| tras normalizar hotspots sin cadena | 330 de 387 |
| **tras la segunda tanda** | **339 de 385** |

Los 46 que quedan: 28 de D2 (la caja no cubre los hotspots), 21 de D1 (la cadena
no forma el sitio), 6 de D3 y 1 de D4 —5VB8, el único receptor real del catálogo
sin ningún hotspot—. Los grupos se solapan.

**Lo que queda no es más de lo mismo.** D1 depende del receptor multicadena, y
D2 exige decidir, caso por caso, si sobra caja o falta anotación: 1TW7 enseñó que
la respuesta puede ser cualquiera de las dos.

---

## 9. Tercera tanda: D2 estaba mal calibrado, y lo estaba a mi favor

### 9.1 El criterio viejo contaba geometría, no defectos

D2 marcaba 28 receptores contando qué fracción de los **átomos** de hotspot caía
fuera del cubo. Al mirar esos 28 de cerca, **siete tenían su ligando
co-cristalizado a 0,0 Å del centro de la caja**. Un residuo del borde del
bolsillo apunta su cadena lateral hacia fuera por construcción; eso no es un
defecto del grid.

### 9.2 La pregunta decisiva, medida

Cuando hay ligando cristalizado hay un requisito físico que no admite
interpretación: **el espacio de poses tiene que contener al ligando que ya se
sabe que se une.**

```
objetivos con ligando en la caja        273
  el ligando cabe ENTERO                272
  el ligando SE SALE                      1   → 6MEO
margen entre el ligando y la pared:  mín 2,8 Å   p10 4,2 Å   mediana 8,1 Å
```

Las cajas del catálogo son buenas. Y el criterio nuevo **atrapa un fallo que el
viejo no veía**: 6MEO, cuya caja no contiene su propio ligando. No es sólo más
laxo — es más correcto en las dos direcciones.

Para los que no tienen ligando queda el centroide de los hotspots, en semilados
de caja para que la medida no dependa del tamaño: mediana 0,18, p95 0,43, y un
hueco limpio entre 0,50 y 0,63. El umbral se pone en 0,6 y deja siete.

**Lo digo explícitamente porque aflojé un control mío y el resultado mejora el
número:** el criterio anterior producía 20 falsos positivos y ocultaba un
positivo verdadero.

### 9.3 Los ocho que quedan en D2, abiertos uno a uno

| | qué se ve en el centro de la caja | lectura |
|---|---|---|
| **1TW7** | `B:THR26` y `A:THR26` a 2,0 Å, con ASN25 y GLY27 | tríada catalítica del dímero. **Los hotspots (16–25 Å) son los equivocados** |
| **5TUN** | `VAL164`, `SER29`, `LEU165` | son literalmente sus tres primeros hotspots. Caja y anotación coinciden; la cola de residuos lejanos arrastra el centroide |
| **1C3P** | `GLY294`, `GLY293`, `GLN254` | `GLY294` es su hotspot más cercano, y HIS131/MET130 están a 5 Å: el sitio de la HDAC. Misma cola |
| **6PSD** | `K:VAL92`, `L:VAL443`, `L:PHE447` | interfaz K/L de un complejo proteína-proteína; los hotspots 90–94 son contiguos a VAL92. Misma cola |
| **5T4X** | `THR131`, `GLN78`, `LEU76` | PDE6δ apo. Sus hotspots (TRP90, MET20, LEU38, ILE109) parecen el bolsillo prenilo real: **aquí la duda recae sobre la caja**, no sobre la anotación |
| **4JZD, 7ZYJ** | el ligando está a 7,5 y 15,9 Å del centro | ya marcados en §8.2: la caja no está sobre el ligando |
| **6MEO** | el ligando A2G no cabe en la caja | el único fallo del test físico |

**El patrón de los apo.** En 5TUN, 1C3P y 6PSD los hotspots cercanos coinciden
con el centro de la caja y lo que dispara D2 es una cola de residuos a 14–18 Å.
Tiene explicación: `discover_pocket_from_pdb` ancla los 15 hotspots en el ligando
holo, y en una estructura **apo** no hay ligando que los ancle. La anotación no
está equivocada, está suelta.

### 9.4 Estado

```
primera tanda                     328 de 387
normalizar hotspots sin cadena    330 de 387
segunda tanda                     339 de 385
recalibrar D2                     354 de 385
```

Los 31 que quedan: **21 de D1** (dependen del receptor multicadena), **8 de D2**,
**6 de D3** y **1 de D4** —5VB8, el único receptor real sin ningún hotspot—. Los
grupos se solapan.

---

## 10. Cuarta tanda: dos de los tres «sospechosos de caja» eran mi herramienta

Al abrir los ocho de D2, tres apuntaban a que la caja estaba mal. Dos no lo
estaban: el defecto era del selector de ligando.

### 10.1 A2G no es un ligando, es azúcar

**6MEO** era el único fallo del test físico: su ligando no cabía en la caja. Ese
«ligando» es `A2G` —N-acetilgalactosamina, 14 átomos, tocando 7 residuos—, es
decir, **la glicosilación**. `NO_SON_LIGANDO` ya excluía NAG, MAN, GAL y FUC,
pero no los dos anómeros de la GalNAc. Añadidos A2G, NGA y ocho azúcares más,
6MEO deja de tener ligando falso y el fallo desaparece.

### 10.2 Elegir la copia del ligando: por qué «la que más toca» habría sido peor

**4JZD** tenía dos copias de `1NJ`: la que el selector elegía tocaba **un**
residuo, y la de al lado tocaba **24**. Mismo patrón en 6SXG (2 frente a 6). El
selector tomaba la más cercana al centro sin mirar si estaba unida a algo.

La corrección obvia —quedarse con la que más residuos toca— es **falsa**, y vale
la pena dejar escrito por qué:

| | el selector elegía | la más contactada |
|---|---|---|
| 2NNJ | `225` (15 residuos) | `HEM` (31) |
| 2VE3 | `REA` (19) | `HEM` (33) |
| 4EJJ | `NCT` (11) | `HEM` (29) |
| 4NY4 | `2QH` (16) | `HEM` (30) |

En un citocromo P450 el **hemo es un cofactor** y toca el doble de residuos que
el fármaco. «El que más toca» habría anclado cuatro sitios en el cofactor.

Y aun limitándolo a copias del *mismo* compuesto sigue siendo falso: en **4QA0**
—HDAC8 con SAHA— las dos copias están unidas de verdad, una por cadena, y esa
regla movía el sitio a la cadena contraria a la que declaran la caja **y** los
doce hotspots.

**La regla que queda** es más estrecha: entre copias del mismo compuesto se
descartan las que tocan menos de cinco residuos —no están en ningún bolsillo— y
entre las que quedan manda la cercanía a la caja, que es la intención de quien
curó el objetivo.

### 10.3 Estado

```
primera tanda                     328 de 387
normalizar hotspots sin cadena    330 de 387
segunda tanda                     339 de 385
recalibrar D2                     354 de 385
arreglar el selector de ligando   355 de 385
```

Quedan **30**: 21 de D1, 7 de D2, 5 de D3 y 1 de D4.

**Y aquí se acaba lo que se puede arreglar sin decidir.** Los 30 restantes
necesitan una de estas tres cosas, y las tres son decisiones del propietario:

1. **El receptor multicadena** (21 de D1). El sitio *es* una interfaz: no hay
   una cadena única que declarar, y forzar una sería volver al defecto del
   doc 71.
2. **Cómo anotar hotspots sin ligando** (1TW7, 5TUN, 1C3P, 6PSD, 5VB8). En
   estructuras apo no hay ligando que ancle la anotación. En 1TW7 los hotspots
   están sencillamente en otro sitio; en 5TUN, 1C3P y 6PSD los cercanos aciertan
   y sobra una cola de residuos a 14–18 Å.
3. **Recentrar cajas** (4JZD, 7ZYJ, 8WGR, 5T4X). Cambia el sitio que se acopla,
   así que cambia los números y exige el corrigendum del doc 71 §2.3.

---

## 11. Recentrar cajas: el estándar ya lo fijaba el propio catálogo

No hizo falta inventar criterio. Medido sobre los 278 objetivos con ligando en su
caja, la distancia entre el centro de la caja y el centro del ligando es:

```
mediana 0,0 Å      p90 0,0 Å      p95 4,8 Å
```

**Nueve de cada diez cajas ya están centradas exactamente sobre el ligando
co-cristalizado.** El trabajo era aplicar esa regla a las que se quedaron fuera.

### 11.1 Por qué «el ligando está lejos» no basta

Veinte objetivos tienen su ligando a más de 3 Å del centro, seis de ellos a más
de 19 Å —**5YUA a 46,7 Å**—. Recentrarlos todos habría sido un error: en esos
seis **los hotspots caen sobre la caja**, a 0,18–0,50 semilados. La caja apunta a
un sitio que la anotación reconoce y el ligando lejano está en otro bolsillo de la
misma proteína. Moverla habría cambiado el objetivo científico del receptor sin
que nadie lo pidiera.

### 11.2 La regla: dos testigos contra uno

Se recentra cuando el ligando **y** los hotspots coinciden entre sí y discrepan de
la caja: ligando unido de verdad (≥5 residuos), a más de 3 Å del centro, y el
centroide de los hotspots al menos 1,5 Å más cerca de ese ligando que de la caja.

El margen no es decorativo: sin él entraba 6SX7 con los hotspots a 5,9 Å de la
caja y 5,3 Å del ligando. Seis décimas no son un testigo.

**El desempate entre copias simétricas.** En 7ZYJ y 8WGR el ligando aparece dos
veces, ambas unidas y ambas a la *misma* distancia del centro. `elegir_ligando` no
puede desempatarlas —por diseño, porque allí los hotspots no son testigo—. Aquí sí
lo son y ya se exige que lo sean. En 8WGR una copia está a 0,8 Å del centroide de
hotspots y la otra a 14,3 Å: no era un empate, es que la caja miraba al hueco
entre las dos.

### 11.3 Las once

```
1VKG CRI  4,7 Å      4JV6 18F  4,4 Å      6SXC OHT  4,3 Å      7ZYJ KFC 15,9 Å
1W22 NHB  5,0 Å      4JV8 1M1  4,6 Å      6SXG OHT  4,5 Å      8WGR DSM  6,9 Å
4JZD 1NJ  7,5 Å      4QA0 SHH  5,2 Å      7JVU SHH  4,8 Å
```

En las once, los hotspots quedan entre 0,8 y 4,7 Å del ligando y estaban entre 3,7
y 16,1 Å de la caja vieja. **Recentrar cambia el sitio que se acopla**, así que
cambia los números de cualquier resultado anterior sobre estos receptores: exige
el corrigendum del doc 71 §2.3.

### 11.4 Estado

```
primera tanda                     328 de 387
normalizar hotspots sin cadena    330 de 387
segunda tanda                     339 de 385
recalibrar D2                     354 de 385
arreglar el selector de ligando   355 de 385
recentrar once cajas              358 de 385
```

Quedan **27**, y ya no se solapan por casualidad:

| grupo | n | quiénes |
|---|---:|---|
| D1 — la cadena no forma el sitio | 21 | necesitan `protein_surgery` multicadena |
| D2 — caja y hotspots no coinciden | 5 | 1TW7, 1C3P, 5T4X, 5TUN, 6PSD: **los cinco son apo** |
| D3 | 1 | 6VU4 |
| D4 — sin hotspots | 1 | 5VB8 |

Los siete de D2/D3/D4 son el mismo problema: **estructuras sin ligando que ancle
la anotación**. Es el pendiente que el doc 35 dejó abierto en 2026-08-02 sobre
5TUN, con nombre y apellido.

---

## 12. Los apo: el detector confirmó la anotación y acusó a la caja

`docs/35_GRID_APO_5TUN_PENDIENTE.md` dejó esto abierto el 2026-08-02 sobre 5TUN.
Se cierra aquí, y el resultado no fue el esperado.

### 12.1 MolPocket no da un resultado uniforme, y tratarlo como si lo diera sería el error

```
1C3P   cavidad rango  1 de 18, druggability 0,79   conserva 15 de 15 hotspots
5TUN   cavidad rango  1 de 15, druggability 0,81   conserva 15 de 15 hotspots
1TW7   cavidad rango  1 de 19, druggability 0,10   conserva  0 de 10
6PSD   cavidad rango  1 de 59, druggability 0,30   conserva  0 de 15
5T4X   cavidad rango  8 de  8, druggability 0,25   conserva  2 de 15
5VB8   la cavidad más cercana está a 20,3 Å del centro — el detector no reconoce el sitio
```

Tres situaciones, cada una pide otra cosa:

- **El detector CONFIRMA la anotación** (1C3P, 5TUN): 15 de 15, con cavidad bien
  puntuada. Entonces los hotspots no son el problema, **la caja lo es**, y hay
  dos testigos independientes contra ella. Se recentra la caja sobre la cavidad.
  Para **5TUN esto confirma por otra vía lo que el doc 35 midió hace un año**: el
  grid estaba ~7 Å fuera.
- **El detector CONTRADICE con confianza**: se re-anota. No ocurrió en ninguno.
- **El detector NO SABE** (1TW7, 6PSD, 5T4X): druggability de 0,10 a 0,30, o la
  peor cavidad de las ocho que encontró. **No se toca.** Sustituir una anotación
  posiblemente buena por una estimación mala no es mejorar: es cambiar un
  problema conocido por uno oculto.

En 1TW7 además sabemos por química que la caja está bien —su centro cae sobre la
tríada catalítica del dímero—, así que una cavidad con druggability 0,10 a 12 Å
de ahí no es candidata a nada.

### 12.2 La etiqueta, en las dos superficies

Los chips que declaran el sitio —qué cadenas lo forman, si hay cristal que lo
respalde, de dónde salen los hotspots— viven ahora en un **componente
compartido**, `ChipsDelSitio`, que usan el catálogo de receptores y la pestaña de
Evaluación. Si una superficie dijera «Interfaz B·A» y la otra callara, el
investigador no sabría cuál creer, y la que calla es la que engaña.

Repetirlo en Evaluación no es redundancia: quien abre un caso guardado, o vuelve
tras cambiar de pestaña, no pasa por el catálogo y se llevaría el número sin la
condición.

### 12.3 Estado

```
...                               358 de 385
apo: 1C3P y 5TUN recentrados      360 de 385
```

Quedan **25**: 21 de D1, y cuatro que el detector no supo resolver —1TW7, 5T4X,
6PSD y 6VU4— más 5VB8, sin hotspots.

---

## 13. D1: el receptor multicadena, conectado — 380 de 385

`preparer_multichain.py` existía desde `3f0ef0d` y **nadie lo invocaba**. Ahora sí.

### 13.1 El modo se deriva, no se declara

`prepare_target` recibe `site_chains` del catálogo. Con dos o más cadenas conserva
todas y **recorta al sitio**; con una, el comportamiento histórico queda intacto
byte a byte. No hay interruptor que ponga nadie: una política congelada en la
tabla obligaría a reanotar 385 filas el día que cambie el umbral.

El recorte no es opcional en ese camino: conservar los oligómeros enteros
reintroduciría los receptores de 5 y 10 MB que la v1.6 eliminó.

### 13.2 El radio, por fin derivado

```
r = (√3/2)·lado + 4 Å
```

**No es un parámetro: es una consecuencia.** El receptor tiene que conservar todo
residuo que un ligando pueda tocar desde cualquier punto de la caja. Los 12 Å
fijos de la primera versión perdían **389 de los 926 átomos alcanzables de 1TW7 —
el 42%**: el mismo defecto que el módulo existe para reparar, entrando por otra
puerta. El invariante es ahora una prueba, no una promesa.

Y el temor de la v1.6 no reaparece: sobre 6HW5 (49.296 átomos) el recorte deja
menos del 15%.

### 13.3 Medido sobre 1TW7, el caso de libro del doc 71

```
                        átomos DENTRO de la caja de docking
modo actual (cadena A)        A: 301                         301
multicadena recortado         A: 301   B: 299                600
```

**El bolsillo se dobla.** El sitio activo de la proteasa del VIH-1 *está* en la
interfaz del dímero; hasta hoy se acoplaba contra la mitad.

### 13.4 Los 21 declaraban `"A"`, que es el default del ORM

Ninguno de los 21 tenía un solo hotspot nombrando su cadena declarada, y la
distancia mediana de esa cadena al centro de la caja era 34 Å —115,7 Å en 7T9I—.
No era una anotación equivocada: **era una anotación que nunca se hizo.**

Con el docking ya resuelto por `site_chains`, `chain` queda como etiqueta: la usan
el visor, el dossier y el selector. Ponerla igual a la cadena que más aporta no
elige nada, describe lo que ya está medido. **No mueve ningún número**: arregla lo
que el usuario lee.

### 13.5 Un defecto encontrado de paso, y no es pequeño

`utils/structural.py:get_residue_coordinates` parseaba el prefijo de cadena con
las dos mitades **intercambiadas**: `"A:ARG76".partition(":")` deja `"A"` a la
izquierda, y el código tomaba la izquierda como nombre de residuo y la derecha
como cadena. Como el bucle construye `res_id = "ARG76"`, la clave registrada
(`"A"`) no coincidía nunca.

Comprobado sobre 1AJ6: `["A:ARG76"]` → `{}`, `["ARG76"]` → coordenadas.

Es decir: **`GET /targets` no ha enviado nunca las coordenadas de los hotspots del
catálogo curado**, porque los 385 las llevan con prefijo. El fallo era silencioso
—no lanzaba nada, sólo omitía— y el visor se las arreglaba recalculándolas en el
navegador. Nadie lo notó porque quien las necesitaba se las apañaba solo.

### 13.6 Estado

```
...                               360 de 385
D1 con preparación multicadena    380 de 385
```

**Quedan cinco**, y son exactamente aquellos en los que decidí no actuar:

| | por qué sigue abierto |
|---|---|
| 1TW7 | la caja es correcta (tríada catalítica); los hotspots están en el codo, y MolPocket da druggability 0,10 |
| 5T4X | PDE6δ apo; la cavidad más cercana es la 8ª de 8, druggability 0,25 |
| 6PSD | interfaz proteína-proteína; druggability 0,30, no es un bolsillo de fármaco |
| 6VU4 | el ligando MEA no ancla la anotación |
| 5VB8 | canal de sodio sin hotspots; el detector no reconoce el sitio a 20,3 Å |

Los cinco necesitan que un humano mire la estructura. No hay herramienta que los
cierre, y forzarlos sería cambiar un problema conocido por uno oculto.

---

## 14. Subir un receptor: los dos modos, medidos

### 14.1 El modo automático acierta en el 100%

Barrido completo sobre las 385 estructuras locales:

```
descubrimiento automático OK : 385 de 385   (100%)
  de ellas por la rama apo (MolPocket)      :  90
anotación del sitio OK       : 385 de 385   (100%)
fallos                       :   0
```

El umbral que pedía el contrato era 95%. **Noventa de las 385 no tienen ligando
co-cristalizado**: sin la rama apo de MolPocket, el modo automático caería al 77%
y ninguna prueba de la ruta holo se enteraría. `test_subida_de_receptores.py` lo
fija con una muestra sembrada de 24 estructuras —35 s— y comprueba aparte que la
rama apo sigue viva.

### 14.2 El modo manual ya no deja al usuario peor que al catálogo

Un receptor subido nunca recibía `site_chains`. Quien subiera la proteasa del VIH
con su propia caja tenía **exactamente** el modo de fallo C del doc 71 que
acabábamos de reparar en el catálogo.

El cálculo del sitio vive ahora en `backend/services/targets/sitio_de_union.py`,
una sola implementación que usan los tres caminos: el catálogo curado, la ingesta
automática y la subida manual. Verificado antes de cambiar nada: **reproduce los
cuatro campos del sitio en los 385 objetivos con cero discrepancias**.

---

## 15. Doc 71 §3, defecto C1: la conclusión injustificada

El informe explica que una afinidad de Vina no es energía libre, y dos párrafos
después afirmaba:

> «Los niveles de binding calculados están en el rango micromolar alto.
> Probablemente insuficiente para actividad farmacológica in vivo.»

Son **dos saltos que su propia premisa prohíbe**:

1. de un score de Vina a una **constante de disociación** («micromolar»). La
   función de puntuación está entrenada para *ordenar* candidatos, no para
   predecir una Kd: convertir −5,8 kcal/mol en una concentración es leer una
   regla graduada en unidades que no tiene;
2. de esa constante a **actividad in vivo**, que además atraviesa permeabilidad,
   metabolismo, unión a proteínas plasmáticas y dosis.

Se corrige **borrando** la inferencia, no matizándola: un «probablemente» no
arregla una afirmación cuya premisa el documento ya negó.

**Pero borrar no puede costar la señal.** Lo que sí se puede decir es dónde cae el
número en la escala de Vina, que es la única en la que significa algo:

> «Afinidad débil en la escala de Vina (-5,2 kcal/mol): por encima de -6 el score
> deja de discriminar bien entre unir y no unir, así que este resultado sirve para
> descartar, no para priorizar. El score de Vina ordena candidatos; no es energía
> libre ni se traduce a una concentración.»

Está en un solo sitio —`utils/scientific.py`— y hay prueba parametrizada sobre
cinco afinidades que falla si vuelve a aparecer «micromolar», «in vivo», «IC50»,
«Kd» o «Ki» en los avisos.

**Un detalle que casi se cuela.** La primera redacción usaba el signo menos
tipográfico (U+2212). Ese texto va al PDF, y el doc 71 (defecto D2) ya registra
glifos que se extraen como cuadrados: es la misma familia de problema, y
perjudica búsqueda y copiado. Hay prueba que lo impide.

---

## 16. Doc 71 §3, Grupo A: ocho síntomas, un contrato de datos roto

El doc 71 sospechaba que los ocho defectos de «serialización y evidencia ML» eran
uno solo: *«ocho síntomas apuntando al mismo sitio suelen ser un contrato de
datos roto, no ocho bugs»*. Lo eran, y el sitio es **dos lectores sobre dos
fuentes distintas**: el frontend leía los scores directamente del ORM, y el
dossier construía su sección de evidencia desde `build_evidence_summary`, que no
los tenía. Cada superficie decía la verdad que veía, y las dos no coincidían.

### A3 y A7 — el mismo renglón

```ts
sub: realDot[s.id]?.sub ?? (s.post_hoc ? "cálculo opcional" : "sin salida serializada")
```

`sub` sólo se sobrescribía para MM-GBSA. Cualquier etapa con valor **real** —Vina
con sus nueve poses, XGBoost con su score— se mostraba como
`-7.0 kcal/mol · sin salida serializada`: **dos afirmaciones contradictorias en la
misma tarjeta**, con la segunda desmintiendo a la primera.

De ahí salían los dos defectos que el informe listó por separado, y el desacuerdo
con el dossier, que decía «9 poses serializadas» y daba su hash. **El dossier
tenía razón.** La regla está ahora en `lib/procedenciaDeSenales.ts`, con su
prueba: «sin salida serializada» sólo puede decirse cuando no hay valor.

Y no se recurre al `sub` de `pipelineDefinitions` («v1.2.7», «500 trees») como
respaldo: son literales de la definición de familia, y presentarlos como la
procedencia de esta corrida sería la misma invención que el fix UI-8 ya quitó de
MM-GBSA, en letra pequeña.

### A6 — una colisión de nombres, no un dato que falte

La matriz decía **«motor no informado · universal»** en un documento que declara
Vina 1.2.7 dos secciones más abajo. Causa: la dimensión «Dominio del modelo» leía
`engine_used`, que es el **motor hardware del router (gpu/cpu)** —su propia
columna lo dice: *«None en pipeline eval»*, porque ese camino no usa el router—.

El motor de docking vive en `docking_protocol.engine` y su versión en
`vina_version`. Ahora el motor se nombra en la señal de docking, que es de donde
sale, y la dimensión del modelo habla del modelo. **Confundir las dos identidades
era lo que hacía que el documento se contradijera consigo mismo.**

### A1 y A4 — lo que el resumen no serializaba

`build_evidence_summary` gana un bloque `ml_signals` con las salidas de XGBoost
—incluidos SHAP y la probabilidad del clasificador—, CL-GNN, GNN geométrica,
cuántica y MM-GBSA. **`None` explícito donde la corrida no produjo nada**, nunca
cero ni el 0,5 neutro de un modelo silenciado: eso convertiría una ausencia en
una predicción.

Y A4: hay **dos** XGBoost en el producto —el selector de poses (`XGBRanker v0.6`)
y el de rescoring— y compartían nombre en el mismo documento. El bloque declara
cuál es cuál.

### A2 y A5 — el peso no es una contribución

El stacking por familia reparte pesos **antes** de correr: en proteasa CL-GNN
lleva 0,60 porque así lo midió el diagnóstico de familia. Si esa etapa después no
serializa nada, el documento acaba atribuyendo dominancia a un modelo que no dijo
una palabra: *«CL-GNN-dominante»*, peso 0,00, salida «no reportada».

No se corrige bajando el peso —es un dato del protocolo, no de la corrida— sino
**declarando la contradicción donde se lee la conclusión**:

> «El protocolo de familia asigna peso en el stacking a CL-GNN, pero esas etapas
> no serializaron salida en esta corrida. El peso describe lo que el protocolo
> esperaba, no lo que aportó: no debe leerse como que ese modelo dominó el
> resultado.»

### Lo que queda del Grupo A

**A8** se cierra en §17, con el Grupo B.

backend 1353 pruebas, frontend 720.

---

## 17. Doc 71 §3, Grupo B y A8

### B1 y B2 — `except Exception: pass` alrededor de la única escritura

El doc 71 sospechaba que eran «la misma causa vista desde dos sitios». Lo son, y
la causa estaba escrita literalmente:

```python
        except Exception:
            pass
```

en `pro_features.py`, envolviendo el único punto donde el resultado de
selectividad llega a la base. Si el commit fallaba —y con SQLite, escribir desde
una segunda sesión mientras la respuesta está en *streaming* es justo cuando
falla— el flujo seguía emitiendo `done` con los números, la interfaz los pintaba,
y la base no se enteraba nunca.

De ahí los dos síntomas:

- **B1**: el dossier lee `selectivity_ran = False` y declara «la corrida no
  registró un panel de anti-targets». Desde su punto de vista es *literalmente
  cierto*.
- **B2**: el resultado sólo vive en el estado del componente, así que desaparece
  al cambiar de pestaña.

Y en el frontend, el mismo tragado: `saveSelectivityResults(...).catch(() => {})`,
dos veces.

**Corrección de este documento.** La primera versión de §17 se quedó en añadir
un aviso de «resultado sin guardar». Eso informa del problema; no lo resuelve.
Poner un cartel donde hace falta que el dato no se pierda es cambiar una
amputación por una curita. Lo que sigue es el arreglo de verdad, en §17 bis.

### A8 — el dossier tenía los datos y no los pintaba

`PreflightDeclarado` guarda **tres** listas: `blockers`, `warnings` y
`not_evaluated`. El dossier renderizaba las dos primeras. De ahí que la interfaz
mostrara «dos advertencias y tres controles sin evaluar» y el documento hablara
sólo de las advertencias.

**Un control que no se evaluó no es un control que pasó**, y omitirlo lo
convierte en lo segundo por defecto. Es la misma distinción que este producto ya
sostiene en la validez física de poses, donde `not_evaluated` nunca se mezcla con
`passed`.

### Estado del doc 71 §3

| grupo | estado |
|---|---|
| C1 (crítico) | **cerrado** (§15) |
| A1, A2, A3, A4, A5, A6, A7 | **cerrados** (§16) |
| A8 | **cerrado** |
| B1, B2 | **cerrados** |
| C2, D1, D2, E1–E5 | abiertos |

backend 1354 pruebas, frontend 720.

---

## 17 bis. Que el panel de selectividad persista de verdad

El aviso de §17 era insuficiente y la corrección tenía tres partes encadenadas.

### 17b.1 Se guardaba UNA vez, al final de los ocho

`handleRunAll` recorría los ocho anti-targets en un bucle y llamaba a guardar
**después del último**. Un panel completo tarda minutos. Si el usuario cambiaba
de pestaña a la mitad —y el panel se monta dentro de
`{advancedTab === "selectivity" && ...}`, así que cambiar de pestaña lo
**desmonta**— todo lo acoplado hasta ahí se perdía sin haber llegado nunca a la
base.

Ahora **cada resultado se persiste al salir**, dentro del bucle. Una tanda
interrumpida deja escrito exactamente lo que alcanzó a calcular, y repetir el
panel ya no repite el trabajo hecho.

### 17b.2 El backend fusiona en vez de reemplazar

`evaluation.anti_target_results = payload.off_targets` reemplazaba la lista
entera. Con guardado incremental eso es una pérdida esperando a ocurrir: dos
peticiones pueden llegar desordenadas, y una tardía con menos objetivos borraría
minutos de docking ya escrito.

La fusión es por `pdb_id`, gana el último valor de cada objetivo, y las filas sin
`pdb_id` no entran —sin clave no hay forma de actualizarlas después—. Y
`commit_with_retry` en vez de `commit`: es la misma contención de SQLite que ya
obligó al pipeline a usarlo.

### 17b.3 Al volver, se lee de la base — siempre

La rehidratación existía, pero **sólo dentro del auto-poll**, que se enciende
únicamente cuando el pipeline corrió el panel. Quien lo lanzaba a mano volvía a
la pestaña y encontraba el panel vacío **aunque el resultado estuviera
guardado**.

Ahora se lee al montar siempre que haya evaluación y no haya nada en memoria: no
pisa un panel en curso ni compite con el auto-poll. Y lo que viene de la base se
marca como guardado, porque lo está: mostrar el aviso ámbar ahí sería una alarma
falsa, y una alarma falsa enseña a ignorar la verdadera.

### 17b.4 Un detalle de React que habría vuelto a morder

El guardado vivía **dentro** del actualizador de `setResultsMap`. React puede
invocar ese actualizador dos veces (StrictMode) y no garantiza cuándo: un efecto
de red ahí dentro se dispara de más o tarde. Ahora el siguiente mapa se compone
fuera, contra un espejo en `useRef`, se persiste, y luego se aplica.

### 17b.5 Qué queda del aviso

Se queda, y sólo para cuando la escritura falla de verdad. Entonces sí hay que
decirlo, porque el usuario decide si repite el panel. Pero ya no es la respuesta
al defecto: es el último recurso cuando el arreglo no alcanza.

backend 1363 pruebas, frontend 724.

---

## 18. La cacería: dónde más se borra el trabajo al cambiar de página

El defecto de §17 bis no era un caso aislado sino un **patrón**, y merecía un
barrido. La firma es siempre la misma:

> una operación cara se ejecuta, su resultado vive sólo en el estado de un
> componente que se desmonta al navegar, y nadie lo escribe —o lo escribe el
> navegador, que es justo quien desaparece—.

### 18.1 Inventario

| sitio | qué pasaba | estado |
|---|---|---|
| `POST /selectivity/{id}` | **tercer** `except Exception: pass` sobre la misma escritura | corregido |
| `POST /selectivity/stream` | `except: pass` + `commit` sin reintento | corregido (§17) |
| `POST /selectivity/save` | reemplazaba la lista entera | corregido (§17 bis) |
| `POST /selectivity/dock-target` | **no persistía nada**: guardar era tarea del navegador | corregido |
| `POST /mmgbsa/{id}` | **no persistía nada**: mil pasos de minimización que se borraban al recargar | corregido |
| `GET /anti-targets` | degradaba en silencio si la base no respondía | ahora registra |
| `SelectivityModal.tsx` | duplicado con los tres defectos… y **sin usar por nadie** | marcado |
| `app/evaluation/batch/page.tsx` | — | **ya estaba bien** |

### 18.2 Lo que estaba bien, y por qué conviene decirlo

La página de **batch** —que era la sospecha— resultó ser el ejemplo a seguir:
guarda el `run_id` en almacenamiento de usuario y al montar **le pregunta al
backend por el estado real**, restaurando el paso del asistente. Su propio
comentario dice la regla: *«No se restaura desde localStorage nada que el backend
pueda contradecir»*. Es exactamente lo que le faltaba al panel de selectividad.

También se revisaron los otros `.catch(() => {})` del frontend
—`ProXaiTab`, la carga de poses y proteína en `ProEvaluation`, el sondeo de
`CaseRunTracker`—: son **lecturas** que se repiten al montar. Perder una no
pierde trabajo, y el servidor sigue siendo la fuente.

### 18.3 El cambio de fondo: quien hace el trabajo es quien lo guarda

`dock_single_anti_target` devolvía el resultado y se desentendía. Si el usuario
cerraba la pestaña, cambiaba de vista o se le caía la conexión entre un
anti-target y el siguiente, ese docking —**ya pagado en CPU**— se perdía sin
dejar rastro.

Ahora persiste el endpoint. El resultado sobrevive **aunque el cliente
desaparezca**, que es exactamente lo que pasa al cambiar de pestaña en un panel
que se desmonta. Lo mismo con MM-GBSA: el valor se escribe donde el dossier ya lo
buscaba, así que el informe deja de declarar «no calculado» algo que el usuario
vio en pantalla.

### 18.4 Una prueba que estuve a punto de escribir mal

El primer intento prohibía el patrón `except Exception: pass` en todo el módulo.
Dio cinco falsos positivos —limpiezas de directorios temporales y lecturas de
archivo con alternativa, donde tragar el fallo *es* lo correcto— y me habría
llevado a ensuciar código sano para callar la prueba.

Lo que se comprueba ahora es la **propiedad**, no la forma: toda función que
escriba el resultado reintenta con `commit_with_retry`, registra el fallo, y se
lo dice al cliente en `persisted`.

backend 1367 pruebas, frontend 724.

---

## 19. Doc 71 §3: E1, D1 y E3

Los tres que el doc 71 agrupa como «baratos y visibles», con E1 primero por ser
el único de severidad alta que quedaba.

### 19.1 E1 — la vista previa del certificado

Lo primero fue descartar la sospecha del informe. Los dos flujos **sí** resuelven
documentos distintos, y es deliberado: el **certificado** (`GET /blockchain/
certificate/…`) sella cuándo se emitió algo; el **dossier del caso**
(`POST /evaluation/dossier/…`) declara qué evidencia produjo una corrida. Hay
incluso una prueba de frontera que impide mezclarlos.

Lo que sí era un defecto está en el servidor: **`generate_certificate_pdf` es
síncrona** —ReportLab componiendo tablas, imágenes y apéndice— y se llamaba
directamente desde un `async def`. En un backend de escritorio de un solo proceso
eso **congela el bucle de eventos entero** mientras dura: el sondeo del pipeline,
el catálogo, la petición gemela del propio certificado.

Y explica la asimetría que el informe describió. La descarga la dispara un click;
la vista previa **se monta sola**, y React invoca el efecto dos veces en
desarrollo. Salían **dos renders simultáneos del mismo documento**, sin que nadie
cancelara el primero: bloqueo doble, y el WebView cortando la petición en vuelo.

Dos correcciones:

- el render sale a un hilo con `asyncio.to_thread` —lo que este repositorio ya
  usa para el gestor de modelos y la siembra de estructuras—;
- el visor aborta con `AbortController` la petición que va a descartar. De paso
  se cerró una fuga: la limpieza revocaba `url` leyéndola por cierre, y en la
  primera pasada `url` todavía era `""` porque el `await` no había resuelto, así
  que ese blob quedaba vivo hasta recargar la ventana.

> **No se pudo reproducir el `Failed to fetch` exacto sin la VM.** Lo que se
> corrige son los dos mecanismos que producen esa forma de fallo. Queda dicho
> para que nadie lea esto como una confirmación.

### 19.2 D1 — `características`

No era JSON mal decodificado, como parecía. Es una regla del lenguaje: **las
secuencias de escape sólo las interpreta el parser dentro de un literal de
cadena**. En el texto entre etiquetas JSX no hay literal, así que la secuencia
son seis caracteres y se pintan seis.

Había **seis** líneas así, todas en `ProXaiTab.tsx` —el informe vio una porque
las otras aparecen en otros estados—. Y el error no lo detecta el compilador ni
el linter: es texto perfectamente válido.

Por eso hay una prueba que barre todos los `.tsx` y no sólo un arreglo. Lo que
**no** prohíbe: la misma secuencia dentro de comillas es correcta y se usa a
propósito (el mapa de etiquetas ECIF de ese mismo archivo está lleno de ellas y
renderiza bien). Se inspecciona sólo lo que queda fuera de las comillas.

*Nota al margen:* la primera versión de esa prueba metió la secuencia inválida en
su propio nombre y no compilaba. El defecto es fácil de reintroducir incluso
sabiendo exactamente cuál es.

### 19.3 E3 — la fecha sin huso

`datetime.utcnow().isoformat()` produce `2026-09-02T20:22:57.261446`: sin `Z` ni
offset, y `utcnow()` además devuelve un datetime **naive** —está deprecado en 3.12
justo por esto—.

Iba dentro del **memo que se sella en cadena**. En un certificado eso pesa más
que en cualquier otro sitio: el documento existe para poder reconciliarse con
otras fuentes, y una hora sin huso no se compara con nada sin adivinar. También
se corrigió el `timestamp` que se escribe en una columna `DateTime(timezone=True)`.

**Los memos ya sellados no cambian**: quedan en la cadena tal como se emitieron.

### 19.4 Estado del doc 71 §3

| | |
|---|---|
| cerrados | C1, A1–A8, B1, B2, **E1**, **D1**, **E3** |
| abiertos | C2, D2, E2, E4, E5 |

backend 1374 pruebas, frontend 725.

---

## 20. Doc 71 §3: los cinco que quedaban

### 20.1 C2 — un estado físico atribuido a algo que no existe

El dossier decía, con veinte líneas de distancia:

> «Pose recomendada por el selector: — (El selector no recomendó ninguna pose.)»
> «Estado físico de la pose recomendada: **passed**»

Las dos frases eran ciertas por separado. Cuando el selector se abstiene, el
estado que trae el contrato es el de la pose que **habría** recomendado.

No se borra el dato —es útil saber que la candidata descartada pasaba los
controles—: se le pone el nombre de quién es. Un campo que atribuye una propiedad
a algo inexistente no es un dato de más, es una contradicción dentro del mismo
documento.

### 20.2 E2 — la pose que desaparecía de las dos listas

```python
if e == FISICO_PASA and r != rank_sugerido
```

Excluir la pose sugerida es correcto **cuando el selector recomendó algo**: esa
pose es la recomendación, no una alternativa a sí misma. Pero al abstenerse,
`rank_sugerido` es la candidata que descartó, y no hay recomendación de la que
sea alternativa.

Excluirla ahí la hacía desaparecer de **las dos listas a la vez**: no era la
recomendada, porque no hubo ninguna, y tampoco figuraba entre las físicamente
válidas aunque hubiera pasado los controles.

### 20.3 D2 — medido, no supuesto

Generando el PDF y extrayendo su texto con `pypdf`:

```
-   U+002D  sobrevive        •   U+2022  →  U+007F
*   U+002A  sobrevive        ⚠   U+26A0  →  ■
·   U+00B7  sobrevive        ▪   U+25AA  →  ■
→   U+2192  sobrevive        ✓   U+2713  sobrevive
```

La causa no es el texto sino la fuente: `font_path` apunta a
`/usr/share/fonts/truetype/dejavu/…`, **una ruta de Linux que en Windows nunca
existe**, así que se cae a Courier. Ni Courier ni Helvetica llevan el glifo del
bullet en su codificación.

Se usa el punto medio, el más parecido a una viñeta de los que sobreviven. Y la
prueba **genera el documento y comprueba la extracción**, así que no depende de
que nadie recuerde la tabla.

### 20.4 E5 — la página casi vacía

`allowWidows = 1` es el valor por defecto de ReportLab: permite dejar la última
línea de un párrafo sola al principio de la página siguiente. Apagado en la hoja
de estilos entera. La prueba comprueba que ninguna página del documento generado
queda con menos de 120 caracteres.

### 20.5 E4 — la doble barra

El overlay del comparador de poses lleva su propia `overflow-y-auto`, pero la
página de detrás seguía desplazándose. Es el mismo `useScrollLock` que ya usan
los otros seis modales del producto; éste se quedó sin él.

### 20.6 Un fallo que no estaba en la lista

La prueba que genera el PDF encontró esto antes de poder comprobar nada:

```
UnboundLocalError: cannot access local variable 'hia_note'
```

`hia_note` sólo se asignaba en la rama donde hay absorción intestinal
serializada. Con cualquier molécula cuyo ADMET no se ejecutó, **el certificado no
se podía generar en absoluto**.

No estaba entre los 19 defectos porque la evaluación de la VM tenía ADMET
completo y nunca entró por ahí. Lo encontró una prueba que **genera el documento
de verdad**, no una que inspecciona el código — y esa es toda la diferencia.

### 20.7 Estado final del doc 71 §3

**Los 19 defectos están cerrados.**

| grupo | |
|---|---|
| C1, C2 | conclusión injustificada y pose contradictoria |
| A1–A8 | serialización y evidencia ML |
| B1, B2 | selectividad que no persistía |
| D1, D2 | codificación en pantalla y en PDF |
| E1–E5 | certificado, poses, fecha, scroll y paginación |

backend 1385 pruebas, frontend 725.

---

## 21. La resincronización: que las correcciones lleguen

Sin esto, nada de los veinte apartados anteriores llega a una máquina que haya
abierto la aplicación alguna vez. La causa está en dos líneas:

```python
if len(existing_targets) > 10:
    return
...
if existing:
    continue
```

El catálogo se escribía **una vez**, en el primer arranque, y nunca más.

### 21.1 La línea divisoria no es técnica, es de propiedad

> **El catálogo describe la estructura; el usuario produce el resto.**

| del catálogo | del usuario |
|---|---|
| nombre, descripción, cadena, caja, familia, organismo, resolución, hotspots y su procedencia, composición del sitio, cofactores, umbrales | si el receptor está preparado y dónde, la calibración local (`spearman_rho`, `calibration_date`), si lo marcó como caliente, todo lo de blockchain |

Sobrescribir una calibración local sería **borrar trabajo del usuario para poner
un `null`** — exactamente lo que este módulo existe para evitar en la otra
dirección.

Y sólo actúa sobre filas que el catálogo posee: ni privadas, ni de comunidad, ni
variantes de preparación. Una variante lleva el mismo `pdb_id` que su padre *a
propósito*; sobrescribirla destruiría justo lo que la hace una variante.

### 21.2 Invalida el receptor preparado, y esto importa

Si cambia la cadena, las cadenas del sitio o la caja, el `.pdbqt` que hay en
disco describe **otra cosa**. Servirlo sería acoplar contra el receptor viejo con
la anotación nueva, que es peor que cualquiera de los dos por separado. Se marca
como no preparado y se vuelve a preparar en la siguiente corrida.

Un cambio descriptivo —el organismo, la resolución— no invalida nada.

### 21.3 Los retirados no se borran

2ONV y 5TXJ salieron del catálogo. Sus filas se **conservan**: puede haber
evaluaciones colgando de ellas, y borrar el trabajo de alguien para limpiar una
tabla no es una operación que el arranque deba hacer solo. Se marcan con
`retired_reason` y `list_targets` deja de ofrecerlos.

### 21.4 Por qué se ejecuta sola

Porque el defecto es precisamente que nada llegaba: una sincronización que hay
que lanzar a mano no habría arreglado la VM. Es idempotente —se salta entera si
la huella SHA-256 del catálogo no cambió, así que el coste de un arranque normal
es leer un archivo y hacer un `SELECT`— y un fallo no impide arrancar: se
registra y se sigue con el catálogo que haya. Una base desactualizada es
preferible a una aplicación que no abre.

### 21.5 Probada contra una base de verdad

18 pruebas que reproducen el escenario de la VM —una base sembrada con el
catálogo antiguo— y fijan las cuatro propiedades de las que depende que sea
seguro ejecutarlo solo: actualiza lo del catálogo, no toca lo del usuario,
invalida el `.pdbqt` cuando hace falta, y la segunda vuelta no hace nada.

*Una de esas pruebas la escribí mal:* afirmaba que la cadena de 1TW7 cambiaría, y
la cadena de 1TW7 en el catálogo **es** `A` —está entre las que forman el sitio,
así que nunca hizo falta corregirla—. La aserción habría pasado por casualidad en
otro receptor. Ahora comprueba `site_chains`, que es lo que de verdad cambia.

backend 1409 pruebas, frontend 725.

---

## 22. Los cinco que quedan, uno por uno

Al abrirlos aparecieron **dos diagnósticos que no estaban en ninguna lista**.

### 22.1 1TW7 — la caja está bien; los hotspots están en el codo

Proteasa del VIH-1, 1,3 Å, multirresistente. El centro de la caja cae sobre
`B:THR26` y `A:THR26` a **2,0 Å**, con `ASN25` y `GLY27` al lado: es la tríada
catalítica del dímero (ASN porque 1TW7 es el mutante inactivo D25N, lo habitual
en complejos con sustrato). Los diez hotspots anotados —`LYS14`, `ILE15`,
`GLY16`, `GLY17`, `GLN18`, `PRO63`, `ILE64`, `GLU65`, `LYS70`, `VAL71`— están a
**16–25 Å**, en la región del codo y la bisagra de las aletas.

MolPocket no ayuda: su cavidad más cercana está a 12,3 Å con **druggability
0,10**. Con la preparación multicadena el docking ya usa las dos cadenas y el
bolsillo se dobló (301 → 600 átomos); lo que falta es **reanotar diez hotspots**,
y ninguna herramienta da una respuesta de fiar sin ligando.

### 22.2 5T4X — aquí la duda recae sobre la caja

PDE6δ apo, 1,81 Å. El centro cae sobre `THR131`, `GLN78`, `LEU76`; los hotspots
—`TRP90`, `MET20`, `LEU38`, `ILE109`, `TRP32`— parecen el **bolsillo prenilo
real** de PDE6δ, que es su sitio farmacológico. La cavidad que MolPocket ofrece
está a 1,8 Å del centro pero es **la 8.ª de 8**, con druggability 0,25.

Es el único de los cinco donde la sospecha recae sobre la caja y no sobre la
anotación.

### 22.3 6PSD — no es un bolsillo de fármaco

CRACR2a con la cadena intermedia ligera de dineína, 2,66 Å. El centro cae sobre
`K:VAL92`, `L:VAL443`, `L:PHE447`: la **interfaz de un complejo
proteína-proteína**. Los hotspots 90–94 son contiguos al VAL92 que está a 1,4 Å,
así que la anotación acierta en el núcleo; lo que dispara el fallo es una cola de
residuos a 14–18 Å.

MolPocket da druggability **0,30**, y eso es información, no ruido: una interfaz
PPI **no es** un bolsillo de molécula pequeña. La pregunta de fondo no es cómo
anotarlo sino si un objetivo así pertenece a un catálogo de docking.

### 22.4 6VU4 — no es una proteína

«β-hairpin peptide mimic», y al abrirlo: **28 residuos** entre dos cadenas. El
centro cae sobre `ILE12`/`ILE13`/`GLY14` de ambas —la interfaz del par— y los
hotspots coinciden (0,3 semilados). Falla sólo porque el `MEA` que hay a 6,2 Å no
los toca, y **MEA es un aditivo de cristalización**, no un ligando.

Es **la misma categoría que 2ONV y 5TXJ**, los dos que se retiraron: un péptido,
no un receptor. Se salvó del filtro por tener 452 átomos en la caja frente a los
36 de 2ONV.

### 22.5 5VB8 — el hallazgo: falta el 75% del receptor

Canal de sodio NavAb, 2,85 Å. El archivo trae **una sola cadena**, y el propio
PDB lo dice:

```
AUTHOR DETERMINED BIOLOGICAL UNIT: TETRAMERIC
SOFTWARE DETERMINED QUATERNARY STRUCTURE: TETRAMERIC
```

La unidad biológica hay que **generarla** aplicando las matrices `BIOMT` del
`REMARK 350`. Nuestro pipeline lee sólo las coordenadas depositadas, así que ve
**un cuarto del canal**. La caja está sobre el eje del poro —que es donde el poro
estaría— y por eso su centro queda a **10,3 Å del átomo más cercano**: apunta a
espacio vacío, porque tres cuartas partes de la pared del poro no existen en el
archivo.

### 22.6 Lo que ese hallazgo obligó a medir

**46 de los 385** declaran una unidad biológica que hay que generar con BIOMT —el
12% del catálogo—. Podría haber sido un defecto sistémico, así que se midió lo
que de verdad discrimina: la distancia del centro de la caja al átomo más
cercano.

```
mediana 3,5 Å      p90 4,3      p99 5,4      máximo 10,3
por encima de 6 Å:  2 de 385
```

- **5VB8** — 10,3 Å, y es de los 46. El caso real.
- **2A3W** — 8,2 Å. Amiloide sérico P, decamérico, pero la caja está centrada en
  su ligando co-cristalizado dentro de una cavidad amplia. **El ligando sí está
  ahí**: no es el mismo problema.

Es decir: de los 46, **uno**. Un sitio contenido en una subunidad se acopla bien
contra la unidad depositada; sólo importa cuando la pared del bolsillo la forman
las copias que faltan. Queda una prueba que vigila esa distancia para el receptor
que alguien añada mañana.

### 22.7 Qué necesita cada uno

| | naturaleza del problema | qué habría que decidir |
|---|---|---|
| **1TW7** | anotación: 10 hotspots en el sitio equivocado | reanotar a mano desde la química (tríada y aletas) |
| **5T4X** | la caja, no la anotación | recentrar sobre el bolsillo prenilo, con criterio |
| **6PSD** | interfaz PPI, no bolsillo | ¿pertenece a un catálogo de docking? |
| **6VU4** | péptido de 28 residuos | misma categoría que 2ONV y 5TXJ: candidato a retirar |
| **5VB8** | falta el 75% del receptor | generar el tetrámero con BIOMT, o retirarlo |

**Ninguno de los cinco es un fallo de código.** Los cinco son decisiones
científicas, y dos de ellas —6PSD y 6VU4— son de alcance de producto: qué cuenta
como receptor.

---

## 23. Los cinco, retirados — y una corrección a §22.6

### 23.1 Mi medida anterior era optimista

En §22.6 concluí que de los 46 con unidad biológica a generar, **sólo 5VB8**
estaba afectado. La medida era la distancia del centro de la caja al átomo más
cercano, y **no detecta el caso que importa**: un sitio en una interfaz generada
por simetría, donde el centro sí toca la cadena depositada pero **la pared de
enfrente falta**. Ahí la distancia es normal —3 o 4 Å— y el defecto es invisible.

La medida correcta es directa: **generar el ensamblaje y contar cuántos átomos
aparecen dentro de la caja que no estaban en el archivo.**

Primero se verificó la suposición en la que se apoya —que la primera matriz
`BIOMT` es la identidad—: cierto en las 39, y con exactamente una identidad en
cada una. (39 y no 46: el recuento anterior tomaba el máximo índice `BIOMT`
entre *todos* los ensamblajes declarados, y varias entradas declaran más de uno.
Los 39 son los de `BIOMOLECULE: 1`, el ensamblaje principal.)

### 23.2 El resultado

```
PDB     depositados   que faltan   % que falta
5VB8            516         2125        80,5%   x4
5YUA            614         1306        68,0%   x4
6SX5            396          728        64,8%   x4
6SX7            330          523        61,3%   x4
6VU4            452          624        58,0%   x3
6SXC            411          545        57,0%   x4
6SXG            410          542        56,9%   x4
6MWA            336          347        50,8%   x4
6SXE            425          431        50,4%   x4
6P6X            787          661        45,6%   x4
5E4G            288          227        44,1%   x2
6OGV            288          195        40,4%   x2
…
6LU7            480           69        12,6%   x2
```

**31 de los 39 tienen átomos que faltan dentro de su caja de docking. Diez
superan el 40%.** Ocho tienen cero.

Es **el mismo defecto que el modo C del doc 71** —el sitio se forma entre
copias y sólo se conserva una— pero generado por la **simetría cristalográfica**
en vez de por el filtrado de cadena. Y era invisible a todas las comprobaciones
construidas hasta ahora, porque todas leen las coordenadas depositadas.

> **No está corregido.** Queda medido y con nombre; repararlo exige generar el
> ensamblaje antes de preparar el receptor, que es una pieza nueva.

### 23.3 Los cinco, fuera

`curated_targets.json` pasa de **385 a 380**, y el expediente queda en
**380 de 380**. Los siete retirados conservan su fila completa en
`docs/auditorias/receptores_retirados.json`; reponer uno es copiarla de vuelta.

### 23.4 Retirar 1TW7 estuvo a punto de apagar cuatro pruebas en silencio

Tres archivos de prueba cargaban 1TW7 **del catálogo** y hacían `pytest.skip`
cuando no lo encontraban. Al retirarlo habrían pasado a saltar sin que nadie lo
notara — incluido `test_el_radio_derivado_no_pierde_nada_de_lo_que_el_ligando_
puede_tocar`, que es **el invariante del radio de recorte**.

Un `skip` que oculta cobertura perdida es peor que un fallo. Ahora:

- la referencia es **5COP** —proteasa del VIH salvaje, sitio en la interfaz del
  dímero, 54 átomos de contacto por cadena y evidencia de ligando
  co-cristalizado: el mismo caso de libro que 1TW7, con mejor material—;
- y si desaparece del catálogo, las pruebas **fallan**, no saltan.

### 23.5 Estado

```
catálogo                380 objetivos
expediente              380 de 380
sitios de interfaz       98
cadena declarada fuera    0
```

backend 1410 pruebas, frontend 725.

---

## 24. La unidad biológica, generada

### 24.1 Qué es lo que faltaba

Un PDB deposita la **unidad asimétrica**: lo que hizo falta para describir el
cristal. La **unidad biológica** es la forma funcional. Cuando el ensamblaje
tiene simetría interna que coincide con la del cristal, basta depositar una
fracción, y el resto se reconstruye aplicando las matrices `BIOMT` del
`REMARK 350`.

Nuestro pipeline leía **sólo las coordenadas depositadas**. Por eso el defecto
era invisible a todas las comprobaciones construidas hasta ahora: todas miraban
el mismo archivo incompleto.

### 24.2 Se aplica siempre, y por eso es seguro

Cuando sólo hay la identidad —341 de los 380— la función devuelve la entrada
**intacta**. Y cuando el sitio está contenido en una subunidad, las copias
generadas caen lejos de la caja y el recorte al sitio las descarta: el resultado
no cambia. No hay que decidir caso por caso, que es donde se cuelan los errores.

Las cadenas nuevas se nombran en orden fijo, así que la misma entrada da siempre
la misma salida. De eso depende que la caché del receptor preparado siga siendo
válida: si los nombres cambiaran entre corridas, se invalidaría el `.pdbqt` en
cada arranque.

### 24.3 Lo que cambió en el catálogo

**Quince objetivos** resultaron tener un sitio distinto del anotado:

```
1KTZ  ['A']       → ['A', 'C']          6P6X  ['A']       → ['A', 'C']
3RVY  ['A','B']   → ['A', 'B', 'D']     6SX5  ['A']       → ['A', 'D']
3RVZ  ['B','A']   → ['B', 'C', 'A']     6SX7  ['A']       → ['A', 'D']
3RW0  ['A','B']   → ['A', 'B', 'D']     6SXC  ['A']       → ['A', 'C']
5E4G  ['A']       → ['A', 'B']          6SXG  ['A']       → ['A', 'C']
5VA1  ['A']       → ['A', 'B']          8GJR  ['C']       → ['C', 'B']
5YUA  ['A']       → ['A', 'B', 'D']     6MWA  ['B']       → ['B', 'C']
6OGV  ['A']       → ['A', 'B']
```

Sitios de interfaz: **98 → 110**. Y **ninguno** perdió su cadena declarada, así
que no hubo regresión: el expediente sigue en **380 de 380**.

Medido sobre el receptor preparado:

```
                     antes    ahora
5YUA                   614     1911   ×3,1
6P6X                   776     1428   ×1,8
6SX5                   396      984   ×2,5
1KTZ                   177      226   ×1,3
```

### 24.4 Dos defectos que salieron al hacerlo

**Había dos implementaciones de la anotación del sitio.** `anotar_sitio` en el
backend y una copia en `scripts/anotar_sitio_en_catalogo.py` que la reconstruía
desde `revisar()`. Coincidieron en los 385 objetivos… **hasta que una empezó a
generar el ensamblaje y la otra no**. El catálogo se quedó sin las cadenas de
simetría y el `--aplicar` no cambió nada, en silencio. El script delega ahora en
la única implementación.

*Duplicar una medida no es redundancia: es una divergencia esperando a ocurrir* —
y esta vez ocurrió en el sitio donde más fácil era pasarla por alto.

**Y `trim_to_pocket` perdía cadenas.** Cuando el recorte quita más de la mitad de
los átomos, pasa el resultado por **PDBFixer** para tapar los extremos rotos.
PDBFixer reescribe el PDB a través de la topología de OpenMM y **renombra las
cadenas**. Sobre 6SX5:

```
tras filtrar a {A, D}    {'A': 2079, 'D': 2079}
con caps                 {'A': 1423}            ← la cadena D desapareció
sin caps                 {'A': 700, 'D': 1345}
```

El receptor perdía media cavidad **en silencio**, que es exactamente el defecto
que el recorte multicadena existe para reparar. Los caps siguen activos por
defecto —MM-GBSA los necesita: un terminal roto falsea la energía— y se apagan
por argumento sólo en la preparación del receptor, donde la identidad de cadena
sostiene todo lo demás.

### 24.5 Estado

```
catálogo                380 objetivos
expediente              380 de 380
sitios de interfaz      110
cadena declarada fuera    0
```

backend 1418 pruebas, frontend 725, `cargo check` limpio.
