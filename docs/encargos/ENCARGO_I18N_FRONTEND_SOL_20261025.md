# Encargo: castellano que se cuela en la interfaz en inglés — GPT Sol 6.1

**Fecha del encargo:** 2026-10-25
**Commit anclado:** `4fc7a928` (rama `codex/release-hygiene`, versión declarada 1.0.4)
**Ejecutor:** GPT Sol 6.1
**Alcance:** **sólo `frontend/`**. Nada de backend, Rust, motores ni ciencia.
**Naturaleza:** inventario + arreglos + guardianes, en tres fases con puerta de
aceptación entre cada una. Puede durar varias sesiones.
**Idioma de los entregables:** castellano. **Idioma de la interfaz que se audita:** inglés.

---

## 0. Antes de leer nada más

Tres frases que gobiernan este encargo:

1. **Con la aplicación en English, el usuario no debe leer castellano en ningún
   estado alcanzable**: ni en la pantalla inicial, ni en un resultado, ni en un
   error, ni en un tooltip, ni en el texto que aparece después de pulsar cuatro
   botones. La Microsoft Store rechaza por calidad una aplicación cuyos idiomas
   declarados no están realmente soportados, y el paquete declara `es-ES` y `en-US`.
2. **Lo que se verifica tiene que ser lo que se entrega** (restricción 1 de
   `AGENTS.md`). Las pruebas de este repositorio dicen hoy que no queda castellano
   pendiente, y el propietario lo ve en la pantalla. Las dos cosas son ciertas a
   la vez; tu trabajo empieza por entender por qué.
3. **Un guardián tiene que demostrar que ve** (restricción 2). Todo detector que
   escribas o amplíes lleva autotest con muestras que debe marcar y muestras que no.

Lee `AGENTS.md` completo antes de empezar, en especial «Construir» y
«Restricciones que no debes romper». Después lee los ficheros de la sección 2.

---

## 1. El problema, medido el 2026-10-25 sobre `4fc7a928`

El propietario usa la aplicación en inglés y encuentra frases en castellano
sueltas. Algunas están a la vista; otras sólo aparecen después de una acción:
al terminar una evaluación, en los resultados concretos de distintas pestañas,
en avisos y estados de error.

Los guardianes actuales no las ven. Esto es lo que se midió antes de escribir
este encargo (verifícalo tú; no lo cites como medido por ti):

| Guardián | Qué mira | Qué dice hoy |
|---|---|---|
| `scripts/finish-i18n-frontend.cjs` + inventario `lib/__tests__/textoPendienteDeTraducir.json` | literales visibles **sólo en `.tsx`** de `app/`, `components/` y `hooks/` (`finish-i18n-frontend.cjs:262-263`) | inventario vacío: `[]` |
| `lib/__tests__/interfazSinTextoFijo.test.ts` (trinquete `MARCAS_ES`) | las mismas carpetas (`CARPETAS`, línea 32) | `PRESUPUESTO_TOTAL = 0` (línea 108) |
| `context/__tests__/idiomasCompletos.test.ts` | que `es` y `en` tengan las mismas claves | verde |
| `context/__tests__/inglesAmericano.test.ts` | grafías británicas en `TRANSLATIONS.en` | verde |

Huecos que ya se ven sin ejecutar nada (son pistas, no el inventario):

- **`lib/` no lo mira nadie.** 36 ficheros `.ts` de `lib/` contienen literales con
  tildes o eñes fuera de comentarios y pruebas, entre ellos `evaluationEvidence.ts`,
  `structuralEvidence.ts`, `resultFieldPresentation.ts`, `preflight.ts`,
  `dossier.ts`, `errors.ts`, `api.ts`, `proApi.ts`, `pipelineStream.ts`,
  `pipelineDefinitions.ts`, `molcy.ts`, `moldex.ts`, `cohorts.ts`, `registro.ts`,
  `procedenciaDeSenales.ts`, `sitioDelReceptor.ts`, `seleccionDeResiduos.ts`,
  `selectividadMargen.ts`, `targetGrouping.ts`, `catalogoDeReceptores.ts`,
  `decisionesDeCaso.ts`, `reporteDeIA.ts`, `softwareCatalog.ts`, `visor3d.ts`,
  `webgl.ts`, `tauri.ts` y `lib/cases/*`. Más `hooks/useScrollLock.ts` y
  `context/motivoDeTurno.ts`. Muchos son comentarios o mensajes de consola; otros
  son exactamente el texto de los resultados que el propietario ve. Separarlos es
  parte del trabajo.
- **Funciones que componen texto fuera de React.** Algunas ya reciben el traductor
  como parámetro (`lib/preflight.ts:242`, `lib/modulosDescargables.ts:3`,
  `lib/controlesFisicos.ts:22`), y `preflight.ts:244` todavía compara contra la
  cadena castellana `"No definido"`. Ése es el patrón a seguir y el antipatrón a buscar.
- **Formato de fechas y números.** Hay unas 20 llamadas a `toLocaleString`/
  `toLocaleDateString` o con `"es-MX"`/`"es-ES"` fijos. Las que eligen por
  `locale` están bien (`app/history/page.tsx:21`); las que no pasan locale toman
  el del sistema operativo, no el de la aplicación.
- **Texto que llega del backend.** Avisos, motivos de abstención, errores HTTP
  (`detail`), estados de una corrida en streaming, nombres de etapa. El backend
  está fuera de alcance (sección 3), pero su texto se ve en la interfaz y hay que
  inventariarlo.

---

## 2. Cómo funciona el i18n del frontend (léelo antes de tocar nada)

- `context/LanguageContext.tsx`: `useLanguage()` da `t(clave, valores?)` y
  `locale`; `interpolar()` sustituye `{variable}`. Tiene un bloque histórico de
  claves en línea.
- `context/traducciones/*.ts`: **un módulo por superficie** (`evaluacion`,
  `resultados`, `pro`, `lote`, `moldex`, `molcy`, `ia`, `opciones`, `catalogo`,
  `casos`, `registro`, `notificaciones`, `paneles`, `paginas`, `comun`…). Cada uno
  exporta `{ es, en }` con exactamente las mismas claves. `index.ts` explica por qué.
  Una clave nueva va al módulo de su superficie, no al bloque histórico ni a
  `generadas.ts`.
- El inglés es **americano** (decisión del propietario, 2026-10-04).
- Los **códigos de aviso** (`CODIGOS_DE_AVISO`, p. ej. `DECODIFICADO_LATIN1`,
  `VALIDADOR_EXCEDIO_EL_PLAZO`) se muestran tal cual por diseño. No se traducen.
  Lo que sí se traduce es el texto humano que los acompaña, si lo genera el frontend.

---

## 3. Alcance (no negociable)

**Dentro:** todo lo que vive en `frontend/` y se pinta en la ventana: `app/`,
`components/`, `hooks/`, `context/`, `lib/`, `public/` (textos), y las pruebas y
scripts de `frontend/scripts/` que hagan falta para los guardianes.

**Fuera, aunque veas castellano:**

- `backend/` entero (incluidos sus mensajes, avisos y el PDF del dossier).
- `frontend/src-tauri/` (Rust: notificaciones nativas, diálogos del sistema,
  `vigia_webview.rs`). Si ves texto ahí, inventárialo con origen `rust`.
- `tools/` (motor Molcy, Vina…), `scripts/artifacts_science/` (sellados: **no se
  tocan nunca**), `docs/papers/`.
- Componentes de terceros: Ketcher (editor de moléculas), Mol* (visor 3D).
  Inventárialos con origen `tercero` si muestran castellano, sin parchearlos.
- Contenido del usuario o de datos: nombres de caso, de moléculas, de receptores
  del catálogo, respuestas de MolChat (salida del LLM).
- `frontend/public/tutorial/molcy/` y `lib/tutorial/molcy-marcas.json`: **se
  generan, no se retocan** (ver 6.4).

**Texto del backend que se ve en la interfaz:** no lo arregles en el backend ni lo
traduzcas en el frontend **comparando la cadena castellana** (eso se rompe en
cuanto alguien reescribe el mensaje, y es el antipatrón de `preflight.ts:244`). Hay
dos salidas aceptables:

1. Si el backend ya manda un **código estable** junto al texto, el frontend puede
   traducir por código, con la frase castellana como respaldo si llega un código
   desconocido. Cada correspondencia nueva lleva prueba.
2. Si no hay código, se **inventaría** con origen `backend` (endpoint, campo,
   ejemplo literal, cómo llegar) para un encargo posterior. No se toca.

---

## 4. Entorno de trabajo

### 4.1 Worktree aparte (obligatorio)

No trabajes en `D:\moldesign-build`. Crea el tuyo desde el commit anclado:

```bash
git -C D:/moldesign-build worktree add -b sol/i18n-frontend D:/moldesign-worktrees/sol-i18n 4fc7a928
```

Commits en `sol/i18n-frontend`. **No empujes nada a ningún remoto** (restricción 8
de `AGENTS.md`: la rama de desarrollo nunca va al repositorio público) y no
fusiones en otra rama: la integración la hace el propietario.

### 4.2 La aplicación, como usuario

Usa una cápsula de QA (`scripts/qa_sandbox/README.md`), no `next dev`: la cápsula
sirve el export estático con la CSP de producción y un backend con el entorno de
la app instalada.

```bash
node scripts/qa_sandbox/sandbox-up.mjs --agente 1
```

Abre `http://localhost:13011` (nunca `127.0.0.1`). Cambia el idioma a **English**
en Opciones y comprueba que queda guardado al recargar. Con `--reset` vuelves a
«primer uso», que es un estado distinto que también hay que recorrer. Tras
cambiar código, `--rebuild`.

Las evaluaciones son **con Vina real** (exhaustividad 8 por defecto: tarda poco).
No descargues ESMFold (8,4 GB), Blender ni modelos de MolChat: recorre sus
tarjetas de descarga, estados «no instalado» y mensajes, no la descarga.

### 4.3 Qué puedes ejecutar

`npm run test:run`, `npm run typecheck`, `npm run lint`, `npm run test:e2e`,
`npm run test:ux`, `npm run smoke:prod`, `node scripts/finish-i18n-frontend.cjs`
(`--json`, `--autotest`), Playwright contra la cápsula, la cápsula misma.
**No** ejecutes `npm run tauri:build` ni `stage:desktop`.

---

## 5. Falsos positivos conocidos: esto NO es un hallazgo

- Siglas y nombres de producto que se escriben igual en los dos idiomas (lista
  `SIGLAS` y `NOMBRES_PROPIOS` de `finish-i18n-frontend.cjs`): Vina, SMILES, PDBQT,
  RMSD, kcal/mol, Moldex, Molcy, MolChat…
- El nombre del idioma en el selector («Español»).
- Códigos de aviso en MAYÚSCULAS_CON_GUIONES (sección 2).
- Campos y enums de formatos de archivo (`canonical_smiles`, `control_role`…):
  traducirlos rompe el CSV/SDF.
- Comentarios, `console.*` y mensajes sólo para desarrolladores que nunca llegan a
  la ventana. Comprueba que de verdad no llegan (un `throw new Error("…")` que
  luego se pinta en un aviso **sí** es interfaz).
- Contenido del usuario y de datos (sección 3).

---

## 6. Las tres fases

Al final de cada fase, **para** y entrega lo de esa fase. El propietario lo revisa
antes de que empiece la siguiente.

### FASE A — Inventario (sin cambiar código de producto)

Dos barridos independientes, y la comparación entre ellos.

**A1. Barrido estático.** Amplía *en una copia aparte* (o con un flag) el barrido
de `finish-i18n-frontend.cjs` a `lib/**/*.ts`, `hooks/**/*.ts` y `context/**/*.ts`
(fuera de `traducciones/` y de `__tests__/`). Para cada literal con castellano
decide, abriendo el código, si llega a la ventana. «Llega» incluye: retorno de una
función que acaba en JSX, `title`, `aria-label`, `placeholder`, `alt`, texto de un
toast o notificación, contenido de un `Error` que se muestra, nombre de archivo
descargado, texto copiado al portapapeles.

**A2. Recorrido dinámico en English.** Con la cápsula, recorre la aplicación como
usuario y captura cada pantalla y cada estado donde aparezca castellano. Mira el
texto visible **y** los atributos (`title`, `aria-label`, `placeholder`), los
tooltips al pasar el ratón y los diálogos. Un script Playwright que vuelque
`innerText` y esos atributos en cada estado y los pase por un detector de
castellano te ahorra trabajo y es la semilla del guardián de la fase C.

Recorrido mínimo (amplíalo con lo que descubras; anota lo que no pudiste alcanzar):

1. **Primer uso** (cápsula recién reseteada): bienvenida, avisos, campana de
   notificaciones, Inicio, tutorial de Molcy.
2. **Evaluación, preparación del caso:** crear caso; selector de receptores con las
   tres secciones (Verificados, Tus receptores, Demostración) y la búsqueda;
   etiqueta «Demostración» en cada vista que la lleve; subir un receptor propio por
   los caminos A (PDB crudo), B (preparado) y C (PDBQT), incluido un rechazo (un
   archivo inválido); ligando por SMILES y por el editor; un SMILES inválido;
   parámetros de la evaluación (menú de motores: Vina, ESMFold apagado, «Vía API»
   sin conectar); caja del sitio.
3. **Comprobación previa y Preparación:** un receptor que pase, uno que pida
   revisión y uno que se abstenga (los hay en Demostración: metales retirados junto
   al sitio, huecos, copias del ligando). Lee cada aviso desplegado.
4. **Ejecutar y resultados:** progreso en streaming y nombres de etapa; cancelar una
   corrida; terminar una; cada pestaña y panel de resultados: poses, afinidad,
   evidencia de la evaluación, evidencia estructural, interacciones, controles
   físicos (incluida una etapa «no evaluada»), procedencia de señales, ADMET
   experimental, drug-likeness, visor 3D y su leyenda, mapa de contactos.
   Guardar en Moldex. Exportar/descargar el dossier (el PDF es del backend: sólo
   comprueba que el frontend pide el idioma correcto y que los textos de la
   descarga están en inglés).
5. **Moldex:** lista, detalle de una corrida guardada, comparación, filtros, tiers.
6. **Lotes / Batch:** importar una cohorte (CSV y SDF), duplicados y excepciones,
   ejecutar, resultados, cohortes guardadas.
7. **Molcy:** estudio de fotos (CPU), estados sin GPU para vídeo, historial de
   trabajos, Blender no instalado.
8. **MolChat / Intérprete IA:** ajustes del proveedor, modelos recomendados sin
   descargar, entrada por voz, un turno fallido.
9. **Historial, Comunidad, Registro científico, Certificación** (devnet).
10. **Opciones, Legal, Acerca de, Ayuda.**
11. **Errores:** backend parado («motor desconectado»), receptor no disponible,
    petición que devuelve 4xx/5xx, cola de guardado de casos con error.
12. **Fechas y números** en todas las pantallas anteriores: separador decimal,
    formato de fecha, unidades.

**Entregable de la fase A** (en `docs/auditorias/i18n-frontend-2026-10-25/` dentro
de tu worktree):

- `inventario.json`: una entrada por hallazgo, con este esquema:

  ```json
  {
    "id": "I18N-001",
    "texto": "literal tal como aparece",
    "origen": "frontend_tsx | frontend_lib | formato | backend | rust | tercero",
    "archivo": "frontend/lib/evaluationEvidence.ts:123",
    "superficie": "Evaluación > Resultados > Evidencia",
    "como_llegar": "pasos exactos desde una cápsula recién reseteada",
    "captura": "capturas/I18N-001.png",
    "visto_por": "estatico | dinamico | ambos",
    "propuesta": "clave nueva / clave existente / traducir por código / inventariar"
  }
  ```

  Para origen `backend`, `archivo` es el endpoint y el campo
  (`POST /evaluation/... → avisos[].mensaje`), y cuando lo encuentres, la línea del
  backend que lo produce (sólo como referencia).
- `INFORME_FASE_A.md`: totales por origen y por superficie; **qué vio el barrido
  dinámico que el estático no, y al revés**, con la causa de cada ceguera; lo que no
  pudiste alcanzar y por qué.
- `glosario.md`: los términos del producto en los dos idiomas tal como **ya** los usa
  `TRANSLATIONS.en` (Evaluation, Batch, Preparation, Not evaluated, Demo…). Donde el
  diccionario actual use dos traducciones para un mismo término, señálalo; no lo
  unifiques todavía.

### FASE B — Arreglos

Un commit por superficie (p. ej. «i18n: resultados de la evaluación»), cada uno con
sus pruebas en verde. Reglas:

- **La clave va al módulo de su superficie** en `context/traducciones/`, con `es` y
  `en`. Reutiliza una clave existente si dice exactamente lo mismo; no dupliques.
- **El castellano no se reescribe** de paso. El texto `es` nuevo es el literal que
  había, palabra por palabra. Si ves una errata o una afirmación dudosa en el
  castellano, anótala en `observaciones.md`; no la corrijas en este encargo.
- **El inglés dice lo mismo que el castellano, ni más ni menos.** Este producto
  existe para decir cuándo no confiar en un número: no suavices «NO EVALUADO»,
  «se abstiene», «Demostración», «no calibrado», «experimental», ni conviertas un
  «no se demostró» en «no funciona» o en «funciona». Respeta el glosario.
- **Funciones fuera de React reciben el traductor como parámetro** (patrón de
  `lib/preflight.ts:242` y `lib/modulosDescargables.ts:3`). No importes el hook en
  `lib/`. Donde una función devuelva texto ya compuesto, valora que devuelva una
  clave y sus valores y que componga el componente.
- **Nada de comparar contra la cadena castellana** para decidir lógica
  (`preflight.ts:244`). Si lo encuentras, sustitúyelo por un valor estructurado y
  añade prueba.
- **Fechas y números** con el `locale` de la aplicación (reutiliza
  `lib/formatoNumerico.ts` si cubre el caso), nunca con el del sistema.
- **Interpolación** con `{variable}`; no concatenes trozos de frase traducidos por
  separado (el orden de las palabras cambia entre idiomas).
- **Pruebas**: cada componente o función que cambie lleva una prueba que lo renderice
  o lo llame en `en` y compruebe que no sale castellano, y en `es` que sale el texto
  de antes. Las instantáneas que cambien se regeneran, no se editan a mano.
- **No subas presupuestos ni añadas entradas al inventario** del trinquete para que
  una prueba pase. Si una prueba se queja, es que hay texto sin traducir.
- **Registro de cambios:** añade una entrada por commit (o por lote) en
  `docs/versions/1.0.4_cambios.md`, con el estilo de las existentes.

**6.4 Tutorial de Molcy.** Si cambia un texto visible en Evaluación o Molcy que salga
en las capturas del tutorial, regenera con
`frontend/scripts/capturas-tutorial-molcy.mjs` contra una cápsula nueva por idioma.
Si no puedes, decláralo en el informe; no edites las imágenes ni
`molcy-marcas.json` a mano.

### FASE C — Guardianes que miran el artefacto

Lo que deja este encargo, más que los arreglos, es que no vuelva a pasar.

1. **Ampliar el barrido estático** a `lib/`, `hooks/` y `context/` (fuera de
   `traducciones/` y `__tests__/`), con las mismas reglas de visibilidad, en
   `finish-i18n-frontend.cjs` y en el trinquete de `interfazSinTextoFijo.test.ts`.
   Amplía su autotest: muestras de `lib/` que deben marcarse (un `return "Sin
   datos"` que acaba en JSX, un `throw new Error("…")` que se muestra) y que no
   (un comentario, un `console.warn`). Lo que quede pendiente de verdad va al
   inventario con su motivo, y el propietario decide.
2. **Guardián en el export, en English.** Una prueba Playwright (junto a
   `e2e/`, ejecutable por `npm run test:e2e` o con un script propio) que sirve el
   export real, pone la app en English, recorre los estados de la fase A que se
   puedan alcanzar sin Vina (o con un backend simulado donde ya lo haya) y falla
   si encuentra castellano en `innerText`, `title`, `aria-label` o `placeholder`.
   Con lista blanca explícita y nombrada (siglas, «Español», códigos de aviso) y
   **con un control positivo**: un estado plantado con un texto castellano que la
   prueba debe detectar. Una prueba que no demuestra que ve no vale (restricción 2).
3. Comprueba que los guardianes nuevos **fallan** al revertir uno de tus arreglos,
   y anota el comando y la salida.

**Verificación antes de entregar cada fase B o C:** `npm run test:run`,
`npm run typecheck`, `npm run lint`, `npm run test:e2e`, `npm run test:ux` y
`npm run smoke:prod` (toca el export: es obligatorio). Repite el recorrido de A2 en
English sobre el export reconstruido y adjunta capturas antes/después de cada
hallazgo cerrado.

---

## 7. Reglas de evidencia

- Todo hallazgo lleva `ruta:línea` o endpoint, y los pasos para llegar a él.
- Todo arreglo cita los `id` del inventario que cierra.
- Si citas una cifra de este encargo o del repositorio sin volver a medirla, márcala
  como citada. Si la mides, da el comando.
- No inferir de un nombre: que una función se llame `etiquetaEn…` no prueba que
  devuelva inglés. Ábrela.
- Si algo no lo pudiste comprobar, dilo en `lo_que_no_pude.md`. Un hueco declarado
  vale; un hueco escondido invalida la entrega.

---

## 8. Cómo sobrevive una tarea larga

Mantén `docs/auditorias/i18n-frontend-2026-10-25/PROGRESO.md` al día: fase actual,
último commit, superficies cerradas, superficies pendientes, y el siguiente paso
concreto. Al retomar una sesión, léelo antes que nada y comprueba con
`git log` que coincide.

---

## 9. Entrega final

- La rama `sol/i18n-frontend` con un commit por superficie y los guardianes.
- En `docs/auditorias/i18n-frontend-2026-10-25/`: `inventario.json` (con el estado
  final de cada entrada: `cerrado` con commit, `backend`, `rust`, `tercero` o
  `pendiente` con motivo), `INFORME_FASE_A.md`, `INFORME_FINAL.md`, `glosario.md`,
  `observaciones.md`, `lo_que_no_pude.md`, `PROGRESO.md` y `capturas/`.
- `INFORME_FINAL.md` responde, con cifras y rutas:
  1. ¿Cuántas cadenas castellanas visibles en English había, por origen y superficie?
  2. ¿Cuántas quedan, y por qué cada una?
  3. ¿Por qué los guardianes anteriores no las veían?
  4. ¿Qué detecta ahora cada guardián nuevo, y cómo se demostró que ve?
  5. ¿Qué texto del backend o de Rust hace falta para cerrar del todo el inglés,
     listo para un encargo siguiente?

---

## 10. Confirmación antes de empezar

Antes de la fase A, responde con:

- el commit sobre el que trabajas (`git rev-parse HEAD` en tu worktree) y que el
  árbol está limpio;
- el estado de la cápsula (`--estado`) con el idioma en English;
- tu plan para A1 y A2 en pocas líneas, y cualquier punto de este encargo que te
  parezca ambiguo o imposible, **antes** de resolverlo por tu cuenta.
