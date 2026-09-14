//! Pruebas del módulo de casos, con énfasis en las NEGATIVAS.
//!
//! Un test que sólo comprueba el camino feliz no dice nada sobre una frontera
//! de seguridad: lo que hay que demostrar es que las llamadas hostiles fallan.
//! Aquí se invoca directamente el núcleo de los comandos —`core_create`,
//! `core_write`, `resolve_case`, `resolve_grant`— con rutas no autorizadas,
//! traversal, manifiestos parciales e identificadores inexistentes.

use super::*;
use std::sync::atomic::{AtomicU64, Ordering};

static COUNTER: AtomicU64 = AtomicU64::new(0);

fn temp_dir(tag: &str) -> PathBuf {
    let n = COUNTER.fetch_add(1, Ordering::SeqCst);
    let base = std::env::temp_dir().join(format!(
        "moldesign_cases_{tag}_{}_{n}",
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_nanos()
    ));
    fs::create_dir_all(&base).unwrap();
    // Se canonicaliza: en Windows el temp suele venir con nombre corto (8.3) y
    // sin esto la comparación de containment fallaría por forma, no por fondo.
    fs::canonicalize(&base).unwrap()
}

const NOW: &str = "2026-08-23T12:00:00.000Z";

fn valid_manifest(id: &str, dir: &Path) -> String {
    initial_manifest(id, "Caso", "explore-hypothesis", NOW, dir)
}

// ── Saneamiento de nombres ───────────────────────────────────────────

#[test]
fn accepts_plain_names() {
    assert!(validate_folder_name("Serie A").is_ok());
    assert!(validate_folder_name("caso-01_final").is_ok());
    assert_eq!(validate_folder_name("trailing ").unwrap(), "trailing");
}

#[test]
fn rejects_traversal_separators_and_absolutes() {
    for bad in [
        "..",
        ".",
        "../escape",
        "a/b",
        "a\\b",
        "..\\..\\Windows",
        "C:\\Windows",
        "/etc/passwd",
        "D:",
        "",
        "   ",
        "trailing.",
        "what?",
        "a\u{0007}b",
        "CON",
        "nul",
        "LPT9",
    ] {
        assert!(
            validate_folder_name(bad).is_err(),
            "debería rechazar {bad:?}"
        );
    }
}

// ── Containment tras canonicalizar ───────────────────────────────────

#[test]
fn ensure_within_accepts_child_and_rejects_sibling() {
    let root = temp_dir("within");
    let parent = root.join("autorizada");
    let outsider = root.join("fuera");
    fs::create_dir_all(&parent).unwrap();
    fs::create_dir_all(&outsider).unwrap();
    let child = parent.join("hijo");
    fs::create_dir_all(&child).unwrap();

    assert!(ensure_within(&parent, &child).is_ok());
    let err = ensure_within(&parent, &outsider).unwrap_err();
    assert!(err.starts_with("UNAUTHORIZED"), "{err}");
    let _ = fs::remove_dir_all(root);
}

#[test]
fn ensure_within_rejects_traversal_even_when_it_exists() {
    let root = temp_dir("traversal");
    let parent = root.join("autorizada");
    fs::create_dir_all(parent.join("sub")).unwrap();
    fs::create_dir_all(root.join("secreto")).unwrap();

    // `autorizada/sub/../../secreto` EXISTE y canonicaliza a root/secreto, que
    // está fuera. Es el caso que una comprobación léxica dejaría pasar.
    let sneaky = parent.join("sub").join("..").join("..").join("secreto");
    let err = ensure_within(&parent, &sneaky).unwrap_err();
    assert!(err.starts_with("UNAUTHORIZED"), "{err}");
    let _ = fs::remove_dir_all(root);
}

#[cfg(unix)]
#[test]
fn ensure_within_rejects_symlink_escaping_the_authorized_dir() {
    let root = temp_dir("symlink");
    let parent = root.join("autorizada");
    let outside = root.join("fuera");
    fs::create_dir_all(&parent).unwrap();
    fs::create_dir_all(&outside).unwrap();
    let link = parent.join("enlace");
    std::os::unix::fs::symlink(&outside, &link).unwrap();

    // El symlink vive DENTRO de la carpeta autorizada pero apunta fuera. Sólo
    // la canonicalización real lo descubre.
    let err = ensure_within(&parent, &link).unwrap_err();
    assert!(err.starts_with("UNAUTHORIZED"), "{err}");
    let _ = fs::remove_dir_all(root);
}

// ── Registro de autorización ─────────────────────────────────────────

#[test]
fn unregistered_case_id_is_rejected() {
    let registry = CaseRegistry::default();
    let err = registry.resolve_case("no-existe").unwrap_err();
    assert!(err.starts_with("UNAUTHORIZED"), "{err}");
}

#[test]
fn unknown_token_is_rejected() {
    let registry = CaseRegistry::default();
    let err = registry.resolve_grant("token-inventado").unwrap_err();
    assert!(err.starts_with("UNAUTHORIZED"), "{err}");
}

#[test]
fn a_token_authorizes_only_its_own_directory() {
    let a = temp_dir("token_a");
    let b = temp_dir("token_b");
    let registry = CaseRegistry::default();
    let token_a = registry.grant(a.clone());

    assert_eq!(registry.resolve_grant(&token_a).unwrap(), a);
    // No hay forma de que un token de `a` devuelva `b`.
    assert_ne!(registry.resolve_grant(&token_a).unwrap(), b);
    let _ = fs::remove_dir_all(a);
    let _ = fs::remove_dir_all(b);
}

#[test]
fn write_refuses_a_manifest_belonging_to_another_case() {
    let dir = temp_dir("crosswrite");
    let case_dir = dir.join("caso");
    fs::create_dir_all(&case_dir).unwrap();
    let mine = valid_manifest("caso-mio", &case_dir);
    write_manifest_atomic(&case_dir, &mine).unwrap();

    // Manifiesto válido, pero de OTRO caso: escribirlo aquí mezclaría dos casos.
    let foreign = valid_manifest("caso-ajeno", &case_dir);
    let err = core_write(&case_dir, "caso-mio", &foreign).unwrap_err();
    assert!(err.starts_with("UNAUTHORIZED"), "{err}");
    // Y el archivo bueno sigue intacto.
    assert!(read_manifest_with_recovery(&case_dir, None)
        .unwrap()
        .0
        .contains("caso-mio"));
    let _ = fs::remove_dir_all(dir);
}

#[test]
fn create_rejects_traversal_folder_names_without_touching_disk() {
    let parent = temp_dir("create_traversal");
    for bad in ["..", "../fuera", "a/b", "C:\\Windows"] {
        let err = core_create(&parent, bad, "Caso", "explore-hypothesis", NOW).unwrap_err();
        assert!(err.starts_with("UNSAFE_NAME"), "{bad}: {err}");
    }
    // Nada se creó dentro de la carpeta autorizada.
    assert_eq!(fs::read_dir(&parent).unwrap().count(), 0);
    let _ = fs::remove_dir_all(parent);
}

#[test]
fn create_rejects_unknown_study_kind() {
    let parent = temp_dir("create_kind");
    let err = core_create(&parent, "caso", "Caso", "inventado", NOW).unwrap_err();
    assert!(err.starts_with("INVALID_MANIFEST"), "{err}");
    let _ = fs::remove_dir_all(parent);
}

#[test]
fn create_builds_the_full_structure_inside_the_authorized_dir() {
    let parent = temp_dir("create_ok");
    let (id, canonical, contents) =
        core_create(&parent, "Serie A", "Serie A", "compare-series", NOW).unwrap();

    assert!(is_contained(&parent, &canonical));
    for sub in CASE_SUBDIRS {
        assert!(canonical.join(sub).is_dir(), "falta {sub}");
    }
    validate_manifest(&contents).unwrap();
    assert_eq!(manifest_id(&contents).unwrap(), id);
    let _ = fs::remove_dir_all(parent);
}

#[test]
fn create_refuses_to_overwrite_an_existing_case() {
    let parent = temp_dir("create_twice");
    core_create(&parent, "caso", "Caso", "explore-hypothesis", NOW).unwrap();
    let err = core_create(&parent, "caso", "Caso", "explore-hypothesis", NOW).unwrap_err();
    assert!(err.starts_with("ALREADY_EXISTS"), "{err}");
    let _ = fs::remove_dir_all(parent);
}

// ── Validación COMPLETA del manifiesto ───────────────────────────────

#[test]
fn manifest_validation_rejects_partial_manifests() {
    let dir = temp_dir("manifest_partial");
    // Antes bastaba con `schemaVersion`: esto se escribía en disco como si
    // fuera un caso.
    assert!(validate_manifest(r#"{"schemaVersion":1}"#).is_err());
    assert!(validate_manifest("{").is_err());
    assert!(validate_manifest("[]").is_err());
    // v5 is current: a partial v5 manifest is invalid for its missing fields,
    // not because the native layer is behind the frontend schema.
    assert!(validate_manifest(r#"{"schemaVersion":4,"id":"a"}"#).is_err());
    assert!(validate_manifest(r#"{"schemaVersion":8,"id":"a"}"#)
        .unwrap_err()
        .starts_with("UNSUPPORTED_VERSION"));

    let good = valid_manifest("id-1", &dir);
    validate_manifest(&good).unwrap();

    // Campo a campo: quitar cualquiera de los obligatorios debe fallar.
    for key in [
        "id",
        "name",
        "createdAt",
        "updatedAt",
        "lastOpenedAt",
        "status",
        "activeView",
        "storage",
        "archived",
        "context",
    ] {
        let mut value: serde_json::Value = serde_json::from_str(&good).unwrap();
        value.as_object_mut().unwrap().remove(key);
        let text = serde_json::to_string(&value).unwrap();
        assert!(
            validate_manifest(&text).is_err(),
            "debería rechazar sin `{key}`"
        );
    }

    // Enumeraciones desconocidas.
    for (key, bad) in [
        ("status", serde_json::json!("casi-listo")),
        ("activeView", serde_json::json!("otra")),
        ("archived", serde_json::json!("no")),
    ] {
        let mut value: serde_json::Value = serde_json::from_str(&good).unwrap();
        value.as_object_mut().unwrap().insert(key.into(), bad);
        assert!(
            validate_manifest(&serde_json::to_string(&value).unwrap()).is_err(),
            "debería rechazar `{key}` inválido"
        );
    }
    let _ = fs::remove_dir_all(dir);
}

#[test]
fn write_rejects_partial_manifest_before_touching_the_good_file() {
    let dir = temp_dir("write_partial");
    let case_dir = dir.join("caso");
    fs::create_dir_all(&case_dir).unwrap();
    let good = valid_manifest("id-1", &case_dir);
    write_manifest_atomic(&case_dir, &good).unwrap();

    assert!(write_manifest_atomic(&case_dir, r#"{"schemaVersion":1}"#).is_err());
    assert!(write_manifest_atomic(&case_dir, "no-json").is_err());
    // El archivo bueno no se tocó.
    assert_eq!(
        read_manifest_with_recovery(&case_dir, None).unwrap().0,
        good
    );
    let _ = fs::remove_dir_all(dir);
}

// ── Escritura atómica y recuperación ─────────────────────────────────

#[test]
fn atomic_write_never_leaves_the_manifest_missing() {
    let dir = temp_dir("atomic");
    let case_dir = dir.join("caso");
    fs::create_dir_all(&case_dir).unwrap();

    let first = valid_manifest("id-a", &case_dir);
    write_manifest_atomic(&case_dir, &first).unwrap();
    assert!(case_dir.join(MANIFEST_FILE).is_file());

    let mut second_value: serde_json::Value = serde_json::from_str(&first).unwrap();
    second_value["name"] = serde_json::json!("Caso actualizado");
    let second = serde_json::to_string_pretty(&second_value).unwrap();
    write_manifest_atomic(&case_dir, &second).unwrap();
    // El destino nunca deja de existir: tras el reemplazo sigue ahí y con el
    // contenido nuevo.
    assert!(case_dir.join(MANIFEST_FILE).is_file());
    assert!(read_manifest_with_recovery(&case_dir, None)
        .unwrap()
        .0
        .contains("Caso actualizado"));
    // Y el anterior quedó respaldado.
    assert!(case_dir.join(BACKUP_FILE).is_file());
    let _ = fs::remove_dir_all(dir);
}

#[test]
fn recovers_from_backup_when_the_manifest_is_corrupt() {
    let dir = temp_dir("recover_corrupt");
    let case_dir = dir.join("caso");
    fs::create_dir_all(&case_dir).unwrap();

    let good = valid_manifest("id-bueno", &case_dir);
    write_manifest_atomic(&case_dir, &good).unwrap();
    // Segunda escritura: crea el backup con el contenido bueno.
    let newer = valid_manifest("id-bueno", &case_dir);
    write_manifest_atomic(&case_dir, &newer).unwrap();

    // Fallo INDUCIDO: el manifiesto queda truncado, como tras un corte.
    fs::write(case_dir.join(MANIFEST_FILE), "{\"schemaVer").unwrap();

    let (text, recovered) = read_manifest_with_recovery(&case_dir, None).unwrap();
    assert!(recovered, "debería haberse recuperado del backup");
    validate_manifest(&text).unwrap();
    // Y se restauró: la siguiente lectura ya es normal.
    let (again, recovered_again) = read_manifest_with_recovery(&case_dir, None).unwrap();
    assert!(!recovered_again);
    assert_eq!(again, text);
    let _ = fs::remove_dir_all(dir);
}

#[test]
fn recovers_from_backup_when_the_manifest_disappears() {
    let dir = temp_dir("recover_missing");
    let case_dir = dir.join("caso");
    fs::create_dir_all(&case_dir).unwrap();
    let good = valid_manifest("id-x", &case_dir);
    write_manifest_atomic(&case_dir, &good).unwrap();
    write_manifest_atomic(&case_dir, &good).unwrap();

    fs::remove_file(case_dir.join(MANIFEST_FILE)).unwrap();
    let (text, recovered) = read_manifest_with_recovery(&case_dir, None).unwrap();
    assert!(recovered);
    assert!(text.contains("id-x"));
    let _ = fs::remove_dir_all(dir);
}

#[test]
fn reports_the_original_error_when_neither_file_is_usable() {
    let dir = temp_dir("recover_none");
    let case_dir = dir.join("caso");
    fs::create_dir_all(&case_dir).unwrap();

    let err = read_manifest_with_recovery(&case_dir, None).unwrap_err();
    assert!(err.starts_with("NOT_FOUND"), "{err}");

    fs::write(case_dir.join(MANIFEST_FILE), "{roto").unwrap();
    fs::write(case_dir.join(BACKUP_FILE), "{tambien roto").unwrap();
    let err = read_manifest_with_recovery(&case_dir, None).unwrap_err();
    assert!(err.starts_with("INVALID_MANIFEST"), "{err}");
    let _ = fs::remove_dir_all(dir);
}

// ── Reemplazo del registro (las dos ramas de `replace_target`) ────────

#[test]
fn replace_target_creates_a_file_that_did_not_exist() {
    let dir = temp_dir("replace_create");
    let src = dir.join("src.tmp");
    let dst = dir.join("dst.json");
    fs::write(&src, b"hola").unwrap();

    replace_target(&src, &dst).unwrap();

    assert!(dst.is_file(), "el destino debería haberse creado");
    assert!(!src.exists(), "el temporal debería haber desaparecido");
    assert_eq!(fs::read(&dst).unwrap(), b"hola");
    let _ = fs::remove_dir_all(dir);
}

#[test]
fn replace_target_overwrites_an_existing_file() {
    let dir = temp_dir("replace_overwrite");
    let src = dir.join("src.tmp");
    let dst = dir.join("dst.json");
    fs::write(&src, b"nuevo").unwrap();
    fs::write(&dst, b"viejo").unwrap();

    replace_target(&src, &dst).unwrap();

    assert_eq!(fs::read(&dst).unwrap(), b"nuevo");
    assert!(!src.exists(), "el temporal debería haberse consumido en el reemplazo");
    let _ = fs::remove_dir_all(dir);
}

// ── Inicializar ──────────────────────────────────────────────────────

#[test]
fn initialize_refuses_a_folder_that_already_has_a_case() {
    let dir = temp_dir("init_twice");
    core_initialize(&dir, "Caso", "explore-hypothesis", NOW).unwrap();
    let err = core_initialize(&dir, "Caso", "explore-hypothesis", NOW).unwrap_err();
    assert!(err.starts_with("ALREADY_EXISTS"), "{err}");
    let _ = fs::remove_dir_all(dir);
}

#[test]
fn initialize_creates_the_structure_in_place() {
    let dir = temp_dir("init_ok");
    let (id, contents) = core_initialize(&dir, "En sitio", "review-pose", NOW).unwrap();
    validate_manifest(&contents).unwrap();
    assert_eq!(manifest_id(&contents).unwrap(), id);
    for sub in CASE_SUBDIRS {
        assert!(dir.join(sub).is_dir());
    }
    let _ = fs::remove_dir_all(dir);
}

// ── Varios ───────────────────────────────────────────────────────────

#[test]
fn ids_are_distinct_and_uuid_shaped() {
    let a = new_id();
    let b = new_id();
    assert_ne!(a, b);
    assert_eq!(a.len(), 36);
}

#[test]
fn study_kinds_match_the_frontend_union() {
    for kind in [
        "explore-hypothesis",
        "compare-series",
        "review-pose",
        "prepare-evidence",
    ] {
        assert!(validate_study_kind(kind).is_ok());
    }
    assert!(validate_study_kind("otra-cosa").is_err());
}

// ── Ciclo de vida completo, extremo a extremo ────────────────────────
//
// Es el sustituto verificable del "smoke test desde la aplicación": ejecuta el
// MISMO núcleo que corren los comandos —`core_create`, `read_manifest_with_recovery`,
// `core_write`, el registro de autorización— en la secuencia crear → cerrar →
// reabrir. Lo que NO cubre es el diálogo nativo ni el webview, que necesitan
// una GUI.

#[test]
fn full_lifecycle_create_close_reopen() {
    let parent = temp_dir("lifecycle");
    // Registro REAL con su archivo: sin atajos de test, porque lo que se quiere
    // comprobar es justamente que la autorización sobrevive al cierre.
    let store = parent.join("registro.json");
    let registry = CaseRegistry::load_from(Some(store.clone()));

    // 1. El usuario elige carpeta: el diálogo canonicaliza y concede un token.
    let token = registry.grant(parent.clone());

    // 2. CREAR.
    let authorized = registry.resolve_grant(&token).unwrap();
    let (id, case_dir, manifest) =
        core_create(&authorized, "Serie A", "Serie A", "compare-series", NOW).unwrap();
    registry.register(&id, case_dir.clone()).unwrap();
    validate_manifest(&manifest).unwrap();
    assert!(case_dir.join(MANIFEST_FILE).is_file());
    for sub in CASE_SUBDIRS {
        assert!(case_dir.join(sub).is_dir());
    }

    // 3. Trabajar: se edita el contexto y se escribe por `case_id`.
    let mut value: serde_json::Value = serde_json::from_str(&manifest).unwrap();
    value["context"]["question"] = serde_json::json!("¿Discrimina la serie?");
    value["updatedAt"] = serde_json::json!("2026-08-23T13:00:00.000Z");
    let edited = serde_json::to_string_pretty(&value).unwrap();
    let dir = registry.resolve_case(&id).unwrap();
    core_write(&dir, &id, &edited).unwrap();

    // 4. CERRAR: la instancia se destruye. Se vuelve a cargar DESDE DISCO, que
    // es lo que hace el arranque de la aplicación.
    drop(registry);
    let closed = CaseRegistry::load_from(Some(store.clone()));
    assert!(
        closed.resolve_grant(&token).is_err(),
        "el token de sesión no debe sobrevivir al cierre"
    );

    // 5. REABRIR por `case_id`, como haría el arranque tras cargar el registro.
    let dir = closed.resolve_case(&id).unwrap();
    let (reopened, recovered) = read_manifest_with_recovery(&dir, None).unwrap();
    assert!(!recovered);
    assert_eq!(manifest_id(&reopened).unwrap(), id);
    assert!(
        reopened.contains("¿Discrimina la serie?"),
        "se perdió la edición"
    );

    // 6. Y un `case_id` que nunca se autorizó sigue rechazado.
    assert!(closed
        .resolve_case("otro-id")
        .unwrap_err()
        .starts_with("UNAUTHORIZED"));

    let _ = fs::remove_dir_all(parent);
}

#[test]
fn reopening_after_a_crash_recovers_the_last_good_manifest() {
    let parent = temp_dir("lifecycle_crash");
    let registry = CaseRegistry::load_from(Some(parent.join("registro.json")));
    let token = registry.grant(parent.clone());
    let authorized = registry.resolve_grant(&token).unwrap();
    let (id, case_dir, manifest) =
        core_create(&authorized, "Con corte", "Con corte", "review-pose", NOW).unwrap();
    registry.register(&id, case_dir.clone()).unwrap();

    // Una segunda escritura deja el backup con contenido bueno.
    core_write(&case_dir, &id, &manifest).unwrap();
    // CORTE simulado a mitad de la siguiente escritura.
    fs::write(case_dir.join(MANIFEST_FILE), "{\"schemaVer").unwrap();

    let dir = registry.resolve_case(&id).unwrap();
    let (recovered_text, recovered) = read_manifest_with_recovery(&dir, None).unwrap();
    assert!(recovered, "debería haberse recuperado del backup");
    assert_eq!(manifest_id(&recovered_text).unwrap(), id);

    let _ = fs::remove_dir_all(parent);
}

// ── R2: registro durable con ruta inyectable ─────────────────────────

#[test]
fn registry_survives_being_destroyed_and_reloaded() {
    let home = temp_dir("registry_roundtrip");
    let store = home.join("authorized_cases.json");
    let case_dir = home.join("caso");
    fs::create_dir_all(&case_dir).unwrap();
    let case_dir = fs::canonicalize(&case_dir).unwrap();

    // 1. Persistir.
    let first = CaseRegistry::load_from(Some(store.clone()));
    first.register("id-persistente", case_dir.clone()).unwrap();
    assert!(store.is_file(), "el registro no llegó a disco");

    // 2. DESTRUIR la instancia. Es lo que pasa al cerrar la aplicación.
    drop(first);

    // 3. Cargar de nuevo y resolver el MISMO case_id.
    let second = CaseRegistry::load_from(Some(store.clone()));
    assert_eq!(second.resolve_case("id-persistente").unwrap(), case_dir);
    assert_eq!(second.health(), RegistryHealth::Ok);
    // Y un id que nunca se registró sigue rechazado.
    assert!(second
        .resolve_case("otro")
        .unwrap_err()
        .starts_with("UNAUTHORIZED"));

    let _ = fs::remove_dir_all(home);
}

#[test]
fn registry_reports_failure_when_it_cannot_persist() {
    let home = temp_dir("registry_fail");
    // Fallo INDUCIDO: la ruta del registro es un DIRECTORIO, así que escribir
    // el archivo no puede funcionar. No se usa ningún atajo de test.
    let store = home.join("bloqueado");
    fs::create_dir_all(&store).unwrap();

    let registry = CaseRegistry::load_from(Some(store.clone()));
    let err = registry.register("id-1", home.clone()).unwrap_err();
    assert!(err.starts_with("IO_ERROR"), "{err}");
    // Y se REVIERTE: no puede quedar autorizado en memoria algo que el
    // siguiente arranque no va a encontrar.
    assert!(registry
        .resolve_case("id-1")
        .unwrap_err()
        .starts_with("UNAUTHORIZED"));

    let _ = fs::remove_dir_all(home);
}

#[test]
fn registry_recovers_from_its_backup_and_declares_it() {
    let home = temp_dir("registry_recover");
    let store = home.join("authorized_cases.json");
    let case_dir = home.join("caso");
    fs::create_dir_all(&case_dir).unwrap();
    let case_dir = fs::canonicalize(&case_dir).unwrap();

    let first = CaseRegistry::load_from(Some(store.clone()));
    first.register("id-a", case_dir.clone()).unwrap();
    // Segunda escritura: deja el backup con contenido bueno.
    first.register("id-a", case_dir.clone()).unwrap();
    drop(first);
    assert!(backup_of(&store).is_file());

    // El principal se corrompe.
    fs::write(&store, "{ roto").unwrap();
    let recovered = CaseRegistry::load_from(Some(store.clone()));
    assert!(
        matches!(
            recovered.health(),
            RegistryHealth::RecoveredFromBackup { .. }
        ),
        "debería declararse recuperado, y no como estado sano"
    );
    assert_eq!(recovered.resolve_case("id-a").unwrap(), case_dir);

    let _ = fs::remove_dir_all(home);
}

#[test]
fn persisting_over_a_corrupt_registry_never_overwrites_its_good_backup() {
    let home = temp_dir("registry_backup_safety");
    let store = home.join("authorized_cases.json");
    let backup = backup_of(&store);
    let old_case_dir = home.join("caso-anterior");
    let new_case_dir = home.join("caso-nuevo");
    fs::create_dir_all(&old_case_dir).unwrap();
    fs::create_dir_all(&new_case_dir).unwrap();

    let mut old_cases = HashMap::new();
    old_cases.insert(
        "id-anterior".to_string(),
        old_case_dir.to_string_lossy().to_string(),
    );
    let good_backup = serde_json::to_string_pretty(&PersistedRegistry {
        version: 1,
        cases: old_cases,
    })
    .unwrap();
    write_registry_atomic(&backup, &good_backup).unwrap();
    let backup_before = fs::read(&backup).unwrap();
    fs::write(&store, "{ registro roto").unwrap();

    // Se fuerza la ruta directa de persistencia para reproducir el caso que
    // antes copiaba el principal corrupto sobre la única copia recuperable.
    let registry = CaseRegistry::default();
    *registry.store_path.lock().unwrap() = Some(store.clone());
    registry
        .cases
        .lock()
        .unwrap()
        .insert("id-nuevo".into(), new_case_dir);
    registry.persist().unwrap();

    assert_eq!(fs::read(&backup).unwrap(), backup_before);
    let primary = read_registry_file(&store).unwrap();
    assert!(primary.cases.contains_key("id-nuevo"));
    let _ = fs::remove_dir_all(home);
}

#[test]
fn registry_rejects_an_unsupported_version() {
    let home = temp_dir("registry_version");
    let store = home.join("authorized_cases.json");
    fs::write(&store, r#"{"version":2,"cases":{}}"#).unwrap();

    let err = match read_registry_file(&store) {
        Ok(_) => panic!("una versión futura no puede abrirse como v1"),
        Err(error) => error,
    };
    assert!(err.starts_with("UNSUPPORTED_VERSION"), "{err}");
    let loaded = CaseRegistry::load_from(Some(store));
    assert!(matches!(loaded.health(), RegistryHealth::Corrupted { .. }));
    let _ = fs::remove_dir_all(home);
}

#[test]
fn a_failed_registry_restoration_keeps_the_backup_readable() {
    let home = temp_dir("registry_restore_fail");
    let store = home.join("registro-bloqueado");
    let backup = backup_of(&store);
    // El destino principal es un directorio: se puede detectar como ilegible,
    // pero no reemplazarlo por un archivo.
    fs::create_dir_all(&store).unwrap();
    let good = serde_json::to_string_pretty(&PersistedRegistry {
        version: 1,
        cases: HashMap::new(),
    })
    .unwrap();
    write_registry_atomic(&backup, &good).unwrap();
    let backup_before = fs::read(&backup).unwrap();

    let loaded = CaseRegistry::load_from(Some(store));
    let detail = match loaded.health() {
        RegistryHealth::RecoveredFromBackup { detail } => detail,
        other => panic!("salud inesperada: {other:?}"),
    };
    assert!(detail.contains("no pudo restaurarse"), "{detail}");
    assert_eq!(fs::read(&backup).unwrap(), backup_before);
    assert!(read_registry_file(&backup).is_ok());
    let _ = fs::remove_dir_all(home);
}

#[test]
fn forget_reverts_if_it_cannot_persist() {
    let home = temp_dir("forget_fail");
    let store = home.join("authorized_cases.json");
    let case_dir = home.join("caso");
    fs::create_dir_all(&case_dir).unwrap();
    let case_dir = fs::canonicalize(&case_dir).unwrap();

    let registry = CaseRegistry::load_from(Some(store.clone()));
    registry.register("id-1", case_dir.clone()).unwrap();

    // Ahora se hace imposible escribir: se sustituye el archivo por un
    // directorio con el mismo nombre.
    fs::remove_file(&store).unwrap();
    fs::create_dir_all(&store).unwrap();

    assert!(registry.forget("id-1").is_err());
    // Sigue autorizado: si se hubiera olvidado sólo en memoria, el usuario
    // vería desaparecer el caso y al reiniciar volvería a aparecer.
    assert_eq!(registry.resolve_case("id-1").unwrap(), case_dir);

    let _ = fs::remove_dir_all(home);
}

// ── R2: recuperación segura del manifiesto ───────────────────────────

#[test]
fn a_corrupt_primary_never_overwrites_a_good_backup() {
    let dir = temp_dir("backup_safety");
    let case_dir = dir.join("caso");
    fs::create_dir_all(&case_dir).unwrap();

    let good = valid_manifest("id-bueno", &case_dir);
    write_manifest_atomic(&case_dir, &good).unwrap();
    write_manifest_atomic(&case_dir, &good).unwrap(); // crea el backup

    // El principal se corrompe.
    fs::write(case_dir.join(MANIFEST_FILE), "{roto").unwrap();
    // Y ahora se ESCRIBE otra vez. Antes, el respaldo previo copiaba el
    // principal a ciegas y machacaba el último manifiesto bueno.
    let newer = valid_manifest("id-bueno", &case_dir);
    write_manifest_atomic(&case_dir, &newer).unwrap();

    let backup = fs::read_to_string(case_dir.join(BACKUP_FILE)).unwrap();
    validate_manifest(&backup).expect("el backup debe seguir siendo válido");
    assert!(!backup.contains("{roto"));

    let _ = fs::remove_dir_all(dir);
}

#[test]
fn a_good_copy_survives_a_failed_restoration() {
    let dir = temp_dir("restore_fail");
    let case_dir = dir.join("caso");
    fs::create_dir_all(&case_dir).unwrap();
    let good = valid_manifest("id-x", &case_dir);
    write_manifest_atomic(&case_dir, &good).unwrap();
    write_manifest_atomic(&case_dir, &good).unwrap();

    // Se corrompe el principal y se hace IMPOSIBLE restaurarlo: `case.json`
    // pasa a ser un directorio, así que la escritura fallará.
    fs::remove_file(case_dir.join(MANIFEST_FILE)).unwrap();
    fs::create_dir_all(case_dir.join(MANIFEST_FILE)).unwrap();

    // Aun así se puede leer: se devuelve el contenido del backup.
    let (text, recovered) = read_manifest_with_recovery(&case_dir, None).unwrap();
    assert!(recovered);
    validate_manifest(&text).unwrap();
    // Y el backup SIGUE en disco: nunca se pasa por un estado sin copia buena.
    assert!(case_dir.join(BACKUP_FILE).is_file());
    validate_manifest(&fs::read_to_string(case_dir.join(BACKUP_FILE)).unwrap()).unwrap();

    let _ = fs::remove_dir_all(dir);
}

// ── R2: identidad ────────────────────────────────────────────────────

#[test]
fn core_read_rejects_a_manifest_from_another_case() {
    let dir = temp_dir("identity");
    let case_dir = dir.join("caso");
    fs::create_dir_all(&case_dir).unwrap();
    // La carpeta está autorizada como `id-esperado` pero contiene otro caso:
    // pasa si se reutiliza una carpeta o se copia un `case.json`.
    write_manifest_atomic(&case_dir, &valid_manifest("id-intruso", &case_dir)).unwrap();

    let err = core_read(&case_dir, "id-esperado").unwrap_err();
    assert!(err.starts_with("UNAUTHORIZED"), "{err}");
    // Y con el id correcto sí lee.
    assert!(core_read(&case_dir, "id-intruso").is_ok());

    let _ = fs::remove_dir_all(dir);
}

// ── R2: reparar de verdad ────────────────────────────────────────────

#[test]
fn repair_restores_from_backup_and_verifies_it() {
    let dir = temp_dir("repair");
    let case_dir = dir.join("caso");
    fs::create_dir_all(&case_dir).unwrap();
    let good = valid_manifest("id-r", &case_dir);
    write_manifest_atomic(&case_dir, &good).unwrap();
    write_manifest_atomic(&case_dir, &good).unwrap();

    fs::write(case_dir.join(MANIFEST_FILE), "{roto").unwrap();
    let repaired = core_repair(&case_dir, "id-r").unwrap();
    validate_manifest(&repaired).unwrap();
    assert_eq!(manifest_id(&repaired).unwrap(), "id-r");

    let _ = fs::remove_dir_all(dir);
}

#[test]
fn repair_does_not_replace_the_right_backup_with_a_foreign_primary() {
    let dir = temp_dir("repair_foreign_primary");
    let case_dir = dir.join("caso");
    fs::create_dir_all(&case_dir).unwrap();

    // La carpeta tiene un principal válido, pero de otro caso, y un backup
    // válido del caso esperado. Reparar debe usar el segundo sin rotar el
    // contenido ajeno sobre él.
    let foreign = valid_manifest("id-ajeno", &case_dir);
    write_manifest_atomic(&case_dir, &foreign).unwrap();
    let mine = valid_manifest("id-mio", &case_dir);
    fs::write(case_dir.join(BACKUP_FILE), &mine).unwrap();
    let backup_before = fs::read(case_dir.join(BACKUP_FILE)).unwrap();

    let repaired = core_repair(&case_dir, "id-mio").unwrap();
    assert_eq!(manifest_id(&repaired).unwrap(), "id-mio");
    assert_eq!(fs::read(case_dir.join(BACKUP_FILE)).unwrap(), backup_before);
    assert_eq!(
        manifest_id(&fs::read_to_string(case_dir.join(MANIFEST_FILE)).unwrap()).unwrap(),
        "id-mio"
    );
    let _ = fs::remove_dir_all(dir);
}

#[test]
fn repair_refuses_when_there_is_nothing_to_restore_from() {
    let dir = temp_dir("repair_none");
    let case_dir = dir.join("caso");
    fs::create_dir_all(&case_dir).unwrap();
    fs::write(case_dir.join(MANIFEST_FILE), "{roto").unwrap();

    // Sin backup no hay nada que reparar, y se dice. Un «Reparar» que no repara
    // nada es peor que no ofrecerlo.
    let err = core_repair(&case_dir, "cualquiera").unwrap_err();
    assert!(err.starts_with("NOT_FOUND"), "{err}");

    let _ = fs::remove_dir_all(dir);
}

// ── R2: activeRun en el manifiesto ───────────────────────────────────

#[test]
fn manifest_accepts_a_case_with_an_active_run() {
    let dir = temp_dir("active_run");
    let good = valid_manifest("id-run", &dir);
    let mut value: serde_json::Value = serde_json::from_str(&good).unwrap();
    value["activeRun"] = serde_json::json!({
        "taskId": "task-123",
        "executionState": "running",
        "startedAt": "2026-08-23T12:00:00.000Z",
    });
    // Rust no valida el interior de `activeRun` —eso lo hace el modelo de
    // TypeScript—, pero un manifiesto con corrida debe seguir siendo válido y
    // por tanto escribible.
    validate_manifest(&serde_json::to_string(&value).unwrap()).unwrap();
    let _ = fs::remove_dir_all(dir);
}

// ── R3: identidad en relocalización, reparación y recuperación ───────

#[test]
fn relocating_to_the_wrong_case_folder_leaves_the_registry_untouched() {
    let home = temp_dir("relocate_wrong");
    let store = home.join("registro.json");
    let correcta = home.join("correcta");
    let ajena = home.join("ajena");
    fs::create_dir_all(&correcta).unwrap();
    fs::create_dir_all(&ajena).unwrap();
    let correcta = fs::canonicalize(&correcta).unwrap();
    let ajena = fs::canonicalize(&ajena).unwrap();

    write_manifest_atomic(&correcta, &valid_manifest("id-mio", &correcta)).unwrap();
    write_manifest_atomic(&ajena, &valid_manifest("id-ajeno", &ajena)).unwrap();

    let registry = CaseRegistry::load_from(Some(store.clone()));
    registry.register("id-mio", correcta.clone()).unwrap();
    let antes = fs::read(&store).unwrap();

    // El usuario elige por error la carpeta del OTRO caso.
    let err = core_verify_identity(&ajena, "id-mio").unwrap_err();
    assert!(err.starts_with("UNAUTHORIZED"), "{err}");

    // El registro sigue apuntando a la carpeta buena y el archivo no ha
    // cambiado ni un byte: la comprobación va ANTES de tocar nada.
    assert_eq!(registry.resolve_case("id-mio").unwrap(), correcta);
    assert_eq!(fs::read(&store).unwrap(), antes);

    let _ = fs::remove_dir_all(home);
}

#[test]
fn relocating_to_the_right_folder_moves_the_mapping() {
    let home = temp_dir("relocate_ok");
    let store = home.join("registro.json");
    let vieja = home.join("vieja");
    let nueva = home.join("nueva");
    fs::create_dir_all(&vieja).unwrap();
    fs::create_dir_all(&nueva).unwrap();
    let vieja = fs::canonicalize(&vieja).unwrap();
    let nueva = fs::canonicalize(&nueva).unwrap();
    write_manifest_atomic(&nueva, &valid_manifest("id-movido", &nueva)).unwrap();

    let registry = CaseRegistry::load_from(Some(store));
    registry.register("id-movido", vieja).unwrap();

    core_verify_identity(&nueva, "id-movido").unwrap();
    registry.register("id-movido", nueva.clone()).unwrap();
    assert_eq!(registry.resolve_case("id-movido").unwrap(), nueva);

    let _ = fs::remove_dir_all(home);
}

#[test]
fn repair_refuses_a_backup_belonging_to_another_case() {
    let dir = temp_dir("repair_foreign");
    let case_dir = dir.join("caso");
    fs::create_dir_all(&case_dir).unwrap();

    // Manifiesto bueno del caso propio…
    let mine = valid_manifest("id-mio", &case_dir);
    write_manifest_atomic(&case_dir, &mine).unwrap();
    // …y un backup AJENO, como si alguien hubiera copiado un `.bak` de otra
    // carpeta.
    fs::write(
        case_dir.join(BACKUP_FILE),
        valid_manifest("id-ajeno", &case_dir),
    )
    .unwrap();
    let backup_antes = fs::read(case_dir.join(BACKUP_FILE)).unwrap();
    let principal_antes = fs::read(case_dir.join(MANIFEST_FILE)).unwrap();

    let err = core_repair(&case_dir, "id-mio").unwrap_err();
    assert!(err.starts_with("UNAUTHORIZED"), "{err}");
    // NADA se ha tocado: ni el principal ni el backup.
    assert_eq!(
        fs::read(case_dir.join(MANIFEST_FILE)).unwrap(),
        principal_antes
    );
    assert_eq!(fs::read(case_dir.join(BACKUP_FILE)).unwrap(), backup_antes);

    let _ = fs::remove_dir_all(dir);
}

#[test]
fn recovery_never_restores_a_backup_from_another_case() {
    let dir = temp_dir("recover_foreign");
    let case_dir = dir.join("caso");
    fs::create_dir_all(&case_dir).unwrap();

    // El principal se corrompe y el backup es de OTRO caso.
    fs::write(case_dir.join(MANIFEST_FILE), "{roto").unwrap();
    fs::write(
        case_dir.join(BACKUP_FILE),
        valid_manifest("id-ajeno", &case_dir),
    )
    .unwrap();
    let principal_antes = fs::read(case_dir.join(MANIFEST_FILE)).unwrap();
    let backup_antes = fs::read(case_dir.join(BACKUP_FILE)).unwrap();

    // Se rechaza ANTES de escribir. Restaurar y rechazar después habría dejado
    // el `case.json` del caso ajeno dentro de esta carpeta.
    let err = core_read(&case_dir, "id-mio").unwrap_err();
    assert!(err.starts_with("UNAUTHORIZED"), "{err}");
    assert_eq!(
        fs::read(case_dir.join(MANIFEST_FILE)).unwrap(),
        principal_antes
    );
    assert_eq!(fs::read(case_dir.join(BACKUP_FILE)).unwrap(), backup_antes);

    let _ = fs::remove_dir_all(dir);
}

// ── R3: salud del registro ───────────────────────────────────────────

#[test]
fn a_real_first_run_is_not_the_same_as_a_corrupt_registry() {
    let home = temp_dir("health_first");
    let store = home.join("registro.json");

    // Ni principal ni backup: primer arranque de verdad.
    let fresh = CaseRegistry::load_from(Some(store.clone()));
    assert_eq!(fresh.health(), RegistryHealth::FirstRun);

    // Ahora los DOS existen y ninguno se puede leer. La lista sigue vacía, pero
    // esa lista vacía NO es un estado sano y hay que poder distinguirlo.
    fs::write(&store, "{ roto").unwrap();
    fs::write(backup_of(&store), "tampoco json").unwrap();
    let broken = CaseRegistry::load_from(Some(store.clone()));
    assert!(
        matches!(broken.health(), RegistryHealth::Corrupted { .. }),
        "un registro ilegible no puede presentarse como primer arranque"
    );

    let _ = fs::remove_dir_all(home);
}

#[test]
fn recovering_the_registry_restores_the_primary_and_keeps_the_backup() {
    let home = temp_dir("health_restore");
    let store = home.join("registro.json");
    let case_dir = home.join("caso");
    fs::create_dir_all(&case_dir).unwrap();
    let case_dir = fs::canonicalize(&case_dir).unwrap();

    let first = CaseRegistry::load_from(Some(store.clone()));
    first.register("id-a", case_dir.clone()).unwrap();
    first.register("id-a", case_dir.clone()).unwrap(); // deja backup bueno
    drop(first);

    fs::write(&store, "{ roto").unwrap();
    let recovered = CaseRegistry::load_from(Some(store.clone()));
    assert!(matches!(
        recovered.health(),
        RegistryHealth::RecoveredFromBackup { .. }
    ));
    // El principal quedó restaurado y legible…
    assert!(read_registry_file(&store).is_ok());
    // …y el backup bueno sigue ahí.
    assert!(read_registry_file(&backup_of(&store)).is_ok());
    assert_eq!(recovered.resolve_case("id-a").unwrap(), case_dir);

    let _ = fs::remove_dir_all(home);
}

// ── R3: contrato del manifiesto, campo por campo ─────────────────────

#[test]
fn active_run_contract_matches_typescript() {
    let dir = temp_dir("run_contract");
    let good = valid_manifest("id-run", &dir);
    let with_run = |run: serde_json::Value| {
        let mut value: serde_json::Value = serde_json::from_str(&good).unwrap();
        value["activeRun"] = run;
        serde_json::to_string(&value).unwrap()
    };

    // Válida.
    validate_manifest(&with_run(serde_json::json!({
        "taskId": "t-1",
        "executionState": "running",
        "startedAt": "2026-08-23T12:00:00.000Z",
        "lastKnownProgress": 40,
        "lastError": "algo",
    })))
    .unwrap();

    // Campo por campo.
    for (nombre, run) in [
        (
            "sin taskId",
            serde_json::json!({"executionState":"running","startedAt":"2026-08-23T12:00:00.000Z"}),
        ),
        (
            "taskId vacío",
            serde_json::json!({"taskId":"","executionState":"running","startedAt":"2026-08-23T12:00:00.000Z"}),
        ),
        (
            "taskId no cadena",
            serde_json::json!({"taskId":7,"executionState":"running","startedAt":"2026-08-23T12:00:00.000Z"}),
        ),
        (
            "sin executionState",
            serde_json::json!({"taskId":"t","startedAt":"2026-08-23T12:00:00.000Z"}),
        ),
        (
            "executionState desconocido",
            serde_json::json!({"taskId":"t","executionState":"corriendo","startedAt":"2026-08-23T12:00:00.000Z"}),
        ),
        (
            "sin startedAt",
            serde_json::json!({"taskId":"t","executionState":"running"}),
        ),
        (
            "startedAt no es fecha",
            serde_json::json!({"taskId":"t","executionState":"running","startedAt":"ayer"}),
        ),
        (
            "progreso no numérico",
            serde_json::json!({"taskId":"t","executionState":"running","startedAt":"2026-08-23T12:00:00.000Z","lastKnownProgress":"medio"}),
        ),
        (
            "lastError no cadena",
            serde_json::json!({"taskId":"t","executionState":"running","startedAt":"2026-08-23T12:00:00.000Z","lastError":5}),
        ),
        ("activeRun no es objeto", serde_json::json!("t-1")),
    ] {
        assert!(
            validate_manifest(&with_run(run)).is_err(),
            "debería rechazar: {nombre}"
        );
    }

    // AUSENTE sigue siendo válido: los casos de R1 no tienen esta clave y
    // tienen que poder abrirse.
    validate_manifest(&good).unwrap();
    let mut sin_run: serde_json::Value = serde_json::from_str(&good).unwrap();
    sin_run["activeRun"] = serde_json::Value::Null;
    validate_manifest(&serde_json::to_string(&sin_run).unwrap()).unwrap();

    let _ = fs::remove_dir_all(dir);
}

#[test]
fn the_run_book_is_validated_row_by_row() {
    // El libro de corridas (v7) sustituye a `activeRun`. Esta frontera es la
    // que decide si el archivo LLEGA A ESCRIBIRSE: una fila rota que se dejara
    // pasar aquí reventaría después en TypeScript, con el archivo ya en disco.
    let dir = temp_dir("run_book");
    let good = valid_manifest("id-book", &dir);
    let with_runs = |runs: serde_json::Value| {
        let mut value: serde_json::Value = serde_json::from_str(&good).unwrap();
        value["runs"] = runs;
        serde_json::to_string(&value).unwrap()
    };

    // Un libro con varias corridas, con y sin metadatos de fila.
    validate_manifest(&with_runs(serde_json::json!([
        {
            "taskId": "t-1",
            "executionState": "completed",
            "startedAt": "2026-08-23T12:00:00.000Z",
            "finishedAt": "2026-08-23T12:04:00.000Z",
            "ligandSmiles": "CCO",
            "affinityKcal": -7.4,
            "protocol": {
                "dockingEngine": "vina",
                "exhaustiveness": 8,
                "numPoses": 9,
                "conformers": 1,
            },
        },
        {
            "taskId": "t-2",
            "executionState": "running",
            "startedAt": "2026-08-23T13:00:00.000Z",
        },
    ])))
    .unwrap();

    for (nombre, runs) in [
        (
            "runs no es lista",
            serde_json::json!({"taskId": "t-1"}),
        ),
        (
            "fila no es objeto",
            serde_json::json!(["t-1"]),
        ),
        (
            "fila sin taskId",
            serde_json::json!([{"executionState":"running","startedAt":"2026-08-23T12:00:00.000Z"}]),
        ),
        (
            "estado desconocido",
            serde_json::json!([{"taskId":"t","executionState":"corriendo","startedAt":"2026-08-23T12:00:00.000Z"}]),
        ),
        (
            "finishedAt no es fecha",
            serde_json::json!([{"taskId":"t","executionState":"completed","startedAt":"2026-08-23T12:00:00.000Z","finishedAt":"luego"}]),
        ),
        (
            "afinidad no numérica",
            serde_json::json!([{"taskId":"t","executionState":"completed","startedAt":"2026-08-23T12:00:00.000Z","affinityKcal":"buena"}]),
        ),
        (
            "protocolo sin motor",
            serde_json::json!([{"taskId":"t","executionState":"completed","startedAt":"2026-08-23T12:00:00.000Z","protocol":{"exhaustiveness":8,"numPoses":9,"conformers":1}}]),
        ),
        (
            "exhaustiveness cero",
            serde_json::json!([{"taskId":"t","executionState":"completed","startedAt":"2026-08-23T12:00:00.000Z","protocol":{"dockingEngine":"vina","exhaustiveness":0,"numPoses":9,"conformers":1}}]),
        ),
        (
            // Un libro con la misma corrida dos veces no permitiría decir cuál
            // de las dos es la buena.
            "taskId repetido",
            serde_json::json!([
                {"taskId":"t","executionState":"completed","startedAt":"2026-08-23T12:00:00.000Z"},
                {"taskId":"t","executionState":"failed","startedAt":"2026-08-23T13:00:00.000Z"},
            ]),
        ),
    ] {
        assert!(
            validate_manifest(&with_runs(runs)).is_err(),
            "debería rechazar: {nombre}"
        );
    }

    // AUSENTE y VACÍO son los dos legítimos: un caso recién creado no ha
    // lanzado nada.
    validate_manifest(&good).unwrap();
    validate_manifest(&with_runs(serde_json::json!([]))).unwrap();
    validate_manifest(&with_runs(serde_json::Value::Null)).unwrap();

    let _ = fs::remove_dir_all(dir);
}

#[test]
fn a_v6_manifest_with_its_single_run_still_opens() {
    // La migración a v7 la hace TypeScript al abrir. Rust sólo tiene que dejar
    // pasar el v6 tal como está en disco: rechazarlo aquí dejaría inaccesibles
    // todos los casos existentes.
    let dir = temp_dir("v6_run");
    let good = valid_manifest("id-v6", &dir);
    let mut value: serde_json::Value = serde_json::from_str(&good).unwrap();
    value["schemaVersion"] = serde_json::json!(6);
    value["activeRun"] = serde_json::json!({
        "taskId": "t-legacy",
        "executionState": "completed",
        "startedAt": "2026-08-23T12:00:00.000Z",
    });
    validate_manifest(&serde_json::to_string(&value).unwrap()).unwrap();

    // Y su `activeRun` se sigue validando con el mismo contrato.
    value["activeRun"] = serde_json::json!({"taskId": "t", "executionState": "corriendo"});
    assert!(validate_manifest(&serde_json::to_string(&value).unwrap()).is_err());

    let _ = fs::remove_dir_all(dir);
}

#[test]
fn dates_are_validated_as_dates_not_just_as_strings() {
    let dir = temp_dir("dates");
    let good = valid_manifest("id-f", &dir);
    for key in ["createdAt", "updatedAt", "lastOpenedAt"] {
        let mut value: serde_json::Value = serde_json::from_str(&good).unwrap();
        value[key] = serde_json::json!("ayer por la tarde");
        let err = validate_manifest(&serde_json::to_string(&value).unwrap()).unwrap_err();
        assert!(err.contains("ISO 8601"), "{key}: {err}");
    }
    let _ = fs::remove_dir_all(dir);
}

#[test]
fn context_text_fields_must_be_strings_when_present() {
    let dir = temp_dir("context_contract");
    let good = valid_manifest("id-c", &dir);
    for key in [
        "question",
        "decision",
        "systemRationale",
        "controls",
        "assumptions",
        "uncertainties",
        "notes",
    ] {
        let mut value: serde_json::Value = serde_json::from_str(&good).unwrap();
        value["context"][key] = serde_json::json!(42);
        assert!(
            validate_manifest(&serde_json::to_string(&value).unwrap()).is_err(),
            "debería rechazar `context.{key}` numérico"
        );
    }
    // Ausentes: válido. La ausencia es un estado legítimo del producto.
    validate_manifest(&good).unwrap();
    let _ = fs::remove_dir_all(dir);
}

// ── Esquema v2: modos en vez de secciones ────────────────────────────

#[test]
fn a_new_case_lands_on_evaluation_not_on_a_questionnaire() {
    let dir = temp_dir("v2_initial");
    let text = initial_manifest("id-v2", "Caso", "explore-hypothesis", NOW, &dir);
    let value: serde_json::Value = serde_json::from_str(&text).unwrap();

    assert_eq!(value["schemaVersion"], 7);
    assert_eq!(value["ownerUserId"], "test-owner");
    assert_eq!(value["activeView"], "evaluation");
    // La clave vieja NO se escribe: dos nombres para lo mismo obligarían a
    // decidir cuál gana en cada lectura.
    assert!(value.get("activeSection").is_none());
    validate_manifest(&text).unwrap();

    let _ = fs::remove_dir_all(dir);
}

#[test]
fn v1_manifests_keep_opening() {
    // Un caso guardado por el build anterior sigue siendo válido: rechazarlo
    // aquí lo dejaría inaccesible aunque el frontend sepa migrarlo.
    let dir = temp_dir("v1_compat");
    let mut value: serde_json::Value = serde_json::from_str(&initial_manifest(
        "id-v1",
        "Caso",
        "explore-hypothesis",
        NOW,
        &dir,
    ))
    .unwrap();
    let obj = value.as_object_mut().unwrap();
    obj.insert("schemaVersion".into(), serde_json::json!(1));
    obj.remove("activeView");
    obj.insert("activeSection".into(), serde_json::json!("context"));

    validate_manifest(&serde_json::to_string(&value).unwrap()).unwrap();
    let _ = fs::remove_dir_all(dir);
}

#[test]
fn each_version_is_validated_against_its_own_key() {
    let dir = temp_dir("v2_keys");
    let base: serde_json::Value = serde_json::from_str(&initial_manifest(
        "id-x",
        "Caso",
        "explore-hypothesis",
        NOW,
        &dir,
    ))
    .unwrap();

    // v2 con la clave vieja: se rechaza. Escribirlo dejaría un manifiesto que
    // el propio build no sabe releer.
    let mut v2_old_key = base.clone();
    let obj = v2_old_key.as_object_mut().unwrap();
    obj.remove("activeView");
    obj.insert("activeSection".into(), serde_json::json!("evaluate"));
    assert!(validate_manifest(&serde_json::to_string(&v2_old_key).unwrap()).is_err());

    // v1 con la clave nueva: también se rechaza, por lo mismo.
    let mut v1_new_key = base.clone();
    let obj = v1_new_key.as_object_mut().unwrap();
    obj.insert("schemaVersion".into(), serde_json::json!(1));
    assert!(validate_manifest(&serde_json::to_string(&v1_new_key).unwrap()).is_err());

    let _ = fs::remove_dir_all(dir);
}

#[test]
fn v2_only_accepts_the_two_modes_that_exist() {
    let dir = temp_dir("v2_modes");
    let base: serde_json::Value = serde_json::from_str(&initial_manifest(
        "id-m",
        "Caso",
        "explore-hypothesis",
        NOW,
        &dir,
    ))
    .unwrap();

    for view in ["evaluation", "report"] {
        let mut value = base.clone();
        value["activeView"] = serde_json::json!(view);
        validate_manifest(&serde_json::to_string(&value).unwrap()).unwrap();
    }
    // Las secciones retiradas no son modos válidos en v2.
    for view in [
        "context", "system", "site", "ligands", "evaluate", "evidence",
    ] {
        let mut value = base.clone();
        value["activeView"] = serde_json::json!(view);
        assert!(
            validate_manifest(&serde_json::to_string(&value).unwrap()).is_err(),
            "`{view}` no es un modo de v2"
        );
    }

    let _ = fs::remove_dir_all(dir);
}

// ── Esquema v3: inputs persistentes ──────────────────────────────────

#[test]
fn v3_accepts_a_case_with_persisted_inputs() {
    let dir = temp_dir("v3_inputs");
    let mut value: serde_json::Value = serde_json::from_str(&initial_manifest(
        "id-v3",
        "Caso",
        "explore-hypothesis",
        NOW,
        &dir,
    ))
    .unwrap();
    value.as_object_mut().unwrap().insert(
        "inputs".into(),
        serde_json::json!({
            "receptor": { "pdbId": "7E2Y", "chain": "A", "origin": "curado" },
            "ligand": { "inputSmiles": "CCO", "canonicalSmiles": "CCO" },
            "grid": { "center": [1.0, 2.0, 3.0], "size": [20.0, 20.0, 20.0] }
        }),
    );
    value.as_object_mut().unwrap().insert(
        "preflight".into(),
        serde_json::json!({
            "fingerprint": "sha256:abc",
            "inputDocument": "{}",
            "generatedAt": NOW,
            "blockers": [],
            "warnings": [],
            "notEvaluated": []
        }),
    );

    validate_manifest(&serde_json::to_string(&value).unwrap()).unwrap();
    let _ = fs::remove_dir_all(dir);
}

#[test]
fn v3_rejects_inputs_that_would_be_unreadable_later() {
    // Un `inputs` corrupto que pasara por aquí se escribiría en disco y
    // reventaría después en TypeScript: el peor sitio para enterarse.
    let dir = temp_dir("v3_bad_inputs");
    let base: serde_json::Value = serde_json::from_str(&initial_manifest(
        "id-v3b",
        "Caso",
        "explore-hypothesis",
        NOW,
        &dir,
    ))
    .unwrap();

    for bad in [
        serde_json::json!("no soy un objeto"),
        serde_json::json!({ "receptor": { "chain": "A" } }),
        serde_json::json!({ "ligand": { "canonicalSmiles": "CCO" } }),
        serde_json::json!({ "receptor": "7E2Y" }),
    ] {
        let mut value = base.clone();
        value
            .as_object_mut()
            .unwrap()
            .insert("inputs".into(), bad.clone());
        assert!(
            validate_manifest(&serde_json::to_string(&value).unwrap()).is_err(),
            "debería rechazar inputs = {bad}"
        );
    }
    let _ = fs::remove_dir_all(dir);
}

#[test]
fn v3_rejects_a_preflight_without_its_fingerprint() {
    // Un preflight sin fingerprint no se puede comparar con nada: no es un
    // preflight ausente, es uno corrupto.
    let dir = temp_dir("v3_bad_preflight");
    let mut value: serde_json::Value = serde_json::from_str(&initial_manifest(
        "id-v3c",
        "Caso",
        "explore-hypothesis",
        NOW,
        &dir,
    ))
    .unwrap();
    value.as_object_mut().unwrap().insert(
        "preflight".into(),
        serde_json::json!({ "generatedAt": NOW, "inputDocument": "{}" }),
    );
    assert!(validate_manifest(&serde_json::to_string(&value).unwrap()).is_err());
    let _ = fs::remove_dir_all(dir);
}

#[test]
fn v3_rejects_an_unexecutable_preflight_configuration() {
    let dir = temp_dir("v3_bad_execution_config");
    let base: serde_json::Value = serde_json::from_str(&initial_manifest(
        "id-v3d",
        "Caso",
        "explore-hypothesis",
        NOW,
        &dir,
    ))
    .unwrap();

    for bad_config in [
        serde_json::json!({ "gridCenter": [1.0, 2.0] }),
        serde_json::json!({
            "gridCenter": [1.0, 2.0, 3.0],
            "gridSize": [20.0, 20.0, 20.0],
            "customHotspots": [],
            "dockingEngine": "vina",
            "exhaustiveness": 0,
            "numPoses": 9,
            "seed": 42
        }),
        serde_json::json!({
            "gridCenter": [1.0, 2.0, 3.0],
            "gridSize": [20.0, 20.0, 20.0],
            "customHotspots": "A:ASP1",
            "dockingEngine": "vina",
            "exhaustiveness": 8,
            "numPoses": 9,
            "seed": 42
        }),
    ] {
        let mut value = base.clone();
        value.as_object_mut().unwrap().insert(
            "preflight".into(),
            serde_json::json!({
                "fingerprint": "sha256:abc",
                "inputDocument": "{}",
                "executionConfig": bad_config
            }),
        );
        assert!(
            validate_manifest(&serde_json::to_string(&value).unwrap()).is_err(),
            "debería rechazar executionConfig = {bad_config}"
        );
    }
    let _ = fs::remove_dir_all(dir);
}

#[test]
fn older_schemas_keep_opening_after_v3() {
    // La garantía que no se puede perder: ningún caso guardado por un build
    // anterior queda inaccesible.
    let dir = temp_dir("v3_compat");
    let base: serde_json::Value = serde_json::from_str(&initial_manifest(
        "id-old",
        "Caso",
        "explore-hypothesis",
        NOW,
        &dir,
    ))
    .unwrap();

    let mut v1 = base.clone();
    let obj = v1.as_object_mut().unwrap();
    obj.insert("schemaVersion".into(), serde_json::json!(1));
    obj.remove("activeView");
    obj.insert("activeSection".into(), serde_json::json!("context"));
    validate_manifest(&serde_json::to_string(&v1).unwrap()).unwrap();

    let mut v2 = base.clone();
    v2.as_object_mut()
        .unwrap()
        .insert("schemaVersion".into(), serde_json::json!(2));
    validate_manifest(&serde_json::to_string(&v2).unwrap()).unwrap();

    let mut v3 = base.clone();
    v3.as_object_mut()
        .unwrap()
        .insert("schemaVersion".into(), serde_json::json!(3));
    validate_manifest(&serde_json::to_string(&v3).unwrap()).unwrap();

    let _ = fs::remove_dir_all(dir);
}

#[test]
fn manifest_owner_blocks_other_sessions_and_only_legacy_can_be_unowned() {
    let dir = temp_dir("owner_boundary");
    let owned = initial_manifest("owned", "Caso", "review-pose", NOW, &dir);
    ensure_manifest_owner(&owned, "test-owner", false).unwrap();
    assert!(ensure_manifest_owner(&owned, "another-owner", false)
        .unwrap_err()
        .starts_with("UNAUTHORIZED"));

    let mut legacy: serde_json::Value = serde_json::from_str(&owned).unwrap();
    legacy.as_object_mut().unwrap().remove("ownerUserId");
    legacy["schemaVersion"] = serde_json::json!(5);
    let legacy = serde_json::to_string(&legacy).unwrap();
    ensure_manifest_owner(&legacy, "test-owner", true).unwrap();
    assert!(ensure_manifest_owner(&legacy, "test-owner", false).is_err());
    let _ = fs::remove_dir_all(dir);
}

#[test]
fn schema_v6_requires_a_non_blank_owner_but_v5_remains_migratable() {
    let dir = temp_dir("owner_schema_boundary");
    let base: serde_json::Value = serde_json::from_str(&initial_manifest(
        "owned-schema",
        "Caso",
        "review-pose",
        NOW,
        &dir,
    ))
    .unwrap();

    for invalid_owner in [serde_json::Value::Null, serde_json::json!("   ")] {
        let mut v6 = base.clone();
        v6["ownerUserId"] = invalid_owner;
        assert!(validate_manifest(&serde_json::to_string(&v6).unwrap())
            .unwrap_err()
            .contains("ownerUserId"));
    }

    let mut v5 = base;
    v5["schemaVersion"] = serde_json::json!(5);
    v5.as_object_mut().unwrap().remove("ownerUserId");
    validate_manifest(&serde_json::to_string(&v5).unwrap()).unwrap();
    let _ = fs::remove_dir_all(dir);
}

#[test]
fn an_empty_session_identity_never_authorizes_a_manifest() {
    let dir = temp_dir("empty_session_identity");
    let owned = initial_manifest("owned-empty", "Caso", "review-pose", NOW, &dir);

    for missing_identity in ["", "   "] {
        assert!(ensure_manifest_owner(&owned, missing_identity, false)
            .unwrap_err()
            .starts_with("UNAUTHORIZED"));
        assert!(ensure_manifest_owner(&owned, missing_identity, true)
            .unwrap_err()
            .starts_with("UNAUTHORIZED"));
    }

    let _ = fs::remove_dir_all(dir);
}

#[test]
fn atomic_sibling_replaces_existing_file_without_residue() {
    let home = temp_dir("atomic_sibling");
    let target = home.join("authorized_cases.json");
    fs::write(&target, b"old").unwrap();

    write_atomic_sibling(&target, b"new").unwrap();

    assert_eq!(fs::read(&target).unwrap(), b"new");
    let names: Vec<_> = fs::read_dir(&home)
        .unwrap()
        .map(|entry| entry.unwrap().file_name())
        .collect();
    assert_eq!(names, vec![target.file_name().unwrap()]);
    let _ = fs::remove_dir_all(home);
}
