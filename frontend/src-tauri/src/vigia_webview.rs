//! Lo que hace la ventana cuando WebView2 pierde un proceso o una navegación termina en una página de error.
//!
//! EL FALLO (VM de 1.0.2, 2026-10-12). Con la aplicación quieta alrededor de una hora, la ventana dejó de enseñar MolDesign y
//! enseñó el cartel de WebView2 que pide actualizar la página. No quedó registro de por qué: Tauri no atiende
//! `ProcessFailed` ni las navegaciones fallidas, así que WebView2 se quedaba en su página de error y la aplicación no se
//! enteraba. El frontend no navega solo (se revisó: ningún temporizador recarga ni cambia de dirección), así que el cartel
//! sólo puede venir de WebView2: un proceso suyo que muere (memoria agotada, la GPU de una VM al apagarse la pantalla…) o
//! una navegación que falla.
//!
//! QUÉ HACE. Escribe cada evento en el registro de arranque (`desktop-bootstrap.log`, junto a los demás registros de la
//! aplicación) con su tipo, su motivo y su código de salida —la próxima vez habrá con qué diagnosticar—, y se recupera:
//!
//! - si muere el proceso que dibuja la página (`RENDER_PROCESS_EXITED`), recarga la misma página, como pide la
//!   documentación de WebView2. Las corridas viven en el backend, que no se toca; lo que la página tenía sólo en memoria
//!   se pierde igual que con el botón «Actualizar»;
//! - si una navegación de la ventana termina en página de error de red, vuelve al inicio de la aplicación;
//! - un proceso que no responde, la GPU que se reinicia o el proceso del navegador que termina sólo se registran: los dos
//!   primeros los resuelve WebView2, y el tercero no se puede recuperar recargando.
//!
//! Como mucho 3 recuperaciones cada 10 minutos: si la causa sigue ahí, recargar en bucle no la arregla y taparía el fallo.

use std::collections::VecDeque;
use std::time::{Duration, Instant};

/// Qué hacer con un evento de WebView2.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) enum Accion {
    /// Recargar la página que estaba abierta.
    Recargar,
    /// Volver al inicio de la aplicación.
    VolverAlInicio,
    /// Sólo dejarlo escrito.
    Registrar,
    /// Nada: no es un fallo.
    Nada,
}

// Valores de `COREWEBVIEW2_PROCESS_FAILED_KIND` (WebView2 SDK; los mismos en webview2-com-sys 0.38).
const PROCESO_NAVEGADOR: i32 = 0;
const PROCESO_PAGINA: i32 = 1;
const PAGINA_SIN_RESPUESTA: i32 = 2;
const PROCESO_MARCO: i32 = 3;
const PROCESO_UTILIDAD: i32 = 4;
const PROCESO_SANDBOX: i32 = 5;
const PROCESO_GPU: i32 = 6;

// Valores de `COREWEBVIEW2_WEB_ERROR_STATUS` que importan aquí (una prueba los compara con las constantes del SDK).
const ESTADO_DESCONOCIDO: i32 = 0;
const SERVIDOR_INALCANZABLE: i32 = 6;
const TIEMPO_AGOTADO: i32 = 7;
const RESPUESTA_INVALIDA: i32 = 8;
const CONEXION_ABORTADA: i32 = 9;
const CONEXION_REINICIADA: i32 = 10;
const DESCONECTADO: i32 = 11;
const NO_SE_PUDO_CONECTAR: i32 = 12;
const NOMBRE_NO_RESUELTO: i32 = 13;
const CANCELADA: i32 = 14;
const REDIRECCION_FALLIDA: i32 = 15;
const ERROR_INESPERADO: i32 = 16;

pub(crate) fn accion_por_proceso(tipo: i32) -> Accion {
    match tipo {
        PROCESO_PAGINA => Accion::Recargar,
        _ => Accion::Registrar,
    }
}

/// Una navegación de la ventana principal que terminó. Sólo los errores de red dejan a WebView2 enseñando su página de error.
///
/// `CANCELADA` y `CONEXION_ABORTADA` no: son las que se cancelan o se convierten en descarga (un PDF, un vídeo), y volver al
/// inicio ahí borraría la pantalla en la que el investigador estaba trabajando.
pub(crate) fn accion_por_navegacion(exito: bool, estado: i32) -> Accion {
    if exito {
        return Accion::Nada;
    }
    match estado {
        NOMBRE_NO_RESUELTO
        | NO_SE_PUDO_CONECTAR
        | CONEXION_REINICIADA
        | DESCONECTADO
        | SERVIDOR_INALCANZABLE
        | TIEMPO_AGOTADO
        | RESPUESTA_INVALIDA
        | REDIRECCION_FALLIDA
        | ERROR_INESPERADO => Accion::VolverAlInicio,
        CANCELADA | CONEXION_ABORTADA | ESTADO_DESCONOCIDO => Accion::Registrar,
        // Certificados y credenciales: no los pide ninguna dirección de la aplicación; se registran y nada más.
        _ => Accion::Registrar,
    }
}

pub(crate) fn nombre_del_proceso(tipo: i32) -> &'static str {
    match tipo {
        PROCESO_NAVEGADOR => "navegador",
        PROCESO_PAGINA => "pagina",
        PAGINA_SIN_RESPUESTA => "pagina_sin_respuesta",
        PROCESO_MARCO => "marco",
        PROCESO_UTILIDAD => "utilidad",
        PROCESO_SANDBOX => "sandbox",
        PROCESO_GPU => "gpu",
        _ => "otro",
    }
}

pub(crate) fn nombre_del_motivo(motivo: i32) -> &'static str {
    // `COREWEBVIEW2_PROCESS_FAILED_REASON`.
    match motivo {
        0 => "inesperado",
        1 => "sin_respuesta",
        2 => "terminado",
        3 => "fallo",
        4 => "no_arranco",
        5 => "sin_memoria",
        6 => "perfil_borrado",
        _ => "otro",
    }
}

/// Como mucho `maximo` recuperaciones dentro de cada `ventana` de tiempo.
pub(crate) struct Limitador {
    ventana: Duration,
    maximo: usize,
    recientes: VecDeque<Instant>,
}

impl Limitador {
    pub(crate) fn new(maximo: usize, ventana: Duration) -> Self {
        Self {
            ventana,
            maximo,
            recientes: VecDeque::new(),
        }
    }

    pub(crate) fn permitir(&mut self, ahora: Instant) -> bool {
        while self
            .recientes
            .front()
            .is_some_and(|t| ahora.duration_since(*t) >= self.ventana)
        {
            self.recientes.pop_front();
        }
        if self.recientes.len() >= self.maximo {
            return false;
        }
        self.recientes.push_back(ahora);
        true
    }
}

/// El inicio de la aplicación a partir de la dirección con la que se abrió la ventana (`http://tauri.localhost/` instalada,
/// el servidor de Next en desarrollo).
pub(crate) fn inicio_de(url: &tauri::Url) -> tauri::Url {
    let mut inicio = url.clone();
    inicio.set_path("/");
    inicio.set_query(None);
    inicio.set_fragment(None);
    inicio
}

#[cfg(windows)]
pub fn vigilar(ventana: &tauri::WebviewWindow) {
    use std::sync::{Arc, Mutex};
    use webview2_com::Microsoft::Web::WebView2::Win32::{
        ICoreWebView2NavigationCompletedEventArgs2, ICoreWebView2ProcessFailedEventArgs2,
        COREWEBVIEW2_PROCESS_FAILED_KIND, COREWEBVIEW2_PROCESS_FAILED_REASON,
        COREWEBVIEW2_WEB_ERROR_STATUS,
    };
    use webview2_com::{take_pwstr, NavigationCompletedEventHandler, ProcessFailedEventHandler};
    use windows::core::{Interface, BOOL, PWSTR};

    let inicio = match ventana.url() {
        Ok(url) => inicio_de(&url),
        Err(error) => {
            log::warn!("Vigía del WebView sin dirección de inicio: {error}");
            return;
        }
    };
    let limitador = Arc::new(Mutex::new(Limitador::new(3, Duration::from_secs(600))));
    let para_proceso = ventana.clone();
    let para_navegacion = ventana.clone();
    let limitador_navegacion = limitador.clone();

    // Recargar o navegar desde otro hilo y un poco después: el despachador de Tauri lo encola en el bucle de la ventana,
    // fuera del manejador del evento de WebView2 (el ejemplo de Microsoft también lo difiere).
    fn despues(ventana: tauri::WebviewWindow, accion: Accion, inicio: tauri::Url) {
        std::thread::spawn(move || {
            std::thread::sleep(Duration::from_millis(500));
            let resultado = match accion {
                Accion::Recargar => ventana.reload(),
                Accion::VolverAlInicio => ventana.navigate(inicio),
                Accion::Registrar | Accion::Nada => Ok(()),
            };
            if let Err(error) = resultado {
                crate::bootstrap_log(&format!("webview:recuperacion_fallida {error}"));
                log::error!("No se pudo recuperar la ventana: {error}");
            }
        });
    }

    let inicio_proceso = inicio.clone();
    let resultado = ventana.with_webview(move |plataforma| unsafe {
        let Ok(webview) = plataforma.controller().CoreWebView2() else {
            crate::bootstrap_log("webview:vigia_sin_core");
            return;
        };
        let mut token = 0i64;
        let limitador_proceso = limitador.clone();
        let registro = webview.add_ProcessFailed(
            &ProcessFailedEventHandler::create(Box::new(move |_, args| {
                let Some(args) = args else { return Ok(()) };
                let mut tipo = COREWEBVIEW2_PROCESS_FAILED_KIND::default();
                args.ProcessFailedKind(&mut tipo)?;
                let (mut motivo, mut salida) = (COREWEBVIEW2_PROCESS_FAILED_REASON::default(), 0i32);
                let mut descripcion = String::new();
                if let Ok(args2) = args.cast::<ICoreWebView2ProcessFailedEventArgs2>() {
                    let _ = args2.Reason(&mut motivo);
                    let _ = args2.ExitCode(&mut salida);
                    let mut texto = PWSTR::null();
                    if args2.ProcessDescription(&mut texto).is_ok() {
                        descripcion = take_pwstr(texto);
                    }
                }
                let mut accion = accion_por_proceso(tipo.0);
                if accion != Accion::Registrar && !limitador_proceso.lock().map(|mut l| l.permitir(Instant::now())).unwrap_or(false) {
                    accion = Accion::Registrar;
                    crate::bootstrap_log("webview:recuperacion_suprimida demasiadas en 10 min");
                }
                let linea = format!(
                    "webview:proceso_fallido tipo={} motivo={} salida=0x{:08X} descripcion={:?} accion={:?}",
                    nombre_del_proceso(tipo.0),
                    nombre_del_motivo(motivo.0),
                    salida as u32,
                    descripcion,
                    accion
                );
                crate::bootstrap_log(&linea);
                log::error!("{linea}");
                if accion == Accion::Recargar {
                    despues(para_proceso.clone(), accion, inicio_proceso.clone());
                }
                Ok(())
            })),
            &mut token,
        );
        if let Err(error) = registro {
            crate::bootstrap_log(&format!("webview:vigia_proceso_no_registrado {error}"));
        }
        let registro = webview.add_NavigationCompleted(
            &NavigationCompletedEventHandler::create(Box::new(move |sender, args| {
                let Some(args) = args else { return Ok(()) };
                let mut exito = BOOL::default();
                args.IsSuccess(&mut exito)?;
                if exito.as_bool() {
                    return Ok(());
                }
                let mut estado = COREWEBVIEW2_WEB_ERROR_STATUS::default();
                args.WebErrorStatus(&mut estado)?;
                let mut http = 0i32;
                if let Ok(args2) = args.cast::<ICoreWebView2NavigationCompletedEventArgs2>() {
                    let _ = args2.HttpStatusCode(&mut http);
                }
                let mut direccion = String::new();
                if let Some(sender) = sender {
                    let mut texto = PWSTR::null();
                    if sender.Source(&mut texto).is_ok() {
                        direccion = take_pwstr(texto);
                    }
                }
                let mut accion = accion_por_navegacion(false, estado.0);
                if accion == Accion::VolverAlInicio
                    && !limitador_navegacion.lock().map(|mut l| l.permitir(Instant::now())).unwrap_or(false)
                {
                    accion = Accion::Registrar;
                    crate::bootstrap_log("webview:recuperacion_suprimida demasiadas en 10 min");
                }
                let linea = format!(
                    "webview:navegacion_fallida estado={} http={} url={:?} accion={:?}",
                    estado.0, http, direccion, accion
                );
                crate::bootstrap_log(&linea);
                log::warn!("{linea}");
                if accion == Accion::VolverAlInicio {
                    despues(para_navegacion.clone(), accion, inicio.clone());
                }
                Ok(())
            })),
            &mut token,
        );
        if let Err(error) = registro {
            crate::bootstrap_log(&format!("webview:vigia_navegacion_no_registrado {error}"));
        }
        crate::bootstrap_log("webview:vigia_activo");
    });
    if let Err(error) = resultado {
        crate::bootstrap_log(&format!("webview:vigia_no_instalado {error}"));
    }
}

#[cfg(not(windows))]
pub fn vigilar(_ventana: &tauri::WebviewWindow) {}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn muere_la_pagina_y_se_recarga() {
        assert_eq!(accion_por_proceso(PROCESO_PAGINA), Accion::Recargar);
    }

    #[test]
    fn lo_que_webview2_resuelve_solo_o_no_se_arregla_recargando_solo_se_registra() {
        for tipo in [
            PROCESO_NAVEGADOR,
            PAGINA_SIN_RESPUESTA,
            PROCESO_MARCO,
            PROCESO_UTILIDAD,
            PROCESO_SANDBOX,
            PROCESO_GPU,
            99,
        ] {
            assert_eq!(accion_por_proceso(tipo), Accion::Registrar, "tipo {tipo}");
        }
    }

    #[test]
    fn una_pagina_de_error_de_red_vuelve_al_inicio() {
        for estado in [
            NOMBRE_NO_RESUELTO,
            NO_SE_PUDO_CONECTAR,
            CONEXION_REINICIADA,
            DESCONECTADO,
            SERVIDOR_INALCANZABLE,
            TIEMPO_AGOTADO,
        ] {
            assert_eq!(
                accion_por_navegacion(false, estado),
                Accion::VolverAlInicio,
                "estado {estado}"
            );
        }
    }

    #[test]
    fn una_descarga_o_una_cancelacion_no_tocan_la_pantalla() {
        // Un PDF o un MP4 que se descarga termina la navegación sin éxito: volver al inicio borraría el trabajo en pantalla.
        assert_eq!(
            accion_por_navegacion(false, CONEXION_ABORTADA),
            Accion::Registrar
        );
        assert_eq!(accion_por_navegacion(false, CANCELADA), Accion::Registrar);
        assert_eq!(
            accion_por_navegacion(false, ESTADO_DESCONOCIDO),
            Accion::Registrar
        );
        assert_eq!(
            accion_por_navegacion(true, NOMBRE_NO_RESUELTO),
            Accion::Nada
        );
    }

    #[test]
    fn el_limitador_corta_el_bucle_y_se_recupera_con_el_tiempo() {
        let mut limitador = Limitador::new(3, Duration::from_secs(600));
        let t0 = Instant::now();
        assert!(limitador.permitir(t0));
        assert!(limitador.permitir(t0 + Duration::from_secs(1)));
        assert!(limitador.permitir(t0 + Duration::from_secs(2)));
        assert!(!limitador.permitir(t0 + Duration::from_secs(3)));
        assert!(!limitador.permitir(t0 + Duration::from_secs(599)));
        assert!(limitador.permitir(t0 + Duration::from_secs(600)));
    }

    #[test]
    fn el_inicio_es_la_raiz_de_la_aplicacion() {
        let instalada: tauri::Url = "http://tauri.localhost/molcy?x=1#y".parse().unwrap();
        assert_eq!(inicio_de(&instalada).as_str(), "http://tauri.localhost/");
        let desarrollo: tauri::Url = "http://localhost:3000/evaluation".parse().unwrap();
        assert_eq!(inicio_de(&desarrollo).as_str(), "http://localhost:3000/");
    }

    /// Los números se escribieron a mano: tienen que ser los del SDK que enlaza wry (la primera versión de este módulo se
    /// equivocó en los de los errores de red, y una descarga habría devuelto la ventana al inicio).
    #[cfg(windows)]
    #[test]
    fn las_constantes_son_las_del_sdk_de_webview2() {
        use webview2_com::Microsoft::Web::WebView2::Win32 as sdk;
        let red = [
            (
                ESTADO_DESCONOCIDO,
                sdk::COREWEBVIEW2_WEB_ERROR_STATUS_UNKNOWN,
            ),
            (
                SERVIDOR_INALCANZABLE,
                sdk::COREWEBVIEW2_WEB_ERROR_STATUS_SERVER_UNREACHABLE,
            ),
            (TIEMPO_AGOTADO, sdk::COREWEBVIEW2_WEB_ERROR_STATUS_TIMEOUT),
            (
                RESPUESTA_INVALIDA,
                sdk::COREWEBVIEW2_WEB_ERROR_STATUS_ERROR_HTTP_INVALID_SERVER_RESPONSE,
            ),
            (
                CONEXION_ABORTADA,
                sdk::COREWEBVIEW2_WEB_ERROR_STATUS_CONNECTION_ABORTED,
            ),
            (
                CONEXION_REINICIADA,
                sdk::COREWEBVIEW2_WEB_ERROR_STATUS_CONNECTION_RESET,
            ),
            (
                DESCONECTADO,
                sdk::COREWEBVIEW2_WEB_ERROR_STATUS_DISCONNECTED,
            ),
            (
                NO_SE_PUDO_CONECTAR,
                sdk::COREWEBVIEW2_WEB_ERROR_STATUS_CANNOT_CONNECT,
            ),
            (
                NOMBRE_NO_RESUELTO,
                sdk::COREWEBVIEW2_WEB_ERROR_STATUS_HOST_NAME_NOT_RESOLVED,
            ),
            (
                CANCELADA,
                sdk::COREWEBVIEW2_WEB_ERROR_STATUS_OPERATION_CANCELED,
            ),
            (
                REDIRECCION_FALLIDA,
                sdk::COREWEBVIEW2_WEB_ERROR_STATUS_REDIRECT_FAILED,
            ),
            (
                ERROR_INESPERADO,
                sdk::COREWEBVIEW2_WEB_ERROR_STATUS_UNEXPECTED_ERROR,
            ),
        ];
        for (nuestro, suyo) in red {
            assert_eq!(nuestro, suyo.0, "{suyo:?}");
        }
        let procesos = [
            (
                PROCESO_NAVEGADOR,
                sdk::COREWEBVIEW2_PROCESS_FAILED_KIND_BROWSER_PROCESS_EXITED,
            ),
            (
                PROCESO_PAGINA,
                sdk::COREWEBVIEW2_PROCESS_FAILED_KIND_RENDER_PROCESS_EXITED,
            ),
            (
                PAGINA_SIN_RESPUESTA,
                sdk::COREWEBVIEW2_PROCESS_FAILED_KIND_RENDER_PROCESS_UNRESPONSIVE,
            ),
            (
                PROCESO_MARCO,
                sdk::COREWEBVIEW2_PROCESS_FAILED_KIND_FRAME_RENDER_PROCESS_EXITED,
            ),
            (
                PROCESO_UTILIDAD,
                sdk::COREWEBVIEW2_PROCESS_FAILED_KIND_UTILITY_PROCESS_EXITED,
            ),
            (
                PROCESO_SANDBOX,
                sdk::COREWEBVIEW2_PROCESS_FAILED_KIND_SANDBOX_HELPER_PROCESS_EXITED,
            ),
            (
                PROCESO_GPU,
                sdk::COREWEBVIEW2_PROCESS_FAILED_KIND_GPU_PROCESS_EXITED,
            ),
        ];
        for (nuestro, suyo) in procesos {
            assert_eq!(nuestro, suyo.0, "{suyo:?}");
        }
        assert_eq!(sdk::COREWEBVIEW2_PROCESS_FAILED_REASON_OUT_OF_MEMORY.0, 5);
        assert_eq!(sdk::COREWEBVIEW2_PROCESS_FAILED_REASON_CRASHED.0, 3);
        assert_eq!(sdk::COREWEBVIEW2_PROCESS_FAILED_REASON_TERMINATED.0, 2);
    }

    #[test]
    fn los_nombres_del_registro_cubren_los_valores_del_sdk() {
        assert_eq!(nombre_del_proceso(PROCESO_PAGINA), "pagina");
        assert_eq!(nombre_del_proceso(PROCESO_GPU), "gpu");
        assert_eq!(nombre_del_motivo(5), "sin_memoria");
        assert_eq!(nombre_del_motivo(3), "fallo");
    }
}
