> **Documento histórico — julio de 2026.** Escrito para el árbol anterior del
> proyecto (`moldesign-app`) y traído aquí por trazabilidad. Puede describir un
> estado que ya no es el vigente: la versión 1.0.0 es una aplicación de
> escritorio y no tiene componente en la nube. No se ha reescrito su contenido.

# Backlog de Arquitectura: Tecnologías Futuras y Viabilidad (MolDesign v2.0+)

**Documento Objetivo:** Dirigido a Ingenieros de Software Senior y Arquitectos de Datos.
**Propósito:** Evaluar tecnologías emergentes en Química Computacional (*CADD*) y su viabilidad de integración en la arquitectura actual de MolDesign. El objetivo es escalar el rendimiento (Throughput), la precisión (Accuracy) y mantener la filosofía de despliegue *Zero-Conda* / *Windows-Native*.

Se clasifican desde las más críticas y viables, hasta las menos recomendadas.

---

## 1. Prioridad CRÍTICA (Implementación Inmediata / Alta Viabilidad)

### 1.1 Caché Cuántico Persistente (Memoria Muscular)
* **Concepto:** `MolChamb v2.0` ejecuta el binario GFN2-xTB en cada evaluación (~30s por molécula). Dado que las cargas de Mulliken en el vacío son independientes del receptor (Target), recalcular una molécula que ya fue vista en otra campaña de screening es un desperdicio del 100% de CPU.
* **Integración:** Un diccionario persistente (ej. `sqlite3` o `LMDB`) tipo Key-Value donde `Key = SHA256(Canonical_SMILES)` y `Value = JSON(cargas_cuanticas)`. 
* **Viabilidad:** **10/10**. Requiere <50 líneas de código en `compute_quantum_features.py`. No añade dependencias pesadas.
* **Impacto:** Reduce el O(N) del cómputo cuántico a O(1) para librerías previamente cacheadas. Velocidad de MolChamb baja de 30s a 1ms por hit en caché.

### 1.2 Delta Machine Learning (Δ-ML) para Corrección de Vina
* **Concepto:** En lugar de que XGBoost intente predecir la afinidad biológica absoluta, el modelo aprende a predecir el **error residual** de AutoDock Vina. Score_Final = Score_Vina + Prediccion_Error(XGB).
* **Integración:** Cambiar el target de entrenamiento (`y`) de la regresión logística/XGBoost.
* **Viabilidad:** **9/10**. Es un cambio puramente matemático en `engine.py` y el script de entrenamiento. 
* **Impacto:** La literatura reciente demuestra que Δ-ML requiere datasets mucho más pequeños para generalizar, porque la física base (Vina) ya hace el 80% del trabajo pesado.

### 1.3 Pharmacophore Constraint Docking (Anclaje Guiado por Conocimiento)
* **Concepto:** Vina explora a ciegas. Si el investigador sabe que el fármaco *debe* hacer un puente de hidrógeno con el Aspartato 25 (ej. VIH), se puede forzar a Vina (versiones modernas como 1.2.3 o Meeko) a añadir una penalización infinita si la pose no cumple este farmacóforo.
* **Integración:** Pasar restricciones geométricas (`--weight_hbond`) a través de la API de Meeko/Vina.
* **Viabilidad:** **9/10**. Usa las librerías actuales, solo expone parámetros avanzados a la UI/API.
* **Impacto:** Mejora la calidad de la pose (RMSD) dramáticamente en targets difíciles sin aumentar el tiempo computacional.

---

## 2. Prioridad ALTA (Escalamiento y Modelado Complejo / MolDesign v2.0)

### 2.1 Active Learning con Funciones de Adquisición (El Radar Minero)
* **Concepto:** Escalar el pipeline para procesar 100 millones de compuestos es imposible por fuerza bruta. El *Active Learning* propone dockear el 0.1% de la librería al azar, entrenar un modelo sustituto (*Surrogate Model*) en segundos, predecir la librería completa, y luego solo enviar a Vina el Top 1% más prometedor.
* **Integración:** Requiere refactorizar `queue_handler.py` de un flujo *lineal* a un ciclo de retroalimentación *iterativo* (Sample -> Dock -> Train -> Predict -> Filter). 
* **Viabilidad:** **7/10**. Tecnológicamente simple, arquitectónicamente complejo. 
* **Impacto:** Aceleración teórica de 100x a 1000x en *Virtual Screening* masivo.

### 2.2 IA Generativa para Scaffold Hopping (Invención vs Búsqueda)
* **Concepto:** Transformar MolDesign de un motor de *búsqueda* a uno de *invención*. En lugar de cribar librerías estáticas, el usuario proporciona un *Hit* y un modelo Fundacional (ej. Transformer/Diffusion) genera 10,000 derivados patentables y sintetizables de novo, que luego son evaluados por MolChamb.
* **Integración:** Reemplazar el generador determinista (BRICS) por un LLM entrenado en SMILES (ej. MolMIM o ChemGPT).
* **Viabilidad:** **6/10**. Requiere inferencia de modelos pesados, quizás consumiendo una API externa (OpenAI/HuggingFace) para mantener el cliente ligero.
* **Impacto:** Cierra el ciclo de diseño de fármacos, saltando la barrera de la propiedad intelectual de compuestos existentes.

### 2.3 Ensemble Docking (Selección Conformacional)
* **Concepto:** Las proteínas respiran. Usar *Normal Mode Analysis (NMA)* (ej. ProDy) para generar 3-5 conformaciones ligeramente distintas del bolsillo receptor. Dockear contra todas y extraer el `MAX()`.
* **Integración:** `ProDy` es pip-installable. Paralelizar llamadas a Vina.
* **Viabilidad:** **8/10**. Aceptable costo computacional (3x) por un inmenso salto en fidelidad termodinámica.

### 2.4 Agentes Autónomos CADD (MolChat v2.0)
* **Concepto:** Un Agente LLM que lee papers recientes en PubMed sobre un target biológico, extrae los residuos clave (farmacóforos), configura las cajas de Vina de manera autónoma (Neurocirugía), lanza el *pipeline* y redacta el informe final de los 10 mejores *hits*.
* **Integración:** Extender `MolChat` con herramientas de *RAG* (Retrieval-Augmented Generation) y acceso directo a la consola de MolDesign.
* **Viabilidad:** **8/10**. Es el pináculo del SaaS. "Descubrimiento de fármacos con un solo prompt".

---

## 3. Prioridad BAJA (Rompen la Arquitectura o Altamente Ineficientes)

### 3.1 QM/MM Híbrido para Metaloenzimas
* **Concepto:** Para targets como CA2 (Zinc), calcular el bolsillo activo usando Mecánica Cuántica (xTB) y el resto de la proteína con Mecánica Molecular (OpenMM).
* **Por qué NO:** Demasiado lento. Rompe la velocidad del Screening (tardaría horas por molécula). Las fallas con metales se corrigen mejor usando *Fingerprints* (ProLIF) y Machine Learning en lugar de forzar la termodinámica híbrida.

### 3.2 Pre-plegamiento Generativo del Ligando (AI Conformer Generation)
* **Por qué NO:** IAs como GeoMol predicen conformaciones en el vacío, ignorando el bolsillo proteico (*Induced Fit*). Vina ya es extremadamente eficiente encontrando la conformación in-situ con algoritmos genéticos.

### 3.3 Vina-GPU / AutoDock-GPU
* **Por qué NO:** Requiere OpenCL/CUDA Toolkits locales, destruyendo la compatibilidad "Zero-Conda" de Windows. La aceleración masiva se logra mejor vía *Active Learning* (2.1) sin tocar los drivers del usuario final.

---

## 4. El Efecto "Navaja Suiza" (Sinergias Híbridas de Módulos Actuales)
*Sección dedicada a combinaciones innovadoras orquestando los módulos que ya existen en el repositorio actual.*

### 4.1 Generación de Análogos Guiada por Termodinámica (BRICS + MolChamb v2)
* **Concepto:** Actualmente, BRICS rompe una molécula y ensambla fragmentos al azar o guiado por reglas 2D. Si extraemos las cargas cuánticas de los 2,756 fragmentos de la librería vía xTB, podemos ordenar a BRICS que ensamble fragmentos condicionado a la electrostática de la proteína (ej. si el bolsillo es electronegativo, BRICS solo ensambla fragmentos electropositivos).
* **Viabilidad:** **10/10**. Ambos módulos ya están programados.
* **Impacto:** Multiplica el *Hit-Rate* de derivados generados.

### 4.2 CL-GNN Condicionado por ProLIF (Grafos Interactivos)
* **Concepto:** El GNN actual construye grafos basados en átomos y enlaces covalentes. Si inyectamos las interacciones 3D detectadas por ProLIF (ej. "Nodo de Puentes de Hidrógeno", "Arista de Pi-Stacking") directamente en la topología de PyTorch Geometric, el GNN deja de ser ciego a la proteína.
* **Viabilidad:** **9/10**. Requiere modificar la capa de *Message Passing* del GNN para aceptar aristas heterogéneas.
* **Impacto:** Resuelve el problema de Metaloenzimas definitivamente, ya que la coordinación del Zinc se convierte en un nodo explícito en el grafo de la red neuronal.

### 4.3 Salida Temprana Cuántica (The Quantum Early-Exit)
* **Concepto:** Ejecutar xTB en el SMILES *antes* de enviarlo a AutoDock Vina. Si la métrica cuántica del ligando (ej. Dipolo, energía HOMO/LUMO) choca drásticamente con el perfil del bolsillo, se aborta la molécula inmediatamente.
* **Viabilidad:** **10/10**. Solo requiere mover el llamado a xTB al script `molgraph.py` (Early Exit).
* **Impacto:** Ahorra el 100% del costo computacional de Vina y OpenMM para moléculas que termodinámicamente no tienen oportunidad.

### 4.4 Ensamble Predictivo Híbrido (Consensus Folding + XGBoost)
* **Concepto:** Dockear el ligando contra 3 variantes distintas de la proteína (Apo, Holo, AlphaFold). Extraer Vina y ProLIF de las 3, y pasar los 3 vectores a un único modelo XGBoost.
* **Viabilidad:** **10/10**. Puramente orquestación.
* **Impacto:** El XGBoost aprende automáticamente la flexibilidad de la proteína y el efecto de *Induced-Fit*, decidiendo en qué conformación "confiar" más para cada molécula específica.

---
**Conclusión de Arquitectura:** 
El equipo debe enfocarse inmediatamente en el **Caché Cuántico (1.1)** y el **Anclaje Guiado (1.3)**. Para la versión 2.0 (Comercial/Enterprise), la fusión de **Agentes Autónomos (2.4)** orquestando **Active Learning (2.1)** y las **Sinergias Híbridas (Sección 4)** convertirá a MolDesign en el estándar de facto, haciendo irrelevantes los cuellos de botella de hardware de herramientas clásicas como Schrödinger.
