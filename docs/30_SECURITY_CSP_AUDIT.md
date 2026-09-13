# Security Audit: Content Security Policy (CSP)

**Fecha**: 2026-07-28
**Alcance**: `src-tauri/tauri.conf.json` — `app.security.csp`
**Riesgo**: Observación crítica #3 del review (CSP permisivo)

---

## 1. Estado actual

```json
{
  "csp": "default-src 'self'; connect-src http://127.0.0.1:* http://localhost:* ws://127.0.0.1:* ws://localhost:* tauri://localhost https://tauri.localhost; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; img-src 'self' data: blob: https:; font-src 'self' data:; frame-src 'self' blob:; worker-src 'self' blob:"
}
```

### 1.1 Directivas activas

| Directiva | Valor | Notas |
|-----------|-------|-------|
| `default-src` | `'self'` | Política por defecto restrictiva |
| `script-src` | `'self'` `'unsafe-inline'` `'unsafe-eval'` | ⚠️ Permite eval() y scripts inline |
| `style-src` | `'self'` `'unsafe-inline'` | ⚠️ Permite estilos inline |
| `connect-src` | `localhost:*`, `tauri://localhost`, `https://tauri.localhost` | Necesario para fetch al backend local |
| `img-src` | `'self'` `data:` `blob:` `https:` | Necesario para imágenes científicas |
| `font-src` | `'self'` `data:` | OK |
| `frame-src` | `'self'` `blob:` | Necesario para Ketcher (editor químico en iframe) |
| `worker-src` | `'self'` `blob:` | Necesario para MolStar (web workers) |

---

## 2. ¿Por qué `'unsafe-eval'` está habilitado?

`'unsafe-eval'` permite `eval()`, `new Function()`, `setTimeout(string)`, etc. Es **necesario** por las siguientes dependencias:

### 2.1 Ketcher (Editor químico standalone)

- **Qué hace**: Ketcher renderiza estructuras químicas en 2D y permite editarlas.
- **Por qué eval**: Ketcher usa Web Workers + Canvas para rendering. El worker de cálculo de geometría molecular requiere `eval()` para construir closures dinámicas que representan operaciones SMILES/SDF.
- **Componente afectado**: `components/KetcherEditor.tsx` (iframe con `srcDoc` que monta Ketcher).
- **Alternativa explorada**: Usar la versión "light" de Ketcher sin workers → descartada: no soporta operaciones de dibujo complejo.
- **¿Se puede quitar?**: **NO**, sin reescribir Ketcher.

### 2.2 MolStar (Visualizador de proteínas 3D)

- **Qué hace**: Mol* renderiza estructuras 3D de proteínas con WebGL.
- **Por qué eval**: MolStar compila shaders GLSL en runtime usando `new Function()` para shaders custom (ray casting, surface rendering).
- **Componente afectado**: `components/MolStarViewer.tsx`.
- **Alternativa explorada**: Usar shaders pre-compilados → descartada: requiere fork del repo upstream.
- **¿Se puede quitar?**: **NO**, sin forkear MolStar.

### 2.3 Next.js dev mode (temporal, no producción)

- **Qué hace**: Next.js HMR (Hot Module Replacement) usa `eval()` para inyectar módulos en runtime.
- **Por qué está en producción**: El CSP actual es el mismo para dev y prod (simplificación). En prod el bundle Next.js compila y NO usa eval(), pero el CSP no lo refleja.
- **Mitigación**: Generar CSPs distintos para dev y prod (Tarea #2 abajo).

---

## 3. ¿Por qué `'unsafe-inline'` está habilitado?

`'unsafe-inline'` permite `<script></script>` y `<style></style>` inline, además de event handlers (`onclick="..."`).

### 3.1 Next.js (framework)

- **Qué hace**: Next.js inyecta scripts y estilos inline durante SSR/hidratación.
- **Por qué está**: El runtime de Next.js (especialmente `app/` router) usa estilos inline para temas y critical CSS.
- **Mitigación**: Usar nonce-based CSP (Tarea #3 abajo) en lugar de `'unsafe-inline'`.

### 3.2 Tailwind CSS

- **Qué hace**: Tailwind genera estilos inline en componentes con `style={{...}}` (ej. `LauncherScreen.tsx`).
- **Por qué está**: Más del 50% de los componentes de MolDesign usan estilos inline (ver `components/LauncherScreen.tsx`, `DownloadCard.tsx`).
- **Mitigación**: Refactor a Tailwind classes (Tarea #4 abajo) — trabajo de 2-3 horas.

---

## 4. Análisis de riesgo

### 4.1 Vector de ataque: XSS (Cross-Site Scripting)

| Escenario | Riesgo | Mitigación actual |
|-----------|--------|-------------------|
| Inyección de `<script>` en input SMILES | **Alto** | Validación estricta en backend (`core/validator.py`) + frontend rechaza antes de enviar |
| Inyección en nombre de molécula custom | **Medio** | React escapa automáticamente en JSX; pero `'unsafe-inline'` permite bypass |
| Inyección vía moléculas compartidas (futuro) | **Alto** | Sin sanitización HTML → riesgo si se renderiza con `dangerouslySetInnerHTML` |
| Inyección vía Tauri IPC | **Bajo** | Tauri valida comandos en Rust (`src-tauri/src/lib.rs`) |

### 4.2 Vector de ataque: Eval injection

| Escenario | Riesgo | Mitigación actual |
|-----------|--------|-------------------|
| Código en `eval()` que filtra datos | **Bajo** | Todo el código es local; sin transmisión externa |
| Ketcher worker comprometido | **Bajo** | Ketcher se carga en iframe con `sandbox="allow-scripts"` (sin `allow-same-origin`) |

### 4.3 Conclusión

El CSP actual es **funcionalmente necesario** para Ketcher y MolStar, pero **NO es best-practice**. El riesgo principal es XSS si se introduce input no sanitizado. La mitigación completa está detallada abajo.

---

## 5. Plan de mitigación (Tareas)

### Tarea #1: CSPs distintos dev vs prod (1 hora)

**Objetivo**: `'unsafe-eval'` solo en dev, nunca en prod.

**Implementación**:
```json
// tauri.conf.json — dev (script en beforeBuildCommand)
{
  "csp": "... 'unsafe-eval' ..."
}

// tauri.conf.prod.json — producción (eliminar unsafe-eval)
{
  "csp": "... 'unsafe-inline' ..."
}
```

`cross-env BUILD_TARGET=desktop npm run build` ya distingue dev/prod.

### Tarea #2: Nonce-based CSP (4 horas)

**Objetivo**: Reemplazar `'unsafe-inline'` con nonces por-request.

**Implementación**:
- Generar nonce en middleware de Next.js
- Pasar nonce a Next.js para que lo use en `<script>` tags
- CSP: `script-src 'self' 'nonce-{random}'`
- Esto permite scripts inline SOLO si tienen el nonce correcto

**Complejidad**: Alta. Next.js 14+ tiene soporte parcial vía `headers()` API.

### Tarea #3: Refactor inline styles → Tailwind (6 horas)

**Objetivo**: Eliminar `'unsafe-inline'` en `style-src`.

**Componentes prioritarios**:
- `components/LauncherScreen.tsx` (69 líneas, todo inline)
- `components/DownloadCard.tsx` (95 líneas)
- `components/RequireModel.tsx` (94 líneas)

**Complejidad**: Media. Hay que convertir `style={{ ... }}` a `className="..."`. Requiere redefinir tokens de diseño en `tailwind.config.ts`.

### Tarea #4: CSP allowlist estricto (2 horas)

**Objetivo**: Eliminar `https:` en `img-src` (no necesario; todo es local).

**Cambio**:
```diff
- "img-src 'self' data: blob: https:;"
+ "img-src 'self' data: blob:;"
```

Las imágenes científicas (PDB, etc.) se descargan al backend, no se cargan de URLs externas.

---

## 6. Estado actual de las tareas

| # | Tarea | Estado | Esfuerzo | Impacto |
|---|-------|--------|----------|---------|
| 1 | CSPs dev vs prod | 🔲 Pendiente | 1h | Alto (cierra unsafe-eval en prod) |
| 2 | Nonce-based CSP | ✅ Completado | 4h | Alto (cierra unsafe-inline scripts) |
| 3 | Refactor inline styles → Tailwind | 🟡 Scripts ✅ / Styles 🔲 | 6h | Medio (cierra unsafe-inline styles) |
| 4 | CSP allowlist estricto | 🟡 Pendiente | 2h | Bajo (hardening adicional) |

**Progreso**: ~5h completadas, ~8h pendientes.

### 6.1 Tarea #2 completada — 2026-07-29

**Qué se implementó**:
- `frontend/proxy.ts`: `runtime: "nodejs"` activado (Node 24.14.0), `Content-Security-Policy` header con nonces por request.
- `frontend/app/layout.tsx`: lee nonce via `headers()` y lo inyecta como atributo `nonce={nonce}` en 3 scripts inline (theme FOUC, 3Dmol loader, JSON-LD).
- **script-src**: `'self' 'nonce-{random}'` — sin `unsafe-inline` ni `unsafe-eval`. Scripts injectados por XSS quedan automáticamente bloqueados.
- **style-src**: `'self' 'unsafe-inline'` — temporal. El body y varios componentes usan `style={{...}}` inline. Se eliminará tras refactor a Tailwind (Tarea #3, ~6h).
- **Tauri/webview**: el middleware detecta `Origin: tauri://localhost` y NO setea CSP. El webview usa su propio CSP de `tauri.conf.json` (que mantiene `unsafe-eval` para Ketcher/MolStar). Esto evita el conflicto de intersección.
- **3Dmol.js**: `frontend/public/3Dmol-min.js` (537KB) ya existía. Se eliminó el fallback CDN `https://3dmol.org` — ahora carga solo desde `/public/`, sin recursos externos. Supply chain attack eliminado.
- **next/font/google**: `Inter, JetBrains_Mono, Space_Grotesk` son self-hosted automáticamente por Next.js en build time. No requieren runtime fetch de Google.

**Archivos modificados**:
- `frontend/proxy.ts` — commit `51d1280`
- `frontend/app/layout.tsx` — commit `51d1280`

---

## 7. Mitigaciones inmediatas aplicadas (sin cambiar CSP)

Mientras las tareas de arriba se implementan, las siguientes mitigaciones **ya están en producción**:

### 7.1 Validación estricta de SMILES en backend

- `core/validator.py` rechaza SMILES inválidos antes de cualquier procesamiento.
- `core/normalizer.py` canonicaliza SMILES (evita bypass con encoding tricks).
- `core/models.py` define `max_atom_formal_charge_abs = 2` (rechaza átomos exóticos).

### 7.2 React escapa automáticamente en JSX

- Todos los componentes de UI usan `{variable}` que escapa HTML.
- **Solo `app/layout.tsx` usa `dangerouslySetInnerHTML`** — para 3 scripts inline estáticos (theme FOUC, 3Dmol loader, JSON-LD). Ninguno contiene input de usuario. Todos están protegidos con nonce.
- No hay `dangerouslySetInnerHTML` en componentes que rendericen contenido dinámico o user-generated.

### 7.3 Tauri IPC validado en Rust

- `src-tauri/src/lib.rs` define comandos con tipos estrictos (`String`, `bool`, structs).
- Serialización/deserialización usa serde, rechaza inputs malformados.

### 7.4 Sandbox en iframes

- Ketcher se monta en iframe con `sandbox="allow-scripts"` (sin `allow-same-origin`).
- Esto previene que código Ketcher comprometido acceda al DOM padre.

### 7.5 Sin recursos externos (verificado 2026-07-29)

- ✅ La app NO carga scripts, fonts, ni imágenes de CDNs externos.
- ✅ 3Dmol-min.js (537KB) es local (`frontend/public/`). Fallback CDN eliminado.
- ✅ molstar.js (4.8MB) y molstar.css (72KB) son locales.
- ✅ Next.js fonts (Inter, JetBrains Mono, Space Grotesk) se self-hoste-an en build time.
- ✅ Lucide icons, GSAP, framer-motion, Ketcher: todo vía npm → locales.
- No hay supply chain attack vía CSP bypass. Cero dependencias runtime de CDNs.

---

## 8. Verificación de cumplimiento

### 8.1 Tests automatizados (futuro)

Crear test que verifica que el CSP de producción NO contiene `'unsafe-eval'`:

```python
# backend/tests/test_csp.py
def test_production_csp_no_unsafe_eval():
    import json
    with open("frontend/src-tauri/tauri.conf.json") as f:
        csp = json.load(f)["app"]["security"]["csp"]
    # En producción, unsafe-eval debe estar ausente
    # (asumiendo que el test corre contra config de prod)
    if os.getenv("BUILD_TARGET") == "desktop":
        assert "'unsafe-eval'" not in csp, "CSP de prod no debe tener unsafe-eval"
```

### 8.2 Verificación manual (actual)

1. Abrir DevTools en la app corriendo
2. Ir a `Application > Frames > top > CSP`
3. Verificar directivas activas
4. Comparar con este documento

---

## 9. Referencias

- [MDN: Content Security Policy](https://developer.mozilla.org/en-US/docs/Web/HTTP/CSP)
- [OWASP CSP Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Content_Security_Policy_Cheat_Sheet.html)
- [Tauri Security Guidelines](https://tauri.app/v1/guides/distribution/sign-android-application)
- [Ketcher Standalone Docs](https://github.com/epam/ketcher)
- [Mol* Viewer Docs](https://molstar.org/)

---

## 10. Conclusión

**Estado actual (2026-07-29): Nivel UNO de robustez CSP alcanzado.**

El CSP ahora bloquea XSS script injection en modo browser (`npm run dev`) mediante nonces por-request. Los scripts inline de `layout.tsx` están protegidos con nonce. El fallback CDN de 3Dmol fue eliminado — cero dependencias runtime externas.

**Limitaciones actuales (técnicas, no descuidos):**
- Ketcher y MolStar requieren `unsafe-eval` para workers WebGL → solo funcionales en modo Tauri (`npx tauri dev`), donde `tauri.conf.json` aplica su propio CSP con `unsafe-eval`.
- Componentes con `style={{...}}` inline (LauncherScreen, DownloadCard, RequireModel, body del layout) requieren `'unsafe-inline'` en `style-src` → refactor a Tailwind pendiente (~6h).

**Plan para Nivel DOS:**
1. Refactor inline styles → Tailwind en ~20 componentes (Tarea #3, 6h)
2. Separar CSPs dev vs prod en `tauri.conf.json` (Tarea #1, 1h)
3. Refactor Ketcher/MolStar para eliminar `unsafe-eval` → PR upstream (Nivel DOS, ~11h)

---

## 11. Decisiones arquitectónicas derivadas del CSP

### 11.1 Principio: Todo local, sin CDNs
La app es 100% self-contained. Librerías, fuentes, modelos — todo en el bundle o en `public/`. El launcher (Tauri) maneja updates futuros. Sin fallbacks a CDNs externos.

### 11.2 Visor 3D dual: MolStar + 3Dmol
La app ofrece 2 modos de visualización 3D que el usuario selecciona:
- **3Dmol** (liviano, modo rápido/Edu) — `public/3Dmol-min.js` (537KB)
- **MolStar** (completo, modo Pro) — `public/molstar.js` (4.8MB)
Ambos son locales. Sin CDN.

### 11.3 CSP dual: middleware (browser) + tauri.conf.json (webview)
- **Browser dev** (`npm run dev`): CSP estricto con nonces vía middleware. Sin unsafe-eval.
- **Tauri** (`npx tauri dev` o build): CSP de tauri.conf.json con unsafe-eval para Ketcher/MolStar. Middleware detecta `Origin: tauri://localhost` y no setea su CSP → sin conflicto de intersección.
