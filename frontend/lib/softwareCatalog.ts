export const PRODUCT = {
  name: "MolDesign",
  version: "1.0.4",
  edition: "Desktop Edition",
  license: "PolyForm-Noncommercial-1.0.0",
  licenseDisplayName: "PolyForm Noncommercial 1.0.0",
  sourceUrl: "https://github.com/srcacahuate619/moldesign-app",
  noticesUrl: "/legal/THIRD_PARTY_NOTICES.md",
  sourceOfferUrl: "/legal/SOURCE_CODE_AND_RELINKING.md",
  commercialLicenseUrl: "/legal/licenses/COMMERCIAL-LICENSE.md",
} as const;

/** «Método adaptado»: no viaja ningún código suyo; MolDesign reimplementa una idea o un método. */
export type SoftwareAvailability = "Incluido" | "Opcional" | "Servicio externo" | "Método adaptado";
export type SoftwareKind = "Tercero" | "MolDesign" | "Fuente científica";

export interface SoftwareCard {
  name: string;
  version: string;
  kind: SoftwareKind;
  availability: SoftwareAvailability;
  description: string;
  credit: string;
}

export interface SoftwareSection {
  id: "chemistry" | "scoring" | "ai" | "platform" | "sources";
  label: string;
  cards: SoftwareCard[];
}

/**
 * Escaparate funcional: sólo componentes utilizados por la edición Desktop o
 * integraciones opcionales que la interfaz ofrece explícitamente. No es un
 * inventario legal; el inventario completo vive en THIRD_PARTY_NOTICES.md.
 */
export const SOFTWARE_SECTIONS: SoftwareSection[] = [
  {
    id: "chemistry",
    label: "Química y docking",
    cards: [
      {
        name: "AutoDock Vina",
        version: "1.2.7",
        kind: "Tercero",
        availability: "Incluido",
        description: "Motor de docking que genera y puntúa poses ligando–receptor. Incluye vina_trace, una copia de Vina 1.2.7 que registra la búsqueda para la escena «Búsqueda» de Molcy.",
        credit: "AutoDock / Scripps Research",
      },
      {
        name: "Meeko",
        version: "0.7.1",
        kind: "Tercero",
        availability: "Incluido",
        description: "Prepara ligandos y receptores para los formatos utilizados por AutoDock.",
        credit: "Forli Lab, Scripps Research",
      },
      {
        name: "RDKit",
        version: "2025.9.6",
        kind: "Tercero",
        availability: "Incluido",
        description: "Validación química, descriptores, fingerprints y conformaciones moleculares.",
        credit: "RDKit contributors",
      },
      {
        name: "Dimorphite-DL",
        version: "2.0.2",
        kind: "Tercero",
        availability: "Incluido",
        description: "Protona el ligando al pH elegido (7,4 por defecto) antes de prepararlo.",
        credit: "Durrant Lab, University of Pittsburgh",
      },
      {
        name: "gemmi",
        version: "0.7.5",
        kind: "Tercero",
        availability: "Incluido",
        description: "Lee las estructuras mmCIF/PDBx de los receptores que subes.",
        credit: "Global Phasing Ltd. and gemmi contributors",
      },
      {
        name: "Open Babel",
        version: "3.1.1.23",
        kind: "Tercero",
        availability: "Incluido",
        // La descripción anterior decía «rutas de preparación y rescoring», que
        // era más amplia de lo que ocurre: hay un solo punto de uso, el
        // respaldo de conversión del docking, y se ejecuta como programa
        // aparte. La distinción no es cosmética: decide qué obligaciones de
        // licencia arrastra. Ver docs/79_ADR_FRONTERA_OPEN_BABEL.md.
        description:
          "Programa independiente que MolDesign ejecuta como herramienta de línea de órdenes para convertir PDBQT a SDF cuando la exportación del ligando falla. No se enlaza como biblioteca. El ejecutable empaquetado se identifica internamente como 3.1.0 porque la 3.1.1 fue una correccion de empaquetado que no actualizo la cadena; el valor medido vive en el manifiesto del paquete.",
        credit: "Open Babel contributors; empaquetado del wheel por Jinzhe Zeng",
      },
      {
        name: "PoseBusters",
        version: "0.6.5",
        kind: "Tercero",
        availability: "Incluido",
        description: "Comprueba la validez física de las poses: geometría del ligando y contactos con la proteína.",
        credit: "Buttenschoen, Morris & Deane, University of Oxford",
      },
      {
        name: "OpenMM + PDBFixer",
        version: "8.5.2 / 1.12.0",
        kind: "Tercero",
        availability: "Incluido",
        description: "Viajan en el runtime. En 1.0.2 MM-GBSA está desactivado y la interfaz no ofrece ninguna ruta que los use.",
        credit: "OpenMM and PDBFixer contributors",
      },
      {
        name: "ProLIF + MDAnalysis",
        version: "2.1.0 / 2.10.0",
        kind: "Tercero",
        availability: "Incluido",
        description: "Análisis de contactos e interacciones proteína–ligando sobre estructuras 3D.",
        credit: "ProLIF and MDAnalysis contributors",
      },
    ],
  },
  {
    id: "scoring",
    label: "Scoring y modelos",
    cards: [
      {
        name: "xTB (GFN2-xTB)",
        version: "6.7.1",
        kind: "Tercero",
        availability: "Incluido",
        description: "Cálculos semiempíricos ejecutados como proceso independiente para descriptores cuánticos.",
        credit: "Grimme Lab, Universität Bonn",
      },
      {
        name: "XGBoost + SHAP",
        version: "3.2.0 / 0.51.0",
        kind: "Tercero",
        availability: "Incluido",
        description: "Modelos tabulares de rescoring y explicación de contribuciones de sus variables.",
        credit: "DMLC and SHAP contributors",
      },
      {
        name: "ADMET-AI",
        version: "2.0.1",
        kind: "Tercero",
        availability: "Incluido",
        description: "Predicciones computacionales de propiedades ADMET; no sustituyen validación experimental.",
        credit: "Kyle Swanson and contributors",
      },
      {
        name: "TabPFN",
        version: "8.0.8",
        kind: "Tercero",
        availability: "Incluido",
        description: "Viaja en el runtime con su licencia y su atribución; en 1.0.2 ninguna ruta de MolDesign lo usa.",
        credit: "Built with PriorLabs-TabPFN",
      },
      {
        name: "RTMScore",
        version: "snapshot integrado",
        kind: "Fuente científica",
        availability: "Incluido",
        description: "Implementación de investigación para rescoring proteína–ligando. Su distribución permanece bloqueada hasta aclarar la licencia upstream.",
        credit: "Shen et al.; MIT, Copyright (c) 2023 sc8668",
      },
      {
        name: "Modelos MolDesign",
        version: "manifiesto versionado",
        kind: "MolDesign",
        availability: "Incluido",
        description: "Modelos y calibraciones propios con manifiestos, hashes y licencia separados del código.",
        credit: "MolDesign Research",
      },
    ],
  },
  {
    id: "ai",
    label: "IA y lenguaje",
    cards: [
      {
        name: "ESMFold",
        version: "v1 · pesos a petición",
        kind: "Tercero",
        availability: "Opcional",
        description: "Pliega péptidos para que Vina los acople. Sus pesos (8,4 GB) se descargan a petición; el código viaja con Transformers.",
        credit: "Meta AI (Lin et al., Science 2023) · Hugging Face Transformers",
      },
      {
        name: "llama.cpp",
        version: "b10199 · b4ca032ae",
        kind: "Tercero",
        availability: "Incluido",
        description: "Servidor local que ejecuta modelos GGUF fuera del proceso principal de MolDesign.",
        credit: "ggml-org and llama.cpp contributors",
      },
      {
        name: "Qwen2.5-1.5B-Instruct",
        version: "GGUF Q4_K_M",
        kind: "Tercero",
        availability: "Opcional",
        description: "Modelo local compatible con MolChat. Sus pesos tienen licencia propia y conservan su licencia de terceros.",
        credit: "Qwen Team, Alibaba Cloud",
      },
      {
        name: "Anthropic SDK",
        version: "0.86.0",
        kind: "Tercero",
        availability: "Servicio externo",
        description: "Integración opcional configurada por el usuario; las solicitudes se rigen por el proveedor elegido.",
        credit: "Anthropic",
      },
    ],
  },
  {
    id: "platform",
    label: "Plataforma y visualización",
    cards: [
      {
        name: "Tauri",
        version: "2.11.5",
        kind: "Tercero",
        availability: "Incluido",
        description: "Contenedor nativo, ciclo de vida del backend y empaquetado de la edición Desktop.",
        credit: "Tauri Programme within The Commons Conservancy",
      },
      {
        name: "Next.js + React",
        version: "16.3.8 / 19.2.8",
        kind: "Tercero",
        availability: "Incluido",
        description: "Interfaz local y arquitectura de componentes del producto.",
        credit: "Vercel, Meta and contributors",
      },
      {
        name: "FastAPI + Uvicorn",
        version: "0.135.2 / 0.42.0",
        kind: "Tercero",
        availability: "Incluido",
        description: "API local que conecta la interfaz con los pipelines científicos.",
        credit: "FastAPI and Uvicorn contributors",
      },
      {
        name: "3Dmol.js + Mol*",
        version: "2.5.4 / 5.9.0",
        kind: "Tercero",
        availability: "Incluido",
        description: "Visualización molecular 3D de estructuras, receptores, ligandos y complejos.",
        credit: "3Dmol.js, Mol* and RCSB PDB contributors",
      },
      {
        name: "Ketcher",
        version: "3.18.0",
        kind: "Tercero",
        availability: "Incluido",
        description: "Editor químico 2D para dibujar, importar y exportar estructuras moleculares.",
        credit: "EPAM Systems",
      },
      {
        name: "MolTalk",
        version: "1.0.0 · MIT",
        kind: "Tercero",
        availability: "Método adaptado",
        description:
          "La miniatura de Moldex que gira la pose top-1 y la vista 3D del editor nacen de su visor. "
          + "La idea es suya: adaptamos su método para alinear la geometría 3D con el dibujo 2D y "
          + "lo reimplementamos en código propio. No incluimos su código ni sus dependencias.",
        credit: "Dominic Fico · github.com/DomFico/moltalk",
      },
      {
        name: "Solana Web3.js",
        version: "1.98.4",
        kind: "Tercero",
        availability: "Servicio externo",
        description: "Integración opcional para registrar certificados; no constituye por sí misma protección de propiedad intelectual.",
        credit: "Solana Foundation and contributors",
      },
      {
        name: "ReportLab",
        version: "4.2.0",
        kind: "Tercero",
        availability: "Incluido",
        description: "Genera los PDF del dossier y de los certificados.",
        credit: "ReportLab Inc.",
      },
      {
        name: "Motor Molcy",
        version: "a3d0d10",
        kind: "MolDesign",
        availability: "Incluido",
        description: "Dibuja los vídeos y las fotos de Molcy dentro de Blender. Es obra propia de MolDesign, publicada bajo GPL-3.0-or-later, y se ejecuta como programa aparte.",
        credit: "MolDesign · código fuente: github.com/srcacahuate619/moldesign-molcy",
      },
      {
        name: "Blender",
        version: "5.2.2",
        kind: "Tercero",
        availability: "Opcional",
        description: "Ejecuta el motor de Molcy. No viaja en el instalador: MolDesign lo descarga a petición de la Blender Foundation y verifica su SHA-256.",
        credit: "Blender Foundation · GPL-3.0-or-later",
      },
      {
        name: "Molecular Nodes",
        version: "la que instala Blender Extensions",
        kind: "Tercero",
        availability: "Opcional",
        description: "Extensión de Blender que construye las moléculas de las escenas de Molcy. No viaja en el instalador: se instala a petición desde Blender Extensions.",
        credit: "Brady Johnston and contributors · GPL-3.0-or-later",
      },
      {
        name: "Microsoft Visual C++ Runtime",
        version: "14.50.35719",
        kind: "Tercero",
        availability: "Incluido",
        description: "Bibliotecas de ejecución que necesitan los programas nativos incluidos. Se rigen por los términos de redistribución de Microsoft, no por la licencia de MolDesign.",
        credit: "Microsoft Corporation",
      },
    ],
  },
  {
    id: "sources",
    label: "Créditos y fuentes",
    cards: [
      {
        name: "RCSB Protein Data Bank / wwPDB",
        version: "CC0 1.0 · 380 estructuras",
        kind: "Fuente científica",
        availability: "Incluido",
        description:
          "Aporta las estructuras y los metadatos estructurales base del catálogo: "
          + "los 380 archivos .pdb.gz distribuidos proceden directamente de RCSB PDB.",
        // CC0 es una renuncia de derechos: NO exige atribución. Escribir
        // «atribución requerida» aquí inventaría una obligación que la licencia
        // no impone. Lo que RCSB sí recomienda es citar la entrada y a sus
        // autores originales, y eso es norma científica, no condición legal.
        credit:
          "Dominio público (CC0 1.0) · cita científica recomendada: la entrada PDB "
          + "concreta y sus autores originales",
      },
      {
        name: "UniProtKB",
        version: "CC BY 4.0",
        kind: "Fuente científica",
        availability: "Incluido",
        description:
          "Fuente de las descripciones funcionales de los receptores, tomadas del "
          + "comentario FUNCTION y traducidas al español.",
        credit:
          "Atribución requerida · Fuente: UniProtKB; traducción/adaptación al "
          + "español: MolDesign",
      },
      {
        name: "Publicaciones de métodos",
        version: "referencias por motor",
        kind: "Fuente científica",
        availability: "Incluido",
        description: "Vina, Meeko, Dimorphite-DL, PoseBusters, ESMFold, xTB, RTMScore, ADMET-AI y TabPFN conservan sus autores y referencias metodológicas.",
        credit: "Las citas científicas no sustituyen los avisos de licencia",
      },
      {
        name: "Catálogo MolDesign",
        // Eran «387» y el catálogo tiene 380 PDB ID únicos, uno por archivo
        // .pdb.gz distribuido. Contado sobre curated_targets.json.
        version: "380 receptores curados",
        kind: "MolDesign",
        availability: "Incluido",
        description:
          "Curación de MolDesign sobre las estructuras de RCSB: caja de búsqueda, "
          + "hotspots, selección de cadena, familia estructural y estado. Esa capa "
          + "es cálculo propio, no una afirmación de RCSB ni de UniProt.",
        credit:
          "Curación y cálculo: MolDesign · estructuras CC0 de RCSB PDB · "
          + "descripciones CC BY 4.0 de UniProtKB · RCSB y UniProt no certifican "
          + "los resultados de MolDesign",
      },
    ],
  },
];

export interface LicenseHighlight {
  name: string;
  version: string;
  license: string;
  role: string;
  sourceUrl: string;
  attention?: "copyleft" | "attribution" | "blocked";
  /**
   * Cómo se combina con MolDesign. `subproceso` significa que el componente es
   * un programa independiente que se ejecuta aparte y con el que sólo se
   * intercambian archivos; `biblioteca`, que el código de MolDesign lo importa
   * o enlaza. La distinción decide qué obligaciones arrastra hacia el código
   * propio, así que la pantalla de licencias la muestra en vez de dejar que el
   * lector la suponga. `metodo`: no viaja su código; MolDesign reimplementa
   * un método suyo.
   */
  linkage?: "subproceso" | "biblioteca" | "metodo";
}

/** Lista corta para la UI. El inventario completo y los textos viven en /legal. */
export const LICENSE_HIGHLIGHTS: LicenseHighlight[] = [
  {
    name: "Open Babel",
    version: "3.1.1.23",
    // Decía `GPL-2.0-or-later` y era falso: Open Babel declara «GNU General
    // Public License, versión 2», SIN la coletilla «o posterior». Afirmar
    // «or-later» concede un permiso que sus autores no dieron, y además hace
    // desaparecer del informe la incompatibilidad real entre GPL-2.0-only y la
    // y PolyForm Noncommercial no puede relicenciar esos bindings — por eso
    // este componente se ejecuta como programa aparte.
    license: "GPL-2.0-only",
    role: "Conversión estructural de respaldo (PDBQT → SDF). El ejecutable empaquetado reporta internamente 3.1.0 por una corrección de empaquetado; el valor medido consta en el manifiesto del paquete.",
    sourceUrl: "https://github.com/openbabel/openbabel",
    attention: "copyleft",
    linkage: "subproceso",
  },
  // Molcy: el motor es obra propia y viaja; Blender y Molecular Nodes NO viajan (se descargan a petición),
  // pero el usuario los obtiene desde la aplicación para usar Molcy, así que la pantalla los nombra.
  {
    name: "Motor Molcy",
    version: "a3d0d10",
    license: "GPL-3.0-or-later",
    role: "Vídeos y fotos de Molcy; obra propia de MolDesign que se ejecuta dentro de Blender",
    sourceUrl: "https://github.com/srcacahuate619/moldesign-molcy",
    attention: "copyleft",
    linkage: "subproceso",
  },
  {
    name: "Blender",
    version: "5.2.2",
    license: "GPL-3.0-or-later",
    role: "Ejecuta el motor Molcy; se descarga a petición y no viaja en el instalador",
    sourceUrl: "https://projects.blender.org/blender/blender",
    attention: "copyleft",
    linkage: "subproceso",
  },
  {
    name: "Molecular Nodes",
    version: "la que instala Blender Extensions",
    license: "GPL-3.0-or-later",
    role: "Construye las moléculas de las escenas de Molcy; se instala a petición y no viaja en el instalador",
    sourceUrl: "https://github.com/BradyAJohnston/MolecularNodes",
    attention: "copyleft",
    linkage: "subproceso",
  },
  {
    name: "Meeko",
    version: "0.7.1",
    license: "LGPL-2.1-or-later",
    role: "Preparación AutoDock",
    sourceUrl: "https://github.com/forlilab/Meeko",
    attention: "copyleft",
    linkage: "biblioteca",
  },
  {
    name: "MDAnalysis",
    version: "2.10.0",
    license: "LGPL-3.0-or-later",
    role: "Lectura de estructuras para el análisis de interacciones (ProLIF)",
    sourceUrl: "https://github.com/MDAnalysis/mdanalysis",
    attention: "copyleft",
    linkage: "biblioteca",
  },
  {
    name: "GridDataFormats",
    version: "1.2.0",
    license: "LGPL-3.0-or-later",
    role: "Dependencia de MDAnalysis",
    sourceUrl: "https://github.com/MDAnalysis/GridDataFormats",
    attention: "copyleft",
    linkage: "biblioteca",
  },
  {
    name: "paramiko",
    version: "5.0.0",
    license: "LGPL-2.1",
    role: "Dependencia transitiva de fsspec; ningún módulo de MolDesign la usa",
    sourceUrl: "https://github.com/paramiko/paramiko",
    attention: "copyleft",
    linkage: "biblioteca",
  },
  {
    name: "gemmi",
    version: "0.7.5",
    license: "MPL-2.0",
    role: "Lectura de mmCIF/PDBx de los receptores propios",
    sourceUrl: "https://github.com/project-gemmi/gemmi",
    attention: "copyleft",
    linkage: "biblioteca",
  },
  {
    name: "xTB",
    version: "6.7.1",
    license: "LGPL-3.0-or-later",
    role: "Motor cuántico",
    sourceUrl: "https://github.com/grimme-lab/xtb",
    attention: "copyleft",
    linkage: "subproceso",
  },
  {
    name: "rpc-websockets",
    version: "9.3.9",
    license: "LGPL-3.0-only",
    role: "Dependencia transitiva de Solana Web3.js",
    sourceUrl: "https://github.com/elpheria/rpc-websockets",
    attention: "copyleft",
    linkage: "biblioteca",
  },
  {
    name: "TabPFN",
    version: "8.0.8",
    license: "Prior Labs License 1.2",
    role: "Modelo fundacional tabular; viaja en el runtime y ninguna ruta de 1.0.2 lo usa",
    sourceUrl: "https://github.com/PriorLabs/TabPFN",
    attention: "attribution",
  },
  {
    name: "ReportLab",
    version: "4.2.0",
    license: "BSD-3-Clause",
    role: "PDF del dossier y de los certificados; empaqueta la tipografía DarkGarden (GPL con excepción de fuente), que MolDesign no usa",
    sourceUrl: "https://www.reportlab.com/",
  },
  {
    name: "Microsoft Visual C++ Runtime",
    version: "14.50.35719",
    license: "Microsoft redistributable",
    role: "Bibliotecas de ejecución de los programas nativos; no las cubre la licencia de MolDesign",
    sourceUrl: "https://learn.microsoft.com/cpp/windows/redistributing-visual-cpp-files",
  },
  {
    name: "ESMFold",
    version: "v1",
    license: "MIT",
    role: "Plegado de péptidos; sus pesos se descargan a petición",
    sourceUrl: "https://github.com/facebookresearch/esm",
  },
  {
    name: "llama.cpp",
    version: "b10199",
    license: "MIT",
    role: "Inferencia LLM local",
    sourceUrl: "https://github.com/ggml-org/llama.cpp",
  },
  {
    name: "AutoDock Vina",
    version: "1.2.7",
    license: "Apache-2.0",
    role: "Docking, e incluye vina_trace, una copia modificada que registra la búsqueda",
    sourceUrl: "https://github.com/ccsb-scripps/AutoDock-Vina",
    linkage: "subproceso",
  },
  {
    name: "RTMScore",
    version: "snapshot integrado",
    license: "MIT",
    role: "Rescoring de investigación",
    sourceUrl: "https://github.com/sc8668/RTMScore",
  },
  // ── Datos del catálogo de receptores ──────────────────────────────────
  //
  // Las dos fuentes van separadas porque sus condiciones son distintas y
  // fundirlas induciría a error: CC0 no pide atribución y CC BY 4.0 sí. La
  // curación (caja, hotspots, cadena, familia) no procede de ninguna de las
  // dos: la calcula MolDesign, y ninguna certifica sus resultados.
  {
    name: "RCSB Protein Data Bank / wwPDB",
    version: "380 estructuras",
    license: "CC0 1.0",
    role: "Estructuras y metadatos estructurales base · 380 receptores curados · cita científica recomendada",
    sourceUrl: "https://www.rcsb.org/pages/usage-policy",
    // Sin `attention: "attribution"` A PROPÓSITO: CC0 es una renuncia de
    // derechos y no exige atribución. Marcarlo pintaría en la interfaz una
    // obligación que la licencia no impone.
  },
  {
    name: "UniProtKB",
    version: "comentario FUNCTION",
    license: "CC BY 4.0",
    role: "Fuente: UniProtKB; descripciones funcionales · traducción/adaptación al español: MolDesign",
    sourceUrl: "https://www.uniprot.org/help/license",
    attention: "attribution",
  },
  // No viaja código de MolTalk, pero el método de alineación de la elevación
  // 2D → 3D sigue de cerca su `_fit`: se le reconoce y se conserva su aviso MIT
  // (THIRD_PARTY_NOTICES.md y third_party/moltalk/).
  {
    name: "MolTalk",
    version: "1.0.0 · 44da199",
    license: "MIT",
    role: "Inspiró la elevación 2D → 3D de Moldex y del editor; MolDesign reimplementa su método de alineación y no incluye su código",
    sourceUrl: "https://github.com/DomFico/moltalk",
    attention: "attribution",
    linkage: "metodo",
  },
];



