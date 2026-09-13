# Inventario tecnológico integral de MolDesign

**Estado:** documento normativo interno  
**Corte:** 2026-09-07
**Baseline examinada:** rama `codex/release-hygiene`; cifras generadas desde el artefacto staged y el SBOM vigente
**Alcance:** código fuente, runtime de escritorio, herramientas nativas, modelos, superficies de red, almacenamiento, generación de evidencia y toolchain de construcción/pruebas.

---

## 1. Propósito y regla de lectura

Este documento responde cuatro preguntas distintas para cada tecnología:

1. **Qué es.** Biblioteca, programa externo, modelo, formato o servicio.
2. **Dónde vive.** Ruta o subsistema que permite encontrar su uso real.
3. **Por qué existe.** Responsabilidad concreta dentro de MolDesign.
4. **Qué estatus tiene.** No todo lo instalado se ejecuta ni todo lo que aparece
   en el código viaja en el producto.

No se usa la palabra «usamos» como sinónimo de «está instalado». Un paquete
transitivo, un experimento archivado y un motor de producción son categorías
diferentes.

### 1.1 Vocabulario de estado

| Estado | Significado operativo |
|---|---|
| **NÚCLEO** | Necesario para abrir la aplicación o ejecutar su contrato principal. |
| **ACTIVO** | Lo invoca una función disponible, aunque no forme parte de todas las corridas. |
| **BAJO DEMANDA** | Se activa o descarga sólo con una acción explícita del usuario. |
| **RED OPCIONAL** | Requiere un servicio remoto y no debe bloquear el uso local. |
| **EMPAQUETADO AUXILIAR** | Viaja porque otro binario lo necesita; no es una función pública. |
| **EMPAQUETADO SIN USO** | Viaja hoy, pero producción no lo invoca. Es superficie y peso a retirar o justificar. |
| **LABORATORIO** | Investigación, benchmark o herramienta de desarrollo; no es una capacidad del instalador. |
| **DECLARADO AUSENTE** | Hay código o una interfaz, pero el runtime distribuido carece de su productor/dependencia. Debe abstenerse. |
| **PRÓXIMAMENTE** | Visible pero deshabilitado; no existe un camino ejecutable honesto. |
| **RESIDUAL** | Instalado o importable sin consumidor de producción demostrado. Candidato a poda. |

### 1.2 Fuentes de verdad, en orden

Cuando dos archivos discrepan, prevalece este orden:

1. el artefacto staged que entra en el instalador;
2. `python-embed`, `frontend/package-lock.json` y `frontend/src-tauri/Cargo.lock`;
3. `docs/api/sbom.json`;
4. manifiestos directos (`requirements-desktop.txt`, `package.json`,
   `Cargo.toml`, manifiestos de modelos y del launcher);
5. imports y llamadas observadas en código;
6. documentación narrativa.

`backend/requirements-desktop.lock.txt` **no es la fuente del instalador**: es
un snapshot del Python de desarrollo. Por ejemplo, declara versiones distintas
de PyTorch, Transformers, SHAP y ReportLab respecto de `python-embed`.

### 1.3 Qué significa «absolutamente todas»

Este documento contiene todas las **tecnologías con papel arquitectónico o
científico identificable**. La enumeración exhaustiva de dependencias
transitivas vive en el SBOM para evitar duplicar miles de filas:

| Ecosistema distribuido | Fuente canónica | Instancias inventariadas |
|---|---|---:|
| Python embebido | `docs/api/sbom.json → python_embed.paquetes` | 172 |
| npm de producción | `docs/api/sbom.json → npm_produccion.paquetes` | 1.265 |
| crates Rust | `docs/api/sbom.json → rust_produccion.paquetes` | 574 |
| Binarios principales | `docs/api/sbom.json → binarios` | 4 |

El SBOM es exhaustivo por administrador de paquetes, pero no todavía por
archivo PE: hoy omite ejecutables y DLL auxiliares de Vina, llama.cpp, xTB y la
nueva herramienta Open Babel. Éste es un hallazgo abierto, descrito en §13.

---

## 2. Mapa del sistema entregado

```text
Usuario
  │
  ▼
Tauri 2 / Rust ── ventana, ciclo de vida, descargas, actualización, Job Object
  │
  ▼
Next.js 16 + React 19 ── interfaz estática local
  │ HTTP loopback; puerto negociado, nunca fijo
  ▼
FastAPI + Uvicorn + Python embebido
  ├─ RDKit / Meeko / Vina ───────────── docking de moléculas pequeñas
  ├─ perfiles M4 y M5-Zn ───────────── interpretación con dominio/abstención
  ├─ ESMFold descargable → Vina ────── plegamiento y docking de péptidos
  ├─ xTB / OpenMM / ADMET / MolChat ── análisis opcionales
  └─ SQLite + archivos + hashes ─────── persistencia, procedencia y dossier
```

Los únicos motores de la pestaña **Evaluación** que se ejecutan de verdad son:

- **AutoDock Vina 1.2.7**, para docking;
- **ESMFold**, únicamente para plegar péptidos; el docking posterior lo hace
  Vina.

xTB, Open Babel y llama.cpp son herramientas reales, pero no son motores de
docking. QuickVina 2, DiffDock, ColabFold, ESMFold Pro y RFdiffusion permanecen
deshabilitados como «Próximamente».

---

## 3. Plataformas, lenguajes y formatos de intercambio

| Tecnología | Estado | Dónde | Por qué |
|---|---|---|---|
| **Windows x86-64** | NÚCLEO | instalador NSIS y runtime embebido | Plataforma distribuida y verificada hoy. |
| **Python 3.11 embebido** | NÚCLEO | `python-embed/`, staged bajo recursos Tauri | Ejecutar backend y ciencia sin depender del Python del usuario. |
| **TypeScript / JavaScript** | NÚCLEO | `frontend/` | Interfaz, contrato cliente, build y gates del export estático. |
| **Rust 2021** | NÚCLEO | `frontend/src-tauri/` | Contenedor nativo, supervisión de procesos, descargas y empaquetado. |
| **HTML/CSS/WebView2** | NÚCLEO | export de Next abierto por Tauri | Render de la interfaz desktop; WebView2 es una dependencia de plataforma. |
| **PowerShell / scripts Python / Node** | CONSTRUCCIÓN | `scripts/`, `frontend/scripts/` | Build reproducible, staging, smoke tests, sellado y auditorías. |
| **HTTP/JSON sobre loopback** | NÚCLEO | frontend ↔ FastAPI | Separar UI y backend sin exponer un servicio público. |
| **PDB/PDBQT, SDF/MOL, SMILES, FASTA, XYZ** | ACTIVO | ingesta, preparación, docking, ESMFold, xTB | Intercambio estructural y químico entre etapas. |
| **JSON/JSONL, CSV/XLSX, PDF, ZIP** | ACTIVO | casos, cohortes, manifiestos, informes y export | Persistencia legible, lotes y transferencia reproducible. |
| **SHA-256** | NÚCLEO | manifiestos, modelos, installer y paquetes | Identidad de bytes e integridad; no equivale a firma de autor. |

---

## 4. Programas nativos y ejecutables externos

### 4.1 AutoDock Vina

| Campo | Valor |
|---|---|
| Estado | **NÚCLEO** |
| Distribución | `tools/vina/vina.exe`; se copia con `scripts/bundle_helper.py` |
| Uso | `backend/services/docking/vina_service.py`, dispatcher y colas de docking |
| Motivo | Generación y scoring de poses. Es el motor de docking de los tres caminos básicos. |
| Contrato científico | Su afinidad es una señal de ranking del protocolo, no energía libre experimental ni predicción clínica. |

La carpeta contiene además MinGW DLLs y `AutoDock-Vina-GPU-2-1.exe` con sus
kernels. Como `bundle_helper.py` copia el directorio completo, esos bytes viajan
hoy aunque producción usa `vina.exe`. El ejecutable GPU es **EMPAQUETADO SIN
USO**, no un motor ofrecido.

### 4.2 xTB / GFN2-xTB

| Campo | Valor |
|---|---|
| Estado | **ACTIVO OPCIONAL** |
| Distribución | `tools/xtb/xtb.exe`, datos y `libiomp5md.dll` |
| Uso | `backend/services/xtb/`, `compute_quantum_features.py`, MolChamb y ruta quantum/AD4 aislada |
| Motivo | Cargas parciales y descriptores electrónicos GFN2-xTB cuando el protocolo los solicita. |
| Límite | No sustituye parametrización GAFF/Antechamber ni convierte un docking en QM/MM o FEP. |

Existen dos adaptadores a xTB; uno está marcado `ARCHIVED/NOT ROUTED`. La
consolidación a una sola puerta sigue siendo deuda técnica.

### 4.3 llama.cpp

| Campo | Valor |
|---|---|
| Estado | **BAJO DEMANDA** |
| Distribución | `tools/llama/llama-server.exe` y DLLs llama/ggml CPU |
| Uso | `backend/services/ai/local_llm.py` y `local_llm_provider.py` |
| Motivo | Servir MolChat local mediante una API de subproceso, sin cargar el modelo en el backend. |
| Modelo | Qwen2.5-1.5B-Instruct Q4_K_M descargable; no imprescindible para evaluación. |

La carpeta también contiene CLI, benchmarks, cuantizador, TTS, servidores RPC y
otras utilidades de la distribución de llama.cpp. Producción sólo necesita
`llama-server.exe` y su cierre de DLLs; el resto es **EMPAQUETADO SIN USO** hasta
que el staging se reduzca a una lista verificada.

`tools/llama-cuda/` contiene un runtime CUDA mucho mayor, pero
`bundle_helper.py` no lo copia. Es **LABORATORIO/EXCLUIDO**.

### 4.4 Open Babel

| Campo | Valor |
|---|---|
| Estado objetivo | **ACTIVO**, programa independiente invocado por subproceso |
| Artefacto | `tools/openbabel/bin/obabel.exe` y plugins/datos mínimos |
| Uso | fallback PDBQT → SDF para recuperar conectividad antes de validar la pose |
| Motivo | Resolver formatos que RDKit no puede reconstruir de manera fiable directamente desde PDBQT. |
| Licencia medida | `GPL-2.0-only`; wheel `openbabel-wheel==3.1.1.23`, binario que reporta 3.1.0 |
| Procedencia | `tools/openbabel/openbabel-manifest.json` y `README-PROCEDENCIA.md` |

**Estado exacto del corte:** la frontera externa, el staging mínimo, los hashes,
la licencia, las pruebas y la conexión con `scripts/bundle_helper.py` están
presentes como cambios locales concurrentes. El build ya trata `openbabel` como
crítico, lo copia y excluye sus bindings del Python entregado. Aún falta que
esa integración termine sus gates y el smoke/VM limpia antes de atribuírsela a
un release publicado.

No se deben restaurar imports `openbabel`/`pybel` ni `_openbabel.pyd`. El wheel
es fuente de construcción; el producto debe comunicarse exclusivamente con
`obabel.exe` por archivos. Esto mantiene una frontera técnica verificable, pero
la interpretación jurídica final y el cumplimiento de la GPLv2 en cada release
siguen requiriendo revisión competente.

### 4.5 Herramientas presentes pero no entregadas

| Tecnología | Estado | Dónde | Por qué existe / decisión |
|---|---|---|---|
| **Smina** | LABORATORIO | `tools/smina/smina.static` y muestras | Ensayos históricos. No se copia, no se ofrece y no debe aparecer como motor activo. |
| **AutoDock4/AD4** | LABORATORIO/NO RUTEADO | `quantum_ad4_service.py` | Prototipo de cargas xTB + preparación Meeko; no es uno de los motores declarados. |
| **Vina-GPU 2.1** | EMPAQUETADO SIN USO | `tools/vina/` | Evidencia experimental histórica; falta excluirlo del bundle o declararlo como archivo auxiliar no invocado. |

---

## 5. Química computacional y biología estructural en Python

Las versiones son las declaradas para desktop o las observadas en
`python-embed`; cuando difieren, manda el runtime embebido.

| Tecnología | Estado | Dónde | Por qué se usa |
|---|---|---|---|
| **RDKit 2025.9.6** | NÚCLEO | `backend/chem/`, docking, scoring, ESMFold sidecar | Parseo y validación molecular, descriptores, fingerprints, conformeros, SMARTS y geometría. |
| **Meeko 0.7.1** | NÚCLEO | preparación de ligandos | Preparar PDBQT compatible con Vina y preservar la identidad química del ligando. |
| **Dimorphite-DL 2.0.2** | ACTIVO | preparación/protonación | Enumerar estados de protonación plausibles; no estima por sí solo poblaciones predominantes. |
| **MDAnalysis 2.10.0** | ACTIVO | análisis estructural y sidecar de péptidos | Selección, coordenadas y análisis de complejos/poses. |
| **ProLIF 2.1.0** | ACTIVO CON LÍMITES | evidencia de interacciones | Fingerprints proteína–ligando interpretables. No debe entrar en un modelo si su validación lo excluye. |
| **PoseBusters** | ACTIVO | controles físicos de pose | Detectar choques, geometrías y conectividad físicamente problemáticas bajo el protocolo documentado. |
| **OpenMM 8.5.2** | ACTIVO OPCIONAL | refinamiento/preparación y ESMFold sidecar | Operaciones mecánicas y de minimización expresamente configuradas; no implica que MolDesign haga MD. |
| **PDBFixer 1.12** | ACTIVO OPCIONAL | preparación de estructuras | Reparaciones estructurales acotadas; toda alteración debe quedar registrada, no asumirse silenciosamente. |
| **Biopython** | ACTIVO | secuencias y PDB | Lectura y manipulación de secuencias/estructuras. |
| **Gemmi 0.7.5** | RESIDUAL/REVISAR | runtime embebido | Parser estructural disponible; no se identificó un consumidor principal que justifique su presencia. |
| **ProDy 2.3.1** | RESIDUAL/REVISAR | runtime embebido | Análisis de proteínas instalado sin camino de producto confirmado. |
| **GridDataFormats 1.2.0** | TRANSITIVO ACTIVO | MDAnalysis | Lectura de datos de rejilla; licencia LGPL-3.0-or-later. |
| **mmtf-python** | TRANSITIVO | ecosistema estructural | Soporte del formato MMTF si lo consume una dependencia. No es un formato prometido por la UI. |

### 5.1 Descriptores y ADMET

| Tecnología | Estado | Dónde | Por qué se usa |
|---|---|---|---|
| **ADMET-AI 2.0.1** | ACTIVO EXPERIMENTAL | servicios ADMET/evaluación | Señales predictivas ADMET; siempre etiquetadas como modelo, nunca como medición clínica. |
| **Chemprop 2.2.4** | ACTIVO INDIRECTO | dependencia/modelos ADMET | Arquitectura molecular usada por ADMET-AI. |
| **Descriptastorus** | ACTIVO INDIRECTO | features de modelos | Descriptores moleculares reproducibles requeridos por modelos. Metadata de licencia ausente. |
| **MordredCommunity 2.0.7** | ACTIVO INDIRECTO | features de ADMET/modelado | Descriptores químicos extendidos. |
| **PaDELPy 0.1.16** | ACTIVO INDIRECTO | descriptores | Puente a descriptores PaDEL/Java donde se solicitan. |
| **MHFP 1.9.6** | ACTIVO INDIRECTO | similitud/splits | Fingerprints MinHash; metadata de licencia ausente. |
| **AIMSim Core 2.2.3** | ACTIVO INDIRECTO | similitud | Comparaciones de similitud química. |
| **Astartes 1.3.3** | ACTIVO INDIRECTO | validación/splits | Particiones que reducen fuga por similitud. |
| **TabPFN 8.0.8** | EXPERIMENTAL/REVISAR | análisis tabular | Experimentos o modelos tabulares. No debe distribuirse sin resolver sus términos y metadata de licencia. |

---

## 6. Machine learning, scoring y explicabilidad

| Tecnología | Estado | Dónde | Por qué se usa |
|---|---|---|---|
| **PyTorch 2.13.0+cpu** | ACTIVO | `python-embed`, ESMFold y redes | Inferencia neuronal en el runtime distribuido. La build actual es CPU; no prometer CUDA. |
| **Transformers 4.52.0** | ACTIVO BAJO DEMANDA | sidecar ESMFold | Arquitectura y carga local de ESMFold. |
| **SafeTensors 0.8.0** | ACTIVO INDIRECTO | pesos descargables | Serialización segura/eficiente de tensores. |
| **Tokenizers 0.21.4** | ACTIVO INDIRECTO | ESMFold/Transformers | Tokenización de secuencias/configuración. |
| **Hugging Face Hub 0.36.2** | BAJO DEMANDA/RED | model manager y launcher | Descargar por hash/revisión artefactos que no caben o no deben vivir en Git. |
| **PyTorch Geometric** | ACTIVO SEGÚN PERFIL | CL-GNN/rescoring | Representación de grafos moleculares y batching. |
| **DGL** | DECLARADO AUSENTE | `rescoring/gnn_service.py`, RTMScore legacy | Código heredado no ejecutable en el Python embebido; no confundir con CL-GNN operativo. |
| **torch-scatter / torch-sparse** | DECLARADO AUSENTE | código/requirements de investigación | Extensiones GNN no presentes en el runtime empaquetado. |
| **XGBoost 3.2.0** | ACTIVO | M4, selectores y rescoring | Regresión/clasificación tabular sobre features persistidas. |
| **scikit-learn 1.8.0** | ACTIVO | pipelines, calibración y métricas | Preprocesamiento, modelos clásicos y evaluación. |
| **SHAP 0.51.0** | ACTIVO | pestaña de explicabilidad | Explicar el XGBoost realmente ejecutado; una explicación no valida el modelo ni rescata un caso fuera de dominio. |
| **NumPy 2.4.4 / SciPy 1.17.1** | NÚCLEO CIENTÍFICO | transversal | Arrays, álgebra, estadística y geometría. |
| **pandas 3.0.2** | ACTIVO | datasets, lotes y reportes | Tablas y transformaciones reproducibles. |
| **Numba 0.65.0 / llvmlite** | ACTIVO INDIRECTO | SHAP y cómputo numérico | Aceleración JIT. La metadata de licencia de llvmlite debe revisarse en el SBOM. |
| **LightGBM** | ACTIVO INDIRECTO/REVISAR | ecosistema ADMET/modelos | Backend de modelos donde un artefacto lo requiera; no es una salida independiente. |
| **Lightning / PyTorch Lightning 2.6.5** | ENTRENAMIENTO/INDIRECTO | dependencias de ML | Infraestructura de modelos, principalmente entrenamiento; confirmar necesidad en inferencia. |
| **einops 0.8.2** | ACTIVO INDIRECTO | redes | Reorganización de tensores. |
| **joblib / threadpoolctl** | ACTIVO INDIRECTO | scikit-learn/XGBoost | Serialización y control de paralelismo. |

### 6.1 Artefactos y modelos propios

| Artefacto/tecnología | Estado | Dónde | Papel y límite |
|---|---|---|---|
| **M4** | ACTIVO | `backend/scoring/`, `rescoring/artifacts/model-manifest.json` | Vina como observación; XGBoost pKi como interpretación con dominio de aplicabilidad. Fuera de dominio, prevalece Vina y el modelo se marca `REVIEW`. |
| **M5-Zn V1** | ACTIVO EN CUARENTENA/ABSTENCIÓN | `backend/services/protocols/zinc.py`, manifiesto M5, docs 75/77 | Integra señales sólo para perfiles exactos. CA2 carece de productor GNN-D; MMP9 y ACE conservan scores auditables pero no conclusiones liberables por problemas del benchmark. |
| **CL-GNN** | ACTIVO SEGÚN MODELO | `rescoring/`, checkpoints/manifiesto | Señal neuronal ligando/pose. Cualquier afirmación sobre sesgo por tamaño debe citar la prueba y cohorte concreta. |
| **GNN-D** | DECLARADO AUSENTE | backups/benchmarks | Componente exigido por CA2 sin productor de producción; la salida correcta es abstención. |
| **UMS / UMS-warhead** | ACTIVO CON DISTINCIÓN | scoring, MolChamb, M5 | Señales de metales. `ums_warhead` autorizado no es el `ums_score` histórico; no intercambiarlos. |
| **MolChamb** | ACTIVO EXPERIMENTAL | `backend/services/chemistry/molchamb_v2.py` | Descriptores de microentorno y señales xTB; su valor depende de benchmarks trazables. |
| **Selector de pose XGBoost** | ACTIVO | `rescoring/artifacts/pose_selector_v06.xgb` | Ordenar/seleccionar poses bajo el contrato del manifiesto; no convierte una pose top-1 en verdad estructural. |
| **MetaStack / total_score** | EXPERIMENTAL | scoring y manifiestos | Agregación explícita de señales. Estados `REVIEW_*` no deben influir en ranking, explicación ni recomendación. |
| **MolGraph** | ACTIVO COMO EVIDENCIA | backend y docs/paper | Grafo de procedencia y relaciones químicas; no es por sí mismo un predictor validado. |
| **Readiness / FEP-ready** | EN DESARROLLO | auditorías FEP, dossiers y roadmap | Auditar preparación y transferencia; MolDesign no ejecuta FEP ni está certificado por Schrödinger. |

Los pesos grandes no deben confundirse con el código. `launcher-manifest.json`
declara un módulo base de aproximadamente 872 MB, Qwen GGUF de aproximadamente
1,12 GB y ESMFold de aproximadamente 8,44 GB con SHA-256 y revisiones
inmutables. El origen de distribución previsto es
`srcacahuate/moldesign-models`; una descarga sólo es aceptable si el hash y la
licencia coinciden.

---

## 7. Backend, API y ejecución asíncrona

| Tecnología | Estado | Dónde | Por qué se usa |
|---|---|---|---|
| **FastAPI 0.135.2** | NÚCLEO | `backend/api/` | API local tipada para casos, evaluación, lotes, modelos e informes. |
| **Uvicorn 0.42.0** | NÚCLEO | arranque del backend | Servidor ASGI local supervisado por Tauri. |
| **Starlette 1.0.0** | NÚCLEO INDIRECTO | FastAPI/middleware | Base ASGI, requests, responses y middleware. |
| **Pydantic 2.12.5** | NÚCLEO | modelos y contratos | Validación de entrada/salida y estados científicos explícitos. |
| **pydantic-settings 2.13.1 / dotenv** | ACTIVO | configuración | Configuración por entorno sin fijar rutas/puertos de una máquina. |
| **python-multipart 0.0.22** | ACTIVO | uploads | Ingesta de archivos desde la interfaz. |
| **HTTPX 0.28.1** | ACTIVO | sidecars/servicios opcionales | Cliente HTTP con timeouts; loopback y red opcional. |
| **Tenacity 9.1.4** | ACTIVO | integraciones | Reintentos acotados; no debe ocultar fallos permanentes. |
| **SlowAPI 0.1.9** | ACTIVO | middleware/API | Límites de frecuencia en superficies sensibles. |
| **email-validator 2.3.0** | ACTIVO | esquemas de usuario | Validación sintáctica de correo. |
| **python-dateutil** | ACTIVO INDIRECTO | fechas | Parseo/normalización temporal. |
| **openpyxl 3.1.5** | ACTIVO OMITIDO DEL MANIFIESTO DIRECTO | batch/cohort service | Lectura/escritura XLSX. Debe declararse explícitamente en requirements desktop. |
| **requests** | ACTIVO OMITIDO DEL MANIFIESTO DIRECTO | servicios de novo | Cliente HTTP heredado; consolidar con HTTPX o declarar. |

El backend no usa un broker externo: la durabilidad de jobs y la recuperación
se implementan localmente. Cualquier cola en memoria debe considerarse
orquestación, no persistencia.

---

## 8. Persistencia, serialización y evidencia

| Tecnología | Estado | Dónde | Por qué se usa |
|---|---|---|---|
| **SQLite** | NÚCLEO | workspace del usuario | Base local de casos, corridas y estados; no requiere servicio. |
| **SQLAlchemy 2.0.49** | NÚCLEO | `backend/core/models.py`, repositorios | ORM y transacciones. |
| **aiosqlite** | ACTIVO | acceso async | Evitar bloquear el servidor al persistir. El runtime observado usa 0.22.1. |
| **JSON y archivos de caso** | NÚCLEO | workspace, manifests, snapshots | Contratos legibles y portables; escritura atómica supervisada. |
| **diskcache** | ACTIVO/REVISAR | caches locales | Reuso de cómputos; ningún resultado científico debe existir sólo aquí. |
| **msgpack 1.2.1 / dill** | ACTIVO INDIRECTO/REVISAR | serialización/caches | Objetos compactos o de Python; no son formatos de transferencia pública. |
| **ReportLab 4.2.0** | ACTIVO | dossier/certificado PDF | Render reproducible de informes. |
| **Pillow 12.2.0** | ACTIVO | imágenes del informe | Rasterización y composición. |
| **Matplotlib 3.11.0 / Seaborn** | ACTIVO | gráficas científicas | Visualizaciones; deben mostrar procedencia y unidades. |
| **pypdf** | PRUEBAS | tests de dossier | Inspeccionar que el PDF generado contiene el contrato esperado. |
| **ZIP** | ACTIVO | export y updater | Paquete transferible y descarga de módulos; la integridad se verifica con hash. |

Un PDF o hash es **evidencia verificable/tamper-evident**, no «inmutable». La
procedencia científica depende además de versión, configuración, entrada,
salida y estado de aplicabilidad persistidos.

---

## 9. Frontend científico y visualización

| Tecnología | Estado | Dónde | Por qué se usa |
|---|---|---|---|
| **Next.js 16.3.4** | NÚCLEO | `frontend/` | Routing y export estático consumido por Tauri. No se despliega como servidor web. |
| **React / React DOM 19.2.8** | NÚCLEO | componentes | Estado y composición de la interfaz; alineado con Next 16 y React Three Fiber 9. |
| **Tailwind CSS 4.2.2 / PostCSS / Autoprefixer** | NÚCLEO UI | estilos/build | Sistema visual y transformación CSS compatible con el WebView. |
| **3Dmol.js 2.5.4** | ACTIVO | visores de evaluación | Visualización rápida de receptor, ligando y poses. |
| **Mol* 5.9.0** | ACTIVO | visor estructural avanzado | Escenas macromoleculares y selecciones más ricas. |
| **Three.js 0.185 / React Three Fiber / Drei** | ACTIVO | escenas 3D propias | Render y controles 3D no cubiertos por los visores moleculares. Hay versiones transitivas adicionales que conviene deduplicar. |
| **Ketcher 3.18** | ACTIVO | editor químico | Entrada/edición 2D de estructuras y SMILES. |
| **Framer Motion 13.2** | ACTIVO UI | transiciones | Animaciones de estado y navegación. |
| **Lucide React 0.474** | ACTIVO UI | iconografía | Iconos consistentes. |
| **React Virtuoso 4.18.11** | ACTIVO | listas grandes | Virtualización de cohortes/resultados. |
| **brain.js beta** | RESIDUAL/REVISAR | dependencia directa | No se identificó un papel científico de producción que justifique mantenerla. |
| **prom-client 15.1.3** | ACTIVO/REVISAR | métricas | Instrumentación técnica; no implica telemetría remota. |
| **NextAuth 4.24.14** | ACTIVO PARCIAL | autenticación frontend | Sesiones/autenticación; revisar convivencia con auth local del backend. |

### 9.1 Solana en el frontend

`@solana/web3.js` y los wallet adapters permiten conectar una cartera para
anclar o comprobar hashes. Son **RED OPCIONAL**. La interfaz debe llamarlo
«anclaje/verificación», no notarización ni garantía de validez científica.

---

## 10. Contenedor nativo, actualización y sistema operativo

| Tecnología | Estado | Dónde | Por qué se usa |
|---|---|---|---|
| **Tauri 2.11.3** | NÚCLEO | `frontend/src-tauri/` | Empaquetar UI estática y recursos locales como app de escritorio. |
| **tauri-build 2.6.3 / CLI 2.11.4** | CONSTRUCCIÓN | Cargo/npm | Compilar el contenedor y el instalador. |
| **Shell/Dialog/Log/Updater/Single-instance plugins** | ACTIVO | `Cargo.toml` | Lanzamiento controlado, carpetas nativas, logs, actualización y una sola instancia. |
| **Tokio / futures-util** | ACTIVO | Rust | I/O y streaming asíncrono de descargas/procesos. |
| **Reqwest 0.12** | ACTIVO BAJO DEMANDA | Rust launcher | Descargar módulos/modelos y metadatos con verificación. |
| **Serde / serde_json** | NÚCLEO | Rust | Contratos y manifiestos JSON. |
| **sha2 / hex** | NÚCLEO | Rust | Validación de descargas por SHA-256. |
| **zip 2.4** | ACTIVO | Rust | Desempaquetado controlado de módulos. |
| **chrono** | ACTIVO | Rust | Sellos temporales técnicos. |
| **atomicwrites** | NÚCLEO | workspace de casos | Reemplazo atómico de `case.json`; evita archivos a medias. |
| **windows-sys 0.59** | NÚCLEO WINDOWS | backend supervisor | Job Object con `KILL_ON_JOB_CLOSE`; evita procesos huérfanos. |
| **NSIS** | NÚCLEO DE DISTRIBUCIÓN | configuración Tauri | Instalador `.exe`. |
| **Microsoft WebView2** | NÚCLEO DE PLATAFORMA | host Tauri en Windows | Motor web de la UI; su disponibilidad debe verificarse en VM limpia. |
| **Visual C++ Runtime / MinGW runtime / OpenMP** | EMPAQUETADO AUXILIAR | junto a binarios nativos | Cierre de DLLs para que Vina, xTB, llama.cpp y Open Babel funcionen sin la máquina de build. |

Tauri modifica la CSP de producción. La excepción de `style-src` está
deliberadamente configurada porque un nonce invalida `unsafe-inline` y rompería
los estilos React. Sólo `smoke:prod` prueba el export y la CSP que se entregan.

---

## 11. Autenticación, seguridad e integraciones externas

| Tecnología | Estado | Dónde | Por qué se usa |
|---|---|---|---|
| **PyJWT 2.8.0** | ACTIVO | backend auth | Tokens de sesión/autorización. |
| **bcrypt** | ACTIVO | backend auth | Hash de contraseñas; runtime observado 5.0.0 aunque requirements fija 4.2.1. |
| **cryptography 42.0.7** | ACTIVO | seguridad/integraciones | Primitivas criptográficas y dependencias SSH/TLS. |
| **Argon2 / passlib** | RESIDUAL/REVISAR | runtime embebido | Instalados, pero confirmar si existe consumidor o migración activa. |
| **Google OAuth (`google-auth`)** | DECLARADO AUSENTE | `backend/api/routers/auth.py` | Login opcional importado condicionalmente; no funciona en el runtime embebido actual. |
| **Anthropic SDK** | RED OPCIONAL | proveedor remoto de IA | Interpretación/chat sólo con consentimiento y credencial del usuario; nunca necesaria para docking. |
| **Solana Web3.js + JSON-RPC stdlib** | RED OPCIONAL · EXPERIMENTAL | frontend y `backend/services/blockchain/certifier.py` | POC devnet: firmar en cliente y verificar memos; no es certificación ni validez científica. |
| **Paramiko 5.0.0** | RESIDUAL/REVISAR | runtime embebido | SSH instalado; identificar consumidor antes de distribuirlo. Licencia declarada LGPL-2.1. |
| **PostHog** | RESIDUAL/PROHIBIDO SIN OPT-IN | runtime embebido | Paquete presente sin necesidad demostrada. La política es cero telemetría no consentida. |
| **pyOpenCL** | DECLARADO AUSENTE | `backend/core/hardware.py` | Sondeo opcional de hardware; no presente y no necesario. |

La aplicación funciona sin red **después** de descargar voluntariamente los
artefactos opcionales. Las superficies que sí pueden usar red son: Hugging Face
para módulos/modelos, Anthropic, Solana, actualización de Tauri y Google OAuth
si se instala. Deben ser visibles, opt-in y fallar sin degradar la evidencia
local.

---

## 12. Observabilidad y operación local

| Tecnología | Estado | Dónde | Por qué se usa |
|---|---|---|---|
| **structlog 25.5.0** | ACTIVO | logging backend | Eventos estructurados y trazabilidad. |
| **logging de Python / loguru** | ACTIVO/REVISAR | módulos y dependencias | Logs técnicos; conviene consolidar para evitar dos semánticas. |
| **tauri-plugin-log** | ACTIVO | contenedor | Logs del ciclo de vida nativo. |
| **psutil 7.2.2** | ACTIVO | salud/recursos | RAM, procesos y diagnóstico del runtime. |
| **Prometheus client** | ACTIVO LOCAL/REVISAR | backend/frontend | Métricas operativas locales. No debe abrir telemetría por defecto. |
| **tqdm / rich** | HERRAMIENTA | scripts/CLI | Progreso y diagnóstico durante build o tareas largas. |

---

## 13. Desarrollo, pruebas, ciencia reproducible y CI

| Tecnología | Estado | Dónde | Por qué se usa |
|---|---|---|---|
| **pytest / pytest-asyncio** | CONSTRUCCIÓN | `backend/tests/`, `rescoring/tests/` | Contratos unitarios, integración, goldens y abstenciones. |
| **Vitest 5.0 + Testing Library 16.3 + jsdom 30** | CONSTRUCCIÓN | frontend tests | Comportamiento de componentes y contratos cliente. |
| **Playwright 1.62** | CONSTRUCCIÓN | `frontend/e2e/` | Flujos de usuario y accesibilidad sobre build. |
| **TypeScript 5.8.3** | CONSTRUCCIÓN | `tsc --noEmit` | Consistencia estática del frontend. |
| **Vite 8.2** | CONSTRUCCIÓN | Vitest/tooling | Transformación rápida para pruebas; Next sigue siendo el build del producto. |
| **Git / tags / GitHub Releases** | NÚCLEO DE ENTREGA | repositorio y releases | Trazabilidad del código, instalador y hashes. |
| **GitHub Actions** | CI | workflows | Repetir gates en un entorno distinto; no sustituye VM limpia. |
| **SBOM JSON propio** | GATE | `scripts/generate_sbom.py`, `docs/api/sbom.json` | Inventario y revisión de licencias del runtime distribuido; no se afirma compatibilidad CycloneDX. |
| **Goldens/snapshots** | GATE CIENTÍFICO | `scripts/generate_goldens.py`, artefactos | Detectar cambios semánticos entre dev y runtime embebido. |
| **Smoke de producción** | GATE DE ARTEFACTO | `frontend/scripts/smoke-produccion.mjs` | Probar export, CSP, puerto negociado y backend empaquetado. |
| **VM limpia** | GATE MANUAL | protocolo de release | Detectar dependencias accidentales de la máquina de desarrollo. |
| **Authenticode** | PENDIENTE | instalador | Firma de editor. Hoy sólo existe integridad SHA-256, no identidad autenticada. |
| **ODDT** | LABORATORIO | `rescoring/pdbbind_parser.py` | Preparación/feature extraction de benchmarks; no forma parte del runtime ejecutable. |
| **NetworkX** | LABORATORIO | scripts | Análisis de grafos offline, no servicio de producto. |
| **Jupyter** | LABORATORIO | notebooks/experimentos si existen | Exploración; ninguna afirmación debe depender sólo de una celda no versionada. |

`scripts/artifacts_science/` contiene evidencia sellada y no debe editarse para
actualizar este inventario. Las rutas de usuario/IP privadas allí son
procedencia histórica, no configuración del runtime.

---

## 14. Tecnologías internas: qué son realmente

| Nombre interno | Categoría correcta | Uso | No significa |
|---|---|---|---|
| **Dossier de evidencia computacional** | Producto documental | Reunir observaciones, interpretaciones, dominio, abstenciones y procedencia. | Certificado de eficacia o validez clínica. |
| **Certificado científico** | Vista/resumen verificable | Resumen de la evaluación y sus hashes. | Un segundo protocolo científico independiente ni certificación regulatoria. |
| **Moldex** | Gestión/consulta de casos | Navegar el expediente y sus artefactos. | Base pública de compuestos. |
| **MolChat** | Interfaz explicativa | Responder desde evidencia persistida con LLM local/remoto opcional. | Fuente primaria de resultados ni autoridad científica. |
| **Panel de selectividad** | Post-docking | Ejecutar/mostrar comparaciones cuando existen anti-targets evaluados. | Selectividad experimental. |
| **MM-GBSA** | Contrato post-hoc incompleto/opcional | Refinamiento explícito sólo si todos los componentes existen. | Energía libre rigurosa o FEP. |
| **Explicabilidad SHAP** | Interpretación de modelo | Atribuir contribuciones del XGBoost aplicado. | Evidencia de que el valor predicho es correcto. |
| **Paquete FEP-ready** | Dirección de producto | Preparar sistema, decisiones y procedencia para un cálculo externo. | Ejecución de FEP+, compatibilidad certificada o readiness ya validado. |

El dossier y el certificado deben compartir una única fuente de hechos. Si se
conservan como dos PDFs, su diferencia ha de ser de audiencia y profundidad,
no de protocolo ni de resultados.

---

## 15. Inventario de ausencias y residuos que pueden inducir a error

### 15.1 Declarado o referenciado, pero no ejecutable en el bundle

- DGL/RTMScore legacy.
- GNN-D de CA2.
- `torch-scatter` y `torch-sparse`.
- Google OAuth (`google-auth`).
- `pyopencl`.
- faster-whisper/CTranslate2: no están en el Python embebido actual; no declarar
  voz local aunque aparezcan en requirements narrativos o código histórico.

### 15.2 Instalado, pero sin consumidor de producción confirmado

- `llama-cpp-python`: sustituido por `llama-server.exe`; queda código
  experimental.
- ProDy, Gemmi, Argon2, passlib, Paramiko y PostHog.
- `brain.js`.
- múltiples utilidades llama.cpp que se copian por copiar toda la carpeta.
- Vina-GPU dentro de `tools/vina/`.

La acción correcta no es borrar a ciegas: primero una prueba negativa demuestra
que el producto y los modelos arrancan sin la dependencia; después se poda y se
regenera el SBOM.

### 15.3 Motores visibles pero deshabilitados

QuickVina 2, DiffDock, ColabFold, ESMFold Pro y RFdiffusion son catálogo futuro.
Las guardas `ENG-001`, `ENG-003` y `ENG-004` deben impedir que una etiqueta de
interfaz los convierta accidentalmente en una capacidad falsa.

---

## 16. Licencias y obligaciones de distribución

| Componente | Licencia/estado conocido | Consecuencia interna |
|---|---|---|
| MolDesign | PolyForm Noncommercial 1.0.0 + licencia comercial separada mediante CLA | Uso no comercial source-available; todo uso comercial exige acuerdo escrito. Las copias antiguas ya recibidas bajo AGPL conservan esa concesión. |
| Open Babel staged | GPL-2.0-only | Distribuir licencia y fuente correspondiente/oferta válida; mantener y verificar la frontera de programa externo. Revisión jurídica pendiente. |
| Meeko | LGPL-2.1 | Conservar avisos y cumplir condiciones aplicables. |
| GridDataFormats | LGPL-3.0-or-later | Igual; verificar forma de distribución. |
| Paramiko | LGPL-2.1 | Revisar además si debe viajar. |
| rpc-websockets | LGPL-3.0-only | Conservar avisos en el frontend distribuido. |
| TabPFN | Prior Labs License 1.2 | Mantener la atribución visible «Built with PriorLabs-TabPFN» y el texto de licencia ya incluidos. |
| Modelos propios/terceros | `LICENSE-MODELS` + manifiestos individuales | No inferir que la licencia del código cubre pesos. |

Paquetes sin licencia declarada en el SBOM actual:

- Python: ninguno. `jsonalias`/`solders`/`solana-py` se retiraron del runtime.
- npm: ninguno; los siete vacíos originales se resolvieron leyendo sus archivos.
- Rust: `Cargo.lock` fija nombres/versiones, pero el SBOM offline todavía no
  recupera sus licencias; hacen falta avisos generados con la caché completa.

TabPFN también quedó identificado: usa Prior Labs License 1.2, conserva su texto
y la atribución visible exigida; ya no pertenece a la lista de desconocidos.

Este apartado es un mapa técnico de obligaciones, no asesoría legal.

---

## 17. Hallazgos y acciones priorizadas

### P0 — antes del siguiente instalador público

1. ~~**Resolver `jsonalias` y la obligación LGPL de Solana.**~~ **HECHO 2026-09-07:** SDK Python retirado; Web3.js queda con avisos, texto LGPL y vía de reemplazo.
2. **Publicar la oferta de fuente de Open Babel** junto al instalador; los dos
   archivos exactos ya están preparados y el gate local los verifica.
3. **Completar los avisos/licencias Rust** y la revisión jurídica de la frontera
   Open Babel antes de ofrecer licencias comerciales.
4. **Publicar runtime y pesos descargables** con revisión inmutable, tamaño y
   SHA-256; después repetir build + smoke en una VM limpia y sellar el resultado.

### P1 — reducir superficie y falsas capacidades

1. Copiar sólo el cierre mínimo verificado de llama.cpp y Vina; excluir CLI,
   benchmarks, RPC, TTS y Vina-GPU si no se ejecutan.
2. Quitar `openbabel-wheel` del runtime final después de materializar
   `obabel.exe`; el wheel debe ser dependencia de construcción.
3. Declarar `openpyxl` y `requests` directamente o eliminar esos caminos.
4. Demostrar y podar dependencias residuales: llama-cpp-python, ProDy, Gemmi,
   Paramiko, PostHog, brain.js, Argon2/passlib.
5. Unificar los dos adaptadores xTB.

### P2 — gobernanza continua

1. Generar este inventario parcialmente desde manifests/SBOM y comprobar en CI
   que las rutas citadas existen.
2. Añadir un gate que compare **archivos del bundle** contra el SBOM.
3. Registrar en cada corrida no sólo el nombre de la tecnología, sino versión,
   hash del artefacto, configuración y condición de aplicabilidad.
4. Revisar trimestralmente CVE y licencias con una fuente de red actualizada;
   el SBOM offline no es un escáner de vulnerabilidades.

---

## 18. Checklist para añadir una tecnología nueva

No se considera integrada hasta responder y verificar todo lo siguiente:

- [ ] ¿Es motor, librería, modelo, servicio, formato o herramienta de build?
- [ ] ¿Qué necesidad concreta resuelve y qué dependencia reemplaza o añade?
- [ ] ¿Se ejecuta en desarrollo, en el bundle, o en ambos?
- [ ] ¿Qué ocurre si falta, falla, cambia el hash o queda fuera de dominio?
- [ ] ¿El resultado persiste versión, configuración, entrada, salida y motivo de abstención?
- [ ] ¿Tiene prueba unitaria, de integración, de artefacto y VM en proporción al riesgo?
- [ ] ¿Figura en el SBOM real y en las licencias externas?
- [ ] ¿Su licencia permite el modo exacto de distribución y uso?
- [ ] ¿Hace red? Si sí, ¿es visible, opt-in y prescindible para el núcleo local?
- [ ] ¿La UI describe exactamente lo que ejecuta, sin renombrar un fallback como otro motor?
- [ ] ¿Existe un benchmark externo o control positivo/negativo que sostenga la afirmación científica?
- [ ] ¿Se puede retirar sin perder la capacidad de reconstruir expedientes antiguos?

---

## 19. Archivos canónicos para mantener este mapa

| Tema | Fuente |
|---|---|
| Runtime Python distribuido | `python-embed/` y `docs/api/sbom.json` |
| Dependencias Python deseadas | `backend/requirements-desktop.txt` |
| Frontend de producción | `frontend/package.json` y `frontend/package-lock.json` |
| Contenedor Rust | `frontend/src-tauri/Cargo.toml` y `Cargo.lock` |
| Recursos copiados | `scripts/bundle_helper.py` y `frontend/src-tauri/tauri.conf*.json` |
| Modelos descargables | `launcher-manifest.json` |
| Modelos de rescoring | `rescoring/artifacts/model-manifest.json` y `.metadata.json` |
| M5-Zn | manifiesto generado por `scripts/generate_m5_manifest.py` |
| Open Babel | `tools/openbabel/openbabel-manifest.json` |
| Motores ofrecidos | `GET /evaluation/engines` y pruebas `ENG-*` |
| Capacidades científicas | `AGENTS.md`, docs 74–77 y goldens de dossier |
| Licencias | `LICENSE`, `LICENSE-MODELS`, `frontend/public/legal/`, SBOM |
| Release real | `release-manifest.json`, `.sha256`, smoke de producción y acta de VM |

Cada cambio en estas fuentes puede volver obsoleta una fila. La fecha y el
commit de cabecera deben actualizarse sólo después de repetir el censo sobre el
artefacto que se pretende entregar.
