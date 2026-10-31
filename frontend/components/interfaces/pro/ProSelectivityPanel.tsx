import { frontendMessage, type FrontendMessage } from "../../../lib/frontendError";
import { antiTargetFieldMessage, antiTargetFieldText } from "../../../lib/antiTargetPresentation";
import { presentError } from "../../../lib/frontendError";
import React, { useState, useEffect, useRef, useId } from "react";
import { useLanguage } from "../../../context/LanguageContext";
import { createPortal } from "react-dom";
import { ShieldCheck, Play, RefreshCw, AlertTriangle, CheckCircle2, ShieldAlert, Cpu, Activity, BookOpen, Sparkles, X, Info, Loader2 } from "lucide-react";
import { dockSingleAntiTarget, saveSelectivityResults } from "../../../lib/proApi";
import { getEvaluationResult } from "../../../lib/api";
import { antiDianasParaEnviar, antiDianasPorDefecto, useAntiDianas } from "../../../lib/antiDianas";
import { AntiDianasSelector } from "./AntiDianasSelector";
import {
  INCERTIDUMBRE_VINA_KCAL,
  VEREDICTO_SIN_DATOS,
  claveDeVeredicto,
  colorDeMargen,
  margenDeSelectividad,
  veredictoDeMargen,
} from "../../../lib/selectividadMargen";

interface AntiTargetInfo {
  pdb_id: string;
  name: string;
  category: string;
  risk: string;
  riskOrigin?: "frontend" | "backend";
  threshold: number;
  targetFunction: string;
  bioDetails: string;
  mitigationSar: string;
}

interface ProSelectivityPanelProps {
  moleculeId: string | null;
  /** Corrida exacta que el padre está mostrando; ausente sólo en clientes legacy. */
  taskId?: string | null;
  onTargetAffinity?: number | null;
  initialResult?: any;
  onUpdateResult?: (res: any) => void;
  /** v1.7.4: el pipeline lanzó el panel en background (subprocess). El panel
   *  pollea /evaluation/result/{moleculeId} y puebla los resultados cuando
   *  el subprocess persiste (selectivity_ran=true). NO bloquea el pipeline. */
  autoPoll?: boolean;
  /** La tanda sigue activa al ocultar la pestaña; los diálogos sólo se muestran al verla. */
  isActive?: boolean;
  onWorkStateChange?: (active: boolean) => void;
}

/** Sin respuesta del API (no cargó o falló), el panel por defecto del backend: hERG y 5-HT2B. */
const IDS_SIN_API = ["5VA1", "7SRQ"];

/**
 * Lo que la interfaz sabe EXPLICAR de algunas anti-dianas (función, mecanismo y
 * estrategia SAR): texto escrito a mano para «Saber más». NO decide qué
 * anti-dianas tiene el panel: eso lo decide el API (`GET /pro/anti-targets`, las
 * 44 de Bowes 2012 con su disponibilidad). Antes esta lista ERA el panel y
 * mostraba sólo tres, una de ellas CYP3A4, que el backend ya no lleva por
 * defecto, mientras las otras 40 seleccionables no se podían ni ver aquí.
 */
const ANTIDIANAS_CONOCIDAS: AntiTargetInfo[] = [
  {
    pdb_id: "5VA1",
    name: "hERG (KCNH2)",
    category: "Cardiac",
    risk: "Arritmia cardíaca (prolongación del intervalo QT). Canal de potasio vital.",
    threshold: -7.0,
    targetFunction: "Canal de potasio dependiente de voltaje responsable de la repolarización del potencial de acción cardíaco (corriente I_Kr).",
    bioDetails: "El bloqueo farmacológico del poro interno de hERG impide la repolarización miocárdica, lo que resulta en prolongación del intervalo QT en el ECG y riesgo severo de Torsades de Pointes (muerte súbita cardíaca). Es el filtro de seguridad farmacológica N°1 exigido por la FDA y la EMA (Guía ICH S7B).",
    mitigationSar: "Estrategias de Optimización SAR: Disminuir el pKa del nitrógeno básico a través de grupos atrayentes de electrones cercanos; reducir la lipofilicidad (ClogP); romper la planaridad aromática; o introducir sustituyentes polares solubilizantes para reducir el empaquetamiento lipofílico en la cavidad del poro."
  },
  {
    pdb_id: "4NY4",
    name: "CYP3A4",
    category: "Metabolism",
    risk: "Inhibición causa interacciones droga-droga. Metaboliza >50% de fármacos.",
    threshold: -8.0,
    targetFunction: "Isoenzima principal del citocromo P450 hepático y gastrointestinal encargada de la biotransformación oxidativa de más del 50% de medicamentos clínicamente aprobados.",
    bioDetails: "La inhibición potente de CYP3A4 resulta en la inhibición del metabolismo de co-fármacos administrados al paciente, causando aumentos drásticos en las concentraciones plasmáticas y toxicidad sistémica incontrolada (Interacciones Droga-Droga / DDI).",
    mitigationSar: "Estrategias de Optimización SAR: Bloquear los sitios propensos a oxidación alifática u aromática mediante halogenación dirigida (sustitución con Flúor -F); ajustar el volumen estérico global para impedir la coordinación óptima con el grupo hemo (Fe-porfirina)."
  },
  {
    pdb_id: "7SRQ",
    name: "5-HT2B (HTR2B)",
    category: "CNS/Safety",
    risk: "Agonismo de 5-HT2B causa valvulopatía cardíaca e hipertensión pulmonar.",
    threshold: -7.5,
    targetFunction: "Receptor serotoninérgico acoplado a proteína Gq/11 modulador de la proliferación celular en tejido valvular y vascular.",
    bioDetails: "El agonismo prolongado de 5-HT2B estimula la mitogénesis y proliferación aberrante de fibroblastos en las válvulas del corazón, produciendo fibrosis valvular irreversible y regurgitación aórtica/mitral (caso histórico Fenfluramina / Dexfenfluramina), así como hipertensión arterial pulmonar.",
    mitigationSar: "Estrategias de Optimización SAR: Eliminar o modificar farmacóforos triptamínicos básicos; sustituir aminas secundarias por grupos voluminosos o amidas no protonables; verificar el modo de enlace para asegurar comportamiento como antagonista neutro en lugar de agonista."
  },

];

// ═══════════════════════════════════════════════════════════════════════
// Ki a partir de un score de Vina: la banda, nunca el punto
// ═══════════════════════════════════════════════════════════════════════
//
// LO QUE HABÍA. Una función `estimateKiMicromolar` que devolvía
// `exp(ΔG/RT) · 1e6`, y la interfaz lo imprimía como
//
//     Estimación Ki / IC50:   0.4 µM
//
// Dos afirmaciones falsas en una celda de tres centímetros:
//
//  1. «Ki / IC50». Son dos observables experimentales DISTINTOS —una
//     constante de disociación de equilibrio y una concentración inhibitoria
//     dependiente del ensayo—, y ninguno de los dos es lo que mide Vina.
//     El score de Vina es una función empírica ajustada, no una energía libre.
//
//  2. UN DECIMAL. La desviación típica del score de Vina frente a afinidades
//     medidas está en 1.5–2.5 kcal/mol según el conjunto. Como la relación es
//     exponencial, a 310 K:
//
//         error de 1.4 kcal/mol   ->  Ki x/÷ 10        (un orden de magnitud)
//         error de 2.8 kcal/mol   ->  Ki x/÷ 100       (dos órdenes)
//
//     Escribir «0.4 µM» sobre una entrada con esa dispersión no es redondear
//     de más: es inventar cuatro órdenes de magnitud de precisión que el
//     método no tiene. En un panel de anti-dianas —donde el número decide si
//     alguien considera segura su molécula— eso es lo peor que puede hacer
//     esta pantalla.
//
// Y contradecía al resto del producto, que ya se cuida de no disfrazar la
// afinidad de Vina como una constante experimental.
//
// LO QUE HAY AHORA. La misma conversión, pero propagando la incertidumbre y
// diciendo su nombre: un intervalo de órdenes de magnitud, etiquetado como
// derivado del score, no como Ki medido.

/** R·T a 310.15 K, en kcal/mol. */
const RT_KCAL = 0.61626;

/** Concentración implícita por el score, en µM. No es una Ki medida. */
const concentracionImplicadaMicromolar = (deltaGKcal: number): number =>
  Math.exp(deltaGKcal / RT_KCAL) * 1e6;

const formatearConcentracion = (uM: number): string => {
  if (uM >= 1e6) return `${(uM / 1e6).toFixed(0)} M`;
  if (uM >= 1000) return `${(uM / 1000).toFixed(1)} mM`;
  if (uM >= 1) return `${uM.toFixed(1)} µM`;
  if (uM >= 1e-3) return `${(uM * 1000).toFixed(1)} nM`;
  return `${(uM * 1e6).toFixed(1)} pM`;
};

/**
 * El intervalo compatible con el score, dada la dispersión conocida de Vina.
 *
 * `±2 kcal/mol` sobre el score se traduce en dividir y multiplicar la
 * concentración por ~26. Se enseñan los dos extremos porque son lo único que
 * el método sostiene.
 */
export function bandaDeConcentracion(deltaGKcal: number): {
  inferior: string;
  superior: string;
  ordenes: number;
} {
  const fuerte = concentracionImplicadaMicromolar(deltaGKcal - INCERTIDUMBRE_VINA_KCAL);
  const debil = concentracionImplicadaMicromolar(deltaGKcal + INCERTIDUMBRE_VINA_KCAL);
  return {
    inferior: formatearConcentracion(fuerte),
    superior: formatearConcentracion(debil),
    ordenes: Math.log10(debil / fuerte),
  };
}

export const ProSelectivityPanel: React.FC<ProSelectivityPanelProps> = (props) => (
  <ProSelectivitySession key={`${props.moleculeId ?? "sin-molecula"}:${props.taskId ?? "sin-corrida"}`} {...props} />
);

// Una corrida distinta no hereda selección, respuestas tardías ni resultados locales.
const ProSelectivitySession: React.FC<ProSelectivityPanelProps> = ({
  moleculeId,
  taskId = null,
  onTargetAffinity = null,
  initialResult,
  onUpdateResult,
  autoPoll = false,
  isActive = true,
  onWorkStateChange,
}) => {
  const { t } = useLanguage();
  const panelTitleId = useId();
  const sessionActive = useRef(true);
  useEffect(() => {
    sessionActive.current = true;
    return () => { sessionActive.current = false; };
  }, []);
  const [resultsMap, setResultsMap] = useState<Record<string, any>>({});
  // Espejo del mapa para poder componer el siguiente estado fuera del
  // actualizador sin leer una versión obsoleta en una tanda de dockings.
  const resultsMapRef = useRef<Record<string, any>>({});
  const locallyEvaluatedIds = useRef(new Set<string>());
  const mergeStoredResults = (stored: Record<string, any>) => {
    const merged = { ...resultsMapRef.current, ...stored };
    for (const id of locallyEvaluatedIds.current) {
      if (resultsMapRef.current[id]) merged[id] = resultsMapRef.current[id];
    }
    return merged;
  };
  const [isRunning, setIsRunning] = useState(false);
  const [activeTargetId, setActiveTargetId] = useState<string | null>(null);
  // v1.7.4: true mientras el pipeline corre el panel en background y el
  // frontend espera el resultado persistido (polling de /evaluation/result).
  const [bgWaiting, setBgWaiting] = useState(false);
  useEffect(() => {
    onWorkStateChange?.(isRunning || activeTargetId !== null || bgWaiting);
  }, [isRunning, activeTargetId, bgWaiting, onWorkStateChange]);
  useEffect(() => () => { onWorkStateChange?.(false); }, [onWorkStateChange]);
  // AMP-10. Reevaluar una anti-diana de una corrida que ya no es la vigente del
  // caso lo rechaza el servidor (409). Eso NO es un fallo de cálculo y NO borra
  // lo registrado: el resultado anterior se conserva y el motivo se dice. Un
  // 409 vale para toda la evaluación, así que apaga la ampliación del panel
  // entero en vez de dejar que se repita contra cada anti-diana.
  const [ampliacionNoDisponible, setAmpliacionNoDisponible] = useState<string | null>(null);
  // Por anti-diana: «se intentó reevaluar, falló, y se conserva lo anterior».
  const [avisoDeReevaluacion, setAvisoDeReevaluacion] = useState<Record<string, string>>({});
  // DOC 71, DEFECTOS B1 y B2 — LO QUE DE VERDAD LOS ARREGLA.
  //
  // ProAnalysisTabs conserva esta instancia al cambiar de pestaña: selección y
  // tanda siguen en memoria. La persistencia permite recuperar los resultados
  // cuando se vuelve a abrir la evaluación después de un desmontaje real.
  //
  // La corrección tiene dos mitades y hacen falta las dos:
  //
  //   1. cada anti-target se escribe EN CUANTO SALE, y el backend fusiona por
  //      `pdb_id` en vez de reemplazar, para que un guardado tardío no borre
  //      trabajo ya hecho;
  //   2. al montar se lee de la base SIEMPRE que haya evaluación y no haya
  //      resultados en memoria — antes eso sólo pasaba si `autoPoll` estaba
  //      encendido, es decir, sólo cuando el pipeline había corrido el panel.
  //      Quien lo lanzaba a mano volvía a la pestaña y lo encontraba vacío
  //      aunque estuviera guardado.
  //
  // El aviso se queda como último recurso, para cuando la escritura falla de
  // verdad: entonces sí hay que decirlo, porque el usuario decide si repite.
  const [persistencia, setPersistencia] = useState<"pendiente" | "guardado" | "fallido">("pendiente");
  const [errorAlGuardar, setErrorAlGuardar] = useState<string | null>(null);
  const [resultReadError, setResultReadError] = useState<string | null>(null);
  const [resultReadAttempt, setResultReadAttempt] = useState(0);

  const guardar = (objeto: Parameters<typeof saveSelectivityResults>[1]) => {
    if (!moleculeId) {
      // Sin evaluación a la que anclarlo no hay nada que guardar, y el usuario
      // tiene que saberlo antes de cambiar de pestaña.
      setPersistencia("fallido");
      setErrorAlGuardar(t("pr_sel_sin_evaluacion"));
      return;
    }
    setPersistencia("pendiente");
    saveSelectivityResults(moleculeId, { ...objeto, ...(taskId ? { task_id: taskId } : {}) })
      .then(() => { setPersistencia("guardado"); setErrorAlGuardar(null); })
      .catch((e: unknown) => {
        setPersistencia("fallido");
        setErrorAlGuardar(e instanceof Error ? presentError(e, t) : String(e));
      });
  };

  // Modal para t("pr_sel_saber_mas")
  const [selectedDetail, setSelectedDetail] = useState<{
    at: AntiTargetInfo;
    aff: number | null;
    isDanger: boolean;
    thresh: number;
  } | null>(null);
  useEffect(() => {
    if (!isActive) setSelectedDetail(null);
  }, [isActive]);

  // ── Qué anti-dianas tiene ESTE panel ─────────────────────────────────────
  //
  // Antes eran tres fijas. Ahora el API manda: las 44 de Bowes 2012 con su
  // disponibilidad, hERG y 5-HT2B marcadas y el resto opcional (el mismo selector
  // que «Parámetros de la evaluación»). `seleccion === null` significa «el panel por
  // defecto»; así, al llegar el API o cambiar el catálogo, el defecto se
  // actualiza solo, y una elección explícita —incluida «Ninguna»— se respeta.
  // Lo que YA tiene resultado se muestra siempre, esté elegido o no: lo
  // registrado no desaparece por desmarcar una casilla.
  const anti = useAntiDianas();
  const [seleccion, setSeleccion] = useState<string[] | null>(null);
  const idsElegidos = seleccion ?? (anti.targets ? antiDianasPorDefecto(anti.targets) : IDS_SIN_API);
  const panel: AntiTargetInfo[] = [...new Set([...idsElegidos, ...Object.keys(resultsMap)])].map((id) => {
    const delApi = anti.targets?.find((a) => a.pdb_id === id);
    const conocida = ANTIDIANAS_CONOCIDAS.find((a) => a.pdb_id === id);
    const resultado = resultsMap[id];
    return {
      pdb_id: id,
      name: delApi?.name ?? resultado?.name ?? conocida?.name ?? id,
      category: (delApi?.category ?? resultado?.category ?? conocida?.category ?? "").replace(/^Bowes 2012\s*·\s*/, ""),
      risk: delApi?.risk ?? resultado?.risk ?? resultado?.reason ?? conocida?.risk ?? "",
      riskOrigin: delApi?.risk != null || resultado?.risk != null || resultado?.reason != null ? "backend" : "frontend",
      threshold: resultado?.threshold ?? delApi?.threshold_kcal ?? conocida?.threshold ?? -7,
      targetFunction: conocida?.targetFunction ?? "",
      bioDetails: conocida?.bioDetails ?? "",
      mitigationSar: conocida?.mitigationSar ?? "",
    };
  });
  const idsParaEvaluar = anti.targets ? antiDianasParaEnviar(anti.targets, idsElegidos) : idsElegidos;
  const seleccionadosParaEvaluar = panel.filter((at) => idsParaEvaluar.includes(at.pdb_id));
  const seleccionBloqueada = isRunning || activeTargetId !== null || bgWaiting;
  const seleccionadasEvaluadas = seleccionadosParaEvaluar.filter((at) => typeof resultsMap[at.pdb_id]?.affinity === "number" && Number.isFinite(resultsMap[at.pdb_id].affinity)).length;
  const resultadosAnteriores = panel.filter((at) => !idsElegidos.includes(at.pdb_id)).length;

  // Un nuevo render del padre puede reenviar el snapshot anterior de la corrida.
  // Se incorporan sus filas sin reemplazar resultados o estados en curso de este panel.
  const initialSnapshotRef = useRef<string | null>(null);
  useEffect(() => {
    if (initialResult?.off_targets && Array.isArray(initialResult.off_targets)) {
      const snapshot = JSON.stringify(initialResult.off_targets);
      if (initialSnapshotRef.current === snapshot) return;
      initialSnapshotRef.current = snapshot;
      const map: Record<string, any> = {};
      initialResult.off_targets.forEach((t: any) => {
        if (t?.pdb_id) {
          map[t.pdb_id] = t;
        }
      });
      const merged = mergeStoredResults(map);
      resultsMapRef.current = merged;
      setResultsMap(merged);
      setBgWaiting(false);
    }
  }, [initialResult, t]);

  // ── Rehidratación desde lo PERSISTIDO, siempre ──────────────────────────
  //
  // DOC 71, B2. Antes esto sólo ocurría dentro del auto-poll, que se enciende
  // únicamente cuando el pipeline corrió el panel. Quien lo lanzaba a mano
  // cambiaba de pestaña, el componente se desmontaba, y al volver encontraba
  // el panel vacío AUNQUE el resultado estuviera guardado en la evaluación.
  //
  // Se lee una vez al montar, sólo si no hay nada en memoria: no pisa un panel
  // en curso ni compite con el auto-poll.
  useEffect(() => {
    if (!moleculeId) return;
    if (Object.keys(resultsMapRef.current).length > 0) return;
    let cancelado = false;
    (async () => {
      try {
        const data = taskId
          ? await getEvaluationResult(moleculeId, taskId)
          : await getEvaluationResult(moleculeId);
        if (cancelado) return;
        if (!data) { setResultReadError(t("pr_sel_result_read_error")); return; }
        if (taskId && data.task_id !== taskId) {
          setResultReadError(t("pr_sel_result_identity_mismatch"));
          setBgWaiting(false);
          return;
        }
        if (!Array.isArray(data.anti_target_results)) return;
        setResultReadError(null);
        const map: Record<string, any> = {};
        data.anti_target_results.forEach((t: any) => {
          if (t?.pdb_id) map[t.pdb_id] = t;
        });
        if (Object.keys(map).length === 0) return;
        // Lo que hay en la base ya está guardado, por definición.
        const hadLocalResults = Object.keys(resultsMapRef.current).length > 0;
        const merged = mergeStoredResults(map);
        resultsMapRef.current = merged;
        setResultsMap(merged);
        if (!hadLocalResults) setPersistencia("guardado");
        setBgWaiting(false);
      } catch {
        if (!cancelado) setResultReadError(t("pr_sel_result_read_error"));
      }
    })();
    return () => { cancelado = true; };
    // Sólo al montar o al cambiar de molécula.
  }, [moleculeId, taskId, resultReadAttempt, t]);

  // ── v1.7.4: Auto-poll del panel en background ────────────────────────────
  // El pipeline lanza selectivity_subprocess.py y persiste los resultados en
  // DB cuando termina (selectivity_ran=true). Este effect pollea el endpoint
  // /evaluation/result/{moleculeId} hasta ver el resultado persistido y lo
  // vuelca al resultsMap — la sección se actualiza sola, sin bloquear nada.
  const hasResults = Object.keys(resultsMap).length > 0;
  useEffect(() => {
    if (!autoPoll || !moleculeId || hasResults) return;
    let cancelled = false;
    let pollCount = 0;
    const MAX_POLLS = 120; // 120 × 3s = 6 min máximo de espera en background
    setBgWaiting(true);

    const tick = async () => {
      if (cancelled) return;
      pollCount += 1;
      try {
        const data = taskId
          ? await getEvaluationResult(moleculeId, taskId)
          : await getEvaluationResult(moleculeId);
        if (cancelled || !data) return;
        if (taskId && data.task_id !== taskId) {
          setResultReadError(t("pr_sel_result_identity_mismatch"));
          setBgWaiting(false);
          return;
        }
        setResultReadError(null);
        if (data.selectivity_ran === true && Array.isArray(data.anti_target_results)) {
          const map: Record<string, any> = {};
          data.anti_target_results.forEach((t: any) => {
            if (t?.pdb_id) {
              map[t.pdb_id] = t;
            }
          });
          if (Object.keys(map).length > 0) {
            resultsMapRef.current = map;
            setResultsMap(map);
            setPersistencia("guardado");
            setBgWaiting(false);
            return; // resultado llegó → no programar más ticks
          }
        }
      } catch {
        // endpoint puede no estar listo aún — reintentar en el siguiente tick
      }
      if (pollCount >= MAX_POLLS && !cancelled) {
        setBgWaiting(false); // timeout defensivo: se cae al flujo manual
        return;
      }
      if (!cancelled) {
        timer = window.setTimeout(tick, 3000);
      }
    };

    let timer: any = null;
    // Primer chequeo inmediato; tick() agenda los siguientes.
    tick();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [autoPoll, moleculeId, taskId, hasResults, resultReadAttempt, t]);

  const computeMetrics = (currentMap: Record<string, any>) => {
    let worstOffAffinity = 0.0;
    const safetyFlags: string[] = [];
    const safetyMessages: FrontendMessage[] = [];
    const offTargetsList: any[] = [];
    let evaluatedCount = 0;

    // Sobre TODAS las del panel, no sólo las tres de siempre: antes una
    // anti-diana adicional con resultado salía en su tarjeta y no entraba en el
    // peor caso, el veredicto ni las alertas.
    panel.forEach((at) => {
      const r = currentMap[at.pdb_id];
      if (r) {
        offTargetsList.push(r);
        const aff = r.affinity;
        const thresh = r.threshold ?? at.threshold;
        if (aff !== null && aff !== undefined && aff < 0) {
          evaluatedCount++;
          if (aff <= thresh) {
            safetyFlags.push(`ALERTA ${r.name || at.name}: Afinidad potente (${aff.toFixed(1)} kcal/mol) rebasó el umbral crítico (${thresh.toFixed(1)} kcal/mol). Riesgo: ${r.risk || at.risk}`);
            safetyMessages.push(frontendMessage("pr_sel_alert", { name: r.name || at.name, affinity: aff.toFixed(1), threshold: thresh.toFixed(1),
              risk: (r.risk || at.riskOrigin !== "frontend") ? (r.risk || at.risk) : antiTargetFieldMessage(at.pdb_id, "risk", at.risk) }));
          }
          if (aff < worstOffAffinity) {
            worstOffAffinity = aff;
          }
        }
      }
    });

    // ΔΔG = ΔG_off − ΔG_on, en kcal/mol. Ver `lib/selectividadMargen.ts`:
    // el cociente ΔG_on/ΔG_off que había aquí no es una razón de selectividad,
    // y sus umbrales no coincidían con los del backend para la misma corrida.
    const deltaDeltaG = margenDeSelectividad(
      onTargetAffinity != null && onTargetAffinity < 0 ? onTargetAffinity : null,
      worstOffAffinity < 0 ? worstOffAffinity : null,
    );

    let verdict = VEREDICTO_SIN_DATOS;
    if (deltaDeltaG !== null) {
      verdict = veredictoDeMargen(deltaDeltaG);
    } else if (evaluatedCount > 0) {
      if (safetyFlags.length > 0) {
        verdict = "REVISAR — Se rebasó el umbral definido en anti-targets";
      } else {
        verdict = "SIN ALERTA EN ESTE PANEL — Ningún anti-target rebasó el umbral definido";
      }
    }

    return { deltaDeltaG, verdict, safetyFlags, safetyMessages, offTargetsList, evaluatedCount };
  };

  /**
   * Un intento fallido de (re)evaluar una anti-diana.
   *
   * Si había un resultado previo con afinidad, SE CONSERVA y el fallo se declara
   * aparte (AMP-10): sobrescribirlo con «failed» hacía que la pantalla mostrara
   * «Sin evaluar» sobre evidencia que la base sigue guardando. Si no había nada
   * previo, queda la fila fallida como siempre.
   */
  const resolverFallo = (
    at: AntiTargetInfo,
    previo: any,
    e: any,
    base: Record<string, any>,
  ): Record<string, any> => {
    const motivo = presentError(e, t) || t("pr_sel_fallo_docking");
    if (e?.status === 409) setAmpliacionNoDisponible(motivo);
    const teniaResultado = previo != null && previo.affinity !== null && previo.affinity !== undefined;
    if (teniaResultado) {
      setAvisoDeReevaluacion((prev) => ({ ...prev, [at.pdb_id]: motivo }));
      return { ...base, [at.pdb_id]: previo };
    }
    return {
      ...base,
      [at.pdb_id]: {
        pdb_id: at.pdb_id,
        name: at.name,
        category: at.category,
        risk: at.risk,
        threshold: at.threshold,
        status: "failed",
        error: motivo,
        affinity: null,
      },
    };
  };

  const handleRunSingle = async (at: AntiTargetInfo) => {
    if (!moleculeId) return;
    const previo = resultsMapRef.current[at.pdb_id];
    locallyEvaluatedIds.current.add(at.pdb_id);
    setAvisoDeReevaluacion((prev) => {
      const { [at.pdb_id]: _quitado, ...resto } = prev;
      return resto;
    });
    setActiveTargetId(at.pdb_id);

    const runningMap = {
      ...resultsMapRef.current,
      [at.pdb_id]: {
        pdb_id: at.pdb_id,
        name: at.name,
        category: at.category,
        risk: at.risk,
        threshold: at.threshold,
        status: "running",
        affinity: null,
      },
    };
    resultsMapRef.current = runningMap;
    setResultsMap(runningMap);

    try {
      const res = taskId
        ? await dockSingleAntiTarget(moleculeId, at.pdb_id, taskId)
        : await dockSingleAntiTarget(moleculeId, at.pdb_id);
      if (!sessionActive.current) return;
      if (taskId && res.target.task_id !== taskId) {
        throw Object.assign(new Error(t("pr_sel_result_identity_mismatch")), { status: 409 });
      }
      const targetRes = res.target;

      // El guardado NO va dentro del actualizador de estado: React puede
      // invocarlo dos veces (StrictMode) y no garantiza cuándo, así que un
      // efecto de red ahí dentro se dispara de más o tarde. Se calcula el
      // siguiente mapa aquí, se persiste, y luego se aplica.
      const nextMap = { ...resultsMapRef.current, [at.pdb_id]: targetRes };
      resultsMapRef.current = nextMap;
      setResultsMap(nextMap);

      const { deltaDeltaG, verdict, safetyFlags, offTargetsList } = computeMetrics(nextMap);
      const fullObj = {
        on_target: { pdb_id: "Target Principal", affinity_kcal: onTargetAffinity },
        off_targets: offTargetsList,
        selectivity_delta_delta_g: deltaDeltaG,
        selectivity_verdict: verdict,
        safety_flags: safetyFlags,
      };
      if (onUpdateResult) onUpdateResult(fullObj);
      guardar(fullObj);
    } catch (e: any) {
      if (!sessionActive.current) return;
      const restaurado = resolverFallo(at, previo, e, resultsMapRef.current);
      resultsMapRef.current = restaurado;
      setResultsMap(restaurado);
    } finally {
      setActiveTargetId(null);
    }
  };

  const handleRunAll = async () => {
    if (!moleculeId || seleccionBloqueada || seleccionadosParaEvaluar.length === 0) return;
    setIsRunning(true);

    let currentMap = { ...resultsMapRef.current };
    setAvisoDeReevaluacion({});

    // La tanda se fija al empezar: elegir o desmarcar mientras corre no cambia lo que ya está en marcha.
    for (const at of [...seleccionadosParaEvaluar]) {
      const previo = currentMap[at.pdb_id];
      locallyEvaluatedIds.current.add(at.pdb_id);
      setActiveTargetId(at.pdb_id);
      const runningMap = {
        ...resultsMapRef.current,
        [at.pdb_id]: {
          pdb_id: at.pdb_id,
          name: at.name,
          category: at.category,
          risk: at.risk,
          threshold: at.threshold,
          status: "running",
          affinity: null,
        },
      };
      resultsMapRef.current = runningMap;
      setResultsMap(runningMap);

      try {
        const res = taskId
          ? await dockSingleAntiTarget(moleculeId, at.pdb_id, taskId)
          : await dockSingleAntiTarget(moleculeId, at.pdb_id);
        if (!sessionActive.current) return;
        if (taskId && res.target.task_id !== taskId) {
          throw Object.assign(new Error(t("pr_sel_result_identity_mismatch")), { status: 409 });
        }
        currentMap = { ...resultsMapRef.current, [at.pdb_id]: res.target };
      } catch (e: any) {
        if (!sessionActive.current) return;
        currentMap = resolverFallo(at, previo, e, resultsMapRef.current);
        // Un 409 vale para TODA la evaluación: seguir con las demás
        // anti-dianas sólo repetiría el mismo rechazo.
        if (e?.status === 409) {
          resultsMapRef.current = { ...currentMap };
          setResultsMap({ ...currentMap });
          break;
        }
      }

      resultsMapRef.current = { ...currentMap };
      setResultsMap({ ...currentMap });

      // ── Se guarda CADA anti-target en cuanto sale ──────────────────────
      //
      // DOC 71, DEFECTO B2, y el fondo del asunto. Antes este bucle corría los
      // ocho objetivos y guardaba UNA sola vez, después del último. Un panel
      // completo tarda minutos; si el usuario cambiaba de pestaña a la mitad,
      // el componente se desmontaba y todo lo acoplado hasta ahí se perdía sin
      // haber llegado nunca a la base.
      //
      // Ahora cada resultado se persiste al salir. El backend fusiona por
      // `pdb_id`, así que una tanda interrumpida deja escrito exactamente lo
      // que alcanzó a calcular, y al volver a la pestaña se lee de la base.
      // Repetir el panel ya no repite el trabajo hecho.
      const parcial = computeMetrics(currentMap);
      const objetoParcial = {
        on_target: { pdb_id: "Target Principal", affinity_kcal: onTargetAffinity },
        off_targets: parcial.offTargetsList,
        selectivity_delta_delta_g: parcial.deltaDeltaG,
        selectivity_verdict: parcial.verdict,
        safety_flags: parcial.safetyFlags,
      };
      if (onUpdateResult) onUpdateResult(objetoParcial);
      guardar(objetoParcial);
    }

    setActiveTargetId(null);
    setIsRunning(false);
  };

  const { deltaDeltaG, safetyFlags, safetyMessages, evaluatedCount } = computeMetrics(resultsMap);
  const completedCount = panel.filter((at) => resultsMap[at.pdb_id]?.status === "ok" || (resultsMap[at.pdb_id]?.affinity !== null && resultsMap[at.pdb_id]?.affinity !== undefined)).length;

  /**
   * Las anti-dianas que intentaron evaluarse y no dieron afinidad.
   *
   * `sin_sitio` (el catálogo no tiene una caja calibrada) y `desconocida` (se
   * pidió una que no existe en este equipo) son las dos formas que tiene el
   * backend de abstenerse en vez de acoplar contra el origen del sistema de
   * coordenadas, que es lo que hacía antes. Ambas dejan el cociente calculado
   * sobre menos anti-dianas de las que el usuario cree.
   */
  const noEvaluadas = panel.filter((at) => {
    const res = resultsMap[at.pdb_id];
    return res != null && res.affinity == null;
  }).map((at) => at.pdb_id);

  // El color sale de la MISMA escala que el veredicto, no de umbrales propios.
  const ratioColor =
    deltaDeltaG === null
      ? safetyFlags.length > 0
        ? "#ef4444"
        : evaluatedCount > 0
          ? "#10b981"
          : "#64748b"
      : colorDeMargen(deltaDeltaG);

  return (
    <div className="space-y-4 font-sans text-sm sm:text-sm">
      {resultReadError && (
        <div role="alert" className="rounded-xl border border-amber-500/40 bg-amber-950/25 px-3 py-2 text-base leading-6 text-amber-100">
          <p>{resultReadError}</p>
          <button type="button" onClick={() => setResultReadAttempt((value) => value + 1)}
            className="mt-2 min-h-11 rounded-lg border border-current/30 px-3 py-2 text-sm font-semibold focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-amber-300">
            {t("ev_reintentar_recuperacion")}
          </button>
        </div>
      )}
      {/* DOC 71, B1/B2: un resultado que no se guardó no puede presentarse como
          uno que sí. Sin este aviso, el usuario cambia de pestaña, lo pierde, y
          el dossier declara que nunca se corrió un panel de anti-targets. */}
      {persistencia === "fallido" && (
        <div
          role="alert"
          className="rounded-xl border border-amber-500/40 bg-amber-950/25 px-3 py-2 font-mono text-sm text-amber-200"
        >
          <span className="font-bold uppercase tracking-wider">{t("pr_sel_sin_guardar")}</span>{" "}
          {t("auto_49e5b55bba06")}
          {errorAlGuardar ? <span className="text-amber-300"> ({errorAlGuardar})</span> : null}
        </div>
      )}

      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/10 pb-3">
        <div className="flex min-w-0 items-center gap-2 font-sans">
          <ShieldCheck size={18} className="text-purple-400" />
          <span className="font-black uppercase tracking-wider text-zinc-200 text-sm sm:text-sm">
            {t("pr_sel_titulo")}
          </span>
        </div>

      </div>

      {/* AMP-10: la ampliación no está disponible para esta evaluación (409). Lo
          ya registrado se conserva y aquí se dice por qué no se puede ampliar. */}
      {ampliacionNoDisponible !== null && (
        <div
          role="alert"
          className="rounded-xl border border-amber-500/40 bg-amber-950/25 px-3 py-2 font-sans text-base leading-6 text-amber-100"
        >
          <strong className="font-semibold">{t("pr_sel_ampliacion_no_disponible_titulo")}</strong>{" "}
          {t("pr_sel_ampliacion_no_disponible", { motivo: ampliacionNoDisponible })}
        </div>
      )}

      {/* v1.7.4: banner de background — el pipeline ya lanzó el subprocess */}
      {bgWaiting && (
        <div className="flex items-center gap-2.5 rounded-xl border border-purple-500/25 bg-purple-950/30 px-3.5 py-2.5 font-mono text-sm text-purple-200">
          <Loader2 size={14} className="animate-spin text-purple-300 shrink-0" />
          <span>
            {t("pr_sel_en_background")}
          </span>
        </div>
      )}

      {/* Global Metrics Gauge Card */}
      <div className="bg-black/40 p-4 rounded-xl border border-white/10 space-y-3.5">
        <div className="flex items-center gap-4">
          <div
            className="shrink-0 w-16 h-16 rounded-2xl border-2 flex items-center justify-center flex-col shadow-inner"
            style={{ borderColor: ratioColor + "80", backgroundColor: ratioColor + "15" }}
          >
            {/* La cifra grande es ΔΔG en kcal/mol, no un «2.3x» sin unidades.
                El factor que implica va debajo, como intervalo. */}
            <span className="text-lg font-black font-mono leading-none" data-selectivity-color={ratioColor} style={{ color: ratioColor }}>
              {deltaDeltaG !== null
                ? `${deltaDeltaG > 0 ? "+" : ""}${deltaDeltaG.toFixed(1)}`
                : evaluatedCount > 0
                  ? t("pr_sel_completed")
                  : "—"}
            </span>
            <span className="text-sm text-zinc-400 font-sans uppercase font-bold leading-tight">
              {deltaDeltaG !== null ? "kcal/mol" : t("c_estado")}
            </span>
          </div>

          <div className="flex-1 min-w-0">
            <span className="text-sm font-sans text-zinc-400 uppercase tracking-widest block mb-0.5 font-bold">
              {t("pr_sel_resumen")}
            </span>
            <p className="text-base sm:text-base font-bold leading-6 font-sans" data-selectivity-color={ratioColor} style={{ color: ratioColor }}>
              {deltaDeltaG !== null || evaluatedCount === 0 ? t(claveDeVeredicto(deltaDeltaG)) : t(safetyFlags.length > 0 ? "pr_sel_threshold_review" : "pr_sel_threshold_clear")}
            </p>
            {/* SCI-A-037: aquí se enseñaba un «factor implicado» (5.4x – 4651x) a
                partir de la diferencia de scores. Convertir esa diferencia en una
                razón de unión no está validado; se dice lo que es. */}
            {deltaDeltaG !== null && (
              <p className="mt-1 font-sans text-base leading-6 text-zinc-300">
                {t("pr_sel_margen_no_es_razon", { incertidumbre: INCERTIDUMBRE_VINA_KCAL })}
              </p>
            )}

            <div className="flex flex-wrap items-center gap-3 mt-1.5 font-mono text-sm text-zinc-400">
              <span>{t("pn_anti_cobertura_registrada")} <strong className="text-zinc-200">{completedCount}/{panel.length}</strong> {t("pr_sel_evaluated")}</span>
              {onTargetAffinity !== null && onTargetAffinity !== undefined && (
                <span>{t("auto_7b9af481625f")} <strong className="text-purple-300">{onTargetAffinity.toFixed(1)} kcal/mol</strong></span>
              )}
            </div>

            {/* El cociente es un MÍNIMO sobre lo que se llegó a evaluar: si
                alguna anti-diana no se pudo acoplar, un veredicto de «altamente
                selectivo» puede deberse a la que falta. El backend manda el
                estado de cada una; aquí se cuenta lo que no opinó. */}
            {noEvaluadas.length > 0 && (
              <p
                role="status"
                className="mt-2 rounded-lg border border-amber-500/25 bg-amber-500/[0.05] px-2.5 py-2 text-base leading-6 text-amber-100 font-sans"
              >
                <strong className="font-semibold">{t("pr_sel_incomplete_coverage")}</strong>{" "}
                {noEvaluadas.length === 1 ? t("auto_fff211e08ae8") : t("pr_frontend_101", { v0: noEvaluadas.length })}
                {" "}({noEvaluadas.join(", ")}{t("auto_5c7c8c2f3b8e")}
              </p>
            )}
          </div>
        </div>

        {/* Progress Bar */}
        <div className="w-full bg-zinc-900 h-2 rounded-full overflow-hidden border border-white/5">
          <div
            className="h-full bg-purple-500 transition-all duration-300"
            style={{ width: `${panel.length > 0 ? (completedCount / panel.length) * 100 : 0}%` }}
          />
        </div>

        {/* Safety Warnings / Compliance Status */}
        {evaluatedCount > 0 && (
          <div>
            {safetyFlags.length > 0 ? (
              <div className="rounded-xl border border-rose-500/30 bg-rose-950/40 p-3.5 space-y-1.5 font-mono text-sm">
                <span className="font-bold text-rose-300 uppercase tracking-wider block mb-1 flex items-center gap-2">
                  <AlertTriangle size={15} className="text-rose-400" /> {safetyFlags.length} {t("auto_6b882e73c6d3")}
                </span>
                {safetyMessages.map((flag, idx) => (
                  <div key={idx} className="text-rose-200 leading-6 font-sans font-medium text-base">
                    • {flag.render(t)}
                  </div>
                ))}
              </div>
            ) : (
              <div className="rounded-xl border border-emerald-500/30 bg-emerald-950/30 p-3.5 font-mono text-sm text-emerald-300 flex items-center gap-2">
                <CheckCircle2 size={16} className="text-emerald-400 shrink-0" />
                <span className="font-bold">{t("pr_sel_sin_conclusion")}</span>
              </div>
            )}
          </div>
        )}
      </div>

      {Object.keys(resultsMap).length > 0 && <div className="space-y-1 text-sm text-zinc-300" role="status">
        <p className="break-words text-base leading-6">{t("pn_anti_pedidas", { ids: Object.keys(resultsMap).join(", ") })}</p>
        <p className="break-words text-base leading-6">{t("pn_anti_acopladas", { ids: Object.values(resultsMap).filter((row) => typeof row.affinity === "number" && Number.isFinite(row.affinity)).map((row) => row.pdb_id).join(", ") || t("pn_anti_cero") })}</p>
      </div>}

      {/* Anti-Targets 1-by-1 Cards List */}
      <div className="grid min-w-0 items-stretch gap-5 lg:grid-cols-[minmax(0,23rem)_minmax(0,1fr)]">
        <aside className="min-w-0 rounded-xl border border-white/10 bg-black/30 p-4">
          <AntiDianasSelector catalogo targets={anti.targets} selected={idsElegidos} onChange={setSeleccion} error={anti.error} onRetry={anti.retry} disabled={seleccionBloqueada} />
        </aside>
        {/* En dos columnas, el catálogo fija la altura; las tarjetas crecen dentro de su scroll. */}
        <section aria-label={t("pr_sel_anti_targets")} className="flex min-h-0 min-w-0 flex-col gap-3 lg:[contain:size]">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0 space-y-1">
              <h3 id={panelTitleId} className="text-base font-semibold text-zinc-100">{t("pr_sel_anti_targets")}</h3>
              <div className="flex flex-wrap gap-x-3 gap-y-1 text-sm leading-6 text-zinc-300" role="status">
                <span>{t("pn_anti_panel_seleccionadas", { n: idsParaEvaluar.length })}</span>
                <span>{t("pn_anti_panel_evaluadas", { n: seleccionadasEvaluadas })}</span>
                {resultadosAnteriores > 0 && <span>{t("pn_anti_panel_anteriores", { n: resultadosAnteriores })}</span>}
              </div>
            </div>
            <button type="button" onClick={handleRunAll} disabled={!moleculeId || seleccionBloqueada || idsParaEvaluar.length === 0 || ampliacionNoDisponible !== null}
              className="inline-flex min-h-11 max-w-full items-center gap-2 rounded-lg bg-purple-600 px-3 py-2 text-sm font-semibold text-white transition-colors hover:bg-purple-500 active:bg-purple-700 disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-purple-400"
              title={bgWaiting ? t("auto_225f4287b89f") : undefined}>
              {bgWaiting ? <><Loader2 size={16} className="shrink-0 animate-spin" aria-hidden="true" />{t("pr_sel_pipeline_running")}</>
                : isRunning ? <><RefreshCw size={16} className="shrink-0 animate-spin" aria-hidden="true" />{t("pr_sel_evaluating_progress", { completed: seleccionadasEvaluadas, total: idsParaEvaluar.length })}</>
                  : <><Play size={16} className="shrink-0 fill-current" aria-hidden="true" />{t("pn_anti_evaluar_seleccionadas", { n: idsParaEvaluar.length })}</>}
            </button>
          </div>
          <p className="text-base leading-6 text-zinc-300">{t("pn_anti_panel_ayuda")}</p>

        <div role="group" aria-labelledby={panelTitleId} tabIndex={0}
          className="custom-scrollbar min-h-0 max-h-[36rem] space-y-3 overflow-y-auto overscroll-auto p-1 focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-purple-400 lg:max-h-none lg:flex-1">
        {panel.length === 0 && (
          <p role="status" className="rounded-xl border border-white/10 bg-black/40 p-3 font-sans text-base text-zinc-400 leading-6">
            {t("pn_anti_panel_vacio")}
          </p>
        )}

        {panel.map((at) => {
          const res = resultsMap[at.pdb_id];
          const isTargetRunning = activeTargetId === at.pdb_id || res?.status === "running";
          const aff = res?.affinity;
          const thresh = res?.threshold ?? at.threshold;
          const hasAffinity = aff !== null && aff !== undefined;
          const isDanger = hasAffinity && aff <= thresh;

          return (
            <div
              key={at.pdb_id}
              className={`p-4 rounded-xl border transition-all duration-200 flex flex-col sm:flex-row sm:items-center justify-between gap-3.5 ${
                isDanger
                  ? "border-rose-500/40 bg-rose-950/30"
                  : hasAffinity
                  ? "border-emerald-500/30 bg-emerald-950/20"
                  : "border-white/10 bg-black/40"
              }`}
            >
              <div className="space-y-1.5 flex-1 min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-mono font-bold text-zinc-200 text-sm px-2 py-0.5 rounded bg-zinc-800 border border-white/10">
                    {at.pdb_id}
                  </span>
                  <span className="font-bold text-white text-sm sm:text-sm truncate">{at.name}</span>
                  <span className="text-sm font-sans px-2 py-0.5 rounded bg-purple-500/20 text-purple-300 border border-indigo-500/30 font-bold uppercase">
                    {at.category}
                  </span>
                  {!idsElegidos.includes(at.pdb_id) && <span className="text-sm text-zinc-400">{t("pn_anti_resultado_anterior")}</span>}
                  {hasAffinity && (
                    <span className={`text-sm font-sans px-2 py-0.5 rounded font-bold uppercase ${isDanger ? "bg-rose-500/20 text-rose-300 border border-rose-500/30" : "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"}`}>
                      {isDanger ? t("auto_5542e5a19746") : t("auto_1351ada0b9c9")}
                    </span>
                  )}
                </div>
                <p className="text-base text-zinc-300 font-sans leading-6">{at.riskOrigin === "frontend" ? antiTargetFieldText(at.pdb_id, "risk", at.risk, t) : at.risk}</p>
                <div className="flex flex-wrap items-center gap-3 text-sm font-mono">
                  <span className="text-zinc-400">
                    {t("pr_sel_umbral_minimo")} <strong className="text-zinc-200">{thresh.toFixed(1)} kcal/mol</strong>
                  </span>
                  <button
                    onClick={() => setSelectedDetail({ at, aff, isDanger, thresh })}
                    className="text-purple-400 hover:text-purple-300 flex items-center gap-1 font-bold underline cursor-pointer text-sm"
                  >
                    <BookOpen size={12} />
                    {t("pr_sel_saber_mas")}
                  </button>
                </div>
              </div>

              {/* Status & Single Run Button */}
              <div className="flex items-center gap-3 shrink-0 self-end sm:self-center font-mono">
                <div className="text-right">
                  <span className="text-sm text-zinc-400 block uppercase font-sans font-semibold">{t("se_cmp_affinity")}</span>
                  {isTargetRunning ? (
                    <span className="text-amber-400 font-bold animate-pulse text-sm flex items-center gap-1.5">
                      <RefreshCw size={13} className="animate-spin" /> {t("pr_sel_evaluating")}
                    </span>
                  ) : hasAffinity ? (
                    <span className={`text-sm font-black ${isDanger ? "text-rose-400" : "text-emerald-400"}`}>
                      {aff.toFixed(1)} kcal/mol
                    </span>
                  ) : (
                    <span className="text-zinc-400 text-sm font-bold">{t("pr_sel_sin_evaluar")}</span>
                  )}
                  {avisoDeReevaluacion[at.pdb_id] && (
                    <span role="status" className="mt-1 block max-w-[16rem] font-sans text-sm leading-snug text-amber-300">
                      {t("pr_sel_reevaluacion_fallida", { motivo: avisoDeReevaluacion[at.pdb_id] })}
                    </span>
                  )}
                </div>

                <button
                  onClick={() => handleRunSingle(at)}
                  disabled={!moleculeId || seleccionBloqueada || isTargetRunning || ampliacionNoDisponible !== null}
                  className="min-h-11 px-3.5 py-1.5 rounded-xl border border-white/10 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 font-sans font-bold text-sm uppercase tracking-wider transition-all disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
                >
                  {hasAffinity ? t("pr_sel_reevaluate") : t("pr_sel_evaluate")}
                </button>
              </div>
            </div>
          );
        })}
        </div>
        </section>
      </div>

      {/* Modal Educativo y de Optimización SAR t("pr_sel_saber_mas") */}
      {isActive && selectedDetail && typeof window !== "undefined" && createPortal(
        <div
          className="fixed inset-0 z-[99999] flex items-center justify-center p-4 bg-black/80 backdrop-blur-md font-sans"
          onClick={() => setSelectedDetail(null)}
        >
          <div
            className="bg-zinc-950 border border-purple-500/20 rounded-2xl p-6 max-w-lg w-full shadow-2xl relative text-left space-y-4 max-h-[85vh] overflow-y-auto custom-scrollbar"
            onClick={(e) => e.stopPropagation()}
          >
            <button
              onClick={() => setSelectedDetail(null)}
              className="absolute top-4 right-4 text-zinc-400 hover:text-white transition-colors cursor-pointer"
            >
              <X size={18} />
            </button>

            {/* Modal Header */}
            <div className="flex items-center gap-2.5 border-b border-white/10 pb-3 font-mono">
              <span className="font-bold text-zinc-200 text-sm px-2 py-0.5 rounded bg-zinc-800 border border-white/10">
                {selectedDetail.at.pdb_id}
              </span>
              <h3 className="text-sm sm:text-base font-bold uppercase text-white truncate">
                {selectedDetail.at.name}
              </h3>
              <span className="text-sm font-sans px-2 py-0.5 rounded bg-purple-500/20 text-purple-300 border border-indigo-500/30 font-bold uppercase">
                {selectedDetail.at.category}
              </span>
            </div>

            {/* Computed Status & Estimated Ki */}
            <div className="grid grid-cols-2 gap-3 font-mono text-sm">
              <div className="bg-black/50 p-3 rounded-xl border border-white/10 space-y-0.5">
                <span className="text-zinc-400 block font-bold uppercase text-sm">{t("auto_a0e03dfc2c9a")}</span>
                {selectedDetail.aff !== null && selectedDetail.aff !== undefined ? (
                  <span className={`text-sm font-black ${selectedDetail.isDanger ? "text-rose-400" : "text-emerald-400"}`}>
                    {selectedDetail.aff.toFixed(1)} kcal/mol
                  </span>
                ) : (
                  <span className="text-zinc-400 font-bold">{t("pr_sel_sin_evaluar")}</span>
                )}
              </div>

              <div className="bg-black/50 p-3 rounded-xl border border-white/10 space-y-0.5">
                <span className="text-zinc-400 block font-bold uppercase text-sm">
                  {t("pr_sel_concentracion")}
                </span>
                {selectedDetail.aff !== null && selectedDetail.aff !== undefined ? (
                  (() => {
                    const banda = bandaDeConcentracion(selectedDetail.aff);
                    return (
                      <>
                        <span className="text-sm font-black text-purple-300">
                          {banda.inferior} – {banda.superior}
                        </span>
                        <span className="block text-sm leading-relaxed text-zinc-400">
                          {t("auto_2033c07d6b2e")} {banda.ordenes.toFixed(1)} {t("auto_d1728e225254")}{INCERTIDUMBRE_VINA_KCAL} kcal/mol.
                        </span>
                      </>
                    );
                  })()
                ) : (
                  <span className="text-zinc-400 font-bold">—</span>
                )}
              </div>
            </div>

            {/* La advertencia va PEGADA al número, no en un pie de página.
                Separarla del dato es lo que permite leer el dato sin ella. */}
            <p className="rounded-xl border border-amber-500/25 bg-amber-500/[0.05] p-3 text-base leading-6 text-amber-100 font-sans">
              <strong className="font-semibold">{t("pr_sel_no_es_ki")}</strong>{" "}
              {t("auto_3a94369c8527")}{INCERTIDUMBRE_VINA_KCAL} {t("auto_e2dcdd634166")}
            </p>

            {/* Sólo algunas anti-dianas traen ficha explicativa escrita a mano. Las
                demás —casi todas, desde que el panel sale del API— enseñan el
                riesgo que el API declara y dicen que no hay ficha, en vez de
                tres secciones vacías. */}
            {!selectedDetail.at.targetFunction && !selectedDetail.at.bioDetails && !selectedDetail.at.mitigationSar && (
              <div className="space-y-2">
                {selectedDetail.at.risk && (
                  <p className="text-base text-zinc-300 leading-6 font-sans bg-rose-950/20 p-3 rounded-xl border border-rose-500/20">
                    {selectedDetail.at.riskOrigin === "frontend" ? antiTargetFieldText(selectedDetail.at.pdb_id, "risk", selectedDetail.at.risk, t) : selectedDetail.at.risk}
                  </p>
                )}
                <p className="text-base text-zinc-400 leading-6 font-sans">{t("pn_anti_sin_ficha")}</p>
              </div>
            )}

            {/* Function & Pathophysiology */}
            {selectedDetail.at.targetFunction && (
              <div className="space-y-2">
                <h4 className="text-base font-sans font-bold uppercase tracking-wider text-purple-300 flex items-center gap-1.5">
                  <Activity size={14} /> {t("pr_sel_funcion_biologica")}
                </h4>
                <p className="text-base text-zinc-300 leading-6 font-sans bg-black/30 p-3 rounded-xl border border-white/5">
                  {antiTargetFieldText(selectedDetail.at.pdb_id, "targetFunction", selectedDetail.at.targetFunction, t)}
                </p>
              </div>
            )}

            {selectedDetail.at.bioDetails && (
              <div className="space-y-2">
                <h4 className="text-base font-sans font-bold uppercase tracking-wider text-rose-300 flex items-center gap-1.5">
                  <AlertTriangle size={14} /> {t("pr_sel_relevancia_clinica")}
                </h4>
                <p className="text-base text-zinc-300 leading-6 font-sans bg-rose-950/20 p-3 rounded-xl border border-rose-500/20">
                  {antiTargetFieldText(selectedDetail.at.pdb_id, "bioDetails", selectedDetail.at.bioDetails, t)}
                </p>
              </div>
            )}

            {/* Medicinal Chemistry Mitigation SAR */}
            {selectedDetail.at.mitigationSar && (
              <div className="space-y-2">
                <h4 className="text-base font-sans font-bold uppercase tracking-wider text-emerald-300 flex items-center gap-1.5">
                  <Sparkles size={14} /> {t("pr_sel_optimizacion")}
                </h4>
                <p className="text-base text-zinc-300 leading-6 font-sans bg-emerald-950/20 p-3 rounded-xl border border-emerald-500/20">
                  {antiTargetFieldText(selectedDetail.at.pdb_id, "mitigationSar", selectedDetail.at.mitigationSar, t)}
                </p>
              </div>
            )}
          </div>
        </div>,
        document.body
      )}
    </div>
  );
};
