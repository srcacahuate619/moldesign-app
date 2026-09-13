> **Documento histórico — julio de 2026.** Escrito para el árbol anterior del
> proyecto (`moldesign-app`) y traído aquí por trazabilidad. Puede describir un
> estado que ya no es el vigente: la versión 1.0.0 es una aplicación de
> escritorio y no tiene componente en la nube. No se ha reescrito su contenido.

# Auditoría de Tecnologías y Alternativas (Schrödinger vs MolDesign)

> **Documento de Investigación:** Evaluación de tecnologías de código abierto para cerrar la brecha con la suite propietaria de Schrödinger (~30% de capacidades faltantes), manteniendo el enfoque de bajos recursos computacionales y el empaquetado pip/Tauri.

---

## 1. El Objetivo: Cerrar la Brecha con Schrödinger

La suite de Schrödinger es el estándar de oro (y extremadamente costoso) en la industria farmacéutica. Actualmente, MolDesign cubre excelentemente las fases tempranas de cribado (Virtual Screening, Rescoring con IA, ADMET). Sin embargo, carece de las herramientas rigurosas necesarias para la optimización final (Hit-to-Lead), específicamente:

| Capacidad de Schrödinger | ¿Por qué es vital? | Alternativa Open-Source Investigada |
|--------------------------|-------------------|-------------------------------------|
| **FEP+**                 | Calcula la diferencia exacta de energía entre análogos. | **RBFE Acelerado por IA** (Delta-Learning) |
| **WaterMap**             | Mapea el agua atrapada en la proteína. | **3D-RISM** |
| **Induced Fit Docking**  | Adapta la forma de la proteína al fármaco. | **Smina** (Fork de Vina) |
| **Phase (Farmacóforos)** | Filtra millones de moléculas por geometría 3D. | **pmapper** (RDKit) |

A continuación, se detalla la viabilidad de integrar cada alternativa en la arquitectura actual de MolDesign (Windows local, Tauri, sin dependencias de `conda`).

---

## 2. RBFE Acelerado por IA (Relative Binding Free Energy)

**¿Para qué sirve?**
Predice el $\Delta\Delta G$ relativo entre dos moléculas análogas sin hacer simulaciones físicas de días de duración. 

**¿Cómo encaja en MolDesign?**
Altamente compatible. MolDesign ya utiliza PyTorch Geometric (PyG) para el modelo RTMScore y RDKit. Se implementaría entrenando un modelo GNN para tomar "pares" de ligandos, utilizando el puntaje rápido de MM-GBSA como línea base y aplicando correcciones termodinámicas por IA.

* **Ventajas (Lo bueno):** 
  * Velocidad extrema (fracciones de segundo vs días enteros del FEP+ de Schrödinger).
  * 100% compatible con tu pipeline de Python y PyTorch actual.
* **Desventajas (Lo malo):** 
  * Sufre de mala extrapolación (falla si la IA ve un "scaffold" o esqueleto que no estaba en sus datos de entrenamiento).
  * Ignora efectos entrópicos complejos del solvente a menos que estén modelados explícitamente.

---

## 3. 3D-RISM (Reference Interaction Site Model)

**¿Para qué sirve?**
Es el equivalente matemático a *WaterMap*. Resuelve ecuaciones integrales para predecir dónde se ubicarán las moléculas de agua alrededor de la proteína, sin necesidad de simular Dinámica Molecular.

**¿Cómo encaja en MolDesign?**
**Compatibilidad crítica / Muy problemática.** 

* **Ventajas (Lo bueno):** 
  * Físico-química rigurosa y ampliamente validada.
  * Predice la posición del agua con altísima precisión geométrica, más rápido que una simulación MD explícita.
* **Desventajas (Lo malo):**
  * Sobre-estabiliza la densidad del agua en cavidades hidrofóbicas (predice agua donde no la hay).
  * Las energías absolutas calculadas suelen estar erradas.
  * **Empaquetado:** 3D-RISM (`rism3d.snglpnt` de AmberTools) es un binario pesado en C/Fortran que normalmente requiere `conda`. Incluir esto en un instalador `.msi` de Windows "stand-alone" sería una pesadilla técnica de compilación cruzada.

---

## 4. Smina (Docking Flexible - Induced Fit Ligero)

**¿Para qué sirve?**
Es un fork avanzado de AutoDock Vina que permite especificar qué cadenas laterales (rotámeros) de la proteína pueden rotar y adaptarse durante el docking, emulando el protocolo *Induced Fit Docking (IFD)* de Schrödinger de manera ligera.

**¿Cómo encaja en MolDesign?**
**Totalmente compatible.** Es un reemplazo casi transparente. Smina es un ejecutable en C++ (igual que Vina o QuickVina 2). Solo requiere colocar `smina.exe` en la carpeta `externalBin` de Tauri.

* **Ventajas (Lo bueno):** 
  * Se implementa en minutos sin romper la arquitectura.
  * Resuelve la limitación de Vina frente a choques estéricos cuando un ligando es ligeramente más voluminoso que la bolsa original.
* **Desventajas (Lo malo):**
  * **Limitación estructural:** Solo flexiona las cadenas laterales. Si el "backbone" (esqueleto) de la proteína necesita abrirse o moverse (algo que Prime/Glide de Schrödinger sí hacen iterando), Smina fracasará.
  * Usar flexibilidad en más de 5 residuos paraliza el algoritmo por explosión combinatoria.

---

## 5. pmapper (Farmacóforos 3D por Hashes)

**¿Para qué sirve?**
Emula la capacidad de cribado ultra-rápido espacial de *Phase*. Convierte una molécula 3D y sus propiedades (donadores, anillos) en una "firma" (fingerprint) o hash para comparación casi instantánea.

**¿Cómo encaja en MolDesign?**
**Totalmente compatible.** Es una librería nativa de Python optimizada para funcionar sobre `RDKit`.

* **Ventajas (Lo bueno):** 
  * Velocidad absurda. Permite filtrar un millón de moléculas en segundos directamente en RAM.
  * Se integra vía `pip` y no daña el instalador de Windows.
  * Funciona como un pre-filtro ideal antes de que las moléculas pasen al embudo de AutoDock Vina y las redes GNN.
* **Desventajas (Lo malo):**
  * La trampa de las conformaciones. Para no descartar moléculas por accidente (falsos negativos), debes pre-generar computacionalmente cientos de conformaciones 3D válidas para *cada* molécula de la base de datos antes de generar los hashes.
  * Demanda alto consumo de disco/RAM en la etapa de preparación (antes de buscar).

---

## Recomendación de Integración Inmediata

Si el objetivo es potenciar el pipeline de MolDesign hacia el producto comercial (v2.0) sin comprometer el bajo consumo de recursos y la arquitectura `.msi`:

1. **Implementar Smina inmediatamente:** Proporciona un gran impacto tecnológico ("Docking con Proteína Flexible") sin costo de arquitectura.
2. **Integrar pmapper:** Útil como motor de pre-filtrado si se van a soportar bases de datos masivas (millones de compuestos).
3. **Descartar 3D-RISM:** El costo de compilación y empaquetado para Windows supera ampliamente el valor para el usuario final.
4. **I+D a largo plazo para FEP+:** Iniciar investigación en RBFE basado en GNN, apalancándose en la infraestructura matemática (PyTorch Geometric) que ya se desarrolló para RTMScore.
