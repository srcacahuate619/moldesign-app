> **Documento histórico — julio de 2026.** Escrito para el árbol anterior del
> proyecto (`moldesign-app`) y traído aquí por trazabilidad. Puede describir un
> estado que ya no es el vigente: la versión 1.0.0 es una aplicación de
> escritorio y no tiene componente en la nube. No se ha reescrito su contenido.

# Guía de Preparación para Distribución en Steam (Tauri + Python Backend)
**Archivo**: `docs/posibles_problemas_y_mejoras.md`  
**Última revisión**: Julio 2026  

Este documento reúne los posibles problemas técnicos y de arquitectura identificados al empaquetar, distribuir y vender **MolDesign AI** como una aplicación de Windows en la plataforma **Steam**, junto con 10 mejoras e implementaciones clave para garantizar un lanzamiento exitoso.

---

## 📋 10 PROBLEMAS CRÍTICOS Y MEJORAS DE DISTRIBUCIÓN

### 1. El Tamaño de la Descarga y Dependencias de Python (Zero-Conda Strategy)
*   **Problema**: Empaquetar un entorno Conda completo con PyTorch (2+ GB) y modelos de ESMFold (3.5 GB) generará un instalador de más de **8 GB**, lo cual es inaceptable para una aplicación de escritorio e incrementará el consumo de ancho de banda de tus servidores.
*   **Solución**: 
    1.  Migrar la inferencia de GNN-v2 a **ONNX Runtime** (reemplazando PyTorch). Esto reduce la dependencia de 2 GB a menos de 100 MB y permite aceleración en CPU/GPU nativa en Windows con DirectML.
    2.  Utilizar una distribución limpia de **Python Embeddable** compilando y empaquetando las dependencias científicas (RDKit, Meeko, XGBoost) mediante ruedas (`.whl`) locales de pip, evitando Conda por completo.
    3.  Descargar modelos grandes (como ESMFold) bajo demanda en segundo plano en lugar de incluirlos en el build base.

### 2. Dependencia de MSVC Redistributables (Windows Error 126)
*   **Problema**: AutoDock Vina, xTB y RDKit dependen de librerías dinámicas de C++ (`msvcp140.dll`, `vcruntime140.dll`). Si el usuario de Steam tiene una instalación limpia de Windows sin estos runtimes, la aplicación crasheará inmediatamente con un error de carga de DLL al arrancar el backend.
*   **Solución**: Configurar los **Steamworks Common Redistributables** en tu panel de desarrollador de Steamworks. Define que tu aplicación requiere la instalación automática del paquete **"Microsoft Visual C++ 2015-2022 Redistributable (x64)"** antes de poder ejecutarse.

### 3. Permisos de Escritura en el Directorio de Instalación de Steam
*   **Problema**: Steam instala los juegos por defecto en `C:\Program Files (x86)\` o carpetas protegidas del sistema. Intentar escribir archivos temporales (`tempfile`), bases de datos SQLite (`moldesign_local.db`) o logs en la carpeta de instalación del juego provocará un crasheo por denegación de permisos (`PermissionError`).
*   **Solución**: Asegurar que todas las rutas del backend y de logs del frontend estén direccionadas a directorios de usuario con permisos garantizados. Utilizar siempre `%APPDATA%` (e.g. `C:\Users\<Usuario>\AppData\Roaming\MolDesign`) o el directorio `%USERPROFILE%\MolDesign\` para el SQLite, almacenamiento de SDFs de poses, PDFs e historial.

### 4. Falsos Positivos de Antivirus (Windows Defender)
*   **Problema**: El ejecutable de Tauri levantando un backend de FastAPI en segundo plano que a su vez llama a binarios de consola (`vina.exe`) activa las alertas de malware heurístico de Windows Defender y otros antivirus, bloqueando y eliminando binarios indispensables para el pipeline.
*   **Solución**: 
    1.  Firmar criptográficamente todos los archivos `.exe` y `.dll` (incluidos el backend compilado y los binarios de Vina/xTB) con un certificado de firma de código comercial (ej. Sectigo o DigiCert).
    2.  Enviar las compilaciones finales de forma preventiva a Microsoft Defender Security Intelligence para que sean añadidas a la lista blanca de falsos positivos antes del lanzamiento.

### 5. Procesos Zombies en Windows (FastAPI Orphaned Process)
*   **Problema**: Al cerrar el juego, si la app de Tauri crashea o se fuerza su salida por Steam, el proceso de Python que corre el backend asíncrono suele quedar huérfano (zombie) ejecutándose en segundo plano, impidiendo que el puerto local (`:8000`) se libere y bloqueando futuras ejecuciones del juego.
*   **Solución**: Implementar un hilo de monitoreo de proceso padre (*Heartbeat*) en el backend de FastAPI que verifique cada 2 segundos si el PID del proceso Tauri principal sigue existiendo en el sistema operativo; de no existir, el backend debe forzar su propia salida inmediata con `os._exit(0)`.

### 6. Integración Nativa con Steamworks SDK
*   **Problema**: El juego puede sentirse como una simple web empaquetada si carece de integración con las características nativas que los usuarios de Steam esperan.
*   **Solución**: 
    1.  Utilizar un wrapper como `steamworks.js` en tu frontend de Tauri para desbloquear **Logros de Steam (Achievements)** por hitos científicos (ej. "Inhibición Completa", "Lipinski Perfecto").
    2.  Integrar **Steam Cloud** mapeando la ruta de la base de datos `moldesign_local.db` para que el historial y moléculas guardadas del usuario se sincronicen en todos sus ordenadores.
    3.  Crear **Steam Leaderboards** (tablas de clasificación) para competir globalmente por encontrar el compuesto de mayor afinidad/score contra cada diana.

### 7. Modo de Juego Offline (Steam Offline Mode)
*   **Problema**: Steam permite jugar en modo desconectado. Si la aplicación intenta descargar estructuras PDB de internet (desde el RCSB PDB) o requiere conexión constante a APIs externas para predecir ADMET, fallará inmediatamente cuando el usuario no tenga red.
*   **Solución**: 
    1.  Pre-empaquetar las estructuras PDB preparadas de los 19+ targets en el instalador local dentro de una carpeta de assets del backend para que la preparación ocurra sin descargar nada.
    2.  Deshabilitar graciosamente o cambiar a modo "Heurístico Local" los módulos que dependan de APIs externas cuando `ping` a internet falle, mostrando una advertencia clara pero permitiendo jugar.

### 8. Compatibilidad con Steam Deck (Linux / Proton)
*   **Problema**: Más del 10% de los usuarios de Steam juegan en la consola portátil Steam Deck (que corre SteamOS, basado en Linux). Si la aplicación solo tiene compilado el backend para Windows, correrá bajo Proton, lo que puede provocar fallos al resolver rutas de Windows (`Z:\path\to\vina.exe`) o encolar subprocesos asíncronos de Vina.
*   **Solución**: Generar compilaciones nativas separadas para Windows (Tauri `.exe` + backend Windows) y para Linux (Tauri `.deb`/AppImage + backend Linux x64). Si se opta por usar Proton, testear exhaustivamente que la creación de carpetas temporales resuelva dentro del directorio virtual de Wine (`compatdata`) sin provocar excepciones de path.

### 9. Auto-escalado Adaptativo de Hardware
*   **Problema**: Los ordenadores de los usuarios varían drásticamente (desde portátiles de oficina de 2 núcleos hasta PCs gaming de 24 núcleos). Usar una configuración de CPU estricta o un docking pesado congelará los procesadores de los sistemas de gama baja, haciendo que la interfaz web de Tauri deje de responder.
*   **Solución**: Leer la información del procesador al arrancar la app y ajustar dinámicamente el parámetro `--cpu` de AutoDock Vina a `núcleos_físicos - 1` (para dejar siempre un núcleo libre para la renderización de la interfaz), y cambiar el motor de docking de `Vina` (exhaustiveness=8) a `QuickVina 2` (exhaustiveness=4) si el procesador detectado es de gama baja.

### 10. Soporte para Escalado de Interfaz y Mandos (Steam Big Picture)
*   **Problema**: Si el usuario abre el juego en el modo Big Picture de Steam o en la pantalla de 7 pulgadas de Steam Deck, las fuentes pequeñas serán ilegibles y diseñar moléculas arrastrando y haciendo click con los mandos o trackpads resultará sumamente frustrante.
*   **Solución**: 
    1.  Añadir una opción de escalado de interfaz en la configuración del juego (zoom: 100%, 120%, 150%) para pantallas pequeñas de alta densidad o televisiones.
    2.  Asegurar un soporte de navegación por teclado y mando mediante asignación estructurada de `tabindex` y estados `:focus` visuales marcados para que todo el editor molecular pueda controlarse sin necesidad de un ratón de precisión.
