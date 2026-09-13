//! Propiedad del proceso backend en escritorio.
//!
//! # El fallo que arregla este módulo
//!
//! `npx tauri dev` arrancaba Next.js y el backend nunca quedaba disponible. La
//! causa no era el arranque: era **qué** se arrancaba.
//!
//! La resolución del runtime buscaba `<dir>/python/python.exe` empezando por
//! `resource_dir()`, que en `debug` es `src-tauri/target/debug/`. Ahí había una
//! copia histórica del backend —de julio— que un build antiguo dejó. Rust
//! lanzaba **esa** copia, que contestaba `/health` con HTTP 200 pero sin los
//! campos `app` y `version` del contrato actual. El probe la rechazaba
//! semánticamente una y otra vez, agotaba los 30 s y mataba al hijo. Desde
//! fuera parecía «el backend no arranca»; en realidad arrancaba el equivocado.
//!
//! `target/` es salida de compilación. Nunca puede ser la fuente de verdad de
//! qué código se ejecuta.
//!
//! # Cómo se resuelve
//!
//! Dos disposiciones EXPLÍCITAS, no una función que suponga que desarrollo y
//! producción comparten estructura:
//!
//! ```text
//!   desarrollo (debug)            producción (bundle/instalado)
//!   <repo>/backend                <resources>/backend
//!   <repo>/python-embed/python.exe <resources>/python/python.exe
//!   <repo>/tools/vina/vina.exe    <resources>/tools/vina/vina.exe
//!   <repo>/tools/openbabel/       <resources>/tools/openbabel/
//! ```
//!
//! Cada una valida sus rutas ANTES de lanzar nada y dice exactamente qué falta.
//!
//! # Un solo dueño
//!
//! Tauri es el dueño del proceso. Lo arranca una vez, conserva el `Child` real
//! y al cerrar mata **ese** proceso y sólo ese. Nunca se mata a nadie por
//! ocupar un puerto: si 8000 está tomado por algo ajeno, se busca otro puerto
//! libre del rango y se deja en paz al vecino.

use std::net::TcpListener;
use std::path::{Path, PathBuf};
use std::process::Command as StdCommand;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Mutex, OnceLock};

use serde::Serialize;

#[cfg(target_os = "windows")]
use std::os::windows::io::AsRawHandle;
#[cfg(target_os = "windows")]
use std::os::windows::process::CommandExt;
#[cfg(target_os = "windows")]
use windows_sys::Win32::Foundation::CloseHandle;
#[cfg(target_os = "windows")]
use windows_sys::Win32::System::JobObjects::{
    AssignProcessToJobObject, CreateJobObjectW, JobObjectExtendedLimitInformation,
    SetInformationJobObject, JOBOBJECT_EXTENDED_LIMIT_INFORMATION,
    JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE,
};

pub const PORT_RANGE_START: u16 = 8000;
pub const PORT_RANGE_END: u16 = 8020;

// Presupuesto del probe de salud. Un arranque frío comparte CPU y disco con la
// compilación de Next y la carga inicial de RDKit/ML; en la máquina de prueba
// se midieron más de 30 s antes del primer byte de log. El estado `Starting`
// mantiene informada a la interfaz, así que esperar hasta 90 s es preferible a
// matar un proceso sano a mitad de su importación.
const HEALTH_CHECK_TIMEOUT_SECS: u64 = 90;
const HEALTH_REQUEST_TIMEOUT_SECS: u64 = 2;
const HEALTH_PROBE_INTERVAL_MS: u64 = 500;

// ── Estado observable ────────────────────────────────────────────────

/// Fase del motor, tal como la ve la interfaz.
///
/// Son estados DISTINGUIBLES a propósito. Antes todo fallo acababa siendo «no
/// hay modelos», que es un diagnóstico falso cuando lo que pasó es que el
/// proceso no arrancó o que contestó algo que no es MolDesign.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum BackendPhase {
    /// Todavía no se ha intentado.
    Idle,
    /// Arrancando o esperando a que conteste `/health`.
    Starting,
    /// Vivo y con identidad verificada.
    Ready,
    /// Falta el runtime en disco (Python, backend o Vina). No es un fallo de
    /// arranque: no hay nada que arrancar.
    NotInstalled,
    /// El proceso no se pudo lanzar (permisos, ejecutable ilegible, sin puerto).
    SpawnFailed,
    /// El proceso arrancó pero `/health` nunca pasó la validación.
    HealthFailed,
}

#[derive(Debug, Clone, Serialize)]
pub struct BackendStatus {
    pub state: BackendPhase,
    pub port: Option<u16>,
    /// Razón exacta del último fallo. Sin secretos: rutas y campos, no tokens.
    pub detail: Option<String>,
}

impl BackendStatus {
    pub fn idle() -> Self {
        Self {
            state: BackendPhase::Idle,
            port: None,
            detail: None,
        }
    }
    pub fn ready(port: u16) -> Self {
        Self {
            state: BackendPhase::Ready,
            port: Some(port),
            detail: None,
        }
    }
    pub fn failed(state: BackendPhase, detail: String) -> Self {
        Self {
            state,
            port: None,
            detail: Some(detail),
        }
    }
}

/// `true` si hace falta arrancar. Un motor `Ready` no se vuelve a arrancar.
///
/// Es la mitad barata de la idempotencia: la otra mitad es el cerrojo de
/// arranque, que serializa a dos llamantes que lleguen a la vez.
pub fn needs_bootstrap(current: &BackendStatus) -> bool {
    !matches!(current.state, BackendPhase::Ready | BackendPhase::Starting)
}

fn status_slot() -> &'static Mutex<BackendStatus> {
    static SLOT: OnceLock<Mutex<BackendStatus>> = OnceLock::new();
    SLOT.get_or_init(|| Mutex::new(BackendStatus::idle()))
}

/// Cerrojo de ARRANQUE, distinto del cerrojo de estado.
///
/// Separarlos es lo que permite que `backend_status` conteste al instante
/// mientras otra llamada está dentro de los 30 s del probe de salud. Con un
/// solo mutex, consultar el estado se habría quedado esperando al arranque.
fn bootstrap_lock() -> &'static Mutex<()> {
    static LOCK: OnceLock<Mutex<()>> = OnceLock::new();
    LOCK.get_or_init(|| Mutex::new(()))
}

/// Proceso propio y, en Windows, el Job Object que lo ata a la vida de Tauri.
///
/// `Child::drop` NO termina al hijo. El Job Object sí: incluso si `Ctrl+C`
/// aborta el ejecutable antes de que llegue `WindowEvent::Destroyed`, Windows
/// cierra el handle del job y termina Python y sus descendientes.
struct OwnedBackend {
    child: std::process::Child,
    #[cfg(target_os = "windows")]
    job_handle: isize,
}

impl OwnedBackend {
    fn id(&self) -> u32 {
        self.child.id()
    }

    fn kill(&mut self) -> std::io::Result<()> {
        self.child.kill()
    }

    fn wait(&mut self) -> std::io::Result<std::process::ExitStatus> {
        self.child.wait()
    }
}

#[cfg(target_os = "windows")]
impl Drop for OwnedBackend {
    fn drop(&mut self) {
        if self.job_handle != 0 {
            // SAFETY: `job_handle` viene de CreateJobObjectW, pertenece a esta
            // estructura y se cierra exactamente una vez en Drop.
            unsafe { CloseHandle(self.job_handle as _) };
            self.job_handle = 0;
        }
    }
}

fn child_slot() -> &'static Mutex<Option<OwnedBackend>> {
    static CHILD: OnceLock<Mutex<Option<OwnedBackend>>> = OnceLock::new();
    CHILD.get_or_init(|| Mutex::new(None))
}

/// Señal de cierre FINAL de la aplicación.
///
/// Es distinta de un reintento: durante `restart_backend` sí se permite crear
/// otro hijo. Al destruir la ventana, en cambio, cualquier `spawn()` que esté
/// cruzando el hueco entre crear el proceso y guardarlo debe abortar y matarlo.
fn app_shutdown_requested() -> &'static AtomicBool {
    static REQUESTED: AtomicBool = AtomicBool::new(false);
    &REQUESTED
}

fn terminate_owned_child() {
    let mut guard = match child_slot().lock() {
        Ok(guard) => guard,
        Err(poisoned) => poisoned.into_inner(),
    };
    if let Some(mut child) = guard.take() {
        log::info!("Cerrando el backend propio (pid {})", child.id());
        let _ = child.kill();
        let _ = child.wait();
    }
}

/// Lee el estado sin bloquearse con el arranque. Un mutex envenenado no puede
/// dejar la aplicación sin diagnóstico: se recupera el valor de dentro.
pub fn current_status() -> BackendStatus {
    match status_slot().lock() {
        Ok(guard) => guard.clone(),
        Err(poisoned) => poisoned.into_inner().clone(),
    }
}

fn set_status(next: BackendStatus) {
    match status_slot().lock() {
        Ok(mut guard) => *guard = next,
        Err(poisoned) => *poisoned.into_inner() = next,
    }
}

// ── Disposición del runtime ──────────────────────────────────────────

/// Dónde está cada pieza del motor. Se resuelve ENTERA antes de lanzar nada.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct RuntimeLayout {
    pub python_exe: PathBuf,
    pub backend_dir: PathBuf,
    pub vina_exe: PathBuf,
    /// Open Babel, programa independiente GPL-2.0-only que se invoca como
    /// herramienta de línea de órdenes. Se exige igual que Vina: viaja en el
    /// instalador, así que su ausencia es una instalación dañada y no una
    /// función opcional. Ver `docs/79_ADR_FRONTERA_OPEN_BABEL.md`.
    pub openbabel_dir: PathBuf,
    /// Dónde se escriben los logs del backend.
    pub log_dir: PathBuf,
    /// Para el log: de qué árbol salió esto.
    pub kind: &'static str,
}

#[cfg(target_os = "windows")]
const PYTHON_BIN: &str = "python.exe";
#[cfg(not(target_os = "windows"))]
const PYTHON_BIN: &str = "python";

#[cfg(target_os = "windows")]
const VINA_BIN: &str = "vina.exe";
#[cfg(not(target_os = "windows"))]
const VINA_BIN: &str = "vina";

#[cfg(target_os = "windows")]
const OBABEL_BIN: &str = "obabel.exe";
#[cfg(not(target_os = "windows"))]
const OBABEL_BIN: &str = "obabel";

fn require(path: PathBuf, what: &str, missing: &mut Vec<String>) -> PathBuf {
    if !path.exists() {
        missing.push(format!("{what} ({})", path.display()));
    }
    path
}

/// Árbol VIVO del repositorio. Es lo que debe ejecutarse en `debug`.
///
/// Exige `backend/api/main.py`, no sólo `backend/`: una carpeta vacía con el
/// nombre correcto pasaría la comprobación y el fallo aparecería después, al
/// arrancar uvicorn, con un mensaje mucho peor.
pub fn dev_layout(repo_root: &Path) -> Result<RuntimeLayout, String> {
    let mut missing = Vec::new();
    let python_exe = require(
        repo_root.join("python-embed").join(PYTHON_BIN),
        "Python de desarrollo",
        &mut missing,
    );
    let backend_dir = repo_root.join("backend");
    require(
        backend_dir.join("api").join("main.py"),
        "backend/api/main.py",
        &mut missing,
    );
    let vina_exe = require(
        repo_root.join("tools").join("vina").join(VINA_BIN),
        "Vina",
        &mut missing,
    );
    let openbabel_dir = repo_root.join("tools").join("openbabel");
    require(
        openbabel_dir.join("bin").join(OBABEL_BIN),
        "Open Babel (ejecuta `python scripts/stage_openbabel_tool.py`)",
        &mut missing,
    );
    if !missing.is_empty() {
        return Err(format!(
            "El árbol de desarrollo en {} no está completo: falta {}.",
            repo_root.display(),
            missing.join("; ")
        ));
    }
    Ok(RuntimeLayout {
        python_exe,
        backend_dir,
        vina_exe,
        openbabel_dir,
        log_dir: repo_root.join("logs"),
        kind: "desarrollo (árbol vivo del repositorio)",
    })
}

/// Runtime EMPAQUETADO junto al ejecutable instalado.
fn bundled_layout_with_log_dir(
    resource_dir: &Path,
    log_dir: PathBuf,
) -> Result<RuntimeLayout, String> {
    let mut missing = Vec::new();
    let python_exe = require(
        resource_dir.join("python").join(PYTHON_BIN),
        "Python empaquetado",
        &mut missing,
    );
    let backend_dir = resource_dir.join("backend");
    require(
        backend_dir.join("api").join("main.py"),
        "backend/api/main.py",
        &mut missing,
    );
    let vina_exe = require(
        resource_dir.join("tools").join("vina").join(VINA_BIN),
        "Vina",
        &mut missing,
    );
    let openbabel_dir = resource_dir.join("tools").join("openbabel");
    require(
        openbabel_dir.join("bin").join(OBABEL_BIN),
        "Open Babel",
        &mut missing,
    );
    if !missing.is_empty() {
        return Err(format!(
            "El motor no está instalado en {}: falta {}.",
            resource_dir.display(),
            missing.join("; ")
        ));
    }
    Ok(RuntimeLayout {
        python_exe,
        backend_dir,
        vina_exe,
        openbabel_dir,
        log_dir,
        kind: "instalado (recursos empaquetados)",
    })
}

/// En una instalación los recursos son de sólo lectura. Los logs viven en el
/// directorio de aplicación que Tauri publica durante `setup`; si por alguna
/// razón no estuviera disponible, se degrada a una carpeta temporal y nunca a
/// la raíz instalada.
fn bundled_log_dir() -> PathBuf {
    std::env::var_os("MOLDESIGN_LOG_DIR")
        .filter(|value| !value.is_empty())
        .map(PathBuf::from)
        .unwrap_or_else(|| std::env::temp_dir().join("MolDesign").join("logs"))
}

pub fn bundled_layout(resource_dir: &Path) -> Result<RuntimeLayout, String> {
    bundled_layout_with_log_dir(resource_dir, bundled_log_dir())
}

/// Raíz del repositorio en compilaciones de desarrollo.
///
/// Sale de `CARGO_MANIFEST_DIR`, que apunta a `frontend/src-tauri`, y NO de
/// `current_exe()`: el ejecutable vive en `target/debug`, que es exactamente el
/// sitio del que hay que dejar de leer. `MOLDESIGN_DEV_ROOT` permite apuntar a
/// otro árbol sin recompilar.
pub fn dev_repo_root() -> Option<PathBuf> {
    if let Ok(from_env) = std::env::var("MOLDESIGN_DEV_ROOT") {
        if !from_env.trim().is_empty() {
            return Some(PathBuf::from(from_env));
        }
    }
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .parent() // frontend/
        .and_then(|p| p.parent()) // raíz del repositorio
        .map(Path::to_path_buf)
}

/// Elige la disposición según el perfil de compilación.
///
/// En `debug` se usa el árbol vivo y **no** se cae a los recursos: caer sería
/// volver a ejecutar la copia de `target/debug` sin que nadie se entere, que es
/// el fallo original. Si el árbol vivo no está completo, se dice.
pub fn resolve_layout(resource_dir: Option<&Path>) -> Result<RuntimeLayout, String> {
    if cfg!(debug_assertions) {
        let root = dev_repo_root()
            .ok_or_else(|| "No se pudo localizar la raíz del repositorio.".to_string())?;
        return dev_layout(&root);
    }
    let dir = resource_dir
        .ok_or_else(|| "No se pudo localizar la carpeta de recursos instalada.".to_string())?;
    bundled_layout(dir)
}

// ── Salud ────────────────────────────────────────────────────────────

pub enum HealthState {
    Healthy,
    Degraded(String),
    Unhealthy(String),
}

/// Resume la respuesta para el log SIN volcarla entera ni filtrar nada.
///
/// Es lo que faltaba para diagnosticar el fallo original: el rechazo decía «no
/// es JSON de MolDesign» sin enseñar qué había contestado el proceso, así que
/// no se distinguía «hay otro servidor en el puerto» de «es MolDesign pero de
/// una versión anterior al contrato».
pub fn describe_health_body(body: &serde_json::Value) -> String {
    let field = |key: &str| {
        body.get(key)
            .and_then(|v| v.as_str())
            .unwrap_or("<ausente>")
            .to_string()
    };
    let db = body
        .pointer("/components/database/status")
        .and_then(|v| v.as_str())
        .unwrap_or("<ausente>");
    format!(
        "app={} version={} app_mode={} status={} database={}",
        field("app"),
        field("version"),
        field("app_mode"),
        field("status"),
        db
    )
}

/// Validación SEMÁNTICA. Un HTTP 200 no basta y no se va a debilitar.
///
/// El proceso que conteste en nuestro puerto tiene que declarar que es
/// MolDesign, en modo escritorio, con versión y con SQLite sano. Aceptar
/// cualquier 200 habría dado por bueno justo el backend caducado de
/// `target/debug`, que es de donde salió este módulo.
pub fn validate_health_body(body: &serde_json::Value) -> HealthState {
    let summary = describe_health_body(body);
    let app_ok = body.get("app").and_then(|v| v.as_str()) == Some("mol-design");
    let version_ok = body
        .get("version")
        .and_then(|v| v.as_str())
        .map(|s| !s.trim().is_empty())
        .unwrap_or(false);
    let mode_ok = body.get("app_mode").and_then(|v| v.as_str()) == Some("DESKTOP");
    let db_ok = body
        .pointer("/components/database/status")
        .and_then(|v| v.as_str())
        == Some("healthy");

    if !app_ok {
        return HealthState::Unhealthy(format!(
            "la respuesta no se identifica como MolDesign (falta `app`) [{summary}]"
        ));
    }
    if !version_ok {
        return HealthState::Unhealthy(format!(
            "la respuesta no declara versión de la aplicación [{summary}]"
        ));
    }
    if !mode_ok {
        return HealthState::Unhealthy(format!(
            "la respuesta no declara `app_mode` DESKTOP [{summary}]"
        ));
    }
    if !db_ok {
        return HealthState::Unhealthy(format!(
            "el componente de base de datos no está sano (SQLite) [{summary}]"
        ));
    }

    match body.get("status").and_then(|v| v.as_str()) {
        Some("healthy") => HealthState::Healthy,
        Some("degraded") => {
            HealthState::Degraded(format!("el backend se declara degradado [{summary}]"))
        }
        Some(other) => {
            HealthState::Unhealthy(format!("estado de salud inesperado: {other} [{summary}]"))
        }
        None => HealthState::Unhealthy(format!("la respuesta no declara `status` [{summary}]")),
    }
}

fn wait_for_healthy_backend(port: u16, timeout_secs: u64) -> Result<(), String> {
    let url = format!("http://127.0.0.1:{}/health", port);
    let client = reqwest::blocking::Client::builder()
        .timeout(std::time::Duration::from_secs(HEALTH_REQUEST_TIMEOUT_SECS))
        .build()
        .map_err(|e| format!("no se pudo crear el cliente del probe: {}", e))?;

    let deadline = std::time::Instant::now() + std::time::Duration::from_secs(timeout_secs);
    // Sin valor inicial: todas las ramas del bucle escriben la razón antes de
    // llegar a la comprobación del plazo, así que un valor de relleno sólo
    // podría acabar en el mensaje de error tapando la causa verdadera.
    let mut last_error: String;

    loop {
        match client.get(url.as_str()).send() {
            Ok(resp) => {
                let http_status = resp.status().as_u16();
                match resp.json::<serde_json::Value>() {
                    Ok(body) => match validate_health_body(&body) {
                        HealthState::Healthy => return Ok(()),
                        HealthState::Degraded(reason) => {
                            // Vivo, con algún componente no crítico caído (por
                            // ejemplo Vina ausente). Se acepta y se avisa.
                            log::warn!("Backend vivo pero degradado: {}", reason);
                            return Ok(());
                        }
                        HealthState::Unhealthy(reason) => {
                            last_error = reason;
                            log::warn!("Probe de salud rechazó la respuesta: {}", last_error);
                        }
                    },
                    Err(e) => {
                        last_error = format!(
                            "la respuesta de salud no es JSON (http {}): {}",
                            http_status, e
                        );
                    }
                }
            }
            Err(e) => {
                last_error = format!("el probe de salud falló: {}", e);
            }
        }
        if std::time::Instant::now() >= deadline {
            return Err(format!(
                "el backend no llegó a estar sano en el puerto {} en {}s (último: {})",
                port, timeout_secs, last_error
            ));
        }
        std::thread::sleep(std::time::Duration::from_millis(HEALTH_PROBE_INTERVAL_MS));
    }
}

// ── Arranque ─────────────────────────────────────────────────────────

/// Primer puerto LIBRE del rango.
///
/// Si 8000 está ocupado por un proceso ajeno se salta y ya está. No se mata a
/// nadie por ocupar un puerto: el proceso de otro no es nuestro para cerrarlo.
pub fn find_free_port() -> Option<u16> {
    (PORT_RANGE_START..PORT_RANGE_END).find(|p| TcpListener::bind(("127.0.0.1", *p)).is_ok())
}

#[cfg(target_os = "windows")]
fn attach_kill_on_close_job(child: &std::process::Child) -> Result<isize, String> {
    // SAFETY: todos los punteros apuntan a memoria válida durante cada llamada;
    // el handle devuelto se transfiere a `OwnedBackend` o se cierra en error.
    unsafe {
        let job = CreateJobObjectW(std::ptr::null(), std::ptr::null());
        if job.is_null() {
            return Err(format!(
                "no se pudo crear el Job Object del backend: {}",
                std::io::Error::last_os_error()
            ));
        }

        let mut info: JOBOBJECT_EXTENDED_LIMIT_INFORMATION = std::mem::zeroed();
        info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
        if SetInformationJobObject(
            job,
            JobObjectExtendedLimitInformation,
            &info as *const _ as *const std::ffi::c_void,
            std::mem::size_of::<JOBOBJECT_EXTENDED_LIMIT_INFORMATION>() as u32,
        ) == 0
        {
            let error = std::io::Error::last_os_error();
            CloseHandle(job);
            return Err(format!(
                "no se pudo configurar el Job Object del backend: {}",
                error
            ));
        }

        if AssignProcessToJobObject(job, child.as_raw_handle() as _) == 0 {
            let error = std::io::Error::last_os_error();
            CloseHandle(job);
            return Err(format!(
                "no se pudo vincular el backend al Job Object: {}",
                error
            ));
        }

        Ok(job as isize)
    }
}

fn spawn_backend(layout: &RuntimeLayout, port: u16) -> Result<OwnedBackend, String> {
    let _ = std::fs::create_dir_all(&layout.log_dir);
    // Un archivo por lanzamiento en vez de truncar; `backend.latest.log` apunta
    // al más reciente para que el diagnóstico no tenga que adivinar.
    let log_file_name = format!(
        "backend_{}.log",
        chrono::Local::now().format("%Y%m%d_%H%M%S")
    );
    let log_file_path = layout.log_dir.join(&log_file_name);
    let log_file = std::fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(&log_file_path)
        .ok();
    let _ = std::fs::write(layout.log_dir.join("backend.latest.log"), &log_file_name);

    log::info!(
        "Arrancando backend [{}] puerto {}\n  python: {}\n  backend: {}\n  vina: {}\n  log: {}",
        layout.kind,
        port,
        layout.python_exe.display(),
        layout.backend_dir.display(),
        layout.vina_exe.display(),
        log_file_path.display()
    );

    let mut cmd = StdCommand::new(&layout.python_exe);
    cmd.args([
        "-m",
        "uvicorn",
        "api.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        &port.to_string(),
        "--loop",
        "asyncio",
    ])
    // El Python embebido usa python311._pth y por diseño ignora PYTHONPATH.
    // Uvicorn debe recibir el app-dir explícito para que `api.main` sea
    // importable también en una instalación limpia, no sólo desde el repo.
    .arg("--app-dir")
    .arg(&layout.backend_dir)
    .current_dir(&layout.backend_dir)
    .env("APP_MODE", "DESKTOP")
    .env("ENVIRONMENT", "production")
    .env("PYTHONPATH", &layout.backend_dir)
    // Los recursos instalados son inmutables. Evita que Python llene el
    // directorio del programa con __pycache__ después del primer arranque.
    .env("PYTHONDONTWRITEBYTECODE", "1")
    // MODO UTF-8. Sin esto, el Python embebido (3.11.9) arranca con la página
    // de códigos del sistema —cp1252 en un Windows en español— como valor por
    // defecto de `open()`, y el backend tiene 87 llamadas de texto que no pasan
    // `encoding=` explícito.
    //
    // MEDIDO sobre el intérprete que se instala, no supuesto:
    //
    //   sin PYTHONUTF8   leer un archivo UTF-8 -> contenido CORROMPIDO, sin
    //                    excepción; escribir una cadena con «→» -> UnicodeEncodeError;
    //                    sys.stdout.encoding = cp1252.
    //   con PYTHONUTF8   las tres cosas correctas.
    //
    // La lectura silenciosa es la peor de las tres: un PDB o un JSON con un
    // acento vuelve mal y nadie se entera. La escritura sí revienta, y como el
    // stdout del backend va al archivo de log, un solo `print` con una flecha
    // tumbaba la línea.
    //
    // Se arregla aquí y no en las 87 llamadas porque aquí es donde se define el
    // entorno del proceso, y los subprocesos que el backend lanza —Vina, los
    // sidecars, el subproceso de MM-GBSA— lo heredan.
    .env("PYTHONUTF8", "1")
    .env("VINA_EXECUTABLE_PATH", &layout.vina_exe)
    // Open Babel se localiza por esta variable y NUNCA por el PATH: un binario
    // ajeno del equipo del usuario produciría un resultado que el informe
    // atribuiría a la versión y al hash declarados en el manifiesto.
    .env("MOLDESIGN_OPENBABEL_DIR", &layout.openbabel_dir)
    .env("TABPFN_NO_BROWSER", "true");

    if let Some(file) = log_file {
        if let Ok(clone) = file.try_clone() {
            cmd.stdout(std::process::Stdio::from(clone));
        }
        cmd.stderr(std::process::Stdio::from(file));
    }

    #[cfg(target_os = "windows")]
    {
        cmd.creation_flags(0x08000000);
    }

    let mut child = cmd
        .spawn()
        .map_err(|e| format!("no se pudo lanzar {}: {}", layout.python_exe.display(), e))?;

    #[cfg(target_os = "windows")]
    {
        let job_handle = match attach_kill_on_close_job(&child) {
            Ok(handle) => handle,
            Err(reason) => {
                let _ = child.kill();
                let _ = child.wait();
                return Err(reason);
            }
        };
        Ok(OwnedBackend { child, job_handle })
    }

    #[cfg(not(target_os = "windows"))]
    {
        Ok(OwnedBackend { child })
    }
}

/// Arranca el backend si hace falta y devuelve el estado resultante.
///
/// **Idempotente y con exclusión mutua.** Dos llamadas concurrentes —el `setup`
/// de Rust y el proveedor de React piden el motor a la vez— no producen dos
/// procesos: la segunda espera en el cerrojo y encuentra el motor ya listo.
pub fn ensure_backend_sync(resource_dir: Option<PathBuf>) -> BackendStatus {
    if app_shutdown_requested().load(Ordering::SeqCst) {
        return BackendStatus::failed(
            BackendPhase::SpawnFailed,
            "la aplicación se está cerrando; no se iniciará otro motor.".to_string(),
        );
    }

    // Comprobación barata antes del cerrojo: lo normal es que ya esté listo.
    // `Ready` significa que ESTE proceso propio ya pasó la validación semántica
    // durante su arranque. No se repite aquí un probe corto: la precarga puede
    // ocupar temporalmente el backend y convertir una demora inocua en un
    // reinicio destructivo. React confirma la salud contra el puerto devuelto
    // y presenta `disconnected`; sólo `restart_backend` autoriza reemplazarlo.
    let existing = current_status();
    if !needs_bootstrap(&existing) && existing.state == BackendPhase::Ready {
        return existing;
    }
    // `Starting` sin puerto: hay otro arranque en curso. No se toca su estado;
    // se espera en el cerrojo y se adopta su resultado, que es exactamente lo
    // que impide que dos llamantes creen dos procesos.

    let _guard = match bootstrap_lock().lock() {
        Ok(guard) => guard,
        Err(poisoned) => poisoned.into_inner(),
    };

    // Dentro del cerrojo se vuelve a mirar: quien esperaba aquí puede que ya
    // tenga el trabajo hecho por el que iba delante.
    let existing = current_status();
    if existing.state == BackendPhase::Ready {
        return existing;
    }

    set_status(BackendStatus {
        state: BackendPhase::Starting,
        port: None,
        detail: None,
    });

    let layout = match resolve_layout(resource_dir.as_deref()) {
        Ok(layout) => layout,
        Err(reason) => {
            log::error!("Runtime del motor no disponible: {}", reason);
            let status = BackendStatus::failed(BackendPhase::NotInstalled, reason);
            set_status(status.clone());
            return status;
        }
    };

    let port = match find_free_port() {
        Some(port) => port,
        None => {
            let reason = format!(
                "no hay ningún puerto libre en el rango {}-{}.",
                PORT_RANGE_START,
                PORT_RANGE_END - 1
            );
            let status = BackendStatus::failed(BackendPhase::SpawnFailed, reason);
            set_status(status.clone());
            return status;
        }
    };

    let mut child = match spawn_backend(&layout, port) {
        Ok(child) => child,
        Err(reason) => {
            log::error!("{}", reason);
            let status = BackendStatus::failed(BackendPhase::SpawnFailed, reason);
            set_status(status.clone());
            return status;
        }
    };

    // Cierra la carrera mínima `spawn() → child_slot`: si la ventana se
    // destruyó justo después de crear el proceso, el handler de cierre todavía
    // no podía verlo. La señal final permite matarlo aquí antes de publicarlo.
    if app_shutdown_requested().load(Ordering::SeqCst) {
        let _ = child.kill();
        let _ = child.wait();
        return BackendStatus::idle();
    }

    let pid = child.id();
    match child_slot().lock() {
        Ok(mut guard) => *guard = Some(child),
        Err(poisoned) => *poisoned.into_inner() = Some(child),
    }

    // El cierre también puede llegar inmediatamente después de guardarlo. En
    // ese caso ya puede terminarse por la vía normal y no se entra al probe.
    if app_shutdown_requested().load(Ordering::SeqCst) {
        terminate_owned_child();
        return BackendStatus::idle();
    }

    log::info!(
        "Esperando a que el backend esté sano en el puerto {}…",
        port
    );
    if let Err(reason) = wait_for_healthy_backend(port, HEALTH_CHECK_TIMEOUT_SECS) {
        log::error!(
            "El probe de salud falló: {}. Se termina el hijo pid {}.",
            reason,
            pid
        );
        // Se mata SÓLO al hijo que acabamos de registrar como propio.
        terminate_owned_child();
        let status = BackendStatus::failed(BackendPhase::HealthFailed, reason);
        set_status(status.clone());
        return status;
    }

    // Mientras se hacía el probe, la ventana pudo cerrarse y retirar el hijo.
    // Se publica Ready sólo mientras se sostiene el mismo cerrojo que usa el
    // cierre; así no existe un Ready sin proceso administrado.
    let status = {
        let guard = match child_slot().lock() {
            Ok(guard) => guard,
            Err(poisoned) => poisoned.into_inner(),
        };
        if guard.is_none() {
            return current_status();
        }
        let status = BackendStatus::ready(port);
        set_status(status.clone());
        status
    };
    log::info!(
        "Backend listo: pid {} puerto {} [{}]",
        pid,
        port,
        layout.kind
    );
    status
}

/// Termina el backend que ESTA aplicación creó, y nada más.
///
/// No se busca por puerto ni por nombre de proceso: sólo se conoce un `Child`,
/// el nuestro. Un backend que estuviera corriendo antes de abrir la aplicación
/// sigue vivo al cerrarla, que es lo correcto — no es nuestro.
pub fn shutdown_owned_backend() {
    terminate_owned_child();
    set_status(BackendStatus::idle());
}

/// Cierre FINAL de la aplicación. La señal cubre incluso un hijo que todavía
/// no alcanzó `child_slot` cuando se destruyó la ventana.
pub fn shutdown_for_app_exit() {
    app_shutdown_requested().store(true, Ordering::SeqCst);
    shutdown_owned_backend();
}

/// Olvida lo sabido para que el siguiente intento vuelva a arrancar de cero.
/// Es lo que hay detrás del botón «Reintentar» de la interfaz.
pub fn reset_for_retry() {
    shutdown_owned_backend();
}

#[cfg(test)]
mod tests;
