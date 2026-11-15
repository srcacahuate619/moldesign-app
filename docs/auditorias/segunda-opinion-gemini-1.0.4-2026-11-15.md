# Segunda opinión sobre las decisiones abiertas de MolDesign 1.0.4

15 de noviembre de 2026, fecha local. **Autor:** `gemini 4 hydrogen`.  
**Base del repositorio inspeccionada:** `7190fe009bb5f1cc675613af3ec9300f93e87df3` (árbol de trabajo local con cambios previos sin commitear en [decisiones-pendientes-1.0.4-2026-11-14.md](decisiones-pendientes-1.0.4-2026-11-14.md), `segunda-opinion-1.0.4-2026-11-15.md` (encargo incompleto, eliminado) y `frontend/next-env.d.ts`). Este documento deja constancia íntegra y auditable de la segunda opinión solicitada para revisión del equipo, bajo una metodología estrictamente basada en evidencias.

> **Nota de ubicación (2026-11-15).** El archivo se escribió dentro de `investigacion-1.0.4/` y se movió aquí porque el manifiesto de esa carpeta hashea todos sus ficheros. Sólo se ajustaron los enlaces relativos; el texto es el de su autor. Su revisión, punto por punto, está en el commit `ffddd7e9`.

> **Alcance.** Esta segunda opinión evalúa las cinco cuestiones abiertas sin modificar código ni sobrescribir fichas previas. Para [D-09](investigacion-1.0.4/D09-revision-humana.md) se auditó tanto la muestra ciega de 12 dianas (contra las coordenadas locales, `SEQADV`, metales y fuentes primarias) como la gobernanza completa de las 23 promociones preliminares de [D09-adjudicacion.json](investigacion-1.0.4/D09-adjudicacion.json).

---

## Cómo se comprobó y límites de esta revisión

### Verificaciones ejecutadas en esta sesión

1. **Integridad del manifiesto y sellos locales** (con `python-embed/python.exe -B -I` para no crear `__pycache__`):
   - `manifiesto.py --comprobar`: **136** SHA-256 comprobados o registrados sin error.
   - `comprobar_sellos.py --check`: **14** experimentos sellados (`0` sin sellar), **4 034** ficheros verificados, `0` distintos y `0` ausentes.
   - `medir_d09.py`, `comprobar_d04_banda.py`, `comprobar_d07_molchat.py` y `scripts/check_docs_links.py --check`: todos finalizaron con código `0`.
2. **Inspección directa de datos estructurales y JSONs:**
   - Recuentos del panel y redocking en [anti_dianas_bowes44.json](../../backend/data/anti_dianas_bowes44.json), [curated_targets.json](../../curated_targets.json), [D09-adjudicacion.json](investigacion-1.0.4/D09-adjudicacion.json) y [D09-geometria.json](investigacion-1.0.4/D09-geometria.json).
   - Lectura directa de átomos `ATOM`/`HETATM`, ligandos, centroides, contactos a `<= 4,5 Å`, metales cercanos (`<= 10 Å`), distancias inter-sitio y registros `SEQADV` sobre los archivos comprimidos locales `data/targets/<PDB>.pdb.gz` de los 12 casos muestreados, más barrido de `SEQADV` y `redock` sobre las 23 promociones propuestas.
3. **Inspección directa de código fuente y textos vigentes:** lectura línea a línea de [prediccion.py](../../backend/services/targets/prediccion.py), [preparacion_confianza.py](../../backend/services/dossier/preparacion_confianza.py), [i18n_receptores_propios.py](../../backend/core/i18n_receptores_propios.py), [bloques_protocolo.py](../../backend/services/dossier/bloques_protocolo.py), [i18n_catalog.py](../../backend/core/i18n_catalog.py), [ejecucion.py](../../backend/services/pipeline/protocols/m5/ejecucion.py), [queue_handler.py](../../backend/services/docking/queue_handler.py), [runner.py](../../backend/services/pipeline/runner.py), [selectivity.py](../../backend/services/docking/selectivity.py), [selectividad_margen.py](../../backend/services/docking/selectividad_margen.py), [pdf_generator.py](../../backend/services/blockchain/pdf_generator.py), [model.py](../../backend/services/dossier/model.py), [interpreter.py](../../backend/services/evaluation/interpreter.py), [batch.py](../../backend/api/routers/batch.py), [history.py](../../backend/api/routers/history.py), [ProSelectivityPanel.tsx](../../frontend/components/interfaces/pro/ProSelectivityPanel.tsx), [pro.ts](../../frontend/context/traducciones/pro.ts), [resultFieldPresentation.ts](../../frontend/lib/resultFieldPresentation.ts), [OptionsMenu.tsx](../../frontend/components/ui/OptionsMenu.tsx), `SARTable.tsx` (retirado en 1.0.4, B-6), `CommunityPanel.tsx` (retirado en 1.0.4, B-6) y [history/page.tsx](../../frontend/app/history/page.tsx).
4. **Comprobación experimental de SMARTS en RDKit:** ejecución directa con `./python-embed/python.exe -B` sobre los `17` positivos de control de `CORRECTAS_VERIFICADAS`, las `5` entradas de `AMINAS_CON_ATRACTOR_ACOPLADAS`, `10` controles negativos dirigidos (incluyendo zwitteriones y β-aminoéster) y `11` sondas positivas protonadas.
5. **Contrastes de fuentes primarias:** referencias identificadas por `PMID` o `DOI` (salvo fuentes de patrocinador ya verificadas en el dossier, como el expediente sNDA `20-839/S-019` ante FDA para clopidogrel).

### Límites explícitos (qué no se ejecutó)

- No se ejecutaron corridas nuevas de AutoDock Vina, Chai-1 ni PoseBusters; se auditó la evidencia almacenada y las coordenadas PDB ya descargadas.
- No se corrió la suite completa de `pytest` ni pruebas end-to-end de Playwright; la comprobación funcional en memoria se limitó a los scripts de verificación citados y a la batería RDKit de SMARTS.
- Fuera de las 12 dianas muestreadas en [D09-revision-humana.md](investigacion-1.0.4/D09-revision-humana.md), las otras filas del Bowes-44 no recibieron revisión bibliográfica completa fila a fila; sí se verificaron automáticamente sus métricas `redock` y mutaciones `SEQADV`.

---

## Resumen ejecutivo de dictámenes

| Frente | Prioridad | Veredicto independiente | Hallazgo principal |
|---|---|---|---|
| **1. D-09 · Antidianas y muestra Bowes-44** | **Alta** | **Bloquear la promoción en bloque** | Las 4 sesiones evaluadoras usaron el mismo modelo (`gpt-6.1-sol`); **11 de las 23 promociones propuestas fallan el redocking nativo** (`rmsd_pose1_A` hasta `9,15 Å`), incluida **`4C3F` (`Lck`)** que porta la mutación inactiva **`D364N`** (`SEQADV`) y falla `redock` por `5,97 Å`. |
| **2. Textos nuevos (4 frentes)** | **Alta, barata** | **Corregir texto + 4 defectos de código** | El aviso de sitio no adjudicado usa `<` en backend vs `<=` en frontend y **desaparece del PDF/dossier e i18n backend**; `druglikeness_score` en UI sigue diciendo «de reglas» sin «heredado»; la nota UMS = 0 omite que evalúa `molecule_smiles` crudo; Chai-1 conserva jerga cruda y detector lábil si todos los B son iguales. |
| **3. D-01 · Chai-1 `pLDDT < 70` (Cα vs media)** | **Media** | **Mantener Cα + señal dual de cadena lateral** | En las 15 muestras `{Cα < 70} ⊂ {media < 70}` (`solo_local_bajo70 == 0`), y `0/25` (NET) y `0/23` (CDK2) residuos del sitio caen `< 70` bajo ambas lecturas; los casos medidos no deciden la cuestión sin una cohorte con sitios límite flexibles. |
| **4. D-04 · Aminas alifáticas y pKa** | **Media** | **Conservar `9,8`; ampliar `especie_en_revision.py`** | Bajar `9,8 → 8,3` da **0** mejora neta en estado de carga a pH 7,4 (`139/193` en ambos casos) y sesga aminas simples (`S1`); lo prioritario es marcar α-aminoésteres, α-aminocetonas/aldehídos, morfolinas/oxetanos bis-β cíclicos, propargilaminas y β-sulfonas (sin falsos positivos en zwitteriones ni monofluoroaminas). |
| **5. D-07 · Orden de exportación en Lotes** | **Baja** | **Retirar `total_score` de `_orden_exportado`** | `_orden_exportado` sigue ordenando por `total_score` (`batch.py`, L448), aunque `ef_metrics` ya conmuta a `affinity_score` en firmas mixtas (`L801`). Ordenar por validez → diana → `affinity_kcal` ascendente → `row_id`. |

---

## 1. D-09 · Gobernanza y muestra humana de Bowes-44 (`Alta`)

### 1.1 Auditoría de gobernanza de las 23 promociones propuestas

El archivo [anti_dianas_bowes44.json](../../backend/data/anti_dianas_bowes44.json) registra **44** filas: `2` con `sitio_adjudicado: true` (`5VA1`, `7SRQ`), `38` con `false` y `4` sin estructura. En [D09-adjudicacion.json](investigacion-1.0.4/D09-adjudicacion.json) el resumen arroja `A/A: 25`, `B/B: 5`, `A/B: 4`, `B/A: 2`, `C/C: 4` y `U/U: 4`. Tal como documentó [SEGUIMIENTO-REPLICA-2026-11-15.md](investigacion-1.0.4/SEGUIMIENTO-REPLICA-2026-11-15.md#L23-L30), las cuatro sesiones autoras (`Noether`, `Popper`, `Mencius`, `Newton`) ejecutaron el **mismo modelo (`gpt-6.1-sol`, esfuerzo `xhigh`)** y no cruzaron el dictamen documental con dos comprobaciones objetivas disponibles en local: el resultado de `redock` en [anti_dianas_bowes44.json](../../backend/data/anti_dianas_bowes44.json) y los registros `SEQADV` de `data/targets/<PDB>.pdb.gz`.

Al cruzar las **23 promociones nuevas** (`propuesta: true` y `vigente: false`) con esos datos locales, la tasa de fallo mecánico es del **47,8 % (11/23 no reproducen la pose nativa en pose-1)**:

| Grupo `redock` | n | PDB IDs y métricas observadas (`rmsd_pose1_A` / `rmsd_mejor_A` / `centroide`) + `SEQADV` relevantes |
|---|---|---|
| **Fallan `redock` (`pose_reproducida: False`)** | **11** | `5NM4` (`ADORA2A`, `9,15 / 8,80 / 2,58 Å`, **11** mut./conflicto); `9UWL` (`AVPR1A`, `6,69 / 6,49 / 0,82 Å`); `4C3F` (`LCK`, `5,97 / 5,09 / 3,07 Å`, **mutación catalítica `D364N`**); `5U09` (`CNR1`, `4,24 / 1,47 / 1,35 Å`, **1** mut. `T210A`); `4IAR` (`HTR1B`, `3,93 / 1,13 / 0,92 Å`, **4** mut.); `8THK` (`ADRA1A`, `2,74 / 2,74 / 0,43 Å`, **25** conflictos); `7KWE` (`PDE3A`, `2,70 / 1,13 / 1,19 Å`, metales Mn/Mg retirados); `8WE8` (`CACNA1C`, `2,40 / 1,82 / 1,19 Å`); `9EQG` (`GABRA1`, `2,33 / 1,67 / 0,45 Å`); `7WC8` (`HTR2A`, `2,17 / 0,54 / 1,10 Å`, **3** mut.); `8X5Y` (`HRH1`, `2,06 / 0,87 / 0,74 Å`, **2** mut.). |
| **Pasan `redock` (`pose_reproducida: True`)** | **12** | `4N6H` (`OPRD1`, `0,29 Å`, **4** mut. tag/constructo); `8YUT` (`HRH2`, `0,36 Å`, `0` mut.); `5ZKC` (`CHRM2`, `0,38 Å`, **1** mut. `S110R`); `7BVQ` (`ADRB1`, `0,55 Å`, **4** mut. constructo); `4UDD` (`NR3C1`, `0,60 Å`, **4** `ENGINEERED MUTATION`: `N517D`, `V571M`, `F602S`, etc.); `8EA0` (`CHRM3`, `0,81 Å`, `0` mut.); `9EO4` (`SLC6A3`, `0,89 Å`, `0` mut.); `2RH1` (`ADRB2`, `0,96 Å`, **3** mut. incl. `N187E`); `8ZP2` (`SLC6A2`, `1,03 Å`, `0` mut., Na⁺ a `3,92 Å` retirado); `6KUX` (`ADRA2A`, `1,34 Å`, `0` mut.); `9HCO` (`SLC6A4`, `1,90 / 1,76 Å`, `0` mut.); `5IKR` (`PTGS2`, `1,93 / 0,55 Å`, `0` mut.). |

**Conclusión de gobernanza:** promover automáticamente por consenso `A/A` de un mismo modelo habría introducido **11 receptores incapaces de reproducir su propio ligando cocristalizado** y al menos **un mutante catalíticamente inactivo (`4C3F` `D364N`)** bajo etiqueta de sitio adjudicado.

---

### 1.2 Dictamen independiente de los 12 casos muestreados ([D09-revision-humana.md](investigacion-1.0.4/D09-revision-humana.md))

Se aplicó la escala de la hoja sin asumir las actas previas, contrastando coordenadas, centroides, contactos pesados `<= 4,5 Å`, `SEQADV`, iones retirados, `redock` y bibliografía primaria:

- **A:** Caja centrada en el bolsillo humano exacto del mecanismo Bowes, constructo válido para el sitio y redocking reproducible (`<= 2,0 Å`), o apo con validación geométrica externa documentada.
- **B:** Caja en el receptor y cavidad correctos, pero con brecha concreta (estado funcional opuesto, ligando/cofactor o metal ausente relevante, mutación `SEQADV` relevante o fallo de `redock > 2,0 Å`).
- **C:** Caja en otra entidad, quimera o sub-sitio distinto al mecanismo/ensayo de referencia.
- **U:** Evidencia insuficiente para resolver.

| ID | Grado | Cadena, ligando y sitio | Mecanismo y fuente primaria | Brecha o estructura alternativa |
|---|---|---|---|---|
| **08** (`7WC8`) | **B** *(propuesta era `A/A`)* | `HTR2A` (`P28223`), RX `2,45 Å`. Cadena `A`, `92S` (`A:1207`, lumateperona, 29 átomos pesados, `21` contactos `<= 4,5 Å` incl. `A:ASP155` `2,45 Å`, `A:PHE332`, `A:PHE243`). | Bolsillo ortostérico humano de `5-HT2A` unido a antipsicótico atípico **antagonista/inactivo** (`PMID 35084960`, `DOI 10.1126/science.abl8615`). | **Tres brechas:** (1) conformación inactiva/antagonista frente al riesgo Bowes por **agonismo** alucinógeno/Gq; (2) tres mutaciones termoestabilizantes (`SEQADV SER162LYS`, `MET164TRP`, `SER372ASN`, con `I163` a `3,28 Å` del ligando); (3) **`redock=False`** (`rmsd_pose1_A=2,17 Å`, mejor `0,54 Å`, centroide `1,10 Å`). Alternativa activa acoplada a Gq: **`6WHA`** (`PMID 32938682`, `DOI 10.1016/j.cell.2020.08.024`). |
| **04** (`7UL2`) | **C** *(no adjudicado)* | **Quimera `NTSR1` (`P30989`)** + injerto ICL3 de `OPRK1` (`P41145`), cryo-EM `2,4 Å`. Cadena `R`, `Q6Q` (`R:501`, `SR48692`, 42 átomos pesados, `15` contactos `<= 4,5 Å` incl. `R:ARG322`, `R:PHE326`, `R:HIS343`). | `Q6Q` (`SR48692`) es antagonista selectivo del **receptor de neurotensina 1 (`NTSR1`)** (`PMID 36396979`, `DOI 10.1038/s41594-022-00859-8`). El segmento injertado de `OPRK1` dista `22,89 Å` de `Q6Q`, frente a `3,10 Å` a `P30989` ([SEGUIMIENTO](investigacion-1.0.4/SEGUIMIENTO-REPLICA-2026-11-15.md#L32)). | Aunque `redock=True` (`0,82 Å`), **la caja mide afinidad al bolsillo de `NTSR1`, no de `OPRK1`**. Reemplazar por `OPRK1` real: **`6B73`** (activa con agonista `MP1104`, `PMID 29307491`, `DOI 10.1016/j.cell.2017.12.011`) o **`4DJH`** (inactiva con antagonista `JDTic`, `PMID 22437657`, `DOI 10.1038/nature10939`). |
| **10** (`7KWE`) | **B** *(propuesta era `A/A`)* | `PDE3A` (`Q14432`), RX `2,0 Å`. Cadena `A`, `X5M` (`A:1101`, `DNMDP`, 22 átomos pesados, `13` contactos `<= 4,5 Å` incl. `A:GLN1001` `2,62 Å`, `A:HIS961`, `A:PHE1004`). | Sitio catalítico cAMP/cGMP de `PDE3A`, donde `DNMDP` inhibe y actúa además como pegamento molecular con `SLFN12` (`PMID 34272366`, `DOI 10.1038/s41467-021-24495-w`). Base clínica/arritmias PDE3: `PMID 12181427`, OPTIME-CHF `PMID 11911756`. | **`redock=False`** (`rmsd_pose1_A=2,70 Å`, mejor `1,13 Å`, centroide `1,19 Å`) y la preparación retira los metales catalíticos cercanos (`A:MG1103` a `6,78 Å`, `A:MN1102` a `7,40 Å`). No promover a `A` mientras `redock` falle y sin contrastar con inhibidor catalítico clásico (p. ej. revisar **`7L28`** / serie con y sin metales). |
| **01** (`6LQA`) | **B** *(no adjudicado)* | `SCN5A` / `NaV1.5` (`Q14524`), cryo-EM `3,3 Å`. Cadena `B`, `QDN` (`B:2110`, quinidina, 24 átomos pesados, `14` contactos `<= 4,5 Å` incl. `B:VAL405`, `B:PHE402`, `B:THR1417`, `B:GLN371`). | Bloqueo intracelular del poro bajo el filtro `DEKA` por quinidina (`PMID 33684260`, `DOI 10.1002/anie.202102196`). En cambio, el ensayo histórico Bowes-44 (`PMID 23197038`) para «`Na+ channel (site 2)`» usa `[3H]batracotoxina` en sinaptosomas de corteza de rata (`PubChem AID 1962102`). | La caja está en el poro de `SCN5A` humano (solapamiento parcial en la cavidad interna respecto a `BTX-B` en `NaV1.5` de rata, **`8T6L`**, `PMID 38485923`, `DOI 10.1038/s41467-024-45958-w`, choque estérico Fig. 3c), pero cocristalizada con un bloqueante de poro/sitio de anestésicos locales (quinidina) y con **`redock=False` grave** (`rmsd_pose1_A=5,72 Å`, mejor `1,99 Å`, centroide `2,35 Å`). Mantener sin adjudicar hasta separar la definición del ensayo/sitio y resolver el `redock`. |
| **07** (`9EQG`) | **B** *(propuesta era `A/A`)* | `GABRA1` (`P14867`, interfaz `D/C` α1+/γ2−), cryo-EM `2,4 Å`. `site_chains=['D','C']`, `A1H6W` (`A1H D:505`, puerarina, 30 átomos pesados, `18` contactos incl. `C:ASP56`, `C:PHE77`, `D:SER205`, `D:HIS102`). | Sitio alostérico central de benzodiazepinas en la interfaz α1+/γ2− (`PMID 39261733`, `DOI 10.1038/s41586-024-07929-5`; mecanismo BZD `PMID 10816315`). | La caja sí apunta al bolsillo BZD, pero parte de puerarina y **`redock=False`** (`rmsd_pose1_A=2,33 Å`, mejor `1,67 Å`, centroide `0,45 Å`). Contrastar/sustituir por complejo con benzodiazepina/antagonista clásico (**`6HUP`**, **`6D6U`** `PMID 29950725`, **`6X3X`**) que supere `redock <= 2,0 Å`. |
| **12** (`5VA1`) | **A** *(apo, con reserva de umbral y caja)* | `KCNH2` / `hERG` (`Q12809`), cryo-EM **apo**, tetrámero (`A,B,C,D`). Centro `(73,15, 73,15, 78,53)`, caja `(28,8, 28,8, 30,0)`. `Y652 CA` (`A`) a `8,25 Å` del centro. | Bloqueo de la cavidad central intracelular del poro hERG mediado por `Y652`/`F656` (Wang & MacKinnon `PMID 28431243`; mutagénesis `PMID 8772706`, `11005845`). [D09-geometria.json](investigacion-1.0.4/D09-geometria.json) verifica `34/34` átomos de pimozida dentro de la caja en las 4 cadenas (centroide a centro `4,10–4,36 Å`). | Vigente `sitio_adjudicado: true`. Brechas operativas a documentar: `redock=None` (depósito apo), caja muy amplia (`~29–30 Å`) y **discrepancia de umbral** entre [selectivity.py](../../backend/services/docking/selectivity.py#L77) (`-7,0 kcal/mol`) y [curated_targets.json](../../curated_targets.json) (`-7,5 kcal/mol`). Control holo interno recomendado para auditoría: **`8ZYQ`** (`1II`, `redock=True`, `1,7 Å`, `PMID 39321803`). |
| **02** (`8ZP2`) | **A** *(propuesta `A/A`)* | `SLC6A2` / `NET` (`P23975`), cryo-EM `2,4 Å`. Cadena `A`, `A1LX4` (`A1L A:701`, atomoxetina, 19 átomos pesados, `17` contactos incl. `A:PHE72`, `A:TYR151`, `A:SER419`, `A:GLY423`). | Sitio central S1 de recaptación de noradrenalina con inhibidor selectivo clínico atomoxetina (`PMID 39223283`, `DOI 10.1038/s41422-024-01024-0`). | **`redock=True`** (`rmsd_pose1_A=1,03 Å`, mejor `1,03 Å`, centroide `0,47 Å`, `0` `SEQADV`). Salvedad menor de preparación para consignar en dossier: los iones `A:NA702` (`3,92 Å`), `A:NA703` (`6,15 Å`) y `A:CL704` (`8,57 Å`) se retiran antes de acoplar, aunque Vina reproduce la pose a `1,03 Å` sin ellos. |
| **11** (`8Y72`) | **C** *(no adjudicado)* | `OPRM1` / `MOR` (`P35372`), cryo-EM `2,65 Å`. Cadena `R`, `VV9` (`R:403`, `BMS-986122`, 24 átomos pesados, `13` contactos incl. `R:ASN193`, `R:CYS161`, `R:MET245`). | `VV9` ocupa el bolsillo **alostérico extrahelicoidal (PAM)** en la cara lipídica TM2/3/4 (`DOI 10.1126/sciadv.aea9832`), a **`15,09 Å`** de distancia mínima interatómica respecto a DAMGO (cadena `D`). | No modela el bolsillo ortostérico opioide asociado a depresión respiratoria/dependencia, y además **`redock=False`** (`rmsd_pose1_A=5,89 Å`, mejor `2,08 Å`, centroide `1,65 Å`). Reemplazar por complejo ortostérico humano: **`6DDF`** (`PMID 29899455`, `DOI 10.1038/s41586-018-0219-7`) u **`8EF5`** (`PMID 36368306`, `DOI 10.1016/j.cell.2022.09.041`). |
| **06** (`4C3F`) | **B** *(propuesta errónea a `A/A`)* | `LCK` (`P06239`), RX `1,72 Å`. Cadena `A`, `7KW` (`A:1499`, 24 átomos pesados, `13` contactos en bisagra ATP incl. `A:MET319`, `A:GLU317`, `A:THR316`). | Inhibición competitiva del sitio ATP de la tirosina quinasa `Lck` (`PMID 24117015`, `DOI 10.1021/jm401309q`). | **Doble defecto crítico omitido por las 4 sesiones:** (1) el depósito porta la mutación de ingeniería catalíticamente inactiva **`D364N`** (`SEQADV 4C3F ASN A 364 UNP P06239 ASP 364 ENGINEERED MUTATION` en el motivo HRD); (2) **`redock=False` severo** (`rmsd_pose1_A=5,97 Å`, mejor `5,09 Å`, centroide `3,07 Å`). Sustituir por `LCK` silvestre como **`2OF2`** (`PMID 17276681`, `DOI 10.1016/j.bmcl.2007.01.048`). |
| **03** (`7SRQ`) | **A** *(vigente `True`)* | `HTR2B` (`P41595`), cryo-EM `2,7 Å`. Cadena `R`, `7LD` (`R:502`, LSD, 24 átomos pesados, `16` contactos incl. `R:ASP135` `2,83 Å`, `R:PHE340`, `R:ASN344`). | Agonismo ortostérico de `5-HT2B` ligado a valvulopatía cardíaca (`PMID 36087581`, `DOI 10.1016/j.neuron.2022.08.006`; clínica `PMID 9271479`, `11104741`). | Vigente `sitio_adjudicado: true` y **`redock=True`** (`rmsd_pose1_A=1,81 Å`, mejor `1,61 Å`, centroide `0,70 Å`). Salvedades presentes: `truncadas_en_sitio=4` y `SEQADV MET144TRP CONFLICT`; como respaldo cristalográfico sin truncamientos en el bolsillo puede vigilarse **`4IB4`** (`rmsd_pose1_A=1,05 Å`). |
| **09** (`9GJ1`) | **C** *(no adjudicado)* | LBD humano `GluN1` (`GRIN1`, `Q05586`) + `GluN2A` de rata, RX `1,62 Å`. Cadena `B`, `A1IME` (`A1I B:902`, Compound 339, 19 átomos pesados, `18` contactos incl. `B:SER756`, `B:ASP732`, `B:ARG523`). | Agonista parcial en el **sitio coagonista de glicina (`GluN1`)** (`PMID 39560374`); dista `23,76 Å` de `HETATM GLU` en `9GJ1` (`21,05 Å` del bolsillo de glutamato en `GluN2A`) y **carece del dominio transmembrana/poro de bloqueantes PCP**. | El ensayo Bowes/Cerep `0066` mide competición en el **sitio de glutamato** (`CGS 19755` / `CGP-39653`, `PMID 2899170`), y la neurotoxicidad/psicomimesis clínica típica proviene de **bloqueantes del poro canal (sitio PCP/ketamina)**, representado p. ej. por **`7EU8`** (`S`-ketamina en el poro, `PMID 34321660`, `DOI 10.1038/s41586-021-03769-9`). `9GJ1` evalúa un sitio distinto. |
| **05** (`8YUT`) | **A** *(propuesta `A/A`)* | `HRH2` (`P25021`, complejo `HRH2–Gs`), cryo-EM `2,7 Å`. Cadena `R`, `A1D67` (`A1D R:401`, amtamina, 10 átomos pesados, `12` contactos incl. `R:THR103`, `R:ASP98`, `R:ASP186`, `R:TYR250`). | Sitio ortostérico humano de `H2` con agonista selectivo amtamina (`PMID 38647423`, `DOI 10.1002/advs.202310120`). | **`redock=True`** (`rmsd_pose1_A=0,36 Å`, mejor `0,36 Å`, centroide `0,20 Å`, `0` `SEQADV`). Candidato apto para adjudicación `A`, precisando en la ficha que la conformación acoplada corresponde al estado agonista de `HRH2`. |

### Compuerta mínima recomendada antes de tocar el catálogo

1. Exigir `redock.pose_reproducida == True` como requisito eliminatorio previo (salvo estructuras *apo* con validación geométrica externa documentada tipo `5VA1`), lo que descarta de inmediato `11` de las `23` candidatas.
2. Auditar automáticamente `SEQADV` (`ENGINEERED MUTATION` / `CONFLICT`) cerca del sitio o del centro catalítico antes de cualquier dictamen `A`, bloqueando casos como `4C3F` (`D364N`) o revisando explícitamente los `4` mutantes de `4UDD`, `5ZKC` (`S110R`) o `2RH1` (`N187E`).
3. Someter a revisor humano independiente (y no sólo a consenso del mismo LLM) las `12` filas que sí pasaron `redock`.

---

## 2. Revisión de los cuatro textos nuevos (`Alta y barata`)

### 2.1 Chai-1 (`prediccion.py`, `preparacion_confianza.py`, `i18n_receptores_propios.py`)

- **Estado vigente:**
  - [preparacion_confianza.py](../../backend/services/dossier/preparacion_confianza.py#L96): `"estructura predicha por Chai-1 (declarado por el archivo en _struct.title)"`.
  - [preparacion_confianza.py](../../backend/services/dossier/preparacion_confianza.py#L105-L108): `"pLDDT leído de _ma_qa_metric_local: en este archivo coincide con el factor B del Cα de cada residuo, que no es la media del residuo que da el modelo (así lo escribe Chai-1 0.6.1; el archivo no declara su versión)"`.
  - Traducciones paralelas en [i18n_receptores_propios.py](../../backend/core/i18n_receptores_propios.py#L223-L226).
- **Auditoría:** Científicamente honesto (no afirma más de lo comprobado: separa autorreporte del archivo, falta de versión y diferencia entre Cα y media de residuo). Sin embargo, presenta **dos mejoras baratas**:
  1. **Jerga interna de mmCIF y tono desigual:** `_struct.title` y `_ma_qa_metric_local` cargan innecesariamente el texto visible (~190 caracteres en `calfa`), y en el mismo archivo ([preparacion_confianza.py](../../backend/services/dossier/preparacion_confianza.py#L68)) se dice `"Están comprobadas AlphaFold DB y Boltz 2.2.1"`, lo que requiere aclarar explícitamente que lo sin verificar en Chai-1 es la convención general entre versiones.
  2. **Condición de detección lábil en [prediccion.py](../../backend/services/targets/prediccion.py#L205-L207):** si todos los átomos de cada residuo compartieran el mismo `b_iso == valor` (`factor_b_coincide == True`), `local_es_el_calfa` también evaluaría `True`, de modo que [prediccion.py](../../backend/services/targets/prediccion.py#L377) rotularía `"que no es la media del residuo"` sin haber demostrado que los demás átomos difieran del Cα. Añadir `not lectura["factor_b_coincide"]` (o verificar variación intra-residuo) cierra esa brecha lógica.
- **Redacción sugerida:**
  - **ES:** `"Chai-1 (declarado en la cabecera del archivo, sin versión) · pLDDT tomado de la tabla local del mmCIF: en este archivo coincide con el Cα de cada residuo (como exporta Chai-1 0.6.1), no con la media atómica del residuo; convención general sin verificar."`
  - **EN:** `"Chai-1 (self-reported in the file header, no version stated) · pLDDT read from the mmCIF local metric table: in this file it matches each residue's Cα B-factor (as written by Chai-1 0.6.1), not the per-residue atomic mean; general convention unverified."`

### 2.2 Nota de UMS = 0 (`bloques_protocolo.py`, `i18n_catalog.py`, `queue_handler.py`, `runner.py`)

- **Estado vigente:** [bloques_protocolo.py](../../backend/services/dossier/bloques_protocolo.py#L30-L34) (`NOTA_UMS_CERO`, traducida en [i18n_catalog.py](../../backend/core/i18n_catalog.py#L3136)): `"0.0000 — los patrones SMARTS no encontraron ningún grupo que buscan en el SMILES evaluado. Buscan la forma neutra o protonada: una sulfonamida, un hidroxamato o un tiol escritos como anión (N⁻, O⁻, S⁻) no se reconocen y también dan 0."`
- **Auditoría:**
  1. **Desajuste entre texto e implementación:** tanto [queue_handler.py](../../backend/services/docking/queue_handler.py#L1269) como [runner.py](../../backend/services/pipeline/runner.py#L1056) pasan a `ejecutar_m5(...)` **`smiles=pipeline_params.molecule_smiles`** (la cadena de entrada literal del usuario, no `smiles_acoplado` ni un SMILES reprotonado), y dentro de [ejecucion.py](../../backend/services/pipeline/protocols/m5/ejecucion.py#L133-L195) se invoca `ums_autorizado(smiles)` tal cual llega. Decir «en el SMILES evaluado» induce a creer que se evaluó la forma preparada a pH 7,4, cuando en realidad depende de cómo vino escrito el **SMILES de entrada**.
  2. **Oculta fuera del dossier PDF:** [resultFieldPresentation.ts](../../frontend/lib/resultFieldPresentation.ts#L67) sigue mostrando `ums_warhead` simplemente como `"Componente de grupos reactivos UMS"` sin esta aclaración, y la nota tampoco precisa que `0` no descarta grupos reactivos o quelantes fuera del catálogo SMARTS vigente.
- **Redacción sugerida:**
  - **ES:** `"0.0000 — el SMILES de entrada no coincide con los patrones SMARTS vigentes de UMS. Sólo reconocen formas neutras o protonadas (sulfonamidas, hidroxamatos o tioles introducidos como anión N⁻, O⁻ o S⁻ darán 0); tampoco descarta reactividad fuera de esa lista."`
  - **EN:** `"0.0000 — the input SMILES matched none of the current UMS SMARTS patterns. Only neutral or protonated forms are recognised (sulfonamides, hydroxamates or thiols entered as anions N⁻, O⁻ or S⁻ return 0), and 0 does not rule out reactive groups outside this pattern set."`

### 2.3 Aviso de sitio no adjudicado (`selectivity.py`, `ProSelectivityPanel.tsx`, `pro.ts`, `pdf_generator.py`)

- **Estado vigente:**
  - [selectivity.py](../../backend/services/docking/selectivity.py#L116-L142): `AVISO_SITIO_NO_ADJUDICADO = "Sitio no adjudicado: no se ha revisado que la caja corresponda al mecanismo de ese riesgo, así que la alerta mide sólo la afinidad de Vina a esa caja."` y `"ALERTA {nombre}: afinidad {afinidad:.1f} kcal/mol < umbral {umbral:.1f}. Riesgo: {riesgo}"`.
  - [pro.ts](../../frontend/context/traducciones/pro.ts#L786): `"...nobody has checked that the box matches the mechanism behind that risk, so the alert only measures Vina's affinity to that box."`
- **Tres defectos objetivos encontrados al revisar el código:**
  1. **Contradicción de operador `<` vs `<=`:** [selectivity.py](../../backend/services/docking/selectivity.py#L429) y [pdf_generator.py](../../backend/services/blockchain/pdf_generator.py#L1109) disparan alerta cuando `aff < thresh` (`aff >= thresh` pasa), pero [ProSelectivityPanel.tsx](../../frontend/components/interfaces/pro/ProSelectivityPanel.tsx#L458) evalúa **`if (aff <= thresh)`** (disparando también en el empate exacto, p. ej. `-7,0 == -7,0`).
  2. **Omitido completamente del dossier/PDF y sin traducción en backend:** en [model.py](../../backend/services/dossier/model.py) no existen referencias a `safety_flags`, `sitio_adjudicado` ni `selectivity`; en [pdf_generator.py](../../backend/services/blockchain/pdf_generator.py#L1099-L1161) la tabla del panel muestra `["Anti-target", "Afinidad (kcal/mol)", "Umbral operativo", "Lectura"]` sin incluir `sitio_adjudicado` ni `AVISO_SITIO_NO_ADJUDICADO` (y en `backend/core/i18n*.py` hay `0` apariciones del aviso). Además [selectividad_margen.py](../../backend/services/docking/selectividad_margen.py#L94-L159) calcula el margen y su veredicto ignorando `sitio_adjudicado`.
  3. **Imprecisión terminológica y tono coloquial:** «nobody has checked» es impropio de un dossier técnico, y conviene decir «score estimado de Vina» en lugar de «afinidad de Vina» para no equipararlo con una afinidad experimental medida.
- **Redacción sugerida:**
  - **ES:** `"Sitio no adjudicado: no se ha comprobado que esta caja corresponda al sitio del mecanismo responsable de ese riesgo; la alerta refleja únicamente un score estimado de Vina en esa caja estructural."`
  - **EN:** `"Unadjudicated site: it has not been verified that this box corresponds to the site mediating this liability; this flag reflects only an estimated Vina score within that catalog box."`
  *(Acompañado de columna/insignia de adjudicación en la tabla del PDF, traducción en `i18n_catalog.py` y unificación de `<` vs `<=` entre backend y UI).*

### 2.4 Índice compuesto heredado (`total_score` y `druglikeness_score`)

- **Estado vigente y cuatro brechas localizadas:**
  1. En [pdf_generator.py](../../backend/services/blockchain/pdf_generator.py#L1550) (`L1549: # B12: es QED×100, como lo llama el dossier; antes «de reglas» y no mide ninguna regla`) y en [i18n_catalog.py](../../backend/core/i18n_catalog.py#L3006) ya se rotula como `"Índice de similitud a fármaco heredado"` / `"Legacy drug-likeness index"`. **Sin embargo, [resultFieldPresentation.ts](../../frontend/lib/resultFieldPresentation.ts#L45) aún etiqueta `druglikeness_score` como `"Score de reglas de semejanza a fármacos"` / `"Drug-likeness rule score"`** (doble error: ni es «de reglas», pues es `QED×100`, ni advierte que es heredado).
  2. Superficies activas que conservan `total_score` sin aviso de legado: `SARTable.tsx` (retirado en 1.0.4, B-6; líneas 124-168 del código anterior) (pinta `total_score` con `<Trophy />` y `t("c_score")`), `CommunityPanel.tsx` (retirado en 1.0.4, B-6; línea 163 del código anterior), [OptionsMenu.tsx](../../frontend/components/ui/OptionsMenu.tsx#L153), [batch.py](../../backend/api/routers/batch.py#L429-L452) (`TotalScore` y `_orden_exportado`), y [history.py](../../backend/api/routers/history.py#L111-L178) (sigue aceptando orden y filtro `min_score`/`max_score`, aunque [history/page.tsx](../../frontend/app/history/page.tsx#L159-L162) ya retiró el botón en pantalla).
  3. **Instrucción muerta en el prompt narrativo:** en [interpreter.py](../../backend/services/evaluation/interpreter.py#L80-L87), `memory_context = ""` siempre está vacío tras retirar `memory_store`, pero la regla `4. Puedes comparar con evaluaciones previas del usuario si estan disponibles abajo.` sigue inyectándose en el `system_prompt`. Conviene borrar esa regla 4 para no inducir referencias ficticias cuando no hay contexto.

---

## 3. D-01 · Con Chai-1, si `pLDDT < 70` debe leer Cα o media del residuo (`Media`)

### Datos comprobados

Del análisis reproducido en [D01-resultados.json](investigacion-1.0.4/D01-resultados.json), [D01-CDK2-resultados.json](investigacion-1.0.4/D01-CDK2-resultados.json) y [D01.md](investigacion-1.0.4/D01.md) sobre Chai-1 0.6.1 (semilla 42, 5 muestras por caso):

| Caso | Muestras | Residuos `< 70` (Cα / `_ma_qa_metric_local`) | Residuos `< 70` (media atómica `B_iso`) | `solo_local_bajo70` | Sitio experimental vs lecturas (frente a `lDDT-Cα`) |
|---|---:|---:|---:|---:|---|
| `cdk2_apo` (`298 res`) | 5 | `9, 10, 11, 12, 10` | `21, 21, 21, 21, 21` | `0` en todas | Frente a `1HCL`: `3/23` obs `< 70`, **0/23** local, **0/23** media (`ρ` cadena `0,858–0,872` vs `0,758–0,772`). Frente a `1H1Q`: `1/23` obs `< 70`, **0/23** en ambas. |
| `cdk2_lig` (`298 res`) | 5 | `3, 3, 3, 3, 3` | `9, 8, 9, 8, 9` | `0` en todas | Frente a `1H1Q`: `2/23` obs `< 70`, **0/23** local, **0/23** media (`ρ` cadena `0,858–0,869` vs `0,715–0,736`). |
| `net_apo` (`8HFI`, `548 Cα` mapeados) | 5 | `72, 72, 71, 71, 71` | `76, 76, 76, 76, 76` | `0` en todas | Frente a `8HFI`: `1–3/25` obs `< 70`, **0/25** en ambas (`sens=0, spec=1`; `ρ` en sitio `0,324–0,468` Cα vs `0,112–0,280` media). |

### Dictamen y propuesta operativa

1. **Por qué ni Cα solo ni reescribir a media bajo el mismo `< 70` es limpio por separado:**
   - En los casos medidos, ambos producen **exactamente 0 avisos en el sitio** porque los bolsillos de `CDK2` y `NET` son rígidos y están bien modelados (`lDDT` mediano en sitio `82,6–92,9`). Por ello **los datos actuales no tienen potencia para decidir entre una lectura y la otra**.
   - Desde el punto de vista de docking rígido con Vina: la tabla `_ma_qa_metric_local` de Chai-1 mide confianza del centro de token (`Cα`, coherente con el criterio original `generally good backbone prediction` de AlphaFold DB), mientras una **cadena lateral desordenada dentro de la cavidad** puede hundir su `B_iso` atómico (`CA - media = +14,7` en el residuo `A:36` de [test_prediccion_fuente_declarada.py](../../backend/tests/test_prediccion_fuente_declarada.py#L225-L226)) aunque el `Cα` quede sobre `70`, alterando contactos directos y choques estéricos en Vina. Sin embargo, reconstruir silenciosamente la media desde `B_iso` y compararla contra `70` (un umbral calibrado sobre `lDDT-Cα` por residuo) introduce riesgo de falsos positivos en cadenas laterales térmicamente móviles y pierde correspondencia literal con la tabla ModelCIF.
2. **Regla recomendada (mantener Cα + señal dual explícita para cadenas laterales):**
   - Conservar `_ma_qa_metric_local` (`Cα`) como lectura primaria trazable al estándar ModelCIF.
   - Añadir únicamente como **aviso secundario separado** en el análisis del sitio: si existen residuos junto a la caja con `Cα >= 70` pero `media_atómica(B_iso) < 70` (y cuando el archivo exhiba variación intra-residuo), reportar el recuento aparte (*«K residuos junto al sitio con pLDDT atómico medio < 70 pese a Cα >= 70»*) sin adulterar el umbral primario ni mezclarlo en una única cifra opaca.
3. **Diseño mínimo confirmatorio poscorte:** reunir `~20–30` complejos posteriores al corte de entrenamiento con residuos del bolsillo en zona límite (`pLDDT` de cadena lateral entre `50` y `75`: bucles P-loop/DFG en quinasas, ECL2 en GPCRs o sitios inducidos) y medir qué métrica (`Cα < 70`, `media_residuo < 70`, o `mínimo_átomo_pesado_sitio < 70`) discrimina mejor la pérdida de recuperación de pose nativa en Vina (`RMSD <= 2,0 Å`) y el error de rotámero frente al cristal holo.

---

## 4. D-04 · Subclases de aminas alifáticas, SMARTS y `9,8` vs `8,3` (`Media`)

### 4.1 Por qué mantener `9,8` frente a `8,3`

Los resultados en [metrics.json](../../scripts/artifacts_science/DEC-104-D04-CHEMBL/metrics.json#L47-L65) y [D04-ChEMBL-banda.json](investigacion-1.0.4/D04-ChEMBL-banda.json) demuestran que sustituir la constante `9,8` de [ionizacion.py](../../backend/chem/ionizacion.py#L125) por la mediana ajustada de ChEMBL25 (`8,3`):
- mejora el error continuo MAE en `+0,51` unidades de pKa (`IC 95 % [0,18; 0,88]`, `n = 241` evaluación en `131` andamios),
- **pero logra `0` mejora en la especie dominante a pH 7,4**: exactamente **`139 / 193` aciertos binarios con `9,8` y `139 / 193` con `8,3`** (`139 / 188` y `139 / 188` tras excluir la banda `[7,1; 7,7]`, porque tanto `9,8` como `8,3` superan `7,4`),
- mientras en el estrato `S1_alifatica_normal` ([resultados.json](investigacion-1.0.4/resultados.json#L25-L29)) la constante `9,8` tiene ya error pequeño (`MAE = 0,69`, sesgo `+0,32`) y bajarla a `8,3` introduciría un sesgo sistemático negativo de `~ -1,2` unidades (cambiando `LogD` en `63/67` MolFlex y `89/89` 8T69 sin mejorar el estado acoplado).

**Decisión recomendada:** **conservar `9,8` en `ionizacion.py`** para la clase general y corregir el punto ciego real en [especie_en_revision.py](../../backend/chem/especie_en_revision.py): las subclases con grupos inductivos/estereoelectrónicos fuertes que sí cruzan o bordean `pH 7,4` (como `clopidogrel`, que en [resultados.json](investigacion-1.0.4/resultados.json#L46-L61) sale con `motivos_de_revision: []` y se acopla como `+1` pese a tener `pKa = 4,55` y sólo `0,14 %` de fracción protonada a pH 7,4).

### 4.2 Subclases prioritarias, SMARTS depurados sobre `smiles_acoplado` y fuentes primarias

Todas las expresiones SMARTS se definieron sobre la **especie acoplada protonada** (`[NX4+;!H0;!$(N[a])]`, coherente con `_SMARTS_AMINA_CON_ATRACTOR` en [especie_en_revision.py](../../backend/chem/especie_en_revision.py#L122-L126)) para que sólo salten si el producto efectivamente dejó protonado el centro básico:

| Prioridad | Subclase química | SMARTS sobre `smiles_acoplado` | Evidencia primaria verificada (`pKa` exp. y efecto frente a `9,8`) |
|---|---|---|---|
| **1 (Alta)** | **α-aminoéster** | `[NX4+;!H0;!$(N[a])]-[CX4]-[CX3](investigacion-1.0.4/=O)[OX2H0][#6]` | **Clopidogrel** `pKa 4,55` (25 °C potenciometría, sNDA `20-839/S-019` ante FDA y síntesis/estabilidad `PMID 27007371`, ΔpKa `~ -5,2`); **etil éster de glicina** `7,66`. `[OX2H0][#6]` evita disparar en zwitteriones `-COO⁻` y en β-hidroxiaminas (`propranolol`); la distancia de un solo `CX4` excluye acertadamente β-aminoésteres como el `metilfenidato` (`~8,9`, catión dominante). |
| **1 (Alta)** | **α-aminocetona y α-aminoaldehído** | `[NX4+;!H0;!$(N[a])]-[CX4]-[CX3;!$([CX3][OX2,OX1-,NX3])](=O)` | Efecto inductivo α-carbonilo comparable al éster (~2–3,5 unidades de descenso) sin estabilización por carboxilato. La exclusión explícita `[!$([CX3][OX2,OX1-,NX3])]` garantiza `0` falsos positivos en zwitteriones (`-COO⁻`), ácidos y α-aminoamidas. |
| **1 (Alta)** | **Éter bis-β cíclico (*N*-alquilmorfolina y *N*-(oxetan-3-il)amina)** | `[NX4+;!H0;!$(N[a])]1-[CX4]-[CX4]-[OX2H0]-[CX4]-[CX4]1` y `[NX4+;!H0;!$(N[a])]-[CX4;r4]1-[CX4;r4]-[OX2H0;r4]-[CX4;r4]1` | ***N*-metilmorfolina** `pKa 7,38` (`DOI 10.1002/qua.21809`); **gefitinib** `~7,17–7,28` (`PMID 16231967`, `DOI 10.2165/00003088-200544110-00004`); **aminas *N*-(oxetan-3-ilo)** (`PMID 20349959` / `DOI 10.1021/jm9018788`; `PMID 37713805` / `DOI 10.1016/j.ejmech.2023.115802`), con ΔpKa `~ -2,4` a `-3,0` cruzando `7,4`. **Crucial:** no generalizar a éteres β acíclicos simples (`2-metoxietilamina` `9,45`). |
| **1 (Alta)** | **Propargilamina (β-alquino)** | `[NX4+;!H0;!$(N[a])]-[CX4]-C#[CX2]` | **Rasagilina** `~7,3–7,5` (`DOI 10.1016/j.aca.2006.10.015`); **selegilina** `~7,48–7,5`; **pargilina** `~6,6`. ΔpKa `~ -2,3` a `-3,2`, situando la amina en pleno cruce de 50 % neutra a pH 7,4. |
| **1–2** | **β-sulfona / β-sulfonamida** | `[NX4+;!H0;!$(N[a])]-[CX4]-[CX4]-[SX4](investigacion-1.0.4/=O)(=O)[#6,#7]` | Morgenthaler *et al.* 2007 (`PMID 17530727`, `DOI 10.1002/cmdc.200700059`) reportan **`pKa ~5,4`** para la variante cíclica **tiomorfolina 1,1-dióxido**. *Nota sobre fuentes:* para la β-sulfona acíclica simple `2-(metilsulfonil)etilamina` no se localizó en fuentes abiertas determinación acuosa primaria experimental (sólo estimación computacional `~6,3 ± 0,2`), por lo que la evidencia experimental sólida recae en la variante cíclica. |
| **2 (Media / informativa)** | **α-aminoamida** | `[NX4+;!H0;!$(N[a])]-[CX4]-[CX3](investigacion-1.0.4/=O)[NX3]` | **Lidocaína** `~7,86`, **bupivacaína** `~8,1`; estrato `S3_alfa_amida` (`MAE 1,85`, sesgo `+1,85`). Aunque a pH 7,4 siguen siendo mayoritariamente catiónicas (`~74–83 %`), una fracción neutra del `~17–26 %` afecta sensiblemente a `LogD`; conviene separarlo como aviso de zona gris respecto a las subclases que invierten la especie mayoritaria (`< 7,4`). |

**Exclusiones deliberadas para evitar falsas alarmas:**
- **β-monofluoroaminas aisladas:** según Morgenthaler 2007 (`PMID 17530727`), `2-fluoroetilamina` tiene `pKa ~8,9–9,0` (`~97,5 %` protonada a pH 7,4). Mantener la regla actual restringida a `>= 2` flúores (`CF2`/`CF3` en β) salvo casos cíclicos gem-difluoro específicos.
- **Picolilaminas simples:** `2-picolilamina` (`pKa2 = 8,79`) y `3-picolilamina` (`~8,5–8,8`) siguen `> 90–96 %` catiónicas a pH 7,4 sin atractores adicionales en el anillo.
- **Éteres β acíclicos simples** (`2-metoxietilamina` `9,45`, `propranolol` `9,42`): `> 99 %` protonados a pH 7,4.

### 4.3 Resultado reproducible de comprobación SMARTS en RDKit

Ejecutado directamente con `./python-embed/python.exe -B` sobre los fixtures de [test_especie_en_revision.py](../../backend/tests/test_especie_en_revision.py) y sondas manuales:
- `CORRECTAS_VERIFICADAS` (`17` moléculas de control): **`0 / 17` falsos positivos**.
- `AMINAS_CON_ATRACTOR_ACOPLADAS` (`5` moléculas existentes): **`5 / 5` retenidas** por `_SMARTS_AMINA_CON_ATRACTOR`.
- `10` controles negativos dirigidos (`clopidogrel_neutro`, `glicina_zwitterion`, `alanina_zwitterion`, `propranolol+`, `verapamilo+`, `fentanilo+`, `clorfeniramina+`, `imipramina+`, `hidroxicloroquina+`, `2_metoxietilamina+`) más el β-aminoéster `metilfenidato+`: **`0` falsos positivos**.
- `11` sondas positivas objetivo (`clopidogrel+` → `alfa_ester`; `glicina_etil_ester+` → `alfa_ester`; `aminocetona+` → `alfa_cetona_aldehido`; `lidocaina+` y `bupivacaina+` → `alfa_amida`; `N_metilmorfolina+` y `gefitinib+` → `morfolina`; `oxetan_3_piperidina+` → `oxetano_3_amina`; `rasagilina+` y `selegilina+` → `propargilamina`; `tiomorfolina_dioxido+` → `beta_sulfona`): **`11 / 11` aciertos exactos sin cruces espurios**.

---

## 5. D-07 · Métrica que debe ordenar la exportación de un lote (`Baja`)

### Evidencia en código y rendimiento medido

En [SUP-02-TOTAL-SCORE.md](../papers/SUP-02-TOTAL-SCORE.md) y [D07.md](investigacion-1.0.4/D07.md#L5), el `total_score` (0–100) no mejora el orden experimental frente al score de Vina sin transformar: en VMAT2 (`8T69`, `n = 89`) obtiene `ρ = 0,40` vs `0,39` (`Δρ = +0,005`, `IC 95 % [−0,058; +0,061]`, con correlación `0,97` respecto a Vina), y en NET (`8HFI`, `n = 57`) cae a `ρ = 0,03` vs `0,13` (`Δρ = −0,101`, `IC 95 % [−0,334; +0,134]`). Además mezcla afinidad con pesos que pueden degradarse silenciosamente cuando falta algún modelo (`stacking_degraded`).

Pese a ello, hoy en [batch.py](../../backend/api/routers/batch.py):
- `L384`, `L498` (XLSX) y `L591` (CSV) ordenan todas las filas mediante `_orden_exportado` ([batch.py](../../backend/api/routers/batch.py#L447-L452)): `(target, status != "success", stacking_degraded is not False, valor is None, -(valor or 0.0))` **con `valor = resultado.get("total_score")`**,
- mientras en el mismo archivo **`L801` ya cambia automáticamente `ef_metrics` a `basis = "affinity_score" if len(signatures) > 1 else "total_score"`** cuando hay más de una firma de apilado.

### Recomendación concreta de producto

1. **Cambiar la clave primaria numérica de `_orden_exportado` de `total_score` a `affinity_kcal` ascendente (más negativo primero)** dentro de cada diana, conservando la jerarquía de validez:
   - Nivel 1: `target` (no intercalar energías de Vina entre proteínas distintas en un lote multi-diana).
   - Nivel 2: `status != "success"` (corridas válidas primero).
   - Nivel 3: `affinity_kcal` nula al final; finitas ordenadas de más negativa a menos negativa (equivalente a `affinity_score` descendente cuando motor y protocolo coinciden, pero expresado en `kcal/mol` directamente interpretable por el usuario).
   - Nivel 4: `row_id` original de entrada como desempate determinista (eliminando la dependencia de `stacking_degraded` y de `total_score` en el orden de moléculas).
2. **Conservar descriptores como columnas filtrables, no en el índice de orden:** mantener `Affinity_kcal`, alertas/filtros (`PAINS`, `Lipinski`, `QED`, `SAScore`, `Status`), y si se conserva `TotalScore` en `_EXPORT_HEADERS` ([batch.py](../../backend/api/routers/batch.py#L428-L433)) por compatibilidad de hojas externas, renombrar o documentar explícitamente la columna como **índice compuesto heredado no empleado para ordenar**, alineando también `ef_metrics` en `L801` para usar `affinity_kcal` / `affinity_score` en lugar de `total_score`.

---

## Anexo · Procedencia local, SHA-256 y comandos de verificación

### Hashes SHA-256 verificados de los artefactos centrales consultados

| Archivo | SHA-256 |
|---|---|
| `docs/auditorias/investigacion-1.0.4/D09-adjudicacion.json` | `c39f23c79e422fa41c40d3be92f90aea282ab95691593f609dc5a5e8c600071d` |
| `docs/auditorias/investigacion-1.0.4/D09-geometria.json` | `1a1ef5f87935ac100f62e9be37c528734b4b20512011807d01a2324c9d22b3f7` |
| `docs/auditorias/investigacion-1.0.4/D01-resultados.json` | `a8d0f17958178be884b31892fbf35810e0a7cca98ddae218f8f954c7ad1561a7` |
| `docs/auditorias/investigacion-1.0.4/D01-CDK2-resultados.json` | `4c196ca31e5b13bf762606a8edcb4f50fa81cfbba855735ca91d015f30bc7491` |
| `docs/auditorias/investigacion-1.0.4/D04-ChEMBL-banda.json` | `5c9c7dbd25e953fc2df2073df85c9a83a85bb4ab5bfc8f6075f29387411ded4d` |
| `docs/auditorias/investigacion-1.0.4/resultados.json` | `d179a301e1d12269931718f2476595c97927402f57a9381882220b83e7f8918d` |
| `scripts/artifacts_science/DEC-104-D04-CHEMBL/metrics.json` | `90805f48430a157d5d3cd4defb95906e1edd05698b0a2cad5fa9151f964d846d` |
| `backend/data/anti_dianas_bowes44.json` | `d1244f2aaf947afda36eaa8ce0131bf67cbd67199a973be4f8bf4a49eac47a74` |
| `curated_targets.json` | `f66cd263f2a20ac548bf2ee5492e17a28ba04a898c7b6f124bba86c4f24e4593` |

### Comandos para reproducir las comprobaciones locales

```powershell
$inv = 'docs/auditorias/investigacion-1.0.4'
./python-embed/python.exe -B -I "$inv/manifiesto.py" --comprobar
./python-embed/python.exe -B -I "$inv/comprobar_sellos.py" --check
./python-embed/python.exe -B -I "$inv/medir_d09.py"
./python-embed/python.exe -B -I "$inv/comprobar_d04_banda.py"
./python-embed/python.exe -B -I "$inv/comprobar_d07_molchat.py"
./python-embed/python.exe -B scripts/check_docs_links.py --check
```
