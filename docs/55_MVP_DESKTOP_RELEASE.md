> **Documento histórico.** La validación descrita aquí corresponde al instalador
> 1.0.0 de agosto de 2026 y no es la receta vigente. Para el alpha actual usa
> BUILD_GUIDE.md y la cadena de puertas de tauri.conf.json. No desactives el
> bundle ni copies recursos manualmente.
# MolDesign Desktop MVP — release e instalación

**Fecha de validación:** 2026-08-24
**Versión validada:** 1.0.0 (histórica)
**Plataforma:** Windows x64
**Estado:** release candidate funcional para pruebas controladas

## Resultado

MolDesign ya dispone de un instalador autocontenido que puede copiarse a otra
máquina Windows e instalarse sin el repositorio, Node.js, Rust ni una
instalación externa de Python.

Esto cierra el requisito técnico de portabilidad del MVP. No equivale todavía
a un lanzamiento comercial público: falta firma digital y una pasada en una
segunda máquina física que no haya participado del desarrollo.

## Artefacto validado

| Campo | Valor |
|---|---|
| Archivo | frontend/src-tauri/target/release/bundle/nsis/MolDesign AI_1.0.0_x64-setup.exe |
| Tamaño | 510,333,062 bytes (486.7 MiB) |
| SHA-256 | 53C51F21A9196225D5DD3A0C0712B04B49025C5979E6A1D7350898D77FA51E03 |
| Firma Authenticode | No firmada |
| Instalación descomprimida | ~1.85 GiB |

El checksum representa exactamente el artefacto validado el 25 de agosto de
2026. Cualquier rebuild legítimo produce un hash distinto y debe volver a pasar
los gates de esta guía.

## Contrato del MVP

El producto no se presenta como una máquina que descubre fármacos ni como un
oráculo de unión. Es una herramienta local de evidencia estructural inicial:

1. crea/abre un caso de estudio;
2. selecciona una proteína o estructura propia;
3. declara ligandos e hipótesis;
4. ejecuta preflight y conserva configuración;
5. corre docking y capas científicas disponibles;
6. organiza resultados, advertencias, aplicabilidad, abstenciones y
   procedencia para revisión e informe.

La pregunta de producto es:

> ¿Qué evidencia computacional produjo esta corrida, con qué supuestos y
> controles, qué incertidumbre permanece y qué siguiente paso es justificable?

## Contenido del runtime

Incluido en el instalador:

- aplicación Tauri + frontend Next exportado;
- Python 3.11 embebido y dependencias científicas;
- backend FastAPI/Uvicorn;
- AutoDock Vina;
- xTB;
- rescoring y artefactos válidos;
- selector de pose;
- catálogo y estructuras curadas;
- llama.cpp CPU para el intérprete local opcional;
- licencias del proyecto/modelos.

No incluido en el camino crítico:

- pesos GGUF del intérprete;
- CUDA;
- pesos de ESMFold/RFdiffusion;
- datasets de entrenamiento;
- secretos, archivos .env, bases de usuario o logs históricos.

## Instalar en otra máquina

Requisitos:

- Windows 10/11 x64;
- 4 GB libres en disco;
- 16 GB RAM recomendados;
- WebView2. Si no existe, el instalador de Tauri puede necesitar internet para
  descargar el bootstrapper.

Procedimiento:

1. Copiar el instalador y verificar el SHA-256.
2. Ejecutarlo como el usuario que utilizará MolDesign.
3. Si SmartScreen alerta, confirmar únicamente si el hash coincide. Esta
   excepción es temporal mientras no exista firma Authenticode.
4. Abrir MolDesign.
5. Crear un caso de prueba en una carpeta nueva.
6. Confirmar que el motor pasa a estado listo y ejecutar un preflight antes de
   una evaluación real.

Comprobación de hash en PowerShell:

    Get-FileHash ".\MolDesign AI_1.0.0_x64-setup.exe" -Algorithm SHA256

## Receta reproducible de release

Desde frontend/:

    npm run test:run
    npm run tauri:build

La cadena histórica se conserva sólo como registro. La cadena actual de beforeBuildCommand realiza:

1. validación de CSP;
2. verificación del manifiesto de modelos;
3. staging del runtime por lista permitida;
4. escaneo de secretos/estado local;
5. verificación de hashes críticos;
6. imports desde el Python staged;
7. ejecución de Vina;
8. arranque real de FastAPI y validación semántica de /health;
9. comprobación de que el gate no mutó el runtime;
10. build estático de Next;
11. Cargo release y NSIS.

Scripts fuente:

- scripts/bundle_helper.py
- scripts/verify_desktop_bundle.py
- frontend/src-tauri/tauri.conf.json

## Evidencia de validación

| Gate | Resultado |
|---|---|
| Frontend | 28 archivos; 353 pruebas verdes |
| Rust/Tauri | 75 pruebas verdes |
| Next desktop | 14 páginas estáticas; tipos válidos |
| Payload staged | 30,163 archivos + runtime-manifest.json |
| Tamaño staged | 1,829.5 MiB de payload |
| Cachés Python | 0 archivos .pyc |
| Secretos/estado | 0 .env, logs o DB de usuario; sólo seed explícito |
| Instalación NSIS | código 0 en directorio fuera del repositorio |
| Inventario instalado | 30,164 recursos + exe + uninstaller |
| Hashes críticos | Python, backend, modelos, selector, Vina y catálogo válidos |
| Backend instalado | app=mol-design; version=1.0.0; app_mode=DESKTOP |
| Base local | healthy |
| Puerto | dinámico; smoke validado en 8001 |
| Cierre | ventana destruida y backend terminado por Job Object |
| Inmutabilidad | fingerprint antes/después idéntico: 397982…6781 |
| Residuos | 0 procesos, instalación y datos de smoke eliminados |

El smoke se hizo en el mismo host de desarrollo, pero instalando en una carpeta
limpia fuera de resources/ y target/release/. Por eso valida disposición,
inventario, arranque y cierre; no sustituye la prueba física en otro equipo.

## Dónde se escriben los datos

- Recursos del programa: sólo lectura; no reciben .pyc ni logs.
- Logs: app log dir de Tauri, en Windows bajo
  %LOCALAPPDATA%/ai.moldesign.app/logs.
- SQLite y artefactos internos: local_data_dir.
- Casos: carpeta elegida/autorizada por el usuario.

El diagnóstico temprano MOLDESIGN_BOOT_LOG es opt-in y no escribe nada si la
variable no está definida.

## Bloqueadores antes de llamarlo release comercial profesional

1. **Firmar el instalador y el ejecutable** con certificado Authenticode.
2. **Probar en una segunda PC limpia** (Windows 10 y Windows 11, idealmente).
3. **Completar third-party notices/SBOM** de Python, Vina, xTB y llama.cpp.
4. **Definir política de updates**: hoy el MVP se actualiza reinstalando; no
   hay canal de actualización pública.
5. **Prueba funcional de usuario**: crear caso, preflight, evaluación pequeña,
   persistencia, PDF y reapertura después de reiniciar.
6. **Optimizar tamaño** sólo con medición de dependencias; no retirar paquetes
   científicos a ciegas.

## Criterio de salida a beta

La beta puede declararse cuando el mismo instalador firmado pase en otra
máquina:

- instalación sin repositorio;
- arranque del motor;
- creación/reapertura de caso;
- preflight;
- una evaluación pequeña reproducible;
- generación/apertura de evidencia o informe;
- desinstalación limpia.
