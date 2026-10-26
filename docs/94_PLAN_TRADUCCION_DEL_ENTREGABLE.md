# 94 · Plan: traducir al inglés el entregable y las plantillas del backend

> **Nota de reubicación (2026-10-11).** El worktree `D:\moldesign-worktrees\traduccion` del paso 1 se retiró el 2026-10-11. La rama `codex/traduccion-entregable` está íntegra en desarrollo: para trabajar en ella, crea un worktree nuevo con `git worktree add`. Índice: [REUBICACIONES_2026-10-11.md](REUBICACIONES_2026-10-11.md).

Estado: **completado el 2026-10-04**. Fases 0–8 completadas. La medición del inventario se reconcilió antes de continuar, según la instrucción del propietario. La suite backend completa pasó tras ejecutar fuera del sandbox de Windows, donde `TestClient` se detenía creando su socket local; el primer recorrido completo detectó una plantilla sin «docking» y la corrección pasó junto con toda la suite. Fuente de las decisiones:
la sesión de QA de Evaluación y Batch (rama `qa/agente1-evaluacion`), registro en `D:\moldesign-audits\evaluacion-agente1\hallazgos.md`.

> **Si eres el agente que ejecuta esto:** lee primero `AGENTS.md` entero (es corto y cada restricción costó un instalador),
> luego §3 y §8 de este documento, y sólo entonces empieza por la Fase 0. No tomes atajos de §9. Si algo no cuadra con lo medido
> aquí, **para y dilo**: las cifras son del 2026-10-04 y el repositorio cambia.

---

## 1. Qué se decidió y qué NO entra

Decisiones del propietario (2026-10-04), vigentes:

| Decisión | Consecuencia para este plan |
|---|---|
| El entregable (dossier PDF, README del ZIP, JSON del dossier) sale **en el idioma de la interfaz al exportar** | El idioma sale de `Accept-Language`, que el frontend ya manda en cada `fetch`. Español sigue siendo el idioma por defecto. |
| «Traducir todo lo posible» las plantillas del backend que se ven en pantalla | Fases 2–5. Lo que no se pueda traducir se **declara** (no se oculta). |
| Inglés **americano**; la traducción es **sólo de Claude**, sin revisión externa | Glosario fijo (`docs/GLOSARIO_EN.md`) y guardias automáticas (Fase 1 y §6). La calidad se vigila con herramientas, no con confianza. |
| «Caja de búsqueda» / «Search box» en toda la interfaz | Los textos del backend que dicen «caja de docking», «caja de acoplamiento», «caja de trabajo» y «caja efectiva» se unifican **en la Fase 6**, con los goldens regenerados una sola vez. |
| Péptidos «Experimental»; residuos de referencia declarados | **Ya hecho** (`17c806b`, `930a649`). Sus textos nuevos hay que traducirlos como los demás. |
| Todo esto entra en 1.0.2 (decisión del propietario, con la medida de §2 a la vista) | Se ejecuta por fases con puntos de revisión (§7); cada fase deja el producto publicable. |

**Fuera de alcance** (no lo toques): el asistente de primer uso con MolChat (versión siguiente); traducir a un tercer idioma;
cambiar el texto **español** (debe quedar byte a byte igual); los datos de la persona (nombres de moléculas, de casos, SMILES).

---

## 2. Punto de partida medido (2026-10-04)

### 2.1 Cuánto texto hay

Inventario AST v2 sobre el árbol del worktree tras Fase 3 (2026-10-04), antes del refinamiento documentado abajo. Cuenta cadenas de salida fijas y cada `ast.JoinedStr` elegible como una plantilla completa; excluye docstrings y fragmentos `Constant` que sólo forman parte de un f-string. También excluye `core/i18n_catalog.py` y `core/i18n_plantillas.py`, que son registros de traducción, no sitios de salida. Las plantillas se comparan normalizando sus marcadores por orden (`{pedidas}`, `{n}` → `{n1}`); así una declaración sólo cuenta cuando corresponde a un f-string real. Excluye además `tests`, `migrations` y `scripts`.

| Ámbito | Cadenas fijas (nodos `Constant`) | Plantillas f-string (`JoinedStr`) | Coincidencias en catálogo | Pendientes |
|---|---:|---:|---:|---:|
| **Todo el backend** (270 ficheros analizados; 195 con cadenas) | 2.466 | 730 | 502 ocurrencias (435 textos fuente únicos) | 2.694 |
| 12 ficheros prioritarios de dossier / preflight / avisos enumerados en Fase 4 | se detallan por capa en la tabla de Fase 4 | se detallan por capa en la tabla de Fase 4 | — | — |
| Frontend: `interfazSinTextoFijo` | — | — | — | presupuesto y medida actuales: 0 |

**Reconciliación de la medición original.** Las cifras iniciales (4.283 cadenas fijas, 705 f-strings, 652 ya en catálogo y 239 ficheros) no se reproducen. El commit `7035b5f4` que añadió este plan sólo guardó el documento y la fila de changelog: no contiene el script usado para producirlas. La descripción original tampoco precisaba si los `Constant` dentro de `JoinedStr` se contaban además de la plantilla. Aplicando literalmente esa regla del apéndice al commit `4ff68c4d`, se obtuvieron 5.442 nodos `Constant` y 733 plantillas; por eso no basta con atribuir la diferencia a los cambios posteriores del árbol. Esta versión fija y prueba la interpretación AST indicada arriba; desde aquí, los valores de `docs/api/i18n-inventario.json` sustituyen la línea base anterior. En la línea base previa a depurar, las 891 cadenas fuente únicas coincidentes podían exceder las 771 claves porque variantes con distintos espacios se normalizan para buscar coincidencia.

**Refinamiento v2 tras la capa 1.** Al traducir la capa 2, la auditoría real encontró 25 entradas del catálogo con problemas: 20 claves muertas y 21 fragmentos (categorías que se solapan), además de dos términos fuera del glosario, una entrada idéntica y una grafía británica. La inspección del AST mostró que el inventario también contaba algunos literales dentro de `+` y `+=` dinámicos como si cada uno saliera por separado. Se corrigió así: las concatenaciones estáticas cuentan como una sola salida; los fragmentos de concatenaciones dinámicas no cuentan como salidas independientes; una frase completa dentro de una composición sólo se declara completa cuando conserva su límite de oración. Las cadenas de interpolación se traducen mediante plantillas ancladas para proteger los datos capturados. La corrección de la medida no es progreso de traducción: los pendientes previos a este refinamiento no son comparables con los actuales. El inventario vigente marca **2.172 pendientes globales** y cero en los cuatro ficheros de la capa 2; el catálogo queda en **895 entradas / 0 problemas**. Los mensajes que sólo se pueden reconstruir con trozos dinámicos siguen bajo la Fase 7.

**Reconciliación previa a la capa 3.** La inspección de `pdf_generator.py` encontró cuatro literales de `_generic_prefixes` usados sólo como centinelas de `startswith`; no aparecen en el PDF. Se excluyeron del inventario y del catálogo. El total fijo de ese fichero baja de 123 a 119, sus coincidencias bajan de 25 a 21 y sus pendientes siguen en 113; el total pendiente global previo a traducir la capa continúa en 2.172. La medición actual, tras la capa 3, registra 1.992 pendientes globales y cero en las cinco rutas de esa capa.

La medida frontend no es comparable con el barrido AST del backend: `interfazSinTextoFijo` cuenta texto visible bajo sus propios criterios y actualmente exige un total de 0. El valor histórico 206/57 deja de ser presupuesto vigente. El inventario v1 se conserva en `docs/api/i18n-inventario-inicial.json`; al reconciliarlo se comprobó que contaba docstrings, fragmentos que no se traducen por separado y las propias declaraciones de plantilla como si fueran usos. La v2 excluye esos falsos pendientes y sólo marca una plantilla al encontrar su forma en un f-string de salida. Los conteos históricos de v1 (847 exactas y 4.987 pendientes tras Fase 1; 849 coincidencias y 4.987 pendientes después de declarar plantillas en Fase 2) quedan archivados, pero no se comparan con la medida v2. El informe inicial del catálogo marcó 373 entradas con uno o más problemas: 368 claves muertas y 126 fragmentos (categorías que se solapan).

### 2.2 Qué mecanismo existe ya (no hay que inventar otro)

- `backend/core/i18n.py`: `parse_accept_language`, `current_locale()` (un `ContextVar` fijado por el middleware en
  `backend/api/middleware.py`, líneas ~62 y ~75), `translate_text`, `localize_payload`, `localize_json_response`.
- `backend/core/i18n_catalog.py`: `ENGLISH_MESSAGES`, **1.087 entradas** auditadas sin problemas al revisar la capa 3 (895 al cerrar la capa 2); el informe vigente vive en
  `docs/api/i18n-catalogo-auditoria.json`.
- `backend/core/i18n_plantillas.py`: coincidencia exacta, plantillas ancladas y traducción por frases todo-o-nada.
  `backend/core/i18n.py` sigue localizando campos de mensaje en JSON; la vista de exportación del dossier aplica además
  `services/dossier/localization.py` a PDF, README y JSON, sin cambiar `case_snapshot.json`, CSV ni códigos.
- El frontend ya manda `Accept-Language` en cada petición (`frontend/context/LanguageContext.tsx`, `localizedFetch`).
- Las pruebas del mecanismo: `backend/tests/test_i18n.py`.

### 2.3 Qué calidad tiene lo que hay

En el catálogo previo a la Fase 1, muchas claves eran **fragmentos de f-strings** («`' no es un destino declarado.`»), que no casan nunca con el
mensaje completo que sale con números, y su traducción, hecha sin contexto, es mala:

| Español (clave, preauditoría) | Inglés previo a Fase 1 | Problema |
|---|---|---|
| `' no es un destino declarado.` | `'It's not a stated destiny.` | «destino» es *destination* |
| `' no dejó ningún átomo de proteína.` | `'he didn't leave any protein atoms.` | sujeto inventado |
| `(0-1, mayor = más 'drug-like').` | `(0-1, major = plus drug-like).` | «mayor» es *higher*, «más» es *more* |
| `tiene '` | `He's got '` | fragmento |

Conclusión: **el catálogo existente se audita antes de ampliarse** (Fase 1). La auditoría confirmó que los cuatro ejemplos eran entradas muertas de fragmento y los retiró. En total eliminó 368 claves muertas; 126 también eran fragmentos. El informe inicial conserva las 771 entradas y su clasificación en `docs/api/i18n-catalogo-auditoria-inicial.json`. Se conservaron las entradas vivas y se corrigieron seis traducciones.

### 2.4 Contrato que no puede romperse

**La salida en español es byte a byte la actual.** Todas las pruebas, goldens y sellos existentes siguen valiendo porque el
idioma por defecto es `es` y la capa nueva no toca nada en ese caso.

---

## 3. Reglas que no se pueden romper

Cada una viene de un fallo real (ver `AGENTS.md`, «Restricciones», y `docs/versions/1.0.2_cambios.md`).

1. **`backend/services/chemistry/pose_physical_validity.py` está SELLADO** por `PROD-PV-H-01` y `PROD-PV-H-01-PRE`. No cambies **un solo byte**
   (ni tildes ni saltos de línea). Sus textos se traducen **sólo** por catálogo en la capa de presentación. Compruébalo con
   `python scripts/validar_sellos.py --check` antes de **cada** commit que toque `backend/`. (Ya pasó: un script de edición normalizó
   256 líneas de un fichero sellado y rompió los sellos.)
2. **No edites `scripts/artifacts_science/`** (artefactos sellados con hashes).
3. **No importes `openbabel`, `pybel` ni `_openbabel`** desde `backend/` ni `rescoring/` (frontera GPL, `docs/79_ADR_FRONTERA_OPEN_BABEL.md`).
4. **No toques los datos de la persona.** Una cadena sólo se traduce si **coincide entera** con una entrada o plantilla conocida. Un nombre
   de molécula o de caso nunca coincide; no uses traducción por palabras sueltas ni por «si contiene».
5. **No cambies números, unidades, hashes, identificadores, rutas ni códigos** (`REVIEW_OUT_OF_VALIDATED_TARGET`, `SMILES_NO_ADMISIBLE`, …). Se conservan tal cual.
6. **No suavices una cautela científica** al traducir. «No garantiza validez científica» no pasa a «may not be fully validated». Es el producto.
7. **Español sin cambios.** Si necesitas cambiar un texto español para poder traducirlo (p. ej. partir una frase armada con `+`), es un cambio aparte, mínimo, y la prueba de «español idéntico» (Fase 0) debe seguir verde.
8. **Inglés americano** (center, color, catalog, license, canceled, labeled…). Lo vigila `frontend/lib/__tests__/inglesAmericano.test.ts` para el frontend; para el backend se añade el mismo control (Fase 1).
9. **Glosario** `docs/GLOSARIO_EN.md`: «Caja de búsqueda» → *Search box*, «exhaustividad» → *exhaustiveness*, «corrida» → *run*, «semilla» → *seed*, «Parámetros de la evaluación» → *Evaluation parameters*, «acoplamiento» → *docking*, etc. Si falta un término, **añádelo al glosario en el mismo commit**.
10. **Nada de red ni descargas** (ni modelos, ni ESMFold). **No empujes** (`git push`) y no cambies de rama en el árbol principal: trabaja en un worktree propio.
11. **Una fila en `docs/versions/1.0.2_cambios.md` por commit**, con el formato de tabla completo `| (id, este commit) | fecha | tipo | texto | no |`. El fichero es CRLF.
12. **Mensajes de commit en español**, con el trailer de coautoría que indique el entorno.

---

## 4. Diseño

Una sola función, tres escalones, y tres sitios donde se aplica.

### 4.1 `traducir(texto, idioma)`

Módulo nuevo `backend/core/i18n_plantillas.py` (o ampliar `core/i18n.py`; mantén **un** sitio):

1. **Exacta**: `ENGLISH_MESSAGES[texto]` o con espacios normalizados (lo que ya hace `translate_text`).
2. **Plantilla**: entradas `(es, en)` con marcadores con nombre, p. ej.
   `("Se pidieron {pedidas} conformaciones y se generaron {conseguidas}: la cobertura geométrica es menor que la solicitada.",
   "{pedidas} conformers were requested and {conseguidas} were generated: geometric coverage is lower than requested.")`.
   El español se compila a una expresión regular anclada (`^…$`, literales escapados, `{x}` → `(?P<x>.+?)`); las rachas de espacio fijo
   admiten normalización. El patrón se aplica al texto original y el inglés se rellena con **lo capturado, sin reformatear**, incluidos
   números, identificadores y espacios internos. Los marcadores del inglés deben ser **los mismos** que los del español (prueba automática).
3. **Por frases, todo o nada**: si el texto es varias frases (`". "`) y **cada** frase casa con el escalón 1 o 2, se traducen todas y se conserva el separador original; si alguna no casa, **el texto entero se queda en español**.
   Mezclar idiomas en un párrafo es peor que dejarlo entero en español.

Sin coincidencia → se devuelve el original. Nunca se lanza.

### 4.2 Dónde se aplica

| Frontera | Cómo |
|---|---|
| Respuestas JSON de la API | Ampliar `_MESSAGE_FIELDS` con los campos de texto humano que hoy se escapan (auditar **cada** modelo de respuesta: `etiqueta`, `razon`, `observacion`, `nota`, `titulo`, `label`, `summary`, `limits`, `assumptions`, `uncertainties`, `title`, `hint`, `reasons`…). No añadas campos que puedan llevar datos de la persona (`name`, `source_name`, `molecule_name`, `smiles`). `localize_payload` pasa a llamar a `traducir`. |
| Dossier, PDF y paquete | Un único gancho en `api/routers/evaluation_dossier.py` (`dossier_preview`, `dossier_package`, `dossier_preparacion`) y en el de cohortes (`api/routers/evaluation_cohort_runs.py`, `services/cohort/dossier.py`): `dossier = traducir_dossier(dossier, current_locale())`, función que recorre el modelo (dataclasses congeladas: `dataclasses.replace`) y traduce los campos de texto. `services/dossier/pdf.py` y `package.py` (README, descripciones del manifiesto) traducen sus rótulos fijos con la misma función. |
| Corridas en segundo plano | **No se traducen en el momento de ejecutar**: lo que se guarda en la base queda en español (es evidencia, un registro). Se traduce **al servir** (JSON) o **al exportar** (dossier). |

### 4.3 Invariantes (cada una tiene su prueba)

- `es` ⇒ salida idéntica a la actual (instantánea de la Fase 0).
- `en` ⇒ ninguna cadena traducida contiene caracteres propios del español (`áéíóúñ¿¡`) salvo nombres propios y los datos de la persona.
- Las plantillas del español y del inglés tienen **los mismos marcadores**.
- Una cadena que no casa sale **igual que entró**.
- El ZIP es **determinista por idioma** (mismos inputs y mismo `generated_at` ⇒ mismos bytes), y `scripts/verify_dossier_package.py` lo valida en ambos idiomas. El hash de `dossier.pdf` difiere entre idiomas; el manifiesto lo recoge.

---

## 5. Fases

Cada fase termina con un commit (o varios), la fila de changelog, sus pruebas **que fallan sin el cambio**, y las puertas de §7.

### Fase 0 · Línea base (medio día)

1. Worktree propio desde `codex/release-hygiene` o desde la rama que indique el propietario: `git worktree add D:\moldesign-worktrees\traduccion -b traduccion/entregable <base>`. Junctions de `frontend/node_modules` y `models/` como en `scripts/qa_sandbox/README.md`; copia de `data/molgraph_seed.db`.
2. Medir y guardar: `python scripts/report_test_counts.py --check`, suites completas (§7), `validar_sellos --check`, `generate_goldens --check`, `generate_openapi_contract --check`. Anota los números.
3. **Instantánea del español**: con un fixture fijo (`backend/tests/fixtures_dossier.py`) y `generated_at` fijo, guarda el JSON del dossier, el README del ZIP y el manifiesto en `backend/tests/snapshots/dossier_es/`. Prueba `test_dossier_en_espanol_no_cambia.py` que las compara. **Esta prueba es la red de seguridad de todo lo demás.**
4. Script `scripts/inventario_i18n.py` (Apéndice A): escribe `docs/api/i18n-inventario.json` con cada cadena española (clave, fichero:línea, si es f-string con su plantilla `{marcador}`, si está traducida). Es la fuente de verdad del avance.

**Aceptación:** instantánea y inventario commiteados; todo en verde sin cambiar código de producto.

### Fase 1 · Auditar el catálogo existente (1 día)

1. `scripts/auditar_catalogo_i18n.py`: lista las 771 entradas del catálogo previo a la auditoría con su problema: **fragmento** (la clave empieza o acaba a mitad de frase, o empieza por comilla suelta), **clave muerta** (ningún literal del backend la produce), **sospechosa** (lista de §6.2), **idéntica** al español, **con caracteres españoles** en el inglés.
2. Resolver cada una: se retiraron 368 claves sin salida literal completa (126 también eran fragmentos); se corrigieron seis traducciones vivas y se conservaron las 403 entradas restantes. Los fragmentos dinámicos se traducirán como plantillas en la Fase 2.
3. Prueba `test_catalogo_ingles_sin_defectos.py`: sin fragmentos, sin claves muertas, sin los pares de mala traducción de §6.2, sin caracteres españoles, sin grafías británicas, glosario respetado y mismo conjunto de marcadores. El guardián **demuestra que ve** (muestras que deben saltar y muestras que no; es una regla del repositorio).

**Aceptación:** catálogo limpio (403 entradas); `test_catalogo_ingles_sin_defectos.py` y `test_i18n.py` en verde. La auditoría de partida está archivada en `docs/api/i18n-catalogo-auditoria-inicial.json`; el informe actual queda en `docs/api/i18n-catalogo-auditoria.json`.

### Fase 2 · La función y las plantillas (1 día)

Implementar §4.1 con sus pruebas: exacta, plantilla (números sin reformatear, varios marcadores, marcador repetido), por frases todo-o-nada, sin coincidencia, español sin cambios, **dato de la persona que se parece a una plantilla** (no debe traducirse: prueba con un nombre de molécula inventado).

**Aceptación:** pruebas verdes; ningún cambio de comportamiento con `es`.

### Fase 3 · Gancho en el dossier, el PDF y el paquete (completada el 2026-10-04)

1. `traducir_dossier` y su uso en los tres endpoints del caso y en el de cohortes (§4.2).
2. `pdf.py` y `package.py`: rótulos fijos y README por `traducir`. Los nombres de fichero ya son ASCII (`8bcc5e4`).
3. Primera comprobación **real**: genera el paquete de una corrida con `Accept-Language: en`, descomprime y lee README + PDF. Anota lo que sigue en español: es la lista de trabajo de la Fase 4.

**Resultado y lista de trabajo:** los endpoints del caso (`preview`, `preparacion`, `package`) y de cohorte (`preview`, `package`) reciben una vista localizada. El PDF traduce portada, rótulos de tablas, estados, glosario y encabezados; el README traduce título, campos de identidad, encabezados y glosario. `dossier_model.json` y `evidence_summary.json` traducen sólo campos de texto conocidos, y el hash del modelo del manifiesto corresponde a los bytes emitidos. El nombre de caso/cohorte, `source_name`, SMILES, snapshots crudos, rutas, IDs, hashes, códigos y estados internos permanecen sin traducir.

La lectura extraída de PDFs reales confirma inglés en esos rótulos y mantiene el nombre de caso. Queda español en los párrafos explicativos del PDF y del README, las instrucciones de reproducción, parte de la auditoría de preparación, las observaciones que todavía no tengan entrada exacta o plantilla y el cuerpo del dossier de cohorte. Esos textos son trabajo de las capas 1 y 2 de la Fase 4. `pypdf` no está en el runtime embebido: los tests de extracción se omiten allí cuando no está instalado; la comprobación real de esta fase se ejecutó con el Python de desarrollo, que sí lo trae.

Verificación de esta fase en el inventario v1: backend embebido **3305 pasadas / 55 omitidas / 2 xfailed**; frontend **1421/1421** y `tsc` limpio; inventario **4952 pendientes**; catálogo **489 entradas / 0 problemas**; sellos **167/0**, goldens **8**, OpenAPI **2 artefactos**, snapshots españoles idénticos y conteo **3360**. Después, la reconciliación v2 excluyó docstrings, fragmentos que no son mensajes independientes y declaraciones de plantilla; el inventario actual previo a Fase 4 queda en **2694 pendientes**. Se añadió al autotest del auditor una muestra de traducción invocada dentro de un f-string dinámico para que ese caso no vuelva a quedar invisible.

**Aceptación:** cumplida para la primera capa de exportación; el contenido español restante queda enumerado arriba para Fase 4.

### Fase 4 · Traducir por capas (el grueso; 3–5 días)

Orden de prioridad (lo que ve un tercero primero). Cada capa: traducir → `scripts/inventario_i18n.py` → el pendiente de **esa capa** baja a 0 → commit.

| Capa | Ficheros (cadenas fijas / f-strings; pendientes según inventario v2) | Por qué ahí |
|---|---|---|
| 1 | `services/dossier/package.py` (50/0; 0), `taxonomy.py` (8/0; 0), `pdf.py` (45/4; 0), `verify.py` (10/24; 0) | Es lo primero que abre quien recibe el ZIP. |
| 2 | `services/dossier/model.py` (230/28; 223), `bloques_protocolo.py` (38/6; 30), `preparacion.py` (99/11; 104), `services/cohort/dossier.py` (61/4; 15) | Cuerpo del dossier y de la auditoría de preparación. |
| 3 | `services/blockchain/evidence_summary.py` (62/9; 53), `services/blockchain/pdf_generator.py` (119/15; 113), `services/chemistry/censo_de_aguas.py` (1/0; 1), `structural_evidence.py` (4/3; 5), `pipeline/protocols/m5/zinc.py` (1/4; 5) | Avisos y límites que viajan con el resultado. |
| 4 | `services/docking/preflight.py` (134/31; 85), `queue_handler.py` (26/14; 40), `services/pipeline/runner.py` (10/7; 15), `api/routers/evaluation*.py` (134/23; 107), `chem/validator.py` (8/22; 28) | Lo que la interfaz en inglés enseña al comprobar y ejecutar (decisión «traducir lo posible»). |
| 5 | `services/chemistry/pose_physical_validity.py` (12/8; 20 pendientes medidos) — **sellado: sólo catálogo** | Validez física; ver §3.1. |
| 6 | El resto del backend por orden de cadenas pendientes; consultar `docs/api/i18n-inventario.json` | Sólo lo que llegue a la interfaz o al entregable. |

En cada paréntesis se indica `cadenas fijas / plantillas JoinedStr; pendientes`, según la v2. Los fragmentos internos de f-strings, docstrings y declaraciones de plantilla no son salidas independientes y no se suman al pendiente. Las cifras siguen siendo inventario de fuentes de salida, no un recuento de lo que aparece en una corrida concreta. Consulta `docs/api/i18n-inventario.json` para el detalle actual por ruta y línea.

Reglas de traducción en §6. Para **f-strings con números** escribe la plantilla con los marcadores de la f-string.
Para textos armados con `+` o por trozos condicionales, la Fase 7 (modo de faltantes) dirá cuáles quedan.

**Aceptación por capa:** pendiente de la capa = 0 en el inventario; muestreo de §6.3 aprobado; español idéntico.

**Capa 1 completada el 2026-10-04.** El README, la receta, el PDF y el informe del verificador salen en inglés con `Accept-Language: en`; los identificadores, rutas, códigos y datos del caso se conservan. El manifiesto también traduce sus explicaciones de exclusión y procedencia. El auditor normaliza espacios al cotejar catálogo y fuente, para reconocer mensajes cuyos saltos de línea forman parte de la salida española.

Muestra de 40 cadenas revisada: [`docs/api/i18n-muestra-capa-1.md`](api/i18n-muestra-capa-1.md), 0 errores de sentido. El control negativo de `test_dossier_verification_i18n.py` falla al retirar temporalmente el cambio del verificador. La instantánea española pasa byte a byte con Python 3.11.9 embebido. Verificación: backend **3308 pasaron / 55 omitidas / 2 xfailed**; conteo registrado **3363**; frontend **1421/1421** y TypeScript limpio; catálogo **575/0 defectos**; inventario **2630 pendientes globales, 0 en capa 1**; sellos **167/0**, goldens **8**, OpenAPI **2 artefactos**.


**Capa 2 completada el 2026-10-04.** `model.py`, `bloques_protocolo.py`, `preparacion.py` y `cohort/dossier.py` traducen las cadenas completas auditadas y las composiciones dinámicas que se pueden describir sin alterar capturas; nombres de caso y cohorte, SMILES, IDs, estados internos, rutas, hashes y cifras se conservan. La plantilla genérica `del catálogo` se estrechó a un conteo numérico: una prueba negativa confirma que no altera un nombre que contenga esa frase. El auditor de catálogo volvió a **0 defectos**, y el inventario refinado registra **0 pendientes en la capa 2** (model 218/24; protocolo 34/5; preparación 92/3; cohorte 79/5; fijas/plantillas).

Muestra de 40 cadenas revisada: [`docs/api/i18n-muestra-capa-2.md`](api/i18n-muestra-capa-2.md), **0 errores de sentido**. El control negativo de `test_plantillas_de_la_capa_dossier_traducen_composiciones_completas` falla al retirar temporalmente las plantillas de la capa. La instantánea española permanece idéntica. Verificación con Python embebido: backend **3315 pasaron / 56 omitidas / 2 xfailed**; conteo recolectado **3371**; frontend **1421/1421** y TypeScript limpio; catálogo **895/0 defectos**; inventario **2172 pendientes globales / 0 capa 2**; sellos **167/0**, goldens **8**, OpenAPI **2 artefactos**. Los tests embebidos de extracción `pypdf` siguen omitidos porque esa dependencia no viaja en el runtime; pruebas con ReportLab verifican el texto entregado a ambos renderizadores PDF y que generan bytes PDF reales.

**Capa 3 traducida el 2026-10-04; cierre de suite global pendiente.** El resumen de evidencia localiza sólo los campos de texto visible; el certificado PDF traduce los párrafos de identidad, metodología y cautelas científicas, preservando nombres, SMILES, hashes, versiones y descripciones aportadas. El PDF se genera con ReportLab en la prueba. La auditoría del inventario detectó cuatro centinelas `_generic_prefixes` que no se muestran y dejó **0 pendientes** en las cinco rutas de la capa; el inventario global queda en **1.992**. La muestra de 40 cadenas [`docs/api/i18n-muestra-capa-3.md`](api/i18n-muestra-capa-3.md) se revisó con **0 errores de sentido**. El control negativo retiró temporalmente los archivos de traducción desde `HEAD`; la prueba del PDF falló al reaparecer el título español, y luego se restauraron los archivos byte a byte. Pruebas focalizadas: **38/38**; snapshot española: **1/1**; catálogo: **1.087/0 defectos**; sellos **167/0**, goldens **8** y OpenAPI **2 artefactos**. El registro recolectó **3.375 pruebas**. El intento global avanzó los 27 casos de `test_adaptador_open_babel.py` y quedó en `test_calcula_y_persiste` de `test_admet_post_docking.py`; la ejecución aislada del mismo caso también quedó bloqueada, y tras 10 minutos la suite global se interrumpió sin traceback ni resumen. La capa no se declara cerrada mientras esa puerta siga pendiente.

**Capa 4 traducida el 2026-10-04; cierre de suite global pendiente.** Se cubren preflight, cola, pipeline, validación y todas las rutas `evaluation*.py`. La base reconciliada al inicio de la capa tenía **275 ocurrencias pendientes / 250 textos fuente únicos**; ahora las diez rutas tienen **0 pendientes**. Las cadenas localizan avisos dinámicos conservando valores, y el esquema OpenAPI traduce `summary`, `description` y etiquetas sólo en `/openapi.json`; los campos `description` de payloads ordinarios permanecen sin tocar. La muestra [`docs/api/i18n-muestra-capa-4.md`](api/i18n-muestra-capa-4.md) se revisó: **0 errores de sentido en 40**. Control negativo: al retirar temporalmente el catálogo, las plantillas y el localizador desde `HEAD`, fallaron los siete casos de capa 4; los ficheros se restauraron byte a byte. Pruebas: capa 4 + plantillas + inventario **27/27**, preflight **43/43**, contratos y snapshot OpenAPI **4/4**, snapshot española **1/1**; comprobación programática de **250/250** mensajes con marcadores y valores conservados. Catálogo **1.248/0 defectos**, inventario **1.707 pendientes globales / 0 en la capa**, sellos **167/0**, goldens **8**, OpenAPI **2 artefactos**; el registro recolecta **3.383 pruebas**. La suite global conserva el bloqueo documentado en la capa 3 y no se cuenta como aprobada.

### Fase 5 · Los textos que escribe el frontend (1 día)

`frontend/lib/__tests__/interfazSinTextoFijo.test.ts` mide actualmente 0 literales visibles con sus criterios y tiene un presupuesto global de 0. La cifra histórica de 206/57 no aplica al árbol actual. El inventario AST de `finish-i18n-frontend.cjs` mide otra población y no sustituye este criterio de visibilidad.

**Aceptación:** el presupuesto visible permanece en 0; `idiomasCompletos` e `inglesAmericano` siguen en verde. Si una fase posterior introduce texto visible, se traduce con `t()` y se baja el presupuesto del fichero correspondiente.

**Fase 5 completada el 2026-10-04.** `npx tsc --noEmit` pasó; las tres guardas de idioma pasaron **18/18**, y la suite frontend completa pasó **1.421/1.421 en 154 archivos** con Vitest en `threads`, un solo worker y sin paralelismo por archivo. El modo predeterminado `forks` falló al intentar abrir rutas temporales de AppData (`ENOENT`); el modo serial resolvió ese límite del entorno sin fallos de pruebas.

### Fase 6 · Unificar «caja de búsqueda» en el backend y regenerar goldens (medio día)

Sustituir en los textos del backend «caja de docking», «caja de acoplamiento», «caja de trabajo» por «caja de búsqueda»; y «caja efectiva» por
«caja de búsqueda efectiva» **a la vez** en `services/dossier/*.py`, `services/blockchain/*`, `services/docking/preflight.py`, `lib/evaluationEvidence.ts`
y `frontend/lib/__tests__/evaluationEvidence.test.ts` (que fija «caja efectiva»). Eso **sí cambia el español**: es una excepción a §3.7, aprobada por el
propietario; regenera **una sola vez** la instantánea del español y los goldens: `python scripts/generate_goldens.py` y revisa cada diferencia a ojo.
No toques `pose_physical_validity.py` (sellado): su «caja de docking» queda hasta el próximo re-sellado y se documenta.

**Aceptación:** diferencias de goldens y de instantánea explicadas una a una en el commit; sellos intactos.

**Fase 6 completada el 2026-10-04.** En las rutas estipuladas, los rótulos y mensajes usan «caja de búsqueda» y «caja de búsqueda efectiva»; `pose_physical_validity.py` permanece intacto. Se sincronizaron el catálogo inglés, el glosario y las pruebas. La instantánea regenerada cambió `dossier.json` y los hashes/tamaños dependientes de ese cambio en `manifest.json`; `README.md` quedó idéntico. `generate_goldens.py` se ejecutó una vez: reescribió los ocho goldens, sin diferencia de bytes en ninguno. El catálogo queda en **1.249 entradas / 0 defectos**; el inventario, en **1.707 pendientes globales** y cero en las rutas de la capa. Pruebas focalizadas: dossier/modelo/paquete **63 pasaron / 1 omitida**; catálogo y evidencia **36/36**; frontend **24/24**; snapshot español aprobado; sellos **167/0**, goldens **8** y OpenAPI **2 artefactos**. La suite backend completa se intentó con Python 3.11.9: tras los primeros 27 casos, no avanzó durante dos minutos en `test_admet_post_docking.py::test_calcula_y_persiste`; se interrumpió sin resumen. Queda pendiente y no se cuenta como aprobada.

### Fase 7 · Modo de faltantes y recorrido real (1–2 días)

1. Añade `MOLDESIGN_I18N_REPORT=1`: con idioma `en`, cada texto de un campo traducible que **parece español** (marcas de castellano) y no casó se anota (una vez) en `data/i18n_faltantes.jsonl` con el endpoint y el texto. Sólo registra; no cambia ninguna salida.
2. Levanta la cápsula de QA (`node scripts/qa_sandbox/sandbox-up.mjs --agente N`; léete `scripts/qa_sandbox/README.md`) con la interfaz en inglés y recorre con datos reales: evaluación con y sin residuos, receptor no disponible, Batch con filas rechazadas, péptido (sólo si el propietario autoriza descargar ESMFold: **no lo descargues tú**), dossier y paquete.
3. Convierte cada faltante en plantilla o entrada; repite hasta que el recorrido no registre ninguno.

**Aceptación:** `i18n_faltantes.jsonl` vacío tras un recorrido completo; lo que no se pueda traducir está listado en `docs/api/i18n-pendiente.md` con su motivo.

**Recorrido ejecutado el 2026-10-04.** Con el reporter opt-in habilitado, la API sirvió evaluación, resultados y advertencias; se exportaron vista previa PDF y paquete ZIP. Batch comprobó un CSV de dos filas (una elegible y una SMILES inválida) sin guardar cohorte ni ejecutar docking; el catálogo marcó 1EPB como no disponible y dio el motivo de Meeko en inglés. El reporte no se creó porque no encontró faltantes: cero filas. El PDF tiene 9 páginas y se leyó completo; el ZIP declara y contiene 28 archivos, con cero errores y avisos en el verificador. Los identificadores científicos permanecen intactos. [`docs/api/i18n-pendiente.md`](api/i18n-pendiente.md) registra los identificadores conservados y la ruta ESMFold no ejecutada.

**Recorrido visual y export final verificados.** Se reconstruyó `frontend/out` desde el árbol actual con `sandbox-up.mjs`; el manifiesto confirma que la huella coincide, no hay puerto horneado y la cápsula responde `/health`. En la interfaz inglesa se comprobaron los estados y fechas de caso, detalles pendientes, cadenas del receptor, almacenamiento, pestañas y las tres disposiciones científicas. Batch mostró en inglés una fila elegible y una fila SMILES inválida; el receptor 1EPB quedó «Unavailable» con el motivo de Meeko. Se descargó el PDF por HTTP 200 (103.828 bytes) y el ZIP (198.188 bytes); el verificador confirma 28/28 archivos, 0 errores y 0 avisos. El PDF de nueve páginas se leyó completo. No se ejecutó la ruta de péptidos ni se descargó ESMFold. Tras el recorrido, `i18n_faltantes.jsonl` no existe: 0 entradas registradas.

### Fase 8 · Verificación y cierre (medio día)

§7 entera, `python scripts/report_test_counts.py --write`, actualiza las cifras de `AGENTS.md` («Estado y honestidad») **sólo si el registro las cambia**, y escribe en `D:\moldesign-audits\evaluacion-agente1\hallazgos.md` (o el registro que indique el propietario) qué queda abierto.

**Fase 8 completada el 2026-10-04.** La suite backend dio **3.334 pasadas, 56 omitidas y 2 xfail** (19 avisos de dependencias); la suite frontend **1.434 / 1.434 en 156 archivos**; `npx tsc --noEmit` quedó limpio. El contador oficial registra **3.390 pruebas recolectadas** con Python embebido 3.11.9; `--write` y `--check` coinciden. Inventario: **1.687 pendientes globales / 0 en las capas cubiertas**; catálogo **1.288 / 0 defectos**; sellos **167 / 0 distintos**; goldens **8**; OpenAPI **2 artefactos**. La build de exportación estática terminó y prerenderizó 15/15 rutas. El registro externo de hallazgos se actualizó; ESMFold no se descargó ni se ejecutó, como exige §3.10.

---

## 6. Calidad de la traducción

La traducción la hace un agente de menor coste, y la decisión del propietario fue «sólo la traducción de Claude, sin revisión externa»: por eso la calidad se **mide**, no se supone.

### 6.1 Cómo traducir

- Fiel y llana; frases cortas; el tono del español (sobrio, sin adornos). Voz del producto: «declara», «se abstiene», «no garantiza».
- Terminología del campo de docking en su forma de la literatura: *pose, docking, exhaustiveness, search box, receptor, ligand, hotspot, binding site, affinity (kcal/mol), RMSD, protonation, tautomer, stereochemistry, cofactor, run, cohort, dossier*.
- «No evaluado» es *not evaluated* (no *unevaluated*): el estado tiene nombre propio y su sentido es «no se midió», no «salió mal».
- Conserva mayúsculas de las clasificaciones (`REVISAR` → `REVIEW`, `ABSTENCIÓN` → `ABSTENTION`, `REGISTRADO` → `RECORDED`, `NO_EVALUADO` → `NOT EVALUATED`) **si y sólo si** son rótulos visibles; los códigos internos no se traducen.

### 6.2 Controles automáticos (todos en `test_catalogo_ingles_sin_defectos.py` y `test_traduccion_del_entregable.py`)

- Pares de mala traducción **prohibidos**: «mayor»→*major* (es *higher/larger*), «más»→*plus* (es *more*), «destino»→*destiny* (es *destination*), «instalación»→*facility* (es *installation*), «sujeto»→*subject* (en «token inválido: subject» es el campo JWT; revísalo), *he/she* en frases sin sujeto, «corrida»→*race* (es *run*), «hotspots»→*hot spots*, «contacto»→*contact* ok, «afinidad»→*affinity* ok.
- Razón de longitud inglés/español fuera de `[0,4 ; 2,5]` ⇒ revisión manual.
- Mismos marcadores `{x}` en las dos columnas; mismos números y mismos códigos en mayúsculas.
- Inglés sin caracteres españoles; inglés americano (lista de `frontend/lib/__tests__/inglesAmericano.test.ts`).
- **Glosario**: si el español contiene un término del glosario, el inglés contiene su equivalente (`caja de búsqueda` ⇒ `search box`).

### 6.3 Revisión por muestreo (obligatoria al final de cada capa de la Fase 4)

El agente produce un fichero `docs/api/i18n-muestra-capa-N.md` con **40 cadenas al azar de la capa** (español, inglés, fichero:línea). La revisa el propietario o una sesión con un modelo mayor. **Una capa no se da por cerrada** si en la muestra hay más de 2 errores de sentido (no de estilo); en ese caso se repasa la capa entera.

---

## 7. Puertas (orden y órdenes)

Desde la raíz del worktree, con el intérprete que se distribuye (`D:\moldesign-build\python-embed\python.exe`, Python 3.11.9):

```powershell
$env:MOLDESIGN_TESTING = "1"
& D:\moldesign-build\python-embed\python.exe -m pytest backend/tests -q -p no:cacheprovider --no-header   # suite completa (~5 min)
& D:\moldesign-build\python-embed\python.exe scripts\validar_sellos.py --check        # 167 sellados, 0 distintos
& D:\moldesign-build\python-embed\python.exe scripts\generate_goldens.py --check      # 8 corridas doradas
& D:\moldesign-build\python-embed\python.exe scripts\generate_openapi_contract.py --check
& D:\moldesign-build\python-embed\python.exe scripts\report_test_counts.py --check    # y --write al final
cd frontend; npx tsc --noEmit; npx vitest run                                         # suite completa (~2 min)
```

Orden de **verificación de cada cambio de backend**: prueba nueva (debe fallar sin el cambio: `git stash push -- <fichero>`, ejecútala, `git stash pop`), suite
completa, **sellos**, goldens, OpenAPI. Línea base de partida (2026-10-04, rama `qa/agente1-evaluacion`): backend 3256 pasan / 53 omitidas / 2 xfail; frontend 1391 pasan en 150 ficheros y `tsc` limpio.

Fase 0 ejecutada sobre `0da7a86` con Python 3.11.9: backend 3283 pasaron / 53 omitidas / 2 xfailed; frontend 1421/1421 en 154 ficheros y `tsc` limpio; sellos 167/0, goldens 8, OpenAPI 2 artefactos, conteo registrado 3336 y 4692 pendientes en el inventario v1. La instantánea ES (JSON, README y manifiesto) compara byte a byte.
Fase 1 sobre el catálogo depurado: backend 3288 pasaron / 53 omitidas / 2 xfailed; conteo registrado 3341; frontend 1421/1421 en 154 ficheros y `tsc` limpio; sellos 167/0, goldens 8, OpenAPI 2 artefactos, catálogo 403/0 defectos e inventario 4987 pendientes. La instantánea ES sigue comparando byte a byte.
Fase 2: backend 3301 pasaron / 53 omitidas / 2 xfailed; conteo registrado 3354; frontend 1421/1421 en 154 ficheros y `tsc` limpio; sellos 167/0, goldens 8, OpenAPI 2 artefactos; catálogo 403/0 defectos; inventario 849 coincidencias (847 exactas y 2 plantillas), 4987 pendientes. Instantánea ES byte a byte. El control negativo de `test_i18n_plantillas.py` falla al retirar el módulo de producto.

Verificación sobre el **artefacto**, no sólo el código (restricción 1 de `AGENTS.md`): reconstruye el export con `node scripts/qa_sandbox/sandbox-up.mjs --agente N --rebuild`
y abre el dossier en inglés en el navegador. Si tocas algo que afecte a estilos, CSP o empaquetado, `npm run smoke:prod` (necesita el runtime «staged» y es del propietario).

---

## 8. Trampas conocidas de este repositorio (todas costaron tiempo)

- **Los heredocs de Bash se comen las barras invertidas** en rutas de Windows. Usa la herramienta de escritura de ficheros para crear scripts `.py` y ejecútalos; edita con `Edit`, o con un script que **respete el salto de línea de cada fichero** (muchos son CRLF; unos pocos, mixtos).
- **Un script de edición que «normaliza» saltos de línea** altera ficheros enteros (rompió un fichero sellado). Edita sólo las líneas que cambian.
- **`git stash` es el control negativo**: antes de dar una prueba por buena, comprueba que **falla** sin el cambio.
- **Una guardia tiene que demostrar que ve**: incluye muestras que deben saltar y muestras que no; un detector con un carácter de control mal puesto anunció «limpio» sobre un export sucio.
- **Una prueba con regex `re.S` y `.*` voraz** perdió un lado de un conflicto de fusión sin avisar. Para ficheros de texto, trabaja por líneas.
- **`commit` + changelog**: la fila es la **fila completa** de la tabla, no una frase. Dos commits dejaron texto suelto en el changelog y lo detectó la fusión.
- **Un `page.tsx` de Next sólo puede exportar la página**: cualquier otro `export` rompe la comprobación de tipos del build. Las utilidades van a `lib/`.
- **El texto español de las claves `auto_*` del frontend lleva un hash**: no cambies el español de esas claves, sólo el inglés.
- **No hay nunca `localhost:8000` por defecto**: el puerto del backend lo elige Rust; en la cápsula es `18010 + N`.
- **No ocupes el servidor ni la VM de pruebas** sin preguntar; siempre con `--memory`.

---

## 9. Qué NO hacer

- No traducir con una herramienta automática y dar el resultado por bueno: pasa por §6.
- No añadir **fragmentos** al catálogo; añade la **frase entera** o una plantilla.
- No traducir por palabras sueltas ni por «contiene».
- No tocar `pose_physical_validity.py`, `scripts/artifacts_science/` ni los sellos.
- No regenerar goldens antes de la Fase 6, ni subir un presupuesto del ratchet del frontend, ni borrar una guardia que molesta.
- No dar una fase por cerrada sin su prueba que **falla sin el cambio**.
- No empujar, no cambiar de rama en el árbol principal, no descargar modelos.

---

## 10. Definición de hecho

1. Capas 1–3 de la Fase 4 con pendiente **0**; capa 4 (preflight y avisos) con pendiente 0 o listado en `i18n-pendiente.md` con su motivo; capa 5 sólo por catálogo.
2. `traducir_dossier` aplicado en los cuatro endpoints (caso: vista previa, paquete y preparación; cohorte); el ZIP y su verificador válidos en `es` y `en`.
3. `test_dossier_en_espanol_no_cambia.py` verde (salvo la excepción única de la Fase 6, explicada).
4. Recorrido completo de la Fase 7 sin faltantes.
5. Muestras de la Fase 4 aprobadas.
6. Suites completas, sellos (167 / 0), goldens (8), OpenAPI y conteos en verde; presupuesto del frontend menor y sin subidas.
7. Un dossier de verdad generado en inglés, **leído** de principio a fin por quien cierra la tarea, sin español salvo datos de la persona.
8. Registro y changelog al día; lo abierto, escrito.

**Estimación honesta:** de 8 a 12 días de trabajo de un agente, con tres puntos de revisión del propietario: (a) tras la Fase 1 (catálogo auditado y glosario), (b) tras la capa 1 de la Fase 4 (el README y el PDF de portada en inglés, para que lo lea una persona real),
(c) final. Si el calendario de 1.0.2 no aguanta, el corte natural es **tras la capa 3**: lo que ve un tercero al abrir el paquete ya está en inglés y el resto queda declarado.

---

## Apéndice A · Scripts de medida

`scripts/inventario_i18n.py` recorre `backend/**/*.py` (sin componentes `tests`, `migrations`, `scripts`) y extrae por AST los `ast.Constant` de tipo `str` y los `ast.JoinedStr`. Para cada f-string elegible sustituye cada expresión formateada por un marcador `{n1}`, `{n2}`…; sus constantes hijas también pueden aparecer como fragmentos fijos independientes. El filtro exige de 14 a 400 caracteres, espacios y marcas de castellano (`[áéíóúñ¿¡]` o una palabra función: `el la los las de del que con sin una un por para se no es en`). Escribe `docs/api/i18n-inventario.json`; `--check` falla si aumentan las ocurrencias pendientes. Esta definición explícita sustituye la medición original, cuyo script no se conservó.

Línea base reproducible (árbol `0da7a86`, 2026-10-04):

| Fichero | Fijas (`Constant`) | f-strings (`JoinedStr`) | En catálogo | Pendientes |
|---|---:|---:|---:|---:|
| `services/dossier/model.py` | 285 | 28 | 46 | 267 |
| `services/docking/preflight.py` | 189 | 33 | 100 | 122 |
| `services/blockchain/pdf_generator.py` | 161 | 17 | 32 | 146 |
| `services/ai/chat_service.py` | 120 | 27 | 29 | 118 |
| `services/dossier/preparacion.py` | 115 | 11 | 6 | 120 |
| `core/models.py` | 98 | 4 | 0 | 102 |
| `services/blockchain/evidence_summary.py` | 86 | 10 | 31 | 65 |
| `services/docking/queue_handler.py` | 69 | 16 | 23 | 62 |
| `services/cohort/dossier.py` | 71 | 7 | 42 | 36 |
| `api/routers/evaluation.py` | 76 | 6 | 20 | 62 |
| `services/dossier/pdf.py` | 56 | 4 | 10 | 50 |
| `services/dossier/verify.py` | 39 | 24 | 0 | 63 |
| `services/dossier/bloques_protocolo.py` | 44 | 6 | 17 | 33 |
| `services/chemistry/pose_physical_validity.py` (sellado; sólo lectura) | 34 | 8 | 9 | 33 |
| **Todo el backend** | **5.452** | **733** | **1.493 ocurrencias** | **4.692** |

Esta tabla conserva la medición v1 como registro histórico. La v2 excluye docstrings, los fragmentos `Constant` que sólo componen un f-string y los módulos que definen el propio catálogo y las plantillas; compara marcadores por orden para enlazar una declaración con su uso. Su punto de partida vigente está en la tabla de §2.1 y el archivo `docs/api/i18n-inventario.json`.

## Apéndice B · Prompt listo para pegar al agente delegado

> Eres un agente de ingeniería trabajando en el repositorio MolDesign (Windows). Tu tarea es ejecutar, de principio a fin, el plan de
> `docs/94_PLAN_TRADUCCION_DEL_ENTREGABLE.md`: que el dossier PDF, el README del ZIP, el JSON del dossier y los textos de backend que se ven en
> pantalla salgan en inglés cuando el cliente manda `Accept-Language: en`, **sin cambiar ni un byte de la salida en español** (salvo la excepción
> única y explicada de la Fase 6).
>
> Antes de escribir nada: lee `AGENTS.md` entero, `docs/GLOSARIO_EN.md`, `scripts/qa_sandbox/README.md` y las secciones 3, 6 y 8 del plan. Trabaja en un worktree
> propio (`git worktree add …`); nunca cambies de rama en el árbol principal ni empujes. No toques `backend/services/chemistry/pose_physical_validity.py`
> (sellado) ni `scripts/artifacts_science/`; ejecuta `python scripts\validar_sellos.py --check` antes de cada commit que toque `backend/`. No importes `openbabel`.
> No descargues modelos ni uses ESMFold. No uses heredocs de Bash para escribir scripts con rutas de Windows: usa la herramienta de escritura de ficheros.
>
> Trabaja **por fases en el orden del plan**, un commit (o varios) por fase, mensajes en español, y **una fila completa** de la tabla en
> `docs/versions/1.0.2_cambios.md` por commit (el fichero es CRLF). Cada cambio lleva una prueba que **falla sin él** (compruébalo con `git stash`). No des una
> fase por cerrada sin pasar las puertas de la sección 7. Detente y avisa al propietario en los tres puntos de revisión de la sección 10 y siempre que algo no cuadre
> con lo medido en el plan: las cifras son del 2026-10-04.
>
> La calidad de la traducción se mide, no se supone: respeta el glosario, el inglés americano, la lista de pares prohibidos de la sección 6.2 y entrega las muestras
> de la sección 6.3. Nunca traduzcas datos de la persona, números, códigos ni hashes; nunca suavices una cautela científica.

## Apéndice C · Ejemplos (antes y después)

| Español (como sale hoy) | Inglés esperado | Tipo |
|---|---|---|
| `Sin residuos de referencia la corrida no calcula qué residuos del sitio contactan las poses.` | `Without reference residues the run does not compute which site residues the poses contact.` | exacta |
| `Se pidieron {pedidas} conformaciones y se generaron {conseguidas}: la cobertura geométrica es menor que la solicitada.` | `{pedidas} conformers were requested and {conseguidas} were generated: geometric coverage is lower than requested.` | plantilla |
| `{n} elegidos de {total} del catálogo: {lista}` | `{n} selected out of {total} in the catalog: {lista}` | plantilla (la `lista` es de identificadores, no se toca) |
| `Esta corrida es anterior al sellado de los residuos de referencia. No se sustituyen por los del catálogo: podrían no ser los que se usaron.` | `This run predates the recording of reference residues. They are not replaced with the catalog ones: they may not be the ones used.` | dos frases, todo o nada |
| `EXPERIMENTAL: la estructura la predice ESMFold y su calidad no está validada en MolDesign` | `EXPERIMENTAL: the structure is predicted by ESMFold and its quality has not been validated in MolDesign` | exacta (rótulo) |
| `Inhibición de ACE — cribado inicial` (nombre de un caso) | *(sin cambios)* | **dato de la persona: nunca se traduce** |
