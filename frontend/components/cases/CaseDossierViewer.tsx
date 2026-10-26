"use client";

// =====================================================================
// CaseDossierViewer — el dossier del CASO, no el certificado
// =====================================================================
//
// POR QUÉ EXISTE, EN VEZ DE MIGRAR `PDFReportViewer`. Aquel visor pide
// `GET /blockchain/certificate/{id}/preview` y su conversación con el usuario
// gira alrededor del sello: «la integridad de este dossier aún no está
// registrada», «Registrar integridad». Ese flujo sigue vivo en ProEvaluation y
// en Moldex, y romperlo para meter aquí otra ruta habría cambiado el
// comportamiento de dos consumidores que nadie pidió tocar.
//
// El dossier del caso responde otra pregunta —qué evidencia produjo esta
// corrida y qué quedó sin evaluar—, viaja por POST porque el caso vive en el
// cliente, y no tiene nada que ver con la cadena. Son dos documentos distintos
// y por eso son dos componentes distintos.
//
// TRES COSAS QUE ESTE ARCHIVO PROTEGE:
//
// 1. **El dossier que se ve es el del caso que se está mirando.** Cada petición
//    lleva un testigo; una respuesta que llega tarde, de otro caso o de una
//    petición ya sustituida, se descarta. Sin esto, cambiar de caso mientras el
//    PDF se genera podía dejar el dossier de otro caso en pantalla — la
//    atribución falsa que este producto existe para evitar.
//
// 2. **Los object URL se revocan.** Al actualizar, al desmontar y al cambiar de
//    caso. Un blob de varios MB retenido por cada visita al informe es una fuga
//    que el usuario paga en memoria.
//
// 3. **El ZIP no se declara verificado.** Descargarlo prueba que se descargó.
//    El paquete trae su propio manifiesto con hashes para que alguien lo
//    verifique; decir «verificado» porque el navegador guardó un archivo sería
//    exactamente la afirmación sin comprobar que el dossier quiere impedir.

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useLanguage } from "../../context/LanguageContext";
import { AlertCircle, Download, FileArchive, FileText, Loader2, Maximize2, Minimize2, RefreshCw } from "lucide-react";

import {
  DossierError,
  buildCaseProjection,
  dossierPackageFilename,
  dossierPdfFilename,
  requestDossierPackage,
  requestDossierPreview,
  saveBlobAs,
} from "../../lib/dossier";
import type { CaseRecord, ReportableResult, RunInputsRelation } from "../../lib/cases/types";
import { beginFileDownload, failFileDownload } from "../../lib/activityNotifications";

export interface CaseDossierViewerProps {
  readonly caseRecord: CaseRecord;
  readonly reportable: ReportableResult;
  readonly runRelation: RunInputsRelation;
}

type LoadState = "loading" | "ready" | "error";

/** Una operación a la vez por botón: mientras corre, ese botón no acepta más. */
type Busy = "none" | "package";

export function CaseDossierViewer({
  caseRecord,
  reportable,
  runRelation,
}: CaseDossierViewerProps) {
  const { t, locale } = useLanguage();
  const [state, setState] = useState<LoadState>("loading");
  const [error, setError] = useState<string | null>(null);
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [pdfBlob, setPdfBlob] = useState<Blob | null>(null);
  const [pdfName, setPdfName] = useState<string | null>(null);
  const [busy, setBusy] = useState<Busy>("none");
  const [packageError, setPackageError] = useState<string | null>(null);
  const [packageSaved, setPackageSaved] = useState<string | null>(null);
  // Cada petición se numera. Sólo la última manda; las anteriores se descartan
  // aunque contesten después (respuesta tardía de otro caso o de otro intento).
  const requestToken = useRef(0);
  const packageToken = useRef(0);
  const packageController = useRef<AbortController | null>(null);
  const objectUrl = useRef<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const viewerRef = useRef<HTMLDivElement | null>(null);
  const [nativeFullscreen, setNativeFullscreen] = useState(false);
  const [fallbackFullscreen, setFallbackFullscreen] = useState(false);
  const fullscreen = nativeFullscreen || fallbackFullscreen;

  useEffect(() => {
    const syncFullscreen = () => {
      setNativeFullscreen(document.fullscreenElement === viewerRef.current);
    };
    document.addEventListener("fullscreenchange", syncFullscreen);
    return () => document.removeEventListener("fullscreenchange", syncFullscreen);
  }, []);

  useEffect(() => {
    if (!fallbackFullscreen) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      event.preventDefault();
      setFallbackFullscreen(false);
    };
    window.addEventListener("keydown", closeOnEscape, true);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", closeOnEscape, true);
    };
  }, [fallbackFullscreen]);

  const caseId = caseRecord.id;
  const moleculeId = reportable.moleculeId;

  /**
   * La proyección más reciente, sin ser una dependencia del efecto.
   *
   * El dossier NO se regenera con cada cambio del caso. Editar el contexto en
   * «Detalles» cambia `caseRecord` en cada tecla, y atar la petición a ese
   * objeto pediría un PDF por pulsación. El dossier se pide al abrir el
   * informe, al cambiar de caso o de resultado, y cuando se pulsa «Actualizar
   * dossier» — que existe precisamente para eso. Lo que sí está garantizado es
   * que cada petición usa el caso tal como está en ese instante.
   */
  const projection = useMemo(
    () => buildCaseProjection(caseRecord, reportable, runRelation),
    [caseRecord, reportable, runRelation],
  );
  const projectionRef = useRef(projection);
  projectionRef.current = projection;

  const publishUrl = useCallback((next: string | null) => {
    if (objectUrl.current) URL.revokeObjectURL(objectUrl.current);
    objectUrl.current = next;
    setBlobUrl(next);
  }, []);

  useEffect(() => {
    const token = ++requestToken.current;
    const controller = new AbortController();
    let cancelled = false;

    setState("loading");
    setError(null);
    // El PDF anterior deja de ser el de este caso en cuanto se pide otro.
    publishUrl(null);
    setPdfBlob(null);
    setPdfName(null);
    setPackageError(null);
    setPackageSaved(null);

    requestDossierPreview(moleculeId, projectionRef.current, controller.signal)
      .then((artifact) => {
        // Doble guarda: el testigo descarta respuestas de peticiones
        // sustituidas, y `cancelled` descarta las de un montaje ya desmontado.
        if (cancelled || token !== requestToken.current) return;
        publishUrl(URL.createObjectURL(artifact.blob));
        setPdfBlob(artifact.blob);
        setPdfName(artifact.filename);
        setState("ready");
      })
      .catch((failure: unknown) => {
        if (cancelled || token !== requestToken.current) return;
        if ((failure as { name?: string })?.name === "AbortError") return;
        setError(
          failure instanceof DossierError
            ? failure.message
            : (failure as Error)?.message || t("auto_5e8ef3521b05"),
        );
        setState("error");
      });

    return () => {
      cancelled = true;
      controller.abort();
    };
    // `caseId` está en las dependencias aunque no se use dentro: cambiar de
    // caso DEBE tirar la petición en vuelo y pedir el dossier del caso nuevo,
    // incluso en el caso improbable de que dos casos compartieran molécula.
  }, [moleculeId, caseId, attempt, publishUrl, locale]);

  // Revocación al desmontar. Va aparte del efecto de carga: aquel revoca al
  // sustituir, éste al desaparecer.
  useEffect(() => {
    return () => {
      if (objectUrl.current) URL.revokeObjectURL(objectUrl.current);
      objectUrl.current = null;
    };
  }, []);

  // El paquete también es una petición del caso. Si el usuario cambia de caso
  // o abandona Informe, se invalida y cancela: no debe aparecer después una
  // descarga perteneciente a una pantalla que ya no está activa.
  useEffect(() => {
    packageController.current?.abort();
    packageController.current = null;
    packageToken.current += 1;
    setBusy("none");

    return () => {
      packageToken.current += 1;
      packageController.current?.abort();
      packageController.current = null;
    };
  }, [caseId, moleculeId, locale]);

  const toggleFullscreen = useCallback(async () => {
    if (fallbackFullscreen) {
      setFallbackFullscreen(false);
      return;
    }
    if (nativeFullscreen) {
      try {
        await document.exitFullscreen();
      } catch {
        setFallbackFullscreen(false);
      }
      return;
    }
    const element = viewerRef.current;
    if (!element) return;
    try {
      if (typeof element.requestFullscreen !== "function") throw new Error("Fullscreen unavailable");
      await element.requestFullscreen();
    } catch {
      setFallbackFullscreen(true);
    }
  }, [fallbackFullscreen, nativeFullscreen]);

  const refresh = useCallback(() => setAttempt((value) => value + 1), []);

  const downloadPdf = useCallback(() => {
    if (!pdfBlob) return;
    saveBlobAs(pdfBlob, pdfName ?? dossierPdfFilename(caseRecord.name), "evaluation");
  }, [pdfBlob, pdfName, caseRecord.name]);

  const exportPackage = useCallback(async () => {
    if (busy === "package") return;
    setBusy("package");
    setPackageError(null);
    setPackageSaved(null);
    const token = ++packageToken.current;
    const controller = new AbortController();
    packageController.current = controller;
    const proposedName = dossierPackageFilename(caseRecord.id, caseRecord.activeRun?.taskId);
    const activityId = beginFileDownload(proposedName, "evaluation");
    try {
      const artifact = await requestDossierPackage(
        moleculeId,
        projectionRef.current,
        controller.signal,
      );
      // Si mientras tanto se cambió de caso, este ZIP ya no es el que se pidió.
      if (token !== packageToken.current) {
        failFileDownload(activityId, proposedName, "evaluation");
        return;
      }
      const name =
        artifact.filename ?? dossierPackageFilename(caseRecord.id, caseRecord.activeRun?.taskId);
      saveBlobAs(artifact.blob, name, "evaluation", activityId);
      setPackageSaved(name);
    } catch (failure) {
      failFileDownload(activityId, proposedName, "evaluation");
      if (token !== packageToken.current) return;
      if ((failure as { name?: string })?.name === "AbortError") return;
      setPackageError(
        failure instanceof DossierError
          ? failure.message
          : (failure as Error)?.message || "El paquete no se pudo exportar.",
      );
    } finally {
      if (token === packageToken.current) {
        packageController.current = null;
        setBusy("none");
      }
    }
  }, [busy, caseRecord.id, caseRecord.activeRun?.taskId, moleculeId]);

  const loading = state === "loading";
  const packaging = busy === "package";

  return (
    <div
      ref={viewerRef}
      role="region"
      aria-label={t("ca_dossier_caso")}
      data-dossier-fullscreen={fullscreen || undefined}
      className={fullscreen
        ? "fixed inset-0 z-[200] flex h-[100dvh] w-screen flex-col overflow-hidden bg-surface-950 font-sans"
        : "relative flex h-full min-h-0 w-full flex-col overflow-hidden rounded-lg border border-surface-800 bg-surface-950 font-sans"}
    >
      {/* ── Barra de acciones ────────────────────────────────────────── */}
      <div className="flex min-h-16 flex-wrap items-center justify-between gap-3 border-b border-surface-800 bg-surface-900 px-4 py-3">
        <div className="flex min-w-0 items-center gap-2">
          <FileText className="h-4 w-4 shrink-0 text-brand-400" aria-hidden="true" />
          <span className="truncate font-mono text-xs tracking-wider text-surface-300">
            {pdfName ?? dossierPdfFilename(caseRecord.name)}
          </span>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => void toggleFullscreen()}
            aria-pressed={fullscreen}
            aria-label={t(fullscreen ? "ca_dossier_reducir" : "ca_dossier_expandir")}
            title={t(fullscreen ? "ca_dossier_reducir" : "ca_dossier_expandir")}
            className="flex h-11 items-center gap-2 whitespace-nowrap rounded-md border border-surface-700 bg-surface-800 px-3 font-sans text-sm font-semibold text-surface-200 transition-colors hover:bg-surface-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-400"
          >
            {fullscreen ? <Minimize2 className="h-4 w-4" aria-hidden="true" /> : <Maximize2 className="h-4 w-4" aria-hidden="true" />}
            <span>{t(fullscreen ? "ca_dossier_reducir" : "ca_dossier_expandir")}</span>
          </button>
          <button
            type="button"
            onClick={refresh}
            disabled={loading}
            className="flex h-11 items-center gap-2 whitespace-nowrap rounded bg-surface-800 px-3 font-sans text-sm font-semibold text-surface-200 transition-colors hover:bg-surface-700 hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-400 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {loading ? (
              <Loader2 className="h-3 w-3 animate-spin" aria-hidden="true" />
            ) : (
              <RefreshCw className="h-3 w-3" aria-hidden="true" />
            )}
            <span>{t("ca_dossier_update")}</span>
          </button>

          <button
            type="button"
            onClick={downloadPdf}
            disabled={!pdfBlob}
            className="flex h-11 items-center gap-2 whitespace-nowrap rounded bg-surface-800 px-3 font-sans text-sm font-semibold text-surface-200 transition-colors hover:bg-brand-500 hover:text-surface-950 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-400 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Download className="h-3 w-3" aria-hidden="true" />
            <span>{t("z_descargar_pdf")}</span>
          </button>

          <button
            type="button"
            onClick={exportPackage}
            disabled={packaging}
            className="flex h-11 items-center gap-2 whitespace-nowrap rounded bg-surface-800 px-3 font-sans text-sm font-semibold text-surface-200 transition-colors hover:bg-brand-500 hover:text-surface-950 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-400 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {packaging ? (
              <Loader2 className="h-3 w-3 animate-spin" aria-hidden="true" />
            ) : (
              <FileArchive className="h-3 w-3" aria-hidden="true" />
            )}
            <span>{packaging ? t("auto_60b6d132c62d") : t("c_exportar_zip")}</span>
          </button>
        </div>
      </div>

      {/* El paquete se descargó. Eso es TODO lo que se afirma: quien lo reciba
          verifica los hashes con el manifiesto que viaja dentro. */}
      {packageSaved && (
        <p
          role="status"
          className="border-b border-surface-800 bg-surface-900/60 px-4 py-2 text-sm leading-6 text-zinc-400"
        >
          {t("ca_dossier_descargado")} <code className="font-mono text-zinc-300">{packageSaved}</code>{t("ca_dossier_manifiesto")}
        </p>
      )}

      {packageError && (
        <p
          role="alert"
          className="border-b border-red-500/20 bg-red-500/5 px-4 py-2 text-sm leading-6 text-red-300"
        >
          {t("auto_96129f3bbb7a")} {packageError}
        </p>
      )}

      {/* ── Cuerpo ───────────────────────────────────────────────────── */}
      <div className="relative min-h-0 flex-1 bg-surface-950">
        {loading && (
          <div
            role="status"
            className="absolute inset-0 flex flex-col items-center justify-center gap-3"
          >
            <Loader2 className="h-8 w-8 animate-spin text-brand-500" aria-hidden="true" />
            <span className="font-sans text-sm text-surface-400">
              {t("ca_dossier_generando")}
            </span>
          </div>
        )}

        {state === "error" && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 p-6 text-center">
            <AlertCircle className="h-10 w-10 text-red-400" aria-hidden="true" />
            <div className="font-bold text-red-400">{t("ca_dossier_fallo")}</div>
            <p role="alert" className="max-w-md text-sm leading-relaxed text-surface-400">
              {error}
            </p>
            <button
              type="button"
              onClick={refresh}
              className="mt-1 flex h-11 items-center gap-2 rounded bg-surface-800 px-4 font-sans text-sm font-semibold text-surface-200 transition-colors hover:bg-surface-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-400"
            >
              <RefreshCw className="h-3 w-3" aria-hidden="true" />
              {t("c_reintentar")}
            </button>
          </div>
        )}

        {state === "ready" && blobUrl && (
          <iframe
            src={`${blobUrl}#toolbar=0&view=FitH`}
            className="absolute inset-0 h-full w-full border-none bg-transparent"
            title={t("ca_dossier_caso")}
          />
        )}
      </div>
    </div>
  );
}

export default CaseDossierViewer;
