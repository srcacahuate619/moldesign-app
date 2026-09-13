"use client";

import { forwardRef, useEffect, useRef } from "react";
import { animateElements } from "@/lib/webAnimation";
interface LogConsoleProps {
  logs: string[];
  progress: number;
  currentStatus: string;
}

const LOG_COLORS: Record<string, string> = {
  "[blockchain]": "text-purple-300",
  "[rdkit]": "text-cyan-300",
  "[vina]": "text-blue-300",
  "[admet]": "text-rose-300",
  "[tabpfn]": "text-fuchsia-300",
  "[rtmscore]": "text-purple-400",
  "[openmm]": "text-amber-300",
  "[pdf]": "text-purple-200",
  "[sys]": "text-white/50",
  "[SUCCESS]": "text-emerald-300 font-semibold",
  "[ERROR]": "text-rose-400 font-semibold",
};

function getLogColor(log: string): string {
  for (const [prefix, color] of Object.entries(LOG_COLORS)) {
    if (log.includes(prefix)) return color;
  }
  return "text-white/40";
}

export const LogConsole = forwardRef<HTMLDivElement, LogConsoleProps>(
  ({ logs, progress, currentStatus }, ref) => {
    const prevCountRef = useRef(0);
    const containerRef = useRef<HTMLDivElement | null>(null);

    const setRef = (el: HTMLDivElement | null) => {
      containerRef.current = el;
      if (typeof ref === "function") ref(el);
      else if (ref) ref.current = el;
    };

    useEffect(() => {
      if (!containerRef.current) return;
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }, [logs.length]);

    useEffect(() => {
      if (!containerRef.current || logs.length === prevCountRef.current) return;
      const newLogs = containerRef.current.querySelectorAll(".log-line-new");
      if (newLogs.length === 0) return;

      Array.from(newLogs).forEach((node, index) => animateElements(
        node,
        [
          { opacity: 0, transform: "translateY(6px)", filter: "blur(2px)" },
          { opacity: 1, transform: "translateY(0)", filter: "blur(0px)" },
        ],
        { duration: 350, delay: index * 60, easing: "cubic-bezier(0.16, 1, 0.3, 1)" },
      ));

      prevCountRef.current = logs.length;
    }, [logs.length]);

    const isIdle = progress === 0 && currentStatus !== "FAILURE" && currentStatus !== "SUCCESS";

    return (
      <div
        ref={setRef}
        className="mt-4 border border-white/5 bg-black/60 rounded-xl p-3 h-[140px] overflow-y-auto font-mono text-[11px] custom-scrollbar"
      >
        <div className="flex items-center justify-between border-b border-white/5 pb-1.5 mb-2 text-white/30 text-[9px] uppercase tracking-wider font-sans font-bold">
          <span>Registro de Telemetría</span>
          <span className="flex items-center gap-1.5">
            <span className={`h-1.5 w-1.5 rounded-full ${
              isIdle ? "bg-white/20" :
              currentStatus === "FAILURE" ? "bg-red-400" :
              currentStatus === "SUCCESS" ? "bg-white" :
              "bg-purple-400 animate-pulse"
            }`} />
            {isIdle ? "INACTIVO" :
             currentStatus === "FAILURE" ? "ERROR" :
             currentStatus === "SUCCESS" ? "LISTO" :
             "PROCESANDO"}
          </span>
        </div>
        {logs.length === 0 ? (
          <div className="text-white/15 text-center py-6 italic">
            Esperando datos del pipeline...
          </div>
        ) : (
          logs.map((log, idx) => {
            const isNew = idx >= prevCountRef.current && prevCountRef.current > 0;
            return (
              <div
                key={`${idx}-${log.slice(0, 20)}`}
                className={`leading-relaxed ${getLogColor(log)} ${isNew ? "log-line-new" : ""}`}
              >
                {log}
              </div>
            );
          })
        )}
      </div>
    );
  },
);

LogConsole.displayName = "LogConsole";
