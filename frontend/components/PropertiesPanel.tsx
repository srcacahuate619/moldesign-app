import { useState } from "react";
import type { EvaluationResult } from "../lib/types";
import { etiquetaPPB } from "../lib/admetEtiquetas";

type Props = {
  result: EvaluationResult;
};

function Pill({ ok, label }: { ok: boolean | null; label: string }) {
  if (ok === null || ok === undefined) return null;
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-xs font-semibold ${
        ok
          ? "border-emerald-600/40 bg-emerald-900/30 text-emerald-400"
          : "border-red-600/40 bg-red-900/30 text-red-400"
      }`}
    >
      {ok ? "✓" : "✗"} {label}
    </span>
  );
}

function Row({ label, value, unit, onClick }: { label: string; value: number | string | null | undefined; unit?: string, onClick?: () => void }) {
  if (value === null || value === undefined) return null;
  const display = typeof value === "number" ? (Number.isInteger(value) ? String(value) : value.toFixed(2)) : String(value);

  const content = (
    <>
      <span className="text-surface-400 group-hover:text-surface-200 transition-colors">{label}</span>
      <span className="tabular-nums text-gray-300 group-hover:text-white transition-colors">
        {display}
        {unit && <span className="ml-1 text-surface-500">{unit}</span>}
      </span>
    </>
  );

  if (onClick) {
    return (
      <button
        onClick={onClick}
        className="group flex w-full items-center justify-between text-sm hover:bg-surface-800/50 p-1.5 -mx-1.5 rounded transition-all text-left"
      >
        {content}
      </button>
    );
  }

  return (
    <div className="flex items-center justify-between text-sm p-1.5 -mx-1.5">
      {content}
    </div>
  );
}

export function PropertiesPanel({ result }: Props) {
  const [selectedProperty, setSelectedProperty] = useState<{title: string, desc: string, icon: string} | null>(null);

  const hasProps =
    result.molecular_weight !== null ||
    result.log_p !== null ||
    result.tpsa !== null;

  if (!hasProps) return null;

  return (
    <section className="space-y-3 rounded-xl border border-surface-800 bg-surface-900 p-5">
      <h3 className="font-bold text-white">Propiedades fisicoquímicas</h3>
      <p className="text-xs text-surface-400">
        Calculadas con RDKit. Valores reales, no estimaciones de IA. Toca una propiedad para aprender más.
      </p>

      <div className="grid grid-cols-2 gap-x-6 gap-y-0.5">
        <Row
          label="Peso molecular"
          value={result.molecular_weight}
          unit="Da"
          onClick={() => setSelectedProperty({
            title: "Peso Molecular",
            icon: "⚖️",
            desc: "Masa de la molécula expresada en daltons. El umbral de 500 Da es una regla empírica de Lipinski para comparar series; no garantiza absorción ni exposición en una persona."
          })}
        />
        <Row
          label="LogP"
          value={result.log_p}
          onClick={() => setSelectedProperty({
            title: "Coeficiente de Partición (LogP)",
            icon: "🛢️",
            desc: "LogP describe la distribución calculada entre fases acuosa y lipídica. Es un descriptor dependiente del método y del estado químico; no predice por sí solo permeabilidad, circulación ni eficacia."
          })}
        />
        <Row
          label="TPSA"
          value={result.tpsa}
          unit="Å²"
          onClick={() => setSelectedProperty({
            title: "Área de Superficie Polar Topológica (TPSA)",
            icon: "🧲",
            desc: "TPSA resume la superficie polar topológica. Los umbrales de Lipinski y Veber son orientativos y deben interpretarse junto con el resto del perfil; no determinan el paso celular o cerebral."
          })}
        />
        <Row
          label="HBD"
          value={result.hbd}
          onClick={() => setSelectedProperty({
            title: "Donadores de Puentes de Hidrógeno (HBD)",
            icon: "🤝",
            desc: "Número de grupos capaces de donar hidrógeno según la representación química. HBD ≤ 5 es un criterio de Lipinski para comparar compuestos, no una garantía de absorción oral."
          })}
        />
        <Row
          label="HBA"
          value={result.hba}
          onClick={() => setSelectedProperty({
            title: "Aceptores de Puentes de Hidrógeno (HBA)",
            icon: "🤲",
            desc: "Número de átomos aceptores según la representación química. HBA ≤ 10 es un criterio de Lipinski para comparar compuestos, no una garantía de absorción oral."
          })}
        />
        <Row
          label="Rot. bonds"
          value={result.rotatable_bonds}
          onClick={() => setSelectedProperty({
            title: "Enlaces Rotables",
            icon: "🔄",
            desc: "Número de enlaces rotables definido por el descriptor. Valores altos pueden asociarse con mayor flexibilidad conformacional, pero no prueban inestabilidad ni impiden el acoplamiento."
          })}
        />
        <Row label="Átomos pesados" value={result.heavy_atom_count} />
        <Row label="Anillos" value={result.ring_count} />
        <Row
          label="QED"
          value={result.qed}
          onClick={() => setSelectedProperty({
            title: "Quantitative Estimate of Drug-likeness (QED)",
            icon: "🌟",
            desc: "QED combina varios descriptores en una escala histórica de drug-likeness. Un valor alto indica cercanía a esa heurística, no aprobación, seguridad ni similitud causal con fármacos."
          })}
        />
        <Row
          label="LogS (Solubilidad)"
          value={result.blood_solubility_logs}
          onClick={() => setSelectedProperty({
            title: "Solubilidad Acuosa (LogS)",
            icon: "💧",
            desc: "LogS es una estimación o medición expresada en escala logarítmica según el método usado. Los rangos orientativos no sustituyen un ensayo de solubilidad en condiciones experimentales."
          })}
        />
        <Row
          label="PPB"
          value={etiquetaPPB(result.blood_ppb_category)}
          onClick={() => setSelectedProperty({
            title: "Unión a Proteínas Plasmáticas (PPB)",
            icon: "🩸",
            desc: "PPB es una categoría derivada de un modelo o descriptor. La fracción libre depende de concentración, matriz y condiciones; no basta para concluir distribución o actividad."
          })}
        />
        <Row
          label="Absorción Intestinal"
          value={result.blood_hia_permeable != null ? (result.blood_hia_permeable ? "✓ Señal positiva" : "✗ Señal negativa") : null}
          onClick={() => setSelectedProperty({
            title: "Absorción Intestinal Humana (HIA)",
            icon: "🫀",
            desc: "Señal computacional de permeabilidad o absorción intestinal. Su resultado depende del modelo y de su dominio; no predice por sí solo exposición humana."
          })}
        />
        <Row
          label="Llega al Cerebro"
          value={result.blood_bbb_permeable != null ? (result.blood_bbb_permeable ? "✓ Señal positiva" : "✗ Señal negativa") : null}
          onClick={() => setSelectedProperty({
            title: "Barrera Hematoencefálica (BBB)",
            icon: "🧠",
            desc: "Señal computacional de permeabilidad a BBB. No demuestra entrada al cerebro en vivo ni implica beneficio o riesgo terapéutico."
          })}
        />
        <Row label="SA Score" value={result.sa_score} />
      </div>

      {result.sa_reasons && result.sa_reasons.length > 0 && (
        <div className="mt-2 space-y-1 rounded-lg border border-yellow-900/30 bg-yellow-950/20 p-2.5">
          <p className="text-[10px] font-bold uppercase tracking-wider text-yellow-500/80">Alertas de Accesibilidad (SA)</p>
          <ul className="list-inside list-disc space-y-0.5">
            {result.sa_reasons.map((reason, idx) => (
              <li key={idx} className="text-[11px] text-yellow-200/70">{reason}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="flex flex-wrap gap-2 pt-1">
        <button
          onClick={() => setSelectedProperty({
            title: "Regla de los 5 de Lipinski",
            icon: "📜",
            desc: "Las cuatro reglas de Lipinski son filtros históricos para comparar compuestos orales. Incumplir una regla no descarta una molécula ni equivale a toxicidad o fracaso clínico."
          })}
          className="hover:scale-105 transition-transform"
        >
          <Pill ok={result.lipinski_pass} label="Lipinski" />
        </button>
        <button
          onClick={() => setSelectedProperty({
            title: "Reglas de Veber",
            icon: "📜",
            desc: "Veber relaciona enlaces rotables y TPSA con biodisponibilidad oral en ciertos conjuntos. Es una heurística de priorización, no una predicción individual de biodisponibilidad."
          })}
          className="hover:scale-105 transition-transform"
        >
          <Pill ok={result.veber_pass} label="Veber" />
        </button>
      </div>

      {/* Modal Métrica Educativa */}
      {selectedProperty && (
        <div
          className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/60 backdrop-blur-md animate-in fade-in"
          onClick={() => setSelectedProperty(null)}
        >
          <div
            className="bg-surface-900 border border-indigo-500/50 rounded-2xl p-6 max-w-md w-full shadow-2xl relative animate-in zoom-in-95 text-left"
            onClick={(e) => e.stopPropagation()}
          >
            <button
              onClick={() => setSelectedProperty(null)}
              className="absolute top-4 right-4 text-surface-400 hover:text-white transition-colors"
            >
              ✕
            </button>
            <div className="flex items-center gap-4 mb-4">
              <span className="text-3xl">{selectedProperty.icon}</span>
              <h3 className="text-xl font-bold text-white leading-tight">{selectedProperty.title}</h3>
            </div>
            <p className="text-sm text-surface-300 leading-relaxed">
              {selectedProperty.desc}
            </p>
            <div className="mt-6 flex justify-end">
              <button
                onClick={() => setSelectedProperty(null)}
                className="px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-bold rounded-xl transition-colors shadow-lg shadow-indigo-500/20"
              >
                Entendido
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
