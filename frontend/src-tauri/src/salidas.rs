//! Carpetas de salida OPCIONALES de los vídeos de Molcy.
//!
//! Misma regla que los casos: la autoridad sobre qué carpeta existe es de Rust. Sólo el selector nativo
//! escribe `molcy-salidas.json` (junto al registro de casos) y el backend únicamente lo LEE, así que una ruta
//! que llegue por la API sin haber pasado por el selector no se escribe. Se canonicaliza aquí, antes de
//! conceder nada, y se exige un directorio.

use std::collections::BTreeMap;
use std::fs;
use std::path::{Path, PathBuf};

use serde::{Deserialize, Serialize};

pub const OUTPUTS_FILE: &str = "molcy-salidas.json";

#[derive(Serialize, Deserialize, Default)]
struct OutputsFile {
    version: u32,
    folders: BTreeMap<String, String>,
}

#[derive(Serialize)]
pub struct PickedOutput {
    /// Identificador que el backend reconoce; nunca la ruta.
    pub id: String,
    /// Ruta canónica, sólo para mostrar.
    pub display_path: String,
}

/// Junto al registro de casos: sobrevive igual que él (incluido el MSIX).
pub(crate) fn outputs_path(registry: &Path) -> PathBuf {
    registry.with_file_name(OUTPUTS_FILE)
}

fn read_outputs(path: &Path) -> OutputsFile {
    fs::read_to_string(path)
        .ok()
        .and_then(|text| serde_json::from_str::<OutputsFile>(&text).ok())
        .filter(|file| file.version == 1)
        .unwrap_or(OutputsFile {
            version: 1,
            folders: BTreeMap::new(),
        })
}

/// Registra `folder` (ya canónica) y devuelve su id; la misma carpeta conserva el mismo id.
pub(crate) fn register_output(path: &Path, folder: &Path) -> Result<String, String> {
    let canonical = crate::cases::canonicalize(folder)?;
    if !canonical.is_dir() {
        return Err(format!(
            "NOT_A_DIRECTORY: {} no es una carpeta.",
            canonical.display()
        ));
    }
    let shown = canonical.to_string_lossy().to_string();
    let mut file = read_outputs(path);
    if let Some((id, _)) = file.folders.iter().find(|(_, value)| **value == shown) {
        return Ok(id.clone());
    }
    let id = crate::cases::new_id();
    file.folders.insert(id.clone(), shown);
    let text = serde_json::to_string_pretty(&file).map_err(|e| format!("IO_ERROR: {e}"))?;
    if let Some(parent) = path.parent() {
        let _ = fs::create_dir_all(parent);
    }
    crate::cases::write_atomic_sibling(path, text.as_bytes())
        .map_err(|e| format!("IO_ERROR: no se pudo guardar la carpeta de salida ({e})."))?;
    Ok(id)
}

/// Selector nativo de la carpeta donde guardar los vídeos de Molcy.
#[tauri::command]
pub async fn molcy_pick_output_dir(app: tauri::AppHandle) -> Result<Option<PickedOutput>, String> {
    use tauri_plugin_dialog::DialogExt;

    let registry = crate::cases::registry_path(&app)
        .ok_or_else(|| "IO_ERROR: no hay carpeta de datos de la aplicación.".to_string())?;
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
    let outputs = outputs_path(&registry);
    let id = register_output(&outputs, &path)?;
    let display_path = crate::cases::canonicalize(&path)?
        .to_string_lossy()
        .to_string();
    Ok(Some(PickedOutput { id, display_path }))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn la_misma_carpeta_conserva_su_id_y_un_archivo_no_se_registra() {
        let base =
            std::env::temp_dir().join(format!("moldesign-salidas-{}", crate::cases::new_id()));
        let folder = base.join("videos");
        fs::create_dir_all(&folder).unwrap();
        let file = base.join(OUTPUTS_FILE);
        let first = register_output(&file, &folder).unwrap();
        assert_eq!(first, register_output(&file, &folder).unwrap());
        let other = base.join("otra");
        fs::create_dir_all(&other).unwrap();
        assert_ne!(first, register_output(&file, &other).unwrap());
        let plain = base.join("archivo.txt");
        fs::write(&plain, b"x").unwrap();
        assert!(register_output(&file, &plain)
            .unwrap_err()
            .starts_with("NOT_A_DIRECTORY"));
        let _ = fs::remove_dir_all(&base);
    }
}
