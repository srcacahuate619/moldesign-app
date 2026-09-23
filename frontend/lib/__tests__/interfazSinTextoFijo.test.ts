// =====================================================================
// El trinquete: el castellano fijo en la interfaz sólo puede bajar
// =====================================================================
//
// EL FALLO QUE MIDE. El paquete declara `es-ES` y `en-US`, y el diccionario
// tiene los dos idiomas completos. Pero sólo un puñado de componentes consume
// `t()`: el resto lleva el texto escrito a mano, así que con el idioma en
// English el usuario lee castellano. Microsoft rechaza por calidad una
// aplicación cuyos idiomas declarados no están realmente soportados — es la
// misma regla por la que este proyecto ya retiró once idiomas incompletos, y
// el inglés estaba en esa situación sin que nada avisara.
//
// POR QUÉ UN PRESUPUESTO Y NO UN CERO. Quedan cientos de cadenas y la migración
// va por superficies. Un cero hoy dejaría la prueba en rojo durante días, y una
// prueba que vive en rojo deja de leerse. El presupuesto hace dos cosas que un
// cero no hace: mide el avance y IMPIDE EL RETROCESO. Cada superficie migrada
// baja su número; ninguna puede subirlo.
//
// CÓMO SE ACTUALIZA. Al migrar una pantalla se vuelve a ejecutar y se copia el
// número nuevo. Subir un presupuesto para que pase la prueba es exactamente lo
// que esta prueba existe para impedir: si hace falta, es que alguien añadió
// texto sin traducir.
import { execFileSync } from "node:child_process";

import { readdirSync, readFileSync, rmSync, statSync, writeFileSync } from "node:fs";
import { dirname, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

const RAIZ = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..");
const CARPETAS = ["app", "components", "hooks"];

/**
 * Marcas de castellano. Se exige una tilde, una eñe, un signo de apertura o una
 * palabra función: un rótulo como «Vina» o «SMILES» no es castellano, es el
 * nombre de una cosa.
 */
const MARCAS_ES =
  /[áéíóúñü¿¡ÁÉÍÓÚÑÜ]|\b(el|la|los|las|un|una|de|del|que|para|con|por|sin|no|se|es|son|está|están|más|como|pero|este|esta|todo|hay|desde|cuando|puede|tiene|sobre|entre|ya|así|cada|otro|otra)\b/i;

/**
 * Techo por fichero. Se baja al migrar; NUNCA se sube.
 *
 * Los que faltan valen cero: una pantalla nueva nace traducida.
 */
const PRESUPUESTO: Readonly<Record<string, number>> = {
  "components/registro/RegistroCientifico.tsx": 15,
  "components/interfaces/pro/ProParametersTab.tsx": 11,
  "components/ai/ChatPanel.tsx": 10,
  "components/interfaces/pro/EvaluationEvidencePanel.tsx": 10,
  "components/interfaces/pro/TargetSelectorModal.tsx": 10,
  "components/ui/OptionsMenu.tsx": 0,
  "components/ai/AISettingsModal.tsx": 8,
  "components/MethodDisclaimer.tsx": 8,
  "components/interfaces/pro/ProDockingTab.tsx": 6,
  "components/MoleculeViewer3D.tsx": 6,
  "components/ScoreCard.tsx": 6,
  "components/ui/AboutModal.tsx": 6,
  "components/DrugLikenessPanel.tsx": 5,
  "components/evaluation/CaseEvaluationRunner.tsx": 5,
  "components/interfaces/pro/ProConfigPanel.tsx": 5,
  "components/interfaces/pro/Web3DViewer.tsx": 5,
  "components/PropertiesPanel.tsx": 5,
  "components/ai/ChatInput.tsx": 4,
  "components/interfaces/pro/EstadoDelLigando.tsx": 4,
  "components/interfaces/pro/ProSarTab.tsx": 4,
  "components/interfaces/pro/ReceptorVariantModal.tsx": 4,
  "components/MolecularComparison.tsx": 4,
  "components/registro/ContrasteInicio.tsx": 4,
  "components/SupportPanel.tsx": 4,
  "components/TraspasoInvitado.tsx": 4,
  "components/ai/ProviderBadge.tsx": 3,
  "components/interfaces/pro/AvisoSinWebGL.tsx": 3,
  "components/OptionsPanel.tsx": 3,
  "components/PDFReportViewer.tsx": 3,
  "components/ai/ChatMessage.tsx": 2,
  "components/DownloadCard.tsx": 2,
  "components/DownloadNotifications.tsx": 2,
  "components/evaluation/LipinskiSpiderChart.tsx": 2,
  "components/interfaces/pro/PoseComparisonDialog.tsx": 2,
  "components/KetcherEditor.tsx": 2,
  "components/LauncherScreen.tsx": 2,
  "components/Navigation.tsx": 2,
  "components/PipelineFlowchart.tsx": 2,
  "components/ReproducibilityInfo.tsx": 2,
  "components/science/ProtocoloM5Zn.tsx": 2,
  "components/ScientificWarnings.tsx": 2,
  "components/ui/LogConsole.tsx": 2,
  "app/evaluation/batch/page.tsx": 1,
  "app/evaluation/page.tsx": 1,
  "components/ai/BloqueDeEvidencia.tsx": 1,
  "components/CommunityPanel.tsx": 1,
  "components/interfaces/pro/AdvancedMolstarViewer.tsx": 1,
  "components/interfaces/pro/ProAlertsTab.tsx": 1,
  "components/interfaces/pro/StageCard.tsx": 1,
  "components/LauncherGate.tsx": 1,
  "components/MoldexCard.tsx": 1,
  "components/MoleculeTechViewer.tsx": 1,
  "components/RequireModel.tsx": 1,
  "components/science/DetalleDelSitio.tsx": 1,
  "components/TechNetwork3D.tsx": 1,
  "components/ui/Ayuda.tsx": 1,
  "components/ui/VirtualMoleculeList.tsx": 1,
};

/** Techo global. Es el que cuenta: el detalle por fichero sólo dice dónde. */
const PRESUPUESTO_TOTAL = 0;

function ficheros(dir: string, acc: string[] = []): string[] {
  let entradas: string[];
  try {
    entradas = readdirSync(dir);
  } catch {
    return acc;
  }
  for (const e of entradas) {
    if (["node_modules", ".next", "out", "__tests__", "e2e"].includes(e)) continue;
    const p = join(dir, e);
    if (statSync(p).isDirectory()) ficheros(p, acc);
    else if (/\.tsx$/.test(e) && !/\.test\./.test(e)) acc.push(p);
  }
  return acc;
}

/** Fuera comentarios: la prosa de documentación no es interfaz. */
function sinComentarios(src: string): string {
  return src
    .replace(/\/\*[\s\S]*?\*\//g, " ")
    .replace(/\{\/\*[\s\S]*?\*\/\}/g, " ")
    .replace(/(^|[^:])\/\/[^\n]*/g, "$1 ");
}

/** Texto que el usuario LEE o ESCUCHA y que no pasa por el traductor. */
export function cadenasFijas(src: string): string[] {
  const limpio = sinComentarios(src);
  const vistas = new Set<string>();
  const candidatos: string[] = [];
  for (const m of limpio.matchAll(/>\s*([^<>{}\n][^<>{}]{3,})\s*</g)) candidatos.push(m[1]);
  for (const m of limpio.matchAll(
    /\b(title|placeholder|aria-label|aria-description|alt|label)\s*=\s*[{"']\s*["'`]?([^"'`}\n]{4,})["'`]?/g,
  )) {
    candidatos.push(m[2]);
  }
  for (const c of candidatos) {
    const txt = c.trim();
    if (txt.length < 4 || !/[a-zA-Z]/.test(txt)) continue;
    if (/^[\d\s.,:%×·–—/+-]+$/.test(txt)) continue;
    if (!MARCAS_ES.test(txt)) continue;
    vistas.add(txt);
  }
  return [...vistas];
}

const medidos = ficheros(join(RAIZ, CARPETAS[0]))
  .concat(...CARPETAS.slice(1).map((c) => ficheros(join(RAIZ, c))))
  .map((ruta) => ({
    rel: relative(RAIZ, ruta).replace(/\\/g, "/"),
    cadenas: cadenasFijas(readFileSync(ruta, "utf8")),
  }))
  .filter((f) => f.cadenas.length > 0);

console.log(JSON.stringify(medidos, null, 2));
describe("la interfaz no puede tener más castellano fijo que ayer", () => {
  it("ningún fichero supera su presupuesto", () => {
    const excesos = medidos
      .map((f) => ({ ...f, techo: PRESUPUESTO[f.rel] ?? 0 }))
      .filter((f) => f.cadenas.length > f.techo)
      .map((f) => `${f.rel}: ${f.cadenas.length} > ${f.techo} — p.ej. «${f.cadenas[0]}»`);
    expect(
      excesos,
      "Texto visible sin traducir por encima de lo permitido. Pásalo por `t()` "
        + "en vez de subir el presupuesto:\n  " + excesos.join("\n  "),
    ).toEqual([]);
  });

  it("el total no crece", () => {
    const total = medidos.reduce((s, f) => s + f.cadenas.length, 0);
    expect(
      total,
      `Hay ${total} cadenas visibles en castellano fijo y el techo es `
        + `${PRESUPUESTO_TOTAL}. Con el idioma en English el usuario las lee en `
        + "castellano.",
    ).toBeLessThanOrEqual(PRESUPUESTO_TOTAL);
  });


  // EL BARRIDO AST ESTUVO CIEGO. Hasta el 2026-09-22 esta prueba exigía que
  // el barrido no imprimiera «Texto visible sin clave», y pasaba en verde: su
  // regex de términos técnicos llevaba /i y se tragaba cualquier palabra sin
  // tilde —Cohortes, OPCIONES, Guardar—, y la rama de castellano tenía las
  // tildes convertidas en «?». Con el detector reparado, el barrido cuenta
  // 619 literales pendientes en 76 ficheros. La capa de arriba (MARCAS_ES)
  // tampoco los ve: exige una tilde o una palabra función, y un rótulo de una
  // palabra no lleva ninguna de las dos.
  const SCRIPT = resolve(__dirname, "../../scripts/finish-i18n-frontend.cjs");
  const INVENTARIO = resolve(__dirname, "textoPendienteDeTraducir.json");

  it("el barrido AST demuestra que ve antes de contar", () => {
    // Si el autotest del script falla, sale con 1 y execFileSync lanza.
    const salida = execFileSync(process.execPath, [SCRIPT, "--autotest"], {
      cwd: resolve(__dirname, "../.."),
      encoding: "utf8",
    });
    expect(salida).toContain("el guardian ve");
  });

  it("el barrido ve un literal nuevo, con clave o sin ella, en un componente real", () => {
    // La mutación que el autotest del script no cubre: un fichero de verdad en
    // components/. «Definir» TIENE clave (lo_paso_definir) y aun así se pinta
    // sin t(); el 2026-09-23 ese caso era invisible y un lote de migración
    // escondió así cuatro literales de otros ficheros.
    const raiz = resolve(__dirname, "../..");
    const mutante = join(raiz, "components", "MutanteDelGuardian.tsx");
    writeFileSync(mutante, [
      "export function MutanteDelGuardian() {",
      "  return (<div><span>Rótulo de mutación sin clave</span><span>Definir</span></div>);",
      "}",
      "",
    ].join("\n"), "utf8");
    try {
      const actual: string[] = JSON.parse(execFileSync(process.execPath, [SCRIPT, "--json"], {
        cwd: raiz,
        encoding: "utf8",
      }));
      expect(actual).toContain("components/MutanteDelGuardian.tsx: Rótulo de mutación sin clave");
      expect(actual).toContain("components/MutanteDelGuardian.tsx: Definir");
    } finally {
      rmSync(mutante, { force: true });
    }
  });

  it("el texto pendiente de traducir sólo puede bajar", () => {
    const actual: string[] = JSON.parse(execFileSync(process.execPath, [SCRIPT, "--json"], {
      cwd: resolve(__dirname, "../.."),
      encoding: "utf8",
    }));
    const base = new Set<string>(JSON.parse(readFileSync(INVENTARIO, "utf8")));
    const nuevas = actual.filter((e) => !base.has(e));
    const resueltas = [...base].filter((e) => !actual.includes(e));
    expect(
      nuevas,
      "Texto visible nuevo sin pasar por t(). Tradúcelo; no lo añadas al inventario:\n  "
        + nuevas.join("\n  "),
    ).toEqual([]);
    expect(
      resueltas,
      "Estas cadenas ya no están pendientes. Quítalas de textoPendienteDeTraducir.json "
        + "o el trinquete deja de vigilar (node scripts/finish-i18n-frontend.cjs --json):\n  "
        + resueltas.join("\n  "),
    ).toEqual([]);
  });

  it("una pantalla que ya se migró no puede volver atrás", () => {
    // Las superficies terminadas se listan aquí con cero. Es lo que convierte
    // el presupuesto en un trinquete y no en una foto. OJO: «terminada» aquí
    // significa sin MARCAS_ES, no sin texto fijo; el inventario del barrido AST
    // todavía encuentra rótulos en varias (CaseWorkspace, CaseSidebar…).
    const TERMINADAS: string[] = [
      "app/comunidad/page.tsx",
      "app/global-error.tsx",
      "app/history/page.tsx",
      "app/moldex/page.tsx",
      "components/CertificationModal.tsx",
      "components/cases/CaseContextPanel.tsx",
      "components/cases/CaseDetailsDrawer.tsx",
      "components/cases/CaseDispositionPanel.tsx",
      "components/cases/CaseDossierViewer.tsx",
      "components/cases/CaseEmptyState.tsx",
      "components/cases/CaseReportView.tsx",
      "components/cases/CaseRunHistoryModal.tsx",
      "components/cases/CaseSidebar.tsx",
      "components/cases/CaseSidebarShell.tsx",
      "components/cases/CaseWorkspace.tsx",
      "components/cases/CreateCaseDialog.tsx",
      "components/evaluation/EstimacionDeCorrida.tsx",
      "components/evaluation/PreparationPanel.tsx",
      "components/interfaces/pro/CustomReceptorModal.tsx",
      "components/interfaces/pro/DockingEnginePanel.tsx",
      "components/interfaces/pro/ProAnalysisTabs.tsx",
      "components/interfaces/pro/ProEvaluation.tsx",
      "components/interfaces/pro/ProOptionsModal.tsx",
      "components/interfaces/pro/ProSelectivityPanel.tsx",
      "components/interfaces/pro/ProXaiTab.tsx",
      "components/ui/LegalModal.tsx",
    ];
    for (const rel of TERMINADAS) {
      const f = medidos.find((m) => m.rel === rel);
      expect(
        f?.cadenas ?? [],
        `${rel} ya estaba traducida y volvió a tener texto fijo`,
      ).toEqual([]);
    }
  });
});
