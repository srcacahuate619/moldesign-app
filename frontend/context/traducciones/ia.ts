// =====================================================================
// MolChat — el intérprete de IA y sus ajustes
// =====================================================================
//
// DOS TEXTOS DE AQUÍ SON PROMESAS DE PRIVACIDAD Y SE TRADUCEN LITERALES:
//
//   · «Tus credenciales y API Keys se almacenan en tu dispositivo mediante
//     LocalStorage. Nunca son transmitidas a nuestros servidores ni utilizadas
//     para telemetría.»
//   · «En esta máquina» — la etiqueta que distingue un proveedor local de uno
//     en la nube. Perder ese matiz al traducir sería perder la única señal que
//     le dice al usuario si su pregunta sale del equipo.
//
// El comando de Ollama y el nombre de LocalStorage no se traducen: son literales
// que el usuario copia.

import type { ModuloDeTraduccion } from "./index";

export const ia: ModuloDeTraduccion = {
  es: {
    ia_interprete: "Intérprete IA",
    ia_molchat: "MolChat · Intérprete IA",
    ia_rapido: "Rápido",
    ia_razonamiento: "Razonamiento",
    ia_sin_conversaciones: "Sin conversaciones",
    ia_nueva_conversacion: "Nueva conversación",
    ia_modelo_no_descargado: "Modelo LLM no descargado",
    ia_configuracion: "Configuración",
    ia_abrir_configuracion: "Abrir configuración de MolChat",
    ia_cerrar_configuracion: "Cerrar configuración de MolChat",
    ia_ocultar_error: "Ocultar error del último turno",
    ia_ocultar_aviso: "Ocultar este aviso",
    ia_ocultar_aviso_modelo: "Ocultar aviso del modelo local",
    ia_evidencia_usada: "Evidencia usada en esta respuesta",

    // ── Entrada y dictado ─────────────────────────────────────────
    ia_shift_enter: "Shift+Enter · nueva línea",
    ia_microfono: "Micrófono · dictado local",
    ia_dictado_no_disponible:
      "Dictado no disponible: falta el reconocimiento de voz local. Puedes seguir "
      + "escribiendo.",
    ia_dictado_fallo:
      "El dictado local falló. Puedes seguir escribiendo.",
    ia_si_consultar: "Sí, consultar",
    ia_no_gracias: "No, gracias",

    // ── Proveedores ───────────────────────────────────────────────
    ia_sin_proveedor: "Sin proveedor",
    ia_destino_sin_comprobar: "Destino sin comprobar",
    ia_en_esta_maquina: "En esta máquina",
    ia_conectado: "Conectado",
    ia_interprete_local: "Intérprete IA local",
    ia_interprete_online: "Intérprete IA online",
    ia_url_servidor: "URL del servidor",
    ia_sin_modelos:
      "Sin modelos descargados. Busca uno en HuggingFace abajo.",
    ia_modelos_recomendados: "Modelos recomendados para descarga local",
    ia_abrir_carpeta_modelos: "Abrir carpeta de modelos locales (Explorador)",
    ia_cuantizacion: "Cuantización",
    ia_cambiar_destino: "Cambiar el destino",
    ia_asignacion_gpu: "Asignación GPU (VRAM)",
    ia_temperatura: "0 = Analítico (química), 1 = Creativo",

    // ── Nube ──────────────────────────────────────────────────────
    ia_nube_configura:
      "Configura los credenciales y endpoints para conectar MolChat con este "
      + "proveedor.",
    ia_nube_ollama_cors:
      "Asegúrate de ejecutar `OLLAMA_ORIGINS=\"*\" ollama serve` para permitir "
      + "CORS.",
    ia_nube_credenciales_a: "Tus credenciales y API Keys se almacenan",
    ia_nube_credenciales_b:
      "en tu dispositivo mediante LocalStorage. Nunca son transmitidas a nuestros "
      + "servidores ni utilizadas para telemetría.",
  },
  en: {
    ia_interprete: "AI interpreter",
    ia_molchat: "MolChat · AI interpreter",
    ia_rapido: "Fast",
    ia_razonamiento: "Reasoning",
    ia_sin_conversaciones: "No conversations",
    ia_nueva_conversacion: "New conversation",
    ia_modelo_no_descargado: "LLM model not downloaded",
    ia_configuracion: "Settings",
    ia_abrir_configuracion: "Open MolChat settings",
    ia_cerrar_configuracion: "Close MolChat settings",
    ia_ocultar_error: "Hide the error from the last turn",
    ia_ocultar_aviso: "Hide this notice",
    ia_ocultar_aviso_modelo: "Hide the local model notice",
    ia_evidencia_usada: "Evidence used in this answer",

    ia_shift_enter: "Shift+Enter · new line",
    ia_microfono: "Microphone · local dictation",
    ia_dictado_no_disponible:
      "Dictation unavailable: local speech recognition is missing. You can keep "
      + "typing.",
    ia_dictado_fallo: "Local dictation failed. You can keep typing.",
    ia_si_consultar: "Yes, ask",
    ia_no_gracias: "No, thanks",

    ia_sin_proveedor: "No provider",
    ia_destino_sin_comprobar: "Destination not checked",
    ia_en_esta_maquina: "On this machine",
    ia_conectado: "Connected",
    ia_interprete_local: "Local AI interpreter",
    ia_interprete_online: "Online AI interpreter",
    ia_url_servidor: "Server URL",
    ia_sin_modelos: "No models downloaded. Find one on HuggingFace below.",
    ia_modelos_recomendados: "Models recommended for local download",
    ia_abrir_carpeta_modelos: "Open the local models folder (File Explorer)",
    ia_cuantizacion: "Quantisation",
    ia_cambiar_destino: "Change the destination",
    ia_asignacion_gpu: "GPU allocation (VRAM)",
    ia_temperatura: "0 = Analytical (chemistry), 1 = Creative",

    ia_nube_configura:
      "Set the credentials and endpoints to connect MolChat with this provider.",
    ia_nube_ollama_cors:
      "Make sure to run `OLLAMA_ORIGINS=\"*\" ollama serve` to allow CORS.",
    ia_nube_credenciales_a: "Your credentials and API keys are stored",
    ia_nube_credenciales_b:
      "on your device using LocalStorage. They are never transmitted to our "
      + "servers and never used for telemetry.",
  },
};
