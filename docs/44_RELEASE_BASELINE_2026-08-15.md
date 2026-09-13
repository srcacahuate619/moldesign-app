# 44 — Release Baseline Desktop

**Fecha:** 2026-08-15  
**Estado:** Baseline recuperable de infraestructura local  
**Derivado de:** `docs/43_PLAN_ACCION_MADUREZ.md`, A-00

---

## Alcance

Este documento captura el estado de referencia antes de ejecutar correcciones
de Código/Calidad. No modifica configuraciones de usuario, receptores, modelos
ni base de datos productiva.

El baseline valida la infraestructura desktop aislada. **No es una validación
científica E2E:** el smoke reemplaza docking y scoring por un stub determinista
para probar el ciclo de job, persistencia y storage sin ejecutar Vina/MM-GBSA.

## Identidad del árbol auditado

| Campo | Valor |
|---|---|
| Commit base | `44d26c25e59e16f22f7c00b1a714d59104d0fe48` |
| Commit fecha | 2026-08-14T01:44:38-06:00 |
| Mensaje | `feat(science): resultados Fase B y MolFlex - artefactos experimentales consolidados` |
| Estado de trabajo | **Sucio y preservado**: contiene cambios de producto, ciencia, documentación y artefactos no committeados. |
| Runtime Python embebido | 3.11.9 |
| Node / npm | v24.14.0 / 11.9.0 |
| Rust / Cargo | 1.95.0 |
| Catálogo fuente | 387 targets (`curated_targets.json`) |

## Artefactos de referencia

| Artefacto | SHA-256 |
|---|---|
| `backend/requirements-desktop.lock.txt` | `d34fe5c0be972fb3b5f35578b60d0b6f9962a580812f5504ea54344cd99f57d6` |
| `frontend/package-lock.json` | `9d2a856380a91aaaa14743cba9230334ca4f4637bf9094362a32b8fa3f21bc63` |
| `curated_targets.json` | `ba8654ebce79c35ee77d5c0589155fbf569df48f3349b9e965ea2ce491c7c2` |
| `rescoring/artifacts/model-manifest.json` | `8c25f974ca3ba6c0a978bc16d1ab41906da100e57d4f16e5c76da5d348549f0` |

### Modelos declarados

| Modelo | Archivo | SHA-256 | Estado |
|---|---|---|---|
| Fase A universal | `model_a_universal.json` | `d2041777857586065aa29dcc8b876a9c1e89394dacbf517e9c071e5cba27f0b2` | Producción, holdout honesto histórico. |
| Ruta C v0.6 | `pose_selector_v06.xgb` | `9827ddb94c5ded5b2ef1dda1250606d73f73163becc310641d5bd493196e5d31` | Experimental integrado; no sustituye el score de afinidad. |

El `model-manifest.json` está en schema v4 y declara ambos modelos.

## Comprobaciones realizadas

| Comprobación | Resultado | Evidencia clave |
|---|---|---|
| Desktop smoke aislado | **PASS** | `submit → polling → SQLite → filesystem`; estado `SUCCESS`, 1 molécula, 1 resultado y poses legibles. |
| Contrato smoke | **PASS** | Aspirina `CC(=O)Oc1ccccc1C(=O)O`, score stub 88.0, target persistido `6X1A`. |
| Gate Vina / Fase A | **PASS** | Share de importancia Vina: 0.02837 < 0.10. |
| CSP de producción | **PASS con excepción** | No contiene `unsafe-eval`; contiene `unsafe-inline` documentado. |
| `cargo check` Tauri | **PASS con warning** | Launcher compila; warning por asignación inicial no leída de `last_error`. |

## Contratos golden protegidos desde ahora

Antes de cambiar Código, cada modificación que alcance pipeline debe conservar:

1. El submit local produce un task id y un estado terminal consultable.
2. SQLite conserva molécula, resultado y metadata tras una nueva conexión.
3. Poses se guardan y se leen por la ruta lógica
   `poses/{smiles_hash}/{target}/poses.sdf`.
4. El backend desktop puede trabajar sin Redis, Celery, MinIO ni PostgreSQL.
5. El manifest v4 mantiene todos sus modelos declarados y sus hashes.
6. La app Tauri acepta únicamente un backend que responda health semántico.

## Lo que este baseline no certifica

- Calidad de docking real, redocking, pose selection ni MM-GBSA.
- Una instalación limpia o el instalador NSIS.
- Integraciones opcionales: RCSB, blockchain, proveedores LLM o comunidad.
- Rendimiento bajo batch/carga.
- Las tres suites del repositorio; se encuentran rojas y constituyen la
  siguiente campaña de trabajo.

## Próxima puerta

**C-01 — reparar el build frontend.** Ningún refactor de pipeline ni purga
cloud debe comenzar hasta que `npm run build` sea verde sobre un árbol de
dependencias reproducible.
