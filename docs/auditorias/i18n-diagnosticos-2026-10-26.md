# Internacionalización: 112 diagnósticos pendientes

El control estricto de frontend registraba 112 entradas `pendiente` tras la
revisión de 1.0.4. Eran candidatos estáticos de diagnóstico, no 112 pantallas
reproducidas. Este trabajo los revisa sin declarar traducidos los mensajes de
Rust, del backend o del usuario que llegan como texto externo.

- **108 entradas sustituidas:** los diagnósticos locales del esquema de casos,
  los repositorios y otros flujos usan mensajes estructurados con versiones en
  español e inglés. Se conservan los campos, valores y códigos de error.
  `CaseError.message` y `detail` mantienen su representación española para
  consumidores anteriores; la interfaz traduce al presentar los mensajes y
  detalles etiquetados. Los casos no disponibles conservan el error estructurado
  durante la sesión. Las pruebas comparan también las claves y variables de
  ambos idiomas para que una traducción no pierda datos.
- **Dos entradas de etiqueta de almacenamiento:** «Guardado en este
  navegador» es un valor de contrato guardado en el caso. Se conserva en el
  almacenamiento y `localizeCaseStorageLabel` lo traduce al mostrarlo.
- **Dos diagnósticos internos:** los errores de adopción no soportada y módulo
  sin URL se capturan en sus flujos; la interfaz recibe respectivamente el ID
  del caso fallido o un estado de descarga localizado, no ese texto interno.
  Las pruebas cubren ambos caminos.

Se retiraron del inventario las firmas ya sustituidas y se clasificaron las
cuatro firmas que siguen existiendo con su consumidor y motivo. El autotest
del guardián pasó sus 65 muestras y `npm run check:i18n` informó cero literales
JSX, candidatos sin revisar, diagnósticos pendientes y revisiones obsoletas.
Este barrido no sustituye probar errores reales del backend, diálogos nativos ni
la aplicación instalada.

Las regresiones dirigidas se escribieron antes de los cambios y reproducen
mensajes y detalles localizados, errores externos intactos, nombres sintéticos,
los dos diagnósticos internos y el cambio de idioma. La revisión independiente
añadió otras dos superficies: el descriptor del puente Tauri se conserva al
envolver su error y el aviso de carpeta del navegador se traduce al presentarse.
El 2026-10-27 se cubrió además el cambio de idioma con un aviso de caso ya
visible: el contexto conserva el mensaje estructurado y su detalle hasta
presentarlos, sin modificar la interfaz pública ni traducir texto externo. El
diálogo de creación y el registro de decisiones de Preparación también conservan
los errores hasta presentarlos: las pruebas incluyen fallos que llegan después
de cambiar idioma, avisos tardíos y mensajes externos.

La suite completa final de Vitest pasó con **2379 pruebas en 273 archivos** y
TypeScript pasó. El export de escritorio compiló y su recorrido en inglés pasó
48 estados y cuatro controles positivos; no encontró texto sin tratar en los
canales revisados. Los guardianes de recursos remotos, URL del backend y CSP
también pasaron. ESLint terminó sin errores y con 30 advertencias. Una pasada
anterior descubrió una cadena técnica igual en ambos idiomas; se corrigió antes
de la repetición que pasó. La suite y el recorrido se repitieron tras los últimos
arreglos del 2026-10-27. No se construyó ni probó un instalador nuevo.
