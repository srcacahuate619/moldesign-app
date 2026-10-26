# Historias moleculares — MolDesign Scientific Assets

**Versión:** 2.0 · 20 de septiembre de 2026  
**Propósito:** catálogo editorial y técnico para transformar los resultados estructurales y computacionales de MolDesign en animaciones comprensibles, atractivas y científicamente trazables mediante Blender.  
**Estado:** propuesta de producción; las estructuras, interacciones y mecanismos de cada nuevo caso deberán comprobarse antes de publicar.

> **Tesis de producto:** no vender únicamente modelos 3D de proteínas: explicar visualmente **qué cambia, qué se observa, qué se predice y por qué importa**. La espectacularidad debe proceder de la cámara, la iluminación, la composición y los datos, no de inventar un mecanismo molecular.

## 1. Dos protocolos complementarios

| Dimensión | Protocolo Protagonista — historias individuales | Protocolo Campaña — historias en lote |
|---|---|---|
| Propósito | Explicar un mecanismo molecular concreto con comienzo, contraste y conclusión. | Ofrecer un catálogo visual consistente de receptores y sitios de unión. |
| Producción | Semiautomática: scripts + revisión editorial y científica por pieza. | Desatendida por worker, con control de calidad y revisión humana de excepciones. |
| Fuente | Varias estructuras/estados, literatura, mediciones, trayectorias si aportan valor. | Un manifiesto de estructura y sitio por receptor; datos adicionales solo cuando existan. |
| Duración orientativa | 12–30 s, según el mecanismo. | Micropreview de 3–5 s + versión de ficha de ~9–20 s. |
| Salidas | Video principal, cortes breves, escena editable, referencias y ficha explicativa. | Miniatura, MP4 optimizado, escena reutilizable y `case.json`. |
| Validación | Revisión científica del guion, estructuras, anotaciones y límites de cada animación. | Verificación automática de entrada, geometría, encuadre, integridad del video y procedencia. |

Los **380 receptores** son un catálogo de entradas, no 380 mecanismos farmacológicos completos: algunos pueden carecer del ligando, del estado funcional o de la evidencia necesaria para una historia específica. No se asumirán cuotas de cobertura por tipo antes de auditar el catálogo real.

---

## 2. Protocolo Protagonista — ideas individuales

Cada historia debe poder expresarse en una pregunta: *¿qué no entiende todavía el espectador y qué le permitirá comprender este video?* Las duraciones son propuestas editoriales, no tiempos físicos de una reacción ni de dinámica molecular.

### Historia 1 — Cuando un fármaco deja de funcionar: resistencia de EGFR

- **Pregunta:** ¿cómo cambia el reconocimiento farmacológico cuando aparece resistencia y qué mecanismo diferente ofrece un inhibidor posterior?
- **Sistema candidato:** EGFR–Erlotinib (`1M17` como referencia de unión al dominio quinasa), una estructura verificada con T790M y un complejo experimental apropiado con Osimertinib. Registrar numeración PDB/canónica y mutaciones adicionales de cada estructura.
- **Guion (18–25 s):** (1) revelar Erlotinib, bolsillo y contacto de bisagra; (2) comparar estados estructurales alineados y presentar el cambio del entorno del *gatekeeper*, junto con la competencia con ATP; (3) cambiar al complejo con Osimertinib y señalar el enlace con Cys797 cuando la estructura lo respalde.
- **Visual protagonista:** bolsillo en superficie semitransparente; superposición de poses en estados distintos; revelado de contactos **verificados**. Las transiciones entre estructuras se rotulan como **comparación/interpolación didáctica**, no como una trayectoria física medida.
- **Análisis:** alineamiento de regiones homólogas, PLIF por estado, distancias y geometría del enlace; datos externos para cualquier afirmación sobre potencia o resistencia clínica.
- **Límite científico:** T790M **no** debe representarse universalmente como una metionina que choca y expulsa a Erlotinib; el aumento de afinidad por ATP en determinados contextos mutacionales es parte importante de la explicación. El *score* de docking no equivale a respuesta clínica.
- **Salida:** hero piece de MolDesign, clip de 5 s y ficha que distingue evidencia experimental de modelado y animación conceptual.

### Historia 2 — La unión que cambia el mecanismo: inhibidores covalentes

- **Pregunta:** ¿qué diferencia el reconocimiento reversible de un inhibidor que forma un enlace covalente con su diana?
- **Sistemas candidatos:** KRAS G12C–Sotorasib/Adagrasib; EGFR–Osimertinib; BTK–Ibrutinib. Seleccionar un complejo con estado covalente y conectividad química inequívocos.
- **Guion (12–18 s):** (1) localizar el bolsillo y mostrar el reconocimiento inicial como **esquema**; (2) primer plano del átomo nucleófilo y del carbono electrofílico; (3) revelar el aducto covalente a partir de la estructura del producto.
- **Visual protagonista:** un enlace C–S emerge en el instante de transición **didáctica** entre estados; la distancia mostrada se calcula desde los átomos identificados del estado al que corresponde.
- **Análisis:** topología y química del aducto, contactos no covalentes pertinentes y referencias del mecanismo. La formación/ruptura del enlace **no** se obtiene por una MD clásica estándar ni por MM-GBSA.
- **Límite científico:** no afirmar que el fármaco desactiva la proteína “para siempre”; la duración del efecto depende también de recambio proteico, exposición y biología celular.

### Historia 3 — La proteína no es una estatua: aperturas y cierres conformacionales

- **Pregunta:** ¿por qué una estructura estática no describe todos los estados funcionales de una proteína?
- **Sistemas candidatos:** proteasa del VIH-1 (flaps abiertos/cerrados, después de confirmar las estructuras elegidas); quinasas DFG-in/DFG-out; GPCR en estados funcionales distintos.
- **Guion (12–18 s):** (1) comparar dos estados experimentales; (2) destacar la región móvil y el cambio en accesibilidad del bolsillo; (3) mostrar el estado con ligando, con sus contactos documentados.
- **Visual protagonista:** *ghost overlay* de conformaciones, superficie del canal, medición de una distancia entre residuos de referencia.
- **Análisis:** correspondencia átomo-residuo, alineamiento, desplazamientos y, opcionalmente, trayectoria OpenMM preparada para estudiar **fluctuaciones locales**.
- **Límite científico:** una interpolación entre estructuras apo y holo no demuestra que la proteína recorrió exactamente ese camino ni que todo cambio obedezca a un “ajuste inducido”; considerar también selección conformacional.

### Historia 4 — El fármaco como pegamento: degradación dirigida de proteínas

- **Pregunta:** ¿cómo puede una molécula pequeña favorecer una nueva interfaz entre proteínas y desencadenar degradación de una diana?
- **Sistema candidato:** complejo estructural **documentado** de una *molecular glue* o un PROTAC; como tema editorial de 2026, investigar el sistema DCAF11–DDX18 asociado a un compuesto activado por glutatión, antes de diseñar la escena.
- **Guion (20–30 s):** (1) mostrar por separado la diana y el componente reclutador; (2) presentar la molécula que estabiliza la proximidad y el complejo ternario **cuando exista una estructura de referencia**; (3) pasar a un diagrama celular estilizado de ubiquitinación y proteasoma.
- **Visual protagonista:** dos superficies proteicas que revelan una nueva interfaz; la parte estructural y la consecuencia celular se separan mediante un rótulo/transition card.
- **Análisis:** interfaz proteína–proteína, distancias, estructura ternaria, mecanismo bioquímico y literatura experimental.
- **Límite científico:** un acoplamiento favorable o una MD corta **no demuestran** ubiquitinación ni degradación; estas etapas requieren evidencia experimental. No recrear un complejo ternario si solo se dispone de estructuras individuales sin rotularlo como hipótesis.
- **Interés editorial:** la degradación dirigida y los *molecular glues* tienen trabajos recientes relevantes (véase sección 7). Esta sería una pieza especial, **no** una plantilla automática aplicada a los 380 receptores.

### Historia 5 — La selectividad invisible: una molécula, dos bolsillos

- **Pregunta:** ¿cómo pueden diferencias entre dianas emparentadas alterar el reconocimiento de un mismo compuesto?
- **Sistemas candidatos:** COX-1/COX-2, familias de CDK u otras parejas con comparaciones experimentales y ligandos claramente identificados.
- **Guion (15–20 s):** (1) alinear las dos proteínas; (2) alternar superficies y residuos diferenciales; (3) comparar poses y contactos respaldados por datos.
- **Visual protagonista:** pantalla dividida sincronizada o transición entre bolsillos alineados, sin teletransportar un fármaco “rechazado” si no hay evidencia de ello.
- **Análisis:** secuencia, geometría local, PLIF, datos experimentales de selectividad cuando existan.
- **Límite científico:** no inferir toxicidad clínica de una única diferencia de residuo ni anunciar “selectividad 1000×” sin mediciones comparables, contexto experimental y fuente.

### Historia 6 — De fragmento a candidato: el diseño racional en el bolsillo

- **Pregunta:** ¿qué se gana —y qué se puede perder— al modificar un grupo químico de un ligando?
- **Sistemas candidatos:** serie publicada de fragmentos/análogos con estructuras comparables y mediciones de afinidad; BACE1 o proteasas son posibles familias a explorar, no series ya seleccionadas.
- **Guion (12–20 s):** (1) revelar fragmento y espacio del bolsillo; (2) comparar **moléculas distintas** mediante alineamiento del andamio común; (3) mostrar contactos ganados, perdidos y regiones expuestas a solvente.
- **Visual protagonista:** morfología comparativa del ligando con rótulo “análogo A → análogo B”; no representar que la molécula muta espontáneamente durante una unión real.
- **Análisis:** estructuras, propiedades, contactos, solvatación y ensayos experimentales publicados.
- **Límite científico:** no convertir un cambio de *score* de docking o MM-GBSA en un salto demostrado de µM a nM; una predicción no equivale a afinidad medida.

### Historia 7 — La molécula y el metal: coordinación en metaloenzimas

- **Pregunta:** ¿qué papel tiene un ion metálico en la arquitectura del sitio activo y en el reconocimiento de ligandos?
- **Sistema inicial:** anhidrasa carbónica con Zn²⁺ (`1BN1`, sujeto a validación de cadena/ligando/estado); luego otra clase de metal o cofactor.
- **Guion (12–16 s):** (1) plano global; (2) descender al metal; (3) revelar sus coordinantes con etiquetas de distancia reales y diferenciar el ligando de referencia.
- **Visual protagonista:** geometría del centro metálico y coordinación, sin brillo tipo “reactor nuclear”.
- **Análisis:** elemento, sitio de coordinación, distancias, estado químico respaldado por la fuente; umbrales dependientes del metal y su entorno.
- **Límite científico:** no asignar automáticamente cataliticidad a cualquier ion presente ni reducir toda coordinación a “distancia menor que 2.4 Å”.

### Historia 8 — La incertidumbre también importa: la misma molécula, distintas poses

- **Pregunta:** ¿por qué el docking entrega poses alternativas y por qué un score no es una prueba de unión?
- **Sistema:** evaluación reproducible de MolDesign con varias poses de un mismo ligando y receptor curado; puede reutilizarse EGFR si hay resultados apropiados.
- **Guion (12–18 s):** (1) presentar dos o tres poses candidatas en el mismo bolsillo; (2) comparar orientación y contactos; (3) mostrar la pose seleccionada junto con el valor y tipo exacto de *score* reportado.
- **Visual protagonista:** superposición controlada de poses, sin mover el ligando como si la interpolación fuera una ruta dinámica.
- **Análisis:** configuración de docking, unidades, score de cada pose, diferencias geométricas y limitaciones del ranking.
- **Límite científico:** **no** convertir líneas de hidrógeno o PLIF en una descomposición causal exacta de un modelo de *scoring* si ese modelo no ofrece dicha atribución.
- **Valor de producto:** conecta de manera directa el core de MolDesign con la idea futura de “explicación visual bajo demanda”.

### Historia 9 — Lo que pasa entre las imágenes: dinámica molecular local

- **Pregunta:** ¿cómo cambian las distancias y los contactos durante fluctuaciones del complejo ya formado?
- **Sistema:** complejo proteína–ligando parametrizado y equilibrado; EGFR–Erlotinib como primer caso técnico si se valida el sistema de simulación.
- **Guion (10–16 s):** (1) pose estructural de referencia; (2) transición señalizada hacia una **trayectoria calculada**; (3) mostrar una distancia o contacto actualizándose con los fotogramas; (4) resumen de lo observado en esa trayectoria.
- **Visual protagonista:** desplazamientos térmicos coherentes, cámara estable, microanotaciones; evitar un movimiento “gelatinoso” artificial.
- **Análisis:** OpenMM, topología/parametrización del ligando, solvente, equilibración, RMSD/RMSF y ocupación de contactos. MM-GBSA puede acompañar análisis de *snapshots* **con limitaciones**; no genera fuerzas ni una trayectoria de asociación.
- **Límite científico:** indicar tiempo físico simulado y escala de reproducción cinematográfica por separado. Una simulación corta no demuestra estabilidad a largo plazo, afinidad experimental ni entrada espontánea al bolsillo.

---

## 3. Protocolo Campaña — ideas automatizables por lote

El lote debe elegir una **plantilla según la evidencia disponible**, no obligar a que cada receptor tenga ligando, mecanismo de resistencia, trayectoria o interacción detectable. Los nombres de las plantillas son etiquetas de producción; sus afirmaciones científicas se generan solo desde el manifiesto validado.

### Lote A — Identidad estructural: “Conoce al receptor”

- **Aplica a:** cualquier estructura interpretable del catálogo, incluso sin ligando.
- **3 beats:** vista global con nombre/PDB → orientación hacia región de interés → plano limpio final con identificación del dominio/cadena visualizado.
- **Automatización:** delimitar entidad biológica de interés, encuadre adaptativo y controles de oclusión.
- **Salidas:** miniatura, micropreview de 3–5 s, video de ficha y `case.json`.
- **Contingencia:** si no se puede localizar de forma confiable el sitio, permanecer en vista estructural; **no inventar un bolsillo**.

### Lote B — Anclaje del ligando de referencia

- **Aplica a:** complejos con ligando de interés identificado **inequívocamente** en la cadena y el sitio correctos.
- **3 beats:** receptor global → cámara al ligando → contactos geométricos anotables y superficie opcional.
- **Automatización:** resolver instancia de ligando, alinear coordenadas, aplicar PLIF validado, seleccionar hasta tres contactos legibles.
- **Contingencia:** mostrar pose y bolsillo sin “líneas de puente H” si no hay contactos que cumplan criterios; un ligando cocristalizado no es necesariamente un fármaco.

### Lote C — Cavidad sin ligando de interés

- **Aplica a:** entradas donde no está el ligando de referencia; distinguir **apo confirmado** de “ligando no identificado/no incluido en los metadatos”.
- **3 beats:** estructura global → aproximación al centro del sitio curado o cavidad calculada → superficie y residuos con propiedades **calculadas**.
- **Automatización:** seleccionar método y parámetros de detección de cavidad, registrar volumen si es calculable.
- **Contingencia:** no publicar “druggability 0.88”, propiedades electrostáticas o potencial terapéutico si el pipeline no calculó una métrica definida y validada.

### Lote D — Centro metálico y cofactores

- **Aplica a:** centros metálicos con identidad y vecindad atómica verificadas; subplantillas distintas para metal aislado, hemo y otros cofactores.
- **3 beats:** estructura global → enfoque al centro → coordinantes y distancias compatibles con su química.
- **Automatización:** selección por entorno local, asignación cuidadosa de elemento e inspección de posibles átomos coordinantes.
- **Contingencia:** si faltan identificadores químicos o resolución estructural suficiente, omitir las líneas de coordinación y añadir advertencia.

### Lote E — Huella visual de familia estructural

- **Aplica a:** familias del catálogo después de confirmar clasificación y correspondencias de residuos.
- **Plantillas:** quinasas (bisagra/gatekeeper cuando estén identificados), GPCR (hélices transmembrana y sitio de ligando cuando se conozca), proteasas (residuos catalíticos si están curados), receptores nucleares (bolsillo y región funcional cuando aplique).
- **3 beats:** arquitectura familiar → rasgo estructural característico → detalle local con rótulo explicativo.
- **Contingencia:** no imponer la misma tríada, conformación o localización de entrada a todos los miembros de una familia.

### Lote F — Comparación de poses de un cálculo MolDesign

- **Aplica a:** trabajos que guardan varias poses comparables y sus scores, no necesariamente a cada entrada del catálogo.
- **3 beats:** receptor y bolsillo → dos poses superpuestas/alternadas → pose elegida con score y procedencia del cálculo.
- **Automatización:** consumir directamente resultados de docking y datos de configuración; generar una visualización de comparación, **no** una animación de movimiento físico entre poses.
- **Contingencia:** no afirmar que la pose con score más favorable sea la biológicamente correcta.

### Lote G — “Trayectoria disponible”: fluctuación molecular

- **Aplica a:** casos que ya tengan una trayectoria validada y topología consistente; no es requisito para las 380 estructuras.
- **3 beats:** pose de referencia → movimiento local real de la trayectoria → resumen de una métrica observable (por ejemplo, distancia en Å a lo largo del tiempo).
- **Automatización:** mapear IDs de átomos, alinear la trayectoria y actualizar anotaciones por frame.
- **Contingencia:** si no hay trayectoria validada, usar animación de **cámara** sobre estructura fija, identificándola como tal; nunca sustituir MD por vibración aleatoria presentada como simulación.

### Formatos derivados de una sola escena

- **Tarjeta del catálogo:** miniatura estática y video silenciado de 3–5 s, encuadre legible desde el primer fotograma y carga diferida al pasar el cursor.
- **Ficha del receptor:** versión de 9–20 s con contexto global y aproximación al sitio.
- **Promoción/portafolio:** reencuadre específico a 16:9, 9:16 y 1:1; el mismo video recortado automáticamente puede perder etiquetas y requerir una cámara/layout alternativo.
- **Producto independiente:** GLB o escena editable + medios + metadatos + licencias, únicamente cuando la compatibilidad fuera de Blender esté probada.

---

## 4. Qué producir primero: cartera piloto

| Entrega | Historia | Qué demuestra | Primer criterio de salida |
|---|---|---|---|
| P0 | **EGFR: unión + resistencia + Osimertinib** | Comparación de estados, anotaciones y narrativa farmacológica. | Guion revisado, estructuras bien identificadas, transiciones didácticas rotuladas y video final. |
| P1 | **KRAS G12C: inhibición covalente** | Que el motor puede representar un mecanismo químico distinto. | Conectividad covalente y referencia estructural del aducto verificadas. |
| P2 | **Molecular glue / degradación dirigida** | Que puede contar una historia proteína–proteína y una consecuencia celular. | Complejo y mecanismo seleccionados a partir de literatura; separar estructura del esquema de degradación. |
| P3 | **Proteasa del VIH-1: dos conformaciones** | Que puede comparar cambios de forma sin inventar una trayectoria. | Correspondencia de residuos y dos estados estructurales comprobados. |
| P4 | **Anhidrasa carbónica: centro de Zn²⁺** | Que puede generalizar a metales/cofactores. | Coordinantes identificados y video con distancias coherentes. |

**Lote piloto paralelo:** conservar `1BN1`, `2NNJ` y `1HSG` como pruebas de estilo ya generadas; agregar casos estructuralmente diferentes, incluyendo uno sin ligando inequívocamente identificado y otro multimerico. No dar por verificada una interacción solo porque se dibujó bien en el MP4.

---

## 5. Pipeline compartido: qué automatizar y qué reservar para curación

```text
Catálogo + estructura original + fuente científica
                 |
                 v
Auditoría: entidad/cadena/ligando/estado/numeración
                 |
                 v
Manifiesto científico (átomos, coords, PLIF, procedencia)
                 |
          +------+------+
          |             |
          v             v
   Campaña: plantilla   Protagonista: guion específico,
   visual + cámara      varios estados + revisión humana
          |             |
          +------+------+
                 v
 Blender headless: geometría, cámara, anotaciones, render
                 |
                 v
 QC técnico + QC geométrico + revisión científica adecuada
                 |
                 v
MP4 / PNG / BLEND o GLB / case.json / informe de límites
```

**No mezclar roles:**

- **MolDesign / análisis externo:** resultados computacionales, poses, estructuras, interacciones y su procedencia.
- **OpenMM:** evolución temporal de un sistema **preparado y parametrizado**; no garantiza asociación espontánea del ligando desde solvente en clips breves.
- **MM-GBSA:** estimaciones energéticas aproximadas sobre configuraciones preparadas; no dirige movimiento ni demuestra causalidad de un score por contacto individual.
- **Blender:** cámara, lenguaje visual, materiales, animación didáctica y representación de trayectorias.
- **Narrativa:** interpreta el alcance de cada evidencia y marca explícitamente qué escenas son experimentales, predichas, simuladas o conceptuales.

### Reglas editoriales universales

1. **No inventar interacciones ni números:** calcular distancias desde átomos identificados; no inferir un puente H solo por cercanía o por una línea atractiva.
2. **No confundir visualización con inferencia causal:** PLIF y distancias pueden describir una pose, pero no necesariamente explican la contribución de cada contacto al score de ML/docking.
3. **No animar transformaciones como si fueran videos experimentales:** un morph entre mutantes, apo/holo o compuestos químicos es una comparación didáctica salvo que exista trayectoria correspondiente.
4. **Etiquetas mínimas y trazables:** priorizar uno a tres elementos principales; conservar identificador PDB, cadena, residuo, átomo, método y unidades en metadatos.
5. **Control de calidad autónomo:** identidad de receptor/ligando, geometría, cámara, oclusiones, duración real, medios decodificables y registro de errores; problemas científicos ambiguos pasan a revisión humana.
6. **No prometer automatización perfecta:** lotes desatendidos con reintentos y salida `SUCCESS` / `WARNING` / `FAILED`; estructuras problemáticas se excluyen o reciben plantilla más simple.
7. **Separar explicación de tratamiento clínico:** ningún video de docking ni MM-GBSA demuestra eficacia clínica, resistencia individual o seguridad de un fármaco.

---

## 6. Plantilla de ficha para cada nueva historia

```yaml
id: HERO-XXX                    # o BATCH-XXX
nombre: ""
pregunta_educativa: ""
publico: "estudiantes / investigadores / desarrolladores"
sistema:                         # diana, variantes y ligandos
  receptor: ""
  estructuras: []                 # PDB, cadena, estado, ligando
  referencias: []
evidencia:
  experimental: []
  computacional: []
  conceptual: []
beats:                            # por beat: tiempo, cámara, objetos, rótulos
  - inicio_s: 0.0
    fin_s: 0.0
    objetivo: ""
    datos_que_se_muestran: []
    movimientos: []
    rotulos: []
riesgos_cientificos: []
verificacion_pre_publicacion: []
salidas: ["preview.png", "video.mp4", "case.json"]
```

La lista de estructuras **no se completa de memoria**: se consulta el registro original y se comprueba identidad, cadena, ligando y estado químico antes de producir la animación.

---

## 7. Radar editorial: temas actuales para futuras historias

Estos trabajos justifican **explorar temas**, no garantizan demanda comercial ni prueban por sí mismos las escenas que se propongan.

- **Molecular glues / degradación dirigida.** Un estudio de *Nature* del 5 de agosto de 2026 describe un degradador dependiente de DCAF11 activado por glutationilación que recluta DDX18; ofrece una base específica para estudiar una escena de complejo inducido: https://www.nature.com/articles/s41586-026-10873-1
- **Reclutamiento alternativo de ligasas E3.** *Nature Chemical Biology* (12 de mayo de 2026) describe un degradador monovalente capaz de reclutar dos sistemas E3 para degradar SMARCA2/4: https://www.nature.com/articles/s41589-026-02224-y
- **Dinámica conformacional y descubrimiento de fármacos.** La revisión sobre q-CAR del 14 de agosto de 2026 discute la relevancia de estudiar estados conformacionales y movimiento, más allá de una sola estructura estática: https://www.nature.com/articles/s44386-026-00057-2
- **Resistencia a terapias dirigidas en EGFR.** Revisión de noviembre de 2025 sobre mecanismos de resistencia a inhibidores de EGFR: https://pubmed.ncbi.nlm.nih.gov/41219394/

**Siguiente decisión editorial:** elegir la pregunta educativa, comprobar que hay evidencia estructural suficiente y generar un pequeño *animatic* antes de dedicar tiempo a un render final.
