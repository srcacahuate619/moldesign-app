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

### Fase 1 — Pesar la distribución
- [ ] Subir modelos a Hugging Face
- [ ] Crear `manifest.json` (versión, checksums SHA-256, URLs)
- [ ] Modificar `scripts/bundle.py` para excluir modelos pesados
- [ ] Compilar installer liviano (~2.5 GB raw → ~1.8 GB LZMA2)

### Fase 2 — Módulo de descarga nativo (Rust)
- [ ] Comando `download_model` en `lib.rs` con reqwest streaming
- [ ] Eventos `download:progress` y `download:complete`
- [ ] Reanudación automática (Range headers + .part files)
- [ ] Verificación SHA-256 post-descarga

### Fase 3 — Estado global de descarga (frontend)
- [ ] `DownloadProvider.tsx` — estado `missing|downloading|ready`
- [ ] `checkModels()` — escanea FS vía Tauri API
- [ ] `startDownload()` / `pauseDownload()` / `verifyModels()`

### Fase 4 — UI del Launcher
- [ ] `LauncherScreen.tsx` — layout principal tipo Riot
- [ ] `DownloadCard.tsx` — barra de progreso + velocidad + pausa
- [ ] `PlayButton.tsx` — habilitado solo al 100%
- [ ] `ModelSettings.tsx` — panel de gestión en Settings

### Fase 5 — Guards en páginas existentes
- [ ] `RequireModel` wrapper — muestra blocker si falta el modelo
- [ ] Aplicar a `/evaluacion` (requiere ESMFold)
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
