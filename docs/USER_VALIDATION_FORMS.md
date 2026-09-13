# Encuesta de Validación de Usuarios v2.0 — MolDesign AI
> **Versión Ultra-Optimizada**: 10 preguntas | Tiempo estimado de llenado: 3 - 5 minutos.  
> **Objetivo**: Validar frecuencia de uso, presupuesto real (comportamiento pasado), prioridades de selección, trabajo con metaloenzimas, barreras de adopción y predisposición a la certificación de descubrimientos sin fricción técnica.

---

## Estructura Lista para Copiar en Google Forms / Microsoft Forms

---

### SECCIÓN 1: Perfil y Frecuencia de Uso

#### 1.1 ¿Cuál es tu rol y con qué frecuencia realizas docking molecular?
- [ ] Realizo docking semanalmente (Investigador principal / Bioinformático activo)
- [ ] Realizo docking mensualmente (Estudiante de posgrado / Investigador junior)
- [ ] No realizo docking directamente, pero dirijo/diseño proyectos que lo requieren (PI / Director de laboratorio)
- [ ] No realizo docking actualmente, pero necesito implementarlo en mi investigación
- [ ] Otro: ______

#### 1.2 ¿A qué institución/empresa perteneces y en qué país? *(Opcional)*
`[Texto corto: Ej. Tec de Monterrey, México]`

---

### SECCIÓN 2: Flujo Actual, Presupuesto y "Job-to-be-Done"

#### 2.1 ¿Qué herramienta usas PRINCIPALMENTE para docking hoy?
- [ ] AutoDock Vina (línea de comandos / scripts propios)
- [ ] Schrödinger Suite / MOE / GOLD (licencia institucional privativa)
- [ ] Plataformas Cloud / Web (DiffDock, GNINA web, etc.)
- [ ] PyMOL / Chimera (solo para visualización, sin docking activo)
- [ ] No uso ninguna actualmente
- [ ] Otro: ______

#### 2.2 En el último año, ¿cuánto dinero (aproximadamente) ha gastado tu laboratorio/empresa en software de modelado molecular?
- [ ] $0 USD (usamos únicamente herramientas gratuitas / open source)
- [ ] $1 – $5,000 USD
- [ ] $5,001 – $20,000 USD
- [ ] $20,001 – $50,000 USD
- [ ] Más de $50,000 USD
- [ ] No manejo el presupuesto / No lo sé

#### 2.3 ¿Cuál es el resultado final que necesitas entregar al concluir una campaña de docking? *(Elige la principal)*
- [ ] Una lista priorizada de 5–10 candidatos para pedir/sintetizar e ir a ensayo in vitro
- [ ] Figuras, métricas y poses de docking para publicar un paper
- [ ] Datos de binding para justificar una solicitud de patente o IP
- [ ] Validación teórica para una tesis académica
- [ ] Otro: ______

---

### SECCIÓN 3: Prioridades, Metaloenzimas y Barreras de Adopción

#### 3.1 Si tuvieras que elegir HOY una herramienta para tu próximo proyecto de screening, ¿qué priorizarías? *(Ordena del 1 al 3 tus prioridades principales)*
`[Respuesta de tipo Ordenamiento / Ranking o Opción Múltiple con 3 opciones]`
- Precisión del scoring (que prediga fielmente la afinidad real)
- Velocidad de cómputo (que corra rápido en mi laptop/servidor sin GPU)
- Costo cero en licencias de software
- Privacidad total de los datos (ejecución local sin subir moléculas a servidores externos)
- Facilidad de uso (interfaz visual sin requerir líneas de comando)

#### 3.2 ¿Trabajas con enzimas que contienen iones metálicos (Zinc, Hierro, Manganeso) en su sitio activo?
- [ ] Sí, frecuentemente (ej. Anhidrasa Carbónica, MMPs, HDACs, Proteasas)
- [ ] Ocasionalmente
- [ ] No, mis blancos son proteínas sin cofactores metálicos
- [ ] No estoy seguro

#### 3.3 ¿Qué te IMPEDIRÍA cambiar tu herramienta actual de docking por una solución mejor o más rápida?
- [ ] Mi flujo actual ya está automatizado (scripts y pipelines propios)
- [ ] Mi institución/PI ya pagó la licencia anual de un software comercial
- [ ] No confío en herramientas nuevas si no tienen un paper peer-reviewed respaldándolas
- [ ] No tengo tiempo para aprender a usar otra interfaz
- [ ] Nada me lo impediría: me cambiaría si es más precisa, rápida o accesible

---

### SECCIÓN 4: Protección y Certificación de Descubrimientos

#### 4.1 Imagina que descubres una molécula muy prometedora hoy. ¿Cómo demuestras que la encontraste primero?
- [ ] Solicito una patente formal (proceso costoso y lento)
- [ ] Publico un preprint (ChemRxiv / bioRxiv / arXiv)
- [ ] Uso un sello de tiempo / notariado tradicional
- [ ] No hago nada formal, solo anoto la fecha en mi cuaderno de laboratorio
- [ ] No lo había pensado / No sé cómo hacerlo

#### 4.2 Si existiera una herramienta para certificar la prioridad de tu descubrimiento en segundos por < $1 USD (generando un PDF con código QR verificable institucionalmente), ¿la usarías?
- [ ] Sí, inmediatamente en mis proyectos
- [ ] Depende de si mi universidad / institución reconoce la validez del comprobante
- [ ] No, prefiero los métodos tradicionales (patente / cuaderno)
- [ ] No entiendo bien cómo funciona, necesitaría ver una demostración primero

---

### SECCIÓN 5: NPS, Beta Testing y Bucle Viral

#### 5.1 En una escala del 0 al 10, ¿qué tan probable es que recomiendes a un colega probar un pipeline de docking acelerado por Machine Learning que no requiera GPU?
`[Escala lineal 0 (Nada probable) a 10 (Extremadamente probable)]`

#### 5.2 ¿Te gustaría probar la versión Beta temprana de MolDesign AI con tus propios receptores/moléculas?
- [ ] ¡Sí! Déjame tu correo electrónico: ________________________
- [ ] No por el momento

#### 5.3 ¿Conoces a algún colega, estudiante o investigador a quien le pueda servir esta herramienta y puedas recomendarle esta encuesta?
- [ ] Sí (Nombre/Correo o Red Social): ________________________
- [ ] No por ahora

---

## 📊 Matriz de Análisis de Respuestas para Milestone 4

| Pregunta | Métrica a Reportar | Interpretación para la Entrega |
|---|---|---|
| **1.1 & 2.1** | % de usuarios con docking activo semanal/mensual que usan Vina vs. Software Privativo | Define la penetración del target técnico y si el usuario actual ya conoce Vina. |
| **2.2** | % de laboratorios con presupuesto > $0 en software | Valida la viabilidad comercial (TAM/SAM) y modelo freemium/SaaS. |
| **2.3** | *Job-to-be-Done* dominante (In vitro vs. Paper vs. Patente) | Orienta los tutoriales y exports de la app (PDF report vs. export a CSV/SMILES). |
| **3.1** | Ranking #1 de prioridad (Precisión vs. Costo vs. Velocidad vs. Privacidad) | Define el valor central en el One-Pager de venta / pitch. |
| **3.2** | % de investigadores que trabajan con metaloenzimas | Mide el tamaño del mercado interesado en el **Universal Metal Score (UMS)**. |
| **3.3** | Objeción principal de cambio | Permite preparar las objeciones en el pitch (ej. publicar paper para dar confianza). |
| **4.1 & 4.2** | Interés en Certificación Instantánea (< $1 USD con QR) | Valida la hipótesis DeSci / Solana sin la barrera conceptual de la palabra "blockchain". |
| **5.1 & 5.2** | NPS Inicial + Tasa de conversión a Beta Testers (% con email) | Evidencia de tracción real y leads para entrevistas 1-on-1. |
