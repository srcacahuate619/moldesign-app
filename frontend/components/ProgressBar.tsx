type Props = {
  progress: number;
  status: string;
};

const STATUS_LABELS: Record<string, string> = {
  PENDING: "En cola…",
  STARTED: "Procesando…",
  SUCCESS: "Completado",
  FAILURE: "Error",
  RETRY: "Reintentando…",
  submitted: "Enviado…",
};

export function ProgressBar({ progress, status }: Props) {
  const isActive = status === "PENDING" || status === "STARTED" || status === "submitted" || status === "RETRY";
  const label = STATUS_LABELS[status] ?? status;
  const pct = Math.max(0, Math.min(100, progress));

  return (
    <div className="rounded-xl border border-surface-800 bg-surface-900 p-4">
      <div className="mb-2 flex items-center justify-between text-sm">
        <span className={`font-medium ${isActive ? "pulse-glow text-brand-400" : "text-gray-300"}`}>
          {isActive && <span className="spinner mr-2 inline-block" />}
          {label}
        </span>
        <span className="tabular-nums text-surface-400">{progress}%</span>
      </div>
      <div className="h-2.5 overflow-hidden rounded-full bg-surface-800">
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{
            width: `${pct}%`,
            background: isActive
              ? "linear-gradient(90deg, #3b82f6, #8b5cf6)"
              : status === "SUCCESS"
                ? "#22c55e"
                : "#ef4444",
          }}
        />
      </div>
    </div>
  );
}
