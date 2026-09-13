> **Documento histórico — julio de 2026.** Escrito para el árbol anterior del
> proyecto (`moldesign-app`) y traído aquí por trazabilidad. Puede describir un
> estado que ya no es el vigente: la versión 1.0.0 es una aplicación de
> escritorio y no tiene componente en la nube. No se ha reescrito su contenido.

De acuerdo con la documentación más reciente del proyecto (especialmente en docs/SESSION_SUMMARY_v1.6.md y el 
docs/roadmap.md)

1. ¿En qué nos quedamos? (Logros de la versión v1.6)
La última sesión (v1.6, finalizada alrededor del 9 al 11 de julio de 2026) se enfocó en resucitar el pipeline de docking, corregir bugs críticos de simulación y universalizar el flujo de trabajo sin valores hardcodeados:

Corrección de 8 bugs críticos: Se solucionaron problemas que provocaban que varios targets clave (como PDE5, MMP9 y GLP-1R) tuvieran 0 dockings exitosos. Entre estos parches destacan:
Recorte de cadena principal (chain trimming): Evita dockear contra dímeros/tetrámeros enteros reduciendo el tamaño del receptor (ej. MMP9 de 5.8MB a 146KB).
Sanitización de PDBQT (_sanitize_pdbqt_rigid): Remoción de tags ROOT/BRANCH/ENDBRANCH generados por OpenBabel que causaban errores de parseo en Vina.
Centros dinámicos: Carga de centros correctos para el sitio activo desde 
curated_targets.csv en vez de coordenadas fijas erróneas.

Pipeline Universal y Dinámico:
Los pesos de combinación (stacking) ahora se cargan dinámicamente desde 
stacking_weights.json
La familia estructural del receptor se auto-detecta usando regex y bases de datos curadas (structural_family.py)
Se descubren automáticamente unos 390 targets PDB en local o descargándolos directamente de la base de datos RCSB.
Benchmarks Ejecutados: Se completaron los benchmarks en targets como 5-HT1A, CDK2, HIV-protease, ER-alpha, Factor Xa, AChE, y CA2.

2. Lo que ya está desarrollado pero sigue "Offline" (Desconectado)
Existen varios módulos de infraestructura científica y aprendizaje automático ya codificados, pero que actualmente no están conectados al flujo principal de producción:

AutoRecalibrator: El código de recalibración automática de configuraciones (auto_recalibrator.py) está listo pero no conectado al pipeline principal.
MM-GBSA Real: El cálculo avanzado de MM-GBSA (molchamb_v2.py) está completo, pero en producción el score de MM-GBSA se mantiene hardcodeado temporalmente como None.
Features Metálicas e Interacciones de Zinc: Las herramientas en protein_surgery.py detectan metales (como Zn²⁺, Fe, Mg), pero solo emiten advertencias en lugar de alimentar al modelo de Machine Learning (crítico para metaloenzimas como CA2 o MMP9).
Features Cuánticas: Se calculan las 19 features cuánticas usando xTB (compute_quantum_features.py) pero no se usan como inputs para XGBoost.

3. Próximos Pasos (Plan de Conexión)
Los siguientes pasos están priorizados según su urgencia y complejidad técnica:

🛠️ Fase A: Correcciones Inmediatas (1-2 horas)
Solucionar mismatch de pesos en GNN-v2: Corregir un error de checkpoint en el tensor residue_bias.weight de la red neuronal. (esto nose si sea verdad, hay que comprobarlo)

🔌 Fase B: Conexión de Infraestructura Existente (1 día)
Conectar MM-GBSA: Modificar queue_handler.py para que le pase el mmgbsa_score real calculado a engine.py (lo cual proveerá una señal energética muy importante para el solvente). (por verificar, no quiero romper nada que ya funciona)
Conectar AutoRecalibrator: Configurar engine.py para consultar en runtime SciConfigRegistry y aplicar recalibración automática por target. (hemos hecho el pipeline universal y dinamico al 100%, solo nos falta comprobar si aun no lo conectamos correctamente)
Integrar Metales a ML: Pasar las features de metales extraídas por protein_surgery.py directamente al vector de descriptores de Machine Learning. (o conviene mejor hacer un modelo especializado en metaloenzimas?, nose si valga la pena el esfuerzo)
🧠 Fase C: Mejoras del Modelo (2-3 días)
Features Cuánticas en XGBoost: Integrar las 19 features de xTB (física cuántica) al set de entrenamiento de XGBoost para enriquecer la predicción de afinidad molecular. (vale la pena?, ya funciona tal cual como está, creo que seria un retroceso mover lo que ya funciona)
Entrenar modelo específico para Metaloenzimas: Crear model_a_metaloenzyme usando datos específicos de PDBbind con metales de transición coordinados (como Zinc) para compensar que Vina no parametriza metales.
Validación estadística para el Paper: Implementar validación cruzada con división por andamios moleculares (scaffold split) y Bootstrap CI para dar robustez científica a los resultados. (creo que esto es lo unico que vale la pena en esta fase)
⚖️ Fase D: GAFF2 & Entorno Python (Decisión Arquitectónica)
Actualmente, openff-toolkit no compila en Python 3.14, lo que limita a MM-GBSA a moléculas con átomos de C, H, O, N, S, P (dejando fuera los halógenos de los decoys DUD-E). Debemos elegir una de las siguientes opciones:

Opción A: Aceptar la limitación actual de C,H,O,N,S,P y documentarla formalmente.
Opción B: Migrar el backend a Python 3.12 (donde sí funciona openff-toolkit). Tengo miedo de esta opcion, siento que se romperá todo el flujo de trabajo que ya hemos logrado con pythhon 3.14.
Opción C: Ejecutar un subproceso (subprocess) hacia un entorno Conda aislado con Python 3.12 + OpenFF solo para la tarea de MM-GBSA. (esto podriamos intentarlo pero lamentablemente no creo que sea viable para el producto comercial final)
--------------------------------------------------------

1. Discrepancias Científicas y ML (Validación y Rigor)
De acuerdo con 
docs/08_SCIENTIFIC_VALIDATION.md
 (Sección 4), existen inconsistencias que deben resolverse antes de poder publicar o lanzar comercialmente la herramienta:

SHAP Dependence y Análisis por Familia: Falta generar los gráficos de dependencia SHAP y el análisis de atribución de importancia de descriptores separados por cada familia de receptores. (hay que comprobar la veracidad de esto)
2. Componentes de Arquitectura "Desconectados" o Fuera de Línea
Varias funcionalidades clave están programadas pero permanecen desconectadas del flujo de producción:

Early Exit con MolGraph (Pre-filtro de Docking):
Problema: Aunque la lógica para descartar de forma segura compuestos inactivos está escrita en predict_early_exit() (
backend/services/ai/molgraph.py#L505
), esta no está conectada en el encolador de docking (
backend/services/docking/queue_handler.py
). Conectarla ahorraría entre un 15% y 20% de tiempo computacional en screenings masivos.
Cálculo Real de MM-GBSA (MolChamb v2): El backend tiene listo el cálculo avanzado de relajación por solvente implícito en 
molchamb_v2.py
, pero la variable mmgbsa_score está hardcodeada como None en la cola de procesamiento. (compruebalo)
Integración de Features de Metales: El script protein_surgery.py detecta e identifica átomos de Zinc o Hierro en metaloenzimas, pero estas interacciones solo emiten advertencias en lugar de inyectarse como descriptores en el modelo de regresión XGBoost.
3. Calidad y Validez Científica en el Backend (Propuestas de Mejora)
En el backend científico (docs/propuestas_de_mejora.md), se detectan los siguientes problemas:

Desfase en el Hash de Protonación (Dimorphite-dl):
Problema: En conformer.py la molécula se protona fisiológicamente a pH 7.4. Esto altera la SMILES y su Hash. Los archivos de conformaciones 3D y poses resultantes se guardan bajo el hash protonado. Sin embargo, la base de datos registra la molécula con el hash neutro original. (podriamos guardar los 2 y especificar cada uno)
Impacto: Provoca un error 503 "Docked poses not found" al intentar abrir el visor 3D Molstar para cualquier molécula que cambie su estado de carga a pH 7.4.
Inferencia Vectorizada Inactiva: La función predict_batch_rescore() en rescoring_service.py puede puntuar múltiples compuestos a la vez con XGBoost, pero no está conectada. Su activación en cribados masivos y generadores de análogos promete aceleraciones de 10x a 50x. (hay que comprobarlo)
Caja de Docking Adaptativa (Clipping de Ligandos): Si el conformero de un ligando muy grande (macrociclo o péptido) supera las dimensiones del Grid Box del receptor, AutoDock Vina recortará la estructura, provocando fallos en la simulación. Se debe calcular la diagonal máxima en Å vía RDKit para redimensionar dinámicamente la caja con un buffer de 
4.0A˚
4.0A˚.
Detección de Estereocentros Indefinidos: Cuando un usuario introduce un SMILES quiral indefinido, RDKit genera una conformación 3D eligiendo un enantiómero aleatorio. Se requiere implementar un análisis con Chem.FindMolChiralCenters para alertar al usuario o mapear todos los enantiómeros posibles en el docking.
4. Distribución en Steam e Integración Desktop (Tauri + Steamworks)
De cara a distribuir la aplicación en Steam (
docs/posibles_problemas_y_mejoras.md
 y 
docs/17_STEAM_DEPLOYMENT.md
):

Procesos Zombies de Python: Al forzar el cierre de la app desde Tauri o Steam, el backend de FastAPI puede quedarse huérfano y retener el puerto :8000. Es necesario programar un hilo Heartbeat que mate automáticamente el proceso de Python si detecta que el proceso padre (Tauri) ya no existe. (creo que esto ya esta implementado, verificalo)
Rutas de Escritura y Permisos: Evitar que SQLite y los logs escriban en el directorio de instalación (e.g., Program Files), redireccionando todo el almacenamiento local obligatoriamente a %APPDATA% o al directorio de usuario (~/MolDesign/data/).
Wrapper del SDK de Steamworks: Instalar e integrar steamworks.js en Tauri para desbloquear logros en Steam, sincronizar partidas/bases de datos mediante Steam Cloud, y habilitar tablas de clasificación de afinidades (Steam Leaderboards).
Firma de Código (Code Signing) y Antivirus: Para evitar que Windows Defender bloquee o elimine vina.exe o xtb.exe por falsos positivos, se requiere adquirir un certificado comercial de firma de código (Sectigo/DigiCert) y firmar todos los binarios y el instalador .msi.
 
