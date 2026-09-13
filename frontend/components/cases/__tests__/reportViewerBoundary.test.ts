// =====================================================================
// Guardia: los dos visores no se mezclan
// =====================================================================
//
// HAY DOS DOCUMENTOS Y RESPONDEN A PREGUNTAS DISTINTAS.
//
//   · El CERTIFICADO (`PDFReportViewer` → `GET /blockchain/certificate/…`)
//     sella cuándo se emitió algo. Lo consumen ProEvaluation y Moldex, y su
//     conversación gira alrededor del registro de integridad.
//
//   · El DOSSIER DEL CASO (`CaseDossierViewer` → `POST /evaluation/dossier/…`)
//     declara qué evidencia produjo una corrida y qué quedó sin evaluar. Viaja
//     por POST porque el caso vive en el cliente.
//
// Migrar el primero al segundo habría cambiado el comportamiento de dos
// consumidores que nadie pidió tocar; meter blockchain en el segundo lo
// convertiría en un sello, que es justo lo que no es.
//
// Es un test estático a propósito: un test de comportamiento sólo cubre el
// camino que ejercita, y esta frontera se cruza escribiendo un import.

import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

const COMPONENTS = join(__dirname, "..", "..");

function source(...parts: string[]): string {
  return readFileSync(join(COMPONENTS, ...parts), "utf8");
}

/**
 * El archivo SIN comentarios.
 *
 * Estos archivos explican por escrito por qué NO usan al otro visor, así que
 * buscar el nombre en el texto crudo encontraría justamente la explicación de
 * su ausencia. Lo que se vigila es el código.
 */
function code(...parts: string[]): string {
  return source(...parts)
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/^[ 	]*\/\/.*$/gm, "");
}

describe("frontera entre el certificado y el dossier del caso", () => {
  it("ProEvaluation sigue usando su visor histórico, intacto", () => {
    const pro = source("interfaces", "pro", "ProEvaluation.tsx");
    expect(pro).toContain('import { PDFReportViewer } from "../../PDFReportViewer"');
    expect(pro).toContain("<PDFReportViewer");
    // Y no se le ha colado el visor del caso, que exige un `CaseRecord` que
    // ProEvaluation no tiene.
    expect(pro).not.toContain("CaseDossierViewer");
  });

  it("PDFReportViewer sigue pidiendo el certificado por la ruta histórica", () => {
    const viewer = source("PDFReportViewer.tsx");
    expect(viewer).toContain("fetchCertificateBlobUrl");
    expect(viewer).toContain("downloadCertificate");
    // Su flujo de certificación sigue en pie.
    expect(viewer).toContain("CertificationModal");
  });

  it("el informe del caso NO monta el visor del certificado", () => {
    const reportView = code("cases", "CaseReportView.tsx");
    expect(reportView).toContain("CaseDossierViewer");
    expect(reportView).not.toContain("PDFReportViewer");
  });

  it("el dossier del caso no habla de cadena ni de certificados", () => {
    const dossierViewer = code("cases", "CaseDossierViewer.tsx");
    expect(dossierViewer).not.toContain("blockchain/certificate");
    expect(dossierViewer).not.toContain("certifyMolecule");
    expect(dossierViewer).not.toContain("CertificationModal");
  });
});
