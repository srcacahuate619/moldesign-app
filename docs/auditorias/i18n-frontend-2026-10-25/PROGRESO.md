# Progreso — entrega de Fase C para revisión

**Fases A y B aceptadas; correcciones previas a C hechas; Fase C implementada y verificada.** Pendiente revisión del propietario antes de integrar. Rama aislada: sol/i18n-frontend; base 4fc7a9281fecb209a94784d15983475d64b517e8. Commit de implementación C: 09eae11a.

## Fase A

Se sustituyó f4a60be7 por bd3788f5. Los 317 archivos pesados están archivados en F:/Backups/moldesign-evidencia/2026-10-25-i18n-fase-a/; el manifiesto SHA-256 es 9440755aecb5e052208160dc6e08eff91736d1e6033fb935d5c79af98482b2f1, citado en ARCHIVO_EVIDENCIA.md. El informe, inventario, glosario, herramientas y evidencia ligera permanecen en el repositorio. auditar-i18n-fase-a.cjs está en herramientas/.

## Fase B y correcciones aceptadas

B corrigió el diccionario inglés, comparaciones por prosa y presentación por valores estructurados sin alterar formatos persistidos. Antes de C:
- 8988a55b restaura LF en 30 archivos afectados por CRLF, en commit propio y sin cambio semántico.
- 111b28bf reabre I18N-115/116 junto a I18N-113: calibrationTooltip() aún afirma que la caja está calibrada; lo decide el propietario.
- 38c6c272 quita la exclusión general de <code>/<pre>; el filtro decide por contenido y planta prosa castellana en <pre> como control positivo.

## Fase C

Los guardianes estático y de export están implementados. El barrido incluye lib/, hooks/ y context/ TS/TSX; Playwright inspecciona texto, title, aria-label y placeholder en el export desktop con CSP de producción. El recorrido automatizado cubre 48 estados con fixtures locales y planta castellano en los cuatro canales. Revertir el CTA de controles fallidos hace fallar los guardianes estático y de export; ambos pasan al restaurarlo.

El inventario final contiene 403 entradas: 248 cerradas y 155 pendientes con motivo. 48 son exclusiones previas y 107 entradas diagnósticas estáticas nuevas aún no reproducidas en pantalla. Por eso npm run check:i18n mantiene salida 1 con 112 diagnósticos. Las dos fugas demostradas por el export y cerradas en C son I18N-402 (nombre de Molcy en Licencias) e I18N-403 (botón de controles fallidos).

Los reportes DOM y capturas de C están archivados en F:/Backups/moldesign-evidencia/2026-10-26-i18n-fase-c/ con manifiesto SHA-256 copiado a evidencia/manifiesto-fase-c-sha256.json. El detalle está en INFORME_FASE_C.md e INFORME_FINAL.md. smoke:prod y las capturas del tutorial de Molcy corresponden al propietario al integrar. No se hizo push ni merge.
