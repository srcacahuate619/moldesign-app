> **Documento histórico — julio de 2026.** Escrito para el árbol anterior del
> proyecto (`moldesign-app`) y traído aquí por trazabilidad. Puede describir un
> estado que ya no es el vigente: la versión 1.0.0 es una aplicación de
> escritorio y no tiene componente en la nube. No se ha reescrito su contenido.

# ADR 0001: Patrón de Modo Dual (CLOUD / DESKTOP)

- **Fecha**: 2026-07-01
- **Estado**: Aceptado
- **Decisión**: Johan Amezcua (Tech Lead)

## Contexto

MolDesign AI necesita ejecutarse en dos entornos fundamentalmente distintos:

1. **Cloud (SaaS)**: PostgreSQL, Redis, Celery, MinIO — escalable, multi-tenant
2. **Desktop (local)**: SQLite, LRU in-memory, ThreadPoolExecutor, disco local — offline, single-user

Mantener dos codebases separadas duplica el mantenimiento y el riesgo de divergencia. Necesitamos un único código fuente que se adapte al entorno en runtime.

## Decisión

Usar una variable de entorno `APP_MODE` (`CLOUD` | `DESKTOP`) que activa implementaciones concretas via Strategy Pattern.

```
APP_MODE=CLOUD
├── DB: PostgreSQL via asyncpg
├── Cache: Redis
├── Queue: Celery + Redis broker
├── Storage: MinIO (S3-compatible)
└── Auth: JWT + OAuth (cloud)

APP_MODE=DESKTOP
├── DB: SQLite via aiosqlite
├── Cache: dict LRU in-memory (10K items)
├── Queue: ThreadPoolExecutor (2-6 workers)
├── Storage: ~/MolDesign/data/ (local disk)
└── Auth: JWT + auto-login
```

### Implementación

1. **`core/config.py`**: `Settings` de Pydantic lee `APP_MODE` y expone settings condicionales
2. **`core/db_factory.py`**: Fábrica que retorna engine PostgreSQL o SQLite según el modo
3. **`core/storage.py`**: Interfaz unificada con implementaciones MinIO y local-disk
4. **`services/docking/queue_handler.py`**: Abstractión sobre Celery y ThreadPoolExecutor
5. **`utils/cache.py`**: Misma interfaz, backend Redis o dict LRU
6. **`api/routers/auth.py`**: Desktop auto-login, cloud requiere autenticación

### Frontend

El frontend usa **build dual**: SSR para cloud, static export para desktop (Tauri). La URL de API se configura dinámicamente:

```typescript
// frontend/lib/config.ts
const API_URL = typeof window !== 'undefined' && window.__TAURI__
  ? 'http://localhost:8000'
  : process.env.NEXT_PUBLIC_API_URL
```

## Consecuencias

### Positivas

- **Single codebase**: Todo el backend es el mismo, solo cambia la configuración
- **Testing unificado**: Los tests corren en modo DESKTOP con SQLite en memoria
- **Despliegue simple**: Cloud corre con `APP_MODE=CLOUD`, desktop usa default `DESKTOP`
- **Onboarding rápido**: Un desarrollador puede correr todo local sin infraestructura cloud

### Negativas

- **Complejidad en factories**: Cada recurso externo necesita una fábrica o strategy
- **Testing de ambos modos**: Tests específicos de cloud requieren PostgreSQL/Redis reales
- **Feature parity**: No todas las features de cloud están disponibles en desktop (Celery beat, webhooks)

### Mitigaciones

- Las factories siguen el patrón Lazy Singleton: el recurso se crea al primer uso, no al importar
- Los tests de integración cloud llevan marker `@pytest.mark.slow`
- El frontend oculta opciones cloud-only (OAuth, Celery dashboard) en modo desktop

## Opciones Consideradas

| Opción | Pros | Contras |
|--------|------|---------|
| **APP_MODE env var** (elegida) | Single codebase, test uniforme | Factories adicionales |
| Repos separados | Independencia total | 2x mantenimiento, divergencia asegurada |
| Monorepo con symlinks | Código compartido | Complejidad de build, Windows issues con symlinks |
| Feature flags externos (LaunchDarkly) | Control granular | Dependencia externa, latencia, costo |

## Referencias

- [docs/02_DESKTOP.md](../02_DESKTOP.md) — Adaptación cloud → desktop
- [docs/04_ARCHITECTURE.md](../04_ARCHITECTURE.md) — Organización del código
- [backend/core/config.py](../../backend/core/config.py) — Implementación de Settings
- [backend/core/database.py](../../backend/core/database.py) — Motor y sesiones de SQLite (la antigua `db_factory.py` se fusionó aquí)
