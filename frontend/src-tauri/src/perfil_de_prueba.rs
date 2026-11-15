//! Perfil de prueba: la aplicación entera en una carpeta que no es la del usuario.
//!
//! POR QUÉ EXISTE. La prueba de resistencia (`frontend/scripts/resistencia.mjs`) conduce el binario que se entrega:
//! crea casos, evalúa y lo deja en reposo durante minutos. Contra el perfil real dejaría corridas en el Historial, casos
//! en Documentos y un registro de casos ajeno, y no podría correr con la aplicación del usuario abierta (la instancia
//! única le pasaría el control a ésa). Con `MOLDESIGN_PERFIL_DE_PRUEBA=<carpeta>`, todo lo que la aplicación escribe va
//! dentro de esa carpeta:
//!
//! | Qué                                      | Normalmente                          | Con el perfil de prueba     |
//! |------------------------------------------|--------------------------------------|-----------------------------|
//! | registro de casos autorizados            | datos de la aplicación               | `app-data\`                 |
//! | carpeta por defecto de los casos          | `Documentos\MolDesign\Casos`         | `documentos\`               |
//! | datos persistentes (modelos, registro MSIX)| `%USERPROFILE%\MolDesign`            | `home\MolDesign\`           |
//! | registro de descargas                    | datos locales de la aplicación       | `app-local\`                |
//! | logs y traza de arranque                 | logs de la aplicación                | `logs\`                     |
//! | perfil de WebView2 (caché, almacenamiento)| datos locales de la aplicación       | `webview\`                  |
//! | backend: `USERPROFILE`, `APPDATA`, `LOCALAPPDATA`, `TEMP`, `LOCAL_DATA_DIR` | los del usuario | dentro de `home\` |
//!
//! y no se registra la instancia única. Se anuncia en la traza de arranque, en la primera línea.
//!
//! LO QUE NO HACE: caer en silencio al perfil real. Si la variable está puesta y la carpeta no sirve (relativa, o no se
//! puede crear), la aplicación no arranca: una prueba que creía estar aislada habría escrito en los datos del usuario.

use std::path::{Path, PathBuf};
use std::sync::OnceLock;

pub const VARIABLE: &str = "MOLDESIGN_PERFIL_DE_PRUEBA";

static RAIZ: OnceLock<Option<PathBuf>> = OnceLock::new();

/// Valida el valor de la variable. Separado para poder probarlo sin tocar el entorno.
pub fn validar(valor: Option<&std::ffi::OsStr>) -> Result<Option<PathBuf>, String> {
    let Some(valor) = valor.filter(|v| !v.is_empty()) else {
        return Ok(None);
    };
    let ruta = PathBuf::from(valor);
    if !ruta.is_absolute() {
        return Err(format!(
            "{VARIABLE} debe ser una ruta absoluta; se recibió {}",
            ruta.display()
        ));
    }
    std::fs::create_dir_all(&ruta)
        .map_err(|e| format!("{VARIABLE}: no se pudo crear {} ({e})", ruta.display()))?;
    Ok(Some(ruta))
}

/// Lee la variable una vez. Termina el proceso si está puesta y no sirve (ver arriba).
pub fn iniciar() -> Option<&'static Path> {
    RAIZ.get_or_init(|| match validar(std::env::var_os(VARIABLE).as_deref()) {
        Ok(raiz) => raiz,
        Err(motivo) => {
            let _ = std::fs::write(
                std::env::temp_dir().join("moldesign_perfil_de_prueba_invalido.txt"),
                &motivo,
            );
            eprintln!("{motivo}");
            std::process::exit(2);
        }
    })
    .as_deref()
}

/// La carpeta del perfil de prueba, si la hay.
pub fn raiz() -> Option<&'static Path> {
    RAIZ.get().and_then(|r| r.as_deref())
}

pub fn activo() -> bool {
    raiz().is_some()
}

/// Una subcarpeta del perfil, creada. `None` sin perfil de prueba.
pub fn carpeta(nombre: &str) -> Option<PathBuf> {
    let dir = raiz()?.join(nombre);
    let _ = std::fs::create_dir_all(&dir);
    Some(dir)
}

/// El «perfil de usuario» que ve el backend dentro del perfil de prueba.
pub fn home() -> Option<PathBuf> {
    carpeta("home")
}

/// Variables de entorno del backend: el usuario que ve Python es uno nuevo, dentro del perfil.
///
/// Python resuelve `Path.home()` con `USERPROFILE` en Windows; las cachés de modelos y el almacén de proveedores cuelgan
/// de ahí. Es lo mismo que hace la cápsula de QA (`scripts/qa_sandbox/sandbox-up.mjs`).
pub fn entorno_del_backend() -> Vec<(&'static str, PathBuf)> {
    let Some(home) = home() else {
        return Vec::new();
    };
    let sub = |nombre: &str| {
        let dir = home.join(nombre);
        let _ = std::fs::create_dir_all(&dir);
        dir
    };
    vec![
        ("USERPROFILE", home.clone()),
        ("HOME", home.clone()),
        ("APPDATA", sub("AppData\\Roaming")),
        ("LOCALAPPDATA", sub("AppData\\Local")),
        ("TEMP", sub("Temp")),
        ("TMP", sub("Temp")),
        ("LOCAL_DATA_DIR", sub("MolDesign\\data")),
    ]
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn sin_variable_no_hay_perfil() {
        assert_eq!(validar(None).unwrap(), None);
        assert_eq!(validar(Some(std::ffi::OsStr::new(""))).unwrap(), None);
    }

    #[test]
    fn una_ruta_relativa_no_vale() {
        let error = validar(Some(std::ffi::OsStr::new("perfil"))).unwrap_err();
        assert!(error.contains("ruta absoluta"), "{error}");
    }

    #[test]
    fn una_ruta_absoluta_se_crea() {
        let dir = std::env::temp_dir().join(format!("moldesign-perfil-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&dir);
        let raiz = validar(Some(dir.as_os_str())).unwrap().unwrap();
        assert!(raiz.is_dir());
        let _ = std::fs::remove_dir_all(&dir);
    }
}
