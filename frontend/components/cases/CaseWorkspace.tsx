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
//   - el contexto de investigacion acompana al dossier y, antes de tener
//     resultados, queda disponible en una seccion desplegable de Evaluacion.
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
import { etapaDeEvaluacionChat, marcarEtapaDeEvaluacionChat } from "../../lib/evaluacionDesdeChat";
import resultStyles from "../interfaces/pro/ResultPanels.module.css";
import dynamic from "next/dynamic";
import { AlertTriangle, ArrowLeft, ChevronDown, FileText, X } from "lucide-react";

import { useCases } from "../../context/CaseContext";
import { registerNativeJobDestinationResolver } from "../../lib/nativeJobNotifications";
import { KeepAliveContext, useKeepAliveActive } from "../../context/KeepAliveContext";
import {
  CaseError,
  type CaseRecoveryAction,
  type CaseStudyKind,
  type CaseView,
  relacionDeLaCorridaActiva,
  structuralSystemIsSealed,
  type ReportableResult,
  type ReportRecoveryState,
} from "../../lib/cases/types";
import { caseViewLabel, displayCasePath, localizeCaseStorageLabel } from "../../lib/cases/uiLabels";
import { escucharPeticionesDeEvaluacion, type PeticionRecibida } from "../../lib/peticionDeEvaluacion";
import { currentEditorReader, waitEditorReader } from "../../lib/editorSnapshot";
import { CaseEmptyState } from "./CaseEmptyState";
import { CaseSidebar } from "./CaseSidebar";
import { CaseSidebarShell } from "./CaseSidebarShell";
import { describePendingDetails } from "./caseContextLabels";
import { CaseReportView } from "./CaseReportView";
import { CaseContextPanel } from "./CaseContextPanel";
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

function formatTimestamp(iso: string, locale: string): string {
  const parsed = Date.parse(iso);
  if (Number.isNaN(parsed)) return "—";
  return new Date(parsed).toLocaleString(locale);
}

export function CaseWorkspace() {
  const { t, locale } = useLanguage();
  const {
    ownerUserId, cases, activeCase, loading, error, saveState, hasLiveWork,
    repository, createCase, selectCase, updateContext, setActiveView, setArchived,
    forgetCase, relocateCase, openExistingFolder, initializeFolder, revealInFileManager,
    setLiveWork, setActiveRun, retrySave, dismissError,
    setInputs, setPreflight, recordDecision, setDisposition,
    repairCase, acceptRelocation, unregisteredRun, retryRegisterRun, registerRun,
  } = useCases();
  const [dialogOpen, setDialogOpen] = useState(false);
  const creandoDesdeChat = useRef(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [runHistoryOpen, setRunHistoryOpen] = useState(false);
  const navigationState = useRef({ ownerUserId, activeCase, hasLiveWork });
  navigationState.current = { ownerUserId, activeCase, hasLiveWork };
  const cargandoSmiles = useRef(false);
  const [smilesDesdeChat, setSmilesDesdeChat] = useState<{ requestId: string; caseId: string; smiles: string; deadline: number; onApplied: () => void } | null>(null);
  const asignandoReceptor = useRef(false);
  const [receptorDesdeChat, setReceptorDesdeChat] = useState<{ requestId: string; caseId: string; pdbId: string; deadline: number; onVisible: (already: boolean) => void; onError: (status: string) => void } | null>(null);
  const [receptorConfirmacion, setReceptorConfirmacion] = useState<{ caseId: string; owner: string; pdbId: string; already: boolean; finish: (status: string) => void } | null>(null);
  const evaluandoDesdeChat = useRef(false);
  const [evaluacionDesdeChat, setEvaluacionDesdeChat] = useState<{ requestId: string; caseId: string; deadline: number; onResult: (result: { status: string; task_id?: string; reason?: string }) => void } | null>(null);
  const nativeSequence = useRef(0);
  const pendingNative = useRef<{ caseId: string; taskId: string; sequence: number;
    resolve: (opened: boolean) => void; timer: ReturnType<typeof setTimeout> } | null>(null);
  const [nativeSelection, setNativeSelection] = useState<{ caseId: string; taskId: string; sequence: number } | null>(null);
  const settleNative = useCallback((opened: boolean) => {
    const pending = pendingNative.current;
    if (!pending) return;
    pendingNative.current = null;
    clearTimeout(pending.timer);
    pending.resolve(opened);
  }, []);
  const requestedRunSelected = useCallback((taskId: string) => {
    const pending = pendingNative.current;
    if (pending?.taskId === taskId && navigationState.current.activeCase?.id === pending.caseId) settleNative(true);
  }, [settleNative]);
  const closeRunHistory = useCallback(() => {
    nativeSequence.current += 1;
    settleNative(false);
    setNativeSelection(null);
    setRunHistoryOpen(false);
  }, [settleNative]);
  useEffect(() => {
    const unregister = registerNativeJobDestinationResolver("evaluation", async destination => {
      const sequence = ++nativeSequence.current;
      settleNative(false);
      const state = navigationState.current;
      if (!state.ownerUserId || destination.ownerId !== state.ownerUserId || !destination.caseId || !destination.taskId) return false;
      let record;
      try { record = state.activeCase?.id === destination.caseId ? state.activeCase : await repository.readCase(destination.caseId); }
      catch { return false; }
      if (sequence !== nativeSequence.current || navigationState.current.ownerUserId !== destination.ownerId
        || record.ownerUserId !== destination.ownerId || !record.runs.some(run => run.taskId === destination.taskId)) return false;
      if (!(await selectCase(record.id)) || sequence !== nativeSequence.current
        || navigationState.current.ownerUserId !== destination.ownerId) return false;
      return new Promise<boolean>(resolve => {
        const selection = { caseId: record.id, taskId: destination.taskId!, sequence };
        pendingNative.current = { ...selection, resolve, timer: setTimeout(() => settleNative(false), 10000) };
        setNativeSelection(selection);
        setRunHistoryOpen(true);
        setActiveView("evaluation");
      });
    });
    return () => { unregister(); nativeSequence.current += 1; settleNative(false); };
  }, [repository, ownerUserId, selectCase, setActiveView, settleNative]);

  /**
   * Lo que pidió Preparación («vuelve a evaluar con este tautómero»). Sólo se entrega al runner de SU caso, y sólo si
   * ese caso llegó a abrirse: con trabajo vivo en otro, `selectCase` se niega y la petición se descarta en vez de
   * quedar esperando a que alguien abra ese caso más tarde.
   */
  const [peticion, setPeticion] = useState<PeticionRecibida | null>(null);
  useEffect(() => escucharPeticionesDeEvaluacion((recibida) => {
    void selectCase(recibida.casoId).then((abierto) => {
      if (!abierto) return;
      setPeticion(recibida);
      setActiveView("evaluation");
    });
  }), [selectCase, setActiveView]);
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
  const storageLabel = localizeCaseStorageLabel(repository, t);
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
   * Se calcula aquí, una vez, para la advertencia en Evaluación y la vista
   * del informe: las dos tienen que decir lo mismo.
   */
  const runRelation = activeCase ? relacionDeLaCorridaActiva(activeCase) : "desconocida";

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

  useEffect(() => {
    const recibir = (evento: Event) => {
      const detalle = (evento as CustomEvent<{
        name: string; owner: string; handled: boolean; respond: (status: "created" | "exists" | "failed" | "unknown") => void;
      }>).detail;
      if (!detalle || typeof detalle.name !== "string" || typeof detalle.respond !== "function") return;
      detalle.handled = true;
      if (detalle.owner !== ownerUserId) { detalle.respond("failed"); return; }
      if (creandoDesdeChat.current) { detalle.respond("failed"); return; }
      creandoDesdeChat.current = true;
      void (async () => {
        try {
          const normalizar = (name: string) => name.normalize("NFC").trim().toLocaleLowerCase();
          const existentes = await repository.listCases();
          if (existentes.some((caso) => normalizar(caso.name) === normalizar(detalle.name))) {
            detalle.respond("exists"); return;
          }
          const parent = requiresDirectory ? await repository.defaultParentDirectory?.() : null;
          if (requiresDirectory && !parent) { detalle.respond("failed"); return; }
          const record = await createCase(detalle.name, "explore-hypothesis", parent?.token);
          detalle.respond(record ? "created" : "failed");
        } catch (error) {
          if (error instanceof CaseError && error.code === "ALREADY_EXISTS") {
            detalle.respond("exists"); return;
          }
          // A failure after the write may have happened; never claim absence.
          detalle.respond("unknown");
        } finally {
          creandoDesdeChat.current = false;
        }
      })();
    };
    window.addEventListener("molchat-create-case", recibir);
    return () => window.removeEventListener("molchat-create-case", recibir);
  }, [createCase, ownerUserId, repository, requiresDirectory]);

  useEffect(() => {
    if (!receptorConfirmacion) return;
    const pending = receptorConfirmacion;
    if (ownerUserId !== pending.owner || activeCase?.id !== pending.caseId) { pending.finish("unknown"); return; }
    if (saveState === "error") { pending.finish("save_failed"); return; }
    if (activeCase.inputs?.receptor?.pdbId?.toUpperCase() === pending.pdbId.toUpperCase() &&
        (saveState === "saved" || (pending.already && saveState === "idle"))) {
      // A previous queued write may have set `saved` while a newer write is
      // still pending. Confirm the receptor in the persisted case itself.
      let cancelled = false;
      let retry: ReturnType<typeof setTimeout> | undefined;
      const verify = async () => {
        try {
          const persisted = await repository.readCase(pending.caseId);
          if (cancelled) return;
          const current = navigationState.current;
          if (current.ownerUserId !== pending.owner || current.activeCase?.id !== pending.caseId) { pending.finish("unknown"); return; }
          if (current.activeCase.inputs?.receptor?.pdbId?.toUpperCase() !== pending.pdbId.toUpperCase()) { pending.finish("unknown"); return; }
          if (persisted.inputs?.receptor?.pdbId?.toUpperCase() === pending.pdbId.toUpperCase()) {
            pending.finish(pending.already ? "already_selected" : "applied");
          } else retry = setTimeout(() => void verify(), 150);
        } catch { if (!cancelled) pending.finish("unknown"); }
      };
      void verify();
      return () => { cancelled = true; if (retry) clearTimeout(retry); };
    }
  }, [receptorConfirmacion, ownerUserId, activeCase, saveState, repository]);

  useEffect(() => {
    const recibir = (evento: Event) => {
      const detalle = (evento as CustomEvent<{ caseName: string; owner: string; requestId: string; deadline: number;
        handled: boolean; respond: (result: { status: string; task_id?: string; reason?: string }) => void }>).detail;
      if (!detalle || typeof detalle.respond !== "function") return;
      detalle.handled = true;
      if (detalle.owner !== ownerUserId || Date.now() >= detalle.deadline) { detalle.respond({ status: "failed" }); return; }
      const ocupadoPor = navigationState.current.hasLiveWork ? t("ev_chat_ocupado_trabajo")
        : evaluandoDesdeChat.current ? t("ev_chat_ocupado_otra")
        : asignandoReceptor.current ? t("ev_chat_ocupado_receptor")
        : cargandoSmiles.current ? t("ev_chat_ocupado_smiles")
        : unregisteredRun ? t("ev_chat_ocupado_corrida") : null;
      if (ocupadoPor) { detalle.respond({ status: "busy", reason: t("ev_chat_no_pulsado", { motivo: ocupadoPor }) }); return; }
      evaluandoDesdeChat.current = true;
      marcarEtapaDeEvaluacionChat(detalle.requestId, t("ev_chat_etapa_recibida_casos"));
      let terminado = false;
      const acabar = (result: { status: string; task_id?: string; reason?: string }) => {
        if (terminado) return;
        terminado = true;
        clearTimeout(timer);
        evaluandoDesdeChat.current = false;
        setEvaluacionDesdeChat(null);
        detalle.respond(navigationState.current.ownerUserId === detalle.owner ? result : { status: "unknown" });
      };
      const timer = setTimeout(() => acabar({ status: "unknown",
        reason: t("ev_chat_plazo", { etapa: etapaDeEvaluacionChat(detalle.requestId, t) }) }),
        Math.max(0, detalle.deadline - Date.now()));
      void (async () => {
        try {
          const normalizar = (name: string) => name.normalize("NFC").trim().toLocaleLowerCase();
          const encontrados = (await repository.listCases()).filter(c =>
            (!c.ownerUserId || c.ownerUserId === detalle.owner) && normalizar(c.name) === normalizar(detalle.caseName));
          if (terminado || navigationState.current.ownerUserId !== detalle.owner) { acabar({ status: "unknown" }); return; }
          if (!encontrados.length) { acabar({ status: "case_not_found" }); return; }
          if (encontrados.length > 1) { acabar({ status: "case_ambiguous" }); return; }
          if (encontrados[0].archived || encontrados[0].unavailable) { acabar({ status: "blocked" }); return; }
          const id = encontrados[0].id;
          if (!(await selectCase(id))) { acabar({ status: "busy", reason: t("ev_chat_caso_sin_abrir") }); return; }
          if (terminado || Date.now() >= detalle.deadline || navigationState.current.ownerUserId !== detalle.owner) { acabar({ status: "unknown" }); return; }
          marcarEtapaDeEvaluacionChat(detalle.requestId, t("ev_chat_etapa_caso_abierto"));
          setActiveView("evaluation");
          setEvaluacionDesdeChat({ requestId: detalle.requestId, caseId: id, deadline: detalle.deadline, onResult: acabar });
        } catch { acabar({ status: "failed" }); }
      })();
    };
    window.addEventListener("molchat-evaluate-case", recibir);
    return () => window.removeEventListener("molchat-evaluate-case", recibir);
  }, [ownerUserId, repository, selectCase, setActiveView, t, unregisteredRun]);

  useEffect(() => {
    const recibir = (evento: Event) => {
      const detalle = (evento as CustomEvent<{ caseName: string; pdbId: string; owner: string; requestId: string; deadline: number;
        handled: boolean; respond: (status: string) => void }>).detail;
      if (!detalle || typeof detalle.respond !== "function") return;
      detalle.handled = true;
      if (detalle.owner !== ownerUserId || Date.now() >= detalle.deadline) { detalle.respond("failed"); return; }
      if (navigationState.current.hasLiveWork || evaluandoDesdeChat.current || asignandoReceptor.current || cargandoSmiles.current) { detalle.respond("busy"); return; }
      asignandoReceptor.current = true;
      let terminado = false;
      const acabar = (status: string) => {
        if (terminado) return;
        terminado = true;
        clearTimeout(timer);
        asignandoReceptor.current = false;
        setReceptorDesdeChat(null);
        setReceptorConfirmacion(null);
        detalle.respond(status);
      };
      const timer = setTimeout(() => acabar("unknown"), Math.max(0, detalle.deadline - Date.now()));
      void (async () => {
        try {
          const normalizar = (name: string) => name.normalize("NFC").trim().toLocaleLowerCase();
          const encontrados = (await repository.listCases()).filter((c) =>
            (!c.ownerUserId || c.ownerUserId === detalle.owner) && normalizar(c.name) === normalizar(detalle.caseName));
          if (terminado || navigationState.current.ownerUserId !== detalle.owner) { acabar("unknown"); return; }
          if (!encontrados.length) { acabar("case_not_found"); return; }
          if (encontrados.length > 1) { acabar("case_ambiguous"); return; }
          if (encontrados[0].archived || encontrados[0].unavailable) { acabar("failed"); return; }
          const id = encontrados[0].id;
          if (!(await selectCase(id))) { acabar("busy"); return; }
          if (terminado || Date.now() >= detalle.deadline || navigationState.current.ownerUserId !== detalle.owner) { acabar("unknown"); return; }
          setActiveView("evaluation");
          setReceptorDesdeChat({ requestId: detalle.requestId, caseId: id, pdbId: detalle.pdbId, deadline: detalle.deadline,
            onVisible: (already) => {
              if (terminado || Date.now() >= detalle.deadline) { acabar("unknown"); return; }
              setReceptorConfirmacion({ caseId: id, owner: detalle.owner, pdbId: detalle.pdbId, already, finish: acabar });
            }, onError: acabar });
        } catch { acabar("failed"); }
      })();
    };
    window.addEventListener("molchat-assign-receptor", recibir);
    return () => window.removeEventListener("molchat-assign-receptor", recibir);
  }, [ownerUserId, repository, selectCase, setActiveView]);

  useEffect(() => {
    const recibir = (evento: Event) => {
      const detalle = (evento as CustomEvent<{ caseName: string; smiles: string; owner: string; requestId: string; deadline: number;
        handled: boolean; respond: (status: "applied" | "not_found" | "ambiguous" | "busy" | "failed" | "unknown") => void }>).detail;
      if (!detalle || typeof detalle.respond !== "function") return;
      detalle.handled = true;
      if (detalle.owner !== ownerUserId || Date.now() >= detalle.deadline) { detalle.respond("failed"); return; }
      if (navigationState.current.hasLiveWork) { detalle.respond("busy"); return; }
      if (cargandoSmiles.current || asignandoReceptor.current || evaluandoDesdeChat.current) { detalle.respond("busy"); return; }
      cargandoSmiles.current = true;
      let terminado = false;
      const acabar = (status: "applied" | "not_found" | "ambiguous" | "busy" | "failed" | "unknown") => {
        if (terminado) return;
        terminado = true;
        clearTimeout(timer);
        cargandoSmiles.current = false;
        setSmilesDesdeChat(null);
        detalle.respond(status);
      };
      const timer = setTimeout(() => acabar("unknown"), Math.max(0, detalle.deadline - Date.now()));
      void (async () => {
        try {
          const normalizar = (name: string) => name.normalize("NFC").trim().toLocaleLowerCase();
          const encontrados = (await repository.listCases()).filter((c) =>
            (!c.ownerUserId || c.ownerUserId === detalle.owner) && normalizar(c.name) === normalizar(detalle.caseName));
          if (terminado || navigationState.current.ownerUserId !== detalle.owner) { acabar("failed"); return; }
          if (encontrados.length === 0) { acabar("not_found"); return; }
          if (encontrados.length > 1) { acabar("ambiguous"); return; }
          if (encontrados[0].archived || encontrados[0].unavailable) { acabar("failed"); return; }
          const id = encontrados[0].id;
          if (!(await selectCase(id))) { acabar("busy"); return; }
          if (terminado || Date.now() >= detalle.deadline || navigationState.current.ownerUserId !== detalle.owner) { acabar("unknown"); return; }
          setActiveView("evaluation");
          setSmilesDesdeChat({ requestId: detalle.requestId, caseId: id, smiles: detalle.smiles, deadline: detalle.deadline,
            onApplied: () => {
              const state = navigationState.current;
              acabar(Date.now() < detalle.deadline && state.ownerUserId === detalle.owner && state.activeCase?.id === id ? "applied" : "unknown");
            } });
        } catch { acabar("failed"); }
      })();
    };
    window.addEventListener("molchat-load-smiles", recibir);
    return () => window.removeEventListener("molchat-load-smiles", recibir);
  }, [ownerUserId, repository, selectCase, setActiveView]);

  useEffect(() => {
    const recibir = (evento: Event) => {
      const detalle = (evento as CustomEvent<{ caseName: string; operation: string; revision: string; owner: string; deadline: number;
        handled: boolean; respond: (result: { status: string; molfile?: string; revision?: string }) => void }>).detail;
      if (!detalle || typeof detalle.respond !== "function") return;
      detalle.handled = true;
      if (detalle.owner !== ownerUserId || Date.now() >= detalle.deadline) { detalle.respond({ status: "failed" }); return; }
      void (async () => {
        try {
          const normalizar = (name: string) => name.normalize("NFC").trim().toLocaleLowerCase();
          const encontrados = (await repository.listCases()).filter((c) =>
            (!c.ownerUserId || c.ownerUserId === detalle.owner) && normalizar(c.name) === normalizar(detalle.caseName));
          if (encontrados.length === 0) { detalle.respond({ status: "not_found" }); return; }
          if (encontrados.length > 1) { detalle.respond({ status: "ambiguous" }); return; }
          const record = encontrados[0];
          if (record.archived || record.unavailable || navigationState.current.ownerUserId !== detalle.owner) { detalle.respond({ status: "failed" }); return; }
          if (detalle.operation === "snapshot" && !(await selectCase(record.id))) { detalle.respond({ status: "not_ready" }); return; }
          if (Date.now() >= detalle.deadline) { detalle.respond({ status: "unknown" }); return; }
          const reader = detalle.operation === "check" ? currentEditorReader(record.id)
            : await waitEditorReader(record.id, Math.min(15000, detalle.deadline - Date.now()));
          const state = navigationState.current;
          if (!reader || Date.now() >= detalle.deadline || state.ownerUserId !== detalle.owner || state.activeCase?.id !== record.id) {
            detalle.respond({ status: detalle.operation === "check" ? "changed" : "not_ready" }); return;
          }
          if (detalle.operation === "check") { detalle.respond({ status: reader.check(detalle.revision) ? "ok" : "changed" }); return; }
          const snapshot = await reader.snapshot();
          if (Date.now() >= detalle.deadline || navigationState.current.activeCase?.id !== record.id || navigationState.current.ownerUserId !== detalle.owner) {
            detalle.respond({ status: "changed" }); return;
          }
          detalle.respond(snapshot);
        } catch { detalle.respond({ status: "failed" }); }
      })();
    };
    window.addEventListener("molchat-read-editor", recibir);
    return () => window.removeEventListener("molchat-read-editor", recibir);
  }, [ownerUserId, repository, selectCase]);

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

  const defaultParentDirectory = useCallback(async () => {
    if (!repository.defaultParentDirectory) return null;
    return repository.defaultParentDirectory();
  }, [repository]);

  const handleSelect = useCallback(
    (id: string) => {
      void selectCase(id);
      setSidebarOpen(false);
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
    ? t("ca_trabajo_en_curso_bloquea")
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
      className="flex min-h-0 w-full flex-col overflow-hidden bg-surface-950 text-zinc-200"
      style={{ height: `calc(100dvh - ${NAV_HEIGHT})` }}
    >
      <div className="flex min-h-0 flex-1 flex-col lg:flex-row">
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
          className="whitespace-nowrap rounded-md border border-surface-700 px-2.5 py-1 text-sm text-zinc-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400"
        >
          {t("ca_sidebar_cases")}
        </button>
        <span className="min-w-0 truncate text-sm text-zinc-400">
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
            aria-label={t("ca_sidebar_cases")}
            className="relative z-10 flex w-[85vw] max-w-[300px]"
          >
            <div className="min-w-0 flex-1">{sidebar}</div>
            <button
              type="button"
              onClick={() => setSidebarOpen(false)}
              aria-label={t("ca_cerrar_panel")}
              className="absolute right-1 top-1 rounded p-1.5 text-zinc-400 hover:text-zinc-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400"
            >
              <X className="h-4 w-4" aria-hidden="true" />
            </button>
          </div>
        </div>
      )}

      <main data-case-workspace="true" className="flex min-h-0 min-w-0 flex-1 flex-col">
        {/* Estado del motor de cálculo. Sólo aparece cuando hay algo que decir:
            arrancando, no instalado, o caído con su razón y su reintento. */}
        <EngineStatusBar />

        {error && (
          <div
            role="alert"
            className="flex items-start gap-2 border-b border-amber-500/30 bg-amber-500/10 px-4 py-2 text-base leading-6 text-amber-200 font-sans"
          >
            <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
            <span className="min-w-0 flex-1">
              {error}
            </span>
            {saveState === "error" && (
              <button
                type="button"
                onClick={() => void retrySave()}
                className="shrink-0 whitespace-nowrap rounded border border-amber-500/40 px-2 py-0.5 text-sm hover:text-amber-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400"
              >
                {t("c_reintentar")}
              </button>
            )}
            <button
              type="button"
              onClick={dismissError}
              aria-label={t("ca_workspace_dismiss_notice")}
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
            className="flex flex-wrap items-center gap-2 border-b border-red-500/30 bg-red-500/10 px-4 py-2 text-base leading-6 text-red-200 font-sans"
          >
            <span className="min-w-0 flex-1">
              {t("ca_corrida_arranco")} <strong>{t("ca_id_no_guardado")}</strong>{t("auto_d970f808cba3")}{" "}
              <code className="break-all font-mono">{unregisteredRun.taskId}</code>
            </span>
            <button
              type="button"
              onClick={() => void retryRegisterRun()}
              className="shrink-0 whitespace-nowrap rounded border border-red-500/40 px-2 py-0.5 text-sm hover:text-red-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-400"
            >
              {t("ca_workspace_retry_save")}
            </button>
            <button
              type="button"
              onClick={() => void navigator.clipboard?.writeText(unregisteredRun.taskId)}
              className="shrink-0 whitespace-nowrap rounded border border-red-500/40 px-2 py-0.5 text-sm hover:text-red-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-400"
            >
              {t("ca_workspace_copy_id")}
            </button>
          </div>
        )}


        {relocationConflict && (
          <div
            role="alertdialog"
            aria-label={t("ca_ya_registrado")}
            className="border-b border-amber-500/30 bg-amber-500/10 px-4 py-3 text-base leading-6 text-amber-100 font-sans"
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
                className="rounded-md border border-amber-500/40 px-3 py-1 text-sm hover:text-amber-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400"
              >
                {t("ca_usar_carpeta_nueva")}
              </button>
              <button
                type="button"
                onClick={() => setRelocationConflict(null)}
                className="rounded-md border border-surface-700 px-3 py-1 text-sm text-zinc-300 hover:text-zinc-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400"
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
            className="border-b border-surface-700 bg-surface-900 px-4 py-3 text-base leading-6 text-zinc-300 font-sans"
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
                className="rounded-md border border-brand-500/40 bg-brand-600 px-3 py-1 text-sm font-medium text-white hover:bg-brand-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400"
              >
                {t("ca_inicializar_como_caso")}
              </button>
              <button
                type="button"
                onClick={() => setPendingFolder(null)}
                className="rounded-md border border-surface-700 px-3 py-1 text-sm text-zinc-300 hover:text-zinc-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400"
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
              hasLiveWork ? workLockedReason
                : capabilities.openFolderUnavailableMessage?.render(t) ?? capabilities.openFolderUnavailableReason
            }
            storageLabel={storageLabel}
            createDisabled={hasLiveWork}
            createDisabledReason={workLockedReason}
          />
        ) : (
          <>
            {/* Cabecera y acciones reservan espacio fuera del scroll del caso.
                Ningún título ni control de resultados queda debajo de ellos. */}
            <header data-case-header="true" className={`${resultStyles.caseHeader} shrink-0 border-b border-surface-800 bg-surface-950 px-4 py-3 sm:px-6`}>
              <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
                <div className="min-w-0 flex-1 basis-72">
                  <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                    <h1 id="case-title" className="min-w-0 truncate text-base font-semibold tracking-tight text-zinc-100">
                      {activeCase.name}
                    </h1>
                    <span className="whitespace-nowrap rounded border border-surface-700 px-1.5 py-0.5 font-sans text-sm uppercase tracking-wider text-zinc-400">
                      {t(`ca_case_status_${activeCase.status}`)}
                    </span>
                    {activeCase.activeRun && (
                      <span className={resultStyles.runStrip + " inline-flex min-w-0 max-w-full flex-wrap items-baseline gap-x-1 font-sans text-zinc-400 leading-5"}>
                        <span>{activeRunPendingRegistration ? t("auto_262949a66911") : t("ca_workspace_run_registered")}</span>
                        <code title={activeCase.activeRun.taskId} className="min-w-0 max-w-full font-mono [overflow-wrap:anywhere]">{activeCase.activeRun.taskId}</code>
                        <span>· {{
                          idle: t("ca_run_state_idle"),
                          submitted: t("ca_run_state_submitted"),
                          running: t("ca_run_state_running"),
                          interrupted: t("ca_run_state_interrupted"),
                          completed: t("ca_run_state_completed"),
                          failed: t("ca_run_state_failed"),
                          cancelled: t("ca_run_state_cancelled"),
                        }[activeCase.activeRun.executionState]}</span>
                      </span>
                    )}
                  </div>
                  <div className={resultStyles.caseMeta}><dl className="mt-1.5 flex flex-wrap gap-x-5 gap-y-1 font-mono text-sm text-zinc-400">
                    <div className="flex min-w-0 gap-1.5">
                      <dt className="sr-only">{t("ca_workspace_storage")}</dt>
                      <dd className="min-w-0 [overflow-wrap:anywhere]">
                        {activeCase.storage.mode === "folder"
                          ? displayCasePath(activeCase.storage.path)
                          : t("ca_workspace_storage_browser")}
                      </dd>
                    </div>
                    <div className="flex gap-1.5">
                      <dt>{t("auto_5dfeeb357031")}</dt>
                      <dd>{formatTimestamp(activeCase.updatedAt, locale)}</dd>
                    </div>
                  </dl></div>
                </div>

                                <div className="min-w-0 max-w-full">
                  {reportable && (
                    <button
                      type="button"
                      onClick={() => setActiveView(view === "report" ? "evaluation" : "report")}
                      className="inline-flex min-h-11 shrink-0 items-center gap-2 whitespace-nowrap rounded-md border border-surface-700 px-3 py-1.5 text-sm text-zinc-300 transition-colors hover:border-surface-600 hover:text-zinc-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400"
                    >
                      {view === "report" ? (
                        <>
                          <ArrowLeft className="h-4 w-4 shrink-0" aria-hidden="true" />
                          <span>{t("ca_volver_evaluacion")}</span>
                        </>
                      ) : (
                        <>
                          <FileText className="h-4 w-4 shrink-0" aria-hidden="true" />
                          <span>{caseViewLabel("report", t)}</span>
                        </>
                      )}
                    </button>
                  )}
                </div>
              </div>
            </header>

            <div
              data-case-scroll="true"
              className={`evaluation-scrollbar min-h-0 flex-1 overscroll-contain ${reportable && view === "report" ? "flex flex-col overflow-hidden" : "overflow-y-auto"}`}
            >
            {!reportable && (
              <section className="border-b border-surface-800 px-4 py-2 sm:px-6">
                <details className="group">
                  <summary className="flex min-h-11 cursor-pointer list-none items-center justify-between gap-3 text-sm font-semibold text-zinc-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400">
                    <span>{t("ca_context_questions_heading")}</span>
                    <span className="flex items-center gap-2 text-xs font-normal text-zinc-400">
                      {describePendingDetails(activeCase.context, t)}
                      <ChevronDown className="h-4 w-4 transition-transform group-open:rotate-180" aria-hidden="true" />
                    </span>
                  </summary>
                  <div className="border-t border-surface-800">
                    <CaseContextPanel
                      context={activeCase.context}
                      saveState={saveState}
                      onChange={updateContext}
                      onRetry={retrySave}
                      embedded
                      variant="panel"
                    />
                  </div>
                </details>
              </section>
            )}
            {/* La atribución de una corrida anterior se conserva visible en Evaluación. */}
            {reportable && view === "evaluation" && runRelation !== "corresponde" && (
              <div className="flex flex-wrap items-center gap-2 border-b border-surface-800 bg-surface-900 px-4 py-2 text-base leading-6 text-zinc-300 sm:px-6 font-sans">
                <FileText className="h-3.5 w-3.5 shrink-0 text-brand-400" aria-hidden="true" />
                <span className="min-w-0 flex-1">
                  {runRelation === "corrida_anterior"
                    ? t("auto_7f0c5ddda6e9")
                    : t("auto_b3945ccefff7")}
                </span>
              </div>
            )}

            {reportUnrecoverable && (
              <p
                role="status"
                className="border-b border-amber-500/30 bg-amber-500/10 px-4 py-2 text-base leading-6 text-amber-200 sm:px-6 font-sans"
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

            {/* Este envoltorio conserva ambos paneles dentro del mismo scroll;
                la cabecera y el pie pertenecen a la columna del caso. */}
            <div className={`min-h-0 flex-1 ${reportable && view === "report" ? "flex flex-col" : ""}`}>
              <div
                id="case-panel-evaluation"
                hidden={!evaluationVisible}
                className="h-full"
              >
                {/* `KeepAliveContext` en false pausa Molstar y demás viewers
                    mientras el modo está oculto, sin desmontar nada. */}
                <KeepAliveContext.Provider value={evaluationKeepAlive}>
                  <CaseEvaluationRunner
                    key={activeCase.id}
                    caseId={activeCase.id}
                    caseRuns={activeCase.runs}
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
                    onOpenRunHistory={() => { setNativeSelection(null); setRunHistoryOpen(true); }}
                    onInputsChange={setInputs}
                    preflight={activeCase.preflight}
                    onPreflightChange={setPreflight}
                    decisions={activeCase.decisions}
                    onDecision={recordDecision}
                    peticion={peticion?.casoId === activeCase.id ? peticion : undefined}
                    smilesDesdeChat={smilesDesdeChat?.caseId === activeCase.id ? smilesDesdeChat : undefined}
                    receptorDesdeChat={receptorDesdeChat?.caseId === activeCase.id ? receptorDesdeChat : undefined}
                    evaluacionDesdeChat={evaluacionDesdeChat?.caseId === activeCase.id ? evaluacionDesdeChat : undefined}
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
                  className="h-full min-h-0 flex-1"
                  role="region"
                  aria-labelledby="case-report-title"
                >
                  {/* El caso ENTERO, no un extracto: la proyección que pide el
                      dossier necesita inputs, preflight, decisiones y corrida.
                      Pasar sólo nombre y contexto obligaría a reconstruirlo a
                      trozos justo donde importa que sea fiel. */}
                  <CaseReportView
                    key={activeCase.id}
                    caseRecord={activeCase}
                    reportable={reportable}
                    runRelation={runRelation}
                    pendingDetails={describePendingDetails(activeCase.context, t)}
                    context={activeCase.context}
                    contextSaveState={saveState}
                    onContextChange={updateContext}
                    onRetryContextSave={retrySave}
                    disposition={activeCase.disposition}
                    dispositions={activeCase.dispositions}
                    showDisposition={activeCase.activeRun?.executionState === "completed"}
                    onDispositionSubmit={setDisposition}
                  />
                </div>
              )}
            </div>
            </div>
          </>
        )}
        <div id="evaluation-actions-outlet" className="shrink-0"/>
      </main>


      {activeCase && runHistoryOpen && (
        <CaseRunHistoryModal
          key={nativeSelection?.sequence ?? "manual"}
          runs={activeCase.runs}
          requestedTaskId={nativeSelection?.caseId === activeCase.id ? nativeSelection.taskId : undefined}
          onRequestedRunSelected={requestedRunSelected}
          structuralSystem={activeCase.structuralSystem}
          currentFingerprint={activeCase.preflight?.fingerprint ?? null}
          activeTaskId={activeCase.activeRun?.taskId}
          onClose={closeRunHistory}
        />
      )}

      <CreateCaseDialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        onCreate={handleCreate}
        requiresDirectory={requiresDirectory}
        storageLabel={storageLabel}
        onPickDirectory={requiresDirectory ? pickParentDirectory : undefined}
        onDefaultDirectory={requiresDirectory ? defaultParentDirectory : undefined}
      />
      </div>
    </div>
  );
}

export default CaseWorkspace;
