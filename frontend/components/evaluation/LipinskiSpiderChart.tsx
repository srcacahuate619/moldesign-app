"use client";

export function LipinskiSpiderChart({
  mw,
  logP,
  hbd,
  hba,
  rotb
}: {
  mw: number;
  logP: number;
  hbd: number;
  hba: number;
  rotb: number;
}) {
  const mwNorm = Math.min(100, (mw / 500) * 50);
  const logPNorm = Math.min(100, (logP / 5.0) * 50);
  const hbdNorm = Math.min(100, (hbd / 5) * 50);
  const hbaNorm = Math.min(100, (hba / 10) * 50);
  const rotbNorm = Math.min(100, (rotb / 10) * 50);

  const cx = 100;
  const cy = 100;

  const getCoords = (r1: number, r2: number, r3: number, r4: number, r5: number) => {
    const p1 = { x: cx, y: cy - r1 };
    const p2 = { x: cx + r2 * Math.sin(72 * Math.PI / 180), y: cy - r2 * Math.cos(72 * Math.PI / 180) };
    const p3 = { x: cx + r3 * Math.sin(144 * Math.PI / 180), y: cy - r3 * Math.cos(144 * Math.PI / 180) };
    const p4 = { x: cx + r4 * Math.sin(216 * Math.PI / 180), y: cy - r4 * Math.cos(216 * Math.PI / 180) };
    const p5 = { x: cx + r5 * Math.sin(288 * Math.PI / 180), y: cy - r5 * Math.cos(288 * Math.PI / 180) };
    return `${p1.x},${p1.y} ${p2.x},${p2.y} ${p3.x},${p3.y} ${p4.x},${p4.y} ${p5.x},${p5.y}`;
  };

  const limitPath = getCoords(50, 50, 50, 50, 50);
  const realPath = getCoords(mwNorm, logPNorm, hbdNorm, hbaNorm, rotbNorm);

  return (
    <div className="flex flex-col items-center justify-center space-y-4 p-4 lg:pl-6 lg:border-l lg:border-zinc-100 lg:dark:border-zinc-800">
      <h4 className="text-xs font-bold uppercase tracking-wider text-zinc-400">Red de Viabilidad (Lipinski)</h4>
      <div className="relative w-52 h-52">
        <svg viewBox="0 0 200 200" className="w-full h-full">
          <circle cx="100" cy="100" r="25" fill="none" className="stroke-zinc-100 dark:stroke-zinc-800/40" strokeWidth="1" />
          <circle cx="100" cy="100" r="50" fill="none" className="stroke-zinc-200 dark:stroke-zinc-800/80" strokeWidth="1" strokeDasharray="2" />
          <circle cx="100" cy="100" r="75" fill="none" className="stroke-zinc-100 dark:stroke-zinc-800/40" strokeWidth="1" />
          <circle cx="100" cy="100" r="100" fill="none" className="stroke-zinc-100 dark:stroke-zinc-900/15" strokeWidth="1" />

          {[0, 72, 144, 216, 288].map(ang => (
            <line
              key={ang}
              x1="100"
              y1="100"
              x2={100 + 100 * Math.sin(ang * Math.PI / 180)}
              y2={100 - 100 * Math.cos(ang * Math.PI / 180)}
              className="stroke-zinc-200 dark:stroke-zinc-800/50"
              strokeWidth="1"
            />
          ))}

          <polygon
            points={limitPath}
            fill="none"
            className="stroke-zinc-400 dark:stroke-zinc-650"
            strokeWidth="1.5"
            strokeDasharray="4"
          />

          <polygon
            points={realPath}
            className="fill-zinc-900/10 dark:fill-white/10 stroke-zinc-900 dark:stroke-white"
            strokeWidth="2"
          />

          {[
            { r: mwNorm, ang: 0 },
            { r: logPNorm, ang: 72 },
            { r: hbdNorm, ang: 144 },
            { r: hbaNorm, ang: 216 },
            { r: rotbNorm, ang: 288 }
          ].map((pt, i) => {
            const px = cx + pt.r * Math.sin(pt.ang * Math.PI / 180);
            const py = cy - pt.r * Math.cos(pt.ang * Math.PI / 180);
            return (
              <circle
                key={i}
                cx={px}
                cy={py}
                r="4"
                className="fill-zinc-900 dark:fill-white stroke-white dark:stroke-zinc-900"
                strokeWidth="1.5"
              />
            );
          })}
        </svg>

        <span className="absolute top-[-8px] left-1/2 -translate-x-1/2 text-[9px] font-mono font-bold text-zinc-400 uppercase">Peso M.</span>
        <span className="absolute top-[35%] right-[-10px] text-[9px] font-mono font-bold text-zinc-400 uppercase">LogP</span>
        <span className="absolute bottom-[2%] right-[10%] text-[9px] font-mono font-bold text-zinc-400 uppercase">Donadores H</span>
        <span className="absolute bottom-[2%] left-[10%] text-[9px] font-mono font-bold text-zinc-400 uppercase">Aceptores H</span>
        <span className="absolute top-[35%] left-[-12px] text-[9px] font-mono font-bold text-zinc-400 uppercase">Rotables</span>
      </div>

      <div className="text-[10px] text-zinc-400 text-center font-mono leading-relaxed pt-2">
        <span className="inline-block w-2 h-2 border border-dashed border-zinc-400 mr-1.5" />
        Límite Ideal
        <span className="inline-block w-2 h-2 bg-zinc-900 dark:bg-white ml-3 mr-1.5" />
        Tu Compuesto
      </div>
    </div>
  );
}
