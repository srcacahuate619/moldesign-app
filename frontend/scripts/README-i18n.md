# Guardianes i18n

Ejecutar desde frontend/.

- npm run test:i18n:export construye el export de escritorio y recorre out/ con Playwright, CSP de producción y fixtures locales. No ejecuta Vina, Blender, modelos ni servicios externos.
- npm run check:i18n es la comprobación estricta. Sale con 1 mientras haya diagnósticos pendientes, candidatos sin revisar, texto JSX pendiente o revisiones obsoletas. El 2026-10-26 se resolvieron los 112 diagnósticos de la fase C: 108 entradas sustituidas por mensajes localizables y cuatro revisadas por su uso real. Dos son una etiqueta persistida que se traduce al presentar; los otros dos son errores capturados que no llegan a la interfaz. El recorrido dinámico sigue siendo necesario.
- node scripts/finish-i18n-frontend.cjs --autotest demuestra que el barrido ve los controles positivos y distingue comentarios y consola.
- --json conserva el formato del trinquete: regresiones sin revisar. Una lista vacía NO significa que no haya deuda.
- --source-json enumera todos los candidatos TS, y --report-json incluye las revisiones y los pendientes.
- node scripts/probar-regresion-i18n.mjs revierte temporalmente el CTA de controles fallidos a 4fc7a928, exige que fallen el trinquete y el export, restaura ProAnalysisTabs.tsx y reconstruye/verifica el export limpio. --connection aplica la misma prueba al descriptor ERROR_DE_CONEXION de History. Rechaza ejecutarse si el archivo elegido tiene cambios ajenos.

El barrido TS cubre lib/, hooks/ y context/, tanto .ts como .tsx, excluyendo pruebas y traducciones. Reconoce retornos, propiedades de presentación, errores y constantes escalares usadas en una salida del mismo módulo. No es análisis completo de flujo entre módulos. Las revisiones exactas de i18n-source-review.json llevan archivo, función y texto: una frase distinta o una función nueva requiere revisión. Los diagnósticos pendientes siguen fallando en el modo estricto; su presencia en el inventario no los autoriza.

El guardián DOM mira texto renderizado y todos los atributos title, aria-label y placeholder, incluidos controles fuera del viewport. Las exclusiones tienen nombre: términos técnicos completos, selector Español, códigos de aviso, los tres tooltips pendientes del propietario y valores exactos de los campos originales del Registro. Nunca excluye una región completa de la pantalla. Los atajos de teclado se retiran de la muestra léxica sin ocultar el resto de la frase.

Los controles positivos plantan texto castellano en los cuatro canales, incluido un pre. Las pruebas del barrido también plantan archivos TS reales en lib, hooks y context, y los borran en finally. No se excluyen code/pre por etiqueta.

El recorrido automatizado no prueba estados con resultados científicos nuevos, diálogos nativos ni los píxeles del tutorial. smoke:prod y la regeneración de las capturas del tutorial corresponden al propietario al integrar.
