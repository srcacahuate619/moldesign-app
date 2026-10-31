"use client";

import { Translated, useLanguage } from "@/context/LanguageContext";
import React, { memo, useEffect, useState } from 'react';
import { getPoseFile, getProteinFile } from '../lib/api';
import { MoleculeViewer3D } from './MoleculeViewer3D';
import { motion } from 'framer-motion';
import { Microscope, ArrowLeftRight, Zap, AlertTriangle } from 'lucide-react';
import {
  compararMoleculas,
  compararIndices,
  filaComparativa,
  type MoldexMolecule,
} from '../lib/moldex';

interface ComparisonProps {
  molA: MoldexMolecule;
  molB: MoldexMolecule;
  onClose: () => void;
}

type EstadoArtefacto = "cargando" | "listo" | "error";

type Artefactos = {
  pose: string | null;
  prot: string | null;
  estado: EstadoArtefacto;
  sinIdentidad?: boolean;
};

const INICIAL: Artefactos = { pose: null, prot: null, estado: "cargando" };

const MolecularComparison: React.FC<ComparisonProps> = memo(function MolecularComparison({ molA, molB, onClose }) {
  const { t } = useLanguage();
  const [dataA, setDataA] = useState<Artefactos>(INICIAL);
  const [dataB, setDataB] = useState<Artefactos>(INICIAL);

  useEffect(() => {
    let activo = true;

    // MOLDEX-INT-010: antes esto era `.then()` sin `.catch()`. Una descarga
    // fallida —artefacto ausente, huérfano o no autorizado— dejaba el visor
    // vacío para siempre, sin decir por qué.
    const cargar = (
      mol: MoldexMolecule | undefined,
      set: React.Dispatch<React.SetStateAction<Artefactos>>,
    ) => {
      if (!mol) return;
      const taskId = mol.provenance?.task_id;
      if (!taskId) { set({ pose: null, prot: null, estado: "error", sinIdentidad: true }); return; }
      set(INICIAL);
      Promise.all([getPoseFile(mol.id, taskId), getProteinFile(mol.id, taskId)])
        .then(([pose, prot]) => {
          if (activo) set({ pose, prot, estado: pose && prot ? "listo" : "error" });
        })
        .catch(() => {
          if (activo) set({ pose: null, prot: null, estado: "error" });
        });
    };

    cargar(molA, setDataA);
    cargar(molB, setDataB);

    return () => {
      activo = false;
    };
  }, [molA, molB]);

  // Comparar dos evaluaciones de la MISMA molécula es el caso principal de tener
  // varias fichas por molécula: sin la marca de la corrida las dos columnas se
  // titularían igual.
  const mismaMolecula = !!molA && !!molB && molA.id === molB.id;
  const nombreDe = (mol: MoldexMolecule | undefined) => {
    const corrida = mol?.provenance?.task_id ? ` #${mol.provenance.task_id.slice(0, 6)}` : "";
    const porTarget = `MDX-${mol?.target?.pdb_id || "UKN"}-${mol?.smiles_hash?.substring(0, 4)?.toUpperCase() || "XXXX"}${corrida}`;
    const esPorDefecto = !mol?.name;
    const base = esPorDefecto ? porTarget : mol!.name;
    return { porTarget, mostrado: !esPorDefecto && mismaMolecula ? `${base}${corrida}` : base };
  };

  const nombreA = nombreDe(molA);
  const nombreB = nombreDe(molB);

  // MOLDEX-SCI-004: antes de restar nada, saber si estas dos fichas se pueden
  // comparar. Un score de docking sólo significa algo relativo al receptor y al
  // protocolo que lo produjeron.
  const veredicto = compararMoleculas(molA, molB, t);
  const veredictoIndice = compararIndices(molA, molB, t);
  const indice = filaComparativa(`${t("mx_indice_compuesto")} (0-100)`, molA?.metrics?.score, molB?.metrics?.score);
  if (!veredictoIndice.comparable) {
    indice.delta = null;
    indice.textoDelta = "—";
  }

  // MOLDEX-SCI-003: `?? 0` convertía una métrica no calculada en un cero y
  // después restaba contra él. Ahora el faltante se conserva como faltante.
  const filas = [
    filaComparativa("LOG P", molA?.metrics?.log_p, molB?.metrics?.log_p),
    filaComparativa(t("mx_compare_weight"), molA?.metrics?.mw, molB?.metrics?.mw),
    filaComparativa("TPSA (Å²)", molA?.metrics?.tpsa, molB?.metrics?.tpsa),
    indice,
  ];

  const panel = (
    mol: MoldexMolecule | undefined,
    datos: Artefactos,
    nombre: { mostrado: string },
    alineadoDerecha: boolean,
  ) => (
    <div className="space-y-6">
      <div className="rounded-2xl bg-slate-950 border border-slate-800 p-2 overflow-hidden">
        {datos.estado === "error" ? (
          <div
            role="alert"
            className="flex h-[260px] flex-col items-center justify-center gap-2 px-6 text-center text-[11px] text-slate-400"
          >
            <AlertTriangle size={20} className="text-amber-500" />
            <span>
              <Translated id={datos.sinIdentidad ? "rx_sin_identidad_corrida" : "z_comparador_no_cargo"} />
            </span>
          </div>
        ) : (
          <MoleculeViewer3D
            poseData={datos.pose || undefined}
            proteinData={datos.prot || undefined}
            height={260}
            hotspots={mol?.target?.hotspots?.map((h: any) => h.name) || []}
            hotspotsHit={mol?.hotspots_hit || []}
            hideLegend={true}
          />
        )}
      </div>
      <div className={`space-y-2 ${alineadoDerecha ? "text-right" : ""}`}>
        <h3 className="text-xl font-bold text-white">{nombre.mostrado}</h3>
        <div className={`flex items-center gap-4 ${alineadoDerecha ? "justify-end" : ""}`}>
          {alineadoDerecha && (
            <div className="text-xs text-slate-500 font-bold uppercase">{mol?.target?.pdb_id || t("pr_compare_target")}</div>
          )}
          <div className={`flex items-center gap-1 font-black ${alineadoDerecha ? "text-emerald-400" : "text-indigo-400"}`}>
            <Zap size={14} fill="currentColor" />
            {/* Una afinidad ausente no es 0.00. */}
            {mol?.metrics?.affinity !== null && mol?.metrics?.affinity !== undefined
              ? `${mol.metrics.affinity.toFixed(2)} kcal/mol`
              : t("auto_185e750ee009")}
          </div>
          {!alineadoDerecha && (
            <div className="text-xs text-slate-500 font-bold uppercase">{mol?.target?.pdb_id || t("pr_compare_target")}</div>
          )}
        </div>
      </div>
    </div>
  );

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="fixed inset-0 z-[100] flex items-center justify-center bg-slate-950/90 backdrop-blur-md p-8"
    >
      <div className="relative w-full max-w-6xl rounded-3xl border border-slate-800 bg-slate-900 p-8 shadow-2xl overflow-y-auto max-h-[92vh]">
        <button
          onClick={onClose}
          aria-label={t("pr_compare_close")}
          className="absolute top-6 right-6 rounded-full bg-slate-800 p-2 text-slate-400 hover:text-white transition-colors"
        >
          <Microscope size={20} className="rotate-45" />
        </button>

        <h2 className="text-3xl font-black text-white mb-8 flex items-center gap-4">
          <ArrowLeftRight className="text-indigo-500" /> <Translated id="z_comparador_titulo" />
        </h2>

        <div className="grid grid-cols-2 gap-12">
          {panel(molA, dataA, nombreA, false)}
          {panel(molB, dataB, nombreB, true)}
        </div>

        {/* SCI-A-012: la abstención afecta al índice, no a los descriptores. */}
        {!veredicto.comparable && (
          <div
            role="alert"
            className="mt-12 rounded-2xl border border-amber-500/30 bg-amber-500/10 p-6 text-[12px] leading-relaxed text-amber-200/90"
          >
            <p className="mb-3 flex items-center gap-2 font-black uppercase tracking-widest text-amber-400">
              <AlertTriangle size={15} /> <Translated id="z_no_comparables" />
            </p>
            <ul className="list-disc space-y-1.5 pl-5">
              {veredicto.motivos.map((motivo, i) => (
                <li key={i}>{motivo}</li>
              ))}
            </ul>
            <p className="mt-3 text-amber-200/60">
              <Translated id="z_no_comparables_detalle" />
            </p>
          </div>
        )}

          <div className="mt-12 overflow-hidden rounded-2xl border border-slate-800 bg-slate-950/50">
            <table className="w-full text-sm text-left">
              <caption className="sr-only">
                <Translated id="auto_9835328903b8" /> {nombreA.porTarget} {t("ca_and")} {nombreB.porTarget}
              </caption>
              <thead className="bg-slate-800/50 text-[10px] font-bold uppercase tracking-widest text-slate-500">
                <tr>
                  <th scope="col" className="px-6 py-3">{t("pr_compare_property")}</th>
                  <th scope="col" className="px-6 py-3 text-center">{nombreA.porTarget}</th>
                  <th scope="col" className="px-6 py-3 text-center">{t("pr_compare_difference")}</th>
                  <th scope="col" className="px-6 py-3 text-center">{nombreB.porTarget}</th>
                </tr>
              </thead>
              <tbody className="text-slate-300 font-mono text-xs">
                {filas.map(fila => (
                  <tr key={fila.etiqueta} className="border-t border-slate-800/50 hover:bg-slate-800/20 transition-colors">
                    <th scope="row" className="px-6 py-4 text-left font-bold text-slate-500 font-sans">{fila.etiqueta}</th>
                    <td className="px-6 py-4 text-center">{fila.textoA}</td>
                    <td className="px-6 py-4 text-center font-bold">
                      <span
                        className={
                          fila.delta === null
                            ? 'text-slate-600'
                            : 'text-slate-300'
                        }
                        title={fila.delta === null && (fila !== indice || veredictoIndice.comparable) ? t("auto_7c3ae9bd54e6") : undefined}
                      >
                        {fila.textoDelta}
                      </span>
                      {fila === indice && veredictoIndice.calibracionAusente && (
                        <p className="mt-1 font-sans font-normal text-slate-400">
                          {t("z_indice_calibracion_ausente")}
                        </p>
                      )}
                    </td>
                    <td className="px-6 py-4 text-center">{fila.textoB}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
      </div>
    </motion.div>
  );
});

export default MolecularComparison;
