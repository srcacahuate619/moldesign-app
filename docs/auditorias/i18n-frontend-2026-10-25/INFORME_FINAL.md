# Informe final — auditoría i18n del frontend

Fases A y B aceptadas; Fase C completada en sol/i18n-frontend (09eae11a), pendiente de revisión e integración. Base: 4fc7a9281fecb209a94784d15983475d64b517e8.

## Conteo final

El inventario tiene 403 registros: 248 cerrados y 155 pendientes. Incluye fugas reproducidas, productores externos y candidatos estáticos; los diagnósticos nuevos no se presentan como fugas dinámicas confirmadas.

| Origen | Total | Cerrado | Pendiente |
|---|---:|---:|---:|
| frontend TSX | 157 | 153 | 4 |
| frontend lib | 198 | 89 | 109 |
| formato | 6 | 6 | 0 |
| backend | 39 | 0 | 39 |
| Rust | 3 | 0 | 3 |

Por superficie: Casos 151 (47/104), Evaluación 131 (96/35), MolChat 52 (48/4), Inicio/global 14 (14/0), Acceso 6 (6/0), Batch 6 (5/1), Preparación/Casos 6 (6/0), Opciones 8 (6/2), resto 29 (20/9). Las cifras entre paréntesis son cerrados/pendientes.

## Pendientes

- I18N-113, 115 y 116: tooltips cuya afirmación sobre la caja calibrada decide el propietario.
- I18N-249–250: documentos legales de public/, excluidos expresamente.
- I18N-252–254: productor Rust, fuera del alcance.
- I18N-255–293: mensajes backend sin código estable.
- I18N-294: QuickVina Coming soon en Lotes, decisión de disponibilidad.
- I18N-295–401: 112 candidatos estáticos en 107 registros que requieren reproducción y revisión; ninguno se aprobó como excepción silenciosa.

## Guardianes y causa de los escapes

El trinquete anterior miraba TSX en app/, components/ y hooks/, sin inspeccionar el export real ni atributos accesibles. C amplía el análisis local a TS/TSX de lib/, hooks/ y context/. Playwright revisa DOM y title/aria-label/placeholder bajo CSP de producción en 48 estados.

npm run check:i18n es estricto: reporta 0 JSX, 0 sin revisión, 112 diagnósticos pendientes y 0 revisiones obsoletas; sale con 1 mientras exista esa deuda. finish-i18n-frontend.cjs --autotest y el autotest DOM tienen controles positivos y negativos. npm run test:i18n:export prueba English persistente y cuatro canales. probar-regresion-i18n.mjs revierte un arreglo real y demuestra el fallo de ambos guardianes; luego reconstruye y verifica el export limpio.

El recorrido confirmó y cerró I18N-402 (nombre Motor Molcy en Licencias) e I18N-403 (CTA interpolado de controles fallidos). También sustituyó en History la comparación con prosa castellana por el descriptor FrontendError. No se alteraron formatos persistidos.

El detalle está en INFORME_FASE_C.md. Los textos backend/Rust para un siguiente encargo están en inventario.json por productor/campo. El manifiesto SHA-256 de Fase A se cita en ARCHIVO_EVIDENCIA.md: 9440755aecb5e052208160dc6e08eff91736d1e6033fb935d5c79af98482b2f1. Los reportes DOM y capturas de C están archivados en F:/Backups/moldesign-evidencia/2026-10-26-i18n-fase-c/; su manifiesto, evidencia/manifiesto-fase-c-sha256.json, tiene SHA-256 c9300fefa31f69cd623ecc22fb0f51ad31094b6a0ada14dc39bff05da3761b76.

Verificación: suite 260/2325, typecheck, lint (0 errores, 30 avisos), E2E 13/13, UX 12/12 y guardián de export 48 estados pasan. El modo estricto termina con 1 por los 112 diagnósticos pendientes declarados.

smoke:prod y la regeneración de capturas del tutorial corresponden al propietario al integrar. No se hizo push ni merge.
