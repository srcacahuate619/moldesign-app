use std::collections::HashMap;
use std::ffi::OsString;
use std::path::{Component, Path, PathBuf};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;

use futures_util::StreamExt;
use reqwest::{Client, StatusCode, Url};
use sha2::{Digest, Sha256};
use tauri::{AppHandle, Emitter, Manager};
use tokio::io::{AsyncReadExt, AsyncWriteExt};
use tokio::sync::Mutex;

pub struct DownloadState {
    pub cancel_flags: Mutex<HashMap<String, Arc<AtomicBool>>>,
}

#[derive(Clone, serde::Serialize)]
pub struct DownloadProgress {
    pub model_id: String,
    pub bytes_downloaded: u64,
    pub total_bytes: u64,
    pub speed_bytes_per_sec: f64,
}

#[derive(Clone, serde::Serialize)]
pub struct DownloadComplete {
    pub model_id: String,
    pub success: bool,
    pub error: Option<String>,
}

#[tauri::command]
pub fn get_resource_dir(app: AppHandle) -> Result<String, String> {
    // Devuelve el directorio donde se descargan los modelos. En un paquete MSIX,
    // `resource_dir` es de solo lectura (WindowsApps), así que se redirige a un
    // data dir writable y no-virtualizado. En desktop/dev sigue siendo el
    // directorio de recursos.
    let dir = model_root(&app)?;
    Ok(dir.to_string_lossy().to_string())
}

/// Raíz donde se descargan/extraen los modelos, y contra la que `resource_path`
/// impone su frontera de contención.
///
/// En desktop/dev es `resource_dir`. En un paquete MSIX es
/// `%USERPROFILE%\MolDesign` —writable y persistente, a diferencia de
/// `WindowsApps` (solo lectura) y de `LocalCache` (que se borra al desinstalar).
///
/// POR QUÉ AQUÍ Y NO EN `…\MolDesign\models`. Esta función devolvía
/// `persistent_data_dir().join("models")`, y el frontend le concatena el destino
/// que declara `launcher-manifest.json`. Eso producía rutas con el segmento
/// duplicado —`…\MolDesign\models\models\llm\`— mientras el backend buscaba en
/// otro sitio: la descarga se marcaba correcta y el motor no encontraba nada.
///
/// La raíz correcta la fijan los dos consumidores, no esta función:
///
///   `backend/services/ai/local_llm.py`      MODEL_SEARCH_PATHS incluye
///                                           `~/MolDesign` + `models/llm`
///   `backend/services/motores/catalogo.py`  directorios_de_busqueda() incluye
///                                           `~/MolDesign`, y ESMFOLD_ARCHIVOS
///                                           son `esmfold/models/…`
///
/// Con la raíz en `~/MolDesign`, los destinos del manifiesto —`models/llm/` y
/// `esmfold/models/`— aterrizan exactamente donde se buscan. Hay una prueba que
/// fija esa correspondencia: si alguien cambia un destino del manifiesto o una
/// ruta de búsqueda del backend, falla en vez de descubrirse con una descarga
/// de 8,4 GB que no sirve.
fn model_root(app: &AppHandle) -> Result<PathBuf, String> {
    let candidate = if crate::is_packaged_app() {
        crate::persistent_data_dir(app)
    } else {
        app.path().resource_dir().ok()
    };
    let Some(root) = candidate else {
        return Err("No se puede resolver el directorio de descargas".into());
    };
    std::fs::create_dir_all(&root)
        .map_err(|e| format!("No se puede crear el directorio de descargas: {}", e))?;
    std::fs::canonicalize(&root)
        .map_err(|e| format!("No se puede resolver el directorio de descargas: {}", e))
}

fn lexical_normalize(path: &Path) -> Result<PathBuf, String> {
    let mut normalized = PathBuf::new();
    for component in path.components() {
        match component {
            Component::Prefix(prefix) => normalized.push(prefix.as_os_str()),
            Component::RootDir => normalized.push(std::path::MAIN_SEPARATOR.to_string()),
            Component::CurDir => {}
            Component::ParentDir => {
                if !normalized.pop() {
                    return Err("La ruta contiene un salto fuera de su raíz".into());
                }
            }
            Component::Normal(part) => normalized.push(part),
        }
    }
    Ok(normalized)
}

fn resource_path(app: &AppHandle, raw: &str, label: &str) -> Result<PathBuf, String> {
    let root = model_root(app)?;
    let requested = PathBuf::from(raw);
    if !requested.is_absolute() {
        return Err(format!(
            "{} debe ser una ruta absoluta dentro de resource_dir",
            label
        ));
    }
    let normalized = lexical_normalize(&requested)?;
    if !normalized.starts_with(&root) {
        return Err(format!("{} queda fuera de resource_dir", label));
    }

    // Canonicalize the nearest existing ancestor. Checking only the final
    // path misses a planted symlink in a parent directory when the final file
    // does not exist yet; that would let a download/create operation escape
    // the trusted resource tree.
    let mut probe = normalized.clone();
    let mut suffix: Vec<OsString> = Vec::new();
    while !probe.exists() {
        let component = probe
            .file_name()
            .ok_or_else(|| format!("{} no tiene un ancestro existente", label))?;
        suffix.push(component.to_os_string());
        if !probe.pop() {
            return Err(format!("{} no tiene un ancestro existente", label));
        }
    }
    let resolved_probe = std::fs::canonicalize(&probe)
        .map_err(|e| format!("No se puede resolver {}: {}", label, e))?;
    if !resolved_probe.starts_with(&root) {
        return Err(format!("{} resuelve fuera de resource_dir", label));
    }
    let mut resolved = resolved_probe;
    for component in suffix.iter().rev() {
        resolved.push(component);
    }
    Ok(resolved)
}

fn copy_staged_tree(source: &Path, destination: &Path) -> Result<(), String> {
    if std::fs::symlink_metadata(destination)
        .map(|metadata| metadata.file_type().is_symlink())
        .unwrap_or(false)
    {
        return Err(format!(
            "Destino staged es un enlace simbólico: {}",
            destination.display()
        ));
    }
    std::fs::create_dir_all(destination)
        .map_err(|e| format!("No se puede crear destino {}: {}", destination.display(), e))?;
    for item in std::fs::read_dir(source).map_err(|e| format!("No se puede leer staging: {}", e))? {
        let item = item.map_err(|e| format!("Error leyendo staging: {}", e))?;
        let source_path = item.path();
        let target_path = destination.join(item.file_name());
        if std::fs::symlink_metadata(&target_path)
            .map(|metadata| metadata.file_type().is_symlink())
            .unwrap_or(false)
        {
            return Err(format!(
                "Destino staged es un enlace simbólico: {}",
                target_path.display()
            ));
        }
        let metadata = std::fs::symlink_metadata(&source_path)
            .map_err(|e| format!("No se puede leer staging: {}", e))?;
        if metadata.file_type().is_symlink() {
            return Err(format!(
                "El archivo staged es un enlace simbólico: {}",
                source_path.display()
            ));
        }
        if metadata.is_dir() {
            copy_staged_tree(&source_path, &target_path)?;
        } else if metadata.is_file() {
            if let Some(parent) = target_path.parent() {
                std::fs::create_dir_all(parent)
                    .map_err(|e| format!("No se puede crear destino: {}", e))?;
            }
            std::fs::copy(&source_path, &target_path)
                .map_err(|e| format!("No se puede instalar {}: {}", target_path.display(), e))?;
        } else {
            return Err(format!(
                "Entrada staged no soportada: {}",
                source_path.display()
            ));
        }
    }
    Ok(())
}

fn validate_download_url(raw: &str) -> Result<Url, String> {
    let url = Url::parse(raw).map_err(|e| format!("URL de descarga inválida: {}", e))?;
    if url.scheme() != "https" {
        return Err("Las descargas sólo admiten HTTPS".into());
    }
    let host = url.host_str().unwrap_or("").to_ascii_lowercase();
    if host != "huggingface.co" && host != "cdn-lfs.huggingface.co" {
        return Err(format!("Host de descarga no autorizado: {}", host));
    }
    Ok(url)
}

async fn verify_sha256(path: &PathBuf, expected_hex: &str) -> Result<(), String> {
    let mut file = tokio::fs::File::open(path)
        .await
        .map_err(|e| format!("Error abriendo para verificar: {}", e))?;

    let mut hasher = Sha256::new();
    let mut buf = [0u8; 65536];

    loop {
        let n = file
            .read(&mut buf)
            .await
            .map_err(|e| format!("Error leyendo para hash: {}", e))?;
        if n == 0 {
            break;
        }
        hasher.update(&buf[..n]);
    }

    let actual = hex::encode(hasher.finalize());
    if actual != expected_hex {
        return Err(format!(
            "SHA-256 mismatch: esperado {}, actual {}",
            expected_hex, actual
        ));
    }
    Ok(())
}

#[tauri::command]
pub async fn download_model(
    app: AppHandle,
    state: tauri::State<'_, DownloadState>,
    model_id: String,
    url: String,
    dest: String,
    sha256: String,
    resume: bool,
) -> Result<(), String> {
    // Validate the request before publishing a cancellation token. Invalid
    // URLs/paths must not leave a stale flag that a later request can observe.
    let validated_url = validate_download_url(&url)?;
    let dest_path = resource_path(&app, &dest, "destino de descarga")?;

    let cancel_flag = Arc::new(AtomicBool::new(false));
    {
        let mut flags = state.cancel_flags.lock().await;
        flags.insert(model_id.clone(), cancel_flag.clone());
    }

    if let Some(parent) = dest_path.parent() {
        tokio::fs::create_dir_all(parent)
            .await
            .map_err(|e| format!("Error creando directorio: {}", e))?;
    }

    let client = Client::builder()
        .user_agent("MolDesign-Launcher/1.0")
        .build()
        .map_err(|e| format!("Error creando HTTP client: {}", e))?;

    let part_path = dest_path.with_extension("part");
    let mut downloaded: u64 = 0;

    if resume && part_path.exists() {
        downloaded = tokio::fs::metadata(&part_path)
            .await
            .map_err(|e| format!("Error leyendo .part: {}", e))?
            .len();
    }

    let mut req = client.get(validated_url.clone());
    if resume && downloaded > 0 {
        req = req.header("Range", format!("bytes={}-", downloaded));
    }

    let mut resp = req
        .send()
        .await
        .map_err(|e| format!("Error en request: {}", e))?;

    if !resp.status().is_success() {
        return Err(format!("Error HTTP descargando {}: {}", url, resp.status()));
    }
    // A server that ignores Range and returns 200 must not be appended to a
    // partial file: that would silently corrupt the artifact before hashing.
    if resume && downloaded > 0 && resp.status() != StatusCode::PARTIAL_CONTENT {
        downloaded = 0;
        drop(resp);
        resp = client
            .get(validated_url)
            .send()
            .await
            .map_err(|e| format!("Error reiniciando descarga: {}", e))?;
        if !resp.status().is_success() {
            return Err(format!("Error HTTP reiniciando {}: {}", url, resp.status()));
        }
    }

    let total = if resume && downloaded > 0 {
        resp.content_length()
            .unwrap_or(0)
            .saturating_add(downloaded)
    } else {
        resp.content_length().unwrap_or(0)
    };

    let mut file = if resume && downloaded > 0 {
        tokio::fs::OpenOptions::new()
            .append(true)
            .open(&part_path)
            .await
            .map_err(|e| format!("Error abriendo .part para append: {}", e))?
    } else {
        tokio::fs::File::create(&part_path)
            .await
            .map_err(|e| format!("Error creando .part: {}", e))?
    };

    let mut stream = resp.bytes_stream();
    let start = std::time::Instant::now();
    let mut last_emit = std::time::Instant::now();
    let mut total_downloaded = downloaded;

    while let Some(chunk) = stream.next().await {
        if cancel_flag.load(Ordering::SeqCst) {
            return Err("Descarga cancelada por el usuario".into());
        }

        let data = chunk.map_err(|e| format!("Error en chunk: {}", e))?;
        file.write_all(&data)
            .await
            .map_err(|e| format!("Error escribiendo: {}", e))?;

        total_downloaded += data.len() as u64;

        let now = std::time::Instant::now();
        if now.duration_since(last_emit).as_millis() >= 250 {
            let elapsed = now.duration_since(start).as_secs_f64();
            let speed = if elapsed > 0.0 {
                total_downloaded as f64 / elapsed
            } else {
                0.0
            };

            let _ = app.emit(
                "download:progress",
                DownloadProgress {
                    model_id: model_id.clone(),
                    bytes_downloaded: total_downloaded,
                    total_bytes: total,
                    speed_bytes_per_sec: speed,
                },
            );

            last_emit = now;
        }
    }

    file.flush()
        .await
        .map_err(|e| format!("Error flushing: {}", e))?;
    drop(file);

    // Verify the completed temporary file before it becomes visible as a
    // usable model. A mismatch never leaves a corrupt final artifact behind.
    if !sha256.is_empty() {
        if let Err(error) = verify_sha256(&part_path, &sha256).await {
            let _ = tokio::fs::remove_file(&part_path).await;
            return Err(error);
        }
    }

    tokio::fs::rename(&part_path, &dest_path)
        .await
        .map_err(|e| format!("Error renombrando .part a destino: {}", e))?;

    let _ = app.emit(
        "download:complete",
        DownloadComplete {
            model_id: model_id.clone(),
            success: true,
            error: None,
        },
    );

    {
        let mut flags = state.cancel_flags.lock().await;
        flags.remove(&model_id);
    }

    Ok(())
}

#[tauri::command]
pub async fn cancel_download(
    state: tauri::State<'_, DownloadState>,
    model_id: String,
) -> Result<(), String> {
    let mut flags = state.cancel_flags.lock().await;
    if let Some(flag) = flags.remove(&model_id) {
        flag.store(true, Ordering::SeqCst);
        Ok(())
    } else {
        Err(format!("No hay descarga activa para {}", model_id))
    }
}

#[tauri::command]
pub async fn extract_archive(
    app: AppHandle,
    archive_path: String,
    dest_dir: String,
    module_id: String,
) -> Result<(), String> {
    let archive = resource_path(&app, &archive_path, "archivo ZIP")?;
    let dest = resource_path(&app, &dest_dir, "destino de extracción")?;

    if !archive.exists() {
        return Err(format!("Archive not found: {}", archive_path));
    }

    tokio::task::spawn_blocking(move || {
        let file =
            std::fs::File::open(&archive).map_err(|e| format!("Cannot open archive: {}", e))?;

        let mut zip = zip::ZipArchive::new(file).map_err(|e| format!("Cannot read zip: {}", e))?;

        let total = zip.len();
        if total == 0 {
            return Err("El archivo ZIP no contiene entradas".into());
        }
        let staging = dest.join(format!(
            ".moldesign-extract-{}-{}",
            module_id
                .chars()
                .map(|c| if c.is_ascii_alphanumeric() || c == '-' || c == '_' {
                    c
                } else {
                    '_'
                })
                .collect::<String>(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .map_err(|e| format!("Reloj del sistema inválido: {}", e))?
                .as_nanos()
        ));
        std::fs::create_dir_all(&staging)
            .map_err(|e| format!("Cannot create staging directory: {}", e))?;

        for i in 0..total {
            let mut entry = zip
                .by_index(i)
                .map_err(|e| format!("Error reading entry {}: {}", i, e))?;

            let name = entry.name().to_string();
            let safe_name = entry
                .enclosed_name()
                .ok_or_else(|| format!("Entrada ZIP fuera del destino: {}", name))?
                .to_path_buf();
            if entry.is_symlink() {
                return Err(format!("Entrada ZIP simbólica no permitida: {}", name));
            }
            let out_path = staging.join(&safe_name);

            if entry.is_dir() {
                std::fs::create_dir_all(&out_path)
                    .map_err(|e| format!("Cannot create dir {}: {}", out_path.display(), e))?;
            } else {
                if let Some(parent) = out_path.parent() {
                    std::fs::create_dir_all(parent)
                        .map_err(|e| format!("Cannot create parent {}: {}", parent.display(), e))?;
                }

                let mut out = std::fs::File::create(&out_path)
                    .map_err(|e| format!("Cannot create file {}: {}", out_path.display(), e))?;

                std::io::copy(&mut entry, &mut out)
                    .map_err(|e| format!("Error extracting {}: {}", name, e))?;
            }

            let pct = ((i + 1) as f64 / total as f64 * 100.0) as u32;
            if pct % 10 == 0 || i == total - 1 {
                let _ = app.emit(
                    "extract:progress",
                    serde_json::json!({
                        "module_id": module_id,
                        "current": i + 1,
                        "total": total,
                        "pct": pct
                    }),
                );
            }
        }

        copy_staged_tree(&staging, &dest)?;
        std::fs::remove_dir_all(&staging)
            .map_err(|e| format!("Cannot remove staging directory: {}", e))?;
        std::fs::remove_file(&archive).map_err(|e| format!("Cannot remove archive: {}", e))?;

        let _ = app.emit(
            "extract:complete",
            serde_json::json!({
                "module_id": module_id,
                "success": true
            }),
        );

        Ok::<_, String>(())
    })
    .await
    .map_err(|e| format!("Extraction failed: {}", e))??;

    Ok(())
}

#[tauri::command]
pub async fn file_exists(app: AppHandle, dest: String) -> Result<bool, String> {
    let path = resource_path(&app, &dest, "archivo de modelo")?;
    Ok(path.exists())
}

#[tauri::command]
pub async fn verify_model(app: AppHandle, dest: String, sha256: String) -> Result<bool, String> {
    let path = resource_path(&app, &dest, "archivo de modelo")?;
    if !path.exists() {
        return Ok(false);
    }
    verify_sha256(&path, &sha256).await.map(|_| true)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn las_rutas_parent_no_salen_de_la_raiz() {
        let root = PathBuf::from(r"C:\app\resources");
        let inside =
            lexical_normalize(Path::new(r"C:\app\resources\models\..\models\peso.bin")).unwrap();
        assert!(inside.starts_with(&root));
        let escape = lexical_normalize(Path::new(r"C:\app\resources\..\secreto.bin")).unwrap();
        assert!(!escape.starts_with(&root));
    }

    #[test]
    fn solo_se_aceptan_descargas_https_de_hugging_face() {
        assert!(
            validate_download_url("https://huggingface.co/org/repo/resolve/abc/peso.bin").is_ok()
        );
        assert!(validate_download_url("https://cdn-lfs.huggingface.co/peso.bin").is_ok());
        assert!(validate_download_url("http://huggingface.co/peso.bin").is_err());
        assert!(validate_download_url("https://example.com/peso.bin").is_err());
    }
}
