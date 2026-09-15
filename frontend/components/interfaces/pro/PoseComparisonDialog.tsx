"use client";


import { useLanguage } from "@/context/LanguageContext";
import { useEffect, useState } from "react";
import { useScrollLock } from "@/hooks/useScrollLock";
import { AlertTriangle, ArrowLeftRight, Loader2, X } from "lucide-react";
import { getPoseFile, getProteinFile } from "../../../lib/api";
import { MoleculeViewer3D } from "../../MoleculeViewer3D";

export interface PoseComparisonDialogProps {
  readonly moleculeId: string;
  readonly leftRank: number;
  readonly rightRank: number;
  readonly onClose: () => void;
}

/**
 * El endpoint devuelve el SDF completo de una corrida. Este extractor conserva
 * un registro por pose y usa la misma convención 1-indexada que el backend
 * (`pose_rank=1` es la primera pose del archivo); nunca inventa coordenadas.
 */
export function extractPoseFromSdf(sdf: string, rank: number): string | null {
  if (!Number.isInteger(rank) || rank < 1) return null;
  const records = sdf
    .split(/\$\$\$\$\s*/)
    .map((record) => record.trim())
    .filter((record) => record.includes("M  END"));
  const record = records[rank - 1];
  return record ? `${record}\n$$$$\n` : null;
}

export function PoseComparisonDialog({
  moleculeId,
  leftRank,
  rightRank,
  onClose,
}: PoseComparisonDialogProps) {
  const { t } = useLanguage();
  // DOC 71, DEFECTO E4, SEGUNDA VUELTA. El bloqueo de la pagina de detras se
  // arreglo con este hook —el mismo que usan los otros seis modales— pero el
  // sintoma seguia: una barra de desplazamiento pegada al borde derecho de la
  // pantalla, justo donde estaba la de la pagina. No era la de detras: era la
  // de este overlay.
  //
  // La diferencia con los otros seis, mirada una por una:
  //
  //     AboutModal, LegalModal, TargetSelectorModal,
  //     ProOptionsModal y otros modales de configuracion
  //         fixed inset-0 flex items-center justify-center   -> sin scroll
  //         el panel:  flex flex-col overflow-hidden  + cuerpo overflow-y-auto
  //
  //     este                                       ANTES
  //         fixed inset-0 ... overflow-y-auto   -> barra a lo alto del VIEWPORT
  //
  // Un contenedor `fixed inset-0` ocupa la ventana entera, asi que su barra se
  // dibuja en el mismo sitio que la de la pagina y se lee como una duplicada.
  // Dentro de la tarjeta —que es mas estrecha— la barra pertenece visiblemente
  // a la tarjeta y no puede confundirse con nada.
  useScrollLock(true);
  const [state, setState] = useState<
    | { kind: "loading" }
    | { kind: "ready"; protein: string; left: string; right: string }
    | { kind: "error"; message: string }
  >({ kind: "loading" });

  useEffect(() => {
    let disposed = false;
    setState({ kind: "loading" });
    Promise.all([getPoseFile(moleculeId), getProteinFile(moleculeId)])
      .then(([sdf, protein]) => {
        if (disposed) return;
        if (!sdf || !protein) {
          setState({
            kind: "error",
            message: t("auto_990cc7b4b8ec"),
          });
          return;
        }
        const left = extractPoseFromSdf(sdf, leftRank);
        const right = extractPoseFromSdf(sdf, rightRank);
        if (!left || !right) {
          setState({
            kind: "error",
            message: t("auto_91d8ff3aff6a"),
          });
          return;
        }
        setState({ kind: "ready", protein, left, right });
      })
      .catch((error) => {
        if (!disposed) {
          setState({
            kind: "error",
            message: error instanceof Error ? error.message : "No se pudieron recuperar las coordenadas de las poses.",
          });
        }
      });
    return () => {
      disposed = true;
    };
  }, [leftRank, moleculeId, rightRank]);

  useEffect(() => {
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-[135] flex items-center justify-center overflow-hidden bg-black/80 p-4 backdrop-blur-sm"
      role="presentation"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="pose-comparison-title"
        className="flex max-h-full w-full max-w-6xl flex-col overflow-hidden rounded-2xl border border-surface-700 bg-surface-950 shadow-2xl"
      >
        <header className="flex shrink-0 items-start justify-between gap-4 border-b border-surface-800 px-5 py-4">
          <div className="min-w-0">
            <div className="flex items-center gap-2 text-purple-300">
              <ArrowLeftRight size={17} aria-hidden="true" />
              <h2 id="pose-comparison-title" className="font-mono text-xs font-bold uppercase tracking-[0.14em]">
                Comparar poses en 3D
              </h2>
            </div>
            <p className="mt-1.5 text-xs leading-5 text-zinc-500">
              {t("auto_ed5c43cd041b")}{leftRank} y #{rightRank}.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-white/[0.08] text-zinc-400 transition-colors hover:border-white/20 hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-purple-400"
            aria-label={t("pn_cerrar_comparador")}
          >
            <X size={16} aria-hidden="true" />
          </button>
        </header>

        {/* El cuerpo es lo unico que se desplaza. `min-h-0` es obligatorio: sin
            el, un hijo flex no se encoge por debajo de su contenido y la tarjeta
            desborda la ventana en vez de dejar que este div haga scroll. */}
        <div className="min-h-0 flex-1 overflow-y-auto">
        {state.kind === "loading" && (
          <div className="flex min-h-72 flex-col items-center justify-center gap-3 px-5 text-zinc-400" role="status">
            <Loader2 className="h-6 w-6 animate-spin text-purple-300" aria-hidden="true" />
            <p className="text-xs">{t("pn_recuperando_poses")}</p>
          </div>
        )}

        {state.kind === "error" && (
          <div className="m-5 flex items-start gap-3 rounded-xl border border-amber-500/25 bg-amber-500/[0.05] p-4 text-amber-100" role="alert">
            <AlertTriangle size={18} className="mt-0.5 shrink-0 text-amber-300" aria-hidden="true" />
            <p className="text-xs leading-5">{state.message}</p>
          </div>
        )}

        {state.kind === "ready" && (
          <div className="grid gap-4 p-4 lg:grid-cols-2">
            <PoseViewport rank={leftRank} poseData={state.left} proteinData={state.protein} />
            <PoseViewport rank={rightRank} poseData={state.right} proteinData={state.protein} />
          </div>
        )}
        </div>
      </section>
    </div>
  );
}

function PoseViewport({ rank, poseData, proteinData }: { rank: number; poseData: string; proteinData: string }) {
  return (
    <article className="overflow-hidden rounded-xl border border-surface-800 bg-black">
      <header className="flex items-center justify-between border-b border-surface-800 px-3 py-2">
        <h3 className="font-mono text-[11px] font-bold uppercase tracking-wider text-zinc-200">Pose #{rank}</h3>
        <span className="font-mono text-[10px] text-zinc-500">coordenadas registradas</span>
      </header>
      <MoleculeViewer3D poseData={poseData} proteinData={proteinData} height={360} hideLegend />
    </article>
  );
}
