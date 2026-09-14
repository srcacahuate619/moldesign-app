// =====================================================================
// Legal — términos, privacidad y licencias
// =====================================================================
//
// POR QUÉ ESTE MÓDULO SE TRADUCE DISTINTO QUE LOS DEMÁS. Aquí no se busca que
// suene natural: se busca que diga EXACTAMENTE lo mismo. Un texto legal
// traducido «con soltura» cambia lo que el producto se compromete a hacer, y
// esta pantalla es de las que un revisor de la Store abre seguro.
//
// TRES COSAS QUE NO SE SUAVIZAN AL CRUZAR DE IDIOMA:
//
//   1. Lo que el producto NO es. «No es un dispositivo médico ni reemplaza el
//      juicio clínico» no puede volverse «is not intended as a medical device»:
//      la intención no es el punto, la calificación sí.
//
//   2. La ausencia de garantía. «Tal cual», sin garantías expresas o
//      implícitas, es fórmula reconocible —«as is», without warranties of any
//      kind— y se escribe con esa fórmula, no con una paráfrasis.
//
//   3. Lo que un certificado NO concede. «No concede automáticamente una
//      patente ni otro derecho registral» tiene que seguir negando lo mismo.
//
// Y lo que dice de privacidad no puede volverse absoluto en ninguno de los dos
// idiomas: hay descargas de Hugging Face, consultas al RCSB y proveedores de IA
// opcionales. `idiomasCompletos.test.ts` lo comprueba con una regla explícita.

import type { ModuloDeTraduccion } from "./index";

export const legal: ModuloDeTraduccion = {
  es: {
    // ── Contenedor ────────────────────────────────────────────────
    lg_titulo: "Información legal",
    lg_cerrar: "Cerrar información legal",
    lg_repositorio: "Repositorio de esta versión",
    lg_pestana_terminos: "Términos",
    lg_pestana_privacidad: "Privacidad",
    lg_pestana_licencias: "Licencias",
    lg_version_vigente: "Versión {version} · Vigente desde {fecha}",
    lg_fecha_vigencia: "10 de septiembre de 2026",

    // ── Documentos empaquetados ───────────────────────────────────
    lg_boton_inventario: "Inventario completo",
    lg_boton_comercial: "Uso comercial",
    lg_doc_inventario: "Inventario completo de terceros",
    lg_doc_fuente: "Fuente y recompilación",
    lg_doc_comercial: "Licencia de uso comercial",

    // ── Términos ──────────────────────────────────────────────────
    lg_terminos_titulo: "Condiciones de uso científico",
    lg_terminos_intro:
      "MolDesign AI es una herramienta de investigación computacional. Sus "
      + "resultados son hipótesis in silico y requieren validación experimental.",
    lg_terminos_1_titulo: "1. Alcance y uso responsable",
    lg_terminos_1:
      "No es un dispositivo médico ni reemplaza el juicio clínico, farmacéutico, "
      + "toxicológico o regulatorio. El usuario debe cumplir la legislación "
      + "aplicable y no utilizar la plataforma para actividades ilícitas.",
    lg_terminos_2_titulo: "2. Resultados y reproducibilidad",
    lg_terminos_2:
      "Scores, poses, propiedades y explicaciones dependen de los datos, "
      + "versiones, parámetros y modelos registrados en cada corrida. Ninguna "
      + "predicción constituye por sí sola evidencia experimental.",
    lg_terminos_3_titulo: "3. Datos y trabajos del usuario",
    lg_terminos_3:
      "MolDesign no reclama propiedad sobre las moléculas, casos o resultados "
      + "aportados por el usuario. Un certificado criptográfico acredita "
      + "integridad y fecha, pero no concede automáticamente una patente ni otro "
      + "derecho registral.",
    lg_terminos_4_titulo: "4. Código, modelos y componentes de terceros",
    lg_terminos_4_a:
      "El código y los modelos propios identificados de MolDesign se ofrecen bajo",
    lg_terminos_4_b:
      "para fines no comerciales. Cualquier uso comercial requiere un acuerdo "
      + "escrito separado. Los conjuntos de datos, modelos y componentes de "
      + "terceros conservan sus propias licencias.",
    lg_terminos_5_titulo: "5. Servicios opcionales",
    lg_terminos_5:
      "Algunas funciones sólo operan si el usuario configura o descarga recursos "
      + "externos, entre ellos Hugging Face, DiffDock, ColabFold, RFdiffusion, "
      + "Solana o proveedores de IA. Su disponibilidad y condiciones dependen de "
      + "cada proveedor.",
    lg_terminos_6_titulo: "6. Sin garantía",
    lg_terminos_6:
      "El software se proporciona «tal cual», sin garantías expresas o "
      + "implícitas, dentro de los límites permitidos por la legislación "
      + "aplicable y por las licencias incluidas.",

    // ── Privacidad ────────────────────────────────────────────────
    lg_privacidad_titulo: "Privacidad local-first",
    lg_privacidad_intro:
      "Los casos y resultados permanecen en el espacio de trabajo local, salvo "
      + "cuando el usuario activa una integración externa identificada.",
    lg_privacidad_sello_casos: "Casos locales",
    lg_privacidad_sello_analitica: "Sin analítica propia",
    lg_privacidad_sello_red: "Red bajo demanda",
    lg_privacidad_1_titulo: "1. Datos almacenados",
    lg_privacidad_1:
      "Cuentas locales, configuraciones, receptores, moléculas, corridas, "
      + "resultados y respaldos se guardan en el dispositivo y se separan por "
      + "usuario y sesión.",
    lg_privacidad_2_titulo: "2. Conexiones externas explícitas",
    lg_privacidad_2:
      "Descargar modelos desde Hugging Face, consultar fuentes científicas, "
      + "certificar en Solana o usar un proveedor de IA transmite a ese tercero "
      + "la información necesaria para la operación. La interfaz debe identificar "
      + "esa salida antes de ejecutarla.",
    lg_privacidad_3_titulo: "3. Telemetría",
    lg_privacidad_3:
      "MolDesign no incorpora analítica de producto ni crash reporting remoto. "
      + "Los componentes locales se configuran para desactivar telemetría propia "
      + "cuando ofrecen esa opción. Los servicios externos mantienen políticas "
      + "independientes.",
    lg_privacidad_4_titulo: "4. Credenciales y respaldos",
    lg_privacidad_4:
      "Las credenciales configuradas y los archivos exportados quedan bajo "
      + "control del usuario. No deben compartirse respaldos que contengan "
      + "información confidencial sin la protección correspondiente.",

    // ── Licencias ─────────────────────────────────────────────────
    lg_licencias_titulo: "Licencias y código fuente",
    lg_licencias_intro:
      "Esta pantalla resume los componentes que requieren atención especial. El "
      + "inventario completo del runtime y los textos íntegros se distribuyen con "
      + "la aplicación.",
    lg_aviso_incluido: "Aviso incluido",
    lg_componentes_destacados: "Componentes destacados",
    lg_atencion_copyleft: "Copyleft",
    lg_atencion_atribucion: "Atribución requerida",
    lg_atencion_bloqueo: "Bloqueo de distribución",
    lg_programa_independiente:
      "Programa independiente: se ejecuta como proceso aparte y sólo intercambia "
      + "archivos. MolDesign no lo enlaza ni importa su código.",
    lg_enlazado:
      "Se enlaza o se importa desde el código de MolDesign.",
    lg_nota_licencia_propia:
      "Uso, estudio, modificación y redistribución no comerciales permitidos. El "
      + "uso comercial requiere una licencia escrita separada. Es "
      + "source-available, no open source según OSI.",
    lg_nota_tabpfn:
      "Atribución exigida por la Prior Labs License 1.2 para productos que "
      + "incorporan TabPFN.",
    lg_nota_upstream:
      "La copia integrada incluye el texto upstream y su atribución: "
      + "Copyright (c) 2023 sc8668. La licencia permite uso y redistribución "
      + "comercial conservando ese aviso.",
    lg_pie_local_first: "Local-first · conexiones externas identificadas",
    lg_no_es_asesoria:
      "Los modelos descargables muestran su licencia y procedencia por separado "
      + "antes de instalarse. Este resumen técnico no sustituye asesoría jurídica "
      + "profesional.",
  },
  en: {
    lg_titulo: "Legal information",
    lg_cerrar: "Close legal information",
    lg_repositorio: "Repository for this version",
    lg_pestana_terminos: "Terms",
    lg_pestana_privacidad: "Privacy",
    lg_pestana_licencias: "Licences",
    lg_version_vigente: "Version {version} · In force since {fecha}",
    lg_fecha_vigencia: "10 September 2026",

    lg_boton_inventario: "Full inventory",
    lg_boton_comercial: "Commercial use",
    lg_doc_inventario: "Full third-party inventory",
    lg_doc_fuente: "Source and rebuild",
    lg_doc_comercial: "Commercial use licence",

    lg_terminos_titulo: "Conditions of scientific use",
    lg_terminos_intro:
      "MolDesign AI is a computational research tool. Its results are in silico "
      + "hypotheses and require experimental validation.",
    lg_terminos_1_titulo: "1. Scope and responsible use",
    lg_terminos_1:
      "It is not a medical device and does not replace clinical, pharmaceutical, "
      + "toxicological or regulatory judgement. The user must comply with "
      + "applicable law and must not use the platform for unlawful activities.",
    lg_terminos_2_titulo: "2. Results and reproducibility",
    lg_terminos_2:
      "Scores, poses, properties and explanations depend on the data, versions, "
      + "parameters and models recorded in each run. No prediction on its own "
      + "constitutes experimental evidence.",
    lg_terminos_3_titulo: "3. User data and work",
    lg_terminos_3:
      "MolDesign claims no ownership over the molecules, cases or results "
      + "contributed by the user. A cryptographic certificate attests integrity "
      + "and date, but does not automatically grant a patent or any other "
      + "registered right.",
    lg_terminos_4_titulo: "4. Third-party code, models and components",
    lg_terminos_4_a:
      "The identified MolDesign code and in-house models are offered under",
    lg_terminos_4_b:
      "for non-commercial purposes. Any commercial use requires a separate "
      + "written agreement. Third-party datasets, models and components keep "
      + "their own licences.",
    lg_terminos_5_titulo: "5. Optional services",
    lg_terminos_5:
      "Some features only work if the user configures or downloads external "
      + "resources, among them Hugging Face, DiffDock, ColabFold, RFdiffusion, "
      + "Solana or AI providers. Their availability and terms depend on each "
      + "provider.",
    lg_terminos_6_titulo: "6. No warranty",
    lg_terminos_6:
      "The software is provided “as is”, without warranties express or "
      + "implied, to the extent permitted by applicable law and by the licences "
      + "included.",

    lg_privacidad_titulo: "Local-first privacy",
    lg_privacidad_intro:
      "Cases and results stay in the local workspace, except when the user "
      + "enables an identified external integration.",
    lg_privacidad_sello_casos: "Local cases",
    lg_privacidad_sello_analitica: "No analytics of our own",
    lg_privacidad_sello_red: "Network on demand",
    lg_privacidad_1_titulo: "1. Stored data",
    lg_privacidad_1:
      "Local accounts, settings, receptors, molecules, runs, results and backups "
      + "are saved on the device and kept separate per user and session.",
    lg_privacidad_2_titulo: "2. Explicit external connections",
    lg_privacidad_2:
      "Downloading models from Hugging Face, querying scientific sources, "
      + "certifying on Solana or using an AI provider transmits to that third "
      + "party the information needed for the operation. The interface must "
      + "identify that outbound traffic before running it.",
    lg_privacidad_3_titulo: "3. Telemetry",
    lg_privacidad_3:
      "MolDesign includes no product analytics and no remote crash reporting. "
      + "Local components are configured to disable their own telemetry where "
      + "they offer that option. External services keep independent policies.",
    lg_privacidad_4_titulo: "4. Credentials and backups",
    lg_privacidad_4:
      "Configured credentials and exported files remain under the user's "
      + "control. Backups containing confidential information should not be "
      + "shared without appropriate protection.",

    lg_licencias_titulo: "Licences and source code",
    lg_licencias_intro:
      "This screen summarises the components that need special attention. The "
      + "full runtime inventory and the complete texts are distributed with the "
      + "application.",
    lg_componentes_destacados: "Highlighted components",
    lg_aviso_incluido: "Notice included",
    lg_atencion_copyleft: "Copyleft",
    lg_atencion_atribucion: "Attribution required",
    lg_atencion_bloqueo: "Distribution blocked",
    lg_programa_independiente:
      "Independent program: it runs as a separate process and only exchanges "
      + "files. MolDesign neither links it nor imports its code.",
    lg_enlazado: "It is linked or imported from MolDesign's own code.",
    lg_nota_licencia_propia:
      "Non-commercial use, study, modification and redistribution are permitted. "
      + "Commercial use requires a separate written licence. It is "
      + "source-available, not open source under the OSI definition.",
    lg_nota_tabpfn:
      "Attribution required by the Prior Labs License 1.2 for products that "
      + "incorporate TabPFN.",
    lg_nota_upstream:
      "The bundled copy includes the upstream text and its attribution: "
      + "Copyright (c) 2023 sc8668. The licence permits commercial use and "
      + "redistribution provided that notice is kept.",
    lg_pie_local_first: "Local-first · external connections identified",
    lg_no_es_asesoria:
      "Downloadable models show their licence and provenance separately before "
      + "being installed. This technical summary does not replace professional "
      + "legal advice.",
  },
};
