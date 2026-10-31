# Herramientas de Fase A archivada

La copia auditar-i18n-fase-a.cjs se movió aquí por decisión del propietario. Conserva sus 23 controles y no es todavía el guardián de C.

Desde la raíz del worktree:

```
node docs/auditorias/i18n-frontend-2026-10-25/herramientas/auditar-i18n-fase-a.cjs --autotest
node docs/auditorias/i18n-frontend-2026-10-25/herramientas/archivo-fase-a.cjs
node docs/auditorias/i18n-frontend-2026-10-25/herramientas/revisar-a1.cjs --summary
```

archivo-fase-a resuelve y verifica la evidencia externa mediante el manifiesto citado en ARCHIVO_EVIDENCIA.md. Las herramientas de compilación son históricas: sólo sirven para la base de producto 4fc7a928; no regenerar el inventario operativo después de modificar producto en B. La compilación ya no escribe los tres JSON voluminosos en el repositorio. El barrido puede enviar nuevos candidatos a stdout o a una ruta externa explícita; --write del triage exige --salida-dir fuera del repositorio.

El helper de captura recibe una página Playwright real, espera el estado elegido por el llamador y conserva DOM y PNG sin modificar CSS. RECORRIDO.md documenta las acciones. red.json externo mantiene indices_originales y se puede reconstruir con el hash original declarado en red-deduplicacion.json.
