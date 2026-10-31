"use client";


import { useLanguage } from "@/context/LanguageContext";
import dynamic from "next/dynamic";
import { useCallback, useRef, useState, useEffect } from "react";
import type { PreparacionDeLaCorrida } from "../lib/elevacion";
import { VIEWER_SWITCH_BUTTON_CLASS } from "./interfaces/pro/viewerOverlayStyles";

const VisorElevacionEditor = dynamic(() => import("./elevacion/VisorElevacionEditor"), { ssr: false });

function KetcherEditorLoading() {
  const { t } = useLanguage();
  return (
    <div className="flex items-center justify-center rounded-xl border border-dashed border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900/50"
      style={{ height: 550 }}
    >
      <div className="flex items-center gap-3 text-sm font-medium text-zinc-500">
        <div className="h-4 w-4 animate-spin rounded-full border-2 border-zinc-300 dark:border-zinc-600 border-t-transparent" />
        {t("c_loading_molecular_editor")}
      </div>
    </div>
  );
}

const KetcherEditorInner = dynamic(() => import("./KetcherEditorInner"), {
  ssr: false,
  loading: () => <KetcherEditorLoading />,
});

type Props = {
  caseId?: string;
  onSmilesChange?: (smiles: string) => void;
  initialSmiles?: string;
  height?: number | string;
  showSmilesInput?: boolean;
  /** pH y tautómero de la corrida que se va a lanzar: la vista «Se acoplará» del visor 3D prepara con ellos. */
  preparacion?: PreparacionDeLaCorrida;
};

export function KetcherEditor({ caseId, onSmilesChange, initialSmiles, height = 750, showSmilesInput = true, preparacion }: Props) {
  const { t } = useLanguage();
  const [textSmiles, setTextSmiles] = useState(initialSmiles || "");
  const [ketcherError, setKetcherError] = useState<string | null>(null);
  const [isFocused, setIsFocused] = useState(false);
  // Ketcher es el editor; la elevación 3D es una vista alternativa, como Web3D
  // frente a Mol*. Se alterna con el botón de la esquina.
  const [vista, setVista] = useState<"ketcher" | "elevacion">("ketcher");
  // El visor se monta al primer uso y después sólo se oculta: volver a él no lo reinicia.
  const [visorUsado, setVisorUsado] = useState(false);
  // El dibujo de Ketcher se lee al abrir el visor: el levantamiento parte de él.
  const leerDibujo = useRef<(() => Promise<string | null>) | null>(null);
  const [molfile, setMolfile] = useState<string | null>(null);
  const abrirVisor = useCallback(async () => {
    setVisorUsado(true);
    setVista("elevacion");
    const leido = leerDibujo.current ? await leerDibujo.current() : null;
    setMolfile(leido);
  }, []);

  useEffect(() => {
    if (initialSmiles !== undefined && initialSmiles !== textSmiles) {
      setTextSmiles(initialSmiles);
    }
  }, [initialSmiles, textSmiles]);

  const handleTextChange = useCallback(
    (value: string) => {
      setTextSmiles(value);
      onSmilesChange?.(value);
    },
    [onSmilesChange],
  );

  const handleKetcherSmiles = useCallback(
    (smiles: string) => {
      if (smiles !== textSmiles && !isFocused) {
        setTextSmiles(smiles);
        onSmilesChange?.(smiles);
      }
    },
    [onSmilesChange, textSmiles, isFocused],
  );

  return (
    <div className="space-y-4">
      <div className="space-y-3">
        {ketcherError ? (
          <div className="flex items-center justify-center rounded-xl border border-dashed border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900/50 p-12">
            <div className="text-center">
              <div className="mb-3 text-4xl grayscale opacity-80">⚠️</div>
              <p className="text-sm font-semibold text-zinc-900 dark:text-white">
                {t("pn_editor_no_cargo")}
              </p>
              <p className="mt-1 text-xs text-zinc-500">{ketcherError}</p>
            </div>
          </div>
        ) : (
          // `isolate`: el visor 3D y su botón se apilan sólo dentro del editor.
          // Sin él, su z-index competía con la cabecera fija del caso
          // (Evaluación / Informe, `sticky z-20`) y la tapaba al desplazar.
          <div className="relative isolate rounded-xl overflow-hidden border border-zinc-200 dark:border-zinc-800 bg-white">
            {/* Ketcher sigue montado bajo el visor 3D: volver no lo reinicia ni pierde el dibujo. */}
            <KetcherEditorInner
              caseId={caseId}
              requestedSmiles={initialSmiles}
              initialSmiles={textSmiles}
              onSmilesChange={handleKetcherSmiles}
              height={height}
              onLectorDelDibujo={(leer) => { leerDibujo.current = leer; }}
            />
            {visorUsado && (
              <VisorElevacionEditor
                smiles={textSmiles}
                activo={vista === "elevacion"}
                preparacion={preparacion}
                molfile={molfile}
                onSwitchViewer={() => setVista("ketcher")}
              />
            )}
            {vista === "ketcher" && (
              <div className="pointer-events-auto absolute bottom-3 right-3 z-10">
                <button
                  type="button"
                  onClick={() => { void abrirVisor(); }}
                  className={VIEWER_SWITCH_BUTTON_CLASS}
                  title={t("pr_viewer_switch_to", { viewer: "3D" })}
                >
                  {t("pr_viewer_switch_label", { viewer: "3D" })}
                </button>
              </div>
            )}
          </div>
        )}
        {showSmilesInput && (
          <div className="flex items-center gap-3">
            <label className="text-[11px] font-bold uppercase tracking-widest text-zinc-500">SMILES</label>
            <input
              type="text"
              value={textSmiles}
              onFocus={() => setIsFocused(true)}
              onBlur={() => setIsFocused(false)}
              onChange={(e) => handleTextChange(e.target.value)}
              className="flex-1 rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900 px-3 py-2 font-mono text-xs text-zinc-700 dark:text-zinc-300 focus:outline-none focus:border-zinc-400 dark:focus:border-zinc-600 transition-colors"
              placeholder={t("pn_editor_smiles")}
            />
          </div>
        )}
      </div>
    </div>
  );
}
