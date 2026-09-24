/// Manifiesto de aplicación propio, en vez del que embebe `tauri-build`.
///
/// El de la librería declara ÚNICAMENTE la dependencia de Common-Controls 6 y no
/// dice nada sobre DPI. Sin declaración, Windows ejecuta el proceso como
/// *DPI-unaware* y escala su ventana por mapa de bits: la interfaz se ve borrosa
/// a partir del 125 % y al arrastrar la ventana entre monitores con escalas
/// distintas. El WACK lo señala en `DPIAwarenessValidation`, que es un test
/// obligatorio de la certificación de Store:
///
///   «El archivo moldesign.exe no tiene el valor PerMonitorV2 manifestado en el
///    manifiesto ni realiza llamadas a las API de reconocimiento de PPP.»
///
/// Se conserva **literalmente** la dependencia de Common-Controls del manifiesto
/// original —quitarla cambiaría el estilo visual de los controles nativos— y se
/// añade el bloque `windowsSettings`. Los dos valores son deliberados:
///
/// - `dpiAware = true/pm` lo leen Windows 7/8.x y como respaldo Windows 10; el
///   `/pm` pide por-monitor donde exista.
/// - `dpiAwareness = PerMonitorV2` es el que lee Windows 10 1703 en adelante y
///   el que exige el WACK. Se lista `PerMonitor` detrás como degradación para
///   versiones que no entiendan V2: Windows toma el primer valor que reconoce.
const APP_MANIFEST: &str = r#"<?xml version="1.0" encoding="utf-8"?>
<assembly xmlns="urn:schemas-microsoft-com:asm.v1" manifestVersion="1.0">
  <dependency>
    <dependentAssembly>
      <assemblyIdentity
        type="win32"
        name="Microsoft.Windows.Common-Controls"
        version="6.0.0.0"
        processorArchitecture="*"
        publicKeyToken="6595b64144ccf1df"
        language="*"
      />
    </dependentAssembly>
  </dependency>
  <application xmlns="urn:schemas-microsoft-com:asm.v3">
    <windowsSettings>
      <dpiAware xmlns="http://schemas.microsoft.com/SMI/2005/WindowsSettings">true/pm</dpiAware>
      <dpiAwareness xmlns="http://schemas.microsoft.com/SMI/2016/WindowsSettings">PerMonitorV2, PerMonitor</dpiAwareness>
    </windowsSettings>
  </application>
</assembly>
"#;

/// `tauri.conf.json` empaqueta `resources/`, y `tauri-build` aborta si no existe
/// («resource path 'resources' doesn't exist»). Ese directorio sólo aparece con
/// `npm run stage:desktop`, así que en un clon limpio (la CI pública, un fork)
/// ni `cargo clippy` ni `cargo test` compilaban (2026-09-23, canal entre
/// sesiones B→F-006). Se crea vacío y se avisa.
///
/// Esto no deja pasar un instalador sin runtime: `tauri build` ejecuta antes las
/// puertas de `beforeBuildCommand` (`check:runtime-arbol`, `stage:desktop`,
/// `verify:desktop-runtime`…), que exigen el runtime entero.
fn asegurar_directorio_de_recursos() {
    let recursos = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("resources");
    if !recursos.exists() {
        std::fs::create_dir_all(&recursos).expect("no se pudo crear resources/");
        println!(
            "cargo:warning=resources/ no existía (clon sin staging): se crea vacío. \
             El instalador exige `npm run stage:desktop`."
        );
    }
}

fn main() {
    asegurar_directorio_de_recursos();
    let windows = tauri_build::WindowsAttributes::new().app_manifest(APP_MANIFEST);
    tauri_build::try_build(tauri_build::Attributes::new().windows_attributes(windows))
        .expect("fallo el build script de Tauri");
}
