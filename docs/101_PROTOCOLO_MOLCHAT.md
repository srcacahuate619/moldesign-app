# Protocolo de integración con MolChat

Estado: cambios en preparación local; no se ha probado el instalador integrado ni publicado una versión.

La especificación del lado independiente está en `docs/PROTOCOLO_MOLDESIGN.md` del repositorio MolChat. Esta nota fija el contrato que implementa MolDesign y se verifica con las pruebas de ambos proyectos.

- Los programas son procesos independientes. El host comprueba el manifiesto del sidecar y su salud `moldesign.molchat/1`; no lo importa como biblioteca.
- El backend comunica al sidecar su puerto real, tomado del socket ASGI, nunca de la cabecera `Host`.
- La sesión `mh1` es de corta vida y está ligada a una cuenta. El iframe y el padre comprueban origen y ventana; la sesión no viaja en la URL. El mensaje de sesión incluye el idioma `es` o `en` y el tema `dark` o `light`, que el sidecar aplica y actualiza cuando cambian en MolDesign; el sidecar también acepta hosts anteriores que no los envían. Las acciones conservan la autorización, la aprobación por huella y la reconciliación existentes.
- `GET /molchat-host/contract`, con identidad, declara `moldesign.molchat/1` y capacidades versionadas. `platform-actions/1` declara la superficie de acciones, no que cada motor esté disponible. La ausencia de una capacidad o una versión incompatible detiene la operación.
- `POST /molchat-host/properties`, con identidad, valida el SMILES y devuelve `properties/1`, sus descriptores, el SMILES canónico, la versión de RDKit y avisos. Se calcula con el código del producto sin ADMET-AI; no es una predicción de actividad. Una entrada inválida devuelve 422 sin valores.
- La CSP permite el iframe local del sidecar. El runtime sigue restringido a loopback; cada ventana verifica el origen y la ventana que envían mensajes.

Pruebas: regresiones de salud, puerto, identidad, cálculo y mensajes; pruebas del cliente independientes; e integración entre procesos. `npm run smoke:molchat-csp` carga la UI vendorizada con la CSP de producción en Chromium, desde el origen de Tauri; requiere el puerto local 80 libre y un navegador de Playwright o `MOLCHAT_TEST_BROWSER`. No sustituye la prueba del instalador WebView2. Antes de publicar se debe comprobar que el commit fuente vendorizado está disponible y probar el instalador construido.
