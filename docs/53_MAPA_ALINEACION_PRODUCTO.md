# 53 — Mapa de alineación del producto MolDesign

**Estado:** dirección de producto vigente tras el cierre de `REC-12-R1` y
`REC-11-CRUCES`.

**Revisión del 2026-08-22.** Dos cambios, ambos verificados contra los artefactos sellados y
contra el código:
1. Se retira la dependencia de `REC-05` para la cuestión de cofactores. `REC-05` fue
   re-alcanzado el mismo día a **metales agrupados** y dejó cofactores y aguas fuera con su
   razón escrita; **no hay experimento pendiente** que autorice corregir receptores. Ver §2.1
   y §11.
2. Se incorpora un defecto interno auditado en el código: existen **tres políticas de
   heteroátomos distintas y no declaradas**, y la que valida el programa científico **no es
   la que ejecuta el producto**. En particular, `preparer.py` elimina todas las aguas —lo
   contrario de lo que declara `docs/51`— y elimina el 100% de los metales porque su puerta
   de conservación depende de un `cofactors_whitelist` que está vacío en los 387 targets del
   catálogo. Ver §6.2, §8 y §12.

**Auditoría externa del 2026-08-22, verificada punto por punto.** Dos hallazgos se
incorporan y se han implementado; dos correcciones al auditor quedan registradas para que no
se repitan:

- **Validez física (el hueco nº1 era real; la cifra que lo justificaba, no).** Implementado
  en `services/chemistry/pose_physical_validity.py`, en configuración `dock` —producción no
  tiene cristal de referencia, así que la `redock` del registro no sirve aquí— con
  degradación declarada a un proxy energético RDKit. **Aviso**: las tasas `dock` y `redock`
  **no son comparables**; presentar una como si refutara la otra repetiría el error de
  escala de `MF-29-EMP-COR`.

  **Corregido el 2026-08-23 por `MF-33-H-COR`.** El auditor y nosotros dábamos por buena la
  medición de `MF-33-TOP1` —10/116 = 8.62 % y 18/116 = 15.52 %, con `internal_energy`
  apareciendo 203 veces— y de ahí «más del 84 % de lo que se entrega es físicamente
  inválido». Esa medición estaba **contaminada por la capa de reconstrucción de
  hidrógenos**: con reconstrucción canónica las tasas son **91.38 % y 94.83 %**. El hueco del
  dossier seguía siendo real —no evaluar la física de lo entregado es un hueco aunque la
  física esté bien— pero **la urgencia y la explicación causal eran falsas**. Lo que queda
  como fallo real es geométrico y escaso: 43 de 8224 poses en siete complejos.

  **Este corrigendum deja DOS deudas abiertas, no una.** Son distintas y se pagan por
  separado; la consistencia interna del módulo ayuda pero no basta, porque **ninguna de sus
  dos rutas evalúa la reconstrucción canónica** que `MF-33-H-COR` validó.

  **Deuda 1 — representación de hidrógenos, por validar.** `pose_pdbqt_a_mol` conserva los
  hidrógenos polares que trae Vina y deja implícitos los demás. En la ruta completa,
  PoseBusters añade los que faltan y **optimiza sólo ésos** (`add_hydrogens_with_uff_positions`),
  dejando los polares tal como llegaron; en el proxy, los no polares siguen implícitos tanto
  en la pose como en la referencia. Ninguna hereda hidrógenos del cristal, así que **no es el
  defecto de `MF-33-H-COR`** —y por eso no explota como allí— pero las dos evalúan
  representaciones **distintas** de la canónica. La lección del corrigendum es exactamente
  que una representación inconsistente puede dominar un veredicto sin que se note.

  **Deuda 2 — proxy energético, por calibrar.** El escalón 2 **no es una reimplementación**
  del `internal_energy` de PoseBusters, aunque se describía así:

  | | PoseBusters 0.6.5 `dock` | proxy del escalón 2 |
  |---|---|---|
  | campo de fuerza | UFF | MMFF, con UFF de respaldo |
  | confórmeros de referencia | 50 | 16 |
  | cantidad | `energía_pose / energía_media` | `(pose − mín) / (media − mín)` |
  | umbral | 100.0 sobre **esa** razón | 100.0 sobre **otra** razón |

  Que los dos umbrales valgan 100.0 es coincidencia sin contenido: se aplican a cantidades
  distintas. Los parámetros de `dock` están leídos de `config/dock.yml` del propio paquete;
  el 7.0 / 100 confórmeros que se citó antes son los **defaults de la función aislada**, no
  los de `dock`. Mientras no exista calibración medida, el escalón 2 se llama **proxy
  energético RDKit no calibrado** y nunca «internal_energy».

  **Ya corregido, sin tocar comportamiento** (2026-08-23): el texto que llegaba al usuario
  citaba «el fallo DOMINANTE medido en `MF-33-TOP1` —203 de 243 fallos—», una conclusión
  retractada; el check se renombró a `rdkit_energy_strain_proxy`; y el motor declara la
  versión de PoseBusters, porque los umbrales viven en el paquete y una actualización los
  cambiaría sin que el módulo se entere.

  **Defecto de implementación independiente, corregido con prueba unitaria.** Los controles
  no evaluables se detectaban sólo con `v is None`, pero PoseBusters devuelve **NaN**:
  `_empty_results` de `energy_ratio.py` pone `energy_ratio_passes` a `float("nan")` por
  cuatro caminos —sin confórmero, molécula que no sanitiza, **UFF sin parámetros** e InChI
  irreconstruible—, y un ligando con un metal cae ahí con naturalidad. Como `nan` no es
  `None` ni `False`, ese control desaparecía de las tres listas y **una batería incompleta se
  reportaba como CONTROLES SUPERADOS** — justo lo que la frase obligatoria del §6.3 existe
  para impedir. Ahora sólo aprueba un booleano `True`; todo lo demás es `NO_EVALUADO` y se
  nombra en el detalle. Cubierto por `backend/tests/test_pose_physical_validity.py`.

  **CERRADAS EL 2026-08-23 POR `PROD-PV-H-01`**, y en direcciones distintas.

  **Deuda 1 — sin efecto detectable, pero el diseño no tuvo poder para detectarlo.** A vs C
  da **0 discordantes sobre 232**: la representación mixta no produjo ni una falsa
  tranquilidad ni una falsa alarma. La razón honesta no es que sean equivalentes: **las 232
  poses pasan** el control oficial en los dos brazos, así que no hubo un solo caso
  discriminante. El `energy_ratio` oficial va de −20.3 a 19.1 contra un umbral de 100.0, un
  orden de magnitud por debajo del corte. Se puede afirmar que **en esta cohorte** la ruta
  actual no se equivoca; no se puede afirmar equivalencia general.

  **Deuda 2 — el proxy discrepa, y siempre hacia el falso rechazo.** `R3` se dispara con
  **33 de 232 (14.2%)**, y las 33 en la misma dirección: **proxy FALLA donde el oficial
  PASA**. Sus razones en esos casos van de 124.3 a 18 582 565 contra su umbral de 100.0,
  mientras el oficial las sitúa holgadamente dentro de rango. **No puede llamarse
  `internal_energy`** — y por `R4`, que no depende de los datos, tampoco podría aunque
  hubiera coincidido en las 232.

  **Consecuencia de producto, ya aplicada.** La regla estaba preregistrada: un proxy que
  falla donde el oficial canónico pasa demuestra falso rechazo y obliga a que el fallback
  **sólo emita REVISIÓN, nunca FALLA**. Implementado: el escalón 2 devuelve siempre `review`,
  `checks_que_fallan` vacío, y el detalle explica al usuario por qué un valor fuera de rango
  del proxy no es un veredicto. Con prueba de regresión.

  **Hubo que reparar el instrumento antes, y sin eso nada de lo anterior significaría nada.**
  El lector leía las columnas 77-78 del PDBQT como símbolo químico cuando ahí vive el tipo
  AutoDock: cubría **40 de 232**, con el fallo **correlacionado con la aromaticidad**. El
  lector reparado —plantilla química, `index_map` serial→índice, coordenadas por columnas
  fijas, y pseudo-átomos de pegado de macrociclo descartados por tipo— cubre **232/232**, con
  canonicalización 232/232, cero invariantes violadas y desplazamiento pesado 0.0 Å. Esa
  calificación se observó **antes** del sello y se declaró en el prerregistro: no se presenta
  como hallazgo ciego.
- **Procedencia (correcto).** El dossier no llevaba hashes. Añadido `build_provenance` en
  `blockchain/evidence_summary.py`: hash del SMILES, de la configuración y de las poses, con
  los campos ausentes **declarados** en vez de omitidos. Un registro en cadena certifica
  *cuándo* se emitió el documento, no *sobre qué* se calculó.
- **Corrección al auditor: el índice compuesto ya estaba en apéndice.** Vive bajo «Apéndice
  técnico: salidas heredadas» con su descargo, y la cabecera muestra `Estado:`, no el score.
  Auditaron un PDF anterior a los commits del mismo día.
- **Corrección al auditor: «una confianza que ignora eso miente» excede el dato.** `FND-03`
  da `rango_max` = 4.022 Å ✔, pero también **`complejos_con_veredicto_inestable` = 0** en
  `COLOCACION`, con rango mediano 0.71. El ruido entre semillas es real en RMSD y **no volteó
  el veredicto en ninguno de los 33**. Reportar el rango sigue siendo obligatorio; el verbo
  no. Y `FEP-04` topa en **0.600 con cobertura 0.25**, CI95 [0.462, 0.724], no en 0.620.

**Actualización de literatura del 2026-08-22.** Se incorpora la hipótesis de sitio como
objeto auditable del producto y se añaden los diseños `REC-10`, `REC-13`, `REC-14`,
`REC-15` y `PROS-04`. Los cuatro preprints y la *Perspective* de Nature sólo cambian el
backlog, los controles y las preguntas que MolDesign debe medir; no autorizan integrar
métodos ni formular claims sin superar los gates del programa experimental. Ver §3,
§6.3, §11–§14.

**Propósito:** convertir los resultados del programa experimental en decisiones de
producto. Este documento no sustituye los artefactos sellados ni convierte resultados
exploratorios en evidencia confirmatoria. La autoridad científica sigue estando en los
experimentos, en `docs/49_PROGRAMA_EXPERIMENTAL_CIENTIFICO.md`, en
`docs/50_ROADMAP.md` y en `docs/52_PAPER_MF33_ESQUELETO.md`.

Cuando la visión anterior, el README, el diseño visual o el modelo de negocio entren en
conflicto con este mapa, **este documento gobierna la dirección del producto** hasta que
esas superficies sean actualizadas.

---

## 1. Decisión ejecutiva

MolDesign no debe presentarse hoy como una plataforma que descubre fármacos, predice
éxito experimental o decide si una molécula es buena. La evidencia disponible no sostiene
esa promesa.

MolDesign debe convertirse primero en:

> **Un workspace local de cualificación estructural y evidencia de docking. Recibe un
> sistema y una serie pequeña de ligandos; verifica y documenta su preparación, genera y
> contrasta poses, ejecuta controles físicos y de reproducibilidad, se abstiene cuando la
> evidencia no alcanza y exporta un paquete auditable para revisión humana o cálculos
> posteriores.**

La pregunta principal del producto no es:

> “¿Es esta molécula un buen fármaco?”

Es:

> **“¿Qué evidencia computacional produjo esta corrida, qué partes son reproducibles,
> qué supuestos hizo, qué controles superó, qué incertidumbres permanecen y qué sería
> justificable hacer después?”**

Esto no elimina ML, GNN ni drug discovery. Los coloca en su nivel de madurez correcto:
como instrumentos secundarios, trazables y con derecho a abstención, no como la promesa
central del producto.

---

## 2. ¿Cambian el producto los nuevos resultados?

### 2.1 `REC-12-R1 — GO`: sí, cambia la prioridad del producto

`REC-12-R1` es un resultado preregistrado y ejecutado contra la fuente original de RCSB.
Demuestra que la fuente limpiada de PDBBind ocultaba la pregunta: 115/116 estructuras de
RCSB contienen algún `HETATM` no agua/no metal y en 15/116 aparece al menos una especie
no aditiva cerca del ligando cristalográfico que no sobrevive en el receptor preparado.

El resultado **no demuestra que existan quince cofactores funcionales omitidos**. El
desglose encuentra un núcleo robusto de dos —UDP en `1gwv` y GSH en `1lbk`—, once casos
compatibles con ligandos/inhibidores o segundas copias, y dos huecos de clasificación.
Tampoco demuestra que conservar esas especies mejore el docking ni autoriza a modificar
receptores automáticamente.

> **Corrección del 2026-08-22.** Una versión anterior de este párrafo difería esa decisión
> a «la ablación por familia prevista en `REC-05`». **Ese `REC-05` no existe.** El
> prerregistro sellado ese mismo día (`REC-05-PRE`) lo re-alcanzó y declaró antes de correr
> que: **no cubre cofactores** —quedaron fuera por falta de `n`, porque el núcleo robusto de
> `REC-12-R1` son dos complejos—; **no emite reglas por familia** —declarado inalcanzable
> con `CA`=7, `MG`=3, `MN`=3 y `CU`=2, y sólo `ZN`=21 sobrevive como secundario
> descriptivo—; y cubre **únicamente metales, agrupados**, con `n`=29 y un MDE declarado de
> 20.6 puntos porcentuales.

La consecuencia para el producto **no debilita el diseño de este mapa: lo hace permanente.**
No viene ningún experimento a resolver la ambigüedad de cofactores. Por tanto `REVISAR` y la
decisión humana **no son un estado transitorio a la espera de ciencia**: son parte definitiva
del modelo de datos, y deben persistirse, versionarse y viajar en el paquete reproducible
como cualquier otro hecho de la corrida. Diseñar la §6.2 asumiendo que algún día se
automatiza sería construir sobre una promesa que nadie ha hecho.

Sí demuestra algo directamente aplicable al producto:

> **La fuente y las transformaciones de preparación son parte de la evidencia, no un
> detalle interno invisible.**

Por tanto, el producto debe elevar a **P0**:

- identificar y fijar la fuente estructural exacta;
- distinguir estructura depositada, fuente curada/limpiada y receptor ejecutado;
- calcular y mostrar el diff `fuente → preparado`;
- inventariar aguas, metales, aditivos, cofactores candidatos y otros heteroátomos del
  sitio;
- registrar para cada especie si fue preservada, eliminada, transformada o quedó sin
  resolver;
- exigir una decisión humana cuando la clasificación o relevancia sea ambigua;
- incluir esas decisiones, advertencias y hashes en el dossier y el paquete reproducible.

El producto **no** debe añadir un “score de cofactores” ni conservar todos los
heteroátomos por defecto. La salida correcta ante ambigüedad es `REVISAR`.

### 2.2 `REC-11 × REC-09 — GO`: no cambia la política de aguas

`REC-11-CRUCES` está correctamente registrado como **medición descriptiva post-hoc**. Su
`GO` significa que el cruce prometido fue producido, verificado y sellado con su
limitación; no significa que la asociación observada sea una confirmación científica.

El cruce observa que quitar aguas gana en 5/26 complejos con alguna agua bloqueante según
el criterio cristalográfico de `REC-09`, frente a 5/90 sin ella. Sin embargo:

- la tabla fue inspeccionada antes del registro;
- el p-valor es descriptivo y está prohibido usarlo como evidencia confirmatoria;
- cinco de los diez rescates al quitar aguas no tienen ninguna agua bloqueante;
- entre los 18 casos que se movieron, el criterio no predice la dirección;
- el criterio necesita la pose cristalográfica, precisamente desconocida en producción.

La política sigue gobernada por `REC-11`: 94/116 de cobertura con aguas frente a 96/116
sin ellas, `SIN_DIFERENCIA_DETECTABLE`, sin equivalencia y con MDE de 9.92 puntos
porcentuales. **La política se conserva por inercia, no porque haya sido confirmada.**

El impacto de producto es una salvaguarda:

- no convertir “agua bloqueante a 2.6 Å” en regla automática de producción;
- declarar la política de aguas de cada corrida;
- mostrar la presencia, ausencia y transformación de aguas como evidencia y decisión;
- permitir más adelante una comparación húmedo/seco como análisis de sensibilidad
  opcional, nunca como corrección universal;
- llevar al backlog científico un criterio de agua relevante que no dependa de conocer la
  pose nativa.

No deben aparecer en marketing o UI el enriquecimiento `3.46×` ni su p-valor como prueba.

### 2.3 Lectura conjunta

| Resultado | Nivel epistémico | Qué cambia en el producto | Qué no autoriza |
|---|---|---|---|
| `REC-12-R1 — GO` | Resultado preregistrado sobre fuente e inventario | El diff de preparación y la disposición de especies del sitio pasan a P0 | Preservar cofactores automáticamente o afirmar impacto funcional |
| `REC-11 — INCONCLUSIVE` | Comparación preregistrada de docking de novo | La política de aguas queda explícita, limitada y no confirmada | Declarar equivalencia o cambiar globalmente la política |
| `REC-11 × REC-09 — GO` | Medición descriptiva post-hoc | Añade una guardia contra reglas cristal-dependientes y genera una hipótesis | Usar la asociación como evidencia, gate o política automática |

**Conclusión:** estos cierres no cambian el destino general elegido; lo vuelven más
concreto. MolDesign debe controlar la preparación y la procedencia antes de pretender
interpretar el docking.

---

## 3. Usuario inicial, trabajo y valor

### Usuario inicial

La primera audiencia no debe ser “cualquier persona que quiera descubrir un fármaco”. La
hipótesis de entrada es un laboratorio académico, grupo de química medicinal, core
computacional o CRO pequeño que:

- ya trabaja con estructuras y series pequeñas;
- necesita docking o preparar el sistema para cálculos posteriores;
- carece de una forma uniforme de registrar decisiones, controles y versiones;
- pierde tiempo reconstruyendo qué se hizo o explicando por qué una corrida es confiable.

Esta audiencia y su disposición a pagar son **hipótesis comerciales que deben validarse
con pilotos**, no hechos demostrados por los experimentos científicos.

### Trabajo que resuelve

> “Ayúdame a convertir una estructura y una serie de ligandos en una corrida revisable,
> con sus decisiones de preparación, poses, controles, incertidumbres y archivos listos
> para compartir o continuar.”

### Unidad de valor

La unidad ya no es una molécula con una calificación. Es un **caso reproducible**:

`proyecto → revisión del sistema → corrida → poses y controles → decisión humana → paquete`

El PDF es la lectura humana del caso. El ZIP reproducible es su contraparte verificable.
Ninguno sustituye al otro.

### Posicionamiento frente a plataformas de docking automatizado

La automatización integrada ya es una baseline de mercado. FlexAutoDock reúne recuperación
desde PDB/AlphaFold, entradas por SMILES/PubChem/ZINC, selección de cadena, docking ciego o
dirigido, visualización y screening multi-target en un solo flujo
([Ahmed et al., bioRxiv v1](https://www.biorxiv.org/content/10.64898/2026.08.11.744098v1)).

MolDesign debe igualar la conveniencia útil —entrada flexible, preview de cadena/grid,
visualización, Batch y descarga completa— pero no competir por “automatizar más”. Su
diferenciación es **hacer visibles las transformaciones, alternativas, controles y razones
para no confiar**. Una biblioteca de fitoquímicos, una matriz de scores o un flujo de blind
docking no entran al roadmap por existir en un competidor: requieren demanda propia y una
decisión que mejoren.

---

## 4. Flujo rector del producto

```text
CREAR CASO
    ↓
CUALIFICAR SISTEMA Y SERIE
    ↓
RESOLVER O DECLARAR SUPUESTOS
    ↓
EJECUTAR PROTOCOLO VERSIONADO
    ↓
REVISAR TOP-K, ESTABILIDAD Y CONTROLES FÍSICOS
    ↓
DECIDIR: CONTINUAR / REVISAR / ABSTENERSE
    ↓
EXPORTAR DOSSIER + PAQUETE REPRODUCIBLE
```

Una corrida puede finalizar técnicamente y seguir científicamente en `REVISAR` o
`ABSTENERSE`. El producto debe separar siempre:

- **estado de ejecución:** pendiente, ejecutando, completada, fallida;
- **disposición científica:** apta, limitada, abstención;
- **estado de revisión:** sin revisar, revisada, aprobada por una persona.

---

## 5. Modelo de producto y datos

MolDesign necesita dejar de tratar una evaluación aislada como el centro de todo. El
modelo mínimo es:

| Entidad | Responsabilidad |
|---|---|
| **Proyecto/Caso** | Objetivo, target, serie, responsables y contexto |
| **Revisión del sistema** | Fuente exacta, assembly/cadenas, sitio, preparación y decisiones |
| **Hipótesis de sitio** | Candidatos, detector/conformación, ranking, presupuesto inspeccionado, selección y grids derivados |
| **Revisión de ligando** | Identidad, protonación, tautomería, estereoquímica, carga y conformeros |
| **Corrida** | Protocolo, parámetros, semillas, versiones, hardware y logs |
| **Pose** | Coordenadas, rango, energía/model output y procedencia completa |
| **Control** | Regla, versión, resultado, severidad, dominio y evidencia |
| **Decisión humana** | Autor, fecha, justificación y elementos aceptados/rechazados |
| **Paquete** | Manifiesto, hashes, entradas, salidas y verificación de integridad |

La procedencia debe ser navegable en ambos sentidos: desde una conclusión hasta el
artefacto que la sostiene, y desde un artefacto hasta todas las conclusiones que lo usan.

---

## 6. Capacidades que faltan, en orden

### P0 — Producto confiable y utilizable

#### 6.1 Cualificación antes de ejecutar

Crear una fase visible de `Preparación` que no permita esconder decisiones críticas.

**Receptor:**

- identificador, fuente, fecha, hash y licencia/procedencia;
- unidad asimétrica frente a assembly biológica declarada;
- cadenas incluidas y excluidas;
- residuos faltantes y huecos cerca del sitio;
- metales y coordinación;
- aguas y política aplicada;
- cofactores candidatos, aditivos y otros heteroátomos;
- especies del sitio eliminadas durante limpieza o conversión;
- estado de protonación/cargas si puede conocerse;
- definición y justificación del sitio/grid.

**Ligando:**

- identidad química y conservación de estereoquímica;
- tautómero y estado de protonación elegidos;
- carga formal y método de cargas;
- generación de conformeros;
- diferencias entre entrada y forma ejecutada;
- decisiones inferidas por software frente a decisiones confirmadas por una persona.

Cada control debe usar uno de estos estados, no una nota 0–100:

`CONFIRMADO · DECLARADO · INFERIDO · REVISAR · NO EVALUADO · NO APLICA`

#### 6.2 Diff de preparación estructural

Implementar una comparación persistente:

```text
FUENTE DEPOSITADA → FUENTE CURADA/LIMPIADA → RECEPTOR DE EJECUCIÓN
```

La comparación debe responder qué átomos, residuos, cadenas, aguas, metales y
heteroátomos se perdieron o transformaron. `REC-12-R1` convierte esta capacidad en
requisito P0.

Alertas mínimas:

- `FUENTE_LIMPIADA_O_INCOMPLETA`
- `ESPECIE_DEL_SITIO_ELIMINADA`
- `ASSEMBLY_NO_DECLARADA`
- `CADENA_O_HUECO_CERCA_DEL_SITIO`
- `AGUAS_SIN_POLITICA_DECLARADA`
- `COFACTOR_O_HETEROATOMO_POR_REVISAR`
- `FORMA_QUIMICA_DEL_LIGANDO_INFERIDA`

Una alerta no decide por el usuario. Hace visible la decisión pendiente y conserva su
resolución.

**Defecto interno que este diff destapa antes que ninguna estructura externa.** Auditado en
el código el 2026-08-22: existen **tres políticas de heteroátomos distintas, ninguna
declarada al usuario, y la que valida el programa científico no es la que ejecuta el
producto**.

| Ruta | Aguas | Metales | Cofactores orgánicos | Dónde |
|---|---|---|---|---|
| **Dataset experimental** (`data/molflex_train_v2/*/rec.pdbqt`) | conserva **todas** (1788/1788) | conserva **todos** (42/42) | conserva | `docs/51`, medido por `REC-08-EXT` |
| **Producto, docking** (`preparer.py`) | **elimina todas**, sin excepción | **elimina todos** en la práctica | conserva **12 codificados** | `preparer.py:36,232,254,266` |
| **Producto, MM-GBSA** (MolChamb v2) | **elimina todas** | **elimina todos** | **elimina todos** | `molchamb_v2.py:52` |

Tres consecuencias, en orden de gravedad:

1. **`docs/51` describe el pipeline experimental, no el producto.** La política declarada
   —«se conservan todas las aguas cristalográficas, sin excepción»— es cierta de
   `molflex_train_v2` y **falsa de `preparer.py`**, que las elimina en la línea 232 antes de
   cualquier otro filtro. Todo el programa —`REC-08-EXT`, `REC-09`, `REC-11`, la serie
   `MF-33`— se midió sobre receptores que **el producto no genera**.
2. **Los metales se pierden por una puerta que nadie abrió.** El código declara conservarlos
   (`preparer.py:426`, «v1.8: Conservar cofactores (metales, grupos prostéticos) para docking
   realista»), pero un metal sólo sobrevive si el target lo declara en `cofactors_whitelist`,
   y **ese campo está vacío en los 387 targets de `curated_targets.json`**. El resultado es
   que la intención escrita y el comportamiento real se contradicen: hoy se elimina el 100%
   de los metales, incluidos los catalíticos de las metaloenzimas.
3. **La lista positiva de cofactores existe pero es corta y está codificada**: `HEM`, `HEC`,
   `FAD`, `NAD`, `NAP`, `FMN`, `ATP`, `ADP`, `SAM`, `SF4`, `FES`, `F3S`. **No incluye `UDP`
   ni `GSH`** — exactamente los dos que `REC-12-R1` identificó como núcleo robusto. Los dos
   únicos cofactores funcionales que el programa ha demostrado que se pierden son también
   los dos que el producto descartaría.

Cualquier comparación entre una energía MM-GBSA y un score de docking se está haciendo hoy
sobre sistemas distintos, y cualquier extrapolación de un resultado experimental al producto
cruza una frontera de preparación no declarada. **El diff `fuente → preparado` debe
calcularse por ruta de ejecución, no una sola vez por caso**, y la política de cada ruta debe
declararse junto a su resultado.

**Tampoco existe una lista de cofactores.** Lo que hay en el repo son listas de *exclusión*
—`NON_DRUG_HETATMS` y `CATALYTIC_METALS` en `services/chemistry/protein_surgery.py`—, y su
propósito es localizar el centroide del sitio, no decidir qué se conserva. «Cofactor» está
definido en negativo: *HETATM que no está en la lista de exclusión*. Ésa es exactamente la
razón de que el 15 de `REC-12-R1` sea una cota superior y no un recuento.

Consecuencia de diseño: la clasificación de especies del sitio necesita **una lista positiva
curada** —`NAD`, `FAD`, `HEM`, `SAM`, `ATP`, `GSH`, `UDP`, `PLP`, `COA`…— además de la de
exclusión, y ambas deben ser **datos versionados del producto, no constantes en el código**,
porque van a cambiar y cada cambio reclasifica corridas ya emitidas.

> Nota para el registro científico: `NON_DRUG_HETATMS` ya cubre `CL`, `NA`, `DMF`, `ACE`,
> `GLC` y `NAG`, que son justamente los que la lista `ADITIVOS` de `REC-12-R1` no cubría y
> que produjeron sus dos «huecos de clasificación». La lista del producto está **mejor
> curada** que la del experimento. Eso no se corrige hacia atrás —el prerregistro prohíbe
> mover la lista después de mirar— pero es el punto de partida de cualquier prerregistro
> futuro sobre especies del sitio.

#### 6.3 Cualificación de la hipótesis de sitio

El producto no debe convertir el top-1 de un detector en “el sitio de unión”, especialmente
en una estructura APO. Debe persistir una o más `SiteHypothesis` y declarar si cada una
proviene de:

- ligando co-cristalizado;
- anotación experimental o curación humana;
- selección manual del usuario;
- MolPocket u otro detector sobre una estructura estática;
- detector sobre un ensemble conformacional;
- template estructural recuperado.

Por candidato deben viajar:

- estructura/conformación exacta y su hash;
- detector, versión, configuración y licencia/procedencia;
- centro, tamaño, residuos y grid derivado;
- posición dentro del ranking y métricas crudas, sin convertirlas en probabilidad;
- número total de candidatos generados y candidate budget realmente inspeccionado;
- acuerdo o desacuerdo con otros detectores;
- persona o regla que lo seleccionó y su justificación;
- estado `CONFIRMADO · DECLARADO · INFERIDO · REVISAR · ABSTENERSE`.

La interfaz de Evaluación debe mostrar top-K hipótesis comparables y permitir confirmar,
rechazar o conservar varias. Si el sitio solo fue inferido, el target no puede aparecer como
“estructuralmente cualificado” sin esa limitación.

La motivación externa separa **cobertura** —el candidato correcto fue generado— de
**conversión** —el ranking logró colocarlo dentro del presupuesto útil— y muestra que unir
detectores puede aumentar el oráculo sin ayudar cuando compiten demasiados candidatos
([Moore, bioRxiv v1](https://www.biorxiv.org/content/10.64898/2026.08.11.743381v1);
[Lacuna, código y benchmarks](https://github.com/mooreneural/lacuna)). En MolDesign esta
observación es una hipótesis que gobiernan `REC-10` y `REC-13`, no una regla importada.

Decisión vigente hasta esos resultados:

- MolPocket top-1 es `INFERIDO`, nunca `CONFIRMADO` por sí mismo;
- conservar y mostrar top-K es una mejora de transparencia autorizada;
- cambiar automáticamente de detector, combinar candidatos o ejecutar varios grids sigue
  detrás de experimento;
- el dossier debe declarar qué candidatos quedaron fuera por presupuesto.

#### 6.4 Validación física de poses

Integrar una capa tipo PoseBusters o equivalente con resultados por pose:

- choques y geometría intermolecular;
- enlaces, valencias, aromaticidad y planicidad;
- geometría intramolecular;
- consistencia de identidades y coordenadas;
- checks no evaluables marcados explícitamente.

La frase obligatoria mientras no exista una evaluación debe ser:

> “Ausencia de alertas no significa ausencia de choques, enlaces imposibles o artefactos
> de preparación.”

El control físico es una dimensión de evidencia; no se mezcla con afinidad o ADME en una
media global.

#### 6.5 Dossier de evidencia

La pestaña Evaluación y el PDF deben organizarse alrededor de:

1. identidad del caso y objetivo declarado;
2. entradas, fuentes y hashes;
3. decisiones de preparación;
4. hipótesis de sitio, candidatos considerados, candidate budget y selección;
5. protocolo y entorno ejecutado;
6. poses, top-K y comparación;
7. controles físicos y de reproducibilidad;
8. evidencia por dimensión;
9. supuestos e incertidumbres;
10. razones de abstención;
11. siguiente acción justificable;
12. apéndice de outputs heredados, claramente marcado como no decisional.

Los índices 0–100 no deben ser la jerarquía principal ni parecer probabilidad. Si se
conservan temporalmente por compatibilidad, deben vivir en un apéndice heredado con
fórmula, versión y advertencia.

#### 6.6 Paquete reproducible

Exportar, importar y verificar un paquete que contenga como mínimo:

- entradas originales y preparadas;
- todas las poses relevantes, no solo la elegida;
- parámetros, semillas y versiones;
- resultados de controles;
- logs y fallos;
- decisiones humanas;
- manifiesto y hashes;
- PDF/HTML de lectura;
- comando o receta de reproducción.

El criterio de salida es que una tercera persona pueda reconstruir qué se ejecutó y
detectar cualquier archivo ausente o modificado.

#### 6.7 Eliminar autoridad científica indebida

Revisar todas las superficies que todavía presentan:

- `GLOBAL SCORE`, nota total o ranking universal;
- “seguro”, “viable”, “regulatorio” o “margen terapéutico” sin validación;
- MM/GBSA como energía libre experimental;
- cambios de score como superioridad química;
- atributos XAI como mecanismos causales;
- GNN/IA como garantía de descubrimiento.

La interfaz debe distinguir dato observado, output de modelo, inferencia y decisión.

### P1 — Profundidad científica y operación en cohortes

#### 6.8 Revisión de poses y estabilidad

- mostrar top-K en vez de una única pose soberana;
- repetir semillas cuando el protocolo lo requiera;
- agrupar poses por similitud;
- comparar pose, score, controles y estabilidad entre repeticiones;
- expresar desacuerdo e incertidumbre;
- permitir abstención por falta de estabilidad o validez física.

#### 6.9 Batch como evidencia de cohorte

Batch no se elimina. Evoluciona de “muchas evaluaciones y sus scores” a:

- aplicar un protocolo versionado a una cohorte;
- comprobar comparabilidad entre sistemas y ligandos;
- resumir hipótesis de sitio confirmadas, inferidas, discordantes y no resueltas;
- resumir cobertura, fallos, controles y abstenciones;
- detectar excepciones de preparación;
- revisar casos discordantes;
- exportar un dossier de cohorte y paquetes individuales.

No debe ordenar moléculas por un índice compuesto universal. Puede filtrar por estados de
evidencia, controles, dominio, incertidumbre y decisión humana.

#### 6.10 Readiness estructural del target

Separar al menos:

1. **disponible:** hay una estructura;
2. **dock-ready:** el pipeline puede ejecutarla;
3. **estructuralmente cualificada:** fuente, `SiteHypothesis`, assembly, huecos y especies
   relevantes fueron revisados; un top-1 automático no basta;
4. **transfer-ready:** el sistema y sus decisiones pueden reproducirse o enviarse al
   cálculo posterior.

El estado actual basado solo en receptor preparado, grid y hotspots equivale como máximo a
`dock-ready`.

#### 6.11 Gobernanza de modelos

Todo output de ML/GNN debe declarar:

- tarea exacta;
- contexto de uso y decisión concreta que pretende apoyar;
- qué evidencia consume y qué no permite concluir;
- versión y dataset;
- nivel de madurez `E0–E6`;
- dominio de aplicabilidad;
- incertidumbre/cobertura si existe;
- fallback y condición de abstención;
- si participa en una decisión o corre solo en shadow mode.

Un modelo no asciende por mejorar una métrica interna. Solo una evaluación sellada contra
su gate puede cambiar su rol en producto. La evaluación debe demostrar que mejora una
decisión dentro de su contexto, no solo que mejora un benchmark. Esta regla coincide con la
recomendación de pasar de validación de modelos a impacto decisional de
[Bender et al., Nature Reviews Drug Discovery](https://www.nature.com/articles/s41573-026-01496-2),
pero su evidencia para MolDesign la debe producir `PROS-04`.

### P2 — Extensión después de validar el núcleo

- asistente MolChat que cite artefactos y nunca invente procedencia;
- protocolos y preparaciones de targets compartibles en Comunidad;
- recuperación de precedentes estructurales para una `SiteHypothesis`, con LEN-Seek o
  baseline equivalente, solo en shadow hasta que `REC-14` mida valor downstream
  ([preprint](https://www.biorxiv.org/content/10.64898/2026.08.14.744759v1),
  [código](https://github.com/arsenide33/LEN-Seek));
- handoff explícito a FEP+, MD u otros cálculos posteriores;
- exportación/importación de evidencia dinámica; GaMD permanece como cálculo externo P2 y
  no como “validador de pose” hasta `REC-15`
  ([preprint](https://www.biorxiv.org/content/10.64898/2026.08.10.743837v1),
  [fork de GROMACS-GaMD](https://github.com/math-diff/gromacs-gamd));
- comparación de variantes/resistencia cuando los experimentos lo sostengan;
- automatización mayor solo en decisiones que ya tengan evidencia de producción.

---

## 7. Alineación de las pestañas actuales

No hace falta destruir la aplicación. Hace falta cambiar la jerarquía y el significado de
sus superficies.

| Pestaña actual | Destino | Cambio principal |
|---|---|---|
| **Evaluación** | Centro del producto | Convertirla en `Preparar → cualificar sitio → Ejecutar → Revisar → Exportar`; mostrar top-K hipótesis y el dossier robusto |
| **Batch** | Se conserva | Cohortes comparables, hipótesis de sitio, cobertura, controles, excepciones y abstenciones; no ranking por score global |
| **Moldex** | Evoluciona a Casos/Proyectos | Objetivo, sistema, revisiones, serie, corridas y entregables |
| **Historial** | Evoluciona a Corridas | Procedencia, estados, diffs, comparación y reproducción; no “mejor score” como resumen |
| **Comunidad** | Se pospone/reorienta | Protocolos, targets cualificados y casos reproducibles; eliminar leaderboard científico |
| **Ciencia** | Se conserva | Registro de evidencia, experimentos, madurez y relación experimento → decisión de producto |

No se recomienda una pestaña principal independiente llamada `Informe`. El informe no es
otro flujo: es un **artefacto versionado de una corrida o un caso**, accesible desde
Evaluación, Batch, Moldex e Historial.

---

## 8. Qué no construir ahora

Hasta cerrar P0 no se debe dedicar el ciclo principal a:

- otro score compuesto o una nueva GNN generalista;
- un recomendador universal de “mejor fármaco”;
- convertir automáticamente el pocket top-1 de una estructura APO en sitio confirmado;
- unir detectores o ejecutar múltiples grids por defecto antes de `REC-10/REC-13`;
- una regla automática para conservar/eliminar aguas basada en la pose cristalográfica;
- retener automáticamente cualquier `HETATM` llamado cofactor;
- claims de seguridad, eficacia, viabilidad clínica o aprobación regulatoria;
- comparar o combinar una energía MM-GBSA con un score de docking mientras las dos rutas
  preparen el receptor con políticas de heteroátomos distintas y sin declarar (§6.2): no son
  el mismo sistema, y la diferencia no es atribuible a química;
- blockchain como sustituto de hashes, manifiestos y reproducibilidad;
- una copia generalista de FlexAutoDock o una biblioteca de fitoquímicos sin validar demanda;
- una pestaña de GaMD/MD o un claim de “pose estable = pose correcta”;
- reemplazar motores especializados de FEP/MD;
- ampliar Comunidad antes de que exista una unidad compartible científicamente seria.

El ML existente puede mantenerse, medirse y mejorarse cuando desbloquee una decisión del
flujo rector. No debe dirigir la propuesta de valor mientras siga por debajo de sus gates
o carezca de calibración y dominio de aplicabilidad.

---

## 9. Camino de entrega por hitos

Los hitos se cierran por criterio de salida, no por cantidad de features.

### Hito 0 — Verdad de producto

**Objetivo:** alinear discurso, navegación y contratos.

**Salida:** este mapa adoptado; inventario de claims incompatibles; glosario de estados;
modelo de `Caso/Revisión/SiteHypothesis/Corrida/Control/Decisión/Paquete` aprobado.

### Hito 1 — Cualificación MVP

**Objetivo:** hacer visible lo que entra y lo que cambia antes del docking.

**Salida:** fuente y hashes; diff fuente→preparado; inventario del sitio; top-K
`SiteHypothesis` con origen y estado; decisiones de aguas/cofactores/metales; revisión de
forma química del ligando; bloqueos y abstención.

### Hito 2 — Corrida de evidencia

**Objetivo:** que Evaluación produzca una hipótesis estructural revisable.

**Salida:** protocolo versionado; hipótesis de sitio elegida y alternativas; top-K de
poses; semillas/repeticiones necesarias; PoseBusters; matriz de evidencia; incertidumbres;
siguiente acción; dossier sin score soberano.

### Hito 3 — Reproducción y transferencia

**Objetivo:** que el resultado sobreviva fuera de la sesión y de la máquina original.

**Salida:** paquete exportable/importable; verificación de integridad; reconstrucción por
tercero; handoff documentado a cálculos posteriores. Debe enlazarse al objetivo `FEP-06`.

### Hito 4 — Batch serio

**Objetivo:** operar series sin perder comparabilidad ni excepciones.

**Salida:** protocolo de cohorte; preflight masivo; resumen de hipótesis de sitio,
cobertura/fallos/abstención; casos discordantes; exportación de cohorte.

### Hito 5 — Primer piloto externo

**Objetivo:** validar utilidad, lenguaje y disposición a pagar con trabajo real.

**Salida:** ejecutar `PROS-04`: un laboratorio externo entrega una estructura y una serie
pequeña; casos asignados sin contaminación entre un reporte automatizado básico y el dossier
MolDesign; adjudicación independiente de defectos y decisiones; un segundo investigador
entiende/reproduce el paquete. Se documentan calidad de decisión, tiempo, errores evitados y
voluntad de repetir/pagar.

No se considera validación comercial que el equipo interno valore el dossier, ni que el
usuario prefiera su diseño si no mejora decisiones o reproducibilidad.

---

## 10. Métrica norte y criterios de éxito

La métrica norte no debe ser el promedio del score molecular. Debe medir casos útiles y
auditables:

> **Porcentaje de casos entregados con preparación y sitio cualificados, procedencia
> completa, controles ejecutados o declarados como no evaluables, disposición científica
> explícita y paquete cuya integridad puede verificarse.**

Métricas auxiliares:

- proporción de decisiones de preparación resueltas frente a inferidas;
- proporción de casos con sitio confirmado, inferido, discordante o abstención;
- candidate budget inspeccionado y candidatos excluidos por presupuesto;
- proporción de corridas con procedencia completa de pose;
- cobertura y abstención de cada modelo dentro de su dominio;
- tasa de fallos recuperables y tiempo hasta diagnóstico;
- reproducibilidad por un tercero;
- tiempo desde entrada hasta dossier revisable;
- número de decisiones o defectos relevantes detectados antes de cálculos costosos;
- mejora decisional frente a una baseline automatizada, adjudicada externamente;
- repetición de uso por el usuario externo.

---

## 11. Regla experimento → producto

Para evitar que cada resultado nuevo cambie el producto de manera oportunista:

1. Un resultado **post-hoc** puede generar hipótesis, guardas y nuevas mediciones; no crea
   una regla automática ni un claim.
2. Un experimento preregistrado que pasa su gate puede cambiar una capacidad o política
   solo dentro del alcance exacto medido.
3. `GO` significa que debe leerse la razón de decisión. No tiene el mismo contenido
   epistemológico en todos los artefactos.
4. Una observación de existencia o pérdida no demuestra relevancia funcional.
5. Un resultado `SIN_DIFERENCIA_DETECTABLE` no demuestra equivalencia.
6. La automatización exige validación fuera de muestra, dominio de aplicabilidad,
   trazabilidad y fallback.
7. Si la evidencia no alcanza, el comportamiento correcto del producto es declarar la
   incertidumbre o abstenerse.
8. Un preprint o Perspective puede cambiar el backlog, el modelo de datos o una salvaguarda;
   no promueve un algoritmo a producción sin experimento propio.

### 11bis. Regla producción → experimento

**La §11 es una válvula de un solo sentido, y el 2026-08-23 quedó claro que hace falta la
inversa.** Producción no es sólo el destinatario de la evidencia: en varios puntos **sabe más
que el lado científico**, porque acumuló curación que ningún experimento produjo. Ignorarlo
hace que la ciencia reinvente peor lo que ya existe curado.

Cuatro casos medidos ese mismo día:

| Lo que producción tiene | Y el lado científico |
|---|---|
| `NON_DRUG_HETATMS` en `protein_surgery.py` — aditivos, tampones, glicanos, crioprotectores | La lista `ADITIVOS` de `REC-12-R1` **no cubría** `CL`, `DMF`, `ACE`, `GLC` ni `NAG`, y por eso su cifra de 15 quedó como cota superior |
| Lista positiva de cofactores en `preparer.py` (`HEM`, `NAD`, `FAD`, `FMN`, `ATP`, `SAM`, clusters Fe-S) | **No existía.** `PREP-01` midió que por eso el producto pierde **5** cofactores conocidos frente a los **8** del dataset experimental |
| `fetch_target_cofactors_from_rcsb`, que detecta cofactores desde la fuente original | No hay equivalente; `REC-12-R1` tuvo que descargar los 116 a mano |
| Catálogo de cadena y grid por target, 387 dianas curadas | No hay equivalente |

**La regla, simétrica a la §11:**

1. Una lista, umbral o heurística curada en producción es **material de partida legítimo**
   para un prerregistro, y debe citarse como tal en lugar de reconstruirse peor.
2. Adoptarla **no la valida**: sigue necesitando su gate. Que esté en producción no es
   evidencia de que sea correcta, sólo de que alguien la curó.
3. Un experimento que reconstruye desde cero algo que producción ya tiene **debe declarar por
   qué** — puede haber una razón buena, como no contaminar una comparación, pero tiene que
   estar escrita.
4. Cuando las dos difieren, **la diferencia es el hallazgo**, no un detalle a reconciliar en
   silencio. `PREP-01` existe exactamente por eso.
5. Lo que **no** viaja en esta dirección: los claims. Que producción afirme algo no lo
   convierte en hipótesis con respaldo.

Aplicado a los cierres actuales:

- `REC-12-R1` autoriza construir el **control de fuente y diff de preparación**;
- `REC-12-R1` **no autoriza corregir receptores, y no hay experimento pendiente que llegue a
  autorizarlo**: `REC-05` fue re-alcanzado a metales agrupados y dejó los cofactores fuera
  por `n`=2 (§2.1). La corrección automática de receptores no tiene ruta científica abierta;
  la vía correcta es la decisión humana registrada;
- `REC-05`, cuando cierre, sólo podrá cambiar la política de **metales**, sobre los 29
  complejos que los tienen y con un MDE de 20.6 pp. No dice nada de los otros 87 ni de los
  cofactores, y su prerregistro prohíbe emitir reglas para `CA`, `MG`, `MN` o `CU`;
- `REC-11-CRUCES` autoriza registrar una **hipótesis de criterio pose-blind de aguas**;
- `REC-11-CRUCES` no autoriza cambiar la política ni el comportamiento de producción.

Aplicado a la revisión externa del 2026-08-22:

- la separación cobertura/conversión autoriza que el producto conserve top-K y etiquete
  MolPocket top-1 como `INFERIDO`; `REC-10` decide el ranking y `REC-13` cualquier consenso;
- LEN-Seek solo puede aparecer en shadow como precedente estructural hasta `REC-14`; similitud
  de sitio no transfiere automáticamente ligando, función ni relevancia;
- GaMD es un handoff P2 y no un control de validez de pose; `REC-15` debe demostrar valor a
  costo igualado y entre réplicas;
- FlexAutoDock fija una baseline de conveniencia; no justifica copiar su catálogo ni tratar
  scores como afinidad;
- la recomendación de evaluar impacto en decisiones se instrumenta con `PROS-04`, no como
  claim de que MolDesign ya lo logra.

---

## 12. Backlog inmediato recomendado

Orden de implementación:

1. formalizar el esquema de `Proyecto`, `SystemRevision`, `SiteHypothesis`, `Run`,
   `ControlResult`, `HumanDecision` y `ArtifactPackage`;
2. crear un preflight de receptor/ligando que no ejecute docking;
3. persistir fuente, hashes y diff fuente→preparado, **calculado por ruta de ejecución**, y
   declarar junto a cada resultado qué política de heteroátomos aplicó su ruta — hoy docking
   y MM-GBSA aplican políticas opuestas sin declararlo (§6.2);
4. añadir en Evaluación el panel de cualificación y decisiones pendientes;
5. persistir y mostrar top-K `SiteHypothesis`, candidate budget, selección y grids derivados,
   sin cambiar todavía el detector de producción;
6. integrar PoseBusters por pose con estados `pasa/falla/no evaluado` — **hecho el
   2026-08-22** en `services/chemistry/pose_physical_validity.py`; falta cablearlo al
   pipeline de evaluación para que rellene `eval_result.pose_validation`, que el resumen de
   evidencia ya consume;
7. completar top-K, comparación de poses y estabilidad entre semillas;
8. exportar/importar/verificar el paquete reproducible;
9. retirar score global y claims no sostenidos de Home, Moldex, Historial, Comunidad y
   paneles secundarios de Evaluación;
10. reconstruir Batch sobre casos, protocolos, hipótesis de sitio, controles y abstenciones;
11. ejecutar `REC-10`; dejar consenso (`REC-13`), LEN-Seek (`REC-14`) y GaMD (`REC-15`)
    detrás de sus gates;
12. ejecutar `PROS-04` con el primer piloto externo y conectar su criterio de salida con
    `FEP-06`.

El siguiente bloque de trabajo debe comenzar por los puntos 1–4. PoseBusters es esencial,
pero validar una pose sobre una preparación opaca dejaría intacto el riesgo que
`REC-12-R1` acaba de demostrar.

---

## 13. Definición de “producto completo” para esta etapa

MolDesign alcanza una primera versión completa, funcional y seria cuando una persona
puede:

1. crear un caso e importar receptor y serie;
2. conocer la fuente exacta y todo cambio introducido por la preparación;
3. resolver o declarar assembly, cadenas, huecos, aguas, metales, cofactores y forma
   química de ligandos;
4. inspeccionar hipótesis alternativas de sitio, conocer su origen y confirmar, limitar o
   rechazar la seleccionada;
5. ejecutar un protocolo versionado y reproducible;
6. inspeccionar top-K de poses, estabilidad y controles físicos;
7. distinguir hechos, outputs de modelo, inferencias y decisiones;
8. aceptar, limitar o abstenerse con justificación;
9. exportar un dossier legible y un paquete verificable;
10. entregar el paquete a un tercero que pueda reconstruir la corrida;
11. continuar a un cálculo posterior sin que MolDesign afirme más de lo demostrado.

Ese producto es más estrecho que la visión original, pero también es más útil, defendible
y vendible como hipótesis. La expansión hacia selección molecular, ML/GNN decisional y
drug discovery debe ocurrir después, acumulando evidencia sobre esta base.

---

## 14. Fuentes principales de esta decisión

- `docs/46_RUNTIME_INVENTORY.md`
- `docs/49_PROGRAMA_EXPERIMENTAL_CIENTIFICO.md`
- `docs/50_ROADMAP.md`
- `docs/51_POLITICA_DE_AGUAS.md`
- `docs/52_PAPER_MF33_ESQUELETO.md`
- `docs/papers/FEP-01.md` y `docs/papers/FEP-01-EXT.md`
- `docs/papers/FEP-02.md` y `docs/papers/FEP-02-EXT.md`
- `docs/papers/FEP-04.md`
- `docs/papers/FND-06.md`
- `scripts/artifacts_science/REC-09/`
- `scripts/artifacts_science/REC-11/`
- `scripts/artifacts_science/REC-11-CRUCES/`
- `scripts/artifacts_science/REC-12-R1/`
- `scripts/artifacts_science/REC-05-PRE/` — el re-alcance a metales y sus exclusiones
- `backend/services/chemistry/molchamb_v2.py` y `services/chemistry/protein_surgery.py` —
  auditados el 2026-08-22 para el defecto de doble política de heteroátomos (§6.2)

### Fuentes externas — revisión del 2026-08-22

- [Moore, *Cryptic binding sites are detected but not ranked: coverage, conversion, and detector consensus*, bioRxiv v1](https://www.biorxiv.org/content/10.64898/2026.08.11.743381v1)
- [Lacuna — código y benchmarks de cobertura/conversión](https://github.com/mooreneural/lacuna)
- [Yeo et al., *LEN-Seek: Fast and scalable ligand binding-site similarity search*, bioRxiv v1](https://www.biorxiv.org/content/10.64898/2026.08.14.744759v1)
- [LEN-Seek — repositorio de los autores](https://github.com/arsenide33/LEN-Seek)
- [Ahmed et al., *FlexAutoDock*, bioRxiv v1](https://www.biorxiv.org/content/10.64898/2026.08.11.744098v1)
- [Yang, *Gaussian Accelerated Molecular Dynamics in GROMACS*, bioRxiv v1](https://www.biorxiv.org/content/10.64898/2026.08.10.743837v1)
- [GROMACS-GaMD — fork del trabajo](https://github.com/math-diff/gromacs-gamd)
- [Bender et al., *Artificial intelligence in drug discovery — what it is, where we stand and the path forward*, Nature Reviews Drug Discovery](https://www.nature.com/articles/s41573-026-01496-2)
