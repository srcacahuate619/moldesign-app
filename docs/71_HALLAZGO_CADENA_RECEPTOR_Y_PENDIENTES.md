# 71 — La cadena del receptor, y los 19 defectos abiertos

**Fecha:** 2026-09-02
**Origen:** primera evaluación completa en una VM limpia. El dossier declaraba
«receptor 1TW7 · cadena A» con todos los hotspots en la cadena B.
**Herramienta:** `scripts/auditar_cadena_del_receptor.py`
**Estado:** medido y documentado. **Sin corregir**: la corrección es una decisión
científica del propietario.

---

## 0. Procedencia: esto no es un descubrimiento, es una poblacion que faltaba

**Correccion a la primera version de este documento.** Se presento el hallazgo
como nuevo. No lo es, y la diferencia importa para no repetir el error de
medir lo que ya estaba medido.

El fenomeno estaba documentado y contado desde antes:

| Documento | Que establecio | Sobre que poblacion |
|---|---|---|
| `19_LIMITATIONS.md:21` | El modo de fallo, **con la proteasa del VIH como ejemplo**: «pocket inter-cadena, recorta UNA cadena, **pocket destruido si no curated**» | ninguna: es una limitacion declarada |
| `FEP-02` (artefacto sellado) | **Contado**: `sitio.entre_cadenas: 43` de 203 (21%), `multi_cadena: 87` | cohorte experimental derivada de PDBBind |
| Este documento | 149 de 387 pierden >=20% de la caja; 20 pierden el 100% | **el catalogo curado del producto** |

**La interseccion entre la cohorte de FEP-02 y el catalogo del producto es
CERO.** Los 387 objetivos que el investigador elige en la aplicacion nunca se
midieron para esto.

Y ahi esta lo unico verdaderamente nuevo: `19_LIMITATIONS` acotaba el riesgo
con un «si no curated», es decir, daba por hecho que el catalogo curado tenia
la cadena verificada. **Esa suposicion nunca se comprobo, y es falsa.**

Tres consecuencias para leer el resto del documento:

1. **Nadie corrompio los receptores.** Las estructuras son byte a byte las que
   publica el RCSB; ver `scripts/verificar_integridad_estructuras.py`.
2. **Las auditorias previas no se equivocaron.** Midieron bien lo que se
   propusieron medir. Lo que falto fue conectar «43 sitios estan entre
   cadenas» con «`preparer.py:234` descarta las demas en cada docking real»,
   y extender la medida al catalogo.
3. **Hay un segundo defecto que FEP-02 no podia ver**, porque no es «sitio
   repartido» sino **cadena mal anotada**: en 1IAS la caja esta sobre la
   cadena B y la declarada esta a 19,1 A; en 2OYE la cadena declarada no
   existe en el PDB. Eso no es una limitacion conocida: es un error de datos.

> La leccion operativa es la misma que atraviesa todo el doc 70: una medida
> vale para la poblacion sobre la que se tomo. FEP-02 midio la cohorte
> experimental y su conclusion era correcta para ella; el catalogo del producto
> es otra poblacion y nadie la midio.

---

## 1. El hallazgo

`preparer.py:234` conserva **sólo** la cadena que declara el catálogo:

```python
if current_chain != chain_id:
    continue
```

Para una proteína monomérica eso es ortodoxo y correcto. Cuando el sitio activo
se forma entre varias cadenas, el ligando acopla contra media cavidad — o contra
ninguna.

**La pregunta no es si los hotspots están bien anotados.** Es cuántos átomos que
caen **dentro de la caja de docking** se descartan por no pertenecer a la cadena
declarada. Eso se mide.

### Sobre los 387 objetivos del catálogo

| | |
|---|---:|
| pierden **≥20%** de los átomos de la caja | **149** |
| pierden entre 5% y 20% | 19 |
| pierden <5% | 219 |

**Al menos veinte pierden el 100%**: la cadena declarada no aporta ni un átomo a
la caja.

### Tres modos de fallo, verificados uno a uno

**A — Cadena equivocada. El docking corre contra el vacío.**

```
1IAS   cadenas en el PDB : A, B, C, D, E
       átomos en la caja : B: 577   (A: 0)
       distancia del centro a cada cadena:
           A:  19.1 Å   <- LA DECLARADA
           B:   3.4 Å
```

El receptor preparado no tiene **nada** donde está la caja. Vina acopla contra
espacio vacío y devuelve una afinidad igualmente. Cualquier número producido para
estos objetivos carece de significado físico.

**B — Cadena inexistente.**

```
2OYE   cadenas en el PDB : P (única)
       catálogo declara  : A
```

`preparer.py:298` lanza «No quedaron átomos ATOM tras filtrar la cadena 'A'». Al
menos falla ruidosamente.

**C — Sitio en la interfaz de un oligómero.**

```
1TW7   proteasa del VIH-1, homodímero
       átomos en la caja : A: 309   B: 316
       distancia del centro: A 2.0 Å   B 2.0 Å
```

El sitio activo **está** en la interfaz del dímero: es química de libro de texto.
Conservar sólo A descarta la mitad del bolsillo, y el ligando puede ocupar el
espacio donde debería estar el otro monómero.

### Lo que NO es la causa

El informe de la VM sugería que el emparejamiento de hotspots explicaba el
«fracaso farmacofórico». **No es así.** `vina_service.py:963` tiene un respaldo
sin cadena que empareja `A:LYS14` con `B:LYS14` por nombre y número, así que el
emparejamiento sobrevive.

Pero ese respaldo **enmascara** la discrepancia, y de paso hace que el dossier
nombre residuos de una cadena que no está en el receptor. Es un segundo defecto,
de procedencia, no de química.

---

## 2. Qué propongo hacer

Tres partes, en orden de urgencia. **La primera no requiere decisión científica;
las otras dos sí.**

### 2.1 Bloquear el docking contra el vacío — inmediato

Un docking cuya caja no contiene ni un átomo del receptor preparado no debe
ejecutarse. Ahora mismo se ejecuta y devuelve un número.

Propuesta: un control **bloqueante** en el preflight —donde ya viven los demás—
que cuente átomos del receptor preparado dentro de la caja y detenga la corrida
si son cero, o avise si están por debajo de un umbral.

Esto no decide nada sobre qué cadena es la correcta: sólo impide emitir un
resultado sin sustento. Encaja con la política del preflight, que ya bloquea
cuando no puede sellar la estructura.

**Coste:** bajo. **Riesgo:** bloquea objetivos que hoy «funcionan» devolviendo
números sin sentido — que es el punto.

### 2.2 Corregir el catálogo — requiere criterio

Para los 149, hay que decidir caso por caso entre:

| Opción | Cuándo aplica | Consecuencia |
|---|---|---|
| **Corregir la cadena declarada** | la caja está sobre otra cadena concreta (1IAS → B; 2OYE → P) | trivial, y arregla el caso |
| **Preparar con varias cadenas** | el sitio está en una interfaz (1TW7) | cambia el método; hay que decidir si el receptor multicadena es el contrato |
| **Retirar el objetivo** | la anotación no se puede reconstruir con confianza | reduce el catálogo, aumenta la honestidad |

La auditoría ya produce la lista ordenada por gravedad. Yo empezaría por los ~20
del 100%, que son los que hoy devuelven números sin significado.

**Lo que no haría:** un arreglo automático masivo. Elegir la cadena por «la que
más átomos aporta a la caja» acierta en muchos casos y se equivoca en silencio en
otros, y este repositorio ya tiene bastante experiencia con correcciones que
parecen razonables y afirman algo falso.

### 2.3 Consecuencia sobre lo ya sellado

Hay que comprobar si algún artefacto de `scripts/artifacts_science/` usó
objetivos afectados. Si los usó, el resultado no se borra: se le añade un
**corrigendum** que declare la condición, como se hizo con `MF-33-H-COR`.

**Esto es lo que hace que la corrección no sea sólo técnica.** Cambiar cómo se
prepara un receptor cambia los números de todo lo que se corrió con el método
anterior.

---

## 3. Los 19 defectos abiertos

Del informe de la primera evaluación completa en la VM. Agrupados por **causa
probable**, no por síntoma: ocho de ellos huelen a un solo origen.

### Grupo A — Serialización y evidencia ML *(8 defectos, causa probablemente única)*

Sospecha: el mapeo entre los resultados del pipeline y el resumen de evidencia
pierde campos. El frontend y el dossier leen sitios distintos.

| # | Severidad | Defecto |
|---|---|---|
| A1 | Alto | **XGBoost incoherente**: el frontend muestra salida `0.05`, aviso de dominio y SHAP; el dossier sólo registra el modelo universal y el aviso OOD, sin serializar predicción, features ni explicación |
| A2 | Alto | **CL-GNN ejecutado sin resultado**: declarado entre las etapas habilitadas y llamado «CL-GNN-dominante», pero aparece «no reportado», peso 0.00, sin salida ni motivo de abstención |
| A3 | Alto | **Contradicción de serialización de Vina**: el frontend dice «sin salida serializada», el dossier dice «9 poses serializadas» y da un hash. Uno de los dos usa mal el término |
| A4 | Alto | **Identidad ambigua de XGBoost**: el selector de poses (`v0.6 XGBRanker`) y el XGBoost de rescoring aparecen bajo el mismo nombre |
| A5 | Medio | **Dominancia sin evidencia**: se atribuye dominancia a un modelo que no reportó nada |
| A6 | Medio | **Metadatos del dominio**: la matriz dice «motor no informado · universal» aunque el documento conoce Vina 1.2.7 y declara XGBoost y CL-GNN |
| A7 | Medio | **Procedencia**: Vina y XGBoost muestran valores calculados mientras afirman no tener salida serializada |
| A8 | Medio | **Advertencias de preflight incompletas**: el frontend muestra dos advertencias y tres controles sin evaluar; el dossier sólo dice «hubo advertencias científicas», sin códigos ni mensajes |

**Por dónde empezaría:** trazar un resultado desde el pipeline hasta
`build_evidence_summary` y hasta el PDF, con una corrida real. Ocho síntomas
apuntando al mismo sitio suelen ser un contrato de datos roto, no ocho bugs.

### Grupo B — Selectividad no persiste *(2 defectos, causa única)*

| # | Severidad | Defecto |
|---|---|---|
| B1 | Alto | El dossier conserva `pro_selectivity: false` y declara «la corrida no registró un panel de anti-targets» **aunque el análisis se ejecutó** |
| B2 | Medio | Los resultados desaparecen al cambiar de pestaña: el estado vive en el componente y no se recupera de evidencia persistida |

Son la misma causa vista desde dos sitios: el resultado de selectividad no se
escribe en la evidencia. Arreglar B1 debería arreglar B2.

### Grupo C — Afirmaciones del dossier *(2 defectos, y uno es de criterio)*

| # | Severidad | Defecto |
|---|---|---|
| C1 | **Crítico** | **Conclusión injustificada**: el informe advierte correctamente que la afinidad Vina no es energía libre, y a continuación afirma «rango micromolar alto, probablemente insuficiente in vivo». Es exactamente la inferencia que acaba de declarar inválida |
| C2 | Medio | **Selección de pose contradictoria**: el selector se abstuvo y el dossier dice que no hay pose recomendada, pero después reporta «estado físico de la pose recomendada: passed» |

**C1 no es un bug de código: es el informe contradiciendo su propio contrato.**
En un producto cuya propuesta es saber cuándo no confiar, pesa más que cualquier
defecto de la lista. Se corrige borrando la inferencia, no matizándola.

### Grupo D — Codificación *(2 defectos, dos capas distintas)*

| # | Severidad | Defecto |
|---|---|---|
| D1 | Medio | **SHAP muestra `caracter\u00edsticas`** —la secuencia literal, sin decodificar— en vez de «características»: una cadena JSON escapada que no se decodifica antes de renderizar |
| D2 | Bajo | **PDF**: los marcadores de lista salen como U+007F y la alerta de XGBoost tiene dos glifos ZapfDingbats que se extraen como cuadrados. Perjudica búsqueda, copiado y accesibilidad |

### Grupo E — Interfaz y PDF *(5 defectos, independientes)*

| # | Severidad | Defecto |
|---|---|---|
| E1 | Alto | **Vista previa del certificado falla con `Failed to fetch`**, aunque la pestaña «Informe» carga el PDF correctamente: dos flujos resuelven el documento por rutas o protocolos distintos |
| E2 | Medio | **Pose #2 omitida**: supera los controles físicos y es la que el selector habría elegido, pero se excluye de «alternativas físicamente válidas» aunque el dossier afirme que las nueve pasaron |
| E3 | Medio | **Fecha sin zona horaria**: `2026-09-02T20:22:57.261446` sin `Z` ni offset; no se puede reconciliar de forma auditable con las horas locales |
| E4 | Bajo | **Doble barra de desplazamiento** en «Comparar poses» |
| E5 | Bajo | **Paginación del PDF**: una frase de la sección 9 se corta entre páginas, y la página 7 contiene sólo la última fila del apéndice |

---

## 4. Orden que propongo

1. **C1** — la conclusión injustificada. Es de criterio, cuesta poco y es lo que
   más contradice el contrato del producto.
2. **Grupo A** — ocho defectos de una tacada si la sospecha del contrato de datos
   es correcta.
3. **Grupo B** — selectividad, dos más.
4. **2.1** — bloquear el docking contra el vacío.
5. **E1, E3, D1** — baratos y visibles.
6. **2.2** — el catálogo, con la lista delante y decidiendo caso por caso.
7. El resto.

**Lo que no está en esta lista y sigue pendiente** del doc 70: los 51 lanzadores
de pip con la ruta del constructor incrustada, el `Bad pickle format` del
análisis de interacciones, MM-GBSA y selectividad sin ejercitar, TabPFN queriendo
descargar, `AutoDock-Vina-GPU` muerto en el instalador (2,8 MB), el runtime de
MSVC sin declarar en `THIRD_PARTY_NOTICES.md`, y la limpieza de código muerto
antes de publicar.
