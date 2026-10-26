//! Archivos que WebView2 confirmó como guardados. El frontend sólo recibe un id;
//! no puede pedirle al explorador que abra una ruta arbitraria.

use serde::{Deserialize, Serialize};
use std::{path::PathBuf, sync::Mutex};
use tauri::Manager;

#[derive(Clone, Serialize, Deserialize)]
struct DownloadedFile {
    id: String,
    path: PathBuf,
}

pub struct FileDownloads {
    entries: Mutex<Vec<DownloadedFile>>,
    storage: PathBuf,
}

impl FileDownloads {
    pub fn load(app: &tauri::AppHandle) -> Result<Self, String> {
        let storage = app
            .path()
            .app_local_data_dir()
            .map_err(|e| e.to_string())?
            .join("downloaded-files.json");
        let entries = std::fs::read(&storage)
            .ok()
            .and_then(|bytes| serde_json::from_slice::<Vec<DownloadedFile>>(&bytes).ok())
            .unwrap_or_default();
        Ok(Self {
            entries: Mutex::new(entries),
            storage,
        })
    }

    pub fn record(&self, path: PathBuf) -> Result<String, String> {
        let path = std::fs::canonicalize(path).map_err(|e| e.to_string())?;
        if !path.is_file() {
            return Err("El archivo descargado ya no existe.".into());
        }
        let id = crate::cases::new_id();
        let mut entries = self.entries.lock().map_err(|e| e.to_string())?;
        entries.push(DownloadedFile {
            id: id.clone(),
            path,
        });
        if entries.len() > 128 {
            entries.remove(0);
        }
        let bytes = serde_json::to_vec(&*entries).map_err(|e| e.to_string())?;
        if let Some(parent) = self.storage.parent() {
            std::fs::create_dir_all(parent).map_err(|e| e.to_string())?;
        }
        crate::cases::write_atomic_sibling(&self.storage, &bytes).map_err(|e| e.to_string())?;
        Ok(id)
    }

    fn resolve(&self, id: &str) -> Result<PathBuf, String> {
        let entries = self.entries.lock().map_err(|e| e.to_string())?;
        let entry = entries
            .iter()
            .find(|entry| entry.id == id)
            .ok_or_else(|| "No se encontró esta descarga.".to_string())?;
        if !entry.path.is_file() {
            return Err("El archivo se movió o se eliminó.".into());
        }
        Ok(entry.path.clone())
    }
}

#[tauri::command]
pub fn file_download_reveal(
    downloads: tauri::State<'_, FileDownloads>,
    id: String,
) -> Result<(), String> {
    let path = downloads.resolve(&id)?;
    tauri_plugin_opener::reveal_item_in_dir(path).map_err(|e| e.to_string())
}
