// =====================================================================
// Certificación — el comprobante de integridad en Solana devnet
// =====================================================================
//
// LO QUE ESTE TEXTO TIENE QUE SEGUIR NEGANDO AL CRUZAR DE IDIOMA. Es una prueba
// TÉCNICA en devnet: el SOL no vale nada, la identidad es efímera y lo que se
// publica es un memo de integridad, no un dato científico. Un inglés que
// insinúe «certification on Solana» a secas convierte un experimento en una
// promesa — y es justo la clase de afirmación por la que una tienda retira una
// aplicación.
//
// «devnet» no se traduce: es el nombre de la red.
//
// Y las advertencias de seguridad de la wallet se traducen palabra por palabra.
// «Nunca compartas tu frase de recuperación» protege al usuario de un fraude;
// suavizarla en inglés sería quitarle la protección a quien lea en inglés.

import type { ModuloDeTraduccion } from "./index";

export const certificacion: ModuloDeTraduccion = {
  es: {
    // ── Las advertencias que sostienen todo lo anterior ───────────
    //
    // Son las que dicen que esto NO es una certificación. Se traducen palabra
    // por palabra: un inglés que las suavice convierte una prueba técnica en
    // una promesa de autoría.
    ce_poc_resumen:
      "Prueba de concepto en devnet. Los archivos permanecen locales; la red "
      + "recibe una huella y metadata mínima.",
    ce_poc_experimental:
      "EXPERIMENTAL · Devnet puede reiniciarse y borrar sus registros. Este POC "
      + "sólo prueba el flujo técnico; no certifica autoría, prioridad ni "
      + "validez científica.",
    ce_efimera_detalle:
      "Crea una identidad efímera local, solicita SOL sin valor al faucet y "
      + "publica un memo real. La clave se descarta al terminar.",
    ce_wallet_detalle:
      "Tú apruebas la transacción y pagas la comisión. La firma pública queda "
      + "asociada a tu dirección.",
    ce_directorio_detalle:
      "Consulta wallets compatibles y elige su modelo de custodia. MolDesign "
      + "nunca solicitará tu frase de recuperación.",
    ce_cambiar_metodo: "Cambiar método",
    ce_elegir_otro: "Elegir otro método",
    ce_red_pruebas:
      "Publicará una transacción real en una red de pruebas que puede "
      + "reiniciarse. No tiene validez oficial, científica ni económica.",
    ce_wallet_aprobara:
      "Tu wallet aprobará el memo de integridad y pagará la comisión de la red "
      + "seleccionada.",
    ce_webview_sin_extensiones:
      "El WebView de escritorio no carga extensiones de wallet. Puedes ejecutar "
      + "el POC con identidad efímera o abrir MolDesign en un navegador "
      + "compatible para usar tu wallet.",
    ce_no_custodia:
      "MolDesign no crea ni custodia claves privadas en esta versión. El "
      + "directorio oficial de Solana permite comparar wallets por plataforma y "
      + "modelo de custodia.",
    ce_explorar_wallets: "Explorar wallets de Solana",
    ce_flujo_termino:
      "El flujo técnico terminó en devnet. Este registro puede desaparecer si la "
      + "red de pruebas se reinicia y no constituye certificación.",

    // ── Errores ───────────────────────────────────────────────────
    ce_devnet_no_disponible: "Solana devnet no está disponible en este momento.",
    ce_devnet_no_disponible_corto: "Solana devnet no está disponible.",
    ce_devnet_etiqueta: "devnet no disponible",
    ce_devnet_accesible: "devnet accesible",
    ce_verificando: "verificando",
    ce_memo_fallido: "No se pudo generar el memo de integridad.",
    ce_prueba_fallida:
      "La prueba de Solana devnet no pudo completarse. El faucet público puede "
      + "limitar solicitudes.",
    ce_conecta_wallet: "Conecta tu wallet antes de continuar.",
    ce_error_firma: "Error al firmar con tu wallet.",
    ce_no_registrado: "No se pudo registrar",
    ce_operacion_fallida: "La operación no pudo completarse.",

    // ── Pasos ─────────────────────────────────────────────────────
    ce_paso_faucet: "Solicitando SOL de prueba en devnet",
    ce_paso_memo: "Publicando el memo experimental",
    ce_paso_comprobante: "Preparando el comprobante",
    ce_paso_aprobacion: "Esperando tu aprobación en la wallet",
    ce_paso_confirmando: "Confirmando la transacción en Solana",
    ce_no_cierres:
      "No cierres esta ventana hasta recibir la confirmación de la red.",
    ce_comprobante_creado: "Comprobante de integridad creado",

    // ── Elección de wallet ────────────────────────────────────────
    ce_wallets_solo_web: "Las wallets sólo están disponibles en el navegador web",
    ce_tengo_wallet: "Tengo una wallet",
    ce_solo_navegador:
      "Sólo navegador web · wallet no disponible en la app de escritorio",
    ce_quiero_wallet: "Quiero crear una wallet",
    ce_crear_wallet: "Crear una wallet propia",
    ce_firmar: "Firmar con mi wallet",
    ce_no_en_escritorio: "No disponible dentro de esta app de escritorio",

    // ── La prueba técnica, y lo que no es ─────────────────────────
    ce_prueba_tecnica: "Prueba técnica en Solana devnet",
    ce_faucet_sin_valor: "Faucet devnet · sin valor",
    ce_identidad_efimera: "Identidad efímera local",
    ce_datos_cientificos: "Datos científicos",

    // ── Seguridad de la wallet ────────────────────────────────────
    ce_antes_de_continuar: "Antes de continuar",
    ce_aviso_dominio:
      "· Descarga únicamente desde el dominio oficial del proveedor.",
    ce_aviso_frase:
      "· Nunca compartas tu frase de recuperación con MolDesign ni con soporte.",
    ce_aviso_extensiones:
      "· Esta build de escritorio no conecta extensiones; el POC efímero de "
      + "devnet sí funciona aquí.",
  },
  en: {
    ce_poc_resumen:
      "Proof of concept on devnet. The files stay local; the network receives a "
      + "fingerprint and minimal metadata.",
    ce_poc_experimental:
      "EXPERIMENTAL · Devnet can be reset and wipe its records. This proof of "
      + "concept only exercises the technical flow; it does not certify "
      + "authorship, priority or scientific validity.",
    ce_efimera_detalle:
      "Creates a local ephemeral identity, requests valueless SOL from the "
      + "faucet and publishes a real memo. The key is discarded when it ends.",
    ce_wallet_detalle:
      "You approve the transaction and pay the fee. The public signature stays "
      + "associated with your address.",
    ce_directorio_detalle:
      "Browse compatible wallets and choose their custody model. MolDesign will "
      + "never ask for your recovery phrase.",
    ce_cambiar_metodo: "Change method",
    ce_elegir_otro: "Choose another method",
    ce_red_pruebas:
      "It will publish a real transaction on a test network that can be reset. "
      + "It has no official, scientific or economic validity.",
    ce_wallet_aprobara:
      "Your wallet will approve the integrity memo and pay the fee of the "
      + "selected network.",
    ce_webview_sin_extensiones:
      "The desktop WebView does not load wallet extensions. You can run the "
      + "proof of concept with an ephemeral identity, or open MolDesign in a "
      + "compatible browser to use your wallet.",
    ce_no_custodia:
      "MolDesign neither creates nor holds private keys in this version. The "
      + "official Solana directory lets you compare wallets by platform and "
      + "custody model.",
    ce_explorar_wallets: "Browse Solana wallets",
    ce_flujo_termino:
      "The technical flow finished on devnet. This record may disappear if the "
      + "test network is reset, and it does not constitute certification.",
    ce_devnet_no_disponible: "Solana devnet is not available right now.",
    ce_devnet_no_disponible_corto: "Solana devnet is not available.",
    ce_devnet_etiqueta: "devnet unavailable",
    ce_devnet_accesible: "devnet reachable",
    ce_verificando: "checking",
    ce_memo_fallido: "The integrity memo could not be generated.",
    ce_prueba_fallida:
      "The Solana devnet test could not be completed. The public faucet may "
      + "rate-limit requests.",
    ce_conecta_wallet: "Connect your wallet before continuing.",
    ce_error_firma: "Error signing with your wallet.",
    ce_no_registrado: "Could not be recorded",
    ce_operacion_fallida: "The operation could not be completed.",

    ce_paso_faucet: "Requesting test SOL on devnet",
    ce_paso_memo: "Publishing the experimental memo",
    ce_paso_comprobante: "Preparing the receipt",
    ce_paso_aprobacion: "Waiting for your approval in the wallet",
    ce_paso_confirmando: "Confirming the transaction on Solana",
    ce_no_cierres:
      "Do not close this window until the network confirmation arrives.",
    ce_comprobante_creado: "Integrity receipt created",

    ce_wallets_solo_web: "Wallets are only available in the web browser",
    ce_tengo_wallet: "I have a wallet",
    ce_solo_navegador:
      "Web browser only · wallet not available in the desktop app",
    ce_quiero_wallet: "I want to create a wallet",
    ce_crear_wallet: "Create your own wallet",
    ce_firmar: "Sign with my wallet",
    ce_no_en_escritorio: "Not available inside this desktop app",

    ce_prueba_tecnica: "Technical test on Solana devnet",
    ce_faucet_sin_valor: "devnet faucet · no value",
    ce_identidad_efimera: "Local ephemeral identity",
    ce_datos_cientificos: "Scientific data",

    ce_antes_de_continuar: "Before you continue",
    ce_aviso_dominio:
      "· Download only from the provider's official domain.",
    ce_aviso_frase:
      "· Never share your recovery phrase with MolDesign or with support.",
    ce_aviso_extensiones:
      "· This desktop build does not connect extensions; the ephemeral devnet "
      + "proof of concept does work here.",
  },
};
