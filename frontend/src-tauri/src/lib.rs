mod backend;
mod cases;
mod downloader;

use std::path::PathBuf;
use std::{fs::OpenOptions, io::Write};
use tauri::Manager;

use backend::{
    current_status, ensure_backend_sync, reset_for_retry, shutdown_for_app_exit, BackendStatus,
};
use cases::{
    case_create, case_forget, case_initialize, case_list_authorized, case_open_token,
    case_pick_directory, case_pick_parent_directory, case_read, case_registry_health,
    case_relocate, case_repair, case_reveal, case_write, CaseRegistry,
};
use downloader::{
    cancel_download, download_model, extract_archive, file_exists, get_resource_dir, verify_model,
    DownloadState,
};

/// Traza mínima de bootstrap para diagnosticar instalaciones donde la ventana
/// termina antes de que el plugin de logs alcance a inicializarse.
fn bootstrap_log(message: &str) {
    let path = std::env::var_os("MOLDESIGN_BOOT_LOG")
        .map(PathBuf::from)
        .unwrap_or_else(|| std::env::temp_dir().join("moldesign-desktop-bootstrap.log"));
    if let Some(parent) = path.parent() {
        let _ = std::fs::create_dir_all(parent);
    }
    if let Ok(mut file) = OpenOptions::new().create(true).append(true).open(path) {
        let _ = writeln!(file, "{} {}", chrono::Local::now().to_rfc3339(), message);
    }
}

/// Carpeta de recursos INSTALADA, si la hay.
///
/// Sólo importa en producción. En `debug` la resolución del runtime ni la mira
/// —ver `backend::resolve_layout`—, que es lo que impide volver a ejecutar la
/// copia caducada de `target/debug`.
fn resolve_resource_dir(app: &tauri::AppHandle) -> Option<PathBuf> {
    if let Ok(dir) = app.path().resource_dir() {
        if dir.join("python").join("python.exe").exists() {
            log::info!("Carpeta de recursos: {}", dir.display());
            return Some(dir);
        }
    }
    if let Ok(exe) = std::env::current_exe() {
        if let Some(parent) = exe.parent() {
            if parent.join("python").join("python.exe").exists() {
                return Some(parent.to_path_buf());
            }
            let candidate = parent.join("resources");
            if candidate.join("python").join("python.exe").exists() {
                return Some(candidate);
            }
        }
    }
    None
}

/// `true` si el proceso corre con identidad de paquete MSIX/AppX.
///
/// Bajo identidad de paquete, `dirs::data_dir()`/`app_data_dir()` devuelven la
/// ruta lógica pero las escrituras aterrizan en `LocalCache` (y se borran al
/// desinstalar). Para el índice de casos y las descargas de modelos se usa esta
/// señal para elegir un destino no-virtualizado que sobreviva a la
/// desinstalación.
#[cfg(windows)]
pub(crate) fn is_packaged_app() -> bool {
    use windows_sys::Win32::Storage::Packaging::Appx::GetCurrentPackageFullName;
    let mut len: u32 = 0;
    // Con un buffer nulo, si HAY identidad de paquete la API devuelve
    // ERROR_INSUFFICIENT_BUFFER (122) y escribe la longitud requerida; si NO la
    // hay, devuelve APPMODEL_ERROR_NO_PACKAGE (15700).
    let rc = unsafe { GetCurrentPackageFullName(&mut len, std::ptr::null_mut()) };
    // 122 == ERROR_INSUFFICIENT_BUFFER
    rc == 122 && len > 0
}

#[cfg(not(windows))]
pub(crate) fn is_packaged_app() -> bool {
    false
}

/// Directorio de datos persistente y no-virtualizado de MolDesign, para estado
/// que debe sobrevivir a desinstalar (índice de casos, modelos descargados).
pub(crate) fn persistent_data_dir(app: &tauri::AppHandle) -> Option<PathBuf> {
    app.path().home_dir().ok().map(|d| d.join("MolDesign"))
}

/// Autotest instalado del registro de casos (gate empaquetado).
///
/// Se activa SÓLO cuando existe un centinela en el perfil del usuario
/// (`~/.moldesign-case-self-test.json`), que escribe el gate externo ANTES de
/// lanzar la app por su activación de paquete normal. Un centinela en archivo
/// evita depender de variables de entorno, que la activación de un paquete MSIX
/// no propaga de forma fiable. Ejerce el MISMO núcleo que `case_create` y
/// `case_read` contra el `app_data_dir` real del paquete, escribe la evidencia
/// donde el centinela indique y se consume (borra el centinela). En operación
/// normal no hay centinela y no hace nada.
fn run_case_self_test(app: &tauri::AppHandle) {
    let Ok(home) = app.path().home_dir() else {
        return;
    };
    let req_path = home.join(".moldesign-case-self-test.json");
    let Ok(body) = std::fs::read_to_string(&req_path) else {
        return;
    };
    let Ok(req) = serde_json::from_str::<serde_json::Value>(&body) else {
        // Centinela corrupto: se consume y se sigue como arranque normal.
        let _ = std::fs::remove_file(&req_path);
        return;
    };

    let mode = req
        .get("mode")
        .and_then(|v| v.as_str())
        .unwrap_or("")
        .to_string();
    let evidence = req
        .get("evidence")
        .and_then(|v| v.as_str())
        .map(PathBuf::from)
        .unwrap_or_else(|| home.join(".moldesign-case-self-test-evidence.json"));

    let registry_path = cases::registry_path(app);

    let result = match mode.as_str() {
        "create" => match req
            .get("parent")
            .and_then(|v| v.as_str())
            .map(PathBuf::from)
        {
            None => serde_json::json!({"ok": false, "mode": "create", "error": "falta `parent`"}),
            Some(parent) => {
                let folder = req
                    .get("folder")
                    .and_then(|v| v.as_str())
                    .unwrap_or("acceptance-case");
                let owner = req
                    .get("owner")
                    .and_then(|v| v.as_str())
                    .unwrap_or("self-test-owner");
                match cases::self_test_create_case(
                    &parent,
                    folder,
                    "Caso de aceptación",
                    "explore-hypothesis",
                    owner,
                ) {
                    Ok((id, case_dir, _manifest)) => {
                        let reg = app.state::<CaseRegistry>();
                        match reg.register(&id, case_dir.clone()) {
                            Ok(()) => serde_json::json!({
                                "ok": true,
                                "mode": "create",
                                "case_id": id,
                                "case_dir": case_dir.display().to_string(),
                                "registry_path": registry_path.map(|p| p.display().to_string()),
                                "health": format!("{:?}", reg.health()),
                            }),
                            Err(e) => {
                                serde_json::json!({"ok": false, "mode": "create", "error": e})
                            }
                        }
                    }
                    Err(e) => serde_json::json!({"ok": false, "mode": "create", "error": e}),
                }
            }
        },
        "verify" => {
            let case_id = req.get("case_id").and_then(|v| v.as_str()).unwrap_or("");
            let expected_dir = req.get("case_dir").and_then(|v| v.as_str()).unwrap_or("");
            let reg = app.state::<CaseRegistry>();
            match reg.resolve_case(case_id) {
                Ok(dir) => {
                    let readable = cases::read_manifest_with_recovery(&dir, Some(case_id))
                        .map(|(text, _)| cases::manifest_id(&text).as_deref() == Ok(case_id))
                        .unwrap_or(false);
                    serde_json::json!({
                        "ok": readable,
                        "mode": "verify",
                        "case_id": case_id,
                        "resolved_dir": dir.display().to_string(),
                        "expected_dir": expected_dir,
                        "manifest_readable": readable,
                    })
                }
                Err(e) => {
                    serde_json::json!({"ok": false, "mode": "verify", "case_id": case_id, "error": e})
                }
            }
        }
        other => serde_json::json!({"ok": false, "mode": other, "error": "modo desconocido"}),
    };

    if let Some(parent) = evidence.parent() {
        let _ = std::fs::create_dir_all(parent);
    }
    let ok = result.get("ok").and_then(|v| v.as_bool()).unwrap_or(false);
    let _ = std::fs::write(
        &evidence,
        serde_json::to_string_pretty(&result).unwrap_or_default(),
    );
    let _ = std::fs::remove_file(&req_path); // el centinela se consume
    bootstrap_log(&format!("case_self_test:{mode}:ok={ok}"));
    std::process::exit(if ok { 0 } else { 1 });
}

/// Arranca el motor si hace falta y devuelve su estado.
///
/// Es IDEMPOTENTE: el `setup` de Rust lo llama al abrir y el frontend lo llama
/// otra vez al montar. La exclusión mutua vive en `backend::ensure_backend_sync`,
/// así que las dos llamadas comparten un único proceso.
#[tauri::command]
async fn ensure_backend(app: tauri::AppHandle) -> Result<BackendStatus, String> {
    let resource_dir = resolve_resource_dir(&app);
    tokio::task::spawn_blocking(move || ensure_backend_sync(resource_dir))
        .await
        .map_err(|e| format!("El arranque del motor no se pudo ejecutar: {}", e))
}

/// Estado actual SIN arrancar nada. Barato: la interfaz puede preguntarlo.
#[tauri::command]
fn backend_status() -> BackendStatus {
    current_status()
}

/// Reintento explícito: cierra el proceso propio y vuelve a arrancar.
///
/// Cierra ANTES de reintentar porque un motor a medias —lanzado pero sin pasar
/// el probe— seguiría vivo ocupando su puerto, y el intento siguiente elegiría
/// otro dejando un huérfano detrás.
#[tauri::command]
async fn restart_backend(app: tauri::AppHandle) -> Result<BackendStatus, String> {
    let resource_dir = resolve_resource_dir(&app);
    tokio::task::spawn_blocking(move || {
        reset_for_retry();
        ensure_backend_sync(resource_dir)
    })
    .await
    .map_err(|e| format!("El reintento del motor no se pudo ejecutar: {}", e))
}

/// Permite a WebView2 dibujar WebGL por software cuando no hay GPU.
///
/// EL PROBLEMA. Chromium desactivó SwiftShader para WebGL por omisión: en una
/// máquina sin GPU virtualizada —que es exactamente la del revisor de la Store
/// y la de cualquier VM de pruebas— `canvas.getContext("webgl")` devuelve
/// `null` y el visor molecular no puede existir.
///
/// LO QUE ESTO HACE Y LO QUE NO. No fuerza el render por software: sólo
/// autoriza el repliegue cuando no hay otra cosa. Un equipo con tarjeta gráfica
/// sigue usándola y no pierde un fotograma; medido, Mol* arranca en 1 072 ms
/// con hardware y en 1 260 ms con SwiftShader, así que el repliegue es
/// utilizable, no un consuelo.
///
/// POR QUÉ SE PUEDE. La bandera se llama «unsafe» porque un rasterizador por
/// software amplía la superficie de ataque frente a contenido web hostil. Aquí
/// no hay contenido web hostil: la política de contenido de esta aplicación
/// sólo admite su propio origen, y lo que se dibuja son las estructuras que el
/// usuario ya tiene en su disco.
///
/// NO pisa lo que ya hubiera puesto quien lanza la aplicación: se añade.
#[cfg(target_os = "windows")]
fn permitir_webgl_por_software() {
    const BANDERA: &str = "--enable-unsafe-swiftshader";
    const VARIABLE: &str = "WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS";

    let previo = std::env::var(VARIABLE).unwrap_or_default();
    if previo.contains(BANDERA) {
        return;
    }
    let valor = if previo.trim().is_empty() {
        BANDERA.to_string()
    } else {
        format!("{} {}", previo.trim(), BANDERA)
    };
    // SAFETY: se ejecuta antes de crear la webview y antes de arrancar ningún
    // hilo propio, así que no hay lectura concurrente del entorno.
    unsafe { std::env::set_var(VARIABLE, &valor) };
    bootstrap_log(&format!("webgl:software-permitido {}", valor));
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    bootstrap_log("run:start");
    std::panic::set_hook(Box::new(|info| {
        let msg = format!("PANIC IN MOLDESIGN: {}\n", info);
        let _ = std::fs::write(std::env::temp_dir().join("moldesign_crash.txt"), &msg);
    }));

    // Antes de que exista la webview: después, la variable ya no se lee.
    #[cfg(target_os = "windows")]
    permitir_webgl_por_software();

    let builder = tauri::Builder::default();

    // En desarrollo se permiten instancias independientes. El watcher de
    // Tauri reinicia procesos y una instancia de depuración anterior puede
    // seguir registrada unos instantes; tratar la nueva como «segunda» hace
    // que `npx tauri dev` parezca cerrarse sin error. El instalador sí conserva
    // la protección de una sola instancia.
    #[cfg(not(debug_assertions))]
    let builder = builder
        // ── Una sola instancia ───────────────────────────────────
        //
        // Sin esto, un segundo doble clic en el icono abria OTRA ventana con
        // SU PROPIO backend. Los dos convivian: puertos 8000 y 8001, dos
        // juegos de modelos cientificos en memoria (~1 GB cada uno) y dos
        // motores escribiendo la misma base. SQLite en WAL lo aguanta —los
        // escritores se serializan con `busy_timeout`— asi que no corrompia
        // datos, pero el usuario acababa con dos ventanas identicas sin saber
        // cual estaba mirando.
        //
        // El segundo proceso NO abre ventana: enfoca la que ya existe y sale.
        // Es lo que el usuario queria al hacer doble clic.
        .plugin(tauri_plugin_single_instance::init(|app, _args, _cwd| {
            bootstrap_log("single_instance:segunda_instancia");
            if let Some(window) = app.get_webview_window("main") {
                // Si estaba minimizada, restaurar antes de enfocar: `set_focus`
                // sobre una ventana minimizada no la trae de vuelta.
                let _ = window.unminimize();
                let _ = window.show();
                let _ = window.set_focus();
            }
        }));

    builder
        .plugin(tauri_plugin_shell::init())
        // Abre URLs en el navegador del sistema. Sin esto, `<a target="_blank">`
        // dentro del webview no hace nada y el clic se pierde sin error: era el
        // motivo de que NINGUN enlace externo funcionase en la app instalada.
        // La capability concede solo `opener:allow-open-url`.
        .plugin(tauri_plugin_opener::init())
        // Selector nativo de carpetas. Solo se usa para elegir DONDE crear o
        // abrir un caso; la capability concede unicamente `dialog:allow-open`.
        .plugin(tauri_plugin_dialog::init())
        .manage(DownloadState {
            cancel_flags: tokio::sync::Mutex::new(std::collections::HashMap::new()),
        })
        .invoke_handler(tauri::generate_handler![
            ensure_backend,
            backend_status,
            restart_backend,
            download_model,
            cancel_download,
            verify_model,
            file_exists,
            get_resource_dir,
            extract_archive,
            case_pick_directory,
            case_pick_parent_directory,
            case_repair,
            case_registry_health,
            case_relocate,
            case_create,
            case_initialize,
            case_open_token,
            case_read,
            case_write,
            case_list_authorized,
            case_forget,
            case_reveal,
        ])
        .setup(|app| {
            bootstrap_log("setup:start");
            // Los recursos instalados no son un directorio de datos. Publicar
            // la ruta writable de Tauri antes de arrancar el backend mantiene
            // logs y punteros de diagnóstico fuera del payload firmado.
            if let Ok(log_dir) = app.path().app_log_dir() {
                let _ = std::fs::create_dir_all(&log_dir);
                // Un override explícito se conserva: permite diagnosticar una
                // máquina donde la carpeta estándar no sea legible. Sin
                // override, el instalador escribe junto al resto de logs.
                if std::env::var_os("MOLDESIGN_BOOT_LOG").is_none() {
                    let boot_path = log_dir.join("desktop-bootstrap.log");
                    std::env::set_var("MOLDESIGN_BOOT_LOG", &boot_path);
                }
                bootstrap_log(&format!("setup:app_log_dir={}", log_dir.display()));
                std::env::set_var("MOLDESIGN_LOG_DIR", log_dir);
            }

            // El registro de casos autorizados se carga aqui porque necesita el
            // AppHandle para localizar app data. Sin persistencia, cada
            // reinicio obligaria a volver a elegir la carpeta de cada caso.
            app.manage(CaseRegistry::load(app.handle()));

            // Autotest instalado del registro de casos: inerte sin la variable
            // de entorno. Ver `run_case_self_test`.
            run_case_self_test(app.handle());

            if let Err(e) = app.handle().plugin(
                tauri_plugin_log::Builder::default()
                    // `tauri-plugin-log` incluye stdout por defecto. En el
                    // ejecutable Windows de release no existe una consola
                    // estable; si el pipe heredado se cierra, `fern` intenta
                    // informar el error por stderr y puede entrar en pánico.
                    // El archivo rotativo es el destino canónico del desktop.
                    .clear_targets()
                    .target(tauri_plugin_log::Target::new(
                        tauri_plugin_log::TargetKind::LogDir { file_name: None },
                    ))
                    .level(log::LevelFilter::Info)
                    .build(),
            ) {
                log::error!("Log plugin init failed (non-fatal): {}", e);
            }

            // ── El motor arranca CON la aplicación ──────────────────
            //
            // Antes el único que pedía el backend era `DownloadProvider`, desde
            // React. Quien no llegara a esa pantalla no tenía motor, y el
            // arranque quedaba a merced de que un componente se montara. Aquí
            // se lanza en un hilo aparte para no bloquear la ventana: el probe
            // de salud puede tardar decenas de segundos en un arranque frío.
            let bootstrap_handle = app.handle().clone();
            std::thread::spawn(move || {
                bootstrap_log("backend_thread:start");
                let resource_dir = resolve_resource_dir(&bootstrap_handle);
                bootstrap_log(&format!(
                    "backend_thread:resource_dir={}",
                    resource_dir
                        .as_deref()
                        .map(|path| path.display().to_string())
                        .unwrap_or_else(|| "<none>".to_string())
                ));
                let status = ensure_backend_sync(resource_dir);
                bootstrap_log(&format!("backend_thread:status={:?}", status.state));
                log::info!("Arranque automático del motor: {:?}", status.state);
            });

            // Al cerrar se termina EL PROCESO PROPIO, y sólo ese.
            if let Some(w) = app.get_webview_window("main") {
                w.on_window_event(|event| match event {
                    tauri::WindowEvent::CloseRequested { .. } => {
                        bootstrap_log("window_event:close_requested");
                    }
                    tauri::WindowEvent::Destroyed => {
                        bootstrap_log("window_event:destroyed");
                        shutdown_for_app_exit();
                    }
                    _ => {}
                });
            }

            Ok(())
        })
        .run(tauri::generate_context!())
        .unwrap_or_else(|e| {
            bootstrap_log(&format!("run:error={e}"));
            log::error!("Fatal: tauri runtime failed: {}", e);
            std::process::exit(1);
        });
    bootstrap_log("run:return_ok");
}
