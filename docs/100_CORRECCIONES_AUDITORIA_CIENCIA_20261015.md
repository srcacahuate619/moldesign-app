# Correcciones de la auditoría científica — 2026-10-15

**Estado:** abierto.
**Objeto:** registrar cada corrección aplicada a partir del cierre parcial de la
auditoría científica de GPT Sol 6.1, con diagnóstico, decisión, evidencia y la
prueba que la fija.

**Fuente de auditoría:** `D:\moldesign-audits\AUDIT_ciencia_bef67706\`
— cierre parcial, 37 hallazgos (22 S1 `FALSA`, 15 S2 `SOBREAFIRMADA`), todos de
la Fase A; ledger `ledger.json` (SHA-256
`c80693a33c23347fe59caa3a5d72f96001f776b27e54ae8065e912f0e0d1a9c5`).
Encargo: [`encargos/ENCARGO_AUDITORIA_CIENCIA_SOL_20261015.md`](encargos/ENCARGO_AUDITORIA_CIENCIA_SOL_20261015.md).

## Alcance de lo auditado, y lo que no

La auditoría **sólo cubrió la Fase A** (trazabilidad afirmación → medida →
condición) y se cerró a petición del propietario antes de completar su censo:
quedan 65 candidatos sin adjudicar, 109 `NO_VERIFICABLE` y 1124 archivos sin
censar. **Las fases B (validez interna de los sellos), C (cobertura de readiness)
y D (calibración y abstención) no se iniciaron.** Por tanto:

- de aquí no se sigue ningún dictamen de madurez científica ni de factibilidad;
- el silencio de la auditoría sobre un área no es evidencia de que esté sana.

Medido contra la clave sellada de hallazgos conocidos (12 ítems, sellada antes
de enviar el encargo): de los 10 que caían en Fase A abordó 2 o 3. Acertó de
pleno el de PoseBusters sin su protocolo de hidrógenos y mejoró el de ESMFold.
No tocó el falso rechazo del 14,2 % del proxy de validez física, los sellos
`MANTENIDO`, la protonación no determinista, los tiers de Moldex, rígido contra
flexible ni el 41 % de `FEP-02`. Y tuvo delante el de CL-GNN —cita el peso
0.25 del dossier en SCI-A-026— pero lo adjudicó como defecto de traducción.

### Entrega integrada A/A2 + B + C + D (2026-10-20)

La auditoría se completó después. La entrega integrada vive en
`D:\moldesign-audits\AUDIT_ciencia_bef67706\revision_integral\ENTREGA_AUDITOR\`
(`LEEME.md`, `INFORME_INTEGRADO.md`, `LEDGER_VIGENTE.json` con 245 registros). Lo
anterior de esta sección describe el cierre parcial del 2026-10-15 y se conserva con
su fecha.

- **Unidades.** 74 registros de A/A2, 168 de B (sobre 171 sellos, no 187), uno de C y
  dos de D: 244 defectos o límites y una conclusión sustentada. No son 245 fallos
  independientes ni una tasa de error del producto.
- **Coste.** 52 registros C0 (redactar), 174 C1 (código y su prueba), 11 C2 y 3 C3;
  47 son S1.
- **Contra la clave sellada** (SHA-256 `df819a6e…`, sin cambios desde el 2026-10-15):
  unos 10 de 12 ítems vistos, **con los cuatro de peso alto**, así que su silencio sí
  informa. No vio la protonación no determinista (CLAVE-09) ni la comparación de
  scores rígido/flexible fuera de Moldex (CLAVE-11). Corrigió dos premisas de la
  clave: el proxy de validez física emite hoy siempre REVIEW, no un bloqueo
  (CLAVE-03), y los tiers S/A/B/C/D no se montan en ninguna parte: `ScoreCard.tsx`
  no lo importa ningún componente (CLAVE-10).
- **Los 168 registros de B** describen experimentos sellados: se corrigen con notas
  y corrigenda enlazadas, **nunca** editando `scripts/artifacts_science/`
  (restricción 5 de `AGENTS.md`).

El orden de trabajo va de menos a más cómputo: fase 0, textos C0; fase 1, código C1
con su prueba (la transmisión de reservas primero); fase 2, cierre con suite y
puertas; fase 3, `ABS-TR-01` y `MET-01-R1`; fase 4, `CAL-D-01` y los C-GAP de tipo C2.
No se promete un receptor Verificado para 1.0.3 (dictamen de la Fase D).

Seis hallazgos C1 sólo de frontend (SCI-A-009, 012, 013, 015, 066 y 067) se encargaron
a GPT Sol 6.1 en la rama `sol/frontend-auditoria-ciencia`
(`D:\moldesign-worktrees\sol-frontend-auditoria-PROMPT.md`); su entrega se revisa
aquí antes de integrarse.

## Jerarquía de principios

> **CIENCIA > CALIDAD > EFICIENCIA**

- **Ciencia:** honestidad epistemológica. Un número sin su condición es un
  número falso, y un documento que se contradice a sí mismo no transfiere nada.
- **Calidad:** coherencia de contratos y suites verdes y sincronizadas.
- **Eficiencia:** sólo después de lo anterior.

## Metodología por hallazgo

1. **Verificar el hallazgo antes de aceptarlo.** Las auditorías externas aciertan
   y se verifican igual; cada punto se mide en el código, no se cree.
2. Crear la prueba que reproduzca el fallo, y **demostrar que falla sin el
   arreglo** (restricción 2 de `AGENTS.md`: un guardián tiene que demostrar que
   ve).
3. Aplicar el cambio mínimo que cierra el daño.
4. Verificar la suite afectada.

## Registro de versión

Estas correcciones **no entran en** [`versions/1.0.3_cambios.md`](versions/1.0.3_cambios.md):
1.0.3 es un HOT FIX en build, de alcance acotado al render de Molcy, con su
entrega al Store pendiente. Cuando el propietario decida qué versión las lleva,
su registro recibe la entrada correspondiente.

---

## SCI-A-008 — la metodología del informe negaba el veredicto que su matriz registra

**Veredicto de la auditoría:** `FALSA`, S1, C1, confianza ALTA.
**Verificado:** sí, y el defecto era mayor de lo que describe el hallazgo.

### Diagnóstico

El informe de evaluación individual imprimía en su sección «Metodología
observada y procedencia»:

> Validez física: no evaluada en esta versión de producción.

mientras el pie de **esa misma página** declaraba «Estado: REVISIÓN NECESARIA» y
la matriz del documento registraba el veredicto por pose. El validador corre por
pose desde P0-A y su resultado vive en `structural_evidence`.

Lo que convierte esto en un defecto de procedencia y no en una errata: el mismo
documento firma la contradicción con su SHA-256, que la hace parecer verificada.
El comentario de `services/blockchain/evidence_summary.py:275` ya había
diagnosticado exactamente esta frase —«un dossier que declara no evaluado lo que
sí se midió no es prudente: es incorrecto»— y la barrida que la corrigió alcanzó
`_nota_de_validez_fisica` y `evidence_summary`, **pero no este párrafo**, que
estaba impreso a mano.

### Decisión

La frase pasa a ser condicional, con la misma fuente de verdad que la nota
hermana (`evidence_summary["physical_validity"]`), en
`_frase_de_validez_fisica_en_metodologia`:

- **sin veredicto:** se dice que los controles no llegaron a emitirlo y que esa
  ausencia no habla de las poses — ausencia de evaluación no es ausencia de
  choques ni de artefactos;
- **con veredicto:** se nombra el estado que registró la corrida y se remite a
  su cobertura, recordando que superarlo no demuestra validez experimental.

El límite que ya era correcto —que el análisis geométrico externo debe
documentarse antes de un cálculo posterior— se conserva en **las dos** ramas.

### Un segundo defecto que el arreglo habría creado

`traducir` es **todo-o-nada por frase**: si una frase del párrafo no tiene
pareja inglesa, el párrafo **entero** se emite en castellano. El párrafo estaba
cubierto por una sola plantilla completa en `core/i18n_plantillas.py`, así que
condicionar su última frase habría dejado toda la metodología del informe inglés
en castellano — es decir, habría cerrado SCI-A-008 abriendo el defecto que
SCI-A-026 describe.

Por eso la plantilla termina ahora en `{frase1}`, que se traduce aparte: la rama
con veredicto es una plantilla propia (lleva el estado interpolado) y las dos
frases fijas están en `ENGLISH_MESSAGES`.

### Archivos

| Archivo | Cambio |
|---|---|
| `backend/services/blockchain/pdf_generator.py` | `_frase_de_validez_fisica_en_metodologia` y su uso en la metodología |
| `backend/core/i18n_plantillas.py` | la plantilla del párrafo termina en `{frase1}`; plantilla nueva para la rama con veredicto |
| `backend/core/i18n_catalog.py` | las dos frases fijas de la rama sin veredicto y el límite común |
| `backend/tests/test_informe_vs_dossier_identidad.py` | `TestMetodologiaYValidezFisica`, y `_informe(structural_evidence=…)` |

### Verificación

- `TestMetodologiaYValidezFisica`: 6 pruebas, las dos ramas y los dos idiomas.
- **El guardián demuestra que ve:** restaurado el literal, 2 de sus pruebas
  fallan, y la salida del fallo exhibe la contradicción en la misma página
  («Validez física: no evaluada en esta versión de producción … Estado: REVISIÓN
  NECESARIA»).
- `tests/test_informe_vs_dossier_identidad.py`: 20 pasan.
- Subconjunto afectado (`-k "i18n or traduc or pdf or informe or dossier or
  cohort or blockchain or certificad or idioma or bilingue"`): **801 pasan, 1
  saltada**.
- Las pruebas que leen el PDF necesitan `pypdf`, que no viaja en el runtime
  embebido: con python-embed se saltan, como las otras 18 del mismo motivo.

---

## Fase 0 — afirmaciones de README y AGENTS.md (C0)

Todas verificadas contra el código y los sellos antes de corregir. Sin cambios de
código ni de artefactos sellados.

| ID | Qué decía | Qué dice ahora | Verificado contra |
|---|---|---|---|
| SCI-A-001 (S1) | README: «Vina produce y puntúa poses; XGBoost reordena» | Vina ordena; XGBoost y CL-GNN son señales experimentales sin peso; el selector sólo recomienda | `backend/artifacts/sci_config_registry.json` (`policy`), `tests/test_stacking_release_contract.py` |
| SCI-A-064 (S4) | README: «los 167 experimentos sellados» | 171 al 2026-10-20, con `validar_sellos.py --check` como fuente | carpetas con `manifest.json` en `scripts/artifacts_science/` |
| SCI-A-051 (S2) | AGENTS: «no hay una ρ medida contra datos experimentales» | hay un único intento medido, 8HFI, que no superó el protocolo | `backend/data/intentos_de_verificacion.json`, `CAL-8HFI-01/metrics.json` |
| SCI-A-052 (S2) | AGENTS: «Vina no ordena esa serie mejor que el azar» | no se demostró que la ordene mejor; eso no demuestra que no lo haga (potencia ≈ 62 % para ρ = 0,3 con n = 57, Fase D) | `CAL-8HFI-01/metrics.json` (IC [−0,16; 0,41]) |
| SCI-A-053 (S2) | AGENTS: «381 preparadas y 13 no disponibles» | barrido sobre 381 entradas; 13 no disponibles | `backend/data/disponibilidad_catalogo.json` |
| SCI-A-049 (S2) | AGENTS: fila FEP-01 «ninguno declarado» como estado de hoy | fila de línea base fechada y fila nueva de FEP-01-DECL (39 resueltos, 180 declarados) | `FEP-01/metrics.json`, `FEP-01-DECL/metrics.json` |
| SCI-A-050 (S2) | AGENTS: «El código ya declara 1.0.2» | el código declara 1.0.3; los paquetes descritos son los de 1.0.2 | `backend/core/version.py`, `package.json`, `tauri.conf.json`, `Cargo.toml` |

Verificación: las 16 pruebas de backend que leen README o AGENTS y
`test_sbom_inventario.py` (414 pasan, 1 saltada, python-embed);
`check_docs_links.py --check` verde.

### Seguimiento de SCI-A-008 (`73846c43`)

`bad663f9` dejó las dos frases de la rama «sin veredicto» en un único literal. El
catálogo traduce por frase y `scripts/auditar_catalogo_i18n.py` sólo da por viva una
entrada que aparece entera en el código: quedaban dos claves muertas y
`test_catalogo_ingles_sin_defectos.py` fallaba desde entonces. Su verificación filtró
la suite con `-k` y esa prueba no casaba con ninguna palabra. **Lección:** después de
tocar el catálogo, correr `test_catalogo_ingles_sin_defectos.py` por su nombre.

## Fase 0 — CAL-8HFI-01: el paper, el catálogo y la web (C0)

| ID | Qué decía | Qué dice ahora |
|---|---|---|
| SCI-A-017 (S1) | «Las condiciones (pH, temperatura, radioligando) no constan» en el paper, la condición del sello (app y dossier) y su traducción | es un ensayo de desplazamiento de [3H]nisoxetina (las 58 actividades archivadas en `entrada/chembl_activities_CHEMBL853189.json` lo dicen); el pH, la temperatura y la concentración del radioligando siguen sin constar |
| SCI-A-018 (S2) | «Top-1 válidos en PoseBusters: 5 de 5», sin condición | con la reconstrucción de hidrógenos de MF-33-H-COR, que se explica aparte de la neutralización del RMSD |
| SCI-A-044 (S2) | «los microestados se congelaron… sin ninguna desviación» | se congelaron conectividad y carga; el panel no asigna la configuración del nitrógeno protonado (0 de 57 SMILES acoplados llevan `@`) |
| SCI-A-045 (S2) | «el rango de afinidades no es el problema» | el panel cubre 2,88 unidades de pKi y las fuentes no aíslan por qué la ρ es baja |
| SCI-A-052 (S2) | título «no ordena su serie»; «casi como el azar»; «no se distingue del azar»; en la web, «no ordena… mejor que el azar» | no se demostró que la ordene mejor que el azar, y eso no demuestra que no lo haga (potencia ≈ 62 % para ρ = 0,3) |

El paper lleva una sección «Correcciones» fechada. Ninguna cifra cambia y no se tocó
el experimento sellado. `frontend/public/registro/` se regeneró con
`build_registro_cientifico.py` y `site/` con `build_sitio_publico.py`; el código
`CONDICIONES_DEL_ENSAYO_NO_DOCUMENTADAS` se conserva porque sigue siendo cierto para
pH y temperatura. La frase nueva se mantiene en una sola oración para que la traduzca
el catálogo (con dos, el dossier inglés la dejaba en castellano).

Verificación: subconjunto de backend de dossier, catálogo, sellos, i18n, PDF y
blockchain, 877 pasan y 18 saltadas con python-embed; `test_catalogo_ingles_sin_defectos.py`
verde; vitest de catálogo, registro e intentos, 104 pasan; `build_registro_cientifico.py
--check` y `build_sitio_publico.py --check` al día. Una prueba de render
(`TargetSelectorModal.render.test.tsx`) buscaba el texto viejo y ahora exige el
radioligando.

## Fase 0 — SCI-A-074: M5-Zn ya no llama «validados» a sus tres perfiles (C0)

**Veredicto:** `SOBREAFIRMADA`, S2. **Verificado:** sí. Ningún perfil de M5-Zn produce
`VALIDATED` (README, `docs/77`, `gnn_d_prob=None` en el ejecutor), y el producto los
llamaba «los tres perfiles validados» en 21 sitios: la tarjeta de M5 de la pestaña
Evaluación, los motivos de abstención de `m5/zinc.py`, los bloques del dossier, sus
plantillas y su traducción inglesa.

Pasan a ser «los tres perfiles de M5-Zn» («M5-Zn profiles» en inglés), y la tarjeta
dice además que están implementados y en revisión y que ninguno produce hoy
`VALIDATED`. Los códigos de estado (`REVIEW_OUT_OF_VALIDATED_TARGET` y compañía) no
cambian: son contrato. La corrida dorada `dossier_m5_zn.json` se regeneró y su diff son
exactamente esas dos razones.

Verificación: 792 pruebas de backend de M5, i18n, plantillas, dossier y catálogo
pasan con python-embed (20 saltadas); `generate_goldens.py --check`, 8 verificadas;
`ProtocoloM5Zn.test.tsx`, 17 pasan.

**Fuera de alcance, anotado:** las explicaciones de `ProtocoloM5Zn.tsx` están sólo en
castellano (no pasan por `t()`), así que la interfaz inglesa las muestra en castellano.
Es un defecto de i18n previo, no de esta corrección.

## Fase 0 — textos visibles del producto (C0)

| ID | Superficie | Qué decía | Qué dice ahora |
|---|---|---|---|
| SCI-A-029 (S1) | Molcy, escenas Búsqueda y Ensamble (`molcy.ts`) | que **la corrida** no conserva la traza o los datos del ensamble, también cuando lo que falta es el motor que dibuja la escena | que puede faltar la traza o los datos, **o** el motor de esta instalación; no deduce cuál |
| SCI-A-033 (S1) | ayuda de ESMFold en Opciones (`opciones.ts`) | si la geometría no pasa, «la corrida conserva la estructura y se abstiene» | se abstiene **la transferencia**; con caja declarada la corrida sigue con Vina estándar y `MOTOR_SUSTITUIDO` en CRÍTICA, sin caja falla (`peptide_docking.py`) |
| SCI-A-035 (S1) | pie de los avisos sin severidad (`ProAlertsTab.tsx`) | «Corrida anterior a la etapa que declara la severidad», también para avisos que el runner emite hoy como texto | el motor emitió el aviso como texto, sin código ni severidad; pie e insignia pasan por `t()` y tienen inglés |
| SCI-A-014 (S2) | recibo sin procedencia en Moldex (`paginas.ts`) | «Este recibo es anterior al registro de procedencia» | no conserva una referencia verificable a la corrida; no le atribuye antigüedad |
| SCI-A-006 (S2) | alcance del registro en Moldex (`moldex.ts`) | «acredita integridad y fecha de la revisión publicada» | el memo de devnet lleva hash del SMILES, score redondeado, PDB, fecha y wallet (`blockchain.py`, `certifier.py`); no acredita informe, receptor ni poses ni identifica la revisión |
| SCI-A-052 (S2), extensión | intento de calibración en el catálogo (`cat_intento_azar`) | «El orden que da Vina no se distingue del azar en este panel» | no se demostró que sea mejor que el azar; eso no demuestra que no haya asociación |

Prueba nueva: `ProAlertsTab.sinSeveridad.test.tsx` (ES y EN). **Demuestra que ve:** con
el `ProAlertsTab.tsx` anterior, sus 2 casos fallan. Vitest de Molcy, Moldex, Opciones,
avisos, catálogo, intentos y selector de receptores: 33 archivos y 380 pruebas pasan;
`tsc --noEmit` limpio.

**Queda para la fase 1:**
- SCI-A-006, la nota de procedencia del dossier (backend) y `ce_permiso_detalle`.
- SCI-A-037, el margen de selectividad como factor de unión 10x/100x: está en
  `lib/selectividadMargen.ts`, `ProSelectivityPanel.tsx` y su gemelo de backend, con
  pruebas de paridad. No es una redacción local, así que se trata como C1.
- SCI-A-032, `MOTOR_SUSTITUIDO` dice que el servicio «no está disponible» también
  cuando plegó la estructura.

## Fase 0 — SCI-A-021: el paquete ya no atribuye a sus hashes la conservación desde la generación (C0)

**Veredicto:** `SOBREAFIRMADA`, S2. **Verificado:** sí. `verify.py::verificar_paquete`
compara los archivos con el manifiesto y con `checksums.sha256`, los dos **dentro**
del propio ZIP. Eso demuestra coherencia interna, no que nada cambiara desde la
exportación: quien modifique un archivo y regenere el manifiesto y los checksums
obtiene un `VÁLIDO`. Las tres explicaciones del paquete (README, guía de
verificación y PDF del dossier) y su inglés dicen ahora que la conservación frente a
la exportación original sólo se comprueba contra una huella guardada aparte. No se
añade infraestructura nueva.

Verificación: la instantánea española del dossier se reescribió con python-embed
(reportlab 4.2.0); su diff es la frase nueva del README y los hashes de README, PDF
y checksums. 704 pruebas de backend de dossier, paquete, verificación, catálogo e
i18n pasan, con 10 saltadas.

## Fase 0 — documentos históricos que se leían como vigentes (C0)

| ID | Documento | Corrección |
|---|---|---|
| SCI-A-069 (S2, NO_TRAZABLE) | `metricas_experimentales.md` y su cita en `24_OSS_READINESS_CHECKLIST.md` | aviso de histórico no verificado: sus dos productores (`run_5ht1a_benchmark.py`, `calibrate_stacking_weights.py`) no están en el repositorio; no es evidencia de la calibración vigente |
| SCI-A-070 (S2) | `molgraph_v2.md` §3.1 y §7.2 | el 0 % de falsos negativos se **observó** en un ensayo con 0,0 % de descartes, así que no mide el riesgo; se retira la «garantía» |
| SCI-A-072 (S1) | `plan_early_exit.md` §1 | una ρ de Spearman de 0,73 no es «el 73 % de la varianza» ni deja «un 27 % de riesgo de falsos negativos» |
| SCI-A-073 (S2, NO_TRAZABLE) | `MILESTONE_4_USER_VALIDATION.md` | aviso de histórico; se retira «más rápido y preciso que herramientas comerciales» por falta de comparador reproducible. El PDF de entonces no se regeneró: no debe circular |
| SCI-A-071 (S2) | paper `FND-04` y su registro | un MDE al 80 % de potencia no es un «nunca pudo» ni «formalmente indetectable»; la corrección fechada anota además que el propio modelo de potencia está en revisión (SCI-B-002) |

Registro y web regenerados; `build_registro_cientifico.py --check`,
`build_sitio_publico.py --check` y `check_docs_links.py --check` verdes; vitest del
registro verde. De estos documentos, sólo `MILESTONE_4_USER_VALIDATION` (y el deck)
figuran en `scripts/retenidos_del_publico.txt`; `metricas_experimentales.md`,
`molgraph_v2.md` y `plan_early_exit.md` son públicos y llevan ahora su corrección.

## Fase 0 — el deck institucional (C0)

`DECK_EJECUTIVO_INSTITUCIONAL` ya está retenido del repositorio público y su Markdown
ya decía «BORRADOR HISTÓRICO — NO USAR COMO MATERIAL PÚBLICO». Su PDF no lo decía
(SCI-A-002), y nada señalaba cuáles de sus afirmaciones son falsas.

- **Markdown:** una sección fechada, bajo el aviso, con lo que hoy se sostiene de cada
  afirmación auditada (SCI-A-003, 019, 039, 040, 041 y 042). El texto de julio se
  conserva tal cual debajo. Los deltas de la tabla de metaloenzimas no se sustituyen
  por las restas de sus columnas (0,368 y 0,441): eso sería inventar una medida. Se
  declaran irreconstruibles.
- **PDF:** no tiene generador en el árbol, así que se le estampó en las 6 páginas una
  franja con el mismo aviso y la referencia al Markdown
  (`pypdf` 6.14.2 + reportlab 4.5.1). Comprobado: el aviso aparece en el texto de las
  6 páginas y la franja no tapa contenido.

## Fase 0 — corrigenda de los sellos (Fase B, C0)

Los 27 registros C0 de la Fase B más la parte C0 de SCI-B-022 están en
[`101_CORRIGENDA_SELLOS_AUDITORIA_20261020.md`](101_CORRIGENDA_SELLOS_AUDITORIA_20261020.md):
qué deja de valer, qué se conserva, dónde se corrigió y si lo verifiqué aquí (6 sí,
el resto descansa en la evidencia del ledger). Los artefactos sellados no se tocan. Los
16 papers afectados llevan una sección «Correcciones» fechada, y la entradilla de AF-01
deja de atribuir el 0,3626 al estrato equivocado. La nota de 1.0.2 sobre las «2243
parejas ejecutables hoy» lleva su corrección en línea.

Se anota una inconsistencia del propio ledger (SCI-B-031 cita 0,639 y 0,824, cifras que
no están en el paper ni en el sello).

Registro científico y web regenerados; `--check` de registro, web y enlaces verdes;
vitest del registro verde.

## Fase 0 — lo que queda fuera, con su motivo

- **SCI-A-026** (el dossier inglés con condiciones en castellano) es C0 en el ledger,
  pero arreglarlo es traducir y probar plantillas dinámicas del PDF en sus estados con y
  sin datos: se trata como C1, en la fase 1.
- **SCI-A-031** (Molcy no declara el recorte a tres contactos por clase) vive en
  `tools/molcy/`, que no se edita a mano: va al repositorio del motor y se vendoriza con
  `stage_molcy_motor.py`.
- **SCI-A-006** (resto), **SCI-A-032** y **SCI-A-037**: fase 1, como se dijo arriba.

### Cierre de la fase 0: suite completa

- Vitest completo: 224 archivos. La prueba `EmptyDockingCopy.test.tsx` (QA2-014) tenía
  escrito el texto viejo del alcance del registro (SCI-A-006) y se actualizó al nuevo,
  manteniendo lo que comprueba: que el texto sale en el idioma elegido. `tsc --noEmit`
  limpio.
- **Pendiente tras integrar la rama de Sol:** `ALCANCE_DEL_SELLO` en `lib/moldex.ts`
  repite el alcance viejo. Ningún componente lo muestra (sólo `moldexSello.test.ts`), y el
  fichero está reservado a la tarea de Sol para no pisar su diff.
- Backend completo con python-embed sobre `93021c5e`: **4896 pasan, 35 saltadas, 2 xfail,
  0 fallos** (11 min 52 s).

## Revisión de la entrega de Sol (rama `sol/frontend-auditoria-ciencia`, 2026-10-20)

Seis commits sobre `bad663f9`, uno por tarea (SCI-A-009, 012, 013, 015, 066 y 067). Sólo
toca los 13 ficheros que permitía el encargo (8 de producción, 5 de pruebas). Informe en
`D:\moldesign-worktrees\sol-frontend-auditoria-INFORME.md`.

- **Diff revisado a mano**, tarea por tarea: cumple el encargo. Las pruebas nuevas fallan
  contra `bad663f9` (20 fallan y 40 pasan) y pasan con el arreglo (60), con la salida de
  los dos lados en el informe.
- **Lo repetí yo:** `tsc --noEmit` limpio y las 60 pruebas de los 7 archivos afectados
  en verde en su worktree.
- **Casos propios que Sol no vio** (9, ES/EN, en un fichero temporal que se borró después):
  - arrays de objetos con claves permutadas;
  - un elemento de más en un array;
  - calibración igual con target distinto, y calibración vacía;
  - el registro real del backend a pH 7.4 con `cargas_esperadas_ph_7.4`;
  - protonación fallida con motivo;
  - sufijo vacío en el criterio.

  Los 9 pasan.
- **Fusión de prueba** con `claude/auditoria-ciencia-arreglos` en un worktree desechable
  (ya retirado): sin conflictos, `tsc` limpio y vitest completo con **227 archivos y
  2073 pruebas en verde**.
- **Observaciones menores, no bloqueantes:**
  1. el selector de 3Dmol lleva siempre `chain: preferred.chain`; si un átomo no tuviera
     `chain` definido, 3Dmol no lo seleccionaría (el valor sale del mismo modelo, así que
     no se ve en la práctica);
  2. el bloque «No consta cómo se eligió el estado» también aparece cuando la protonación
     no se aplicó;
  3. con `alternativas: 0`, la tarjeta diría «entre 0 enumerados».
- **Sin verificar:** la app de escritorio y WebView2. Lo cubren el smoke y el build de la
  fase 2.

---

# Fase 1 — código con su prueba (C1)

## SCI-A-059 y SCI-A-007 — el estado global del informe conserva el veredicto físico

**Veredictos:** `SOBREAFIRMADA` S2 y `FALSA` S1. **Verificados:** sí, los dos.

### Diagnóstico

`build_evidence_summary` calculaba `needs_review` con los avisos, la preparación del
target, el dominio del modelo, el fallback y la reproducibilidad — **pero no con los
controles físicos**. Una corrida con poses, procedencia y dominio en orden salía
«EVIDENCIA DISPONIBLE» en verde aunque su pose principal fallara los controles de química
o geometría, en el **mismo PDF** cuya matriz imprime ese fallo. El frontend ya lo hacía
bien (`lib/evaluationEvidence.ts`, prueba SOL-05); el backend no tenía el espejo.

Además, un `failed` no tenía entrada propia en las incertidumbres, y la dimensión
`physical` lo aplanaba a `review`, que en el PDF es ámbar: un fallo medido se pintaba con
el color de «queda por mirar».

El segundo defecto es de redacción y es el que hacía falsa la explicación. El agregador
`_estado_de_etapa` devuelve `review` por **dos** causas —la batería no cubrió todas las
poses, o la principal pasa y una alternativa falla— y el texto nombraba sólo la primera.
Así, una corrida cuya alternativa falla se explicaba como «comprobación incompleta».

### Decisión

- `needs_review` incluye `physical_validity["status"] in {"failed", "review"}`.
- Incertidumbre propia para `failed`.
- La dimensión `physical` conserva `failed`, y el PDF le da el rojo que ya usaba para
  `missing`.
- Los textos de `review` nombran las dos causas, en castellano y en inglés.

**Límite declarado:** el vocabulario de `Estado` del dossier no tiene un miembro para «se
midió y falló». Lo más cercano es `REVISAR`, y ampliarlo cambiaría el contrato del
dossier, su PDF y su JSON. `failed` se mapea explícito a `REVISAR` y la observación del
control sí nombra el fallo; un `Estado` propio queda pendiente.

### Un defecto que el propio arreglo creó, y cómo se vio

Al cambiar la redacción, el párrafo **entero** del informe inglés se quedó en castellano.
Las frases viajan por `i18n_plantillas.py` una a una, así que mover el texto sin mover su
par rompe el documento en silencio. Es la misma lección de SCI-A-008. Lo atrapó
`test_dossier_en_ingles_completo.py`, que ya existía.

### Verificación

- `tests/test_estado_global_con_controles_fisicos.py`, 12 pruebas. **El guardián demuestra
  que ve:** con el `evidence_summary.py` anterior, 7 de ellas fallan.
- Subconjunto de evidencia, dossier, informe, PDF, blockchain, i18n, cohorte y lotes:
  **1010 pasan**, 18 saltadas, 1 xfail.
- Instantánea española reescrita con python-embed: su diff son las frases nuevas y sus
  hashes.

## SCI-A-004 — el PDF del lote deja de negar lo que su propio recuento registra

**Veredicto:** `FALSA`, S1. **Verificado:** sí.

### Diagnóstico

`LIMITES_DE_LA_EVIDENCIA` era una tupla constante, y una de sus cinco frases decía que
«las poses de esta cohorte no han superado todavía una validación geométrica/física
automática». El PDF la imprimía **siempre**, también cuando la tabla de la misma página
contaba «· controles superados: 1». El documento se contradecía a sí mismo y firmaba la
contradicción con su SHA-256, igual que hacía el informe individual en SCI-A-008.

### Decisión

El límite de validez física pasa a calcularse desde los veredictos que ya registra el
embudo (`structural_funnel.physical_verdicts`), con tres ramas:

| Situación | Qué dice ahora |
|---|---|
| nadie recibió veredicto | ninguna pose fue evaluada; una afinidad sólo es interpretable tras revisar la pose |
| todas las evaluadas pasan | superaron los controles de esta batería, y superarlos no demuestra actividad ni afinidad experimental |
| hay fallos o revisiones | parte de la cohorte no los superó, con remisión al desglose |

Los otros cuatro límites no dependen de la corrida y siguen siendo constantes. En el
mismo commit entra SCI-A-007 para el lote: «requiere revisión» nombra sus dos causas.

### Claves muertas del catálogo

Al mover las frases, las dos viejas quedaron sin productor y
`test_catalogo_ingles_sin_defectos.py` lo marcó. Se retiraron: una clave muerta es deuda,
y los paquetes ya exportados llevan su texto dentro, no lo retraducen desde el catálogo.
La de «requiere revisión» tenía **tres** copias en el fichero. Borrarlas por líneas rompió
una entrada multilínea, así que se hizo con `ast`, que sí conoce dónde empieza y acaba
cada par; el catálogo pasó de 1672 a 1671 entradas, que es la que las tres copias
compartían.

### Verificación

- `tests/test_limite_fisico_del_lote.py`, 9 pruebas, y `test_lote_en_ingles.py`
  parametrizado por las tres ramas, para que ninguna se quede sin inglés.
- **El guardián demuestra que ve**: con el `evidence.py` anterior la prueba ni siquiera
  importa, porque el helper no existía. Que el defecto estaba se comprueba leyendo la
  constante del commit anterior con `ast`: sus cinco límites incluyen la frase
  incondicional.
- Subconjunto de cohorte, lotes, evidencia, dossier, PDF, i18n y catálogo: **1009 pasan**,
  18 saltadas.

## SCI-A-027 — Molcy deja de exportar como «no evaluados» controles que sí se midieron

**Veredicto:** `FALSA`, S1. **Verificado:** sí.

### Diagnóstico

`controles_de` exigía `stage_status == "passed"` para conservar **cualquier** control de
la pose. Si la etapa quedaba en `review` o en `failed`, devolvía `None` y el vídeo
rotulaba «CONTROLES FÍSICOS: NO EVALUADOS». Es decir: una corrida cuya pose principal
falló se presentaba como una corrida que nadie midió.

Esa confusión es la que el producto existe para no cometer. `failed` describe la pose;
`not_evaluated` describe al validador, y el propio repositorio ya lo tenía escrito: «las
filas `failed` y `not_evaluated` no son evidencia negativa sobre sus moléculas: describen
lo que le pasó al motor».

### Decisión

El veredicto de la etapa deja de decidir si los controles se exportan. Lo que decide es la
**identidad**: mismo receptor, mismo rango, misma afinidad — las tres comprobaciones que
ya existían y no se tocan. El estado por pose viaja tal cual (`passed`, `failed`,
`review`, `not_evaluated`), con sus fallos nombrados.

La lista de estados de etapa admitidos es **blanca**, tomada de `STAGE_*`: de un estado
que no se sabe leer no se exportan controles. Así el caso `abstained` que ya cubría la
suite sigue devolviendo `None`.

### Verificación

- 4 pruebas nuevas en `tests/test_molcy_ensamble.py`. **El guardián demuestra que ve:**
  con el `ensamble.py` anterior, 3 de ellas fallan.
- Todas las pruebas de Molcy: **573 pasan**, 2 saltadas.

**Pendiente, fuera de este arreglo:** el rótulo de `tools/molcy/scripts/guiones/y.py` que
escribe «NO EVALUADOS» vive en el motor, que se vendoriza desde su propio repositorio y no
se edita a mano. Con este cambio ya recibe el estado real, pero conviene revisar allí que
cada veredicto tenga su rótulo (es el mismo camino que SCI-A-031).

## SCI-D-002 — el filtro de Verificados rechaza resúmenes incoherentes con su protocolo

**Veredicto:** `SOBREAFIRMADA`, S2. **Verificado:** sí, con los tres contraejemplos del
hallazgo.

### Diagnóstico

`supera_el_protocolo` comprobaba que los campos existieran y algunos umbrales, pero no que
el resumen describiera el protocolo declarado ni una correlación posible. Aceptaba:

- **3 de 100 semillas**, porque sólo exigía `semillas >= 5`. El protocolo fija cinco;
  3 aciertos de 100 intentos no es el 3 de 5 que declara.
- **ρ = −0,8 con IC [0,1; 0,5]**: el resumen se contradice en el mismo signo que el gate mira.
- **IC [1,1; 1,3]**, fuera del dominio de cualquier correlación.
- `n: true`, porque en Python `True` es un `int`.

El espejo del frontend (`lib/seccionCatalogo.ts::superaElProtocolo`) tenía los mismos huecos.

### Decisión

Cinco semillas exactas; ρ e IC finitos y en [−1, 1]; ρ > 0 cuando el IC ya la da por
positiva; enteros que no sean booleanos. **No** se exige que el IC contenga la ρ puntual:
un bootstrap percentil no lo garantiza, y la auditoría tampoco lo pide. Si algún día se
amplían las semillas, se cambia antes el protocolo.

Esto es una comprobación de formato y coherencia, no un recálculo de la ciencia: una
entrada real sigue necesitando la revisión del protocolo sellado (el guardián del archivo
vacío no cambia).

### Verificación

- `test_seccion_catalogo.py`: 9 casos nuevos y un control (IC que no contiene la ρ, se
  acepta). **Demuestra que ve:** con el `seccion_catalogo.py` anterior fallan 8 (el
  noveno, `semillas_rmsd_ok: true`, ya lo rechazaba el umbral de 3).
- `seccionCatalogo.test.ts`: 5 casos nuevos; con el `.ts` anterior fallan los 5.
- Backend `-k "catalogo or intentos or verificad or calibracion"`: 275 pasan, 4 saltadas.

## Integración de la rama de Sol (`046bd598`)

`sol/frontend-auditoria-ciencia` se fusionó en esta rama sin conflictos: SCI-A-009, 012,
013, 015, 066 y 067 quedan integrados con la revisión de arriba.

## SCI-A-006 (resto) y SCI-A-058 — el memo y su verificador dicen sólo lo que el memo lleva

**Veredictos:** `SOBREAFIRMADA` S2 los dos. **Verificados:** sí.

### SCI-A-006, lo que quedaba de la fase 0

El memo de devnet es `MolDesign-v1|CC0|<hash del SMILES>|<score>|<PDB>|<fecha>|<wallet>`
(`blockchain.py`, `certifier.py::_build_memo`): ningún hash del informe. Tres textos le
atribuían más:

| Superficie | Decía | Dice |
|---|---|---|
| Nota de procedencia del dossier (`evidence_summary.py`, y su inglés) | «Un registro en cadena certifica CUANDO se emitió el documento» | el memo guarda sus campos, con una fecha declarada por quien firma; no identifica la revisión del documento ni acredita su fecha de emisión |
| Permiso de red de certificación (`ce_permiso_detalle`, ES/EN) y destino `solana-devnet` de `services/ai/red.py` | «saldrían la huella del expediente y sus metadatos mínimos» | saldrían los campos del memo, que se enumeran; ningún hash del informe |
| `ALCANCE_DEL_SELLO` (`lib/moldex.ts`) | el alcance viejo, que la fase 0 ya había corregido en `mx_alcance_registro` | el mismo texto que la ficha muestra; una prueba los ata |

### SCI-A-058

`_parse_memo` aceptaba cualquier primer campo que **empezara** por «MolDesign»
(`MolDesign-v9`, `MolDesignX`), y `_parse_timestamp` caía a `datetime.now()` si la fecha no
se podía leer: `/verify` devolvía «verified» con una fecha que nadie había escrito.

- Sólo se aceptan los dos esquemas emitidos: `MolDesign-v1|CC0|…` y el anterior
  `MolDesign-CC0|…`, con 4 o 5 campos detrás.
- Fecha ISO 8601 o rechazo. Las fechas sin zona (los memos de `utcnow()`) se leen como UTC,
  que es lo que eran.
- `BlockchainRecord.block_time`: la fecha del bloque (`blockTime`), aparte de la declarada.
- `/verify` responde `status: "memo_verified"`, con `declared_timestamp` y `block_time`, y
  un mensaje que dice que acredita los campos del memo y no es un aval científico ni
  institucional. Ningún componente leía `status`.

### Verificación

- `test_certifier.py`: 10 pruebas nuevas; **con el código anterior fallan 9** (la décima
  es el esquema `CC-BY`, que ya fallaba por otra razón).
- `moldexSello.test.ts`: 2 nuevas (no dice «acredita integridad»; es el texto de la ficha).
- Backend `-k "certif or blockchain or consentimiento or red or procedencia or dossier or
  evidence or i18n or catalogo"`: **916 pasan**, 10 saltadas;
  `test_catalogo_ingles_sin_defectos.py` verde; instantánea española reescrita con
  python-embed (su diff es la nota).

## SCI-D-001 y SCI-A-005 — «calibrado» exige n, intervalo y protocolo

**Veredictos:** `SOBREAFIRMADA` S2 los dos. **Verificados:** sí.

### Diagnóstico

`estado_de_calibracion` emitía `CALIBRADO`, sin advertencia, para cualquier `spearman_rho`
no nulo en [−1, 1] de la fila del receptor, y `_calibration_controls` lo convertía en
«PASA: el ranking del motor está calibrado para este receptor». Ese número no dice con
cuántos ligandos se midió, con qué intervalo, contra qué ensayo ni con qué protocolo. Hoy
no hay ningún receptor con ρ distinta de cero, así que el defecto no se manifestaba: era
una puerta abierta.

Moldex (SCI-A-005) publicaba `target.spearman_rho` como «Correlación del benchmark», y los
dos únicos valores del catálogo son el `0.0` por defecto.

### Decisión

- `CALIBRADO` sale sólo de `respaldo_de_calibracion`: la entrada de Verificados del
  receptor, que tiene que superar `supera_el_protocolo` (SCI-D-002). El estado lleva ahora
  `respaldo` (ρ, IC 95 %, n, panel, endpoint, protocolo, hash del receptor) y, aparte,
  `rho_registrada_sin_respaldo`: lo que dice la fila, conservado pero sin conceder nada.
  `spearman_rho` es sólo la ρ respaldada.
- `rho_es_utilizable` pasa a ser condición necesaria, no suficiente.
- El control de la comprobación previa sólo pasa con la medida, y la nombra (n, IC,
  panel, y el protocolo con el que se midió). Un diccionario que diga «calibrado» sin
  medida da advertencia.
- El dossier imprime ρ, IC y n. Las frases nuevas tienen inglés (plantillas); la frase
  vieja del control salió del catálogo.
- Moldex: `spearman_rho` respaldada y el estado completo (`calibracion`). La ficha dice
  «Sin calibrar: no hay una ρ medida con n, intervalo y protocolo» salvo que llegue la
  medida, y el rótulo deja de llamarse «benchmark».
- En el frontend, `RespaldoDelReceptor` advierte ante un «calibrado» sin su medida y
  `ReproducibilityInfo` deja de enseñar la ρ cruda de la fila.

**Límite declarado:** la medida se lee del archivo de Verificados vigente, no de la
instantánea del receptor de la corrida. Con el archivo vacío no cambia nada para ninguna
corrida guardada; si algún día entra un receptor, una corrida anterior lo vería calibrado.
Atar el sello a la corrida es lo que ya hace `catalogo_de_la_corrida` con `sin_declarar`
y `difiere_en`.

### Verificación

- `test_calibracion_de_receptores.py`: 25 pruebas (8 nuevas o reescritas). **Con el código
  anterior fallan 7.**
- `test_moldex_procedencia.py`: 2 casos nuevos (ρ 0.0 y 0.61 sin respaldo); con el
  `moldex.py` anterior fallan los 2.
- `RespaldoDelReceptor.test.tsx`: 1 nueva y 2 actualizadas; con el componente anterior
  fallan 2. `moldexSello.test.ts`: 4 nuevas para `calibracionDeLaFicha`.
- Dos pruebas que daban por calibrado un receptor con ρ suelta se reescribieron: el dossier
  inglés (`test_dossier_en_ingles_completo.py`) y MolChat
  (`test_la_advertencia_de_calibracion_no_se_pierde.py`) inyectan ahora una entrada de
  Verificados, y MolChat tiene un caso nuevo con ρ suelta que sí avisa.
- Instantánea española reescrita con python-embed: el fixture tiene `spearman_rho=0.512`
  sin medida, así que su línea pasa de «Calibrado … ρ = 0.512» a «Sin curar …», y aparece
  la advertencia correspondiente. Es el cambio buscado.
- Backend `-k "calibra or moldex or preflight or dossier or catalogo or i18n or target or
  molchat or submission or report or pdf"`: **932 pasan**, 18 saltadas;
  `test_catalogo_ingles_sin_defectos.py` verde. Vitest de `components`, `lib` y `app`:
  207 archivos, 1940 pruebas; `tsc` limpio.

## SCI-C-001 — un puente disulfuro sin plantilla queda «no evaluado»

**Veredicto:** `SOBREAFIRMADA`, S2. **Verificado:** sí.

### Diagnóstico

`_disulfuros` marcaba roto un puente sólo si una de sus cisteínas tenía plantilla `CYS`. Una
plantilla **ausente** daba el mismo «no roto» que una `CYX`. El camino C con origen escribe
`protonation_templates = {}`, así que, con un par S–S candidato, Preparación emitía
`REGISTRADO` y «ninguno queda como tiol libre en el receptor» sin que nada lo hubiera
comprobado. Y un PDBQT sin origen escribe ahí un motivo en texto, no un diccionario.

### Decisión

Cada puente candidato por geometría cae en uno de cuatro casos:

| Caso | Resultado |
|---|---|
| alguna cisteína con plantilla `CYS` | roto (`REVISAR`, como antes) |
| las dos con `CYX` (o sus variantes terminales) | conservado |
| las dos fuera del receptor, comprobado sobre el PDBQT de la corrida | no cuenta (no deja SH en la cavidad; el recorte se declara aparte) |
| cualquier otro (sin plantillas, parciales, receptor ilegible) | **sin evaluar** |

Con algún puente sin evaluar y ninguno roto, el requisito sale `NO_EVALUADO`, con los
puentes nombrados y la razón: no se sabe si el receptor conserva el enlace. La proximidad
S–S se conserva como dato. Un `protonation_templates` que no sea diccionario se lee como
vacío. Castellano e inglés.

### Verificación

- `test_disulfuros_sin_plantilla.py`, 8 casos (CYX/CYX, CYS, sin plantillas, parcial,
  variantes terminales, puente fuera del receptor, receptor desconocido). **Con el código
  anterior fallan los 8.**
- `test_preparacion_desde_el_ligando.py`: 2 casos nuevos del requisito (ES/EN).
- Backend `-k "prepar or contexto or disulf or dossier or propio or camino or hidrogeno or
  i18n"`: **727 pasan**, 10 saltadas; catálogo inglés verde.
- No verificado con Vina real por el camino C: la regla se prueba sobre la función que lo
  decide, con las plantillas que ese camino escribe.

## SCI-B-016 — la validez física de los experimentos exige la batería entera

**Veredicto:** `SOBREAFIRMADA`, S2. **Verificado:** sí, con las tres respuestas simuladas
de la auditoría: `posebusters_metrica.evaluar_pose` da `pb_valid_fisica = True` con cero
checks físicos, con una carga fallida y con un check en NaN.

### Diagnóstico

`scripts/posebusters_metrica.py::evaluar_pose` emite `pb_valid_fisica = len(fallan) == 0`
sobre los checks **booleanos** que haya. PoseBusters devuelve NaN cuando no puede evaluar un
check (sin conformero, UFF sin parámetros, receptor que no carga), y la envoltura lo
descarta en silencio; los `*_loaded` no cuentan; y una fila sin checks físicos da True. El
validador del producto (`pose_physical_validity.py`) no tiene este defecto: ya clasifica
NaN como `NO_EVALUADO`.

### Un primer arreglo que rompía nueve sellos

El primer commit (`bd725342`) corrigió `posebusters_metrica.py` en sitio. **Es código
productor sellado**: MF-33-PB, MF-33-H-COR, MF-33-MIN, MF-33-TOP1 y cinco prerregistros
guardan su SHA-256, y `validar_sellos.py --check` dio 9 `DISTINTO`. Es el mismo caso que
`redock_pdbbind.py`, que no se reescribe porque respalda procedencia sellada. El commit
siguiente lo devolvió a sus bytes (los 171 sellos vuelven a validar, 0 distintos) y movió
la regla.

### Decisión

- `scripts/posebusters_veredicto.py` (nuevo) tiene la regla y una `evaluar_pose` que la
  aplica; reutiliza la carga de PoseBusters del módulo viejo.

  | Fila | `pb_valid_fisica` |
  |---|---|
  | algún `*_loaded` no es True | `None`, motivo `carga_fallida:…` |
  | ningún check físico | `None`, motivo `sin_checks_fisicos` |
  | algún check físico en False | `False` (un fallo medido es un fallo, aunque falte otro) |
  | algún check físico sin evaluar | `None`, motivo `bateria_incompleta`, con `checks_sin_evaluar` |
  | todos evaluados y en True | `True` |

- `posebusters_metrica.py` queda intacto, con su defecto, porque describe cómo se midió lo
  sellado. **Un guardián** impide que un script que no sea ya productor sellado lo importe:
  un experimento nuevo tiene que usar el módulo nuevo.
- La parte C0 —las tasas de los sellos medidos con la regla vieja— está en `docs/101`; no se
  recalculó nada.

### Verificación

- `scripts/tests/test_posebusters_metrica_cobertura.py`, 15 pruebas: las tres respuestas de
  la auditoría y sus dos controles (fallo físico, fallo sólo de RMSD), NaN y `None`,
  booleanos de numpy, la función pública con un PoseBusters simulado, que el módulo viejo
  **sigue** dando True en los tres casos y el nuevo `None`, y el guardián de importadores con
  su autotest.
- `validar_sellos.py --check`: 171 sellados, 4278 ficheros verificados, 0 distintos, 0
  ausentes.

## SCI-A-068 — una lista de cofactores vacía no es una lista «no registrada»

**Veredicto:** `FALSA`, S1. **Verificado:** sí.

La metodología del informe imprimía «cofactores: sin whitelist registrada» tanto si la
corrida **registró una lista vacía** (`receptor_prep.cofactors_whitelist: []`, una decisión:
no se conservó ningún cofactor) como si no registró nada. `_cofactores_de_la_corrida`
devolvía `[]` en los dos casos y la nota no podía distinguirlos. Además, cuando la lista
venía de la diana, el informe no decía que no era la de la corrida.

`_nota_de_cofactores` sustituye al helper y separa presencia y contenido:

| La corrida… | Nota |
|---|---|
| registró una lista con elementos | los elementos |
| registró una lista vacía | «ninguno conservado (la corrida registró una lista vacía)» |
| no registró la lista, y la diana declara una | «lista de la diana (la corrida no registró la suya): …» |
| no registró nada, y la diana tampoco | «la corrida no registró la lista de cofactores» |

Con inglés (catálogo y una plantilla). Verificación: `test_pdf_cofactores_de_la_corrida.py`
reescrita, 7 pruebas (la de «vacía y ausente ya no dicen lo mismo» falla por construcción
con el helper anterior); `test_metodologia_validez_fisica.py` y catálogo inglés verdes;
backend `-k "pdf or informe or certific or cofactor or dossier or i18n"`: 531 pasan, 18
saltadas.

## SCI-A-028 — el PDB visual de Molcy conserva el elemento de los iones

**Veredicto:** `FALSA`, S1. **Verificado:** sí.

`services/molcy/package.py::pdbqt_a_pdb` tenía su propio mapa de tipos AutoDock, **sin
metales** y en mayúsculas. Un tipo que no conocía caía a la primera letra del nombre del
átomo: el `Fe` conservado de la evidencia de la auditoría salía como `F`, flúor, en el
`prepared.pdb` que lee el motor. Y al pasar a mayúsculas, `NA` (nitrógeno aceptor) y `Na`
(sodio) eran el mismo tipo.

Ahora el elemento sale de `preparer_propio.elemento_de_tipo` —el decodificador que ya usan
el resto del producto y el router de interacciones—, leyendo el tipo por columnas
(`pdbqt_propio._tipo`) y distinguiendo mayúsculas. Un tipo que no conoce no se inventa: la
columna queda vacía y el tipo se declara en `scene.json` (`declarado.tipos_sin_elemento`).

Verificación: `test_molcy_elemento_del_ion.py`, 9 pruebas (Fe, Zn, Mg, Ca, Na y K
conservados; N aceptor; tipo desconocido; declaración en la escena). **Con el `package.py`
anterior fallan 8.** Todas las de Molcy (`-k molcy`): 582 pasan, 2 saltadas.

**Pendiente, en el motor:** `tools/molcy/scripts/nucleo/receptor.py` carga ese PDB con
Molecular Nodes; con el elemento correcto lo dibuja bien, pero no se ha comprobado en un
render.

## SCI-A-025, SCI-A-024 y SCI-A-038 — la generación 3D que dice el dossier es la que ocurrió

**Veredictos:** `FALSA`, S1, los tres. **Verificados:** sí.

### Diagnóstico

- **A-025.** El campo «Generación conformacional» escribía siempre «Confórmero único (ETKDG
  + MMFF94)». `chem/conformer.py::_optimize_with_mmff` cae a UFF cuando MMFF94 no
  parametriza la molécula y a una geometría sin optimizar si UFF también falla, y lo registra
  en `ligand_state.conformero` (`estrategia_embebido`, `campo_fuerza_final`,
  `optimizacion_convergida`). Nadie lo leía. La nota del ensamble de Molcy repetía «(ETKDG +
  MMFF)» para todas las conformaciones, aunque las que no parametriza MMFF entran sin
  minimizar.
- **A-024.** La piscina del ensemble se contaba como `conformaciones × num_poses`: el máximo
  solicitado, no las poses que devolvió Vina (que puede dar menos modos) ni las de una
  conformación que no se acopló. El recuento real está en
  `execution_provenance.por_conformacion[].num_poses`.
- **A-038.** Si el ensemble fallaba, `_generar_conformaciones` seguía con un confórmero sin
  decir cuántos se habían pedido; el protocolo sellaba 1 de 1 y el dossier escribía
  «Confórmero único · REGISTRADO».

### Decisión

- `_metodo_conformacional` deriva el método del registro: «ETKDGv3 + MMFF94» (REGISTRADO);
  UFF, sin converger o sin optimizar se nombran y dan REVISAR; sin registro, «método no
  registrado por la corrida» (REVISAR). Nada atribuye MMFF94 a lo que no lo usó.
- El fallback del runner devuelve `conformers_requested = K` y `conformers_generated = 1`, y
  el dossier dice «Confórmero único (…) · se pidieron K conformaciones» con REVISAR.
- La piscina suma `por_conformacion[].num_poses`; sin ese recuento dice «hasta K×N candidatas
  (recuento no registrado)».
- Cada conformación del ensemble lleva su `minimizacion` (MMFF94, UFF, `sin_minimizar`; la 0,
  lo que registró el conformador) por `por_conformacion` y el contrato del ensamble hasta el
  acta de Molcy; la nota del motor deja de atribuir MMFF a todas.
- Inglés de todo, y de paso el fragmento « · pose elegida entre N candidatas», que se quedaba
  en castellano dentro del `{n3}` de la plantilla genérica (una parte de SCI-A-026): las dos
  formas completas tienen ahora plantilla propia, antes de la genérica.

### Verificación

- `test_generacion_conformacional_declarada.py`, 16 pruebas (métodos, inglés, fallback del
  runner, piscina medida y máxima, propagación de `minimizacion`). **Con el código anterior
  fallan 9 de las 14 primeras.**
- `test_piscina_del_ensemble_en_el_dossier.py` sigue verde sin tocarlo: sin recuento medido la
  cifra sigue apareciendo, ahora como máximo.
- Backend `-k "dossier or conform or ensemble or i18n or catalogo or runner or pipeline"`:
  704 pasan, 12 saltadas; `-k "ensemble or ensamble or conformer or molcy"`: 755 pasan.

## SCI-A-030, SCI-A-031 y SCI-A-027 (motor) — Molcy

**Veredictos:** `FALSA` S1 (A-030) y `SOBREAFIRMADA` S2 (A-031). **Verificados:** sí.

Viven en `tools/molcy/`, que no se edita a mano. Se arreglaron en el repositorio del motor,
rama `claude/auditoria-ciencia` (worktree `D:\moldesign-worktrees\motor-auditoria`, desde
`411a92a`, el commit vendorizado hasta hoy), commits `7e8c89e` y `3f8bb14`, y se vendorizaron
con `stage_molcy_motor.py --fuente … --write`.

- **A-030.** `mapa_de_residuos` usaba como clave sólo el número de residuo y ganaba el primero:
  en un receptor de dos cadenas con la misma numeración, un contacto con B:ASP1 salía rotulado
  «ALA1:B». Ahora la clave es (cadena, número); un mismo (cadena, número) con dos nombres
  (códigos de inserción, que Molecular Nodes no distingue) queda «?». La función pasó a
  `interacciones` (sin `bpy`), así que se prueba sin Blender.
- **A-031.** El rótulo «POLARES 3 | APOLARES 3» de las escenas Búsqueda y Ensamble contaba los
  contactos **dibujados**, recortados a tres por clase. Ahora dice «DIBUJADOS (MAX. 3 POR
  CLASE)» encima del recuento.
- **A-027, lado del motor.** Con el exportador arreglado llegan los cuatro veredictos. «NO
  EVALUADOS» queda para lo que el validador no midió; una batería parcial dice cuántos
  controles quedaron sin evaluar y una revisión sin fallos dice «REVISION NECESARIA».

Verificación: `scripts/pruebas/test_auditoria_ciencia.py` del motor, 12 pruebas; con el motor
anterior fallan 8 (las otras 4 son controles que ya pasaban). Suite del motor: 234 pasan, 1
saltada. En MolDesign, `stage_molcy_motor.py --check` íntegro (63 ficheros,
`claude/auditoria-ciencia@3f8bb14a`), `test_frontera_motor_molcy.py` 10 y
`test_stage_molcy_motor.py` + `test_verify_molcy_motor.py` 46.

**Bloqueante antes de cualquier instalador:** la rama del motor **no está empujada** al
repositorio público, y la GPL pide que `fuente.commit` exista allí. Empujarla es una acción
pública que decide el propietario. Tampoco se comprobó en un render de Blender.

## SCI-A-036 — «Poses solicitadas al motor» es lo que selló la corrida

**Veredicto:** `FALSA`, S1. **Verificado:** sí.

El campo de la sección de generación tomaba `config.num_poses`, la configuración del caso,
que es otro objeto y puede cambiar después de ejecutar: con el caso en 18 y la corrida en 9,
el dossier atribuía 18 a la corrida con `REGISTRADO`. Ahora sale de
`docking_protocol.num_poses`; sin protocolo queda ausente con su razón, y lo declarado por el
caso sigue aparte («Poses declaradas por el caso», `REVISAR` si difiere).
`test_poses_solicitadas_son_las_de_la_corrida.py`: 2 pruebas; con el código anterior fallan
las 2.

## SCI-A-023 — el resumen no niega un ensemble que el protocolo registra

**Veredicto:** `FALSA`, S1. **Verificado:** sí.

El detalle del muestreo terminaba siempre en «No se registraron réplicas ni ensemble», en el
backend (`evidence_summary.py`), en el espejo del frontend (`evaluationEvidence.ts`) y en los
límites del panel de evidencia, también cuando el protocolo de la misma corrida registra un
ensemble de K conformaciones. La frase sale ahora de `docking_protocol.conformers_generated`
(`frase_de_muestreo` / `fraseDeMuestreo`): ensemble de K, confórmero único, o «el protocolo no
informa si hubo ensemble». Las réplicas independientes no las registra ninguna corrida hoy, y
se sigue diciendo. Inglés en plantillas del backend y en `pro.ts`; la clave
`pr_ev_overview_no_replicates` sale.

Verificación: `test_estado_global_con_controles_fisicos.py`, 3 casos nuevos;
`muestreoDeclarado.test.ts`, 3. Instantánea española reescrita con python-embed: el fixture
no registra conformaciones, así que su frase pasa a «El protocolo no informa si hubo ensemble;
no se registraron réplicas». Backend `-k "evidence or dossier or i18n or catalogo or informe or
pdf or resumen"` verde salvo la instantánea, ya reescrita; vitest de `lib` y
`components/interfaces/pro` verde; `tsc` limpio.

## SCI-A-034 y SCI-A-032 — ruta peptídica: el SDF y el motivo de la sustitución

**Veredictos:** `FALSA`, S1, los dos. **Verificados:** sí.

- **A-034.** `peptide_docking.py` y su gemelo de `queue_handler.py` escribían el SDF de poses
  con **todas** las conformaciones del servicio y después construían el resultado sólo con
  las que tenían afinidad de Vina. El aviso decía «se descartaron del resultado», pero la
  descarga «SDF de poses de docking» seguía llevándolas. Ahora `poses_acopladas_y_sdf` decide
  una sola colección: una pose entra en el resultado y en el SDF, en el mismo orden, o en
  ninguno (también si su geometría no se puede escribir). Sin poses acopladas no se escribe
  SDF peptídico: el camino de sustitución escribe el suyo.
- **A-032.** `aviso()` devuelve un **diccionario** (`Aviso.a_dict()`), y los dos caminos leían
  su código con `getattr(a, "codigo", None)`, que en un diccionario es siempre `None` (lo
  comprobé: `dict None`). El aviso de sustitución decía, pues, «Sin respuesta del servicio» y
  «ese servicio no está disponible» también cuando el servicio había plegado la estructura.
  `motivo_de_la_sustitucion` distingue tres causas —plegó sin acoplar, respondió con un error
  (p. ej., transferencia rechazada), no respondió— y `MOTOR_SUSTITUIDO` dice «el servicio
  respondió, pero …» en las dos primeras. El aviso no tenía inglés; ahora sí, con la causa.

Verificación: `test_peptidos_sdf_y_motivo_de_sustitucion.py`, 8 pruebas (con el código
anterior ni siquiera importa: los helpers no existían; el defecto del `getattr` se comprueba
en una línea, arriba). `test_peptide_docking.py` y el catálogo inglés verdes; backend `-k
"peptid or avisos or golden or dorad or queue"`: 240 pasan. **No verificado con ESMFold
real**: el sidecar no está instalado en esta máquina.

## SCI-A-020, 043, 046, 047 y 048 — sin anotación curada, el informe no afirma una función

**Veredictos:** `FALSA` S1 (020, 046, 047, 048) y `SOBREAFIRMADA` S1 (043). **Verificados:**
sí, sobre los cinco depósitos que cita la auditoría (versionados en `data/targets/`). Con el
`certificate_context.py` anterior:

| PDB | Qué es | Qué decía el informe |
|---|---|---|
| 3ERT | receptor nuclear de estrógenos | GPCR o receptor transmembranal |
| 5TOL | BACE1, aspartil proteasa | proteína quinasa (`FRAGMENT: KINASE DOMAIN`) |
| 1BN1 | anhidrasa carbónica II (LYASE) | hidrolasa / proteasa (`MPRO` dentro de `IMPROPER`) |
| 6E53 | transcriptasa inversa de la telomerasa | canal iónico (`POTASSIUM CHLORIDE` del REMARK 280) |
| 1SM3 | anticuerpo con su epítopo | hidrolasa / proteasa |

`generate_physiological_context` clasificaba por subcadenas sobre el PDB **entero**, y el
PDF lo usaba cuando la descripción del catálogo era genérica. Ya no clasifica: devuelve
«Contexto fisiológico no disponible: el receptor no tiene una anotación funcional curada» y
conserva como dato lo que el depósito declara —clasificación del `HEADER` y `TITLE`
(recortado a 160 caracteres)—, sin leer nunca los REMARK, el COMPND ni las condiciones de
cristalización. La descripción curada del catálogo, cuando existe, sigue mandando. Las
cinco frases de clase y la genérica salieron del catálogo; las nuevas tienen inglés.

Verificación: `test_certificate_context.py` reescrita, 16 pruebas (los cinco depósitos
reales, REMARK/COMPND que ya no se leen, sin encabezado, título largo, inglés). Las pruebas
anteriores fijaban precisamente la clasificación por palabras («keeps existing
classification», «preserves keyword priority») y se retiraron. Backend `-k "pdf or certif or
informe or i18n or catalogo or context or dossier"` verde; catálogo inglés verde.

## SCI-A-010 y SCI-A-011 — Moldex: hotspots no evaluados y afinidades heredadas

**Veredictos:** `SOBREAFIRMADA`, S2, los dos. **Verificados:** sí.

- **A-010.** `None` significa «no evaluado» y `[]` «evaluado sin aciertos» (`core/models.py`),
  pero tres eslabones los igualaban: el repositorio guardaba `[]` cuando el docking no había
  evaluado hotspots, la API publicaba `res.hotspots_hit or []` y la ficha normalizaba a `[]`
  y escribía «0/N tocados». Ahora `None` viaja de la persistencia a la ficha, que dice «— no
  evaluado»; una lista vacía sigue siendo un cero. Y `"[]"` en texto ya no se lee como
  `None` en `EvaluationResultRead` (la coerción genérica lo hacía). Los ceros históricos no
  se reinterpretan: no se sabe si se midieron.
- **A-011.** Antes de la v16 del esquema, `affinity_kcal` podía contener la regresión de
  XGBoost escrita encima del score de Vina (`core/database.py`), y la ficha la rotulaba
  «Afinidad calculada (Vina)». `_origen_de_la_afinidad` sólo acredita Vina si la corrida
  guarda versión de Vina y poses y la afinidad coincide (±0,005) con la mejor de ellas; si
  no, «Afinidad heredada (origen no acreditado)». El número se conserva.

**Un defecto que se habría colado:** el modelo de respuesta de `/moldex` (`MoldexTargetRead`,
`MoldexMetricsRead`, `MoldexMoleculeRead`) **filtra** los campos que no declara, así que
`calibracion` (SCI-A-005) y `affinity_origin` no habrían llegado a la interfaz por HTTP, y
`hotspots_hit: None` daba un 500. La prueba de A-005 llamaba a la función directamente y no
lo vio. Los tres campos están declarados ahora y una prueba valida la respuesta contra
`MoldexCatalogRead`. El contrato OpenAPI se regeneró; llevaba además el docstring nuevo de
`/verify` (SCI-A-058), que no se regeneró en su commit.

Verificación: `test_moldex_procedencia.py` 22 pruebas (con el código anterior fallan las de
A-005, A-010 y A-011); backend `-k "moldex or hotspot or repository or evaluation_result or
contrato"`: 149 pasan; `generate_openapi_contract.py --check` verde tras `--write`;
`moldexSello.test.ts` con 2 casos más; `tsc` limpio.

## SCI-A-022 — el dossier no presenta como registrada una corrida sin comprobar

**Veredicto:** `SOBREAFIRMADA`, S2. **Verificado:** sí.

El campo «Corrida» de la portada imprimía el `task_id` que declara el caso con `REGISTRADO`
(«el dato existe y quedó serializado por la corrida») también cuando el resultado almacenado
no guardaba ninguno. El router ya rechazaba una discordancia conocida (409), pero la ausencia
pasaba por coincidencia. `_campo_de_la_corrida` distingue cuatro casos: coinciden
(`REGISTRADO`); sólo lo declara el caso («… (declarada por el caso)», `REVISAR`, la
correspondencia no se pudo comprobar); sólo lo guarda el resultado (`REGISTRADO`, con esa
razón); y discrepan (`REVISAR`, nombrando la corrida almacenada). La exportación del legado se
mantiene, con su identidad marcada. Inglés en plantillas y catálogo.

Verificación: `test_identidad_de_la_corrida_comprobada.py`, 7 pruebas; backend `-k "dossier or
i18n or catalogo or paquete or package"`: 498 pasan, 10 saltadas.

## SCI-A-026 — las condiciones del informe inglés, en inglés

**Veredicto:** `SOBREAFIRMADA`, S2 (C0 en el ledger; se trató como C1 por las plantillas
dinámicas). **Verificado:** sí, frase a frase con `traducir(…, "en")`.

Quedaban en castellano: la advertencia de los pesos del stacking sin salida (lleva la lista
de modelos, así que necesitaba plantilla), «Faltan poses o afinidad serializada», los rótulos
«EVIDENCIA DISPONIBLE» e «EVIDENCIA INCOMPLETA» (el PDF los imprimía sin traducir dentro de
una línea que no tenía plantilla) y «Sin datos suficientes». La piscina del ensemble («pose
elegida entre N candidatas») se arregló con SCI-A-024. La advertencia de stacking degradado
ya tenía inglés y se conserva. El PDF traduce ahora el rótulo y el resumen por separado.

Verificación: `test_informe_ingles_condiciones.py`, 8 pruebas (la última comprueba que los
literales siguen siendo los que emite el código, para que una edición del emisor no deje la
traducción huérfana); catálogo inglés y backend `-k "pdf or informe or ingles or english or
i18n or certific"` verdes. **No verificado sobre el PDF renderizado**: las pruebas que lo
leen necesitan `pypdf`, que no viaja en el runtime; corren en la fase 2 con el Python de
desarrollo.

## SCI-A-037 — un margen de score de Vina no es una razón de unión

**Veredicto:** `SOBREAFIRMADA`, S2 (C0 en el ledger; se trató como C1: la escala vive en
`lib/selectividadMargen.ts` y en su gemelo del backend, con pruebas de paridad). **Verificado:**
sí.

La escala decía «MARGEN AMPLIO — la diana principal une ~100x más fuerte que la peor
anti-diana» y «unas 10x», el panel imprimía un «Factor implicado: 5.4x – 4651x» y el PDF un
«factor orientativo». Todo sale de `10^(ΔΔG / RT·ln10)` aplicado a una **diferencia de scores
de Vina entre receptores distintos**, que el propio producto declara no comparable como
energía libre; nadie validó esa conversión contra razones de unión medidas.

- Los veredictos dicen ahora lo que miden: «MARGEN DE SCORE AMPLIO — la diana principal
  puntúa al menos 2.73 kcal/mol mejor que la peor anti-diana», y así con los demás. **Los
  cortes no cambian** (2.73, 1.36, 0.41, 0), ni la paridad con el backend.
- El panel y el PDF dejan de mostrar factores. El panel dice en su lugar que es una
  diferencia de scores entre receptores distintos y no una razón de afinidades medida, con la
  dispersión típica de ±2 kcal/mol.
- El veredicto tiene clave de traducción (antes se mostraba en castellano en la interfaz
  inglesa) y los guardados con el rótulo anterior se muestran con el nuevo.
- `factorDeSelectividad` / `factor_de_selectividad` siguen sólo para justificar dónde caen los
  cortes, con la condición escrita; `bandaDeFactor` y `formatearFactor` salen.

Verificación: `test_selectividad_margen.py` 16 (3 nuevas, fallan con el código anterior);
`selectividadMargen.test.ts` 12 (2 nuevas, fallan con el código anterior); vitest de
`components/interfaces/pro` y backend `-k "selectiv or pdf or informe or i18n or golden or
dorad or dossier"` verdes; `tsc` limpio. Corregir la interpretación científica pediría una
validación aparte contra razones de unión experimentales; no se propone aquí.

## CLAVE-09 — la protonación es reproducible entre procesos, y la corrida lo deja dicho

**Origen:** la clave sellada de la auditoría (`CLAVE-09`, peso medio), que la auditoría no
vio. Choca con FEP-05/06: un paquete que un tercero tiene que reconstruir.

### Qué se midió aquí

La causa original (dimorphite devolvía la lista en otro orden en cada proceso y se tomaba
`[0]`) está corregida desde el 2026-09-04 (`elegir_microestado` ordena los canónicos). Lo
repetí el 2026-10-20 con dimorphite-dl 2.0.2 y `PYTHONHASHSEED` 0–5:

- el **orden** de la lista sigue cambiando entre procesos (la lisina da tres `[0]` distintos
  con las semillas 0, 1 y 4242): dimorphite itera `set()` de cadenas;
- el **conjunto** de candidatos y el **elegido** son idénticos en los seis procesos para
  lisina, histidina, propranolol, una poliamina-poliácido, un pentapéptido KDEKR, un
  octa-imidazol (100 candidatos) y una octahistidina, que llega al tope de 128 variantes.

### Lo que faltaba, y se hizo

1. **Registro reproducible.** `estado_del_ligando.protonacion` guarda ahora `version_motor`,
   `parametros` (pH mínimo y máximo, precisión, `max_variants`), `candidatos_sha256` (SHA-256
   de los SMILES canónicos ordenados del conjunto) y `recortado`. Con eso un tercero puede
   repetir la enumeración y comprobar que obtiene el **mismo conjunto**, no sólo el mismo
   elegido. `max_variants` se pasa explícito (128, el valor por defecto de dimorphite).
2. **El recorte se declara.** Si la lista llega al tope, el conjunto puede estar incompleto y
   el elegido sale de un subconjunto: aviso `MICROESTADOS_RECORTADOS` (PRECAUCIÓN, en
   `CODIGOS_DE_AVISO`) y, en el dossier, el campo nuevo «Enumeración de microestados» con
   `REVISAR`. Sin recorte, el campo queda `REGISTRADO`. Las corridas anteriores no traen estos
   datos y no enseñan el campo.
3. **Guardián entre procesos.** `test_protonacion_reproducible_entre_procesos.py` repite
   enumeración y elección en tres procesos con distinto `PYTHONHASHSEED` y exige el mismo
   conjunto y el mismo elegido. **Demuestra que ve:** su autotest sustituye la elección por
   `lista[0]` y comprueba que entonces los procesos discrepan; si el orden de dimorphite
   dejara de variar, el autotest falla y avisa de que el guardián ya no demuestra nada.

Verificación: 11 pruebas en ese archivo (≈ 22 s); backend `-k "dossier or prepar or ligand or
especie or protona or i18n"` verde; catálogo inglés verde. **Límite:** la reproducibilidad
se midió en esta máquina y con esta versión de dimorphite; una versión distinta puede
enumerar otro conjunto, y la huella está para detectarlo.

## C-GAP-02 — el contexto de ensayo se contrasta con la corrida

**Origen:** Fase C de la auditoría (`auditoria/fase_c/diez_huecos.md`, hueco 2 de 10, C1).
Las condiciones del ensayo y el constructo sólo viajaban como texto libre en el contexto
del caso: nada contrastaba su pH, sus cadenas o sus cofactores con lo que la corrida
preparó, y una discrepancia no dejaba rastro.

### Decisión

- **Contrato versionado** `ContextoDeEnsayo` (`context.assay` del caso, versión 1;
  identidad `moldesign.contexto_ensayo/1`): pH, temperatura, magnitud medida,
  `protein_construct`, cadenas, cofactores (códigos CCD) y fuente. **Todo opcional.**
  Ausente el bloque, el caso es el de antes. El campo se llama `protein_construct` y no
  `construct` porque este último pisa un método de `BaseModel`.
- **Comparación pura** (`services/dossier/contexto_ensayo.py::clasificar`), con tres
  estados que no se mezclan: `coincide`, `discrepancia` y `desconocido`. Un campo omitido
  en cualquiera de los dos lados es `desconocido` y **nunca** se rotula coincidente ni
  discrepante. El pH coincide dentro de ±0,5 (la precisión con que enumera dimorphite);
  las cadenas y los cofactores, como conjuntos sin distinguir mayúsculas. Una lista de
  cofactores registrada vacía sí se compara («no se conservó ninguno», como en
  SCI-A-068); la clave ausente es `desconocido`.
- **Preparación** añade al bloque Entorno un resumen (`entorno.ensayo`) y un requisito por
  campo declarado (`entorno.ensayo.ph`, `.cadenas`, `.cofactores`), contra el pH de
  protonación, `prepared_chains` y `cofactors_whitelist` que registró la corrida. Una
  discrepancia queda en `REVISAR`, con la acción que la resolvería, y se resuelve con una
  decisión registrada, como el resto de la pestaña; no bloquea. Si la corrida no registró
  su lado, `NO_DISPONIBLE`. Temperatura, magnitud, constructo y fuente se transmiten sin
  compararse: la corrida no tiene con qué.
- **El ZIP** ya llevaba `case/case_snapshot.json` (con el contexto declarado) y
  `preparacion/audit.json` (con cada comparación: valores, fuentes, estado y contrato).
  Con eso un tercero recalcula cada estado sin el disco de quien lo generó.

**Lo que no hace:** no valida ninguna afinidad ni es un detector nuevo; compara lo que el
investigador declara del ensayo con lo que la corrida registró. La interfaz todavía **no
ofrece dónde declarar** el contexto de ensayo (el manifiesto del caso en el frontend no
tiene el campo): hoy sólo lo usa un caso que llegue con él a la API. Es trabajo de
frontend aparte.

### Verificación

`test_contexto_de_ensayo.py`, 63 pruebas: contrato y rechazos, las tablas de `clasificar`,
la **matriz completa** de 27 fichas (cada campo omitido, igual o distinto) sobre la
auditoría —el 100 % de las discrepancias declaradas se señala y ningún omitido aparece—,
el caso sin contexto (ningún requisito nuevo), la corrida que no registró su lado, la
decisión que resuelve, el inglés sin castellano y la reconstrucción desde el ZIP. **Demuestra
que ve:** con lo omitido metido en la auditoría fallan 20, y con `desconocido` convertido
en `coincide`, 8. Contrato OpenAPI regenerado (sólo añade `ContextoDeEnsayo`); la
instantánea española del dossier, reescrita con python-embed: cambia sólo el hash de
`case/case_snapshot.json`, 19 bytes más por el `"assay": null`. Backend `-k "dossier or
prepar or paquete or package or i18n or ingles or contexto or caso or case"`: 874 pasan,
10 saltadas.

## SCI-A-057 — el diagrama de contactos rotula sólo los átomos que forman cada contacto

**Diagnóstico.** `generate_2d_interaction_diagram` (`certificate_figures.py`) pintaba un
puente de hidrógeno o un puente salino sobre **todos** los N, O, F y S del ligando, con el
rótulo de la primera interacción, los formara o no: el mapa de contactos
(`compute_residue_interactions`) no guardaba qué átomo la formaba. Además dibujaba desde
el SMILES, cuyos índices de átomo no son los de la pose de la que salen las distancias.

**Decisión.** Cada contacto lleva `ligand_atoms`: los índices, en la pose, de los átomos
que forman el contacto polar. El mapa y el diagrama leen la pose con la misma función
(`primera_pose`), así que los índices corresponden. El diagrama sólo localiza un contacto
en un átomo si dibuja esa pose; desde el SMILES, o con un contacto sin índices, dibuja el
ligando sin localizar ninguno y la tabla lo da por residuo. Un átomo con dos residuos
lleva los dos rótulos. La tabla y su clasificación no cambian.

**Verificación.** `test_diagrama_de_contactos_por_atomo.py`, 6 pruebas: con un receptor y
una pose sintéticos donde sólo uno de los dos oxígenos del etilenglicol está a 2,9 Å de
una serina, el contacto nombra ese oxígeno y no el otro; los contactos sin índices, los
no polares y los índices fuera de rango no se rotulan. Falla con el código anterior (el
contacto no llevaba `ligand_atoms`). Backend `-k "pdf or certific or golden or dorad or
contact"`: 122 pasan y 19 saltadas; las 8 corridas doradas, idénticas.

## SCI-A-016 — el resumen del intento de calibración conserva su panel y sus condiciones

**Diagnóstico.** El resumen expandido de la insignia de catálogo (resultados, Moldex) decía
«Se intentó verificar este receptor y no superó la calibración (ρ = 0,13; IC 95 %:
−0,16–0,41)» y perdía n, la magnitud, el panel, las condiciones del ensayo y el
experimento: lo que la lista «Intentos publicados» y la tarjeta compacta sí llevaban.

**Decisión.** `ResumenDeIntentos` usa la misma ficha de frases (`frasesDelIntento`) y la
abre con una frase nueva (`cat_intento_resumen`): las cifras y condiciones describen ese
experimento, **no la corrida que se está viendo**. La frase de ensayo ya se corrigió en la
fase 0 (SCI-A-017: desplazamiento de [3H]nisoxetina; pH, temperatura y concentración sin
constar). La clave `cat_intento_insignia` sale, porque nada más la usaba.

**Verificación.** `IntentosDeVerificacion.test.tsx`: el resumen expandido, en los dos
idiomas, contiene ρ, IC, n = 57, Ki, CHEMBL853189, las tres condiciones y CAL-8HFI-01; con
el componente anterior fallan esas dos pruebas. Vitest de `components/science` y
`seccionCatalogo`: 165 pasan. `tsc` limpio.

## SCI-A-054, SCI-A-055 y SCI-A-056 — la baseline de rescoring dice qué midió

Comprobado aquí sobre los artefactos de `rescoring/artifacts/`:

- **SCI-A-054.** El «Spearman CV 0,7731» de `docs/38_FASE_B_BASELINE.md` es de **una**
  partición aleatoria 80/20 del pool (429/108; `train_families.py`, `split = max(5,
  int(n * 0.8))`), sin folds ni predicciones guardadas. Igual el Pearson, el NDCG y la
  tabla de modelos familiares.
- **SCI-A-055.** `split_config.json` guarda el holdout de 328 y cinco folds que cubren
  **otros 328** complejos (262–263 / 65–66 cada uno): 209 de los 537 del pool no están en
  ninguno. El archivo no reconstruye el entrenamiento que dio esas cifras.
- **SCI-A-056.** `shap_analysis.json` no lleva el hash del modelo, se calculó sobre 692/173
  muestras y da ρ 0,7191: es otro modelo. La puerta de importancia Vina daba PASS con su
  cuota (2,8 %).

**Decisión.** `docs/38` lleva una corrección fechada al principio y los dos rótulos
afectados la remiten; las cifras se conservan con su condición real, y `docs/16` deja de
llamarlo CV. `check_vina_importance_gate.py` exige que el SHAP declare el SHA-256 de
`model_a_universal.json`: sin él (o con otro) el veredicto es `NO_VERIFICABLE`, exit 3.
`--permitir-no-verificable` sale con 0 **diciéndolo**, como `--permitir-runtime-ausente`;
la CI y `CONTRIBUTING.md` lo pasan, con un comentario para quitarlo cuando se recalcule el
SHAP. Una FAIL por cuota no la tapa la bandera.

**Lo que no se hizo.** Reproducir folds, guardar IDs y predicciones, y recalcular el SHAP
ligado al modelo: es reentrenar, fase posterior. Los nombres `spearman_cv` de
`model-manifest.json` y de `docs/46_RUNTIME_INVENTORY.md` salen de metadatos generados y se
conservan; AF-01 es un sello y no se edita.

**Verificación.** `rescoring/tests/test_vina_importance_gate_ligado_al_modelo.py`, 5
pruebas: sin hash o con otro, `NO_VERIFICABLE` y exit 3; con la bandera, exit 0 y el mismo
veredicto; ligado, decide la cuota y una FAIL sigue siendo FAIL; y el estado real de los
artefactos versionados (sin hash, 692/173), para que avise quien recalcule el SHAP. La
puerta sobre el árbol: `NO_VERIFICABLE`, exit 3 (0 con la bandera).

## SCI-A-060 a SCI-A-065 — documentos que se quedaron atrás

Cada cifra se volvió a medir en el árbol antes de escribirla.

| ID | Documento | Corrección |
|---|---|---|
| SCI-A-060 (S3) | `docs/37_INTEGRATION_POLICY.md`, RCSB | 381 curados y 446 `.pdb.gz` en `data/targets/`, no 387 y 302 en `data/target_library/` (que ya no viaja). **Los 381 tienen archivo local:** el «1XP0 sin estructura» del ledger es `1xp0.pdb.gz`, en minúsculas |
| SCI-A-061 (S3) | `docs/37`, matriz de consentimiento | los tres disparadores (Moldex, Evaluación y el visor del PDF) abren `CertificationModal`, y sólo él llama a `prepareCertification` / `linkCertification`; ya no hay camino directo |
| SCI-A-062 (S3) | `docs/19_LIMITATIONS.md` y `README.md` | nota de vigencia: es un postmortem de julio; el fallo silencioso devuelve hoy `(NaN, NaN)` con `_record_silent`, nunca `(0.5, 1.0)`; el checkpoint que se carga es `gnn_v3_best.pt`. El README lo enlaza como postmortem con nota de vigencia |
| SCI-A-063 (S4) | `docs/19`, §2.7, §3, §5.1, §5.2 y §9 | el CSV da gpcr 15 y kinase 14 (cambió el 2026-10-04); `stacking_weights.json` tiene 9 claves con pesos, todas con `gnn = 0`, ocho con `vina 1,0` y `lofo_canonical` con `vina 0,25` / `xgb 0,75`. Las rutas de máquina de §5.1 pasan a relativas |
| SCI-A-065 (S4) | `ROADMAP.md` del launcher | casillas marcadas con la ruta que lo demuestra (fases 2 a 5); `PlayButton` y `ModelSettings` no existen con ese nombre; `RequireModel` existe y **no lo monta ninguna página**; las fases 1 y 6 y los costes no se comprueban desde el árbol |

**Visto de paso, sin corregir:** `components/LauncherGate.tsx` dice en un comentario que
«los guardas de página (RequireModel) cubren los modelos que faltan»; ninguna página lo
monta. No cambia lo que hace la aplicación.

`check_docs_links.py --check`, `build_registro_cientifico.py --check` y
`build_sitio_publico.py --check` verdes.

### Cierre de la fase 1: suite completa

Los 77 registros de las fases A, C y D del ledger están en este documento (los seis de
frontend de Sol, integrados en `046bd598`), más CLAVE-09 y C-GAP-02. Los 129 registros C1 de
la Fase B (reparar analizadores y productores de sellos) pasan a la fase 1b, más abajo.

Sobre `b2748e61`, en este worktree y con python-embed 3.11.9:

- backend entero: **5128 pasan, 35 saltadas, 2 xfail y 0 fallos** (9,8 min);
- `rescoring/tests`: 318 pasan, 12 saltadas;
- vitest: **2090 en 228 archivos**, todas en verde; `tsc` limpio;
- `--check` de la CI: conteo de pruebas (reescrito con `--write`: 5163 recolectadas),
  OpenAPI, enlaces, sellos, inventario del runtime, pesos del stacking, frontera de
  licencias de modelos, frontera de Open Babel, pipeline de release, manifiesto de
  modelos, SBOM, lockfile y las 8 corridas doradas, verdes. La puerta de importancia Vina
  dice `NO_VERIFICABLE` (SCI-A-056) y sale con 0 con la bandera que pasa la CI.

No probado aquí: el smoke de producción, las 16 puertas del build y Playwright.

# Fase 1b — registros C1 de la Fase B: reparar analizadores y productores de sellos

**Estado:** en curso (detalle de cada cierre en `docs/102_FASE_1B_CORRECCIONES.md`). Cerrados los 129 registros (SCI-B-131, 155 y 156 con medidas nuevas: MF-33-EXT-MOD-R1 y RS-03-PARAM-A-R1): SCI-B-016 en la fase 1; en la fase 1b, los nueve S1, los 56 con ID < 105 y los 63 del lote de Sol. Los 63 con ID ≥ 105 están encargados a Sol.

**Origen.** El cierre de la fase 1 dejó fuera los 129 registros de clase C1 de la Fase B del ledger vigente (245 registros, `LEDGER_VIGENTE.json`). Esta fase los incorpora al plan. Cada uno es C1: código más prueba, sin cómputo científico.

**Orden.** Por severidad (S1, luego S2 y S3) y, dentro de cada una, por ID. El orden dice qué conviene atacar antes; no agrupa por familia. Los bloques de 1 a 3 días se definen al empezar la fase, agrupando los registros que comparten un productor.

**Método.** El de la fase 1 (sección «Metodología por hallazgo»): verificar el hallazgo en el código, escribir la prueba que falla sin el arreglo, aplicar el cambio mínimo y verificar la suite afectada.

**Restricciones.**
- Los productores y los artefactos de `scripts/artifacts_science/` están sellados. Si un arreglo cambia un byte sellado, la regla nueva vive aparte y el productor vuelve a sus bytes, como en SCI-B-016.
- Si el arreglo de un registro mezcla una parte C0 (texto) con una C1 (código), la C0 va a la corrigenda de sellos y la C1 se hace aquí.
- Los registros C2 y C3 de la Fase B no entran aquí: quedan para la fase 4, al final.

**Puerta.** Cada registro cierra con su prueba en verde y con su línea en esta sección, citando el commit. Al cerrar la fase se repite la fase 2 completa (suite, `--check`, smoke de producción y las 16 puertas), porque esta fase toca productores y analizadores.

### S1 — 9 registros

| ID | Veredicto | Título | Arreglo mínimo (ledger) | Estado |
|---|---|---|---|---|
| SCI-B-022 | FALSA | REC-07 mide contacto con una cisteína ausente del receptor acoplado | C0: retirar la validación funcional y corregir paper/lectura por nota externa, sin reescribir sellos. C1: usar resolución coherente de altloc (átomos comunes más variante elegida) y abortar si Cys25/SG o las anclas no están en el receptor preparado con identidad/coordenadas verificadas. Recuperar el control requiere repetir 15 corridas y tres de determinismo sobre receptor corregido; presupuesto orientativo C3, 1–2 CPU-h basado en los 3661 s previos, sin ejecutar aquí. | hecha en la fase 1b (docs/102): REC-07-R1, NO_GO; con la Cys25 presente el grid recomendado no llega a ella |
| SCI-B-045 | NO_VERIFICABLE | El manifest de FEP-04 no sella todas las entradas necesarias para reconstruir sus filas por complejo | C0: declarar que se reproducen agregados desde per_complex, no filas moleculares desde fuentes crudas. Para registros futuros, incluir hashes de cada input/output, dependency lock/versiones, comando y estado limpio; no reescribir ni volver a sellar FEP-04. | hecha en la fase 1b (docs/102): sellar_experimento.py exige entradas, salidas y versiones en los sellos nuevos |
| SCI-B-076 | FALSA | El CI del gate primario mide exactitud, no precisión balanceada | Tratar el GO como no verificado para G2; una corrida futura debe calcular el intervalo del estimando pre-registrado en el conjunto de evaluación, sin usar el CI de exactitud como sustituto. | hecha en la fase 1b (docs/102): IC de la precisión balanceada [0,049; 0,245], el GO se sostiene |
| SCI-B-083 | FALSA | El radio nominal de 0.5 Å no fija un RMSD inicial de 0.5 Å | Describir la variable como traslación nominal más rotación; reservar ‘rugosidad a 0.5 Å’ hasta medir con RMSD inicial controlado. | hecha en la fase 1b (docs/102): reagrupado por RMSD de partida; el fallo cercano sale de 5 de 30 complejos |
| SCI-B-088 | SOBREAFIRMADA | La ausencia de muestra local no demuestra que rho sea débil a todos los radios | Limitar la conclusión a los radios y complejos con muestra suficiente; no interpolar a R≤2 Å ni tratar ausencia de estimación como evidencia de rho débil. | hecha en la fase 1b (docs/102): cobertura por radio medida; corrección en el paper |
| SCI-B-089 | SOBREAFIRMADA | Una correlación estática entre poses no prueba navegabilidad de la búsqueda | Presentar el resultado como asociación descriptiva entre poses; reservar las afirmaciones sobre navegabilidad y familias de algoritmos para ensayos de búsqueda. | hecha en la fase 1b (docs/102): corrección en el paper (sin código: es lectura) |
| SCI-B-092 | SOBREAFIRMADA | El volumen global de poses no resuelve la falta de soporte local | Separar cantidad total de cobertura local; describir R≤2 como no estimable en COLOCACION con este conjunto. | hecha en la fase 1b (docs/102): cobertura por radio medida; corrección en el paper |
| SCI-B-096 | FALSA | MF-16-R1 no lee energías minimizadas: vuelve a calcular un punto único | No presentar los valores R1 como relajados mientras el productor mida getPotentialEnergy sin minimización; reconstruir el análisis a partir de las energías post-minimización verificadas. | hecha en la fase 1b (docs/102): R1 se reconstruye desde MF-10, 38 de 38 |
| SCI-B-097 | FALSA | El productor conserva los hidrógenos de la primera pose al puntuar las demás | No reutilizar coordenadas H de una pose al cambiar los átomos pesados; recalcular hidrógenos o minimizar cada estructura completa antes de puntuarla. | hecha en la fase 1b (docs/102): defecto real, ninguna cifra publicada depende de él |

### S2 — 102 registros

| ID | Veredicto | Título | Arreglo mínimo (ledger) | Estado |
|---|---|---|---|---|
| SCI-B-002 | SOBREAFIRMADA | El modelo de potencia de FND-04 no corresponde a la respuesta fraccionaria de RS-14 | Retirar esos n/MDE como cuantificación validada del selector; usar un modelo que conserve promedios, varianza y dependencia por complejo/semilla y probarlo con datos sintéticos de respuesta conocida. Mantener los IC de diferencia claramente separados. | hecha en la fase 1b (docs/102): MDE con la varianza observada: 15.6 / 16.9 pp, no 22.3 |
| SCI-B-003 | SOBREAFIRMADA | FEP-01 verifica una permutación pero no la identidad química de la correspondencia atómica | Limitar la afirmación a unicidad/cobertura de índices. Añadir control negativo de permutación, cotejo de elementos/conectividad y tratamiento de simetrías antes de acreditar RMSD. | hecha en la fase 1b (docs/102): acotado a índices únicos que cubren los pesados |
| SCI-B-008 | SOBREAFIRMADA | FEP-03-PDBBIND cuenta extremos de aristas como una red conectada | Usar el cálculo de componentes ya existente para contar redes; renombrar la métrica de grado positivo y conservar ambos números con condición. No afirmar que una componente ya sea una red parametrizable. | hecha en la fase 1b (docs/102): por componente conexo: 11 y 4 dianas, no 28 y 12 |
| SCI-B-016 | SOBREAFIRMADA | La envoltura experimental puede aprobar una batería física incompleta | C1: exigir cobertura y disponibilidad de controles requeridos y guardar sus estados; emitir NO_EVALUADO/REVIEW ante ausencias o NaN, con controles de contrato. C0: condicionar las tasas a los flags retenidos. Una recalificación molecular retrospectiva completa sería C2 y no se ejecutó. | hecha en la fase 1 (`bd725342`, `b9679397`) |
| SCI-B-018 | FALSA | El MDE puede caer fuera del dominio posible de su propio modelo | C1: validar \|delta\|<=q, devolver potencia no alcanzable cuando proceda y calificar el diseño discreto exacto frente al gate real; aplicar también dominio a n_necesario. C0: retirar los MDE imposibles hasta corregirlos. No usar discordancia observada como garantía prospectiva. | hecha en la fase 1b (docs/102): MF-19 y MF-08: MDE 0.132 > d = 0.091, fuera del dominio; «no alcanzable» |
| SCI-B-023 | SOBREAFIRMADA | La proximidad sin identidad no acredita la cota superior de pérdidas | C0: describir correspondencias geométricas aproximadas y retirar la cota garantizada. C1: exigir compatibilidad de especie/elemento y pareo uno a uno, con controles de eliminación, sustitución y movimiento. La calificación existente recupera el negativo en estos datos; no requiere nuevos dockings. | hecha en la fase 1b (docs/102): emparejamiento por proximidad: no es cota superior garantizada |
| SCI-B-025 | FALSA | El intervalo llamado BCa es un intervalo percentil sin corrección BCa | C0: renombrar intervalos originales y declarar la desviación. C1: usar una implementación calificada del método preregistrado y conservar artefacto corregido separado; no sobrescribir sellos. Aquí sólo se reproduce el método original, sin cambiar el gate a posteriori. | hecha en la fase 1b (docs/102): el «BCa» es percentil; BCa real [−0.159, 0.054] y [−0.221, 0.018], gate igual |
| SCI-B-026 | SOBREAFIRMADA | El nulo de RS-14 no aplica la misma estadística que el resultado observado | C0: presentar el control como diagnóstico de entrenamiento con etiquetas perturbadas, sin p calibrado ni garantía de ausencia de sobreajuste. C1: definir misma estadística, folds, semillas, presupuesto y política de etiquetas para observada y permutadas. Su recalificación sobre datos existentes sería C2, sin entrenar aquí. | hecha en la fase 1b (docs/102): el nulo usa otra estadística; p empírico no calibrado, lectura diagnóstica |
| SCI-B-040 | SOBREAFIRMADA | El indicador documentable para FEP no comprueba metales, cofactores ni aguas del sitio | Renombrar 1543/3887 como casos que pasan los dos criterios de cribado estructural aplicados. No llamarlos documentados/listos para FEP ni derivar de ese porcentaje la fracción con todos los supuestos resueltos. Conservar los conteos de metales y aguas como presencia geométrica, no como decisión química. | hecha en la fase 1b (docs/102): «documentado» = dos criterios de cribado, no readiness |
| SCI-B-041 | SOBREAFIRMADA | El GO de comparabilidad de FEP-02-PDBBIND no tiene margen definido y reutiliza toda la cohorte comparadora | Limitar la conclusión a tasas descriptivas de las salidas disponibles: PDBBind exclusivo de los 203 da 1460/3684 (39.6%) frente a 83/203 (40.9%) en la réplica. No presentar GO ni coincidencia de porcentajes como equivalencia validada. Declarar que la copia local omite 1438 receptores y que la ausencia no se comprobó aleatoria. | hecha en la fase 1b (docs/102): 1460/3684 vs 83/203 como coincidencia descriptiva, sin GO de equivalencia |
| SCI-B-042 | SOBREAFIRMADA | FEP-02-EXT-PDBBIND convierte 1438 receptores ausentes en SIN_HUECOS | Distinguir SIN_HUECOS de fuente no disponible/SIN_PDB. Los 1438 casos no tienen evidencia para asignarles huecos=0. Actualizar resumen de cobertura y usar el denominador de casos evaluables; no reescribir el sello. | hecha en la fase 1b (docs/102): 1438 SIN_PDB no son SIN_HUECOS: 2210 de 3887 evaluables (56.9 %) |
| SCI-B-049 | SOBREAFIRMADA | FEP-07-PDBBIND compara 400 bloqueos por receptor con desbloqueos marginales | C0: decir «400 aristas reciben estado prioritario de receptor; 59 también llevan flag de tautómero; 341 son receptor-only en el clasificador». No decir que se recuperan 400 al reparar ni que las 341 sean realmente ejecutables tras reparación. | hecha en la fase 1b (docs/102): 400 = prioridad del clasificador; 59 también tautómero; no «se recuperan» |
| SCI-B-050 | SOBREAFIRMADA | FEP-08 convierte una diferencia puntual dentro de ±15 puntos en independencia del preparador | C1: comunicar 67/369 frente a 1003/4641 y el diferencial puntual bajo el margen fijado; retirar la conclusión causal «depende de la molécula y no del preparador» hasta una comparación apareada o equivalencia inferencial. | hecha en la fase 1b (docs/102): diferencia puntual, sin equivalencia ni emparejamiento |
| SCI-B-051 | SOBREAFIRMADA | FEP-08 llama positivo de readiness a un control de huecos y cadenas | C1: nombrar el resultado control positivo del filtro de numeración/cadena, no validación del auditor de readiness integral. No llamar a 12/15 listos para FEP. | hecha en la fase 1b (docs/102): control positivo del filtro, no del auditor completo |
| SCI-B-052 | NO_TRAZABLE | FND-01-SMOKE registra GO sin vincularlo a una ejecución verificable | C1: conservar comando, hash/commit del código invocado, exit code y log del gate en el manifest o una salida sellada; hacer que finish consuma el resultado observado. Reclasificar FND-01-SMOKE como smoke de infraestructura y excluirlo de las mediciones científicas. | hecha en la fase 1b (docs/102): FND-01-SMOKE es un smoke de infraestructura: su GO no registra comando ni exit code y no cuenta como medición |
| SCI-B-053 | SOBREAFIRMADA | El sello de FND-01-SMOKE no valida y su README contradice el manifest | C1: no editar el artefacto sellado. Crear una nueva versión que clasifique hashes de código como código/asset y regenere README desde el manifest final; conservar en la ficha que el paquete histórico no pasa validate. | hecha en la fase 1b (docs/102): `validate` falla (hash vivo de `experiment_manifest.py`); la copia sellada está en `sellado_original/` y `validar_sellos` la usa |
| SCI-B-055 | SOBREAFIRMADA | FND-03 mide el oráculo best-of-9, no el selector ni el top-1 | C0: calificar la estabilidad binaria como 0/33 en COLOCACION, añadir 1/15 en CONTROL y llamarla estabilidad del oráculo. No derivar estabilidad top-1 ni confianza; para ello se requiere una medición distinta. | hecha en la fase 1b (docs/102): estabilidad del oráculo best-of-9, no del top-1 |
| SCI-B-057 | SOBREAFIRMADA | FND-05 no excluye la cohorte por defecto al repetir el builder | C1: corregir DESIGN §17/§19 para declarar que el guard es opt-in y separar la reproducción histórica del modo para construir datos futuros. Conservar la advertencia de que no hay aislamiento de acceso de máquina. | hecha en la fase 1b (docs/102): el guard de la denylist es opt-in |
| SCI-B-058 | SOBREAFIRMADA | La garantía futura de procedencia no está conectada como gate fail-closed | C1: cablear --strict-unknown y la cobertura por trabajo como condición de salida del builder futuro; no presentar la garantía de 100% como automática hasta que falle cerrado. | hecha en la fase 1b (docs/102): `--strict-unknown` opt-in: la garantía no es automática |
| SCI-B-060 | SOBREAFIRMADA | La ficha pública dice acceso nulo al test aunque se carga metadata de provenance solo-test | C1: corregir la frase pública a 'No se leyeron poses ni labels de test; se cargó metadata de provenance de 113 registros clasificados como solo-test'. No presentar esto como evidencia de fuga de etiquetas. | hecha en la fase 1b (docs/102): se cargan metadatos de 113 registros sólo de test; no hay fuga de etiquetas |
| SCI-B-061 | SOBREAFIRMADA | Los puntos 61.5% y 61.0% no demuestran que el selector no contribuya a la brecha train/test | C1 para la prosa: cambiar 'toda la diferencia ... no el selector' por 'las estimaciones puntuales observadas son cercanas; esta comparación no establece equivalencia'. C2 sólo si se quiere sostener una afirmación confirmatoria, con margen y datos no expuestos. | hecha en la fase 1b (docs/102): 61.5 % y 61.0 % son puntos cercanos; no prueban que el selector no contribuya |
| SCI-B-062 | SOBREAFIRMADA | El roadmap conserva “eje conformacional agotado” pese a la corrección de la extensión | C1 editorial: cambiar el roadmap/encabezado a “meseta observada en train n=116; la extensión muestra rendimientos decrecientes, con aumento hasta K150”, manteniendo los tamaños de cohorte y los fallos reportados. | hecha en la fase 1b (docs/102): «eje agotado» → meseta en train, rendimientos decrecientes en PDBBind |
| SCI-B-063 | SOBREAFIRMADA | La comparación train/PDBBind no identifica la dificultad relativa del universo preregistrado tras la attrition | Reescribir los claims como condicionales a embedding exitoso y publicar el n válido junto a cada porcentaje; aclarar 16 casos no enumerados. Para sostener dificultad relativa de todo PDBBind, reconciliar/medir los faltantes y predeclarar el tratamiento del fallo. | hecha en la fase 1b (docs/102): porcentajes condicionados a los 4636 embebidos; 16 sin enumerar |
| SCI-B-064 | SOBREAFIRMADA | El registro público conserva las cifras de MF-02B que corrigió MF-02B-R1 | Sin tocar el artefacto sellado, actualizar el registro público: enlazar MF-02B-R1 mediante reemplazado_por y presentar 14/38 y 79.3% como cifras corregidas, dejando las antiguas sólo como historia del error. | hecha en la fase 1b (docs/102): MF-02B marcado como reemplazado por MF-02B-R1 en el registro |
| SCI-B-065 | NO_VERIFICABLE | El GO de MF-02B no queda verificado para el endpoint top-K que declara el gate original | Mantener como válido el resultado corregido del oráculo de todas las poses y separar ese estimando del endpoint de entrega A8. No marcar el gate original como fallido: informar su estado como no medido hasta calcular el conjunto exacto entregado. | hecha en la fase 1b (docs/102): R1 mide el oráculo de todas las poses; el endpoint top-K entregado queda sin medir |
| SCI-B-066 | SOBREAFIRMADA | MF-02C-PRE hereda el RMSD alineado y una justificación obsoleta para G3 | No ejecutar el runner sin enmendar el preregistro. Mantener 90% sólo si se presenta como objetivo de mejora y se fija el estimando; no como garantía de no-degradación. Aplicar la métrica pocket-frame al top-K exacto y actualizar la decisión preregistrada. El GO actual pertenece a la categoría prerregistro, no a un resultado medido. | hecha en la fase 1b (docs/102): MF-02C-PRE cita 93.1 % (corregido a 79.3 %): G3 ≥ 90 % no es «no degradación»; no ejecutar sin enmendar |
| SCI-B-067 | SOBREAFIRMADA | MF-02E dice no mirar etiquetas, pero su runner calcula y guarda RMSD contra cristal por caso | Cambiar la nota a: “No se usan RMSD/etiquetas para ajustar parámetros ni para los gates G1/G2; el runner calcula RMSD alineado por caso para reporte. Su consumo downstream debe quedar separado y auditado”. No describirlo como cegamiento total. | hecha en la fase 1b (docs/102): el runner calcula RMSD contra cristal por caso para reporte; no ajusta ni decide gates con él |
| SCI-B-068 | SOBREAFIRMADA | MF-08-PRE-R1 registra G5 de determinismo, pero el runner lo omite | Añadir e implementar G5 antes de usar el runner como ejecución íntegra del PRE-R1; mantener explícito que el resultado observado no evaluó determinismo. La discrepancia mayor del PRE original quedó resuelta por R1 antes de la corrida. | hecha en la fase 1b (docs/102): G5 preregistrado y no implementado |
| SCI-B-069 | SOBREAFIRMADA | MF-09 sobregeneraliza el predominio del muestreo a ausencia de margen del score | Corregir la lectura descriptiva y distinguir cobertura de pose, acierto top-1 y recuperación al ampliar K; no hace falta volver a ejecutar docking para corregir esta aritmética. | hecha en la fase 1b (docs/102): 3 de 33 de COLOCACION son fallos de puntuación |
| SCI-B-070 | SOBREAFIRMADA | MF-09 llama verificación a una unión cuyas entradas no están selladas | Añadir procedencia verificable de las entradas al paquete de MF-09 y rebajar la frase de verificación a consistencia agregada hasta que otro entorno reconstruya el resumen desde los mismos archivos sellados. | hecha en la fase 1b (docs/102): «verificado» = consistencia de agregados |
| SCI-B-071 | NO_VERIFICABLE | MF-09-SYM sella el analizador, pero no sus métricas ni sus entradas | Crear una relectura versionada con hashes de todas las entradas y salidas, y distinguir los resultados agregados reportados de los que se han verificado de forma independiente. | hecha en la fase 1b (docs/102): el sello de MF-09-SYM sólo fija el analizador |
| SCI-B-072 | NO_VERIFICABLE | MF-11-R1 no conserva una captura previa del contrato detallado | No reinterpretar el GO de train como confirmación externa. Si se necesita validar la selección, correr una variante futura con preregistro íntegro y previo, sobre datos no usados para elegir el umbral. | hecha en la fase 1b (docs/102): contrato detallado de R1 no capturado antes |
| SCI-B-074 | NO_VERIFICABLE | MF-11-R2 no documenta un test independiente del umbral | Describir MF-11-R2 como resultado por partición y dejar la confirmación de transferencia pendiente hasta una evaluación con selección train-only y holdouts no usados para seleccionar. | hecha en la fase 1b (docs/102): umbral elegido y evaluado en la misma partición |
| SCI-B-075 | NO_VERIFICABLE | El sello de MF-11-R2 no fija métricas ni datasets de entrada | Mantener el GO como resultado declarado pero con procedencia incompleta; corregir el flujo de sellado en futuras corridas sin reescribir los artefactos científicos ya publicados. | hecha en la fase 1b (docs/102): sello sin métricas ni entradas |
| SCI-B-077 | FALSA | El MDE usa 203 casos cuando la evaluación pareada contiene 87 | No usar 0.136 como capacidad de resolución de la evaluación de 87; mantener la distinción entre el MDE de la diferencia de exactitud y el estimando primario balanceado. | hecha en la fase 1b (docs/102): MDE con n = 87: 0.203; el estimando balanceado (+0.154) queda por debajo |
| SCI-B-078 | NO_VERIFICABLE | Los sellos no fijan el preregistro ni las métricas MF-12 | Dejar el experimento con procedencia temporal y de datos no verificable; corregir el flujo en futuras ejecuciones sin reescribir los artefactos publicados. | hecha en la fase 1b (docs/102): sellos de MF-12 y MF-12-PRE sin métricas, entradas ni preregistro |
| SCI-B-079 | NO_VERIFICABLE | MF-12-PRE declara GO aunque no tiene una métrica para G2 | No contar el GO de PRE como resultado científico; aclarar en registros futuros la diferencia entre protocolo aprobado y gate experimental superado. | hecha en la fase 1b (docs/102): el GO de MF-12-PRE aprueba el protocolo, no un gate |
| SCI-B-080 | NO_VERIFICABLE | MF-13-ESCALA no certifica que el join conserve el denominador completo | Conservar el resultado como agregado declarado y no validado independientemente; futuras reanálisis deben incluir guardias de cobertura/duplicados y hash del output seguro. | hecha en la fase 1b (docs/102): el join omite con `continue` los pids sin poses v2: denominador no garantizado |
| SCI-B-082 | NO_VERIFICABLE | MF-13-PRE no fija el contenido exacto del preregistro | Mantener el preregistro como evidencia documental con precedencia sólo parcial; no reinterpretar el GO de PRE como resultado científico. | hecha en la fase 1b (docs/102): MF-13-PRE sella el runner, no el texto del preregistro |
| SCI-B-084 | NO_VERIFICABLE | La mediana r50 publicada es condicional a r50 definido | Etiquetar las medianas como condicionales a r50 finito y no generalizarlas al estrato completo sin análisis de censura. | hecha en la fase 1b (docs/102): medianas de r50 condicionadas a r50 definido |
| SCI-B-085 | NO_VERIFICABLE | MF-14 mide captura local con ligando rígido | Limitar el nombre y las conclusiones al protocolo de ligando rígido; medir por separado la variante flexible. | hecha en la fase 1b (docs/102): ligando rígido (TORSDOF 0) |
| SCI-B-086 | NO_VERIFICABLE | La semilla global no fija las perturbaciones por complejo | Eliminar el hash aleatorizado de Python del generador o registrar el valor de PYTHONHASHSEED y las semillas derivadas. | hecha en la fase 1b (docs/102): semilla con `hash(pid)` sin PYTHONHASHSEED: no regenerable |
| SCI-B-087 | NO_VERIFICABLE | El sello retroactivo fija el runner, no los datos ni la salida | Mantener MF-14 como evidencia exploratoria post hoc y crear un protocolo prospectivo con entradas y salidas hash-vinculadas. | hecha en la fase 1b (docs/102): sello retroactivo: exploratorio post hoc |
| SCI-B-090 | NO_VERIFICABLE | El resultado documentado corresponde al split train, no a los tres splits de v2 | Etiquetar el resultado como train y no trasladarlo a val/test; completar resultados de esos splits antes de una conclusión general. | hecha en la fase 1b (docs/102): sólo train |
| SCI-B-091 | NO_VERIFICABLE | El sello de MF-15 vincula el código, pero no la instancia de entrada ni el resultado | Mantener el resultado como análisis descriptivo de procedencia parcial; sellar explícitamente referencias exactas de entrada y salida en una revisión reproducible. | hecha en la fase 1b (docs/102): sello sin entrada ni salida |
| SCI-B-093 | SOBREAFIRMADA | La coincidencia con MF-09 es consistencia sobre material compartido, no replicación independiente | Presentar el gate como verificación de consistencia de lectura y separar su peso probatorio de una réplica externa. | hecha en la fase 1b (docs/102): consistencia sobre el mismo material, no réplica |
| SCI-B-095 | NO_VERIFICABLE | El sello fija el analizador, pero no el material ni las métricas de MF-15-EXT | Mantener la conclusión como relectura retrospectiva con procedencia parcial; sellar hashes de datos y salida en futuras mediciones. | hecha en la fase 1b (docs/102): sello sin material ni métricas |
| SCI-B-098 | NO_TRAZABLE | El runner sellado escribe en MF-16, no en MF-16-R1 | Separar el runner R1 y su ruta de salida del experimento original; registrar input/output hashes en el manifest R1. | hecha en la fase 1b (docs/102): runner sellado escribe en MF-16 (cifras de R1 ya reproducidas, SCI-B-096) |
| SCI-B-099 | NO_VERIFICABLE | El contrato dice ‘sin gates’ pero el productor define G1 y G2 | Alinear el contrato del experimento y la salida del productor; preservar una versión preregistrada de los gates. | hecha en la fase 1b (docs/102): G1/G2 del productor no preregistrados: no deciden |
| SCI-B-100 | NO_VERIFICABLE | La comparación pareada se basa sólo en los complejos con dos correlaciones disponibles | Etiquetar el resultado como análisis de casos completos; reportar sensibilidad a casos faltantes y una incertidumbre de efecto pareado. | hecha en la fase 1b (docs/102): análisis de casos completos |
| SCI-B-101 | NO_TRAZABLE | MF-17 consume r50 desde un JSONL scratch ausente y no hash-vinculado | Eliminar la dependencia de scratch, vincular el JSONL de entrada permitido por el expediente y hacer que cualquier falta de fuente bloquee la síntesis. | hecha en la fase 1b (docs/102): la entrada de scratch era la sellada; la ruta sigue sin hash |
| SCI-B-102 | NO_VERIFICABLE | La síntesis no valida igualdad de cohortes ni reporta N por mecanismo | Añadir aserciones de claves iguales y contar cada métrica tras la máscara de disponibilidad; reportar la composición estratificada y no inferir mecanismos causales. | hecha en la fase 1b (docs/102): los 48 pids de MF-09 están en las otras tres fuentes; N por mecanismo publicado aquí |
| SCI-B-103 | SOBREAFIRMADA | El contraste con MF-33 confunde la fuente del conformero y el número de candidatos | Presentar la relación entre ambos estudios como hipótesis exploratoria condicionada a sus protocolos; reservar la atribución causal para un benchmark que iguale candidatos y presupuesto. | hecha en la fase 1b (docs/102): fuente del confórmero y nº de candidatos confundidos |
| SCI-B-104 | NO_VERIFICABLE | La ejecución retroactiva de MF-19 no se reconstruye desde las entradas selladas | Conservar, si aún existe, el paquete original scratch con hashes y procedencia; si no existe, mantener la cifra como resultado reportado no reproducible y no presentarla como verificación independiente. | hecha en la fase 1b (docs/102): resultado reportado, no reconstruible desde el sello |
| SCI-B-105 | SOBREAFIRMADA | MF-21 no garantiza que el RMSD declarado use sólo átomos pesados | Aplicar la referencia sin hidrógenos usada en MF-22 y reemitir agregados después de verificar las entradas; declarar el impacto por separado si había H retenidos. | hecha en la fase 1b (docs/102, lote de Sol): confirmado, clase A |
| SCI-B-106 | NO_VERIFICABLE | El cruce de MF-21 con MF-09 puede omitir unidades sin corregir el denominador | Añadir validaciones fail-closed para claves faltantes/duplicadas y para el número de conformeros/filas válidas; reportar el denominador efectivo de cada estrato. | hecha en la fase 1b (docs/102, lote de Sol): parcial, clase B |
| SCI-B-107 | NO_TRAZABLE | El manifest de MF-21 no fija sus entradas ni el helper que define la lectura molecular | Recuperar el paquete original si existe y crear un manifest completo; si no existe, mantener el resultado como cita reportada sin verificación independiente. | hecha en la fase 1b (docs/102, lote de Sol): parcial, clase C |
| SCI-B-108 | SOBREAFIRMADA | MF-24 incluye una variable nativa y parte del desenlace entre sus predictores | Presentar r_conf como referencia oracular/diagnóstico, no predictor; marcar enterramiento como feature que requiere pose; documentar por separado la lista de seis features operativas y cualquier variable adicional. | hecha en la fase 1b (docs/102, lote de Sol): confirmado, clase A |
| SCI-B-109 | SOBREAFIRMADA | La correlación marginal no demuestra que el enterramiento sea un predictor independiente del tamaño | Reformular la frase como asociación marginal observada y reservar afirmaciones de independencia para un análisis ajustado; conservar la advertencia no causal actual. | hecha en la fase 1b (docs/102, lote de Sol): confirmado, clase A |
| SCI-B-110 | NO_VERIFICABLE | MF-24 no valida que los directorios procesados coincidan con las particiones declaradas | Consumir archivos de partición inmutables en lugar de enumerar carpetas; fallar ante duplicados/ausencias y guardar la invocación exacta del segundo split. | hecha en la fase 1b (docs/102, lote de Sol): parcial, clase B |
| SCI-B-111 | NO_TRAZABLE | El sello de MF-24 no fija los datos ni el helper necesarios para reconstruir sus correlaciones | Recuperar y fijar las entradas exactas y su procedencia; si faltan, conservar los rho como cifras reportadas no reproducibles, no como verificación independiente. | hecha en la fase 1b (docs/102, lote de Sol): confirmado, clase C |
| SCI-B-112 | NO_TRAZABLE | Los outputs de MF-27 no contienen material suficiente para verificar las cifras publicadas | Recuperar el output agregado y el archivo por unidad si existe, sellarlos y regenerar el README desde esos resultados; si se perdieron, dejar los números como citas no verificables. | hecha en la fase 1b (docs/102, lote de Sol): confirmado, clase C |
| SCI-B-113 | NO_TRAZABLE | El productor sellado de MF-27 no implementa el subgrupo ni el MDE reportados | Añadir el productor correcto y regenerar los outputs; si el análisis se hizo fuera del repo, registrar la receta y su procedencia retroactiva. | hecha en la fase 1b (docs/102, lote de Sol): confirmado, clase C |
| SCI-B-115 | NO_TRAZABLE | El preregistro de MF-28 no fija todos los insumos que definen receptor, conformeros y control Vina | Completar el paquete de transferencia con hashes de todos los archivos consumidos y versión/hash de Vina antes de interpretar rendimiento. | hecha en la fase 1b (docs/102, lote de Sol): confirmado, clase C |
| SCI-B-116 | SOBREAFIRMADA | El gate de MF-29-EMP depende del tratamiento de las unidades incompletas | Añadir política de datos faltantes y sensibilidad del gate sobre el denominador planeado; separar fallos por semilla de exclusiones de unidad. | hecha en la fase 1b (docs/102, lote de Sol): confirmado, clase B |
| SCI-B-117 | NO_TRAZABLE | MF-29-EMP no sella las entradas estructurales ni el ejecutable Vina consumidos por el runner | Sellar cada entrada exacta consumida por el runner y el binario efectivo de Vina, resolviendo y registrando también MF29_VINA. | hecha en la fase 1b (docs/102, lote de Sol): confirmado, clase C |
| SCI-B-118 | NO_VERIFICABLE | La precedencia temporal del preregistro de COR no tiene anclaje independiente anterior al resultado | Crear un commit firmado previo a la corrida con hipótesis, protocolo, gate, código e inputs, y añadir luego un commit separado de resultados. | hecha en la fase 1b (docs/102, lote de Sol): confirmado, clase C |
| SCI-B-119 | NO_VERIFICABLE | El gate G2 puede pasar sin cobertura mínima de unidades ni de átomos pesados | Añadir umbral de completitud por unidad y de cobertura atómica, y hacer fallar el gate cuando falten derivas o coordenadas suficientes. | hecha en la fase 1b (docs/102, lote de Sol): parcial, clase B |
| SCI-B-120 | NO_TRAZABLE | El manifest COR no fija por hash las entradas estructurales ni el helper y Vina efectivos | Sellar las entradas directas, helper y ejecutable usados y conservarlos con el paquete de evidencia. | hecha en la fase 1b (docs/102, lote de Sol): confirmado, clase C |
| SCI-B-121 | NO_VERIFICABLE | MF-29-EMP-EXT puede emitir una lectura sin exigir las tres semillas ni las dos recuperaciones | Validar cardinalidad de objetivos, semillas exitosas y unión antes de calcular o publicar la fracción. | hecha en la fase 1b (docs/102, lote de Sol): parcial, clase B |
| SCI-B-122 | NO_TRAZABLE | El manifest de MF-29-EMP-EXT no fija las entradas físicas ni Vina | Incluir y hash-vincular todas las entradas físicas y herramientas efectivamente resueltas en el manifest EXT. | hecha en la fase 1b (docs/102, lote de Sol): confirmado, clase C |
| SCI-B-127 | NO_VERIFICABLE | El enriquecimiento agrupado mezcla controles exitosos con casos COLOCACION | Estratificar cada cruce por COLOCACION/CONTROL y evitar usar el grupo CONTROL dentro del denominador de éxitos para explicar fallos del estrato COLOCACION. | hecha en la fase 1b (docs/102, lote de Sol): confirmado, clase B |
| SCI-B-128 | NO_VERIFICABLE | El gate de MF-33-EXT no exige 116 casos evaluables | Añadir aserciones sobre 116 trabajos, unicidad y 116 resultados válidos; registrar el recuento de fallos separado del denominador del gate. | hecha en la fase 1b (docs/102, lote de Sol): parcial, clase B |
| SCI-B-129 | NO_TRAZABLE | El manifest de MF-33-EXT no fija por hash la cadena de entradas y Vina efectivos | Declarar el selector real y todos los inputs materiales, Vina y su versión en el manifiesto; retirar entradas declaradas que el productor no consume o verificar su función explícitamente. | hecha en la fase 1b (docs/102, lote de Sol): confirmado, clase C |
| SCI-B-130 | NO_TRAZABLE | El Fisher de 14.7x sobre REC-09 no está prerregistrado ni tiene productor sellado | Separar el cruce REC-09 del resultado primario, etiquetarlo post-hoc y sellar sus entradas, código, tabla estratificada y limitaciones. | hecha en la fase 1b (docs/102, lote de Sol): confirmado, clase B |
| SCI-B-131 | NO_VERIFICABLE | El bloque prospectivo no mide cuatro de sus cinco predictores externos | Calcular las cuatro variables con el productor correspondiente para los 68 externos, registrar faltantes y completitud, y mantener INCONCLUSIVE hasta tener el bloque completo. | hecha en la fase 1b (docs/102): MF-33-EXT-MOD-R1, GO; sin señal más allá de K |
| SCI-B-132 | NO_TRAZABLE | El manifest final no fija la fuente usada para separar la cohorte externa | Sellar todas las fuentes que determinan la pertenencia y reportar las claves esperadas, faltantes y duplicadas sin depender de un archivo implícito. | hecha en la fase 1b (docs/102, lote de Sol): parcial, clase C |
| SCI-B-133 | FALSA | El ajuste geométrico omite fallos censurados y K variable | Reescribir el ajuste para observaciones censuradas y K heterogéneo; recalcular y documentar el contraste sólo después de sellar el productor actualizado. | hecha en la fase 1b (docs/102, lote de Sol): confirmado, clase B |
| SCI-B-134 | NO_TRAZABLE | El chi-cuadrado reportado se añadió tras el sello y no lo produce el script sellado | Etiquetar el resultado existente como exploratorio hasta que un productor sellado y una regla previa lo reproduzcan. | hecha en la fase 1b (docs/102, lote de Sol): confirmado, clase C |
| SCI-B-135 | NO_TRAZABLE | Las dependencias estadísticas usadas no están fijadas por hash ni versión | Completar el grafo de dependencias del productor y reproducir sólo después de sellar las dependencias efectivas. | hecha en la fase 1b (docs/102, lote de Sol): confirmado, clase C |
| SCI-B-136 | SOBREAFIRMADA | No rechazar el rango medio no acredita equivalencia ni excluye efectos de orden | Comunicar que no se detectó una ventaja media de conf0 y que el orden real no produjo un exceso de chi2 en la dirección preregistrada; conservar abierta la estructura del orden y no declarar equivalencia. | hecha en la fase 1b (docs/102, lote de Sol): confirmado, clase A |
| SCI-B-137 | NO_TRAZABLE | Los recuentos añadidos de cambio G1/G2 carecen de productor en el sello ORD | Mantener el carácter exploratorio de la propuesta y separar la propiedad teórica de orden de las cifras no reproducidas; sellar el análisis adicional sin modificar los artefactos originales. | hecha en la fase 1b (docs/102, lote de Sol): confirmado, clase B |
| SCI-B-138 | NO_VERIFICABLE | El gate H13 puede aprobar sin las 55 topologías previstas | Hacer fallar o abstenerse al faltar o duplicarse cualquier miembro esperado; conservar los controles numéricos y de entradas entre máquinas que ya existen. | hecha en la fase 1b (docs/102, lote de Sol): parcial, clase B |
| SCI-B-139 | NO_VERIFICABLE | El booleano de gate R1 omite la condición obligatoria entre plataformas | Combinar los criterios en una decisión final que se abstenga si faltan comparaciones; validar que Windows fallido o ausente y errores de ejecución no puedan dar GO total. | hecha en la fase 1b (docs/102, lote de Sol): parcial, clase B |
| SCI-B-140 | NO_VERIFICABLE | El contador de pérdida en sitio usa disminución global por especie | Conservar inventario global por especie para describir preparación; separar y verificar un inventario por copia para el sitio antes de reutilizar esos conteos como evidencia local. | hecha en la fase 1b (docs/102, lote de Sol): confirmado, clase A |
| SCI-B-141 | NO_TRAZABLE | El filtro original que produjo PREP-01 no se recupera con el sello mantenido | Guardar la fuente original por hash y distinguir sus conclusiones históricas de una revisión nueva del filtro vigente; no reejecutar bajo el mismo ID ni dar por recuperado un módulo sólo por coincidir con new_hash. | hecha en la fase 1b (docs/102, lote de Sol): confirmado, clase C |
| SCI-B-143 | SOBREAFIRMADA | Una corrección parcial de poses no demuestra cobertura completa invariante | Conservar las cifras como cota inferior bajo fuentes declaradas y retirar exactitud o inocuidad global hasta cubrir el material faltante. | hecha en la fase 1b (docs/102, lote de Sol): confirmado, clase A |
| SCI-B-145 | NO_VERIFICABLE | La verificación obligatoria de RMSD no bloquea la salida del productor | Separar diagnóstico de métricas válidas y hacer fallar explícitamente el gate de reproducción/completitud antes de emitir conclusiones interpretables. | hecha en la fase 1b (docs/102, lote de Sol): parcial, clase B |
| SCI-B-146 | NO_VERIFICABLE | Los gates de features v2 no exigen cubrir todas las claves de poses | Contabilizar registros ausentes como fallo, comprobar correspondencia de claves y tamaño de vectores antes de emitir GO y conservar controles negativos que omitan una pose o un archivo completo. | hecha en la fase 1b (docs/102, lote de Sol): confirmado, clase A |
| SCI-B-147 | SOBREAFIRMADA | El censo de consumidores mezcla versiones por coincidencias parciales de ruta | Etiquetar la lista como candidatos de revisión y construir aristas por versión/hash con función de la entrada; mantener separada la medición de composición del conjunto v2. | hecha en la fase 1b (docs/102, lote de Sol): confirmado, clase A |
| SCI-B-155 | NO_VERIFICABLE | RS-03-PARAM-A declara energía finita y serialización sin calcularlas | Retirar PASS G9 como prueba de esas propiedades y condicionar aceptación agregada hasta medición nueva registrada; conservar artefactos históricos. | hecha en la fase 1b (docs/102): RS-03-PARAM-A-R1, energía y serialización se sostienen en 115 de 116; 1nw5 no |
| SCI-B-156 | NO_VERIFICABLE | El hash de tipos de átomo no verifica el mapeo biyectivo exigido por RS-03-PARAM-A | Separar hash de orden descriptivo de mapeo validado y exigir la comprobación de correspondencia antes de aceptar G5; propagar la limitación al agregado. | hecha en la fase 1b (docs/102): RS-03-PARAM-A-R1 NO_GO, 1nw5 da 52 partículas para 51 átomos |
| SCI-B-157 | NO_VERIFICABLE | RS-09 verifica un checkpoint distinto de la ruta cargada y no mide aislamiento final | Condicionar la atribución a producción y retirar PASS G6 como prueba del aislamiento completo hasta acreditar el archivo usado y estados antes/después. | hecha en la fase 1b (docs/102, lote de Sol): confirmado, clase C |
| SCI-B-158 | NO_VERIFICABLE | RS-09 confunde selección estable con reextracción idéntica | Describir el control existente como estabilidad de selección limpia; condicionar identidad del extractor y exclusión de drift a comparación de features/scores. | hecha en la fase 1b (docs/102, lote de Sol): confirmado, clase A |
| SCI-B-159 | FALSA | RS-04-OOF --repro no exige la byte-identidad que anuncia | Retirar garantía de exigencia automática de --repro; separar determinismo declarado de comparación acreditada y conservar resultados históricos. | hecha en la fase 1b (docs/102, lote de Sol): confirmado, clase A |
| SCI-B-160 | SOBREAFIRMADA | RS-08 convierte ausencia en top-k en necesidad de nuevas poses | Renombrar clase como no_accionable_en_topk y limitar acción a protocolo restringido; reservar sampling_needed por ausencia de pose en todo el conjunto, sin modificar el resultado histórico. | hecha en la fase 1b (docs/102, lote de Sol): confirmado, clase A |
| SCI-B-161 | SOBREAFIRMADA | FND-08 confunde presencia de archivos con verificabilidad de cifras y productor | Describir G3/G4 como inventario de presencia y no verificación científica. Reemplazar inferencias de verificabilidad/imposibilidad por adjudicación semántica de cada dependencia. | hecha en la fase 1b (docs/102, lote de Sol): confirmado, clase A |
| SCI-B-163 | SOBREAFIRMADA | MF-13 convierte comparación con una referencia local en diagnóstico causal exhaustivo | Mantener fracción de referencias que ganan y umbral MIXTO; retirar optimalidad global y ninguna búsqueda ayuda, evitando interpretar categorías como proporción causal exhaustiva. | hecha en la fase 1b (docs/102, lote de Sol): confirmado, clase A |
| SCI-B-165 | SOBREAFIRMADA | MF-25 declara PAISAJE aunque el descenso citado activa su regla PRESUPUESTO | Publicar discrepancia de lectura sin alterar sello; informar mejora continua y falta de conversiones como endpoints distintos, evitando afirmar que presupuesto nunca es palanca. | hecha en la fase 1b (docs/102, lote de Sol): confirmado, clase B |
| SCI-B-166 | SOBREAFIRMADA | MF-32 trata un control seleccionado por otro brazo como test decisivo contra regresión a la media | Retirar carácter decisivo del control y afirmación de que efecto sobrevive probado; mantener INCONCLUSIVE, curvas y controles como diagnóstico parcial. Vincular límite de FND-03 ya registrado. | hecha en la fase 1b (docs/102, lote de Sol): confirmado, clase A |
| SCI-B-167 | SOBREAFIRMADA | MF-28 cambia movilidad y admisibilidad además de exploración pero cierra causalmente esa vía | Limitar NO_GO a roadmap/protocolo/ensemble y tiempo medido; retirar cierre causal de toda vía de exploración. Conservar desviaciones y sello retroactivo explícitos. | hecha en la fase 1b (docs/102, lote de Sol): confirmado, clase A |
| SCI-B-169 | SOBREAFIRMADA | MF-31 convierte falta de correlación monotónica entre deltas en ausencia de palanca causal | Limitar NO_GO a hipótesis monotónica/proporcional y corregir signo: reducir caja aumenta ocupación con numerador fijo. Mantener mejora de caja como citada, sin certificar su causa por esta correlación. | hecha en la fase 1b (docs/102, lote de Sol): confirmado, clase A |

### S3 — 18 registros

| ID | Veredicto | Título | Arreglo mínimo (ledger) | Estado |
|---|---|---|---|---|
| SCI-B-038 | SOBREAFIRMADA | EXT-PDBBIND atribuye a Kekulize errores químicos y nueve carpetas sin SDF | Informar 673 Kekulize, 2 AtomValence y 9 directorios sin SDF; sólo 675 errores son de IDs PDB-shaped. | hecha en la fase 1b (docs/102): 673 Kekulize + 2 de valencia + 9 carpetas que no son complejos |
| SCI-B-039 | SOBREAFIRMADA | Metrics EXT-PDBBIND conservan el experiment_id de la cohorte base | Añadir mapping inequívoco de identidad/universo fuera del sello; consumidores no infieren cohorte sólo desde metrics.experiment_id. | hecha en la fase 1b (docs/102): 4 sellos con experiment_id heredado, declarados y vigilados |
| SCI-B-094 | NO_VERIFICABLE | La corrección por simetría está limitada a 5000 automorfismos | Declarar el límite de 5000 y añadir una comprobación de truncamiento antes de presentar la invariancia como general. | hecha en la fase 1b (docs/102): límite declarado y medido |
| SCI-B-114 | SOBREAFIRMADA | La ocupación de caja no es el cubo normalizado del radio de giro en el código | Corregir la explicación: son descriptores geométricos relacionados, pero el volumen usa rmax y el radio de giro usa RMS radial. | hecha en la fase 1b (docs/102, lote de Sol): confirmado, clase A |
| SCI-B-123 | NO_VERIFICABLE | El PRE de MF-29-EMP declara 48 elegibles y el informe de ejecución 50 planificados | Alinear la descripción de cohorte con la lista sellada y el criterio TORSDOF utilizado; reportar por separado N planeado y N completo. | hecha en la fase 1b (docs/102, lote de Sol): parcial, clase B |
| SCI-B-124 | NO_VERIFICABLE | El cociente de MF-30 no verifica la identidad de la cohorte miembro a miembro | Añadir al productor una comprobación explícita de igualdad de claves y cohorte; conservar su resultado junto al agregado. | hecha en la fase 1b (docs/102, lote de Sol): parcial, clase B |
| SCI-B-125 | NO_VERIFICABLE | La necesidad de GPU para un modelo generativo no se mide con un candidato concreto | Reformular la razón como incompatibilidad no evaluada con el runtime CPU-only actual, y medir candidatos antes de generalizar sobre la familia. | hecha en la fase 1b (docs/102, lote de Sol): confirmado, clase A |
| SCI-B-126 | NO_VERIFICABLE | El productor de MF-33-CRUCES no valida el solape ni la unicidad de sus cuatro fuentes | Agregar asserts explícitos para cardinalidad, unicidad e igualdad de claves y cambiar el README a 'no recalcula ni modifica MF-33'. | hecha en la fase 1b (docs/102, lote de Sol): parcial, clase B |
| SCI-B-142 | SOBREAFIRMADA | Menos pérdidas de cofactores se interpreta como preparación mejor sin medir relevancia | Reescribir la lectura como diferencia descriptiva condicionada a fuente, especie y cadena; mantener la prohibición de interpretar retención como calidad. | hecha en la fase 1b (docs/102, lote de Sol): confirmado, clase A |
| SCI-B-144 | FALSA | El aumento relativo del 21% se convierte en fracción de positivas mal etiquetadas | Comunicar +21.0% respecto de las positivas originales o 17.4% de las corregidas previamente negativas, limitado al material recomputable. | hecha en la fase 1b (docs/102, lote de Sol): confirmado, clase B |
| SCI-B-148 | FALSA | REC-01 no puede agregar sus salidas explícitas de PDB ausente o ilegible | Completar es_excepcion antes de todo retorno y registrar las causas E6/E7 de forma uniforme, verificando la agregación y persistencia. | hecha en la fase 1b (docs/102, lote de Sol): confirmado, clase B |
| SCI-B-149 | SOBREAFIRMADA | El PASS de G5 reduce el perímetro de integridad fijado en el preregistro | Conservar el sello; documentar la divergencia y aportar evidencia contemporánea de integridad si existe. No reconstruir retrospectivamente hashes pre inexistentes como si fueran históricos. | hecha en la fase 1b (docs/102, lote de Sol): confirmado, clase C |
| SCI-B-150 | SOBREAFIRMADA | La contención exacta no demuestra el techo de éxito con tolerancia RMSD de REC-03 | Conservar el PRE y añadir corrigendum: retirar techo absoluto y porcentajes respecto del supuesto máximo; mantener el gate prospectivo de cinco éxitos como umbral elegido, sin justificarlo como mitad de un máximo demostrado. | hecha en la fase 1b (docs/102, lote de Sol): confirmado, clase A |
| SCI-B-152 | SOBREAFIRMADA | REC-04 cuenta el sitio por el primer registro del residuo y confunde centro ausente con cero | Retirar la lectura de conteos como inventario completo del sitio hasta corregir/definir el instrumento. Conservar resultados históricos y registrar cualquier recuento corregido como nueva unidad. | hecha en la fase 1b (docs/102, lote de Sol): confirmado, clase A |
| SCI-B-153 | NO_VERIFICABLE | REC-09 afirma reproducción universal de MF-13 con ejemplos de score incompatibles | Añadir corrigendum de referencia/ejemplo o de reproducción universal, manteniendo intacto el sello; no elegir silenciosamente una cifra como correcta. | hecha en la fase 1b (docs/102, lote de Sol): parcial, clase B |
| SCI-B-154 | SOBREAFIRMADA | REC-11 convierte un MDE de planificación en un límite absoluto de resolución | Conservar reglas de p y abstención, sustituir no resoluble por potencia inferior al objetivo bajo supuestos, y retirar el rótulo de límite de resolución medido. | hecha en la fase 1b (docs/102, lote de Sol): confirmado, clase A |
| SCI-B-162 | NO_VERIFICABLE | MF-01 sitúa seis ganancias en un estrato cuya tabla sólo permite cuatro | Condicionar frase todos de baja flexibilidad; conservar total marginal seis como aritmética narrativa, sin decidir qué tabla es correcta. | hecha en la fase 1b (docs/102, lote de Sol): confirmado, clase B |
| SCI-B-164 | FALSA | MF-26 dice que no se solapan dos intervalos cuya intersección es [0.342,0.419] | Corregir no se solapan e informar contraste apropiado si se pretende inferencia entre tasas; mantener no generalización como límite descriptivo sin usar solapamiento como prueba de igualdad. | hecha en la fase 1b (docs/102, lote de Sol): confirmado, clase A |

# Fase 2 — cierre con las puertas del build y el smoke de producción

Sobre `40c81f3d`, en el worktree `auditoria-arreglos` (2026-10-21):

| Comprobación | Resultado |
|---|---|
| Las 16 puertas de `beforeBuildCommand`, una a una y en su orden | todas en verde: `stage:desktop` 7,6 min, `verify:desktop-runtime` 3,5 min, `check:evaluation-runtime` (Vina real desde el bundle) 1,6 min, `build:desktop` 4,7 min |
| `smoke:prod` (export real, runtime staged, CSP de producción) | **63/63** |
| Playwright `test:e2e` / `test:ux` (`CI=1`) | **13/13** y **12/12** |
| Backend entero, vitest, `rescoring/tests` y los `--check` de la CI | los de la fase 1, sin cambios de código desde entonces |

**Un tropiezo de montaje, no del producto:** la primera pasada paró en la puerta 1 porque al
worktree le faltaban `tools/vina/Kernel1_Opt.bin`, `Kernel2_Opt.bin` (kernels de Vina-GPU,
ignorados por git) y `data/molgraph_seed.db`. La puerta dijo exactamente qué faltaba. Se
enlazaron desde el árbol principal y la segunda pasada salió entera.

**No cubierto:** `cargo` (fmt, clippy, test), el instalador NSIS/MSIX, WebView2 en una máquina
limpia, WACK y Partner Center. El Rust de esta rama no cambió en las fases 0 a 2; sí lo
cambiará la integración de `sol/contexto-ensayo-ui` (validación de `context.assay` en
`cases.rs`), y entonces hay que pasar `cargo test`.

# Fase 3

## ABS-TR-01, fidelidad semántica — la matriz de transmisión del veredicto físico

**Origen:** el diseño de la Fase D (`auditoria/fase_d/abstencion_y_falso_bloqueo.md`). Separa
dos tareas: la **fidelidad semántica** (que un fallo, una ausencia o una reserva lleguen
intactos del productor a cada salida) y la **validez de la decisión** (falso bloqueo contra
una referencia experta independiente). Esta sección cierra la primera, que no gasta CPU. La
segunda necesita 29 sistemas adjudicados por dos revisores, y quién revisa lo decide el
propietario.

**Regla previa, tal cual del diseño:** una pérdida de un fallo o de una ausencia crítica, o
una salida favorable sin soporte, en una sola fixture, es NO_GO de transmisión.

### Lo que se midió

`test_abs_tr_01_transmision.py`: el control de validez física de la pose principal en
**cinco estados lógicos** (superada, en revisión, fallida, no evaluada y sin evidencia
estructural) por **siete superficies**: resumen del informe, modelo del dossier, Preparación,
ZIP (auditoría y manifiesto), dossier en inglés, Molcy y límite del lote. La verdad de cada
fixture se escribió antes de mirar las salidas: favorable sólo con «superada».

**Resultado: los estados se transmiten bien en las siete superficies.** Ninguna salida es
favorable sin soporte, un fallo no se convierte en ausencia ni en revisión, y la ausencia no
se convierte en aprobado.

### El defecto que destapó: el detalle del validador sólo se traducía si la pose pasaba

Con los detalles **reales** del productor, el dossier inglés imprimía en castellano la razón
de toda pose fallida, en revisión o sin evaluar. El catálogo tenía como plantilla entera el
detalle de una pose superada, y nada más: el traductor parte el texto en frases y exige
pareja para cada una. Una sonda con las quince ramas del productor
(`test_detalle_fisico_en_ingles.py`) dio **10 de 15 sin traducir**: todas las de fallo, de
batería incompleta, del proxy de RDKit y de pose no reconstruida.

**Arreglo:** 22 parejas nuevas en `i18n_plantillas.py`, frase a frase, incluidas las razones
de degradación y los motivos del proxy que el productor mete entre paréntesis (van con hueco
`{frase1}`, que se traduce a su vez o se rechaza entero). El productor,
`pose_physical_validity.py`, está sellado por PROD-PV-H-01 y PROD-PV-H-01-PRE y **no se
toca**: la sonda copia sus f-strings, y una prueba aparte falla si el productor cambia una de
esas frases, para obligar a revisar su pareja. El proxy fuera de rango se traduce como «NOT A
FAILURE VERDICT», igual que dice en castellano.

### Verificación

74 pruebas en los dos archivos, que fallan 14 con el catálogo anterior. Catálogo inglés sin
defectos (9). Backend `-k "ingles or english or i18n or dossier or golden or dorad or pdf or
posebusters or fisic"`: 638 pasan, 20 saltadas, 1 xfail. Las 8 corridas doradas, idénticas.

**Límite:** la matriz sigue un solo control (la validez física), el que la auditoría encontró
aplanado en más superficies. Los demás controles de Preparación ya tienen sus pruebas de
transmisión de la fase 1; no se ha montado para ellos una matriz cruzada igual.

## ABS-TR-01, validez de la decisión — INCONCLUSIVE (2026-10-22)

La segunda tarea. No hubo revisores humanos (decisión del propietario): la referencia es un panel ciego de modelos
de lenguaje sobre los 29 sistemas, con 8 defectos plantados en la ronda 1 y 12 en la ronda 2 para medir a cada
revisor. Cuentan Astra 6, Sol 6.1, GLM 5.3 y step5preview (ronda 2) y Opus 5.5 (ronda 1). Con el registro previo
escrito antes de cualquier salida, cada sistema se evaluó por la API con su ligando del cristal y se pidió
Preparación (`scripts/abs_tr_01/abs_tr_01.py`; sellado `ABS-TR-01-VALIDEZ`).

Sobre 28 auditados: **ninguna falsa autorización** (0/10; Preparación nunca dice «seguir»), **falso bloqueo 3/18**
(16,7 %, límite unilateral 95 % 4,7–37,7 %) y **4 de 10 sistemas que el panel detiene pasan con aviso**. Los
falsos bloqueos son umbrales (ion retirado a ≤ 6 Å que el ligando no coordina en 1RKP y 6KE5; hueco a 6,09 Å en
4JVB). Lo que Preparación no ve: un ligando que coordina el hierro de un hemo conservado (4NY4), un sitio
completado por simetría (6SXC) y un ligando de referencia incompleto (3G0E); el covalente de 6HW5 lo ve y sólo
pide revisión. Dos cosas salieron de paso. El detector de ojivas llamaba «acrilamida» al oxindol del sunitinib
(3G0E): era un falso positivo de las arilidenolactamas (sunitinib, semaxanib, epalrestat), **corregido** en la rama de
integración (`chem/ojivas_covalentes.py`, con su prueba). Y 8WTW no se auditó: ya figuraba en
`disponibilidad_catalogo.json` como no disponible (Meeko no rellena el puente S–S que parte el recorte multicadena), la
interfaz no lo ofrece, pero el preflight de la API no consulta ese archivo y la corrida falla en `mk_prepare_receptor`;
es el comportamiento documentado («la preparación sigue deteniéndose sola»), no un defecto nuevo. Tabla y causas en el
`RESULTADOS.md` del sello.

## MET-01-R1, el ion del sitio medido de verdad — NO_GO

**Origen:** MET-01 (INCONCLUSIVE) no llegó a medir nada porque la evaluación descartaba
`cofactors_whitelist`; arreglado en `a27ded64`. R1 repite el mismo protocolo sobre `9ce8b104`, con
el prerregistro en `dfdc9a26` antes de cualquier docking (rama `claude/met-01-r1`, integrada aquí).

**Resultado:** 380 corridas confirmatorias, 0 fallos de infraestructura y 0 rechazos del producto.
28 entradas pareadas de 35 (7 excluidas, 20 %). Discordancias CON:SIN = 0:3, p bilateral exacta
0,25; controles evaluables 4 de 6, sin pérdida. Semillas con éxito conjunto: SIN 43/160, CON 34/160.
Con el Vina del producto, conservar el ion no mejora la reproducción de la pose del cristal; la
diferencia va en contra de CON y no es significativa, así que tampoco prueba daño ni equivalencia.
Se mantiene la retirada y la abstención. Paper en `docs/papers/MET-01-R1-ION-DEL-SITIO.md`.

**Verificación:** `verify` recalcula las 380 filas desde los crudos y el análisis da los mismos
bytes; sello de 1026 archivos (`23ad7c4d`), decisión en `98ecf485`, `validar_sellos --check` con 172
sellos, 0 distintos y 0 ausentes. La confirmatoria se cortó a las 09:33 UTC en dos shards y se
reanudó a las 15:45 sobre el mismo commit congelado. Después de los resultados sólo cambió el texto
de `report()`, declarado en `CAMBIOS_DESDE_MET01.md`.

**Límites que siguen:** PoseBusters no mira los iones que Meeko escribe como `ATOM` (sus PASA
inorgánicos son vacuos), y Preparación avisó de His coordinante con H en 55 de 160 corridas CON.

## C-GAP-02, un caso con ensayo declarado no abría Preparación

**Origen:** la entrega de Sol de la interfaz de `context.assay` (`sol/contexto-ensayo-ui`, T3
bloqueada). El productor metía la comparación de cada campo y el resumen de lo declarado en
`ubicacion`, que en el contrato describe huecos del esqueleto. El validador de la interfaz
(`esAuditoriaPreparacion`) exige a cada entrada de `ubicacion` la forma de un hueco, así que en
cuanto un caso declaraba su ensayo, el HTTP 200 de Preparación se convertía en «forma que esta
versión no conoce». En la fase 1 no se vio porque la interfaz aún no ofrecía dónde declararlo.

**Arreglo:** campo propio `ensayo` en el requisito (`preparacion.py`), con su tipo y su validador
en `lib/preparacion.ts`. `ubicacion` vuelve a describir sólo huecos, y las dos formas no se
mezclan: el validador sigue rechazando la del ensayo dentro de `ubicacion`.

**Verificación:** `test_contexto_de_ensayo.py` 64 (con una prueba nueva que recorre todos los
requisitos), backend `-k "preparacion or ensayo or zip or dossier"` 584 pasan y 10 saltadas;
`preparacion.test.ts` 31 (13 nuevas: las dos formas aceptadas, rechazadas dentro de `ubicacion` y
diez malformadas); `tsc` limpio. La pantalla con un caso real queda para la T3 de Sol, que ahora
puede hacerse.

## CAL-D-01 R4 y R4B, VMAT2 / 8T69 (2026-10-22)

`CAL-D-01-R4-VMAT2-8T69` ejecutó el registro previo R4 (`0a1a4aed…`, escrito antes de cualquier score): puerta de
pose 5 de 5 (RMSD 0,67–0,71 Å) y 88 de 89 compuestos acoplados. ρ de Spearman 0,391 (IC 95 % 0,219–0,537), ρ de peor
caso sobre las asignaciones binarias de lote 0,320 (0,139–0,473). **NO_GO formal** porque el registro exigía cero
fallos persistentes y el producto cortó el compuesto 4-67 (biciclo[1.1.1]pentano) a los 1200 s en los dos intentos.
`CAL-D-01-R4B-VMAT2-8T69` reanaliza los 88 scores sin 4-67 con una enmienda escrita después de verlos: **INCONCLUSIVE
por construcción** (cumple el criterio, no es confirmatorio y no promociona). Ambos están publicados en
`backend/data/intentos_de_verificacion.json`, con sus papers; 8T69 sigue en Demostración.

**Estadístico:** ρ_peor se calcula exacto por programación dinámica sobre la ventana de Ki a menos de un factor F, y se
validó contra la enumeración de las 2^m asignaciones en 80 casos con empates, copias de bootstrap y valores junto al
umbral (`backend/tests/test_cal_d01r4_rho_peor.py`).

**Incidentes (`DESVIACIONES.md` del experimento):** un intento interrumpido a mano; hilos de intentos agotados que siguen
calculando tras el `Timeout` y frenan los siguientes; un error del análisis (RMSD de panel contra el cristal), corregido
tras congelar; y un primer sellado con 398 MB de perfiles de cápsula, deshecho antes de commitear. Un guardián nuevo
(`test_intentos_de_verificacion.py`) comprueba las cifras publicadas contra los experimentos sellados.

**Abierto (decide el propietario):** un protocolo confirmatorio nuevo antes de promocionar 8T69, y el defecto de producto
(biciclopentano y `Timeout` que no detiene el cálculo).
