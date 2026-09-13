> **Documento histórico — julio de 2026.** Escrito para el árbol anterior del
> proyecto (`moldesign-app`) y traído aquí por trazabilidad. Puede describir un
> estado que ya no es el vigente: la versión 1.0.0 es una aplicación de
> escritorio y no tiene componente en la nube. No se ha reescrito su contenido.

# Propuestas de Mejora y Pulido Científico del Backend (v2)
**Archivo**: `docs/propuestas_de_mejora.md`  
**Última revisión**: Julio 2026  

Este documento recopila las oportunidades reales de mejora identificadas en el backend de **MolDesign AI** para elevar la **eficiencia de procesamiento**, la **calidad del código** y la **validez de los resultados científicos**, sin sacrificar ninguno de estos tres parámetros.

---

## 🛠️ OPORTUNIDADES DE MEJORA Y ACCIONES RECOMENDADAS

### 1. [CALIDAD Y VALIDEZ] Solución al Desfase del Hash de Protonación (Dimorphite-dl)
*   **Problema**: En `conformer.py`, la molécula se protona fisiológicamente a pH 7.4 usando `dimorphite_dl` (por ejemplo, `CCN` pasa a ser `CC[NH3+]`). Debido a esto, el hash se recalcula en caliente y los archivos del conformero y de poses de docking en MinIO/S3 se guardan bajo el **hash protonado**. Sin embargo, la base de datos almacena el registro `MoleculeORM` con el **SMILES neutro original y su hash neutro**.
*   **Impacto**: Cuando el usuario intenta ver las interacciones tridimensionales en `interactions.py` (L66), la API consulta la base de datos, obtiene el hash neutro e intenta buscar el archivo de poses. Dado que el archivo se guardó con el hash protonado, la consulta a disco/MinIO devuelve `None` y la interfaz lanza un error **503 "Docked poses not found"** para cualquier compuesto que cambie su estado de carga a pH 7.4.
*   **Solución**: Unificar el flujo de validación y protonación. La función `create_or_get_molecule` en el repositorio debe ejecutar la validación, tautomería y protonación a pH 7.4 **antes** de calcular el hash e insertar el registro en la base de datos. De este modo, el hash en base de datos coincidirá siempre con el hash físico y se eliminarán los fallos de carga en el visor de interacciones de ProLIF.

---

### 2. [EFICIENCIA] Activación de Inferencia Vectorizada de Rescoring (`predict_batch_rescore`)
*   **Problema**: En `rescoring_service.py` (L180) existe la función `predict_batch_rescore(molecules: list[dict])`, diseñada para agrupar múltiples moléculas en una sola llamada de inferencia XGBoost. Sin embargo, **esta función está huérfana de invocación** en todo el backend; cuando el sistema genera análogos o realiza screenings de múltiples compuestos, los puntúa iterando secuencialmente uno a uno.
*   **Impacto**: Latencia innecesaria y sobrecarga en el procesamiento de bibliotecas de moléculas.
*   **Solución**: Integrar `predict_batch_rescore` en `analog_generator.py` y en la cola de tareas de screening para procesar de golpe todas las moléculas listas para rescoring. Esto ofrece un **speedup de 10x a 50x** al procesar lotes de $N \ge 10$ compuestos.

---

### 3. [VALIDEZ CIENTÍFICA] Caja de Docking Adaptativa (Grid Box Clipping Prevention)
*   **Problema**: Si el tamaño real de la conformación 3D del ligando (especialmente en macrociclos o péptidos de nivel 3) supera las dimensiones de la caja de docking (Grid Box) de la diana, AutoDock Vina recortará la estructura. El ligando no cabrá en la caja o partes del mismo quedarán fuera del campo de fuerzas, produciendo afinidades inválidas o fallos de cálculo.
*   **Impacto**: Falsos negativos y scores de afinidad físicamente imposibles.
*   **Solución**: Calcular las dimensiones máximas del conformero del ligando en Å antes del docking a través de su matriz de coordenadas 3D en RDKit:
    ```python
    conf = mol.GetConformer()
    coords = conf.GetPositions()
    ligand_dimensions = coords.max(axis=0) - coords.min(axis=0)
    ```
    Si cualquiera de las dimensiones del ligando más un margen de solvatación de $4.0\text{ Å}$ supera la dimensión de la caja (`box_size`), el backend debe **redimensionar dinámicamente el Grid Box** o lanzar una alerta científica de clipping estructural en el reporte final.

---

### 4. [VALIDEZ CIENTÍFICA] Detección y Alerta de Estereocentros Indefinidos
*   **Problema**: Si el usuario introduce un SMILES con carbonos asimétricos sin especificar su estereoquímica (por ejemplo, usando `CC(O)C(=O)O` en lugar de la forma explícita `C[C@@H](O)C(=O)O`), RDKit elegirá una conformación quiral de forma totalmente aleatoria al generar el conformero 3D.
*   **Impacto**: Sesgo científico. Se evalúa un único enantiómero aleatorio en el docking, cuando en el laboratorio el compuesto se sintetizaría como una mezcla racémica o podría requerir la purificación del enantiómero activo.
*   **Solución**: Analizar los centros quirales antes del modelado usando `Chem.FindMolChiralCenters(mol, includeUnassigned=True)`. Si se detecta un estereocentro no asignado, el backend debe:
    1.  Añadir una advertencia científica explícita en los metadatos del resultado indicando que se ha evaluado un estereoisómero arbitrario.
    2.  Opcionalmente, enumerar las formas enantioméricas en el pipeline para permitir al usuario evaluar las diferencias de binding entre isómeros.
