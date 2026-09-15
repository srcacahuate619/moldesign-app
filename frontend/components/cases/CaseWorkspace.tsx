"use client";

// =====================================================================
// CaseWorkspace — barra lateral persistente + la evaluación al centro
// =====================================================================
//
// Adopta el MODELO MENTAL de un espacio de trabajo persistente: los casos viven
// a la izquierda y sobreviven a la sesión; el centro es el caso abierto. No
// copia el aspecto de ningún producto concreto.
//
// EVALUATION-FIRST. La versión anterior recibía a cada caso con una botonera de
// siete secciones —Contexto · Sistema · Sitio · Ligandos · Evaluar · Evidencia
// · Informe— de las cuales cinco eran destinos inertes, y aterrizaba en un
// cuestionario de contexto. Eso enseña la arquitectura interna del producto y
// hace pasar por un peaje antes de dejar trabajar. Ahora:
//
//   · abrir o crear un caso lleva directamente a la EVALUACIÓN real;
//   · sólo hay dos modos, y el segundo —Informe— se REVELA cuando existe una
//     corrida completada cuyo `molecule_id` se ha recuperado de verdad;
//   · el contexto científico vive en «{t("ca_detalles")}», a un botón de
//     distancia, y no bloquea nada.
//
// CUATRO DECISIONES QUE NO SON COSMÉTICAS:
//
// 1. AISLAMIENTO. El runner se monta con `key={activeCase.id}`. Al cambiar de
//    caso React desmonta y remonta el subárbol entero, así que SMILES, receptor
//    y resultado no pueden filtrarse: no existe instancia compartida.
//
// 2. UN SOLO MONTAJE. El runner se monta UNA vez por caso y se conserva. En
//    Informe no se desmonta —se oculta— porque desmontarlo tiraría el polling
//    y la referencia al resultado que hace visible ese mismo informe.
//
// 3. PAUSA DE VIEWERS. Al ocultar la evaluación se baja `KeepAliveContext` a
//    `false`, que es el mismo mecanismo con que la app pausa Molstar al cambiar
//    de ruta. Ocultar con `hidden` sin bajar esa bandera dejaba el visor
//    renderizando.
//
// 4. ALTURA. La navegación global mide `h-14`; el workspace ocupa
//    `100dvh - 3.5rem`. Antes pedía `100dvh` y se salía por debajo del viewport.

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useLanguage } from "../../context/LanguageContext";
import dynamic from "next/dynamic";
import { AlertTriangle, FileText, SlidersHorizontal, X } from "lucide-react";

import { useCases } from "../../context/CaseContext";
import { KeepAliveContext, useKeepAliveActive } from "../../context/KeepAliveContext";
import {
  CASE_STATUS_LABELS,
  CASE_VIEW_LABELS,
  CASE_VIEWS,
  type CaseRecoveryAction,
  type CaseStudyKind,
  type CaseView,
  runMatchesInputs,
  structuralSystemIsSealed,
  type ReportableResult,
  type ReportRecoveryState,
} from "../../lib/cases/types";
import { CaseEmptyState } from "./CaseEmptyState";
import { CaseSidebar } from "./CaseSidebar";
import { CaseSidebarShell } from "./CaseSidebarShell";
import { CaseDetailsDrawer, describePendingDetails } from "./CaseDetailsDrawer";
import { CaseReportView } from "./CaseReportView";
import { CaseDispositionPanel } from "./CaseDispositionPanel";
import { CreateCaseDialog } from "./CreateCaseDialog";
import { EngineStatusBar } from "../EngineStatusBar";

// El historial de corridas se carga SÓLO al abrirlo: es un panel que no pinta
// nada mientras está cerrado y trae consigo el cliente del resultado.
const CaseRunHistoryModal = dynamic(() => import("./CaseRunHistoryModal"), { ssr: false });

const CaseEvaluationRunner = dynamic(() => import("../evaluation/CaseEvaluationRunner"), {
  ssr: false,
  loading: () => (
    <div className="flex h-full min-h-[24rem] items-center justify-center">
      <div className="h-8 w-8 animate-spin rounded-full border-2 border-surface-700 border-t-transparent" />
    </div>
  ),
});

/** Altura de la navegación global (`h-14` en `components/Navigation.tsx`). */
const NAV_HEIGHT = "3.5625rem";

const DETAILS_DRAWER_ID = "case-details-drawer";

function formatTimestamp(iso: string): string {
  const parsed = Date.parse(iso);
  if (Number.isNaN(parsed)) return "—";
  return new Date(parsed).toLocaleString();
}

export function CaseWorkspace() {
  const { t } = useLanguage();
  const {
    cases, activeCase, loading, error, saveState, hasLiveWork,
    repository, createCase, selectCase, updateContext, setActiveView, setArchived,
    forgetCase, relocateCase, openExistingFolder, initializeFolder, revealInFileManager,
    setLiveWork, setActiveRun, retrySave, dismissError,
    setInputs, setPreflight, recordDecision, setDisposition,
    repairCase, acceptRelocation, unregisteredRun, retryRegisterRun, registerRun,
  } = useCases();

  const [dialogOpen, setDialogOpen] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [runHistoryOpen, setRunHistoryOpen] = useState(false);
  /** Carpeta elegida sin `case.json`: token para autorizar, ruta para enseñar. */
  const [pendingFolder, setPendingFolder] = useState<
    { token: string; displayPath: string } | null
  >(null);
  /** El caso ya estaba registrado en otra carpeta: decisión explícita. */
  const [relocationConflict, setRelocationConflict] = useState<
    {
      token: string;
      displayPath: string;
      registeredPath: string;
      name: string;
      /** Id que se espera encontrar. Rust lo verifica antes de registrar. */
      caseId: string;
    } | null
  >(null);

  /**
   * Referencia al resultado publicable, ETIQUETADA CON SU CASO.
   *
   * El caso al que pertenece viaja junto al dato a propósito. Sin esa etiqueta,
   * cambiar de caso dejaba visible el «Informe» del anterior durante el hueco
   * entre el cambio y el primer aviso del runner nuevo — el informe de otro
   * caso, con el `molecule_id` de otro caso.
   */
  const [reportRef, setReportRef] = useState<
    { caseId: string; result: ReportableResult } | null
  >(null);
  const [recoveryRef, setRecoveryRef] = useState<
    { caseId: string; state: ReportRecoveryState } | null
  >(null);

  const capabilities = repository.capabilities;
  const requiresDirectory = repository.id === "tauri";
  // La visibilidad de la RUTA la provee el keep-alive de la app; aquí se
  // combina con la del MODO para pausar los viewers con precisión.
  const routeActive = useKeepAliveActive();

  const activeCaseId = activeCase?.id ?? null;
  const reportable = reportRef && reportRef.caseId === activeCaseId ? reportRef.result : null;
  const recoveryState: ReportRecoveryState =
    recoveryRef && recoveryRef.caseId === activeCaseId ? recoveryRef.state : "idle";

  const handleReportableChange = useCallback(
    (result: ReportableResult | null) => {
      const caseId = activeCaseId;
      if (!caseId) return;
      setReportRef(result ? { caseId, result } : null);
    },
    [activeCaseId],
  );

  const handleRecoveryChange = useCallback(
    (state: ReportRecoveryState) => {
      const caseId = activeCaseId;
      if (!caseId) return;
      setRecoveryRef({ caseId, state });
    },
    [activeCaseId],
  );

  /**
   * El modo VISIBLE se deriva; el guardado sólo expresa una preferencia.
   *
   * «Informe» no se muestra por el hecho de estar guardado: se muestra si hay
   * un resultado recuperado. Así, reabrir un caso que se cerró en Informe
   * restaura esa vista en cuanto la recuperación funciona —el usuario la había
   * abierto deliberadamente— y no la restaura nunca en falso.
   */
  const view: CaseView = activeCase?.activeView === "report" && reportable ? "report" : "evaluation";

  /**
   * Relación entre la corrida guardada y los inputs de ahora.
   *
   * Se calcula aquí, una vez, y viaja tanto a la llamada de «Abrir informe»
   * como a la vista del informe: las dos tienen que decir lo mismo.
   */
  const relationRun =
    activeCase?.activeRun &&
    !activeCase.activeRun.inputFingerprint &&
    activeCase.structuralSystem?.sourceRunTaskId === activeCase.activeRun.taskId
      ? {
          ...activeCase.activeRun,
          inputFingerprint: activeCase.structuralSystem.inputFingerprint,
        }
      : activeCase?.activeRun;
  const runRelation = runMatchesInputs(
    relationRun,
    activeCase?.preflight?.fingerprint ?? null,
  );

  /**
   * Una corrida NUEVA cierra el informe anterior.
   *
   * Sin esto, el destino guardado seguiría siendo «Informe» y terminar la
   * siguiente evaluación habría producido un salto automático que nadie pidió.
   * Mientras la recuperación está en curso no se toca: sería deshacer justo la
   * restauración legítima.
   */
  useEffect(() => {
    if (!activeCase || activeCase.activeView !== "report") return;
    // Un resultado ya anunciado —tanto en una corrida viva como recuperada—
    // hace que Informe sea un destino real, aunque el mock/runner antiguo no
    // haya persistido todavía `activeRun`.
    if (reportable) return;
    // Una corrida COMPLETADA todavía puede recuperar su `molecule_id`. No se
    // degrada la preferencia a Evaluación durante el primer render: los efectos
    // del runner aún no han tenido oportunidad de anunciar `recovering`. Si se
    // escribiera aquí, cerrar un caso en Informe nunca sobreviviría realmente a
    // una reapertura aunque el resultado siguiera disponible.
    //
    // En cambio, empezar/reanudar una corrida no terminal sí invalida la
    // preferencia anterior: cuando esa corrida termine se ofrecerá el informe
    // nuevo, sin saltar automáticamente a él.
    if (
      activeCase.activeRun?.executionState === "completed" &&
      (recoveryState === "idle" || recoveryState === "recovering")
    ) {
      return;
    }
    setActiveView("evaluation");
  }, [activeCase, recoveryState, reportable, setActiveView]);

  const drawerRef = useRef<HTMLDivElement | null>(null);
  const drawerOpenerRef = useRef<HTMLElement | null>(null);

  const handleCreate = useCallback(
    async (name: string, studyKind: CaseStudyKind, parentDirectory?: string): Promise<boolean> => {
      // `createCase` devuelve `null` si el guardado pendiente no se pudo
      // drenar. El diálogo NO debe cerrarse entonces: un drenaje fallido que
      // cerrara el diálogo se vería igual que una creación correcta.
      const record = await createCase(name, studyKind, parentDirectory);
      if (!record) return false;
      setSidebarOpen(false);
      return true;
    },
    [createCase],
  );

  const handleOpenFolder = useCallback(async () => {
    const outcome = await openExistingFolder();
    if (outcome.kind === "empty") {
      // NO se importa en silencio: se pide una decisión explícita.
      setPendingFolder({ token: outcome.token, displayPath: outcome.displayPath });
    } else if (outcome.kind === "conflict") {
      // Tampoco se re-mapea en silencio: el usuario estaría editando una copia
      // creyendo que edita el original.
      setRelocationConflict({
        token: outcome.token,
        displayPath: outcome.displayPath,
        registeredPath: outcome.registeredPath,
        name: outcome.record.name,
        caseId: outcome.record.id,
      });
    }
  }, [openExistingFolder]);

  /**
   * Elige la carpeta CONTENEDORA para un caso nuevo.
   *
   * Devuelve token y ruta POR SEPARADO. Antes reutilizaba `openExistingFolder`
   * y devolvía una sola cadena, así que el diálogo acababa enseñando el UUID
   * del token donde debía ir la ubicación.
   */
  const pickParentDirectory = useCallback(async () => {
    if (!repository.pickParentDirectory) return null;
    return repository.pickParentDirectory();
  }, [repository]);

  const handleSelect = useCallback(
    (id: string) => {
      void selectCase(id);
      setSidebarOpen(false);
      setDetailsOpen(false);
    },
    [selectCase],
  );

  const handleRecover = useCallback(
    (id: string, action: CaseRecoveryAction) => {
      if (action === "forget") void forgetCase(id);
      else if (action === "relocate") void relocateCase(id);
      // Reparar es restaurar ESE caso desde su copia, no reintentar el guardado
      // del caso activo, que es otro caso distinto.
      else if (action === "repair") void repairCase(id);
    },
    [forgetCase, relocateCase, repairCase],
  );

  // ── Drawer móvil de casos: foco atrapado, Escape y retorno de foco ──
  useEffect(() => {
    if (!sidebarOpen) {
      drawerOpenerRef.current?.focus?.();
      drawerOpenerRef.current = null;
      return;
    }
    drawerOpenerRef.current = (document.activeElement as HTMLElement) ?? null;
    const root = drawerRef.current;
    const first = root?.querySelector<HTMLElement>(
      'button:not([disabled]), input:not([disabled]), [href], [tabindex]:not([tabindex="-1"])',
    );
    first?.focus();

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.stopPropagation();
        setSidebarOpen(false);
        return;
      }
      if (event.key !== "Tab" || !drawerRef.current) return;
      const items = Array.from(
        drawerRef.current.querySelectorAll<HTMLElement>(
          'button:not([disabled]), input:not([disabled]), [href], [tabindex]:not([tabindex="-1"])',
        ),
      );
      if (items.length === 0) return;
      const firstItem = items[0];
      const lastItem = items[items.length - 1];
      if (event.shiftKey && document.activeElement === firstItem) {
        event.preventDefault();
        lastItem.focus();
      } else if (!event.shiftKey && document.activeElement === lastItem) {
        event.preventDefault();
        firstItem.focus();
      }
    };
    document.addEventListener("keydown", onKeyDown, true);
    return () => document.removeEventListener("keydown", onKeyDown, true);
  }, [sidebarOpen]);

  const workLockedReason = hasLiveWork
    ? "Hay trabajo en curso en este caso. Espera a que termine o cancélalo para cambiar de caso."
    : undefined;

  /**
   * `onCollapse` sólo existe en escritorio: en el cajón móvil el panel ya se
   * cierra con su propia X, y ofrecer dos formas de cerrarlo en el mismo sitio
   * no ayuda a nadie.
   */
  const renderSidebar = (onCollapse?: () => void) => (
    <CaseSidebar
      cases={cases}
      activeCaseId={activeCase?.id ?? null}
      loading={loading}
      onSelect={handleSelect}
      onCreate={() => setDialogOpen(true)}
      onArchive={(id, archived) => void setArchived(id, archived)}
      onReveal={capabilities.canRevealInFileManager ? (id) => void revealInFileManager(id) : undefined}
      onRecover={handleRecover}
      canReveal={capabilities.canRevealInFileManager}
      workLocked={hasLiveWork}
      workLockedReason={workLockedReason}
      onCollapse={onCollapse}
    />
  );
  const sidebar = renderSidebar();

  const evaluationVisible = view === "evaluation";
  const evaluationKeepAlive = useMemo(
    () => routeActive && evaluationVisible,
    [routeActive, evaluationVisible],
  );

  /**
   * El caso guardó una corrida completada pero su resultado no volvió.
   *
   * Se dice en Evaluación, que es donde se aterriza. La alternativa —abrir un
   * «Informe» vacío para explicar que no hay informe— presenta como destino
   * algo que no existe.
   */
  const reportUnrecoverable =
    recoveryState === "unrecoverable" &&
    !reportable &&
    activeCase?.activeRun?.executionState === "completed";
  const activeRunPendingRegistration = Boolean(
    activeCase?.activeRun && unregisteredRun?.taskId === activeCase.activeRun.taskId,
  );

  return (
    <div
      className="flex min-h-0 w-full flex-col overflow-hidden bg-surface-950 text-zinc-200 lg:flex-row"
      style={{ height: `calc(100dvh - ${NAV_HEIGHT})` }}
    >
      {/* El panel de casos se pliega a un raíl y se redimensiona; las dos
          preferencias se recuerdan. Ver `CaseSidebarShell` para el porqué. */}
      <CaseSidebarShell
        totalCasos={cases.length}
        onCreate={() => setDialogOpen(true)}
        createDisabled={hasLiveWork}
        createDisabledReason={workLockedReason}
      >
        {({ plegar }) => renderSidebar(plegar)}
      </CaseSidebarShell>

      <div className="flex items-center justify-between gap-2 border-b border-surface-800 px-3 py-2 lg:hidden">
        <button
          type="button"
          onClick={() => setSidebarOpen(true)}
          aria-expanded={sidebarOpen}
          aria-controls="case-sidebar-drawer"
          aria-haspopup="dialog"
          className="whitespace-nowrap rounded-md border border-surface-700 px-2.5 py-1 text-xs text-zinc-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400"
        >
          Casos
        </button>
        <span className="min-w-0 truncate text-xs text-zinc-500">
          {activeCase ? activeCase.name : t("auto_17ecdaf55d49")}
        </span>
      </div>

      {sidebarOpen && (
        <div className="fixed inset-0 z-40 flex lg:hidden">
          <div
            className="absolute inset-0 bg-black/60"
            onClick={() => setSidebarOpen(false)}
            aria-hidden="true"
          />
          <div
            id="case-sidebar-drawer"
            ref={drawerRef}
            role="dialog"
            aria-modal="true"
            aria-label="Casos"
            className="relative z-10 flex w-[85vw] max-w-[300px]"
          >
            <div className="min-w-0 flex-1">{sidebar}</div>
            <button
              type="button"
              onClick={() => setSidebarOpen(false)}
              aria-label={t("ca_cerrar_panel")}
              className="absolute right-1 top-1 rounded p-1.5 text-zinc-500 hover:text-zinc-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400"
            >
              <X className="h-4 w-4" aria-hidden="true" />
            </button>
          </div>
        </div>
      )}

      <main className="flex min-h-0 min-w-0 flex-1 flex-col">
        {/* Estado del motor de cálculo. Sólo aparece cuando hay algo que decir:
            arrancando, no instalado, o caído con su razón y su reintento. */}
        <EngineStatusBar />

        {error && (
          <div
            role="alert"
            className="flex items-start gap-2 border-b border-amber-500/30 bg-amber-500/10 px-4 py-2 text-xs leading-relaxed text-amber-200"
          >
            <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
            <span className="min-w-0 flex-1">{error}</span>
            {saveState === "error" && (
              <button
                type="button"
                onClick={() => void retrySave()}
                className="shrink-0 whitespace-nowrap rounded border border-amber-500/40 px-2 py-0.5 text-[11px] hover:text-amber-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400"
              >
                {t("c_reintentar")}
              </button>
            )}
            <button
              type="button"
              onClick={dismissError}
              aria-label="Descartar aviso"
              className="shrink-0 rounded p-0.5 hover:text-amber-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400"
            >
              <X className="h-3.5 w-3.5" aria-hidden="true" />
            </button>
          </div>
        )}

        {/* Corrida cuyo identificador NO llegó a disco. Lo único que impide
            perder la tarea es este bloque: se puede reintentar o copiar. */}
        {unregisteredRun && (
          <div
            role="alert"
            className="flex flex-wrap items-center gap-2 border-b border-red-500/30 bg-red-500/10 px-4 py-2 text-xs leading-relaxed text-red-200"
          >
            <span className="min-w-0 flex-1">
              {t("ca_corrida_arranco")} <strong>{t("ca_id_no_guardado")}</strong>{t("auto_d970f808cba3")}{" "}
              <code className="break-all font-mono">{unregisteredRun.taskId}</code>
            </span>
            <button
              type="button"
              onClick={() => void retryRegisterRun()}
              className="shrink-0 whitespace-nowrap rounded border border-red-500/40 px-2 py-0.5 text-[11px] hover:text-red-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-400"
            >
              Reintentar guardado
            </button>
            <button
              type="button"
              onClick={() => void navigator.clipboard?.writeText(unregisteredRun.taskId)}
              className="shrink-0 whitespace-nowrap rounded border border-red-500/40 px-2 py-0.5 text-[11px] hover:text-red-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-400"
            >
              Copiar identificador
            </button>
          </div>
        )}

        {activeCase?.activeRun && (
          <p className="border-b border-surface-800 bg-surface-900 px-4 py-1.5 font-mono text-[11px] text-zinc-400">
            {activeRunPendingRegistration ? t("auto_262949a66911") : "Corrida registrada"}{" "}
            {activeCase.activeRun.taskId.slice(0, 12)}… ·{" "}
            {{
              idle: "preparada",
              submitted: "enviada",
              running: "en curso",
              interrupted: "seguimiento interrumpido",
              completed: "completada",
              failed: "fallida",
              cancelled: "cancelada",
            }[activeCase.activeRun.executionState]}
          </p>
        )}

        {relocationConflict && (
          <div
            role="alertdialog"
            aria-label={t("ca_ya_registrado")}
            className="border-b border-amber-500/30 bg-amber-500/10 px-4 py-3 text-xs leading-relaxed text-amber-100"
          >
            <p>
              <strong>{relocationConflict.name}</strong> {t("auto_72ef951a4533")}{" "}
              <span className="break-all font-mono">{relocationConflict.registeredPath}</span>{t("auto_cc3fb7ae5b1e")}{" "}
              <span className="break-all font-mono">{relocationConflict.displayPath}</span>{t("ca_nada_cambiado")}
            </p>
            <div className="mt-2 flex flex-wrap gap-2">
              <button
                type="button"
                onClick={async () => {
                  const { token, caseId } = relocationConflict;
                  setRelocationConflict(null);
                  // Se dice QUÉ caso se espera: Rust lo verifica contra el
                  // manifiesto antes de mover nada.
                  await acceptRelocation(token, caseId);
                }}
                className="rounded-md border border-amber-500/40 px-3 py-1 text-xs hover:text-amber-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400"
              >
                {t("ca_usar_carpeta_nueva")}
              </button>
              <button
                type="button"
                onClick={() => setRelocationConflict(null)}
                className="rounded-md border border-surface-700 px-3 py-1 text-xs text-zinc-300 hover:text-zinc-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400"
              >
                {t("c_cancelar")}
              </button>
            </div>
          </div>
        )}

        {pendingFolder && (
          <div
            role="alertdialog"
            aria-label={t("ca_carpeta_sin_caso")}
            className="border-b border-surface-700 bg-surface-900 px-4 py-3 text-xs leading-relaxed text-zinc-300"
          >
            <p>
              {t("auto_222f750aceb4")}{" "}
              <span className="break-all font-mono text-zinc-400">{pendingFolder.displayPath}</span>{" "}
              {t("auto_1e6cb1e6dc11")} <code className="font-mono">case.json</code>{t("ca_no_se_importa_solo")}
            </p>
            <div className="mt-2 flex flex-wrap gap-2">
              <button
                type="button"
                onClick={async () => {
                  const { token, displayPath } = pendingFolder;
                  setPendingFolder(null);
                  // El nombre por defecto sale de la carpeta REAL, no del token.
                  const suggested = displayPath.split(/[\\/]/).pop() || "Caso nuevo";
                  await initializeFolder(token, suggested, "explore-hypothesis");
                }}
                className="rounded-md border border-brand-500/40 bg-brand-600 px-3 py-1 text-xs font-medium text-white hover:bg-brand-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400"
              >
                {t("ca_inicializar_como_caso")}
              </button>
              <button
                type="button"
                onClick={() => setPendingFolder(null)}
                className="rounded-md border border-surface-700 px-3 py-1 text-xs text-zinc-300 hover:text-zinc-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400"
              >
                {t("c_cancelar")}
              </button>
            </div>
          </div>
        )}

        {!activeCase ? (
          <CaseEmptyState
            onCreate={() => setDialogOpen(true)}
            onOpenFolder={() => void handleOpenFolder()}
            canOpenFolder={capabilities.canOpenFolder && !hasLiveWork}
            openFolderUnavailableReason={
              hasLiveWork ? workLockedReason : capabilities.openFolderUnavailableReason
            }
            storageLabel={capabilities.storageLabel}
            createDisabled={hasLiveWork}
            createDisabledReason={workLockedReason}
          />
        ) : (
          <>
            {/* ── El scroll empieza AQUÍ, antes de la cabecera ──────────
                Antes la cabecera era hermana del contenedor que scrollea, así
                que sus 94 px —medidos a 1440×900— no se iban nunca de la
                pantalla. Ahora scrollea con el contenido y sólo se queda
                anclada la tira de pestañas, que es el control que hace falta
                tener a mano; la identidad del caso se puede volver a ver
                subiendo, que es lo que uno hace cuando quiere leerla. */}
            <div className="evaluation-scrollbar min-h-0 flex-1 overflow-y-auto overscroll-contain">
            <header className="border-b border-surface-800 px-4 py-3 sm:px-6">
              <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                    <h1 className="min-w-0 truncate text-base font-semibold tracking-tight text-zinc-100">
                      {activeCase.name}
                    </h1>
                    <span className="whitespace-nowrap rounded border border-surface-700 px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-wider text-zinc-400">
                      {CASE_STATUS_LABELS[activeCase.status]}
                    </span>
                  </div>
                  <dl className="mt-1.5 flex flex-wrap gap-x-5 gap-y-1 font-mono text-[11px] text-zinc-500">
                    <div className="flex min-w-0 gap-1.5">
                      <dt className="sr-only">Almacenamiento</dt>
                      <dd className="min-w-0 truncate">
                        {activeCase.storage.mode === "folder"
                          ? activeCase.storage.path
                          : activeCase.storage.label}
                      </dd>
                    </div>
                    <div className="flex gap-1.5">
                      <dt>{t("auto_5dfeeb357031")}</dt>
                      <dd>{formatTimestamp(activeCase.updatedAt)}</dd>
                    </div>
                  </dl>
                </div>

                {/* Botón secundario y discreto. El recuento acompaña, no alarma:
                    ningún detalle pendiente impide ejecutar. */}
                <button
                  type="button"
                  onClick={() => setDetailsOpen((open) => !open)}
                  aria-expanded={detailsOpen}
                  aria-controls={DETAILS_DRAWER_ID}
                  aria-haspopup="dialog"
                  aria-label={t("ca_detalles_con_pendientes", { pendientes: describePendingDetails(activeCase.context) })}
                  className="inline-flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-md border border-surface-700 px-2.5 py-1 text-xs text-zinc-300 transition-colors hover:border-surface-600 hover:text-zinc-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400"
                >
                  <SlidersHorizontal className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                  <span className="sm:hidden">Detalles</span>
                  <span className="hidden sm:inline">{t("ca_detalles")}</span>
                </button>
              </div>

              <p className="mt-1.5 font-mono text-[10px] text-zinc-500 sm:text-right">
                {describePendingDetails(activeCase.context)}
              </p>

            </header>

            {/* La botonera SÓLO existe cuando hay dos destinos reales. Un
                único modo no necesita conmutador, y un conmutador con un
                destino deshabilitado prometería algo que todavía no hay.

                Y es lo ÚNICO que se queda anclado al desplazarse: cambiar de
                Evaluación a Informe tiene que estar siempre a un clic, pero
                la ficha del caso no necesita ocupar sitio mientras se trabaja.
                Cuando no hay informe no se ancla nada y se recupera la altura
                entera. */}
            {reportable && (
              <div className="sticky top-0 z-20 border-b border-surface-800 bg-surface-950/95 px-4 py-2 backdrop-blur sm:px-6">
                <div className="inline-flex rounded-lg border border-surface-700 bg-surface-950 p-1 shadow-inner" role="tablist" aria-label={t("ca_modo_del_caso")}>
                  {CASE_VIEWS.map((mode) => {
                    const selected = view === mode;
                    return (
                      <button
                        key={mode}
                        type="button"
                        role="tab"
                        aria-selected={selected}
                        // El panel del informe sólo existe cuando está
                        // seleccionado, así que sólo entonces se apunta a él:
                        // un `aria-controls` a un id inexistente le miente al
                        // lector de pantalla.
                        aria-controls={
                          mode === "evaluation" || selected ? `case-panel-${mode}` : undefined
                        }
                        id={`case-tab-${mode}`}
                        tabIndex={selected ? 0 : -1}
                        onClick={() => setActiveView(mode)}
                        onKeyDown={(event) => {
                          const current = CASE_VIEWS.indexOf(mode);
                          let next: number | null = null;
                          if (event.key === "ArrowRight") next = (current + 1) % CASE_VIEWS.length;
                          else if (event.key === "ArrowLeft") next = (current - 1 + CASE_VIEWS.length) % CASE_VIEWS.length;
                          else if (event.key === "Home") next = 0;
                          else if (event.key === "End") next = CASE_VIEWS.length - 1;
                          if (next === null) return;
                          event.preventDefault();
                          const nextMode = CASE_VIEWS[next];
                          setActiveView(nextMode);
                          document.getElementById(`case-tab-${nextMode}`)?.focus();
                        }}
                        className={`min-h-9 min-w-[7rem] whitespace-nowrap rounded-md border border-transparent px-3 py-1.5 font-mono text-[11px] font-bold uppercase tracking-[0.08em] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400 ${
                          selected
                            ? "border-brand-500/35 bg-brand-500/15 text-zinc-100 shadow-sm"
                            : "text-zinc-400 hover:bg-white/[0.04] hover:text-zinc-200"
                        }`}
                      >
                        {CASE_VIEW_LABELS[mode]}
                      </button>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Llamada explícita, NO navegación automática. Terminar un cálculo
                no autoriza a mover al usuario de pantalla: se le ofrece. */}
            {reportable && view === "evaluation" && (
              <div className="flex flex-wrap items-center gap-2 border-b border-surface-800 bg-surface-900 px-4 py-2 text-xs leading-relaxed text-zinc-300 sm:px-6">
                <FileText className="h-3.5 w-3.5 shrink-0 text-brand-400" aria-hidden="true" />
                <span className="min-w-0 flex-1">
                  {runRelation === "corresponde"
                    ? t("auto_5dc69e1ba19b")
                    : runRelation === "corrida_anterior"
                      ? t("auto_7f0c5ddda6e9")
                      : t("auto_b3945ccefff7")}
                </span>
                <button
                  type="button"
                  onClick={() => setActiveView("report")}
                  className="shrink-0 whitespace-nowrap rounded-md border border-brand-500/40 bg-brand-600 px-3 py-1 text-xs font-medium text-white transition-colors hover:bg-brand-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400"
                >
                  Abrir informe
                </button>
              </div>
            )}

            {reportUnrecoverable && (
              <p
                role="status"
                className="border-b border-amber-500/30 bg-amber-500/10 px-4 py-2 text-xs leading-relaxed text-amber-200 sm:px-6"
              >
                {t("auto_265b259a1293")}{" "}
                <strong>{t("ca_resultado_no_recuperado")}</strong>{t("auto_99b5f43f6422")}{" "}
                <code className="break-all font-mono">{activeCase.activeRun?.taskId}</code>
              </p>
            )}


            {/* NO hay un seguidor de corrida aparte. Lo hubo mientras el
                runner se montaba de forma perezosa —un caso reabierto en
                Contexto no seguía a nadie—, pero ahora el runner se monta con
                el caso y él mismo reanuda el polling desde el primer instante.
                Mantener además `CaseRunTracker` montado significaría dos
                seguidores escribiendo la misma corrida. */}

            {/* El scroll ya lo lleva el contenedor de arriba, que empieza
                antes de la cabecera. Este envoltorio sólo agrupa los dos
                paneles; `min-h-0` conserva el comportamiento de flex que
                tenía cuando era él quien scrolleaba. */}
            <div className="min-h-0 flex-1">
              <div
                id="case-panel-evaluation"
                role={reportable ? "tabpanel" : undefined}
                aria-labelledby={reportable ? "case-tab-evaluation" : undefined}
                hidden={!evaluationVisible}
                className="h-full"
              >
                {/* `KeepAliveContext` en false pausa Molstar y demás viewers
                    mientras el modo está oculto, sin desmontar nada. */}
                <KeepAliveContext.Provider value={evaluationKeepAlive}>
                  <CaseEvaluationRunner
                    key={activeCase.id}
                    caseId={activeCase.id}
                    activeRun={activeCase.activeRun}
                    onLiveWorkChange={setLiveWork}
                    onActiveRunChange={setActiveRun}
                    onRunRegistered={registerRun}
                    onReportableChange={handleReportableChange}
                    onReportRecoveryChange={handleRecoveryChange}
                    inputs={activeCase.inputs}
                    structuralSystem={activeCase.structuralSystem}
                    structuralSystemSealed={structuralSystemIsSealed(activeCase)}
                    runCount={activeCase.runs.length}
                    onOpenRunHistory={() => setRunHistoryOpen(true)}
                    onInputsChange={setInputs}
                    preflight={activeCase.preflight}
                    onPreflightChange={setPreflight}
                    decisions={activeCase.decisions}
                    onDecision={recordDecision}
                  />
                </KeepAliveContext.Provider>
              </div>

              {/* El panel del informe se MONTA sólo al abrirlo, al revés que
                  el runner. Montarlo oculto pediría el dossier al backend en
                  cuanto termina una corrida —generando el PDF sin que nadie lo
                  haya pedido—, y desmontarlo no cuesta nada: no guarda estado
                  vivo, sólo pinta el resultado. */}
              {reportable && view === "report" && (
                <div
                  id="case-panel-report"
                  role="tabpanel"
                  aria-labelledby="case-tab-report"
                >
                  {activeCase.activeRun?.executionState === "completed" && (
                    <CaseDispositionPanel
                      disposition={activeCase.disposition}
                      runRelation={runRelation}
                      onSubmit={setDisposition}
                    />
                  )}
                  {/* El caso ENTERO, no un extracto: la proyección que pide el
                      dossier necesita inputs, preflight, decisiones y corrida.
                      Pasar sólo nombre y contexto obligaría a reconstruirlo a
                      trozos justo donde importa que sea fiel. */}
                  <CaseReportView
                    caseRecord={activeCase}
                    reportable={reportable}
                    runRelation={runRelation}
                    onBackToEvaluation={() => setActiveView("evaluation")}
                  />
                </div>
              )}
            </div>
            </div>
          </>
        )}
      </main>

      {activeCase && (
        <CaseDetailsDrawer
          id={DETAILS_DRAWER_ID}
          open={detailsOpen}
          onClose={() => setDetailsOpen(false)}
          context={activeCase.context}
          saveState={saveState}
          onChange={updateContext}
          onRetry={retrySave}
        />
      )}

      {activeCase && runHistoryOpen && (
        <CaseRunHistoryModal
          runs={activeCase.runs}
          structuralSystem={activeCase.structuralSystem}
          currentFingerprint={activeCase.preflight?.fingerprint ?? null}
          activeTaskId={activeCase.activeRun?.taskId}
          onClose={() => setRunHistoryOpen(false)}
        />
      )}

      <CreateCaseDialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        onCreate={handleCreate}
        requiresDirectory={requiresDirectory}
        storageLabel={capabilities.storageLabel}
        onPickDirectory={requiresDirectory ? pickParentDirectory : undefined}
      />
    </div>
  );
}

export default CaseWorkspace;
