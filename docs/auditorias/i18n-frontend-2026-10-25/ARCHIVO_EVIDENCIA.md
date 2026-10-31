# Archivo externo de la evidencia de Fase A

La Fase A fue aceptada por el propietario. El commit original f4a60be7204f4af7417b053d60d5f8f396f30654 se rehízo antes de B para retirar la evidencia pesada. Se copiaron y verificaron los 317 archivos originales, sin sobrescribir sus bytes.

Manifiesto: `F:/Backups/moldesign-evidencia/2026-10-25-i18n-fase-a/MANIFIESTO_SHA256.json`, en el disco del propietario.

SHA-256 del manifiesto: `9440755aecb5e052208160dc6e08eff91736d1e6033fb935d5c79af98482b2f1`. Una copia del manifiesto permanece en evidencia/manifiesto-archivo-sha256.json. El directorio externo conserva las rutas originales bajo repo/.

En el repositorio quedan el informe, inventario, glosario, herramientas y evidencia ligera agregada inferior a 1 MB. Los PNG, red.json, triage-a1.json y los barridos/volcados voluminosos están en el archivo externo. Las referencias del inventario apuntan allí.

Verificación: `node docs/auditorias/i18n-frontend-2026-10-25/herramientas/archivo-fase-a.cjs`. La variable MOLDESIGN_I18N_EVIDENCE_ROOT permite leer una copia reubicada que conserve el mismo manifiesto y SHA-256. No se escribe en el archivo al consultar ni recompilar.
