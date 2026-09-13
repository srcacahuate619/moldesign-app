# Política de privacidad de MolDesign

**Vigente desde:** 10 de septiembre de 2026
**Responsable:** Johan Amezcua / amezcua-dev.com
**Contacto:** srcacahuate619@gmail.com

MolDesign es una aplicación de escritorio local-first para investigación computacional estructural. Esta política describe qué datos trata la aplicación y qué ocurre cuando el usuario activa voluntariamente servicios externos.

## 1. Datos tratados localmente

MolDesign puede guardar en el dispositivo cuentas locales, preferencias, rutas de trabajo, receptores, secuencias, moléculas, configuraciones, corridas, poses, resultados, informes, registros técnicos y respaldos. Estos datos sirven para ejecutar y reproducir el trabajo solicitado por el usuario.

MolDesign no incorpora analítica de uso propia, publicidad, seguimiento entre aplicaciones ni crash reporting remoto. El desarrollador no recibe automáticamente los casos o resultados guardados localmente.

## 2. Credenciales

Las claves de proveedores configuradas por el usuario se cifran en reposo mediante una clave local de la instalación. El cifrado reduce la exposición accidental, pero no protege frente a una persona o programa que ya controle la cuenta de Windows o el dispositivo. El usuario es responsable de limitar el acceso al equipo y revocar las credenciales comprometidas.

## 3. Comunicaciones externas opcionales

El funcionamiento básico y AutoDock Vina son locales. Sólo cuando el usuario activa una función externa, MolDesign puede comunicar los datos necesarios al proveedor correspondiente:

- **Hugging Face:** identificadores de modelos y descarga de archivos seleccionados.
- **RCSB PDB, PubChem, ChEMBL y UniProt:** identificadores, nombres, secuencias, PDB IDs, SMILES o consultas científicas necesarias.
- **OpenAI, Anthropic u otro proveedor de IA configurado:** el texto y contexto que el usuario decida enviar, junto con la credencial del proveedor.
- **Solana devnet (prueba de concepto):** dirección pública de la cartera y un memo técnico. Una blockchain pública es observable e inmutable; no se debe incluir información personal, confidencial ni un resultado con significado de certificación científica.

Esos terceros procesan los datos bajo sus propias condiciones y políticas. MolDesign no controla su conservación posterior. Antes de usar una integración, el usuario debe comprobar que puede comunicar legalmente esos datos, especialmente si pertenecen a pacientes, clientes, colaboradores o investigaciones confidenciales.

## 4. Texto generado por IA (MolChat)

MolDesign incluye **MolChat**, un asistente que responde con texto generado por un modelo de lenguaje. Lo que escribe MolChat **no es un resultado calculado**: los números del expediente —afinidad, poses, propiedades, controles— salen de AutoDock Vina y de los modelos de reescalado, no del asistente. Una respuesta de MolChat puede ser incorrecta, estar incompleta o describir mal un resultado propio, y no debe citarse como evidencia.

- **Dónde corre.** Por omisión, el modelo es local (Qwen2.5 1.5B) y la conversación no sale del equipo. Un proveedor en la nube sólo interviene si el usuario lo configura **y** autoriza su destino; hasta entonces el turno no se envía y la aplicación lo dice en pantalla.
- **Qué sale cuando se autoriza.** El texto de la conversación, el contexto de caso y molécula asociado y la credencial del proveedor. El destino concreto (`proveedor@host`) se muestra antes de autorizarlo y la autorización no se hereda al cambiarlo.
- **Cómo reportar una respuesta.** Cada respuesta de MolChat lleva un botón **«Reportar respuesta»** que abre el programa de correo del usuario con la respuesta y el proveedor ya escritos, dirigido al contacto de soporte de la aplicación. No se envía nada hasta que la persona lo manda: MolDesign no transmite conversaciones por su cuenta, tampoco para procesar un reporte.
- **Sin entrenamiento con tus datos.** MolDesign no usa las conversaciones ni los casos para entrenar ni ajustar ningún modelo. Lo que haga con ellos un proveedor en la nube que el usuario haya autorizado se rige por las condiciones de ese proveedor.

## 5. Modelos descargables

ESMFold y los modelos de lenguaje pesados no se incluyen necesariamente en la instalación. Si el usuario solicita su descarga, la aplicación contacta al repositorio indicado. Tras descargarse, la inferencia configurada como local no transmite por sí misma las muestras al autor de MolDesign.

## 6. Conservación y eliminación

Los datos locales permanecen hasta que el usuario los elimina, borra el espacio de trabajo o desinstala la aplicación. La desinstalación puede no borrar carpetas de trabajo o respaldos elegidos por el usuario. Las copias exportadas deben eliminarse por separado. MolDesign no puede borrar datos ya enviados a un tercero o publicados en Solana devnet.

## 7. Investigación sensible

MolDesign no está diseñado para almacenar datos clínicos identificables y no debe usarse como sistema de expediente médico. No envíe información personal, secretos comerciales o materiales sujetos a acuerdos de confidencialidad a integraciones externas sin la autorización y las salvaguardas correspondientes.

## 8. Cambios y contacto

Esta política se actualizará cuando cambien las funciones de red o el tratamiento de datos. La versión vigente se publicará con el código y en la página oficial del producto. Preguntas o solicitudes: **srcacahuate619@gmail.com**.

---

## English summary

MolDesign is local-first. Research cases and results remain on the user's device unless the user explicitly invokes an external integration. MolDesign includes no first-party analytics, advertising, cross-app tracking, or remote crash reporting. Optional requests may send the minimum necessary query data to Hugging Face, RCSB PDB, PubChem, ChEMBL, UniProt, a user-configured AI provider, or Solana devnet, each under its own terms. Solana devnet data is public and effectively immutable.

**Generative AI.** MolDesign ships MolChat, an assistant whose answers are written by a language model. Those answers are not computed results — the numbers in a case file come from AutoDock Vina and the rescoring models — and they can be wrong. The model runs locally by default; a cloud provider is used only if the user configures one **and** authorizes its destination, and the app refuses the turn and says so until then. Every answer carries a **Report answer** button that opens the user's own mail client with the answer and the provider filled in; nothing is transmitted until the person sends it. MolDesign does not use conversations or cases to train or fine-tune any model.

Contact: **srcacahuate619@gmail.com**.
