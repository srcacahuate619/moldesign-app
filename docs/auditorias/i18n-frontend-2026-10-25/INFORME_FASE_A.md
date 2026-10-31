# Fase A — inventario de castellano con la app en English

La aplicación sí presenta castellano en English. El inventario contiene **293 entradas**: mensajes o plantillas de presentación, campos humanos de API y seis dependencias de formato. No es un recuento de palabras ni el número de ocurrencias: una plantilla con números distintos cuenta una vez; un documento propio sin variante inglesa cuenta una vez. Las ramas no reproducidas se distinguen de lo observado. No se ha cambiado producto, diccionario, backend, Rust ni ciencia.

Base comprobada: `4fc7a9281fecb209a94784d15983475d64b517e8`, rama `sol/i18n-frontend`, worktree `D:\moldesign-worktrees\sol-i18n`. El literal `D:\moldesign-build\..\docs\encargos\…` no existía; se leyó el archivo del mismo nombre que está en `D:\moldesign-build\docs\encargos\`. AGENTS.md se leyó completo y coincidía entre main y worktree. Esta entrega cierra A y se detiene para revisión; B y C siguen sin iniciar.

## Recuento y alcance de la evidencia

| Categoría | Entradas |
|---|---:|
| backend | 39 |
| formato | 6 |
| frontend_lib | 90 |
| frontend_tsx | 155 |
| rust | 3 |

`frontend_lib` incluye los módulos TS de context y tres recursos de public. Los nombres de receptor/molécula/caso, prosa del LLM, textos de papers, códigos científicos y claves de archivos no cuentan como fugas. Los tres registros Rust son referencias estáticas del camino IPC, no observaciones del instalador. Cero entradas de tercero significa que no se observó castellano atribuible a esos componentes en el recorrido; no certifica todos sus menús.

| Categoría | Entradas |
|---|---:|
| Acceso | 6 |
| Batch | 5 |
| Casos | 50 |
| Comunidad | 2 |
| Estado del motor | 14 |
| Evaluación | 130 |
| Evaluación / Moldex | 1 |
| MolChat | 52 |
| Molcy | 3 |
| Moldex | 10 |
| Opciones y legal | 8 |
| Preparación y dossier | 10 |
| Registro científico | 2 |

| Categoría | Entradas |
|---|---:|
| ambos | 35 |
| dinamico | 39 |
| estatico | 219 |

Cada entrada lleva ruta:línea o endpoint/campo, consumidor, navegación, propuesta y limitación cuando procede. `captura: null` significa que no se obtuvo una imagen del literal; una captura de la superficie se guarda aparte y no acredita ese texto. El JSON de cada estado conserva también title, aria-label, aria-description, placeholder y alt. Un atributo accesible no necesita tener texto visible en el PNG para ser una fuga.

Hay **137 estados** y **136 PNG asociados**. Falta PNG de: 84-batch-informe. Los contenedores de la app tienen scroll interno: `innerText` puede incluir texto fuera del viewport. Se añadieron capturas enfocadas para SAR, contexto opcional, leyenda y tabla comparativa; no se afirma que cada frase de un control largo quepa en un solo PNG.

## Cómo se midió

Se usó el export estático real, con CSP de producción, servido por la cápsula agente 1: app `http://localhost:13011`, backend `http://127.0.0.1:18011`. No se usó next dev. Se seleccionó English por la UI y persistió al recargar. Chrome 156 con locale del navegador `es-MX`, distinto del idioma de la app, permitió detectar las fechas dependientes del sistema. Esto prueba el export en Chrome, no WebView2 ni el instalador.

La cápsula fue reseteada antes del primer recorrido. El primer export se construyó en 123 s; el manifiesto limpio después del reset documenta su reutilización. Al parar el backend se detuvo sólo el PID/puerto verificado de la cápsula; se restauró con `--rebuild` (75 s). El segundo manifiesto tiene árbol no limpio por los nuevos archivos de auditoría; no hubo diferencias de producto. Los logs y el manifiesto inicial se conservan como evidencia.

Se ejecutó Vina real con ex=8, 9 poses y semilla 42 para 8HFI/aspirina, 1BN1/aspirina, 6SXC/aspirina y 8T69/4-67, además del lote CSV (dos moléculas únicas y una reutilización). Hubo una cancelación. La corrida de 4-67 alcanzó controles físicos `not_evaluated` por plazo; no es un reanálisis ni una repetición científica del experimento sellado, cuyos archivos sólo se leyeron. Se guardaron corridas de QA en Moldex. La preparación dio revisión o bloqueo; no se demostró un sistema global READY para FEP. Los controles técnicos que pasan no se confunden con readiness global.

Las subidas propias A/B/C y un rechazo se recorrieron con fixtures locales. Se comprobó CSV con duplicados/excepciones, SDF duplicado, cohorte guardada, ejecución y resultados. Se dibujó un anillo con Benzene en Ketcher y su SMILES quedó `C1C=CC=CC=1`; no se ejecutó ese dibujo. Se recorrieron Molcy, configuración de renderizador, fotos CPU y estados ausentes, MolChat/proveedores/voz deshabilitada/turno fallido, Historial, Comunidad, Registro y la vista inicial de certificación. Las descargas individual y de cohorte recibieron HTTP 200 con **Accept-Language: en**; no se audita ni reescribe el PDF backend.

El fallo de cola fue real: sólo se hizo readonly el manifiesto del caso sintético I18N Unavailable, se provocó el guardado, se capturó el sufijo castellano y se restauraron sus atributos Archive; Retry recuperó la cola. La disposición de I18N QA se guardó sólo para comprobar su fecha y declara expresamente que es QA, no una conclusión científica.

## Independencia y comparación de los barridos

Se conserva A2 inicial (capturas 01–88, 101 estados) como material recogido antes de la revisión de candidatos A1. Por prudencia, **todas las capturas 89 en adelante se consideran A2b dirigido por A1**, aunque algunas completan una acción ya prevista. No se presentan esas comprobaciones como descubrimientos independientes. PROGRESO.md anterior situaba el corte en 101; se corrige aquí de forma conservadora.

La copia A1 amplía los roots a app/components/hooks/lib/context y .ts/.tsx, excluye traducciones/tests y conserva literales devueltos, throws y plantillas. v3 produjo **4627 candidatos en 243 archivos**, y 17 llamadas de formato. Son candidatos, no defectos. Tras abrir productores y consumidores: 246 filas AST se relacionan con entradas y 4381 se excluyen con motivo en decisiones-a1.json; quedan 0 sin decisión en ese ledger. Varias entradas manuales no tienen fila del detector: nombres sin tilde, el conector «y #», recursos public y errores backend/Rust.

Esta matriz mide **presencia de la cadena en el DOM inicial guardado**, no memoria humana de haberla advertido entonces, ni precisión/recall del detector:

| Categoría | Entradas |
|---|---:|
| sin productor en A1 / ausente del DOM A2 inicial | 2 |
| sin productor en A1 / presente en DOM A2 inicial | 37 |
| trazado en A1 / ausente del DOM A2 inicial | 234 |
| trazado en A1 / presente en DOM A2 inicial | 20 |

- A2 inicial contiene títulos castellanos de preflight, valores de Preparación, motivos de anti-dianas, estado del proveedor y la insignia de carga «anión −1». A1 de frontend no inspecciona los productores backend; ver I18N-084 para la carga frontend y las entradas POST /evaluation/preflight para la API.
- A1 trazó errores de HTTP/transporte, recuperación, autenticación, indicadores de guardado, nombres de descarga, fechas sin locale y comparaciones crudas que A2 inicial no activó. Cada uno conserva su condición; no se fabricaron resultados para obtener una captura.
- A2b confirmó la comparación de Moldex (I18N-231), los fallbacks SHAP (I18N-106), el historial de corridas, los textos del contexto, el visor Web3D y SAR después de terminar la consulta. En SAR, 93 sólo acreditaba LOADING; 117/118 acreditan el resultado. No se reutiliza 93 como prueba de «2 análogos».
- A1 v1 no veía «Capa Distancia» ni «PESO MOL.»: carecen de tildes y palabras función. v2/v3 añadieron vocabulario diferencial es/en y controles positivos. Aun así la heurística no garantiza reconocer nombres como Alanina o el conector y: se añadieron por lectura y búsqueda AST adicional.
- A2 léxico produjo falsos positivos como `Del` en atajos de Ketcher, `principal` en una frase inglesa de Mol*, nombres I18N y claves `protocolo`. Se excluyeron por contexto, no mediante presupuestos nuevos.

## Por qué los guardianes anteriores están verdes

Se volvió a medir `finish-i18n-frontend.cjs --json`: **[]**, `--autotest`: **60 muestras**; las tres suites de i18n pasan **18/18**. Sus rutas reales son lib/__tests__, no context/__tests__ como citaba el encargo. Los recibos están en evidencia/verificacion.

1. El barrido y trinquete previos miran .tsx de app/components/hooks. No cubren módulos TS de lib/context, recursos public ni productores backend/Rust.
2. Su heurística de visibilidad no sigue retorno/helper/variable hasta JSX, ni resuelve una plantilla que se compone antes de llamar t(). Tener la misma frase base en el diccionario no traduce el resultado ya interpolado.
3. La paridad de claves es real, pero no prueba que los consumidores usen una clave o un alias existente. El diccionario también puede contener inglés de baja calidad: Earrings, It's, grafías británicas.
4. Las fechas sin locale no contienen necesariamente una palabra castellana en el código. Adoptan el locale del navegador/sistema y necesitan revisar la llamada y contrastar el render.
5. Un recorrido que captura sólo el estado de carga pierde el resultado posterior, como ocurrió con SAR. Los textos de error y metadatos accesibles requieren acciones y estados adicionales.

También hubo falsos candidatos importantes: evaluationEvidence se localiza al final y su consumidor pasa t; resultFieldPresentation tiene columnas es/en; sitioDelReceptor desvía a funciones inglesas; errors.ts no tiene consumidores; el panel readiness antiguo no se monta. La tabla M5-Zn y defensas legacy están en pistas-sin-estado-demostrado.json: el padre exige un protocolo que no produjo la corrida M4 actual, por lo que no se contaron sus frases internas como fuga de esa pantalla.

## Verificación y siguiente puerta

La herramienta aparte tiene **23 comprobaciones** positivas/negativas (13 lingüísticas, 4 AST, 4 formato, 2 DOM). La compilación del inventario valida esquema, IDs, rutas/líneas existentes, PNG/DOM y ocho controles del ledger. No sustituye un guardián general: el ledger es una revisión curada del commit base. No se tocó el detector original, su inventario ni sus presupuestos.

No se corrieron tauri:build ni stage:desktop. Los seis comandos completos exigidos en B/C quedan para esas fases; esta entrega de A no afirma haberlos ejecutado. Las limitaciones están en [lo_que_no_pude.md](lo_que_no_pude.md), y las observaciones que no deben corregirse de paso en [observaciones.md](observaciones.md).

Revisar [inventario.json](inventario.json), [glosario.md](glosario.md) y los límites antes de B. Toda entrada sigue pendiente o marcada por su origen externo; **cero arreglos se declaran cerrados**.


# Archivo externo de la evidencia de Fase A

La Fase A fue aceptada por el propietario. El commit original f4a60be7204f4af7417b053d60d5f8f396f30654 se rehízo antes de B para retirar la evidencia pesada. Se copiaron y verificaron los 317 archivos originales, sin sobrescribir sus bytes.

Manifiesto: `F:/Backups/moldesign-evidencia/2026-10-25-i18n-fase-a/MANIFIESTO_SHA256.json`, en el disco del propietario.

SHA-256 del manifiesto: `9440755aecb5e052208160dc6e08eff91736d1e6033fb935d5c79af98482b2f1`. Una copia del manifiesto permanece en evidencia/manifiesto-archivo-sha256.json. El directorio externo conserva las rutas originales bajo repo/.

En el repositorio quedan el informe, inventario, glosario, herramientas y evidencia ligera agregada inferior a 1 MB. Los PNG, red.json, triage-a1.json y los barridos/volcados voluminosos están en el archivo externo. Las referencias del inventario apuntan allí.

Verificación: `node docs/auditorias/i18n-frontend-2026-10-25/herramientas/archivo-fase-a.cjs`. La variable MOLDESIGN_I18N_EVIDENCE_ROOT permite leer una copia reubicada que conserve el mismo manifiesto y SHA-256. No se escribe en el archivo al consultar ni recompilar.
