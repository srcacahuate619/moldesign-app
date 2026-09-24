//! Carpetas portables de CASO, detrás de una frontera de autorización.
//!
//! # La frontera
//!
//! **Ningún comando acepta una ruta arbitraria del webview.** Un XSS, o un
//! `invoke` escrito a mano en la consola del devtools, podría si no leer o
//! escribir cualquier archivo del disco con los permisos del usuario. El único
//! punto por el que entra una ruta nueva es el diálogo nativo —que sólo el
//! usuario puede aceptar— y lo que entra por ahí se **canonicaliza** y se
//! registra.
//!
//! A partir de ese momento todo se dirige por `case_id` o por un `token` de
//! sesión: el webview no vuelve a nombrar una ruta nunca.
//!
//! ```text
//!   diálogo nativo ──► canonicalize ──► token (memoria, sólo esta sesión)
//!                                        │
//!                 create/initialize/open ▼
//!                                     case_id ──► registro persistente
//!                                        │        (app data)
//!         read / write / reveal ◄────────┘
//! ```
//!
//! El registro persiste en app data para poder reabrir casos tras reiniciar; si
//! no persistiera, cada arranque obligaría a volver a elegir la carpeta.
//!
//! # Estructura del caso
//!
//! ```text
//! <case>/
//! ├── case.json          manifiesto: FUENTE DE VERDAD
//! ├── .case.json.bak     copia previa, para recuperar
//! ├── inputs/ runs/ evidence/ reports/ exports/
//! ```
//!
//! Las subcarpetas se crean vacías. No se genera evidencia ni informes ficticios.
//!
//! # Errores
//!
//! `Err(String)` con prefijo de código (`UNSAFE_NAME: …`) para que el frontend
//! distinga la causa sin adivinar por el texto del mensaje.

use std::collections::HashMap;
use std::fs;
use std::io;
use std::io::Write;
use std::path::{Component, Path, PathBuf};
use std::sync::Mutex;

use serde::{Deserialize, Serialize};
use tauri::Manager;

pub const CASE_SUBDIRS: [&str; 5] = ["inputs", "runs", "evidence", "reports", "exports"];
pub const MANIFEST_FILE: &str = "case.json";
pub const BACKUP_FILE: &str = ".case.json.bak";
// Must stay aligned with frontend/lib/cases/types.ts. The native boundary
// decides whether the frontend manifest can be written to disk.
const CURRENT_CASE_SCHEMA_VERSION: u64 = 7;
const SUPPORTED_CASE_SCHEMA_VERSIONS: &[u64] = &[1, 2, 3, 4, 5, 6, CURRENT_CASE_SCHEMA_VERSION];
const REGISTRY_FILE: &str = "authorized_cases.json";
const MAX_FOLDER_NAME_LEN: usize = 64;
const MAX_MANIFEST_BYTES: u64 = 4 * 1024 * 1024;

const RESERVED_NAMES: [&str; 22] = [
    "con", "prn", "aux", "nul", "com1", "com2", "com3", "com4", "com5", "com6", "com7", "com8",
    "com9", "lpt1", "lpt2", "lpt3", "lpt4", "lpt5", "lpt6", "lpt7", "lpt8", "lpt9",
];

// ── Estado de autorización ───────────────────────────────────────────

#[derive(Default)]
pub struct CaseRegistry {
    /// `case_id` → carpeta canónica. Persistido en app data.
    cases: Mutex<HashMap<String, PathBuf>>,
    /// `token` → carpeta elegida en el diálogo. **Sólo en memoria**: una
    /// autorización de sesión no debe sobrevivir al cierre de la aplicación.
    grants: Mutex<HashMap<String, PathBuf>>,
    /// Dónde se persiste. INYECTABLE para poder probar el ciclo completo
    /// persistir → destruir → cargar sin necesitar un `AppHandle`.
    store_path: Mutex<Option<PathBuf>>,
    /// Salud del registro al cargarlo. Se declara, no se disimula.
    health: Mutex<RegistryHealth>,
}

/// Cómo se cargó el registro de autorizaciones.
///
/// LA DISTINCIÓN QUE FALTABA: un primer arranque legítimo y un registro
/// ilegible producían los dos una lista vacía, y la lista vacía se presentaba
/// como estado sano. El usuario que perdía todos sus casos no veía diferencia
/// con el que aún no tenía ninguno.
#[derive(Serialize, Clone, PartialEq, Debug, Default)]
#[serde(tag = "state", rename_all = "snake_case")]
pub enum RegistryHealth {
    /// Ni principal ni backup existen: primer arranque de verdad.
    #[default]
    FirstRun,
    /// Se leyó el principal sin incidencias.
    Ok,
    /// El principal no servía y se usó el backup.
    RecoveredFromBackup { detail: String },
    /// NINGUNO de los dos se pudo leer, pero AL MENOS UNO existía. La lista
    /// vacía que se ve NO es un estado sano y hay que decirlo.
    Corrupted { detail: String },
}

#[derive(Serialize, Deserialize, Default)]
struct PersistedRegistry {
    version: u32,
    cases: HashMap<String, String>,
}

impl CaseRegistry {
    pub fn load(app: &tauri::AppHandle) -> Self {
        Self::load_from(registry_path(app))
    }

    /// Carga desde una ruta concreta. La usan `load` y las pruebas.
    ///
    /// Si el principal está corrupto se intenta el backup ANTES de empezar
    /// vacío: empezar vacío significa que el usuario pierde de vista todos sus
    /// casos, que es un daño mucho mayor que trabajar con un registro un poco
    /// más viejo.
    pub fn load_from(path: Option<PathBuf>) -> Self {
        let registry = Self::default();
        if let Ok(mut slot) = registry.store_path.lock() {
            *slot = path.clone();
        }
        let Some(path) = path else { return registry };

        let backup_path = backup_of(&path);
        let existed = path.exists() || backup_path.exists();

        let (parsed, mut health) = match read_registry_file(&path) {
            Ok(p) => (Some(p), RegistryHealth::Ok),
            Err(primary) => match read_registry_file(&backup_path) {
                Ok(p) => {
                    log::warn!("registro principal ilegible ({primary}); se usa el backup");
                    (
                        Some(p),
                        RegistryHealth::RecoveredFromBackup { detail: primary },
                    )
                }
                Err(secondary) => {
                    if existed {
                        // Había algo y no se pudo leer: NO es un primer arranque.
                        log::error!("registro y backup ilegibles: {primary} / {secondary}");
                        (
                            None,
                            RegistryHealth::Corrupted {
                                detail: format!("{primary} · copia de seguridad: {secondary}"),
                            },
                        )
                    } else {
                        (None, RegistryHealth::FirstRun)
                    }
                }
            },
        };
        // Si se recuperó del backup, se restaura el principal de forma segura:
        // el backup NO se toca hasta que la escritura del principal cuaja.
        if matches!(&health, RegistryHealth::RecoveredFromBackup { .. }) {
            if let Some(good) = parsed.as_ref() {
                let restoration = serde_json::to_string_pretty(good)
                    .map_err(|e| format!("no se pudo serializar el backup ({e})"))
                    .and_then(|text| write_registry_atomic(&path, &text))
                    // No basta con que el reemplazo devuelva Ok: se vuelve a
                    // leer el principal antes de declararlo restaurado.
                    .and_then(|_| read_registry_file(&path).map(|_| ()));
                if let Err(error) = restoration {
                    if let RegistryHealth::RecoveredFromBackup { detail } = &mut health {
                        detail.push_str(&format!(
                            " · el backup se leyó, pero el principal no pudo restaurarse: {error}"
                        ));
                    }
                }
            }
        }

        if let Ok(mut slot) = registry.health.lock() {
            *slot = health.clone();
        }

        let Some(parsed) = parsed else {
            return registry;
        };

        if let Ok(mut guard) = registry.cases.lock() {
            for (id, raw) in parsed.cases {
                // Se re-canonicaliza al cargar: una carpeta pudo moverse o
                // borrarse entre sesiones. Si ya no resuelve se conserva la ruta
                // cruda para poder DECIRLE al usuario qué caso falta, en vez de
                // que desaparezca en silencio.
                match canonicalize(Path::new(&raw)) {
                    Ok(canonical) => guard.insert(id, canonical),
                    Err(_) => guard.insert(id, PathBuf::from(raw)),
                };
            }
        }
        registry
    }

    /// Cómo se cargó el registro. La UI lo consume para poder avisar.
    pub fn health(&self) -> RegistryHealth {
        self.health
            .lock()
            .map(|g| g.clone())
            .unwrap_or(RegistryHealth::Ok)
    }

    /// Persiste el registro. **Devuelve `Result`**.
    ///
    /// Un comando no puede declarar éxito si la autorización no llegó a disco:
    /// al siguiente arranque el caso no existiría y el usuario no sabría por
    /// qué. Escritura atómica y con backup, igual que el manifiesto.
    fn persist(&self) -> Result<(), String> {
        let path = {
            let guard = self
                .store_path
                .lock()
                .map_err(|_| "IO_ERROR: el registro de casos está bloqueado.".to_string())?;
            match guard.clone() {
                Some(p) => p,
                // Sin ruta de app data no hay dónde persistir; no es un error del
                // usuario y no debe hacer fallar la operación.
                None => return Ok(()),
            }
        };
        let payload = {
            let guard = self
                .cases
                .lock()
                .map_err(|_| "IO_ERROR: el registro de casos está bloqueado.".to_string())?;
            PersistedRegistry {
                version: 1,
                cases: guard
                    .iter()
                    .map(|(id, p)| (id.clone(), p.to_string_lossy().to_string()))
                    .collect(),
            }
        };
        if let Some(parent) = path.parent() {
            fs::create_dir_all(parent).map_err(|e| {
                format!("IO_ERROR: no se pudo crear la carpeta del registro ({e}).")
            })?;
        }
        let text = serde_json::to_string_pretty(&payload)
            .map_err(|e| format!("IO_ERROR: no se pudo serializar el registro ({e})."))?;

        if path.is_file() {
            // Sólo un principal VALIDADO puede rotar a backup. Si el principal
            // está corrupto y el backup es la única copia buena, copiarlo a
            // ciegas destruiría precisamente la copia que permite recuperar.
            if read_registry_file(&path).is_ok() {
                let previous = fs::read_to_string(&path).map_err(|e| {
                    format!("IO_ERROR: no se pudo leer el registro anterior ({e}).")
                })?;
                write_registry_atomic(&backup_of(&path), &previous)?;
            }
        }
        write_registry_atomic(&path, &text)
    }

    pub fn grant(&self, dir: PathBuf) -> String {
        let token = new_id();
        if let Ok(mut guard) = self.grants.lock() {
            guard.insert(token.clone(), dir);
        }
        token
    }

    pub fn resolve_grant(&self, token: &str) -> Result<PathBuf, String> {
        self.grants
            .lock()
            .ok()
            .and_then(|g| g.get(token).cloned())
            .ok_or_else(|| {
                "UNAUTHORIZED: la carpeta no está autorizada en esta sesión. Vuelve a elegirla."
                    .to_string()
            })
    }

    /// Registra y persiste. Si la persistencia falla, **se revierte**.
    ///
    /// Dejar la autorización sólo en memoria haría que el comando declarase
    /// éxito y al siguiente arranque el caso hubiera desaparecido.
    pub fn register(&self, case_id: &str, dir: PathBuf) -> Result<(), String> {
        let previous = {
            let mut guard = self
                .cases
                .lock()
                .map_err(|_| "IO_ERROR: el registro de casos está bloqueado.".to_string())?;
            guard.insert(case_id.to_string(), dir)
        };
        if let Err(e) = self.persist() {
            if let Ok(mut guard) = self.cases.lock() {
                match previous {
                    Some(old) => guard.insert(case_id.to_string(), old),
                    None => guard.remove(case_id),
                };
            }
            return Err(e);
        }
        Ok(())
    }

    /// Ruta ya registrada para `case_id`, si la hay. Para detectar conflictos.
    pub fn existing_path(&self, case_id: &str) -> Option<PathBuf> {
        self.cases.lock().ok().and_then(|g| g.get(case_id).cloned())
    }

    pub fn resolve_case(&self, case_id: &str) -> Result<PathBuf, String> {
        self.cases
            .lock()
            .ok()
            .and_then(|g| g.get(case_id).cloned())
            .ok_or_else(|| {
                format!("UNAUTHORIZED: el caso {case_id} no está autorizado en este equipo.")
            })
    }

    pub fn forget(&self, case_id: &str) -> Result<(), String> {
        let previous = {
            let mut guard = self
                .cases
                .lock()
                .map_err(|_| "IO_ERROR: el registro de casos está bloqueado.".to_string())?;
            guard.remove(case_id)
        };
        if let Err(e) = self.persist() {
            if let (Ok(mut guard), Some(old)) = (self.cases.lock(), previous) {
                guard.insert(case_id.to_string(), old);
            }
            return Err(e);
        }
        Ok(())
    }

    fn authorized_ids(&self) -> Vec<(String, PathBuf)> {
        self.cases
            .lock()
            .map(|g| g.iter().map(|(k, v)| (k.clone(), v.clone())).collect())
            .unwrap_or_default()
    }
}

pub(crate) fn registry_path(app: &tauri::AppHandle) -> Option<PathBuf> {
    if crate::is_packaged_app() {
        // MSIX: app_data_dir() (Roaming) se redirige a LocalCache y se borra al
        // desinstalar; el índice de casos iría a la basura con el paquete. Se
        // persiste en un directorio no-virtualizado que sobrevive (igual que los
        // datos del backend, en %USERPROFILE%\MolDesign).
        crate::persistent_data_dir(app).map(|d| d.join(REGISTRY_FILE))
    } else {
        app.path()
            .app_data_dir()
            .ok()
            .map(|d| d.join(REGISTRY_FILE))
    }
}

/// Backup hermano del registro. Se calcula por concatenación y no con
/// `with_extension`, que sobre `authorized_cases.json` reemplazaría `.json`.
fn backup_of(path: &Path) -> PathBuf {
    let mut name = path.file_name().unwrap_or_default().to_os_string();
    name.push(".bak");
    path.with_file_name(name)
}

fn read_registry_file(path: &Path) -> Result<PersistedRegistry, String> {
    let text = fs::read_to_string(path)
        .map_err(|e| format!("IO_ERROR: no se pudo leer el registro ({e})."))?;
    let parsed = serde_json::from_str::<PersistedRegistry>(&text)
        .map_err(|e| format!("INVALID_MANIFEST: el registro no es JSON válido ({e})."))?;
    if parsed.version != 1 {
        return Err(format!(
            "UNSUPPORTED_VERSION: registro de casos v{}; este build sólo soporta v1.",
            parsed.version
        ));
    }
    Ok(parsed)
}

/// Diagnóstico bajo demanda de la escritura del registro, para máquinas
/// empaquetadas donde `MoveFileExW` falla con `ERROR_NOT_SAME_DEVICE`.
///
/// Se activa con `MOLDESIGN_CASE_DIAG=1` y escribe una línea por evento en
/// `MOLDESIGN_CASE_DIAG_FILE` (por defecto `%TEMP%\moldesign-case-diag.log`).
/// SÓLO registra rutas y códigos de error: nunca el contenido del expediente.
fn case_diag_enabled() -> bool {
    match std::env::var_os("MOLDESIGN_CASE_DIAG") {
        Some(v) => v.to_string_lossy() != "0",
        None => false,
    }
}

fn case_diag(msg: &str) {
    if !case_diag_enabled() {
        return;
    }
    let path = std::env::var_os("MOLDESIGN_CASE_DIAG_FILE")
        .map(PathBuf::from)
        .unwrap_or_else(|| std::env::temp_dir().join("moldesign-case-diag.log"));
    if let Some(parent) = path.parent() {
        let _ = fs::create_dir_all(parent);
    }
    if let Ok(mut file) = fs::OpenOptions::new().create(true).append(true).open(&path) {
        let _ = writeln!(file, "{} {}", chrono::Utc::now().to_rfc3339(), msg);
    }
}

/// Identidad de volumen de una ruta en Windows, para el diagnóstico: raíz del
/// volumen (`GetVolumePathNameW`), existencia y canonicalización. Nada del
/// expediente.
#[cfg(windows)]
fn path_identity(path: &Path) -> String {
    use std::os::windows::ffi::OsStrExt;
    use windows_sys::Win32::Storage::FileSystem::GetVolumePathNameW;

    fn wide(p: &Path) -> Vec<u16> {
        p.as_os_str().encode_wide().chain(Some(0)).collect()
    }
    let raw = wide(path);
    let mut buf = [0u16; 261];
    let ok = unsafe { GetVolumePathNameW(raw.as_ptr(), buf.as_mut_ptr(), buf.len() as u32) };
    let volume = if ok != 0 {
        let len = buf.iter().position(|&c| c == 0).unwrap_or(buf.len());
        String::from_utf16_lossy(&buf[..len])
    } else {
        format!(
            "<sin volumen: os error {}>",
            io::Error::last_os_error().raw_os_error().unwrap_or(-1)
        )
    };
    let canon = fs::canonicalize(path)
        .map(|p| p.display().to_string())
        .unwrap_or_else(|e| format!("<no canonicaliza: {e}>"));
    format!(
        "path={} exists={} canon={} volumen={}",
        path.display(),
        path.exists(),
        canon,
        volume
    )
}

#[cfg(not(windows))]
fn path_identity(path: &Path) -> String {
    let canon = fs::canonicalize(path)
        .map(|p| p.display().to_string())
        .unwrap_or_else(|e| format!("<no canonicaliza: {e}>"));
    format!(
        "path={} exists={} canon={}",
        path.display(),
        path.exists(),
        canon
    )
}

/// Reemplaza `dst` por `src` (un temporal HERMANO ya sincronizado), con la
/// primitiva correcta por plataforma.
///
/// En Windows, `atomicwrites::replace_atomic` es `MoveFileExW(src, dst,
/// MOVEFILE_WRITE_THROUGH | MOVEFILE_REPLACE_EXISTING)`. Sin `MOVEFILE_COPY_ALLOWED`,
/// `MoveFileExW` responde `ERROR_NOT_SAME_DEVICE` (os error 17) cuando el par de
/// rutas no comparte dispositivo (la redirección de carpetas del paquete MSIX lo
/// observa como volúmenes distintos aunque origen y destino sean hermanos
/// léxicos). Se añade `MOVEFILE_COPY_ALLOWED`: en el mismo volumen sigue siendo
/// un rename atómico; entre volúmenes, `MoveFileExW` simula el movimiento por
/// copia. La no-atomicidad de ese camino de copia queda cubierta por el journal
/// `.bak` y por la recuperación al leer (`write_registry_atomic` /
/// `read_manifest_with_recovery`), de modo que no hay ventana de pérdida
/// silenciosa: ante un corte a mitad de la copia, la siguiente lectura recupera
/// el último contenido bueno del backup.
#[cfg(windows)]
fn replace_target(src: &Path, dst: &Path) -> io::Result<()> {
    use std::os::windows::ffi::OsStrExt;
    use windows_sys::Win32::Storage::FileSystem::{
        MoveFileExW, MOVEFILE_COPY_ALLOWED, MOVEFILE_REPLACE_EXISTING, MOVEFILE_WRITE_THROUGH,
    };

    fn wide(p: &Path) -> Vec<u16> {
        p.as_os_str().encode_wide().chain(Some(0)).collect()
    }
    let src_w = wide(src);
    let dst_w = wide(dst);

    // Un único camino cubre creación y reemplazo. `MOVEFILE_REPLACE_EXISTING`
    // sobrescribe el destino existente; `MOVEFILE_COPY_ALLOWED` evita el
    // `ERROR_NOT_SAME_DEVICE` dejando que un movimiento entre volúmenes se haga
    // por copia.
    let flags = MOVEFILE_WRITE_THROUGH | MOVEFILE_REPLACE_EXISTING | MOVEFILE_COPY_ALLOWED;
    let moved = unsafe { MoveFileExW(src_w.as_ptr(), dst_w.as_ptr(), flags) };
    if moved != 0 {
        Ok(())
    } else {
        Err(io::Error::last_os_error())
    }
}

#[cfg(not(windows))]
fn replace_target(src: &Path, dst: &Path) -> io::Result<()> {
    atomicwrites::replace_atomic(src, dst)
}

/// Escribe mediante un temporal HERMANO del destino.
///
/// `atomicwrites::AtomicFile` creaba una subcarpeta temporal; en un MSIX la
/// redirección de rutas podía ubicar subcarpeta y archivo final en dispositivos
/// distintos, y `MoveFileExW` respondía `ERROR_NOT_SAME_DEVICE`. El hermano
/// comparte la frontera, pero aun así `replace_atomic` (MoveFileExW sin
/// `MOVEFILE_COPY_ALLOWED`) seguía fallando bajo la virtualización del paquete;
/// el reemplazo usa ahora `MoveFileExW` con `MOVEFILE_COPY_ALLOWED` (ver
/// `replace_target`).
fn write_atomic_sibling(path: &Path, bytes: &[u8]) -> io::Result<()> {
    let parent = path
        .parent()
        .filter(|p| !p.as_os_str().is_empty())
        .unwrap_or_else(|| Path::new("."));
    let filename = path
        .file_name()
        .and_then(|n| n.to_str())
        .unwrap_or("moldesign");
    let stamp = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap_or_default()
        .as_nanos();

    if case_diag_enabled() {
        case_diag(&format!("escritura_registro parent={}", parent.display()));
        case_diag(&format!("  destino {}", path_identity(path)));
    }

    for attempt in 0..32_u8 {
        let tmp = parent.join(format!(
            ".{filename}.{}.{}.{}.tmp",
            std::process::id(),
            stamp,
            attempt
        ));
        let mut file = match fs::OpenOptions::new()
            .write(true)
            .create_new(true)
            .open(&tmp)
        {
            Ok(file) => file,
            Err(error) if error.kind() == io::ErrorKind::AlreadyExists => continue,
            Err(error) => return Err(error),
        };
        if let Err(error) = file.write_all(bytes).and_then(|_| file.sync_all()) {
            drop(file);
            let _ = fs::remove_file(&tmp);
            return Err(error);
        }
        drop(file);
        if case_diag_enabled() {
            case_diag(&format!("  temporal {}", path_identity(&tmp)));
        }
        if let Err(error) = replace_target(&tmp, path) {
            case_diag(&format!(
                "  reemplazo FALLIDO os_error={} mensaje={error}",
                error.raw_os_error().unwrap_or(-1)
            ));
            let _ = fs::remove_file(&tmp);
            return Err(error);
        }
        return Ok(());
    }

    Err(io::Error::new(
        io::ErrorKind::AlreadyExists,
        "no se pudo reservar un temporal hermano para la escritura atomica",
    ))
}

/// Reemplaza un archivo del registro sin tocar su backup hermano.
fn write_registry_atomic(path: &Path, text: &str) -> Result<(), String> {
    write_atomic_sibling(path, text.as_bytes())
        .map_err(|e| format!("IO_ERROR: no se pudo persistir el registro de casos ({e})."))
}

// ── Canonicalización y containment ───────────────────────────────────

/// Canonicaliza resolviendo symlinks. Requiere que la ruta EXISTA.
///
/// Se usa la canonicalización real del sistema, no una normalización léxica,
/// justamente para que un symlink que apunte fuera del árbol autorizado quede
/// al descubierto: comparar textos dejaría pasar `caso/enlace → C:\Windows`.
pub fn canonicalize(path: &Path) -> Result<PathBuf, String> {
    fs::canonicalize(path).map_err(|e| {
        format!(
            "NOT_FOUND: no se pudo resolver la ruta {} ({e}).",
            path.display()
        )
    })
}

/// `true` si `child` (canónico) cae dentro de `parent` (canónico).
pub fn is_contained(parent: &Path, child: &Path) -> bool {
    child.starts_with(parent)
}

/// Comprueba que `candidate` esté DENTRO de `authorized`, tras canonicalizar.
///
/// Es la comprobación que ejecutan los comandos antes de tocar el disco.
pub fn ensure_within(authorized: &Path, candidate: &Path) -> Result<PathBuf, String> {
    let canonical = canonicalize(candidate)?;
    let base = canonicalize(authorized)?;
    if !is_contained(&base, &canonical) {
        return Err(format!(
            "UNAUTHORIZED: {} queda fuera de la carpeta autorizada {}.",
            canonical.display(),
            base.display()
        ));
    }
    Ok(canonical)
}

// ── Saneamiento de nombres ───────────────────────────────────────────

/// Valida que `name` sirva como nombre de carpeta HIJA, y sólo eso.
///
/// Rechaza separadores, `.`/`..`, letras de unidad, reservados de Windows,
/// caracteres de control y punto final. **No transforma**: transformar dejaría
/// que `..` se convirtiera en algo válido y ocultaría el intento.
pub fn validate_folder_name(name: &str) -> Result<&str, String> {
    let trimmed = name.trim();
    if trimmed.is_empty() {
        return Err("UNSAFE_NAME: el nombre de la carpeta está vacío.".into());
    }
    if trimmed.len() > MAX_FOLDER_NAME_LEN {
        return Err(format!(
            "UNSAFE_NAME: el nombre supera {MAX_FOLDER_NAME_LEN} caracteres."
        ));
    }
    if trimmed == "." || trimmed == ".." {
        return Err("UNSAFE_NAME: `.` y `..` no son nombres de carpeta válidos.".into());
    }
    if trimmed.contains('/') || trimmed.contains('\\') {
        return Err("UNSAFE_NAME: el nombre no puede contener separadores de ruta.".into());
    }
    if trimmed.contains(':') {
        return Err("UNSAFE_NAME: el nombre no puede contener `:`.".into());
    }
    for ch in trimmed.chars() {
        if (ch as u32) < 32 || ch as u32 == 127 {
            return Err("UNSAFE_NAME: el nombre contiene caracteres de control.".into());
        }
        if matches!(ch, '<' | '>' | '"' | '|' | '?' | '*') {
            return Err(format!(
                "UNSAFE_NAME: el carácter `{ch}` no está permitido."
            ));
        }
    }
    // Windows recorta el punto final en silencio, de modo que la carpeta creada
    // no coincidiría con la pedida. El espacio final ya lo quitó `trim()`.
    if trimmed.ends_with('.') {
        return Err("UNSAFE_NAME: el nombre no puede terminar en punto.".into());
    }
    if RESERVED_NAMES.contains(&trimmed.to_ascii_lowercase().as_str()) {
        return Err(format!(
            "UNSAFE_NAME: `{trimmed}` es un nombre reservado por el sistema operativo."
        ));
    }
    // Red final e independiente: como ruta debe ser UN componente normal.
    let mut components = Path::new(trimmed).components();
    match (components.next(), components.next()) {
        (Some(Component::Normal(_)), None) => Ok(trimmed),
        _ => Err("UNSAFE_NAME: el nombre no es un componente de ruta simple.".into()),
    }
}

// ── Validación COMPLETA del manifiesto v1 ────────────────────────────

const STATUSES: [&str; 7] = [
    "draft",
    "qualifying",
    "ready",
    "running",
    "review",
    "completed",
    "abstained",
];
/// Valores de `activeSection` que escribía el esquema v1. Sólo lectura: este
/// build ya no los produce, pero un caso guardado con ellos tiene que abrirse.
const LEGACY_SECTIONS: [&str; 7] = [
    "context", "system", "site", "ligands", "evaluate", "evidence", "report",
];
/// Modos del esquema v2. Son los dos que existen de verdad en la interfaz.
const VIEWS: [&str; 2] = ["evaluation", "report"];
const STUDY_KINDS: [&str; 4] = [
    "explore-hypothesis",
    "compare-series",
    "review-pose",
    "prepare-evidence",
];

/// Valida el manifiesto **entero**, no sólo `schemaVersion`.
///
/// Comprobar únicamente la versión dejaba pasar un `case.json` de una sola
/// clave: el frontend lo rechazaba después, pero Rust ya lo había escrito en
/// disco como si fuera un caso. Aquí se valida ANTES de escribir, de modo que
/// un manifiesto parcial no llega nunca al archivo.
pub fn validate_manifest(contents: &str) -> Result<(), String> {
    let value: serde_json::Value = serde_json::from_str(contents)
        .map_err(|e| format!("INVALID_MANIFEST: `case.json` no es JSON válido ({e})."))?;
    let obj = value
        .as_object()
        .ok_or_else(|| "INVALID_MANIFEST: `case.json` no contiene un objeto.".to_string())?;

    // v1, v2 y v3 se ACEPTAN las tres. Las versiones viejas se leen para poder
    // migrarlas —el frontend lo hace al abrir el caso—, pero este build sólo
    // escribe v3. Rechazar una versión antigua aquí dejaría inaccesibles los
    // casos existentes; aceptar cualquier versión dejaría escribir en disco algo
    // que nadie sabe leer.
    let version = match obj.get("schemaVersion").and_then(|v| v.as_u64()) {
        Some(v) if SUPPORTED_CASE_SCHEMA_VERSIONS.contains(&v) => v,
        Some(other) => {
            let supported = SUPPORTED_CASE_SCHEMA_VERSIONS
                .iter()
                .map(|version| format!("v{version}"))
                .collect::<Vec<_>>()
                .join(", ");
            return Err(format!(
                "UNSUPPORTED_VERSION: esquema v{other}; este build soporta {supported}."
            ));
        }
        None => return Err("INVALID_MANIFEST: falta una `schemaVersion` entera.".into()),
    };

    for key in ["id", "name"] {
        match obj.get(key).and_then(|v| v.as_str()) {
            Some(s) if !s.is_empty() => {}
            _ => {
                return Err(format!(
                    "INVALID_MANIFEST: falta `{key}` o no es una cadena."
                ))
            }
        }
    }
    if version >= 6 {
        match obj.get("ownerUserId").and_then(|v| v.as_str()) {
            Some(owner) if !owner.trim().is_empty() => {}
            _ => return Err("INVALID_MANIFEST: un manifiesto v6 requiere `ownerUserId`.".into()),
        }
    }
    // Las fechas se validan COMO FECHAS. Antes bastaba con que fueran cadenas,
    // así que `"ayer por la tarde"` pasaba por Rust, se escribía en disco, y
    // reventaba después en TypeScript: el peor sitio para enterarse.
    for key in ["createdAt", "updatedAt", "lastOpenedAt"] {
        match obj.get(key).and_then(|v| v.as_str()) {
            Some(s) if is_iso_8601(s) => {}
            Some(s) => {
                return Err(format!(
                    "INVALID_MANIFEST: `{key}` no es una fecha ISO 8601: {s}."
                ))
            }
            None => {
                return Err(format!(
                    "INVALID_MANIFEST: falta `{key}` o no es una cadena."
                ))
            }
        }
    }

    let status = obj
        .get("status")
        .and_then(|v| v.as_str())
        .ok_or_else(|| "INVALID_MANIFEST: falta `status`.".to_string())?;
    if !STATUSES.contains(&status) {
        return Err(format!("INVALID_MANIFEST: `status` desconocido: {status}."));
    }

    // El destino abierto cambia de nombre y de dominio entre versiones. Se
    // valida el que corresponda: aceptar los dos indistintamente permitiría
    // escribir un v2 con la clave vieja y dejarlo ilegible al releerlo.
    if version == 1 {
        let section = obj
            .get("activeSection")
            .and_then(|v| v.as_str())
            .ok_or_else(|| "INVALID_MANIFEST: falta `activeSection`.".to_string())?;
        if !LEGACY_SECTIONS.contains(&section) {
            return Err(format!(
                "INVALID_MANIFEST: `activeSection` desconocida: {section}."
            ));
        }
    } else {
        let view = obj
            .get("activeView")
            .and_then(|v| v.as_str())
            .ok_or_else(|| "INVALID_MANIFEST: falta `activeView`.".to_string())?;
        if !VIEWS.contains(&view) {
            return Err(format!(
                "INVALID_MANIFEST: `activeView` desconocida: {view}."
            ));
        }
    }

    let validate_triple = |value: Option<&serde_json::Value>, path: &str| -> Result<(), String> {
        let values = value
            .and_then(|v| v.as_array())
            .ok_or_else(|| format!("INVALID_MANIFEST: `{path}` debe ser una lista."))?;
        if values.len() != 3
            || values
                .iter()
                .any(|v| v.as_f64().map_or(true, |number| !number.is_finite()))
        {
            return Err(format!(
                "INVALID_MANIFEST: `{path}` debe contener tres números finitos."
            ));
        }
        Ok(())
    };
    let validate_positive_integer =
        |value: Option<&serde_json::Value>, path: &str| -> Result<(), String> {
            match value.and_then(|v| v.as_u64()) {
                Some(number) if number > 0 => Ok(()),
                _ => Err(format!(
                    "INVALID_MANIFEST: `{path}` debe ser un entero positivo."
                )),
            }
        };

    // v3: los inputs del caso. Son OPCIONALES —un caso recién creado no tiene
    // receptor ni ligando— pero, si están, tienen que tener forma. Un `inputs`
    // corrupto que se dejara pasar aquí se escribiría en disco y reventaría
    // después en TypeScript, que es el peor sitio para enterarse.
    if let Some(inputs) = obj.get("inputs") {
        let inputs = inputs
            .as_object()
            .ok_or_else(|| "INVALID_MANIFEST: `inputs` debe ser un objeto.".to_string())?;
        if let Some(receptor) = inputs.get("receptor") {
            let receptor = receptor.as_object().ok_or_else(|| {
                "INVALID_MANIFEST: `inputs.receptor` debe ser un objeto.".to_string()
            })?;
            match receptor.get("pdbId").and_then(|v| v.as_str()) {
                Some(s) if !s.is_empty() => {}
                _ => {
                    return Err(
                        "INVALID_MANIFEST: `inputs.receptor.pdbId` falta o no es una cadena."
                            .into(),
                    )
                }
            }
        }
        if let Some(ligand) = inputs.get("ligand") {
            let ligand = ligand.as_object().ok_or_else(|| {
                "INVALID_MANIFEST: `inputs.ligand` debe ser un objeto.".to_string()
            })?;
            match ligand.get("inputSmiles").and_then(|v| v.as_str()) {
                Some(s) if !s.is_empty() => {}
                _ => {
                    return Err(
                        "INVALID_MANIFEST: `inputs.ligand.inputSmiles` falta o no es una cadena."
                            .into(),
                    )
                }
            }
        }
        if let Some(grid) = inputs.get("grid") {
            let grid = grid
                .as_object()
                .ok_or_else(|| "INVALID_MANIFEST: `inputs.grid` debe ser un objeto.".to_string())?;
            validate_triple(grid.get("center"), "inputs.grid.center")?;
            validate_triple(grid.get("size"), "inputs.grid.size")?;
        }
        if inputs.get("exhaustiveness").is_some() {
            validate_positive_integer(inputs.get("exhaustiveness"), "inputs.exhaustiveness")?;
        }
        if inputs.get("numPoses").is_some() {
            validate_positive_integer(inputs.get("numPoses"), "inputs.numPoses")?;
        }
        validate_pipeline_config(inputs.get("pipelineConfig"), "inputs.pipelineConfig")?;
    }

    // v3: el preflight guardado. Sin `fingerprint` no sirve para nada —no se
    // puede comparar con los inputs actuales— así que un preflight sin él es
    // corrupción, no ausencia.
    if let Some(preflight) = obj.get("preflight") {
        let preflight = preflight
            .as_object()
            .ok_or_else(|| "INVALID_MANIFEST: `preflight` debe ser un objeto.".to_string())?;
        for key in ["fingerprint", "inputDocument"] {
            match preflight.get(key).and_then(|v| v.as_str()) {
                Some(s) if !s.is_empty() => {}
                _ => {
                    return Err(format!(
                        "INVALID_MANIFEST: `preflight.{key}` falta o no es una cadena."
                    ))
                }
            }
        }
        if let Some(config) = preflight.get("executionConfig") {
            let config = config.as_object().ok_or_else(|| {
                "INVALID_MANIFEST: `preflight.executionConfig` debe ser un objeto.".to_string()
            })?;
            validate_triple(
                config.get("gridCenter"),
                "preflight.executionConfig.gridCenter",
            )?;
            validate_triple(config.get("gridSize"), "preflight.executionConfig.gridSize")?;
            match config.get("customHotspots").and_then(|v| v.as_array()) {
                Some(values) if values.iter().all(|v| v.as_str().is_some()) => {}
                _ => {
                    return Err(
                        "INVALID_MANIFEST: `preflight.executionConfig.customHotspots` debe ser una lista de cadenas."
                            .into(),
                    )
                }
            }
            match config.get("dockingEngine").and_then(|v| v.as_str()) {
                Some(value) if !value.is_empty() => {}
                _ => {
                    return Err(
                        "INVALID_MANIFEST: `preflight.executionConfig.dockingEngine` falta o no es una cadena."
                            .into(),
                    )
                }
            }
            validate_positive_integer(
                config.get("exhaustiveness"),
                "preflight.executionConfig.exhaustiveness",
            )?;
            validate_positive_integer(
                config.get("numPoses"),
                "preflight.executionConfig.numPoses",
            )?;
            if config.get("seed").and_then(|v| v.as_u64()).is_none() {
                return Err(
                    "INVALID_MANIFEST: `preflight.executionConfig.seed` debe ser un entero no negativo."
                        .into(),
                );
            }
            validate_pipeline_config(
                config.get("pipelineConfig"),
                "preflight.executionConfig.pipelineConfig",
            )?;
        }
    }

    if let Some(system) = obj.get("structuralSystem") {
        validate_structural_system(system)?;
    }

    if let Some(disposition) = obj.get("disposition") {
        validate_disposition(disposition)?;
    }

    if let Some(decisions) = obj.get("decisions") {
        decisions
            .as_array()
            .ok_or_else(|| "INVALID_MANIFEST: `decisions` debe ser una lista.".to_string())?;
    }

    let storage = obj
        .get("storage")
        .and_then(|v| v.as_object())
        .ok_or_else(|| "INVALID_MANIFEST: falta `storage`.".to_string())?;
    match storage.get("mode").and_then(|v| v.as_str()) {
        Some("browser") => {}
        Some("folder") => {
            if storage.get("path").and_then(|v| v.as_str()).is_none() {
                return Err("INVALID_MANIFEST: `storage.path` falta en modo carpeta.".into());
            }
        }
        _ => return Err("INVALID_MANIFEST: `storage.mode` inválido.".into()),
    }

    if obj.get("archived").and_then(|v| v.as_bool()).is_none() {
        return Err("INVALID_MANIFEST: `archived` debe ser booleano.".into());
    }

    let context = obj
        .get("context")
        .and_then(|v| v.as_object())
        .ok_or_else(|| "INVALID_MANIFEST: falta `context`.".to_string())?;
    if let Some(kind) = context.get("studyKind") {
        match kind.as_str() {
            Some(k) if STUDY_KINDS.contains(&k) => {}
            _ => return Err("INVALID_MANIFEST: `context.studyKind` desconocido.".into()),
        }
    }
    // Los campos de texto libre: PRESENTE con tipo raro es corrupción, ausente
    // es un estado legítimo. Es el mismo criterio que `parseContext` en
    // TypeScript; si sólo lo aplicara un lado, el otro escribiría en disco algo
    // que después no se puede leer.
    for key in CONTEXT_TEXT_FIELDS {
        if let Some(value) = context.get(key) {
            if !value.is_string() {
                return Err(format!(
                    "INVALID_MANIFEST: `context.{key}` debe ser una cadena."
                ));
            }
        }
    }

    // `activeRun` sólo llega en manifiestos v1-v6. Desde v7 el frontend escribe
    // el LIBRO y deriva el puntero al releer, así que aquí se validan los dos:
    // un v6 en disco sigue teniendo que abrirse.
    validate_run_entry(obj.get("activeRun"), "activeRun")?;
    validate_case_runs(obj.get("runs"))?;
    Ok(())
}

/// Valida el libro de corridas con el MISMO contrato que `parseCaseRuns` en
/// TypeScript.
///
/// AUSENTE ES VÁLIDO —un caso recién creado no ha lanzado nada— y una lista
/// vacía también. Lo que se rechaza es un `runs` que no sea lista, una fila
/// mal formada, o dos filas con el mismo `taskId`: un libro con la misma
/// corrida dos veces no permitiría decir cuál de las dos es la buena, y este
/// es el lado que decide si el archivo llega a escribirse.
fn validate_case_runs(value: Option<&serde_json::Value>) -> Result<(), String> {
    let Some(value) = value else { return Ok(()) };
    if value.is_null() {
        return Ok(());
    }
    let runs = value
        .as_array()
        .ok_or_else(|| "INVALID_MANIFEST: `runs` debe ser una lista.".to_string())?;
    let mut seen: std::collections::HashSet<&str> = std::collections::HashSet::new();
    for (index, entry) in runs.iter().enumerate() {
        let path = format!("runs[{index}]");
        validate_run_entry(Some(entry), &path)?;
        let task_id = entry
            .get("taskId")
            .and_then(|v| v.as_str())
            .unwrap_or_default();
        if !seen.insert(task_id) {
            return Err(format!(
                "INVALID_MANIFEST: `runs` contiene dos veces el taskId {task_id}."
            ));
        }
    }
    Ok(())
}

fn validate_string_list(value: Option<&serde_json::Value>, path: &str) -> Result<(), String> {
    let values = value
        .and_then(|v| v.as_array())
        .ok_or_else(|| format!("INVALID_MANIFEST: `{path}` debe ser una lista de cadenas."))?;
    if values.iter().any(|v| v.as_str().is_none()) {
        return Err(format!(
            "INVALID_MANIFEST: `{path}` debe ser una lista de cadenas."
        ));
    }
    Ok(())
}

fn validate_pipeline_config(value: Option<&serde_json::Value>, path: &str) -> Result<(), String> {
    let Some(value) = value else { return Ok(()) };
    if value.is_null() {
        return Ok(());
    }
    let config = value
        .as_object()
        .ok_or_else(|| format!("INVALID_MANIFEST: `{path}` debe ser un objeto."))?;
    for key in ["enabled_stages", "stage_order", "pro_anti_targets"] {
        if config.get(key).is_some() {
            validate_string_list(config.get(key), &format!("{path}.{key}"))?;
        }
    }
    if let Some(params) = config.get("stage_params") {
        let params = params.as_object().ok_or_else(|| {
            format!("INVALID_MANIFEST: `{path}.stage_params` debe ser un objeto.")
        })?;
        if params.values().any(|entry| !entry.is_object()) {
            return Err(format!(
                "INVALID_MANIFEST: `{path}.stage_params` contiene una etapa que no es un objeto."
            ));
        }
    }
    for key in ["docking_engine", "peptide_docking_engine", "gnn_precision"] {
        if let Some(value) = config.get(key) {
            if !value.is_string() {
                return Err(format!(
                    "INVALID_MANIFEST: `{path}.{key}` debe ser una cadena."
                ));
            }
        }
    }
    for key in ["pro_workers", "pro_parallel_docks", "pro_mmgbsa_steps"] {
        if config.get(key).is_some() {
            match config.get(key).and_then(|v| v.as_u64()) {
                Some(number) if number > 0 => {}
                _ => {
                    return Err(format!(
                        "INVALID_MANIFEST: `{path}.{key}` debe ser un entero positivo."
                    ))
                }
            }
        }
    }
    for key in ["pro_selectivity", "pro_mmgbsa"] {
        if let Some(value) = config.get(key) {
            if !value.is_boolean() {
                return Err(format!(
                    "INVALID_MANIFEST: `{path}.{key}` debe ser booleano."
                ));
            }
        }
    }
    Ok(())
}

fn validate_disposition(value: &serde_json::Value) -> Result<(), String> {
    let disposition = value
        .as_object()
        .ok_or_else(|| "INVALID_MANIFEST: `disposition` debe ser un objeto.".to_string())?;
    match disposition.get("kind").and_then(|v| v.as_str()) {
        Some("accept") | Some("limit") | Some("abstain") => {}
        _ => return Err("INVALID_MANIFEST: `disposition.kind` desconocido.".into()),
    }
    match disposition.get("rationale").and_then(|v| v.as_str()) {
        Some(text) if (3..=4000).contains(&text.chars().count()) => {}
        _ => {
            return Err(
                "INVALID_MANIFEST: `disposition.rationale` debe tener entre 3 y 4000 caracteres."
                    .into(),
            )
        }
    }
    match disposition.get("fingerprint").and_then(|v| v.as_str()) {
        Some(text) if !text.is_empty() && text.chars().count() <= 200 => {}
        _ => return Err("INVALID_MANIFEST: `disposition.fingerprint` no es válido.".into()),
    }
    match disposition.get("at").and_then(|v| v.as_str()) {
        Some(value) if is_iso_8601(value) => Ok(()),
        _ => Err("INVALID_MANIFEST: `disposition.at` debe ser una fecha ISO 8601.".into()),
    }
}

fn validate_structural_system(value: &serde_json::Value) -> Result<(), String> {
    let system = value
        .as_object()
        .ok_or_else(|| "INVALID_MANIFEST: `structuralSystem` debe ser un objeto.".to_string())?;
    for key in [
        "lockedAt",
        "sourceRunTaskId",
        "inputFingerprint",
        "dockingEngine",
    ] {
        if system
            .get(key)
            .and_then(|v| v.as_str())
            .map_or(true, str::is_empty)
        {
            return Err(format!(
                "INVALID_MANIFEST: `structuralSystem.{key}` falta o no es una cadena."
            ));
        }
    }
    if !system
        .get("lockedAt")
        .and_then(|v| v.as_str())
        .is_some_and(is_iso_8601)
    {
        return Err(
            "INVALID_MANIFEST: `structuralSystem.lockedAt` no es una fecha ISO 8601.".into(),
        );
    }
    let receptor = system
        .get("receptor")
        .and_then(|v| v.as_object())
        .ok_or_else(|| {
            "INVALID_MANIFEST: `structuralSystem.receptor` debe ser un objeto.".to_string()
        })?;
    if receptor
        .get("pdbId")
        .and_then(|v| v.as_str())
        .map_or(true, str::is_empty)
    {
        return Err(
            "INVALID_MANIFEST: `structuralSystem.receptor.pdbId` falta o no es una cadena.".into(),
        );
    }
    let grid = system
        .get("grid")
        .and_then(|v| v.as_object())
        .ok_or_else(|| {
            "INVALID_MANIFEST: `structuralSystem.grid` debe ser un objeto.".to_string()
        })?;
    let center = grid.get("center").and_then(|v| v.as_array());
    let size = grid.get("size").and_then(|v| v.as_array());
    for (values, path) in [
        (center, "structuralSystem.grid.center"),
        (size, "structuralSystem.grid.size"),
    ] {
        let values =
            values.ok_or_else(|| format!("INVALID_MANIFEST: `{path}` debe ser una lista."))?;
        if values.len() != 3
            || values
                .iter()
                .any(|v| v.as_f64().map_or(true, |n| !n.is_finite()))
        {
            return Err(format!(
                "INVALID_MANIFEST: `{path}` debe contener tres números finitos."
            ));
        }
    }
    validate_string_list(
        system.get("customHotspots"),
        "structuralSystem.customHotspots",
    )?;
    for key in ["exhaustiveness", "numPoses", "conformers"] {
        match system.get(key).and_then(|v| v.as_u64()) {
            Some(number) if number > 0 => {}
            _ => {
                return Err(format!(
                    "INVALID_MANIFEST: `structuralSystem.{key}` debe ser un entero positivo."
                ))
            }
        }
    }
    validate_pipeline_config(
        system.get("pipelineConfig"),
        "structuralSystem.pipelineConfig",
    )?;
    Ok(())
}

const CONTEXT_TEXT_FIELDS: [&str; 7] = [
    "question",
    "decision",
    "systemRationale",
    "controls",
    "assumptions",
    "uncertainties",
    "notes",
];

const RUN_EXECUTION_STATES: [&str; 7] = [
    "idle",
    "submitted",
    "running",
    "interrupted",
    "completed",
    "failed",
    "cancelled",
];

/// Valida UNA corrida con el MISMO contrato que `parseRunEntry` en TypeScript.
///
/// AUSENTE ES VÁLIDO: un caso creado por R1 no tiene corridas y tiene que
/// seguir abriéndose. Lo que se rechaza es una corrida PRESENTE y mal formada:
/// una corrida que existe y cuyo registro está roto es justo lo que no se puede
/// tratar como "no hay corrida", porque la tarea sigue viva en el backend.
///
/// `path` es la ruta exacta dentro del manifiesto —`activeRun` en los v1-v6,
/// `runs[2]` desde v7— porque el error tiene que decir qué fila falla.
fn validate_run_entry(value: Option<&serde_json::Value>, path: &str) -> Result<(), String> {
    let Some(value) = value else { return Ok(()) };
    if value.is_null() {
        return Ok(());
    }
    let run = value
        .as_object()
        .ok_or_else(|| format!("INVALID_MANIFEST: `{path}` debe ser un objeto."))?;

    match run.get("taskId").and_then(|v| v.as_str()) {
        Some(s) if !s.is_empty() => {}
        _ => {
            return Err(format!(
                "INVALID_MANIFEST: `{path}.taskId` falta o no es una cadena."
            ))
        }
    }
    match run.get("executionState").and_then(|v| v.as_str()) {
        Some(s) if RUN_EXECUTION_STATES.contains(&s) => {}
        Some(s) => {
            return Err(format!(
                "INVALID_MANIFEST: `{path}.executionState` desconocido: {s}."
            ))
        }
        None => return Err(format!("INVALID_MANIFEST: falta `{path}.executionState`.")),
    }
    match run.get("startedAt").and_then(|v| v.as_str()) {
        Some(s) if is_iso_8601(s) => {}
        Some(s) => {
            return Err(format!(
                "INVALID_MANIFEST: `{path}.startedAt` no es una fecha ISO 8601: {s}."
            ))
        }
        None => return Err(format!("INVALID_MANIFEST: falta `{path}.startedAt`.")),
    }
    if let Some(finished) = run.get("finishedAt") {
        match finished.as_str() {
            Some(s) if is_iso_8601(s) => {}
            _ => {
                return Err(format!(
                    "INVALID_MANIFEST: `{path}.finishedAt` no es una fecha ISO 8601."
                ))
            }
        }
    }
    if let Some(progress) = run.get("lastKnownProgress") {
        if !progress.is_number() {
            return Err(format!(
                "INVALID_MANIFEST: `{path}.lastKnownProgress` debe ser un número."
            ));
        }
    }
    if let Some(err) = run.get("lastError") {
        if !err.is_string() {
            return Err(format!(
                "INVALID_MANIFEST: `{path}.lastError` debe ser una cadena."
            ));
        }
    }
    if let Some(affinity) = run.get("affinityKcal") {
        if affinity.as_f64().map_or(true, |v| !v.is_finite()) {
            return Err(format!(
                "INVALID_MANIFEST: `{path}.affinityKcal` debe ser un número finito."
            ));
        }
    }
    if let Some(protocol) = run.get("protocol") {
        let protocol = protocol
            .as_object()
            .ok_or_else(|| format!("INVALID_MANIFEST: `{path}.protocol` debe ser un objeto."))?;
        match protocol.get("dockingEngine").and_then(|v| v.as_str()) {
            Some(s) if !s.is_empty() => {}
            _ => {
                return Err(format!(
                    "INVALID_MANIFEST: `{path}.protocol.dockingEngine` falta o no es una cadena."
                ))
            }
        }
        for key in ["exhaustiveness", "numPoses", "conformers"] {
            match protocol.get(key).and_then(|v| v.as_u64()) {
                Some(n) if n > 0 => {}
                _ => {
                    return Err(format!(
                        "INVALID_MANIFEST: `{path}.protocol.{key}` debe ser un entero positivo."
                    ))
                }
            }
        }
    }
    Ok(())
}

/// Fecha ISO 8601 con zona, que es lo que produce `toISOString()`.
///
/// Se comprueba la FORMA, no sólo que sea una cadena: `"ayer por la tarde"`
/// pasaba el contrato de Rust y reventaba después en el de TypeScript, que es
/// el peor sitio donde descubrirlo — el archivo ya estaba escrito.
fn is_iso_8601(value: &str) -> bool {
    chrono::DateTime::parse_from_rfc3339(value).is_ok()
}

pub fn validate_study_kind(kind: &str) -> Result<&str, String> {
    if STUDY_KINDS.contains(&kind) {
        Ok(kind)
    } else {
        Err(format!(
            "INVALID_MANIFEST: tipo de estudio desconocido: {kind}"
        ))
    }
}

// ── Escritura atómica y recuperación ─────────────────────────────────

/// Reemplazo **atómico real**, también en Windows.
///
/// La versión anterior borraba `case.json` y después renombraba el temporal.
/// Entre las dos operaciones había una ventana en la que el caso NO EXISTÍA: un
/// corte ahí dejaba la carpeta sin manifiesto. Ahora:
///
/// 1. se copia el contenido bueno a `.case.json.bak` antes de tocar nada;
/// 2. se escribe el temporal y se hace `sync_all` —sin eso el reemplazo puede
///    publicar un archivo cuyo contenido sigue en el búfer del sistema—;
/// 3. `replace_target` reemplaza con la primitiva de la plataforma
///    (`MoveFileExW` con `MOVEFILE_COPY_ALLOWED` en Windows, `rename(2)` en
///    Unix), que sustituye **sin** pasar por un estado en el que el destino no
///    existe. En el mismo volumen es un rename atómico; entre volúmenes, la
///    copia queda cubierta por el backup `.bak` y la recuperación al leer.
pub fn write_manifest_atomic(case_dir: &Path, contents: &str) -> Result<(), String> {
    validate_manifest(contents)?;
    let incoming_id = manifest_id(contents)?;
    if !case_dir.is_dir() {
        return Err(format!(
            "NOT_FOUND: la carpeta del caso no existe: {}",
            case_dir.display()
        ));
    }
    let final_path = case_dir.join(MANIFEST_FILE);

    // SÓLO se respalda contenido VÁLIDO. Copiar el principal a ciegas era el
    // agujero: si el principal ya estaba corrupto —justo el caso en el que el
    // backup importa— esa copia machacaba el último manifiesto bueno y la
    // recuperación se quedaba sin nada de lo que tirar.
    if final_path.is_file() {
        if let Ok(previous) = fs::read_to_string(&final_path) {
            if validate_manifest(&previous).is_ok()
                && manifest_id(&previous).ok().as_deref() == Some(incoming_id.as_str())
            {
                let _ = fs::write(case_dir.join(BACKUP_FILE), previous);
            }
        }
    }

    write_atomic_sibling(&final_path, contents.as_bytes())
        .map_err(|e| format!("IO_ERROR: no se pudo escribir `case.json` de forma atómica ({e})."))
}

/// Lee el manifiesto, recuperando de `.case.json.bak` si el principal falta o
/// está corrupto.
///
/// Devuelve `(contenido, recuperado_del_backup)`. La segunda componente sube
/// hasta la interfaz: un caso que se salvó del backup no debe presentarse como
/// si no hubiera pasado nada.
pub fn read_manifest_with_recovery(
    case_dir: &Path,
    expected_case_id: Option<&str>,
) -> Result<(String, bool), String> {
    let final_path = case_dir.join(MANIFEST_FILE);
    let backup_path = case_dir.join(BACKUP_FILE);

    let primary_error = if final_path.is_file() {
        match read_validated(&final_path) {
            Ok(text) => return Ok((text, false)),
            Err(e) => e,
        }
    } else {
        format!("NOT_FOUND: no hay `case.json` en {}", case_dir.display())
    };

    // El principal no sirve: se intenta el backup ANTES de rendirse.
    if backup_path.is_file() {
        if let Ok(text) = read_validated(&backup_path) {
            // IDENTIDAD ANTES DE RESTAURAR. Un backup de otro caso no se escribe
            // NUNCA: restaurarlo y rechazarlo después dejaría el `case.json` del
            // caso ajeno en la carpeta, que es peor que no haber restaurado. Se
            // comprueba primero y no se toca nada.
            if let Some(expected) = expected_case_id {
                match manifest_id(&text) {
                    Ok(found) if found == expected => {}
                    Ok(found) => {
                        return Err(format!(
                            "UNAUTHORIZED: la copia de seguridad es del caso {found}, no de {expected}. No se ha restaurado nada."
                        ))
                    }
                    Err(e) => return Err(e),
                }
            }
            // Se restaura para que la siguiente lectura ya sea normal, pero el
            // BACKUP SE CONSERVA hasta comprobar que la restauración cuajó. Si
            // la escritura falla o queda a medias, sigue habiendo una copia
            // buena en disco: nunca se pasa por un estado sin ninguna.
            match write_manifest_atomic(case_dir, &text) {
                Ok(()) => match read_validated(&final_path) {
                    // Restauración verificada leyendo lo que quedó en disco.
                    Ok(verified) => return Ok((verified, true)),
                    Err(_) => return Ok((text, true)),
                },
                // No se pudo restaurar: se devuelve el contenido bueno del
                // backup igualmente. El caso se puede abrir aunque el disco
                // esté en mal estado, y el backup sigue intacto.
                Err(_) => return Ok((text, true)),
            }
        }
    }
    Err(primary_error)
}

fn read_validated(path: &Path) -> Result<String, String> {
    let size = fs::metadata(path)
        .map_err(|e| format!("IO_ERROR: no se pudo consultar `case.json` ({e})."))?
        .len();
    if size > MAX_MANIFEST_BYTES {
        return Err("INVALID_MANIFEST: `case.json` es sospechosamente grande.".into());
    }
    let text = fs::read_to_string(path)
        .map_err(|e| format!("IO_ERROR: no se pudo leer `case.json` ({e})."))?;
    validate_manifest(&text)?;
    Ok(text)
}

pub fn create_subdirs(case_dir: &Path) -> Result<(), String> {
    for sub in CASE_SUBDIRS {
        fs::create_dir_all(case_dir.join(sub))
            .map_err(|e| format!("IO_ERROR: no se pudo crear `{sub}` ({e})."))?;
    }
    Ok(())
}

/// Prepara la carpeta. **Nunca sobrescribe un `case.json` existente.**
pub fn prepare_case_dir(case_dir: &Path, allow_existing_dir: bool) -> Result<(), String> {
    if case_dir.join(MANIFEST_FILE).exists() {
        return Err(format!(
            "ALREADY_EXISTS: ya hay un caso en {}. No se sobrescribe.",
            case_dir.display()
        ));
    }
    if case_dir.exists() && !allow_existing_dir {
        return Err(format!(
            "ALREADY_EXISTS: la carpeta {} ya existe.",
            case_dir.display()
        ));
    }
    fs::create_dir_all(case_dir)
        .map_err(|e| format!("IO_ERROR: no se pudo crear la carpeta del caso ({e})."))?;
    create_subdirs(case_dir)
}

/// Manifiesto inicial v2. Debe coincidir con `lib/cases/schema.ts`.
fn initial_manifest_owned(
    id: &str,
    name: &str,
    study_kind: &str,
    now: &str,
    path: &Path,
    owner_user_id: &str,
) -> String {
    let manifest = serde_json::json!({
        "schemaVersion": CURRENT_CASE_SCHEMA_VERSION,
        "id": id,
        "ownerUserId": owner_user_id,
        "name": name,
        "createdAt": now,
        "updatedAt": now,
        "lastOpenedAt": now,
        "status": "draft",
        "storage": { "mode": "folder", "path": path.to_string_lossy() },
        // El caso NUEVO entra por la evaluación, no por un cuestionario.
        "activeView": "evaluation",
        "context": { "studyKind": study_kind },
        "archived": false,
    });
    format!(
        "{}\n",
        serde_json::to_string_pretty(&manifest).unwrap_or_default()
    )
}

#[cfg(test)]
pub fn initial_manifest(id: &str, name: &str, study_kind: &str, now: &str, path: &Path) -> String {
    initial_manifest_owned(id, name, study_kind, now, path, "test-owner")
}

pub fn manifest_id(contents: &str) -> Result<String, String> {
    serde_json::from_str::<serde_json::Value>(contents)
        .ok()
        .and_then(|v| v.get("id").and_then(|i| i.as_str()).map(str::to_string))
        .ok_or_else(|| "INVALID_MANIFEST: el manifiesto no declara `id`.".to_string())
}

fn ensure_manifest_owner(
    contents: &str,
    expected_owner: &str,
    allow_legacy: bool,
) -> Result<(), String> {
    if expected_owner.trim().is_empty() {
        return Err("UNAUTHORIZED: falta la identidad de la sesión.".into());
    }
    let value: serde_json::Value = serde_json::from_str(contents)
        .map_err(|_| "INVALID_MANIFEST: no se pudo comprobar el propietario.".to_string())?;
    match value.get("ownerUserId").and_then(|owner| owner.as_str()) {
        Some(owner) if owner == expected_owner => Ok(()),
        Some(_) => Err("UNAUTHORIZED: este caso pertenece a otra cuenta.".into()),
        None if allow_legacy => Ok(()),
        None => Err("UNAUTHORIZED: el caso no declara un propietario.".into()),
    }
}

// ── Núcleo de los comandos, sin tipos de Tauri ───────────────────────
//
// La lógica que puede hacer daño vive aquí, en funciones puras respecto de
// Tauri, para que las PRUEBAS NEGATIVAS puedan invocarla directamente: probar
// sólo a través de `#[tauri::command]` obligaría a levantar una app.

fn core_create_owned(
    parent_authorized: &Path,
    folder_name: &str,
    name: &str,
    study_kind: &str,
    now: &str,
    owner_user_id: &str,
) -> Result<(String, PathBuf, String), String> {
    let kind = validate_study_kind(study_kind)?;
    let safe = validate_folder_name(folder_name)?;
    let case_dir = parent_authorized.join(safe);
    prepare_case_dir(&case_dir, false)?;
    let canonical = match ensure_within(parent_authorized, &case_dir) {
        Ok(c) => c,
        Err(e) => {
            // Un symlink plantado entre medias se detecta aquí; se deshace lo
            // creado para no dejar una carpeta huérfana fuera de alcance.
            let _ = fs::remove_dir_all(&case_dir);
            return Err(e);
        }
    };
    let id = new_id();
    let contents = initial_manifest_owned(&id, name.trim(), kind, now, &canonical, owner_user_id);
    write_manifest_atomic(&canonical, &contents)?;
    Ok((id, canonical, contents))
}

/// Entrada pública para el autotest instalado del registro de casos.
///
/// NO es una ruta de la interfaz: la usa el gate empaquetado para ejercer, en el
/// binario REAL instalado, el MISMO núcleo que ejecuta el comando `case_create`
/// (`core_create_owned` + `registry.register` contra el `app_data_dir` real).
/// La interfaz no tiene que invocarla nunca.
pub fn self_test_create_case(
    parent: &Path,
    folder_name: &str,
    name: &str,
    study_kind: &str,
    owner_user_id: &str,
) -> Result<(String, PathBuf, String), String> {
    core_create_owned(
        parent,
        folder_name,
        name,
        study_kind,
        &now_iso(),
        owner_user_id,
    )
}

#[cfg(test)]
pub fn core_create(
    parent_authorized: &Path,
    folder_name: &str,
    name: &str,
    study_kind: &str,
    now: &str,
) -> Result<(String, PathBuf, String), String> {
    core_create_owned(
        parent_authorized,
        folder_name,
        name,
        study_kind,
        now,
        "test-owner",
    )
}

fn core_initialize_owned(
    dir_authorized: &Path,
    name: &str,
    study_kind: &str,
    now: &str,
    owner_user_id: &str,
) -> Result<(String, String), String> {
    let kind = validate_study_kind(study_kind)?;
    prepare_case_dir(dir_authorized, true)?;
    let id = new_id();
    let contents =
        initial_manifest_owned(&id, name.trim(), kind, now, dir_authorized, owner_user_id);
    write_manifest_atomic(dir_authorized, &contents)?;
    Ok((id, contents))
}

#[cfg(test)]
pub fn core_initialize(
    dir_authorized: &Path,
    name: &str,
    study_kind: &str,
    now: &str,
) -> Result<(String, String), String> {
    core_initialize_owned(dir_authorized, name, study_kind, now, "test-owner")
}

pub fn core_write(case_dir: &Path, case_id: &str, contents: &str) -> Result<(), String> {
    // El `id` del manifiesto tiene que ser el del caso autorizado: sin esta
    // comprobación se podría escribir el contenido de un caso encima de otro.
    if manifest_id(contents)? != case_id {
        return Err("UNAUTHORIZED: el manifiesto no corresponde a este caso.".into());
    }
    write_manifest_atomic(case_dir, contents)
}

/// Lee comprobando que el manifiesto es de ESTE caso.
///
/// Sin esta comprobación, una carpeta reutilizada o un `case.json` copiado de
/// otro sitio devolvería el caso equivocado bajo un `case_id` autorizado: la
/// identidad de la carpeta y la del contenido tienen que coincidir.
pub fn core_read(case_dir: &Path, case_id: &str) -> Result<(String, bool), String> {
    // La identidad esperada VIAJA HACIA DENTRO: la recuperación tiene que poder
    // rechazar un backup ajeno ANTES de escribirlo, no después de restaurarlo.
    let (manifest, recovered) = read_manifest_with_recovery(case_dir, Some(case_id))?;
    let found = manifest_id(&manifest)?;
    if found != case_id {
        return Err(format!(
            "UNAUTHORIZED: la carpeta contiene el caso {found}, no {case_id}."
        ));
    }
    Ok((manifest, recovered))
}

/// Restaura `case.json` desde `.case.json.bak`. Es lo que hace «Reparar».
///
/// Falla si no hay backup válido: un botón que dice reparar y no repara nada es
/// peor que no ofrecerlo.
pub fn core_repair(case_dir: &Path, expected_case_id: &str) -> Result<String, String> {
    let backup_path = case_dir.join(BACKUP_FILE);
    if !backup_path.is_file() {
        return Err("NOT_FOUND: no hay copia de seguridad de la que restaurar este caso.".into());
    }
    let text = read_validated(&backup_path)
        .map_err(|e| format!("INVALID_MANIFEST: la copia de seguridad tampoco sirve ({e})."))?;

    // VALIDAR ANTES DE ESCRIBIR. Restaurar un backup de otro caso y rechazarlo
    // después dejaría el `case.json` ajeno en la carpeta: el rechazo llegaría
    // tarde y el daño ya estaría hecho.
    let found = manifest_id(&text)?;
    if found != expected_case_id {
        return Err(format!(
            "UNAUTHORIZED: la copia de seguridad es del caso {found}, no de {expected_case_id}. No se ha restaurado nada."
        ));
    }
    write_manifest_atomic(case_dir, &text)?;
    // Se verifica leyendo de disco: reparar sin comprobar es prometer.
    read_validated(&case_dir.join(MANIFEST_FILE))
}

/// Relocalización TRANSACCIONAL: comprueba identidad y sólo después registra.
///
/// Devuelve el manifiesto si la carpeta contiene de verdad `expected_case_id`.
/// Si contiene otro caso, no se toca nada y el registro queda igual: la
/// comprobación no puede vivir en el frontend, que podría saltársela.
pub fn core_verify_identity(case_dir: &Path, expected_case_id: &str) -> Result<String, String> {
    let (manifest, _) = read_manifest_with_recovery(case_dir, Some(expected_case_id))?;
    let found = manifest_id(&manifest)?;
    if found != expected_case_id {
        return Err(format!(
            "UNAUTHORIZED: esa carpeta contiene el caso {found}, no {expected_case_id}. El registro no se ha modificado."
        ));
    }
    Ok(manifest)
}

// ── Comandos ─────────────────────────────────────────────────────────

/// Carpeta elegida en el diálogo.
///
/// `token` es AUTORIDAD OPACA: el frontend lo devuelve tal cual y no lo
/// interpreta. `display_path` es SÓLO PRESENTACIÓN: se enseña al usuario y
/// nunca se usa para acceder a nada. Antes iban mezclados y la interfaz acabó
/// mostrando el UUID del token donde debía ir una ruta.
#[derive(Serialize)]
pub struct PickedFolder {
    pub token: String,
    pub display_path: String,
    pub has_manifest: bool,
}

#[derive(Serialize)]
pub struct AuthorizedCase {
    pub case_id: String,
    pub path: String,
    pub available: bool,
    /// Hay copia de seguridad de la que restaurar: sólo entonces «Reparar»
    /// tiene algo que hacer.
    pub can_repair: bool,
}

#[derive(Serialize)]
pub struct OpenedCase {
    pub case_id: String,
    pub path: String,
    pub manifest: String,
    pub recovered_from_backup: bool,
    /// El caso ya estaba registrado en OTRA carpeta. Presente ⇒ no se registró
    /// nada: hace falta una decisión explícita del usuario.
    pub conflicting_path: Option<String>,
}

/// Elige la carpeta CONTENEDORA donde crear un caso nuevo.
///
/// Separado de `case_pick_existing_folder` a propósito: los dos abren el mismo
/// diálogo pero significan cosas distintas, y mezclarlos era lo que hacía que
/// la interfaz enseñara el UUID del token como si fuera una ubicación.
#[tauri::command]
pub async fn case_pick_parent_directory(
    app: tauri::AppHandle,
    registry: tauri::State<'_, CaseRegistry>,
) -> Result<Option<PickedFolder>, String> {
    pick_folder(app, registry).await
}

/// Elige una carpeta que ya contiene —o podría contener— un caso.
#[tauri::command]
pub async fn case_pick_directory(
    app: tauri::AppHandle,
    registry: tauri::State<'_, CaseRegistry>,
) -> Result<Option<PickedFolder>, String> {
    pick_folder(app, registry).await
}

async fn pick_folder(
    app: tauri::AppHandle,
    registry: tauri::State<'_, CaseRegistry>,
) -> Result<Option<PickedFolder>, String> {
    use tauri_plugin_dialog::DialogExt;

    let (tx, rx) = std::sync::mpsc::channel();
    app.dialog().file().pick_folder(move |folder| {
        let _ = tx.send(folder);
    });
    let picked = tokio::task::spawn_blocking(move || rx.recv())
        .await
        .map_err(|e| format!("IO_ERROR: el selector de carpeta falló ({e})."))?
        .map_err(|e| format!("IO_ERROR: el selector de carpeta no respondió ({e})."))?;

    let Some(path) = picked.and_then(|p| p.into_path().ok()) else {
        return Ok(None);
    };
    // Se canonicaliza AQUÍ: lo que se autoriza es la ruta real, no la que
    // devolvió el diálogo. Un symlink queda resuelto antes de conceder nada.
    let canonical = canonicalize(&path)?;
    let has_manifest = canonical.join(MANIFEST_FILE).is_file();
    let token = registry.grant(canonical.clone());
    Ok(Some(PickedFolder {
        token,
        display_path: canonical.to_string_lossy().to_string(),
        has_manifest,
    }))
}

#[tauri::command]
pub fn case_create(
    registry: tauri::State<'_, CaseRegistry>,
    token: String,
    folder_name: String,
    name: String,
    study_kind: String,
    owner_user_id: String,
) -> Result<OpenedCase, String> {
    let parent = registry.resolve_grant(&token)?;
    let (id, canonical, contents) = core_create_owned(
        &parent,
        &folder_name,
        &name,
        &study_kind,
        &now_iso(),
        &owner_user_id,
    )?;
    // Si el registro no persiste, el comando NO declara éxito: al siguiente
    // arranque el caso no estaría autorizado y nadie sabría por qué.
    registry.register(&id, canonical.clone())?;
    Ok(OpenedCase {
        case_id: id,
        path: canonical.to_string_lossy().to_string(),
        manifest: contents,
        recovered_from_backup: false,
        conflicting_path: None,
    })
}

#[tauri::command]
pub fn case_initialize(
    registry: tauri::State<'_, CaseRegistry>,
    token: String,
    name: String,
    study_kind: String,
    owner_user_id: String,
) -> Result<OpenedCase, String> {
    let dir = registry.resolve_grant(&token)?;
    let (id, contents) =
        core_initialize_owned(&dir, &name, &study_kind, &now_iso(), &owner_user_id)?;
    registry.register(&id, dir.clone())?;
    Ok(OpenedCase {
        case_id: id,
        path: dir.to_string_lossy().to_string(),
        manifest: contents,
        recovered_from_backup: false,
        conflicting_path: None,
    })
}

/// Abre el caso de una carpeta autorizada por token.
///
/// CONFLICTO DE UBICACIÓN. Si ese `case_id` ya está registrado en OTRA carpeta,
/// no se re-mapea en silencio: se devuelve `conflicting_path` y no se toca el
/// registro. Cambiar el mapping sin preguntar dejaría al usuario editando una
/// copia mientras cree estar editando el original.
/// Abre el caso de una carpeta autorizada por token.
///
/// CONFLICTO DE UBICACIÓN. Si ese `case_id` ya está registrado en OTRA carpeta,
/// no se re-mapea: se devuelve `conflicting_path` y el registro queda intacto.
/// Mover el mapping sin preguntar dejaría al usuario editando una copia
/// mientras cree estar editando el original.
///
/// **Este comando ya NO acepta `accept_relocation`.** Confirmar una
/// relocalización es otra operación —`case_relocate`— porque exige saber QUÉ
/// caso se esperaba, y ese dato no puede venir implícito.
#[tauri::command]
pub fn case_open_token(
    registry: tauri::State<'_, CaseRegistry>,
    token: String,
    owner_user_id: String,
) -> Result<OpenedCase, String> {
    let dir = registry.resolve_grant(&token)?;
    let (manifest, recovered) = read_manifest_with_recovery(&dir, None)?;
    ensure_manifest_owner(&manifest, &owner_user_id, true)?;
    let id = manifest_id(&manifest)?;

    if let Some(previous) = registry.existing_path(&id) {
        if previous != dir {
            return Ok(OpenedCase {
                case_id: id,
                path: dir.to_string_lossy().to_string(),
                manifest,
                recovered_from_backup: recovered,
                conflicting_path: Some(previous.to_string_lossy().to_string()),
            });
        }
    }
    registry.register(&id, dir.clone())?;
    Ok(OpenedCase {
        case_id: id,
        path: dir.to_string_lossy().to_string(),
        manifest,
        recovered_from_backup: recovered,
        conflicting_path: None,
    })
}

/// Mueve el registro de `expected_case_id` a la carpeta autorizada por `token`.
///
/// TRANSACCIONAL: primero se comprueba que la carpeta contiene ESE caso y sólo
/// después se toca el registro. Si contiene otro, se devuelve error y el
/// registro queda exactamente como estaba — la comprobación no puede vivir en
/// el frontend, que podría saltársela llamando al comando a mano.
#[tauri::command]
pub fn case_relocate(
    registry: tauri::State<'_, CaseRegistry>,
    token: String,
    expected_case_id: String,
    owner_user_id: String,
) -> Result<OpenedCase, String> {
    let dir = registry.resolve_grant(&token)?;
    let manifest = core_verify_identity(&dir, &expected_case_id)?;
    ensure_manifest_owner(&manifest, &owner_user_id, true)?;
    registry.register(&expected_case_id, dir.clone())?;
    Ok(OpenedCase {
        case_id: expected_case_id,
        path: dir.to_string_lossy().to_string(),
        manifest,
        recovered_from_backup: false,
        conflicting_path: None,
    })
}

#[tauri::command]
pub fn case_read(
    registry: tauri::State<'_, CaseRegistry>,
    case_id: String,
    owner_user_id: String,
) -> Result<OpenedCase, String> {
    let dir = registry.resolve_case(&case_id)?;
    // Comprueba que el manifiesto es de ESTE caso: una carpeta reutilizada o un
    // `case.json` copiado devolvería otro caso bajo un id autorizado.
    let (manifest, recovered) = core_read(&dir, &case_id)?;
    ensure_manifest_owner(&manifest, &owner_user_id, true)?;
    Ok(OpenedCase {
        case_id,
        path: dir.to_string_lossy().to_string(),
        manifest,
        recovered_from_backup: recovered,
        conflicting_path: None,
    })
}

#[tauri::command]
pub fn case_write(
    registry: tauri::State<'_, CaseRegistry>,
    case_id: String,
    contents: String,
    owner_user_id: String,
) -> Result<(), String> {
    let dir = registry.resolve_case(&case_id)?;
    ensure_manifest_owner(&contents, &owner_user_id, false)?;
    core_write(&dir, &case_id, &contents)
}

/// Restaura `case.json` desde su copia de seguridad. Es «Reparar», de verdad.
#[tauri::command]
pub fn case_repair(
    registry: tauri::State<'_, CaseRegistry>,
    case_id: String,
    owner_user_id: String,
) -> Result<OpenedCase, String> {
    let dir = registry.resolve_case(&case_id)?;
    let (candidate, _) = read_manifest_with_recovery(&dir, Some(&case_id))?;
    ensure_manifest_owner(&candidate, &owner_user_id, true)?;
    // La identidad se valida DENTRO, antes de escribir nada.
    let manifest = core_repair(&dir, &case_id)?;
    Ok(OpenedCase {
        case_id,
        path: dir.to_string_lossy().to_string(),
        manifest,
        recovered_from_backup: true,
        conflicting_path: None,
    })
}

#[tauri::command]
pub fn case_list_authorized(
    registry: tauri::State<'_, CaseRegistry>,
    owner_user_id: String,
) -> Result<Vec<AuthorizedCase>, String> {
    Ok(registry
        .authorized_ids()
        .into_iter()
        .filter_map(|(case_id, path)| {
            let visible = read_manifest_with_recovery(&path, Some(&case_id))
                .and_then(|(manifest, _)| ensure_manifest_owner(&manifest, &owner_user_id, true))
                .is_ok();
            visible.then(|| AuthorizedCase {
                available: path.join(MANIFEST_FILE).is_file(),
                can_repair: path.join(BACKUP_FILE).is_file(),
                case_id,
                path: path.to_string_lossy().to_string(),
            })
        })
        .collect())
}

/// Salud del registro de autorizaciones.
///
/// La consume el frontend al arrancar. Un registro recuperado puede haber
/// perdido las últimas autorizaciones, y uno corrupto presenta una lista vacía
/// que NO es un estado sano: descubrirlo por sorpresa cuando falta un caso es
/// peor que un aviso al arrancar.
#[tauri::command]
pub fn case_registry_health(registry: tauri::State<'_, CaseRegistry>) -> RegistryHealth {
    registry.health()
}

#[tauri::command]
pub fn case_forget(
    registry: tauri::State<'_, CaseRegistry>,
    case_id: String,
    owner_user_id: String,
) -> Result<(), String> {
    let dir = registry.resolve_case(&case_id)?;
    let (manifest, _) = read_manifest_with_recovery(&dir, Some(&case_id))?;
    ensure_manifest_owner(&manifest, &owner_user_id, true)?;
    // Retira del índice. NO borra la carpeta: este sprint no elimina nada.
    registry.forget(&case_id)
}

#[tauri::command]
pub fn case_reveal(
    registry: tauri::State<'_, CaseRegistry>,
    case_id: String,
    owner_user_id: String,
) -> Result<(), String> {
    let dir = registry.resolve_case(&case_id)?;
    let (manifest, _) = read_manifest_with_recovery(&dir, Some(&case_id))?;
    ensure_manifest_owner(&manifest, &owner_user_id, true)?;
    if !dir.is_dir() {
        return Err("NOT_FOUND: la carpeta del caso ya no existe.".into());
    }
    #[cfg(target_os = "windows")]
    let result = std::process::Command::new("explorer").arg(&dir).spawn();
    #[cfg(target_os = "macos")]
    let result = std::process::Command::new("open").arg(&dir).spawn();
    #[cfg(all(unix, not(target_os = "macos")))]
    let result = std::process::Command::new("xdg-open").arg(&dir).spawn();

    result
        .map(|_| ())
        .map_err(|e| format!("IO_ERROR: no se pudo abrir el explorador ({e})."))
}

// ── Utilidades ───────────────────────────────────────────────────────

pub fn new_id() -> String {
    use std::time::{SystemTime, UNIX_EPOCH};
    let nanos = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_nanos())
        .unwrap_or(0);
    let addr = &nanos as *const u128 as usize as u128;
    let mut state = nanos ^ (addr << 32) ^ 0x9E37_79B9_7F4A_7C15;
    let mut bytes = [0u8; 16];
    for slot in bytes.iter_mut() {
        state ^= state << 13;
        state ^= state >> 7;
        state ^= state << 17;
        *slot = (state & 0xff) as u8;
    }
    bytes[6] = (bytes[6] & 0x0f) | 0x40;
    bytes[8] = (bytes[8] & 0x3f) | 0x80;
    let hex: String = bytes.iter().map(|b| format!("{b:02x}")).collect();
    format!(
        "{}-{}-{}-{}-{}",
        &hex[0..8],
        &hex[8..12],
        &hex[12..16],
        &hex[16..20],
        &hex[20..32]
    )
}

pub fn now_iso() -> String {
    chrono::Utc::now().to_rfc3339_opts(chrono::SecondsFormat::Millis, true)
}

#[cfg(test)]
mod tests;
