# 37 — Política de Integraciones Externas

**Fecha:** 2026-08-13
**Estado:** Normativo (decisiones de producto)
**Origen:** Hallazgo F-13 de `docs/AUDITORIA_CONSOLIDACION_DESKTOP_2026-08-09.md`

---

## Principio rector: 0-telemetría

MolDesign es un producto **desktop-first, local y privado**. El software NO envía
telemetría, métricas de uso ni crash reports a terceros. Los errores los reporta
el usuario activamente; el launcher captura logs locales con rotación
(`backend.latest.log`). Esta premisa es un diferenciador de producto frente a
plataformas cloud privadas y NO debe violarse con integraciones silenciosas.

**Criterio de aceptación para cualquier integración nueva:**

1. **Off por defecto** salvo que sea esencial para el núcleo científico.
2. **Consentimiento visible** si alguna vez envía datos fuera de la máquina.
3. **Degradación elegante**: el núcleo (docking, rescoring, persistencia) sigue
   funcionando sin red.
4. Documentada aquí con: datos transmitidos, endpoint, finalidad, default y
   forma de desactivar.

---

## Inventario de integraciones

| Integración | Papel | Estado | Default | Datos transmitidos |
|---|---|---|---|---|
| **RCSB PDB** | Fuente externa de estructuras proteicas (Search API v2 + descarga de .pdb) | ✅ Esencial (dependencia científica) | On-demand | Solo el PDB ID buscado |
| **Proveedores LLM** (MolChat) | Asistente conversacional opcional | ✅ Opt-in | Off | La pregunta del usuario, solo si activa el chat |
| **Solana** | Certificación de resultados | ✅ Se queda — darle MÁS protagonismo (sesión dedicada pendiente) | Off | Por definir en la sesión de producto |
| **Steam** | Licenciamiento/distribución desktop | 💤 Dormant — cimientos listos, activar ~Q4 2026 | Off | SteamID64 + verificación de compra |
| **OAuth Google/Azure** | Identidad opcional | ✅ Se queda | Off | Credenciales de login solo si el usuario elige ese método |
| **PubChem en certificado** | Nombre común/IUPAC del PDF | ❌ **Eliminado (2026-08-15)** | — | Antes transmitía el SMILES automáticamente; el PDF ahora es local. |
| **RCSB/UniProt/Google Translate en certificado** | Completar descripción faltante | ❌ **Eliminado (2026-08-15)** | — | Antes se activaba implícitamente al exportar; el PDF usa contexto local. |
| **Sentry** | Crash reporting | ❌ **ELIMINADO (2026-08-13)** — viola la premisa 0-telemetría | — | — |

---

## Detalle por integración

### RCSB PDB — esencial

- **Qué es**: el *Protein Data Bank* — base pública global de estructuras 3D de
  proteínas.
- **Rol real en MolDesign**: los **387 targets curados vienen empaquetados
  localmente** (`curated_targets.json` + `data/target_library/`, 302/387
  estructuras .pdb incluidas). RCSB se usa on-demand para:
  1. descargar la estructura de los ~85 targets curados cuyo .pdb aún no está
     en el empaquetado local;
  2. la feature online de búsqueda por nombre (`/targets/resolve-name`,
     backend listo; UI de frontend NO cableada aún).
- **Default**: on-demand (solo cuando el usuario prepara un target cuya
  estructura no está local).
- **Desactivar**: modo offline degrada a "target sin estructura local no
  preparable" — el resto del pipeline sigue intacto.
- **Dato transmitido**: únicamente el PDB ID o nombre buscado. No se envían
  moléculas ni resultados.

### Proveedores LLM — opt-in

- MolChat puede delegar preguntas a proveedores externos. El usuario debe
  activar el acceso web explícitamente (`allow_web`); el chat determinista
  local sigue siendo el default.
- **Dato transmitido**: solo el texto de la pregunta que el usuario envíe
  estando el modo web activo.

### Solana — core, con expansión pendiente

- La certificación de resultados sobre Solana **se queda y requiere más
  protagonismo**. Decisión de producto pendiente (sesión dedicada): definir si
  es feature central, qué se certifica on-chain y qué UX debe tener.
- **Dato transmitido**: por definir en esa sesión (hoy: payload de
  certificación cuando el usuario lo invoca explícitamente).

### Steam — dormant hasta Q4 2026

- `backend/api/routers/steam.py` implementa verificación de compra/licencia vía
  Steam Web API. Solo se activa con `STEAM_WEB_API_KEY` configurada.
- **Decisión**: conservar como cimientos (código aislado y funcional), NO
  exponer en UI hasta el lanzamiento de Steam previsto ~fin de 2026.
- **Dato transmitido**: SteamID64 a la API de Steam (solo en el flujo de
  activación de licencia).
- **Cómo se cumple «no exponer» desde el 2026-09-04**: hasta esa fecha esto
  decía «dormant» pero `api/main.py` montaba el router, así que
  `GET /steam/verify` contestaba a cualquiera que la llamara — y sin
  `STEAM_WEB_API_KEY` contesta `verified: true`. El router ya no se monta salvo
  con `MONTAR_ROUTERS_DORMIDOS=1`. Dormant ahora significa que la ruta no
  existe, no que nadie la use todavía. Fijado en
  `backend/tests/test_routers_dormidos.py`.

### OAuth Google/Azure — se queda

- Login con `GOOGLE_CLIENT_ID` / `MICROSOFT_CLIENT_ID`. No expira el client ID;
  lo que rota es el secret o los tokens de sesión (tarea de consola del
  proveedor, no de código).
- **Dato transmitido**: credenciales de OAuth solo cuando el usuario elige ese
  método de login.

### Sentry — eliminado

- Removido el bloque de inicialización y el sanitizador de eventos de
  `backend/api/main.py` (commit de 2026-08-13). `sentry-sdk` no estaba en
  `requirements-desktop.txt`; no hay dependencia que retirar.
- **Motivo**: la telemetría de crash reporting, aunque fuera opt-in y
  sanitizada, contradice la premisa 0-telemetría. Los usuarios reportan
  errores; la app nunca los envía sola.
- Cualquier reintroducción futura requeriría decisión explícita de producto y
  consentimiento visible en la UI.

### Enriquecimiento automático de certificados — eliminado

- `get_pubchem_names()` enviaba el SMILES completo a PubChem cada vez que se
  descargaba un certificado, sin acción ni aviso adicional de la persona.
- Cuando un target no tenía `description`, el router del certificado llamaba a
  RCSB, UniProt y Google Translate para persistir una descripción. Tampoco era
  una acción de red explícita.
- Ambos caminos se retiraron el 2026-08-15. El PDF conserva el nombre asignado
  localmente, métricas, poses y contexto fisiológico derivado de headers PDB
  locales. Docking, rescoring y persistencia no cambian.
- Una futura reintroducción sólo puede ser una acción de UI visible, opt-in y
  documentada en esta tabla; no un efecto colateral de exportar un PDF.

## Matriz de consentimiento UI — auditoría 2026-08-15

| Integración | Evidencia actual | Estado de consentimiento | Acción pendiente |
|---|---|---|---|
| LLM/web | `ChatPanel` ofrece selector **Offline/Web**; `AIContext` inicia `allowWeb=false` y sólo transmite el texto al activar Web. | 🟢 Explícito. | Mantener el copy de qué datos salen y evitar que un override de entorno se convierta en default UI. |
| Solana | `CertificationModal` explica firma institucional (email como autoría) y firma con wallet; los botones de certificación requieren una acción del usuario. Hay otro camino desde evaluación que llama a certificar directamente. | 🟡 Acción explícita, disclosure no uniforme. | Enrutar todos los disparadores al mismo modal/confirmación e indicar payload, red y coste antes de transmitir. |
| RCSB / AlphaFold | Endpoints `POST /targets/resolve-name` y `/targets/alphafold/*` están expuestos; la UI de búsqueda RCSB aún no está cableada. | 🟡 API explícita, sin UX porque no hay caller. | Cuando se conecte la UI, mostrar “consulta externa” y los identificadores que se enviarán. |
| Comunidad | La página consulta el catálogo local; descargar un target puede usar `community_api_url` configurado y requiere clic en Descargar. | 🟡 Acción explícita, destino configurable no mostrado. | Si la URL no es loopback, mostrar dominio y confirmación antes de descargar. |
| OAuth | En Tauri, `login/page.tsx` fuerza login local y `oauthEnabled=false`; `CloudLogin` sólo se renderiza fuera de desktop. | 🟢 Fuera del runtime desktop. | Conservar esta separación y probarla en el smoke de interfaz cuando exista suite E2E. |
| Steam | Router **no montado** por defecto (`MONTAR_ROUTERS_DORMIDOS`); sin él la ruta no existe. Sin credenciales el handler retorna `verified: true`, que es el motivo de no publicarlo. | 🟢 Dormant, y ahora sin superficie HTTP. | Mantener desmontado hasta la decisión de lanzamiento Q4 2026. |

Esta tabla es un inventario de implementación, no autorización para activar
integraciones. Cualquier acción marcada pendiente requiere una decisión de
producto y su prueba de contrato correspondiente.

---

## Qué NO es una integración externa

- **SQLite / dispatcher local / filesystem**: núcleo local, no salen datos.
- **Vina, xTB, OpenMM**: binarios locales.
- **Modelos de rescoring**: artefactos locales (`rescoring/artifacts/`).
- **RCSB descarga puntual**: dependencia científica on-demand, documentada
  arriba.

## Registro de cambios

- 2026-08-13: documento creado (F-13). Decisiones: LLM opt-in, Solana core,
  Steam dormant-Q4, OAuth activo, RCSB esencial, **Sentry eliminado**.
- 2026-08-15: eliminados los enriquecimientos cloud implícitos del certificado
  (PubChem por SMILES y RCSB/UniProt/Google Translate por descripción faltante).
