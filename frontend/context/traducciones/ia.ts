// =====================================================================
// MolChat — el intérprete de IA y sus ajustes
// =====================================================================
//
// DOS TEXTOS DE AQUÍ SON PROMESAS DE PRIVACIDAD Y SE TRADUCEN LITERALES:
//
//   · «Tus credenciales y API Keys se almacenan en tu dispositivo mediante
//     LocalStorage. Nunca son transmitidas a nuestros servidores ni utilizadas
//     para telemetría.»
//   · «Los datos se quedan en esta máquina» — la etiqueta que distingue un proveedor local de uno
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
    ia_modelo_descargandose: "Descargando el modelo LLM…",
    ia_badge_gpu_sin_cargar: "GPU {gpu} · sin cargar, se carga al preguntar",
    ia_badge_ram_sin_cargar: "RAM {libre}G / {total}G · sin cargar, se carga al preguntar",
    ia_badge_ollama_no_disponible: "Ollama no disponible",
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

    // ── Propuesta de docking (LUNA-05) ────────────────────────────
    // MolChat propone; sólo este botón, con la sesión de la cuenta, lanza.
    ia_propuesta_grupo: "Aprobación de la evaluación propuesta",
    ia_propuesta_aprobar: "Aprobar y lanzar",
    ia_propuesta_cancelar: "Cancelar propuesta",
    ia_propuesta_aprobando: "Lanzando…",
    ia_propuesta_nota:
      "Este botón confirma con tu sesión y queda atado a la huella de esta propuesta. "
      + "Escribir «sí» en el chat no lanza nada.",
    ia_propuesta_lanzada: "Evaluación lanzada tras tu aprobación.",
    ia_propuesta_cancelada: "Propuesta cancelada. No se lanzó nada.",
    ia_propuesta_ya_no_pendiente:
      "Esta propuesta ya no está pendiente: se aprobó, se rechazó o caducó. "
      + "Pídela de nuevo en el chat.",
    ia_propuesta_error: "No se pudo lanzar la evaluación",

    // ── Proveedores ───────────────────────────────────────────────
    ia_sin_proveedor: "Sin proveedor",
    ia_destino_sin_comprobar: "Destino sin comprobar",
    ia_en_esta_maquina: "Los datos se quedan en esta máquina",
    ia_conectado: "Conectado",
    ia_interprete_local: "Intérprete IA local",
    ia_interprete_online: "Intérprete IA online",
    ia_url_servidor: "URL del servidor",
    ia_sin_modelos:
      "Sin modelos descargados. Descarga uno de los recomendados de abajo.",
    ia_modelos_recomendados: "Modelos recomendados para descarga local",
    ia_abrir_carpeta_modelos: "Abrir carpeta de modelos locales (Explorador)",
    ia_cuantizacion: "Cuantización",
    ia_cambiar_destino: "Cambiar el destino",
    ia_asignacion_gpu: "Asignación GPU (VRAM)",
    ia_temperatura: "0 = Analítico (química), 1 = Creativo",

    // ── Ajustes del proveedor ────────────────────────────────────
    ia_cfg_api_key: "Clave de API",
    ia_cfg_base_url: "URL base",
    ia_cfg_available: "Disponible",
    ia_cfg_ram_free: "{gb} GB de RAM libres.",
    ia_cfg_vram_free: "GB libres",
    ia_cfg_saved: "Guardado",
    ia_cfg_keep_loaded: "Mantener MolChat cargado durante las evaluaciones",
    ia_cfg_mode: "Modo",
    ia_cfg_show_api_key: "Mostrar clave de API",
    ia_cfg_hide_api_key: "Ocultar clave de API",
    ia_cfg_ollama: "Ollama",
    ia_cfg_ollama_running_at: "Ollama debe estar instalado y en ejecución en",
    ia_cfg_qwen35_4b_model: "Qwen3.5 4B",
    ia_cfg_qwen35_4b_desc:
      "Elige mejor las herramientas de MolChat: acertó 21 de 21 en nuestro arnés en "
      + "español (Qwen2.5 1.5B, 17). En CPU es unas 3 veces más lento.",
    ia_cfg_advanced: "Avanzado",
    ia_cfg_cloud_provider: "Proveedor en la nube",
    ia_cfg_qwen05_model: "Qwen2.5 0.5B",
    ia_cfg_lightweight: "Ligero",
    ia_cfg_qwen15_model: "Qwen2.5 1.5B",
    ia_cfg_recommended: "Recomendado",
    ia_cfg_vram_insufficient:
      "VRAM insuficiente ({vram} GB disponibles). CPU: {ram} GB RAM.",
    ia_cfg_api_key_example: "sk-...",
    ia_cfg_api_key_guardada: "Hay una clave guardada. Escribe otra sólo para cambiarla.",
    ia_ollama_responde_uno: "Ollama responde en {url} · {n} modelo instalado.",
    ia_ollama_responde_varios: "Ollama responde en {url} · {n} modelos instalados.",
    ia_ollama_sin_comprobar: "Estado de Ollama sin comprobar todavía.",
    ia_ollama_url_sin_guardar: "Guarda la configuración para comprobar la URL nueva.",
    ia_ollama_instalados: "Modelos instalados en Ollama",
    ia_autorizar_y_descargar: "Autorizar {host} y descargar",
    ia_cuant_sin_modelo: "Ninguno de tus modelos tiene esta cuantización.",
    ia_cuant_varios: "Varios de tus modelos la tienen: elige el modelo arriba.",
    ia_chat_stop: "Detener",
    ia_chat_dictation_unavailable_short: "Dictado no disponible",
    ia_chat_send: "Enviar",
    ia_chat_send_message: "Enviar mensaje",
    ia_chat_listening: "Escuchando...",
    ia_chat_ask_molchat: "Pregunta a MolChat...",
    ia_chat_activate_web_mode: "Activar modo web",
    ia_chat_deactivate_web_mode: "Desactivar modo web",
    ia_chat_web_mode: "Web",
    ia_chat_offline: "Sin conexión",
    ia_chat_history: "Historial",
    ia_chat_show_history: "Mostrar historial",
    ia_chat_hide_history: "Ocultar historial",
    ia_chat_new: "Nuevo chat",
    ia_chat_authorize: "Autorizar",
    ia_chat_hide_notice: "Ocultar aviso",
    ia_chat_message_count_one: "{count} mensaje",
    ia_chat_message_count_many: "{count} mensajes",
    ia_provider_destination: "Sale a {host}",

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
    ia_modelo_descargandose: "Downloading the LLM model…",
    ia_badge_gpu_sin_cargar: "GPU {gpu} · not loaded, loads when you ask",
    ia_badge_ram_sin_cargar: "RAM {libre}G / {total}G · not loaded, loads when you ask",
    ia_badge_ollama_no_disponible: "Ollama unavailable",
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

    // ── Docking proposal (LUNA-05) ────────────────────────────────
    ia_propuesta_grupo: "Approval of the proposed evaluation",
    ia_propuesta_aprobar: "Approve and launch",
    ia_propuesta_cancelar: "Cancel proposal",
    ia_propuesta_aprobando: "Launching…",
    ia_propuesta_nota:
      "This button confirms with your session and is bound to this proposal's "
      + "fingerprint. Typing \"yes\" in the chat launches nothing.",
    ia_propuesta_lanzada: "Evaluation launched after your approval.",
    ia_propuesta_cancelada: "Proposal canceled. Nothing was launched.",
    ia_propuesta_ya_no_pendiente:
      "This proposal is no longer pending: it was approved, rejected or expired. "
      + "Ask for it again in the chat.",
    ia_propuesta_error: "The evaluation could not be launched",

    ia_sin_proveedor: "No provider",
    ia_destino_sin_comprobar: "Destination not checked",
    ia_en_esta_maquina: "Data stays on this machine",
    ia_conectado: "Connected",
    ia_interprete_local: "Local AI interpreter",
    ia_interprete_online: "Online AI interpreter",
    ia_url_servidor: "Server URL",
    ia_sin_modelos: "No models downloaded. Download one of the recommended models below.",
    ia_modelos_recomendados: "Models recommended for local download",
    ia_abrir_carpeta_modelos: "Open the local models folder (File Explorer)",
    ia_cuantizacion: "Quantisation",
    ia_cambiar_destino: "Change the destination",
    ia_asignacion_gpu: "GPU allocation (VRAM)",
    ia_temperatura: "0 = Analytical (chemistry), 1 = Creative",

    ia_cfg_api_key: "API key",
    ia_cfg_base_url: "Base URL",
    ia_cfg_available: "Available",
    ia_cfg_ram_free: "{gb} GB of RAM free.",
    ia_cfg_vram_free: "GB free",
    ia_cfg_saved: "Saved",
    ia_cfg_keep_loaded: "Keep MolChat loaded during evaluations",
    ia_cfg_mode: "Mode",
    ia_cfg_show_api_key: "Show API key",
    ia_cfg_hide_api_key: "Hide API key",
    ia_cfg_ollama: "Ollama",
    ia_cfg_ollama_running_at: "Ollama must be installed and running at",
    ia_cfg_qwen35_4b_model: "Qwen3.5 4B",
    ia_cfg_qwen35_4b_desc:
      "Picks MolChat's tools better: 21 of 21 right in our Spanish test harness "
      + "(Qwen2.5 1.5B, 17). About 3 times slower on CPU.",
    ia_cfg_advanced: "Advanced",
    ia_cfg_cloud_provider: "Cloud provider",
    ia_cfg_qwen05_model: "Qwen2.5 0.5B",
    ia_cfg_lightweight: "Lightweight",
    ia_cfg_qwen15_model: "Qwen2.5 1.5B",
    ia_cfg_recommended: "Recommended",
    ia_cfg_vram_insufficient:
      "Insufficient VRAM ({vram} GB available). CPU: {ram} GB RAM.",
    ia_cfg_api_key_example: "sk-...",
    ia_cfg_api_key_guardada: "A key is already saved. Type another one only to replace it.",
    ia_ollama_responde_uno: "Ollama is answering at {url} · {n} model installed.",
    ia_ollama_responde_varios: "Ollama is answering at {url} · {n} models installed.",
    ia_ollama_sin_comprobar: "Ollama status not checked yet.",
    ia_ollama_url_sin_guardar: "Save the settings to check the new URL.",
    ia_ollama_instalados: "Models installed in Ollama",
    ia_autorizar_y_descargar: "Authorize {host} and download",
    ia_cuant_sin_modelo: "None of your models uses this quantisation.",
    ia_cuant_varios: "Several of your models use it: pick the model above.",
    ia_chat_stop: "Stop",
    ia_chat_dictation_unavailable_short: "Dictation unavailable",
    ia_chat_send: "Send",
    ia_chat_send_message: "Send message",
    ia_chat_listening: "Listening...",
    ia_chat_ask_molchat: "Ask MolChat...",
    ia_chat_activate_web_mode: "Enable web mode",
    ia_chat_deactivate_web_mode: "Disable web mode",
    ia_chat_web_mode: "Web",
    ia_chat_offline: "Offline",
    ia_chat_history: "History",
    ia_chat_show_history: "Show history",
    ia_chat_hide_history: "Hide history",
    ia_chat_new: "New chat",
    ia_chat_authorize: "Authorize",
    ia_chat_hide_notice: "Hide notice",
    ia_chat_message_count_one: "{count} message",
    ia_chat_message_count_many: "{count} messages",
    ia_provider_destination: "Goes to {host}",

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
