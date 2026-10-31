// =====================================================================
// Proveedores de IA de MolChat — elegir, pegar la clave y autorizar
// =====================================================================
//
// DOS TEXTOS DE AQUÍ SON PROMESAS SOBRE LA CLAVE Y SE TRADUCEN LITERALES:
//
//   · «La clave se guarda cifrada en MolDesign, para tu cuenta.»
//   · «MolChat la recibe sólo para cada respuesta y nunca la muestra.»
//
// Si cambia cómo se guarda la clave, estas dos frases cambian con ella. Una
// promesa de privacidad que ya no es cierta es peor que no tenerla.

import type { ModuloDeTraduccion } from "./index";

export const proveedores: ModuloDeTraduccion = {
  es: {
    ia_prov_titulo: "Proveedores de IA",
    ia_prov_intro:
      "Elige un proveedor, pega su clave y autoriza el envío. La clave se guarda cifrada en MolDesign, para tu cuenta. MolChat la recibe sólo para cada respuesta y nunca la muestra.",
    ia_prov_no_disponible: "MolChat no está disponible en esta instalación",
    ia_prov_error_carga: "No se pudo cargar la lista de proveedores.",
    ia_prov_error_generico: "No se pudo completar la operación.",
    ia_prov_error_destino:
      "El destino cambió desde que lo viste. Revisa el host y vuelve a intentarlo.",
    ia_prov_error_formato: "La clave no tiene un formato válido.",
    ia_prov_guardado: "Clave guardada y envío autorizado.",
    ia_prov_retirado: "Clave retirada y autorizaciones revocadas.",
    ia_prov_activo: "Activo",
    ia_prov_usar: "Usar este proveedor",
    ia_prov_dejar_de_usar: "Dejar de usar",
    ia_prov_local: "En esta máquina",
    ia_prov_sale_a: "Sale de esta máquina a {host}",
    ia_prov_clave_guardada: "Clave guardada · {pista}",
    ia_prov_sin_clave: "Sin clave",
    ia_prov_autorizado: "Envío autorizado",
    ia_prov_sin_autorizar: "Envío sin autorizar",
    ia_prov_necesita_clave: "Antes de usarlo, guarda una clave y autoriza el envío.",
    ia_prov_clave_label: "Clave de API",
    ia_prov_modelo_label: "Modelo",
    ia_prov_modelo_vacio: "Escribe el nombre del modelo",
    ia_prov_guardar: "Guardar y autorizar envío a {host}",
    ia_prov_retirar: "Retirar clave",
    ia_prov_que_sale: "Qué sale de esta máquina",
    ia_prov_documentacion: "Documentación",
    ia_prov_guardando: "Guardando…",
  },
  en: {
    ia_prov_titulo: "AI providers",
    ia_prov_intro:
      "Choose a provider, paste its key and authorize sending. The key is stored encrypted in MolDesign, for your account. MolChat receives it only for each answer and never shows it.",
    ia_prov_no_disponible: "MolChat is not available in this installation",
    ia_prov_error_carga: "The provider list could not be loaded.",
    ia_prov_error_generico: "The operation could not be completed.",
    ia_prov_error_destino:
      "The destination changed since you saw it. Check the host and try again.",
    ia_prov_error_formato: "The key has an invalid format.",
    ia_prov_guardado: "Key saved and sending authorized.",
    ia_prov_retirado: "Key removed and authorizations revoked.",
    ia_prov_activo: "Active",
    ia_prov_usar: "Use this provider",
    ia_prov_dejar_de_usar: "Stop using",
    ia_prov_local: "On this machine",
    ia_prov_sale_a: "Leaves this machine to {host}",
    ia_prov_clave_guardada: "Key saved · {pista}",
    ia_prov_sin_clave: "No key",
    ia_prov_autorizado: "Sending authorized",
    ia_prov_sin_autorizar: "Sending not authorized",
    ia_prov_necesita_clave: "Before using it, save a key and authorize sending.",
    ia_prov_clave_label: "API key",
    ia_prov_modelo_label: "Model",
    ia_prov_modelo_vacio: "Type the model name",
    ia_prov_guardar: "Save and authorize sending to {host}",
    ia_prov_retirar: "Remove key",
    ia_prov_que_sale: "What leaves this machine",
    ia_prov_documentacion: "Documentation",
    ia_prov_guardando: "Saving…",
  },
};
