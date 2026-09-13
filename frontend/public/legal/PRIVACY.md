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

## 4. Modelos descargables

ESMFold y los modelos de lenguaje pesados no se incluyen necesariamente en la instalación. Si el usuario solicita su descarga, la aplicación contacta al repositorio indicado. Tras descargarse, la inferencia configurada como local no transmite por sí misma las muestras al autor de MolDesign.

## 5. Conservación y eliminación

Los datos locales permanecen hasta que el usuario los elimina, borra el espacio de trabajo o desinstala la aplicación. La desinstalación puede no borrar carpetas de trabajo o respaldos elegidos por el usuario. Las copias exportadas deben eliminarse por separado. MolDesign no puede borrar datos ya enviados a un tercero o publicados en Solana devnet.

## 6. Investigación sensible

MolDesign no está diseñado para almacenar datos clínicos identificables y no debe usarse como sistema de expediente médico. No envíe información personal, secretos comerciales o materiales sujetos a acuerdos de confidencialidad a integraciones externas sin la autorización y las salvaguardas correspondientes.

## 7. Cambios y contacto

Esta política se actualizará cuando cambien las funciones de red o el tratamiento de datos. La versión vigente se publicará con el código y en la página oficial del producto. Preguntas o solicitudes: **srcacahuate619@gmail.com**.

---

## English summary

MolDesign is local-first. Research cases and results remain on the user's device unless the user explicitly invokes an external integration. MolDesign includes no first-party analytics, advertising, cross-app tracking, or remote crash reporting. Optional requests may send the minimum necessary query data to Hugging Face, RCSB PDB, PubChem, ChEMBL, UniProt, a user-configured AI provider, or Solana devnet, each under its own terms. Solana devnet data is public and effectively immutable. Contact: **srcacahuate619@gmail.com**.
