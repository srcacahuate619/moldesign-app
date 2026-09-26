# Fase 5 — bitácora de corrección local

Fecha: 2026-09-25 (America/Mexico_City). Auditoría base: `ae4db6a7aef0f4c14af7b74da350578abbd80074`.

## Rama, procedencia y alcance

- Rama `codex/audit-phase-5`; worktree `D:\moldesign-build\.worktrees\audit-phase-5`.
- Padre local de fase 4: `2d0233cc7cb376ff5bc54973eca84cb0dba4a86b`.
- Commit local de fase 5: `c3aa4689c57087f20afd92bef0df678d4eff7cfb`. Árbol Git limpio al cerrar. No hubo push ni integración a main.
- Temporales, cachés y runtime de prueba se mantuvieron en D:. Las cachés `.cargo-target`, `.npm-cache` y `.pip-cache` creadas para esta fase se borraron tras verificar sus rutas. No se usó el servidor Ubuntu: los fallos de Host, rutas Windows, Tauri, CSP y empaquetado requerían la plataforma distribuida.

## Cambios y motivos

### 5.1 — API-002 y API-013: frontera del backend local

`TrustedHostMiddleware` acepta sólo los hosts de loopback/Tauri previstos; los métodos no seguros con `Origin` ajeno al CORS configurado se rechazan. El arranque Rust genera 32 bytes aleatorios por proceso y los entrega al backend como `MOLDESIGN_LAUNCH_TOKEN`; la WebView obtiene ese secreto por IPC y `desktop-login` exige `X-MolDesign-Launch`. El secreto no aparece en `/health`, en el estado público ni en logs. Los tokens de invitado quedan ligados por hash al arranque y duran 30 minutos (access) o un día (refresh), frente a diez años antes. Reiniciar el proceso invalida su vínculo.

Se exigió identidad en el arranque manual de motores, descargas de receptores y rutas de red que la necesitaban. El smoke del bundle comprueba una petición sin secreto (403) y otra con el secreto del arranque (200). La validación de `Origin` actúa sobre peticiones que lo presentan; un proceso local con acceso directo al loopback sigue siendo parte del modelo de amenaza y depende de la autenticación de cada ruta.

### 5.2 y 5.6 — API-003, API-009 y API-010: identidad y tokens

El espacio anónimo se identifica por correo reservado, no por el nombre `demo`. Se bloquean registros que intenten ocupar identidades reservadas y se normaliza un ocupante histórico al inicializar la cuenta interna. El login de una cuenta sin contraseña devuelve 401; contraseñas que exceden 72 bytes UTF-8 se rechazan con 422 antes de bcrypt.

Cada JWT exige `exp`, `iat`, `sub`, `type` y `jti`; un refresh no sirve como access. SQLite v28 conserva JTI revocados: `/auth/refresh` rota y revoca el refresh anterior, y `/auth/logout` revoca access y refresh de la cuenta. El traspaso desde invitado exige un access token invitado del mismo arranque. Se evitó atribuir consentimiento a un OAuth externo antes de autenticar: en modo escritorio la ruta responde 403.

### 5.3 — API-006: privacidad de estadísticas e imágenes

`/stats/global` sólo cuenta moléculas y certificaciones de la cuenta actual; sin sesión devuelve cero y afinidad desconocida. `/stats/leaderboard` devuelve sólo resultados propios y limita la cantidad. No se publica una mejor afinidad si las evaluaciones de la cuenta abarcan varias dianas, porque las afinidades Vina entre receptores distintos no forman un ranking científico. `/chem/render/{id}` exige propiedad de la molécula y prohíbe caché compartida. La portada dejó de presentar resultados privados como ranking comunitario; las descargas comunitarias usan la ruta autenticada.

### 5.4 — API-007 y API-012: rutas, URLs y consentimiento de red

Los IDs de RCSB se validan antes de construir URLs; los IDs locales admitidos excluyen separadores y unidades. Las lecturas locales comprueban `resolved.is_relative_to(base)` para que un enlace simbólico no saque un PDB del directorio permitido. La búsqueda, metadatos, cofactores, descarga de PDB, AlphaFold, descargas de modelos y RPC devnet pasan por la puerta de consentimiento de red con identidad de petición. Se eliminó una consulta cloud prescindible en descarga comunitaria. MolChat propaga el usuario a su autocompletado PubChem.

### 5.5 — API-004, API-005 y API-014: límites científicos

El esquema rechaza cajas con dimensiones fuera de 5–80 Å, centros no finitos o de magnitud mayor a 10000 Å, exhaustividad fuera de 1–128, poses fuera de 1–20, ensembles superiores a 64, listas de hotspots mayores a 128, perfiles clínicos mayores a 64 KiB y etapas no ejecutables. El upload y las variantes de receptor usan la misma validación de caja antes de escribir. Se distingue el origen del centro del origen del tamaño en preflight; un valor elegido por el usuario ya no se atribuye al catálogo. Las entradas inválidas producen 422. La regla explícita de `openmm` retirado conserva su motivo particular.

### 5.7 — API-015: dependencias del runtime

Se actualizaron `python-multipart` 0.0.22→0.0.32, `starlette` 1.0.0→1.7.0, `PyJWT` 2.8.0→2.15.0, `cryptography` 42.0.7→50.0.1, `pillow` 12.2.0→12.3.0 y `aiohttp` 3.14.1→3.14.3. El lock embebido se regeneró con `scripts/lock_embedded_runtime.py`, y el SBOM con su generador. El nuevo lock refleja 168 distribuciones reales; el encabezado anterior decía 173, aunque la única distribución retirada fue `openbabel-wheel`, que ya no debe viajar como binding Python en la frontera de programa independiente.

**Pendiente:** no se ejecutó un `pip-audit` actualizado ni se añadió su gate al build: el informe base registra 111 avisos en 13 paquetes, y actualizar estos seis no demuestra que el resto esté resuelto. `pip check` informa la dependencia preexistente `aimsim-core → padelpy` ausente. El auditor debe tratar API-015 como mitigación de los paquetes priorizados, no como cierre de todas las vulnerabilidades.

### 5.8 — API-011, API-016, API-018 y API-020: evidencia y abstención

La cirugía de proteínas ya no promete usar un SMILES que ignoraba, usa directorio temporal con limpieza y no devuelve una ruta efímera del servidor. Si fallan detectores de metal o validación de átomos, responde 503 en vez de un falso resultado negativo. Un fallo al calcular grupos quelantes deja un aviso tipado. MM-GBSA sólo se publica en progreso si su resultado se persistió; el fallo de persistencia se registra como error. El certificado PDF advierte cuando faltan pose o receptor. La vía cuántica existente ya se abstiene y avisa en vez de imputar 0,5 silenciosamente.

Open Babel pasa a fail-closed si falta el hash de `bin/obabel.exe`; la guarda G5 exige esa entrada. La verificación de Solana exige que la wallet declarada en el memo figure entre los firmantes de la transacción. Hay pruebas negativas para ausencia de secreto, JWT inválidos, wallet no firmante, PDB IDs maliciosos, caja fuera de rango y acceso a estadísticas ajenas.

**Pendiente:** API-016 inventaría 248 `except` amplios. Se corrigieron las rutas científicas indicadas como críticas para esta fase; no se afirma que todos los `except` del inventario hayan desaparecido.

## Verificaciones

- Backend con Python embebido: **2676 pasadas, 28 omitidas** (242,99 s). Después del último ajuste de contención PDB: **38 pasadas** y **24 pasadas** dirigidas; los grupos se solapan y no se suman.
- Frontend: **1067/1067** pruebas; `npm run typecheck` limpio. El contrato `EvaluationResult` incorporó tres campos que aparecieron al regenerar OpenAPI (`muegge_violations`, `shap_model_id`, `shap_output`); su prueba específica pasó.
- `cargo check --offline -q` pasó con target en D:. `npm run build:desktop` generó el export estático. `generate_openapi_contract.py --check`, `lock_embedded_runtime.py --check` y `generate_sbom.py --check` pasaron.
- Bundle reconstruido tras los últimos cambios: **34787 archivos, 1573,4 MiB**. `check:openbabel` pasó 16 comprobaciones, incluida conversión real PDBQT→SDF. `verify:desktop-runtime` pasó: 680 binarios nativos, 5927 importaciones, cero sin resolver (siete ausencias declaradas). `check:dossier-embebido` comparó diez casos con desarrollo y goldens.
- `check:evaluation-runtime` pasó con Vina real y dos contratos: PRO 65,9 s, normal 27,1 s; evidencia local `D:\moldesign-build\.worktrees\audit-phase-5\tmp\evaluation-runtime-20260925T065159Z`.
- `smoke:prod` sobre backend embebido, export y CSP: **15/15**, incluidos los dos casos de secreto de lanzamiento. Export: 237 archivos sin URL de backend fija; 16 CSS/HTML sin recursos remotos.
- `git -c core.whitespace=cr-at-eol diff --cached --check` pasó. Se usó `cr-at-eol` porque un archivo histórico conserva CRLF.

## Límites para la revisión

No se construyó un instalador NSIS nuevo ni se probó una instalación limpia. El smoke usa Chromium sobre el export y el backend empaquetado; no equivale a WebView2 instalado. Tampoco se hizo una auditoría nueva de vulnerabilidades de todas las dependencias, ni una revisión de los 248 `except` amplios. Los cambios de consentimiento dependen de que cada nuevo destino de red se registre y se pruebe al añadirse. Esta rama queda local para la decisión del auditor; no se empujó.
