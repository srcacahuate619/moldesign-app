# MolDesign AI — Roadmap del Launcher

## Problema

La app pesa ~13 GB en total. El installer NSIS con `tauri build` no puede
empaquetar eso de forma confiable (límites prácticos de NSIS + archivos >2 GB).

## Solución

Un solo `.exe` (el mismo Tauri) que funciona como **launcher** en primer inicio
y como **app completa** cuando los modelos ya están descargados. Exactamente
como hace VS Code, Battle.net o Riot Games.

```
1er inicio: LauncherScreen → descarga modelos → "JUGAR"
2do inicio: salta directo a la app (o al launcher si hay updates)
```

## Arquitectura

```
┌─────────────────────────────────────────────────────┐
│ HUGGING FACE (CDN — $0)                             │
│  ├─ v1.0/manifest.json      ← checksums + URLs      │
│  ├─ v1.0/base.pak           ← Python+frontend+tools  │
│  ├─ v1.0/models-llm.pak     ← 3 GGUF (3.73 GB)      │
│  └─ v1.0/models-esmfold.pak ← pytorch_model.bin     │
│     (solo vos subís — usuarios solo bajan)           │
└─────────────────────────────────────────────────────┘
         │ descarga pausable/reanudable
         ▼
┌─────────────────────────────────────────────────────┐
│ MOLDESIGN LAUNCHER (Tauri — un solo .exe)           │
│                                                      │
│  ¿descargado? → NO → LauncherScreen                 │
│                       ├─ DownloadCard (LLM)          │
│                       ├─ DownloadCard (ESMFold)      │
│                       └─ [▶ JUGAR]                   │
│                                                      │
│  ¿descargado? → SÍ → App normal                     │
│                       ├─ /evaluacion → guard ESMFold │
│                       ├─ /batch      → guard LLM     │
│                       └─ /molchat    → guard LLM     │
└─────────────────────────────────────────────────────┘
```

## Fases

> **Estado comprobado en el árbol el 2026-10-20 (auditoría científica, SCI-A-065).** Las
> casillas marcadas existen en el código; la ruta va al lado. Las fases 1 y 6 (Hugging
> Face, `.pak`, CI de publicación) no se pueden comprobar desde el árbol y quedan sin
> marcar; el runtime base sí se publica en Hugging Face (`scripts/deploy-hf.py`), pero no
> con el formato `.pak` de este plan. Los costes son una proyección, no una medida.

### Fase 1 — Pesar la distribución
- [ ] Subir modelos a Hugging Face
- [ ] Crear `manifest.json` (versión, checksums SHA-256, URLs)
- [ ] Modificar `scripts/bundle.py` para excluir modelos pesados
- [ ] Compilar installer liviano (~2.5 GB raw → ~1.8 GB LZMA2)

### Fase 2 — Módulo de descarga nativo (Rust)
- [x] Comando `download_model` con reqwest streaming (`src-tauri/src/downloader.rs`, no `lib.rs`)
- [x] Eventos `download:progress` y `download:complete` (`downloader.rs`)
- [x] Reanudación (cabecera `Range` + archivo `.part`, `downloader.rs`)
- [x] Verificación SHA-256 post-descarga (`verify_sha256`, `downloader.rs`)

### Fase 3 — Estado global de descarga (frontend)
- [x] `DownloadProvider.tsx` — montado en `app/layout.tsx`
- [x] Escaneo del disco vía Tauri — existe como `checkModules()` (`file_exists`, `verify_model`)
- [x] `startDownload()` y `cancelDownload()`; no hay `pauseDownload()`: se cancela y se reanuda desde el `.part`. La verificación va dentro de `checkModules()`

### Fase 4 — UI del Launcher
- [x] `LauncherScreen.tsx` — en `app/launcher/page.tsx`
- [x] `DownloadCard.tsx` — barra de progreso (sin pausa: cancelar y reanudar)
- [ ] `PlayButton.tsx` — no existe con ese nombre
- [ ] `ModelSettings.tsx` — no existe con ese nombre

### Fase 5 — Guards en páginas existentes
- [x] `RequireModel` wrapper — existe (`components/RequireModel.tsx`) y tiene prueba, **pero no lo monta ninguna página**
- [ ] Aplicar a `/evaluacion` (requiere ESMFold) — sin aplicar; ESMFold se enciende al empezar la corrida
- [ ] Aplicar a `/batch` (requiere LLM)
- [ ] Aplicar a `/molchat` (requiere LLM)

### Fase 6 — CI/CD (post-MVP)
- [ ] GitHub Action que corre `tauri build`
- [ ] Empaqueta recursos en .pak
- [ ] Sube a Hugging Face automáticamente
- [ ] Actualiza `manifest.json`

## Costos

| Recurso | Costo |
|---------|-------|
| Hugging Face (CDN, ~11 GB) | $0 |
| VPS para API (post-MVP) | ~$5-10/mes |
| **Total mensual** | **~$5-10** (solo cuando haya server) |

## Próximo paso después del launcher

Backend server con FastAPI + PostgreSQL para:
- Auth (register/login JWT)
- Receptores compartidos (upload PDB + metadata)
- Resultados compartidos
- Telemetría (contar usuarios activos)
