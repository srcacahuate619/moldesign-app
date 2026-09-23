import React, { useState, useEffect, useRef } from "react";
import { useLanguage } from "../../../context/LanguageContext";
import { createPortal } from "react-dom";
import { ShieldCheck, Play, RefreshCw, AlertTriangle, CheckCircle2, ShieldAlert, Cpu, Activity, BookOpen, Sparkles, X, Info, Loader2 } from "lucide-react";
import { dockSingleAntiTarget, saveSelectivityResults } from "../../../lib/proApi";
import { getEvaluationResult } from "../../../lib/api";
import {
  INCERTIDUMBRE_VINA_KCAL,
  VEREDICTO_SIN_DATOS,
  bandaDeFactor,
  colorDeMargen,
  formatearFactor,
  margenDeSelectividad,
  veredictoDeMargen,
} from "../../../lib/selectividadMargen";

interface AntiTargetInfo {
  pdb_id: string;
  name: string;
  category: string;
  risk: string;
  threshold: number;
  targetFunction: string;
  bioDetails: string;
  mitigationSar: string;
}

interface ProSelectivityPanelProps {
  moleculeId: string | null;
  onTargetAffinity?: number | null;
  initialResult?: any;
  onUpdateResult?: (res: any) => void;
  /** v1.7.4: el pipeline lanzó el panel en background (subprocess). El panel
   *  pollea /evaluation/result/{moleculeId} y puebla los resultados cuando
   *  el subprocess persiste (selectivity_ran=true). NO bloquea el pipeline. */
  autoPoll?: boolean;
}

const DEFAULT_ANTI_TARGETS: AntiTargetInfo[] = [
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
    pdb_id: "4NC3",
    name: "5-HT2B (HTR2B)",
    category: "CNS/Safety",
    risk: "Agonismo de 5-HT2B causa valvulopatía cardíaca e hipertensión pulmonar.",
    threshold: -7.5,
    targetFunction: "Receptor serotoninérgico acoplado a proteína Gq/11 modulador de la proliferación celular en tejido valvular y vascular.",
    bioDetails: "El agonismo prolongado de 5-HT2B estimula la mitogénesis y proliferación aberrante de fibroblastos en las válvulas del corazón, produciendo fibrosis valvular irreversible y regurgitación aórtica/mitral (caso histórico Fenfluramina / Dexfenfluramina), así como hipertensión arterial pulmonar.",
    mitigationSar: "Estrategias de Optimización SAR: Eliminar o modificar farmacóforos triptamínicos básicos; sustituir aminas secundarias por grupos voluminosos o amidas no protonables; verificar el modo de enlace para asegurar comportamiento como antagonista neutro en lugar de agonista."
  },
  {
    pdb_id: "1SO2",
    name: "PDE3A",
    category: "Cardiac",
    risk: "Inhibición de PDE3 afecta contractilidad y frecuencia cardíaca.",
    threshold: -8.0,
    targetFunction: "Fosfodiesterasa específica de nucleótidos cíclicos (cAMP) reguladora de la contractilidad celular en miocardio y musculatura lisa vascular.",
    bioDetails: "La inhibición aguda de PDE3A eleva los niveles intracelulares de cAMP, ejerciendo efectos inotrópicos positivos; sin embargo, su inhibición crónica en fármacos no cardiotónicos aumenta la tasa de mortalidad en pacientes con arritmias ventriculares.",
    mitigationSar: "Estrategias de Optimización SAR: Distorsionar los motivos planos bicíclicos que imitan al anillo purínico del cAMP; modificar la distancia entre el dador de puente de hidrógeno y la cavidad lipofílica de PDE3."
  },
  {
    pdb_id: "6MVW",
    name: "NaV1.5 (SCN5A)",
    category: "Cardiac",
    risk: "Bloqueo de canales de sodio miocardíacos altera conducción eléctrica.",
    threshold: -7.5,
    targetFunction: "Canal de sodio dependiente de voltaje responsable de la despolarización rápida (Fase 0) del potencial de acción miocárdico.",
    bioDetails: "El bloqueo de NaV1.5 disminuye la velocidad de conducción del impulso cardíaco, prolongando el intervalo QRS y la onda P. El bloqueo no deseado puede desencadenar arritmias ventriculares reentrantes o Síndrome de Brugada inducido por fármacos.",
    mitigationSar: "Estrategias de Optimización SAR: Disminuir la lipofilicidad del fragmento que interacciona con los residuos aromáticos Phe1760 y Tyr1767 en el segmento S6 del dominio IV; agregar sustituyentes voluminosos que impidan la entrada al poro interno."
  }
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

export const ProSelectivityPanel: React.FC<ProSelectivityPanelProps> = ({
  moleculeId,
  onTargetAffinity = null,
  initialResult,
  onUpdateResult,
  autoPoll = false,
}) => {
  const { t } = useLanguage();
  const [resultsMap, setResultsMap] = useState<Record<string, any>>({});
  // Espejo del mapa para poder componer el siguiente estado fuera del
  // actualizador sin leer una versión obsoleta en una tanda de dockings.
  const resultsMapRef = useRef<Record<string, any>>({});
  const [isRunning, setIsRunning] = useState(false);
  const [activeTargetId, setActiveTargetId] = useState<string | null>(null);
  // v1.7.4: true mientras el pipeline corre el panel en background y el
  // frontend espera el resultado persistido (polling de /evaluation/result).
  const [bgWaiting, setBgWaiting] = useState(false);
  // DOC 71, DEFECTOS B1 y B2 — LO QUE DE VERDAD LOS ARREGLA.
  //
  // Este panel se monta dentro de `{advancedTab === "selectivity" && ...}`, así
  // que cambiar de pestaña lo DESMONTA y su estado en memoria muere. Ese es el
  // defecto: no que faltara un aviso, sino que el resultado sólo vivía aquí.
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

  const guardar = (objeto: Parameters<typeof saveSelectivityResults>[1]) => {
    if (!moleculeId) {
      // Sin evaluación a la que anclarlo no hay nada que guardar, y el usuario
      // tiene que saberlo antes de cambiar de pestaña.
      setPersistencia("fallido");
      setErrorAlGuardar(t("pr_sel_sin_evaluacion"));
      return;
    }
    setPersistencia("pendiente");
    saveSelectivityResults(moleculeId, objeto)
      .then(() => { setPersistencia("guardado"); setErrorAlGuardar(null); })
      .catch((e: unknown) => {
        setPersistencia("fallido");
        setErrorAlGuardar(e instanceof Error ? e.message : String(e));
      });
  };

  // Modal para t("pr_sel_saber_mas")
  const [selectedDetail, setSelectedDetail] = useState<{
    at: AntiTargetInfo;
    aff: number | null;
    isDanger: boolean;
    thresh: number;
  } | null>(null);

  // Sync initial result from backend
  useEffect(() => {
    if (initialResult?.off_targets && Array.isArray(initialResult.off_targets)) {
      const map: Record<string, any> = {};
      initialResult.off_targets.forEach((t: any) => {
        if (t?.pdb_id) {
          map[t.pdb_id] = t;
        }
      });
      resultsMapRef.current = map;
      setResultsMap(map);
      setBgWaiting(false);
    }
  }, [initialResult]);

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
        const data = await getEvaluationResult(moleculeId);
        if (cancelado || !data || !Array.isArray(data.anti_target_results)) return;
        const map: Record<string, any> = {};
        data.anti_target_results.forEach((t: any) => {
          if (t?.pdb_id) map[t.pdb_id] = t;
        });
        if (Object.keys(map).length === 0) return;
        // Lo que hay en la base ya está guardado, por definición.
        resultsMapRef.current = map;
        setResultsMap(map);
        setPersistencia("guardado");
        setBgWaiting(false);
      } catch {
        // Sin resultado persistido todavía: el panel arranca vacío, que es
        // lo correcto. No se inventa nada ni se marca como fallido.
      }
    })();
    return () => { cancelado = true; };
    // Sólo al montar o al cambiar de molécula.
  }, [moleculeId]);

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
        const data = await getEvaluationResult(moleculeId);
        if (cancelled || !data) return;
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoPoll, moleculeId, hasResults]);

  const computeMetrics = (currentMap: Record<string, any>) => {
    let worstOffAffinity = 0.0;
    const safetyFlags: string[] = [];
    const offTargetsList: any[] = [];
    let evaluatedCount = 0;

    DEFAULT_ANTI_TARGETS.forEach((at) => {
      const r = currentMap[at.pdb_id];
      if (r) {
        offTargetsList.push(r);
        const aff = r.affinity;
        const thresh = r.threshold ?? at.threshold;
        if (aff !== null && aff !== undefined && aff < 0) {
          evaluatedCount++;
          if (aff <= thresh) {
            safetyFlags.push(`ALERTA ${r.name || at.name}: Afinidad potente (${aff.toFixed(1)} kcal/mol) rebasó el umbral crítico (${thresh.toFixed(1)} kcal/mol). Riesgo: ${r.risk || at.risk}`);
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

    return { deltaDeltaG, verdict, safetyFlags, offTargetsList, evaluatedCount };
  };

  const handleRunSingle = async (at: AntiTargetInfo) => {
    if (!moleculeId) return;
    setActiveTargetId(at.pdb_id);

    setResultsMap((prev) => ({
      ...prev,
      [at.pdb_id]: {
        pdb_id: at.pdb_id,
        name: at.name,
        category: at.category,
        risk: at.risk,
        threshold: at.threshold,
        status: "running",
        affinity: null,
      },
    }));

    try {
      const res = await dockSingleAntiTarget(moleculeId, at.pdb_id);
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
      setResultsMap((prev) => ({
        ...prev,
        [at.pdb_id]: {
          pdb_id: at.pdb_id,
          name: at.name,
          category: at.category,
          risk: at.risk,
          threshold: at.threshold,
          status: "failed",
          error: e?.message || "Fallo en docking local",
          affinity: null,
        },
      }));
    } finally {
      setActiveTargetId(null);
    }
  };

  const handleRunAll = async () => {
    if (!moleculeId || isRunning) return;
    setIsRunning(true);

    let currentMap = { ...resultsMap };

    for (const at of DEFAULT_ANTI_TARGETS) {
      setActiveTargetId(at.pdb_id);
      setResultsMap((prev) => ({
        ...prev,
        [at.pdb_id]: {
          pdb_id: at.pdb_id,
          name: at.name,
          category: at.category,
          risk: at.risk,
          threshold: at.threshold,
          status: "running",
          affinity: null,
        },
      }));

      try {
        const res = await dockSingleAntiTarget(moleculeId, at.pdb_id);
        currentMap[at.pdb_id] = res.target;
      } catch (e: any) {
        currentMap[at.pdb_id] = {
          pdb_id: at.pdb_id,
          name: at.name,
          category: at.category,
          risk: at.risk,
          threshold: at.threshold,
          status: "failed",
          error: e?.message || "Fallo en docking local",
          affinity: null,
        };
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

  const { deltaDeltaG, verdict, safetyFlags, evaluatedCount } = computeMetrics(resultsMap);
  const completedCount = DEFAULT_ANTI_TARGETS.filter((at) => resultsMap[at.pdb_id]?.status === "ok" || (resultsMap[at.pdb_id]?.affinity !== null && resultsMap[at.pdb_id]?.affinity !== undefined)).length;

  /**
   * Las anti-dianas que intentaron evaluarse y no dieron afinidad.
   *
   * `sin_sitio` (el catálogo no tiene una caja calibrada) y `desconocida` (se
   * pidió una que no existe en este equipo) son las dos formas que tiene el
   * backend de abstenerse en vez de acoplar contra el origen del sistema de
   * coordenadas, que es lo que hacía antes. Ambas dejan el cociente calculado
   * sobre menos anti-dianas de las que el usuario cree.
   */
  const noEvaluadas = DEFAULT_ANTI_TARGETS.filter((at) => {
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
    <div className="space-y-4 font-sans text-xs sm:text-sm">
      {/* DOC 71, B1/B2: un resultado que no se guardó no puede presentarse como
          uno que sí. Sin este aviso, el usuario cambia de pestaña, lo pierde, y
          el dossier declara que nunca se corrió un panel de anti-targets. */}
      {persistencia === "fallido" && (
        <div
          role="alert"
          className="rounded-xl border border-amber-500/40 bg-amber-950/25 px-3 py-2 font-mono text-[11px] text-amber-200"
        >
          <span className="font-bold uppercase tracking-wider">{t("pr_sel_sin_guardar")}</span>{" "}
          {t("auto_49e5b55bba06")}
          {errorAlGuardar ? <span className="text-amber-300/70"> ({errorAlGuardar})</span> : null}
        </div>
      )}

      {/* Header & Global Run Action */}
      <div className="flex items-center justify-between border-b border-white/10 pb-3">
        <div className="flex items-center gap-2 font-mono">
          <ShieldCheck size={18} className="text-purple-400" />
          <span className="font-black uppercase tracking-wider text-zinc-200 text-xs sm:text-sm">
            {t("pr_sel_titulo")}
          </span>
        </div>

        <button
          onClick={handleRunAll}
          disabled={!moleculeId || isRunning || activeTargetId !== null || bgWaiting}
          className="flex items-center gap-2 px-3.5 py-1.5 rounded-xl bg-purple-600 hover:bg-purple-500 text-white font-mono font-bold text-xs uppercase tracking-wider transition-all disabled:opacity-40 disabled:cursor-not-allowed shadow-[0_0_12px_rgba(168,85,247,0.25)] cursor-pointer"
          title={bgWaiting ? t("auto_225f4287b89f") : undefined}
        >
          {bgWaiting ? (
            <>
              <Loader2 size={14} className="animate-spin text-white" />
              Pipeline corriendo panel...
            </>
          ) : isRunning ? (
            <>
              <RefreshCw size={14} className="animate-spin text-white" />
              Evaluando ({completedCount}/5)...
            </>
          ) : (
            <>
              <Play size={14} className="fill-white" />
              Evaluar Todos (1 a 1)
            </>
          )}
        </button>
      </div>

      {/* v1.7.4: banner de background — el pipeline ya lanzó el subprocess */}
      {bgWaiting && (
        <div className="flex items-center gap-2.5 rounded-xl border border-purple-500/25 bg-purple-950/30 px-3.5 py-2.5 font-mono text-xs text-purple-200">
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
            <span className="text-lg font-black font-mono leading-none" style={{ color: ratioColor }}>
              {deltaDeltaG !== null
                ? `${deltaDeltaG > 0 ? "+" : ""}${deltaDeltaG.toFixed(1)}`
                : evaluatedCount > 0
                  ? "OK"
                  : "—"}
            </span>
            <span className="text-[9px] text-zinc-400 font-mono uppercase font-bold leading-tight">
              {deltaDeltaG !== null ? "kcal/mol" : t("c_estado")}
            </span>
          </div>

          <div className="flex-1 min-w-0">
            <span className="text-xs font-mono text-zinc-400 uppercase tracking-widest block mb-0.5 font-bold">
              {t("pr_sel_resumen")}
            </span>
            <p className="text-xs sm:text-sm font-bold leading-relaxed" style={{ color: ratioColor }}>
              {verdict}
            </p>
            {/* El factor de selectividad, como banda. ΔΔG hereda la dispersión
                de los dos scores de Vina que lo componen, y en escala
                exponencial ±2 kcal/mol son más de un orden de magnitud: dar
                «4.680x» sería la misma pseudoprecisión que ya se quitó de la
                columna de Ki. */}
            {deltaDeltaG !== null && (
              <p className="mt-1 font-mono text-[11px] leading-relaxed text-zinc-500">
                {t("auto_925e4ecea2df")} {formatearFactor(bandaDeFactor(deltaDeltaG).min)} –{" "}
                {formatearFactor(bandaDeFactor(deltaDeltaG).max)} {t("auto_7167a3bad96d")}{INCERTIDUMBRE_VINA_KCAL} {t("auto_8c4ac216c830")}
              </p>
            )}

            <div className="flex flex-wrap items-center gap-3 mt-1.5 font-mono text-xs text-zinc-400">
              <span>{t("auto_d2bc749a0bc0")} <strong className="text-zinc-200">{completedCount}/5</strong> evaluados</span>
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
                className="mt-2 rounded-lg border border-amber-500/25 bg-amber-500/[0.05] px-2.5 py-2 text-[11px] leading-relaxed text-amber-100/85 font-sans"
              >
                <strong className="font-semibold">Cobertura incompleta.</strong>{" "}
                {noEvaluadas.length === 1 ? t("auto_fff211e08ae8") : `${noEvaluadas.length} anti-dianas no se evaluaron`}
                {" "}({noEvaluadas.join(", ")}{t("auto_5c7c8c2f3b8e")}
              </p>
            )}
          </div>
        </div>

        {/* Progress Bar */}
        <div className="w-full bg-zinc-900 h-2 rounded-full overflow-hidden border border-white/5">
          <div
            className="h-full bg-purple-500 transition-all duration-300"
            style={{ width: `${(completedCount / DEFAULT_ANTI_TARGETS.length) * 100}%` }}
          />
        </div>

        {/* Safety Warnings / Compliance Status */}
        {evaluatedCount > 0 && (
          <div>
            {safetyFlags.length > 0 ? (
              <div className="rounded-xl border border-rose-500/30 bg-rose-950/40 p-3.5 space-y-1.5 font-mono text-xs">
                <span className="font-bold text-rose-300 uppercase tracking-wider block mb-1 flex items-center gap-2">
                  <AlertTriangle size={15} className="text-rose-400" /> {safetyFlags.length} {t("auto_6b882e73c6d3")}
                </span>
                {safetyFlags.map((flag, idx) => (
                  <div key={idx} className="text-rose-200 leading-relaxed font-sans font-medium text-xs">
                    • {flag}
                  </div>
                ))}
              </div>
            ) : (
              <div className="rounded-xl border border-emerald-500/30 bg-emerald-950/30 p-3.5 font-mono text-xs text-emerald-300 flex items-center gap-2">
                <CheckCircle2 size={16} className="text-emerald-400 shrink-0" />
                <span className="font-bold">{t("pr_sel_sin_conclusion")}</span>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Anti-Targets 1-by-1 Cards List */}
      <div className="space-y-3">
        <span className="block text-xs font-mono font-bold uppercase tracking-widest text-zinc-300">
          {t("pr_sel_anti_targets")}
        </span>

        {DEFAULT_ANTI_TARGETS.map((at) => {
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
                  <span className="font-mono font-bold text-zinc-200 text-xs px-2 py-0.5 rounded bg-zinc-800 border border-white/10">
                    {at.pdb_id}
                  </span>
                  <span className="font-bold text-white text-xs sm:text-sm truncate">{at.name}</span>
                  <span className="text-xs font-mono px-2 py-0.5 rounded bg-purple-500/20 text-purple-300 border border-indigo-500/30 font-bold uppercase">
                    {at.category}
                  </span>
                  {hasAffinity && (
                    <span className={`text-[10px] font-mono px-2 py-0.5 rounded font-bold uppercase ${isDanger ? "bg-rose-500/20 text-rose-300 border border-rose-500/30" : "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"}`}>
                      {isDanger ? t("auto_5542e5a19746") : t("auto_1351ada0b9c9")}
                    </span>
                  )}
                </div>
                <p className="text-xs text-zinc-300 font-sans leading-relaxed">{at.risk}</p>
                <div className="flex items-center gap-3 text-xs font-mono">
                  <span className="text-zinc-400">
                    {t("pr_sel_umbral_minimo")} <strong className="text-zinc-200">{thresh.toFixed(1)} kcal/mol</strong>
                  </span>
                  <button
                    onClick={() => setSelectedDetail({ at, aff, isDanger, thresh })}
                    className="text-purple-400 hover:text-purple-300 flex items-center gap-1 font-bold underline cursor-pointer text-xs"
                  >
                    <BookOpen size={12} />
                    {t("pr_sel_saber_mas")}
                  </button>
                </div>
              </div>

              {/* Status & Single Run Button */}
              <div className="flex items-center gap-3 shrink-0 self-end sm:self-center font-mono">
                <div className="text-right">
                  <span className="text-xs text-zinc-400 block uppercase font-mono font-semibold">{t("se_cmp_affinity")}</span>
                  {isTargetRunning ? (
                    <span className="text-amber-400 font-bold animate-pulse text-xs flex items-center gap-1.5">
                      <RefreshCw size={13} className="animate-spin" /> Evaluando...
                    </span>
                  ) : hasAffinity ? (
                    <span className={`text-sm font-black ${isDanger ? "text-rose-400" : "text-emerald-400"}`}>
                      {aff.toFixed(1)} kcal/mol
                    </span>
                  ) : (
                    <span className="text-zinc-400 text-xs font-bold">{t("pr_sel_sin_evaluar")}</span>
                  )}
                </div>

                <button
                  onClick={() => handleRunSingle(at)}
                  disabled={!moleculeId || isRunning || isTargetRunning}
                  className="px-3.5 py-1.5 rounded-xl border border-white/10 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 font-mono font-bold text-xs uppercase tracking-wider transition-all disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
                >
                  {hasAffinity ? "Reevaluar" : "Evaluar"}
                </button>
              </div>
            </div>
          );
        })}
      </div>

      {/* Modal Educativo y de Optimización SAR t("pr_sel_saber_mas") */}
      {selectedDetail && typeof window !== "undefined" && createPortal(
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
              <span className="font-bold text-zinc-200 text-xs px-2 py-0.5 rounded bg-zinc-800 border border-white/10">
                {selectedDetail.at.pdb_id}
              </span>
              <h3 className="text-sm sm:text-base font-bold uppercase text-white truncate">
                {selectedDetail.at.name}
              </h3>
              <span className="text-xs font-mono px-2 py-0.5 rounded bg-purple-500/20 text-purple-300 border border-indigo-500/30 font-bold uppercase">
                {selectedDetail.at.category}
              </span>
            </div>

            {/* Computed Status & Estimated Ki */}
            <div className="grid grid-cols-2 gap-3 font-mono text-xs">
              <div className="bg-black/50 p-3 rounded-xl border border-white/10 space-y-0.5">
                <span className="text-zinc-400 block font-bold uppercase text-[10px]">{t("auto_a0e03dfc2c9a")}</span>
                {selectedDetail.aff !== null && selectedDetail.aff !== undefined ? (
                  <span className={`text-sm font-black ${selectedDetail.isDanger ? "text-rose-400" : "text-emerald-400"}`}>
                    {selectedDetail.aff.toFixed(1)} kcal/mol
                  </span>
                ) : (
                  <span className="text-zinc-500 font-bold">{t("pr_sel_sin_evaluar")}</span>
                )}
              </div>

              <div className="bg-black/50 p-3 rounded-xl border border-white/10 space-y-0.5">
                <span className="text-zinc-400 block font-bold uppercase text-[10px]">
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
                        <span className="block text-[10px] leading-relaxed text-zinc-500">
                          {t("auto_2033c07d6b2e")} {banda.ordenes.toFixed(1)} {t("auto_d1728e225254")}{INCERTIDUMBRE_VINA_KCAL} kcal/mol.
                        </span>
                      </>
                    );
                  })()
                ) : (
                  <span className="text-zinc-500 font-bold">—</span>
                )}
              </div>
            </div>

            {/* La advertencia va PEGADA al número, no en un pie de página.
                Separarla del dato es lo que permite leer el dato sin ella. */}
            <p className="rounded-xl border border-amber-500/25 bg-amber-500/[0.05] p-3 text-[11px] leading-relaxed text-amber-100/85 font-sans">
              <strong className="font-semibold">{t("pr_sel_no_es_ki")}</strong>{" "}
              {t("auto_3a94369c8527")}{INCERTIDUMBRE_VINA_KCAL} {t("auto_e2dcdd634166")}
            </p>

            {/* Function & Pathophysiology */}
            <div className="space-y-2">
              <h4 className="text-xs font-mono font-bold uppercase tracking-wider text-purple-300 flex items-center gap-1.5">
                <Activity size={14} /> {t("pr_sel_funcion_biologica")}
              </h4>
              <p className="text-xs text-zinc-300 leading-relaxed font-sans bg-black/30 p-3 rounded-xl border border-white/5">
                {selectedDetail.at.targetFunction}
              </p>
            </div>

            <div className="space-y-2">
              <h4 className="text-xs font-mono font-bold uppercase tracking-wider text-rose-300 flex items-center gap-1.5">
                <AlertTriangle size={14} /> {t("pr_sel_relevancia_clinica")}
              </h4>
              <p className="text-xs text-zinc-300 leading-relaxed font-sans bg-rose-950/20 p-3 rounded-xl border border-rose-500/20">
                {selectedDetail.at.bioDetails}
              </p>
            </div>

            {/* Medicinal Chemistry Mitigation SAR */}
            <div className="space-y-2">
              <h4 className="text-xs font-mono font-bold uppercase tracking-wider text-emerald-300 flex items-center gap-1.5">
                <Sparkles size={14} /> {t("pr_sel_optimizacion")}
              </h4>
              <p className="text-xs text-zinc-300 leading-relaxed font-sans bg-emerald-950/20 p-3 rounded-xl border border-emerald-500/20">
                {selectedDetail.at.mitigationSar}
              </p>
            </div>
          </div>
        </div>,
        document.body
      )}
    </div>
  );
};
