export const PRODUCT = {
  name: "MolDesign AI",
  version: "1.0.0",
  edition: "Desktop Edition",
  license: "PolyForm-Noncommercial-1.0.0",
  sourceUrl: "https://github.com/srcacahuate619/moldesign-app",
  noticesUrl: "/legal/THIRD_PARTY_NOTICES.md",
  sourceOfferUrl: "/legal/SOURCE_CODE_AND_RELINKING.md",
  commercialLicenseUrl: "/legal/licenses/COMMERCIAL-LICENSE.md",
} as const;

export type SoftwareAvailability = "Incluido" | "Opcional" | "Servicio externo";
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
        description: "Motor de docking que genera y puntúa poses ligando–receptor.",
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
        name: "OpenMM + PDBFixer",
        version: "8.5.2 / 1.12.0",
        kind: "Tercero",
        availability: "Incluido",
        description: "Preparación estructural y mecánica molecular para rutas que requieren refinamiento físico.",
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
        description: "Modelo fundacional tabular empleado por rutas predictivas compatibles.",
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
        credit: "MolDesign AI Research",
      },
    ],
  },
  {
    id: "ai",
    label: "IA y lenguaje",
    cards: [
      {
        name: "DiffDock",
        version: "API compatible",
        kind: "Tercero",
        availability: "Servicio externo",
        description: "Docking generativo disponible cuando el investigador configura un servicio DiffDock compatible.",
        credit: "Corso et al.; servicio y pesos administrados por el usuario",
      },
      {
        name: "ColabFold",
        version: "API compatible",
        kind: "Tercero",
        availability: "Servicio externo",
        description: "Predicción de complejos proteína–péptido mediante un endpoint configurado por el investigador.",
        credit: "ColabFold and AlphaFold contributors",
      },
      {
        name: "RFdiffusion",
        version: "sidecar ESMFold-Pro",
        kind: "Tercero",
        availability: "Servicio externo",
        description: "Motor peptídico experimental accesible mediante un sidecar configurado; requiere GPU y no se incluye en el instalador base.",
        credit: "Baker Lab / Institute for Protein Design",
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
        name: "faster-whisper",
        version: "1.2.1",
        kind: "Tercero",
        availability: "Incluido",
        description: "Transcripción local de voz para las entradas compatibles de MolChat.",
        credit: "SYSTRAN and Whisper contributors",
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
        version: "2.11.3",
        kind: "Tercero",
        availability: "Incluido",
        description: "Contenedor nativo, ciclo de vida del backend y empaquetado de la edición Desktop.",
        credit: "Tauri Programme within The Commons Conservancy",
      },
      {
        name: "Next.js + React",
        version: "14.2.25 / 18.3.1",
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
        version: "3.12.0",
        kind: "Tercero",
        availability: "Incluido",
        description: "Editor químico 2D para dibujar, importar y exportar estructuras moleculares.",
        credit: "EPAM Systems",
      },
      {
        name: "Solana Web3.js",
        version: "1.98.4",
        kind: "Tercero",
        availability: "Servicio externo",
        description: "Integración opcional para registrar certificados; no constituye por sí misma protección de propiedad intelectual.",
        credit: "Solana Foundation and contributors",
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
        description: "Vina, Meeko, xTB, RTMScore, ADMET-AI y TabPFN conservan sus autores y referencias metodológicas.",
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
          "Curación de MolDesign sobre las estructuras de RCSB: caja de docking, "
          + "hotspots, selección de cadena, familia estructural y estado. Esa capa "
          + "es cálculo propio, no una afirmación de RCSB ni de UniProt.",
        credit:
          "Curación y cálculo: MolDesign AI · estructuras CC0 de RCSB PDB · "
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
   * lector la suponga.
   */
  linkage?: "subproceso" | "biblioteca";
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
    role: "Conversión estructural de respaldo (PDBQT → SDF) El ejecutable empaquetado reporta internamente 3.1.0 por una correccion de empaquetado; el valor medido consta en el manifiesto del paquete.",
    sourceUrl: "https://github.com/openbabel/openbabel",
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
    role: "Modelo fundacional tabular",
    sourceUrl: "https://github.com/PriorLabs/TabPFN",
    attention: "attribution",
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
    role: "Docking",
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
];



