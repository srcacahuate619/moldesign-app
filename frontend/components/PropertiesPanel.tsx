
import { useLanguage } from "@/context/LanguageContext";
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
  const { t } = useLanguage();
  const [selectedProperty, setSelectedProperty] = useState<{title: string, desc: string, icon: string} | null>(null);

  const hasProps =
    result.molecular_weight !== null ||
    result.log_p !== null ||
    result.tpsa !== null;

  if (!hasProps) return null;

  return (
    <section className="space-y-3 rounded-xl border border-surface-800 bg-surface-900 p-5">
      <h3 className="font-bold text-white">{t("pn_propiedades")}</h3>
      <p className="text-xs text-surface-400">
        {t("pn_propiedades_rdkit")}
      </p>

      <div className="grid grid-cols-2 gap-x-6 gap-y-0.5">
        <Row
          label="Peso molecular"
          value={result.molecular_weight}
          unit="Da"
          onClick={() => setSelectedProperty({
            title: "Peso Molecular",
            icon: "⚖️",
            desc: t("auto_ec0377945f92")
          })}
        />
        <Row
          label="LogP"
          value={result.log_p}
          onClick={() => setSelectedProperty({
            title: t("auto_f2422134496a"),
            icon: "🛢️",
            desc: t("auto_8b8d19d6a005")
          })}
        />
        <Row
          label="TPSA"
          value={result.tpsa}
          unit="Å²"
          onClick={() => setSelectedProperty({
            title: t("auto_98d8f5a99754"),
            icon: "🧲",
            desc: t("auto_7cbf8c0d5ae1")
          })}
        />
        <Row
          label="HBD"
          value={result.hbd}
          onClick={() => setSelectedProperty({
            title: t("auto_411c9577cc23"),
            icon: "🤝",
            desc: t("auto_1e01fec6e93b")
          })}
        />
        <Row
          label="HBA"
          value={result.hba}
          onClick={() => setSelectedProperty({
            title: t("auto_0d82ae16ddd4"),
            icon: "🤲",
            desc: t("auto_da60d4d5d247")
          })}
        />
        <Row
          label="Rot. bonds"
          value={result.rotatable_bonds}
          onClick={() => setSelectedProperty({
            title: "Enlaces Rotables",
            icon: "🔄",
            desc: t("auto_062fc71dfbbf")
          })}
        />
        <Row label={t("pn_atomos_pesados")} value={result.heavy_atom_count} />
        <Row label="Anillos" value={result.ring_count} />
        <Row
          label="QED"
          value={result.qed}
          onClick={() => setSelectedProperty({
            title: "Quantitative Estimate of Drug-likeness (QED)",
            icon: "🌟",
            desc: t("auto_a0adb4d99412")
          })}
        />
        <Row
          label="LogS (Solubilidad)"
          value={result.blood_solubility_logs}
          onClick={() => setSelectedProperty({
            title: "Solubilidad Acuosa (LogS)",
            icon: "💧",
            desc: t("auto_0310df6f0be2")
          })}
        />
        <Row
          label="PPB"
          value={etiquetaPPB(result.blood_ppb_category)}
          onClick={() => setSelectedProperty({
            title: t("auto_81f1389c8e3d"),
            icon: "🩸",
            desc: t("auto_17a9283c624b")
          })}
        />
        <Row
          label={t("z_absorcion_intestinal")}
          value={result.blood_hia_permeable != null ? (result.blood_hia_permeable ? t("auto_c4bcead81aba") : t("auto_3963e4218261")) : null}
          onClick={() => setSelectedProperty({
            title: t("auto_b9132e69d608"),
            icon: "🫀",
            desc: t("auto_30f8b7d8b9a8")
          })}
        />
        <Row
          label="Llega al Cerebro"
          value={result.blood_bbb_permeable != null ? (result.blood_bbb_permeable ? t("auto_c4bcead81aba") : t("auto_3963e4218261")) : null}
          onClick={() => setSelectedProperty({
            title: t("auto_df4596705f22"),
            icon: "🧠",
            desc: t("auto_cf041ff07895")
          })}
        />
        <Row label="SA Score" value={result.sa_score} />
      </div>

      {result.sa_reasons && result.sa_reasons.length > 0 && (
        <div className="mt-2 space-y-1 rounded-lg border border-yellow-900/30 bg-yellow-950/20 p-2.5">
          <p className="text-[10px] font-bold uppercase tracking-wider text-yellow-500/80">{t("z_alertas_sa")}</p>
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
            title: t("auto_4a70388e7d39"),
            icon: "📜",
            desc: t("auto_35f6dace8ff1")
          })}
          className="hover:scale-105 transition-transform"
        >
          <Pill ok={result.lipinski_pass} label="Lipinski" />
        </button>
        <button
          onClick={() => setSelectedProperty({
            title: t("auto_3db8386c07e1"),
            icon: "📜",
            desc: t("auto_b296de8883ee")
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
              {t(selectedProperty.desc)}
            </p>
            <div className="mt-6 flex justify-end">
              <button
                onClick={() => setSelectedProperty(null)}
                className="px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-bold rounded-xl transition-colors shadow-lg shadow-indigo-500/20"
              >
                {t("legal_understood")}
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
