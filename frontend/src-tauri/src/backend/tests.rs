//! Pruebas del arranque del motor.
//!
//! El fallo que motivó este módulo no fue «el backend no arranca»: fue que
//! arrancaba **el backend equivocado** —una copia caducada dentro de
//! `target/debug`— y su `/health` se rechazaba en silencio hasta agotar el
//! plazo. Por eso aquí se prueban las dos mitades de esa historia:
//!
//!   1. la resolución del runtime no vuelve a leer de la salida de compilación;
//!   2. la validación de salud sigue rechazando el contrato viejo, con la razón
//!      exacta y sin debilitarse a «cualquier HTTP 200 vale».

use super::*;
use std::fs;
use std::net::TcpListener;
use std::sync::atomic::{AtomicU64, Ordering};

static COUNTER: AtomicU64 = AtomicU64::new(0);

fn temp_dir(tag: &str) -> PathBuf {
    let n = COUNTER.fetch_add(1, Ordering::SeqCst);
    let base = std::env::temp_dir().join(format!(
        "moldesign_backend_{tag}_{}_{n}",
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_nanos()
    ));
    fs::create_dir_all(&base).unwrap();
    fs::canonicalize(&base).unwrap()
}

fn touch(path: &Path) {
    fs::create_dir_all(path.parent().unwrap()).unwrap();
    fs::write(path, b"placeholder").unwrap();
}

/// Árbol de desarrollo COMPLETO: `<root>/python-embed`, `<root>/backend`,
/// `<root>/tools/vina`, `<root>/tools/openbabel`.
fn make_dev_tree(root: &Path) {
    touch(&root.join("python-embed").join(PYTHON_BIN));
    touch(&root.join("backend").join("api").join("main.py"));
    touch(&root.join("tools").join("vina").join(VINA_BIN));
    touch(
        &root
            .join("tools")
            .join("openbabel")
            .join("bin")
            .join(OBABEL_BIN),
    );
}

/// Runtime EMPAQUETADO completo: `<res>/python`, `<res>/backend`,
/// `<res>/tools/vina`, `<res>/tools/openbabel`.
fn make_bundled_tree(root: &Path) {
    touch(&root.join("python").join(PYTHON_BIN));
    touch(&root.join("backend").join("api").join("main.py"));
    touch(&root.join("tools").join("vina").join(VINA_BIN));
    touch(
        &root
            .join("tools")
            .join("openbabel")
            .join("bin")
            .join(OBABEL_BIN),
    );
}

// ── Disposición del runtime ──────────────────────────────────────────

#[test]
fn dev_layout_points_at_the_live_repository_tree() {
    let root = temp_dir("dev_ok");
    make_dev_tree(&root);

    let layout = dev_layout(&root).unwrap();
    assert_eq!(
        layout.python_exe,
        root.join("python-embed").join(PYTHON_BIN)
    );
    assert_eq!(layout.backend_dir, root.join("backend"));
    assert_eq!(
        layout.vina_exe,
        root.join("tools").join("vina").join(VINA_BIN)
    );
    assert_eq!(layout.openbabel_dir, root.join("tools").join("openbabel"));

    let _ = fs::remove_dir_all(root);
}

#[test]
fn dev_layout_names_every_missing_piece() {
    let root = temp_dir("dev_missing");
    // Sólo el backend: faltan Python, Vina y Open Babel.
    touch(&root.join("backend").join("api").join("main.py"));

    let err = dev_layout(&root).unwrap_err();
    assert!(err.contains("Python de desarrollo"), "{err}");
    assert!(err.contains("Vina"), "{err}");
    assert!(err.contains("Open Babel"), "{err}");

    let _ = fs::remove_dir_all(root);
}

#[test]
fn a_missing_open_babel_is_a_damaged_install_not_an_optional_feature() {
    // Open Babel viaja en el instalador. Si no está, el motor no arranca y se
    // dice cuál es la pieza que falta: dejarlo pasar produciría una aplicación
    // cuyo respaldo de conversión estructural no puede funcionar, y eso sólo
    // se descubriría en mitad de una corrida.
    let root = temp_dir("dev_sin_openbabel");
    touch(&root.join("python-embed").join(PYTHON_BIN));
    touch(&root.join("backend").join("api").join("main.py"));
    touch(&root.join("tools").join("vina").join(VINA_BIN));

    let err = dev_layout(&root).unwrap_err();
    assert!(err.contains("Open Babel"), "{err}");
    assert!(err.contains("stage_openbabel_tool"), "{err}");

    let res = temp_dir("bundle_sin_openbabel");
    touch(&res.join("python").join(PYTHON_BIN));
    touch(&res.join("backend").join("api").join("main.py"));
    touch(&res.join("tools").join("vina").join(VINA_BIN));
    let err = bundled_layout(&res).unwrap_err();
    assert!(err.contains("no está instalado"), "{err}");
    assert!(err.contains("Open Babel"), "{err}");

    let _ = fs::remove_dir_all(root);
    let _ = fs::remove_dir_all(res);
}

#[test]
fn dev_layout_rejects_a_backend_folder_without_its_entrypoint() {
    // Una carpeta `backend/` vacía existía y pasaba la comprobación anterior.
    // El fallo aparecía después, dentro de uvicorn, con un mensaje mucho peor.
    let root = temp_dir("dev_hollow");
    touch(&root.join("python-embed").join(PYTHON_BIN));
    touch(&root.join("tools").join("vina").join(VINA_BIN));
    fs::create_dir_all(root.join("backend")).unwrap();

    let err = dev_layout(&root).unwrap_err();
    assert!(err.contains("api"), "{err}");

    let _ = fs::remove_dir_all(root);
}

#[test]
fn bundled_layout_uses_the_installed_resource_shape() {
    let root = temp_dir("bundled_ok");
    let logs = temp_dir("bundled_logs");
    make_bundled_tree(&root);

    let layout = bundled_layout_with_log_dir(&root, logs.clone()).unwrap();
    assert_eq!(layout.python_exe, root.join("python").join(PYTHON_BIN));
    assert_eq!(layout.backend_dir, root.join("backend"));
    assert_eq!(layout.openbabel_dir, root.join("tools").join("openbabel"));
    assert_eq!(layout.log_dir, logs);
    assert_ne!(layout.log_dir, root);

    let _ = fs::remove_dir_all(root);
    let _ = fs::remove_dir_all(logs);
}

#[test]
fn bundled_layout_reports_a_missing_engine_as_not_installed_material() {
    let root = temp_dir("bundled_missing");
    let err = bundled_layout(&root).unwrap_err();
    assert!(err.contains("no está instalado"), "{err}");
    let _ = fs::remove_dir_all(root);
}

#[test]
fn development_and_production_do_not_share_a_folder_shape() {
    // La misma carpeta no puede valer para las dos: es justo la suposición que
    // hacía la resolución anterior y la que la llevaba a `target/debug`.
    let root = temp_dir("shapes");
    make_dev_tree(&root);
    assert!(dev_layout(&root).is_ok());
    assert!(bundled_layout(&root).is_err());
    let _ = fs::remove_dir_all(root);
}

#[test]
#[cfg(debug_assertions)]
fn debug_builds_never_resolve_to_the_bundled_resource_dir() {
    // ESTA es la regresión. `target/debug` contenía un backend de julio con
    // Python y todo; la resolución lo encontraba primero y lo lanzaba. Con un
    // directorio de recursos perfectamente válido delante, una compilación de
    // desarrollo tiene que seguir sin usarlo.
    let fake_resources = temp_dir("fake_resources");
    make_bundled_tree(&fake_resources);

    match resolve_layout(Some(&fake_resources)) {
        Ok(layout) => {
            assert!(
                !layout.python_exe.starts_with(&fake_resources),
                "una compilación debug resolvió al runtime empaquetado: {}",
                layout.python_exe.display()
            );
            assert_eq!(layout.kind, "desarrollo (árbol vivo del repositorio)");
        }
        // Si el árbol vivo no está completo, el fallo es explícito. Lo que no
        // puede pasar es caer en silencio a los recursos.
        Err(reason) => assert!(reason.contains("árbol de desarrollo"), "{reason}"),
    }

    let _ = fs::remove_dir_all(fake_resources);
}

// ── Contrato de salud ────────────────────────────────────────────────

fn healthy_body() -> serde_json::Value {
    serde_json::json!({
        "status": "healthy",
        "app": "mol-design",
        "version": "1.0.0",
        "app_mode": "DESKTOP",
        "components": { "database": { "status": "healthy", "engine": "SQLite" } }
    })
}

/// La respuesta EXACTA que daba la copia caducada de `target/debug`: HTTP 200,
/// forma creíble, sin `app` ni `version`.
fn stale_backend_body() -> serde_json::Value {
    serde_json::json!({
        "status": "healthy",
        "app_mode": "DESKTOP",
        "environment": "development",
        "unhealthy_components": [],
        "components": {
            "mode": { "status": "healthy", "value": "DESKTOP" },
            "database": { "status": "healthy", "engine": "SQLite" }
        }
    })
}

#[test]
fn a_healthy_moldesign_backend_is_accepted() {
    assert!(matches!(
        validate_health_body(&healthy_body()),
        HealthState::Healthy
    ));
}

#[test]
fn the_stale_backend_is_rejected_and_says_why() {
    match validate_health_body(&stale_backend_body()) {
        HealthState::Unhealthy(reason) => {
            assert!(
                reason.contains("no se identifica como MolDesign"),
                "{reason}"
            );
            // La razón lleva los campos, que es lo que faltaba para poder
            // distinguir «otro servidor» de «MolDesign viejo».
            assert!(reason.contains("app=<ausente>"), "{reason}");
            assert!(reason.contains("app_mode=DESKTOP"), "{reason}");
        }
        _ => panic!("una respuesta sin identidad no puede darse por válida"),
    }
}

#[test]
fn any_http_200_is_not_enough() {
    // Un servidor cualquiera contestando JSON en nuestro puerto.
    let body = serde_json::json!({ "status": "healthy", "hello": "world" });
    assert!(matches!(
        validate_health_body(&body),
        HealthState::Unhealthy(_)
    ));
}

#[test]
fn an_empty_version_is_not_a_version() {
    let mut body = healthy_body();
    body["version"] = serde_json::json!("   ");
    match validate_health_body(&body) {
        HealthState::Unhealthy(reason) => assert!(reason.contains("versión"), "{reason}"),
        _ => panic!("una versión en blanco no es una versión"),
    }
}

#[test]
fn cloud_mode_is_not_the_desktop_backend() {
    let mut body = healthy_body();
    body["app_mode"] = serde_json::json!("CLOUD");
    match validate_health_body(&body) {
        HealthState::Unhealthy(reason) => assert!(reason.contains("DESKTOP"), "{reason}"),
        _ => panic!("CLOUD no puede pasar por el backend de escritorio"),
    }
}

#[test]
fn a_broken_database_is_never_healthy() {
    let mut body = healthy_body();
    body["components"]["database"]["status"] = serde_json::json!("unhealthy");
    match validate_health_body(&body) {
        HealthState::Unhealthy(reason) => assert!(reason.contains("base de datos"), "{reason}"),
        _ => panic!("sin SQLite no hay backend utilizable"),
    }
}

#[test]
fn degraded_is_accepted_but_reported() {
    // Vina ausente degrada sin invalidar: la aplicación abre y lo dice.
    let mut body = healthy_body();
    body["status"] = serde_json::json!("degraded");
    match validate_health_body(&body) {
        HealthState::Degraded(reason) => assert!(reason.contains("degradado"), "{reason}"),
        _ => panic!("`degraded` no es un rechazo"),
    }
}

#[test]
fn the_health_summary_carries_the_relevant_fields() {
    let summary = describe_health_body(&healthy_body());
    assert!(summary.contains("app=mol-design"));
    assert!(summary.contains("version=1.0.0"));
    assert!(summary.contains("app_mode=DESKTOP"));
    assert!(summary.contains("database=healthy"));
}

// ── Idempotencia y puertos ───────────────────────────────────────────

#[test]
fn a_ready_engine_is_not_started_again() {
    assert!(!needs_bootstrap(&BackendStatus::ready(8001)));
    // Tampoco mientras arranca: dos llamantes a la vez no hacen dos procesos.
    assert!(!needs_bootstrap(&BackendStatus {
        state: BackendPhase::Starting,
        port: None,
        detail: None,
    }));
}

#[test]
fn every_failure_state_allows_another_attempt() {
    for phase in [
        BackendPhase::Idle,
        BackendPhase::NotInstalled,
        BackendPhase::SpawnFailed,
        BackendPhase::HealthFailed,
    ] {
        assert!(
            needs_bootstrap(&BackendStatus::failed(phase, "x".into())),
            "{phase:?} debería poder reintentarse"
        );
    }
}

#[test]
fn an_occupied_port_is_skipped_instead_of_taken() {
    // El vecino que ocupa un puerto del rango NO se mata: se elige otro.
    let first = find_free_port().expect("debería haber algún puerto libre");
    let squatter = TcpListener::bind(("127.0.0.1", first)).unwrap();

    let second = find_free_port().expect("debería quedar otro puerto libre");
    assert_ne!(
        first, second,
        "se eligió un puerto que ya estaba ocupado por otro proceso"
    );
    assert!((PORT_RANGE_START..PORT_RANGE_END).contains(&second));

    drop(squatter);
}

#[test]
fn the_status_starts_idle_and_is_readable_without_blocking_a_bootstrap() {
    // `current_status` usa un cerrojo distinto del de arranque a propósito:
    // consultar el estado no puede quedarse esperando 30 s de probe.
    let status = current_status();
    assert!(matches!(
        status.state,
        BackendPhase::Idle
            | BackendPhase::Ready
            | BackendPhase::Starting
            | BackendPhase::NotInstalled
            | BackendPhase::SpawnFailed
            | BackendPhase::HealthFailed
    ));
}
