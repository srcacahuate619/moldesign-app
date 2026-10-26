"use client";

/* Orbe de la pantalla de carga de una evaluación (decisión del propietario, 2026-10-10: «más simétricos y optimizados»).
 *
 * Dos anillos de puntos colocados a ángulos exactos —12 cada 30° y 6 cada 60°— que giran enteros en sentidos opuestos, y
 * un núcleo que respira. Los puntos no se mueven unos respecto de otros: lo que gira es el anillo, con una sola
 * transformación CSS que resuelve el compositor. El orbe anterior (ThinkingOrb en «procesando») escribía desde
 * JavaScript la posición, el tamaño y el brillo de cada punto en cada fotograma, y con la línea de etapas la pantalla de
 * carga gastaba 9,1 s de CPU cada 10 s (medido en el export). Una animación CSS se detiene sola con la pestaña oculta y no
 * corre con «reducir movimiento». */

import type { CSSProperties } from "react";

/** Un punto de un anillo: centrado en el orbe, girado `angulo` y llevado `radio` hacia fuera. */
export function PuntoDeAnillo({ angulo, radio, tam, opacidad, color, brillo }: {
  angulo: number; radio: number; tam: number; opacidad: number; color: string; brillo?: string;
}) {
  const estilo: CSSProperties = {
    width: tam, height: tam, marginLeft: -tam / 2, marginTop: -tam / 2,
    transform: `rotate(${angulo}deg) translateY(-${radio}px)`,
    opacity: opacidad, backgroundColor: color, boxShadow: brillo,
  };
  return <span data-testid="punto-de-anillo" className="absolute left-1/2 top-1/2 rounded-full" style={estilo} />;
}

/** Ángulos repartidos por igual en la circunferencia. */
export function angulosDeAnillo(puntos: number): number[] {
  return Array.from({ length: puntos }, (_, i) => (i * 360) / puntos);
}

const ACENTO = "var(--accent-strong)";
const BRILLO = "0 0 8px rgba(167,139,250,0.75)";

export function OrbeDeEvaluacion({ label }: { label?: string }) {
  const exterior = angulosDeAnillo(12);
  const interior = angulosDeAnillo(6);
  return (
    <div className="flex flex-col items-center gap-3" data-testid="orbe-evaluacion">
      <div className="relative h-24 w-24" aria-hidden="true">
        <div className="absolute inset-0 rounded-full bg-[radial-gradient(circle,rgba(167,139,250,0.16)_0%,transparent_68%)]" />
        {/* Exterior: estela de brillo que crece de un punto al siguiente; gira en el sentido de las agujas del reloj. */}
        <div data-testid="anillo-exterior" className="absolute inset-0 motion-safe:animate-giro">
          {exterior.map((angulo, i) => (
            <PuntoDeAnillo key={angulo} angulo={angulo} radio={40} tam={5} color={ACENTO} brillo={BRILLO}
              opacidad={0.18 + (0.82 * i) / (exterior.length - 1)} />
          ))}
        </div>
        {/* Interior: puntos iguales; gira al revés y a la mitad de velocidad. */}
        <div data-testid="anillo-interior" className="absolute inset-0 motion-safe:animate-giro-inverso">
          {interior.map((angulo) => (
            <PuntoDeAnillo key={angulo} angulo={angulo} radio={22} tam={3} color={ACENTO} opacidad={0.55} />
          ))}
        </div>
        <div className="absolute left-1/2 top-1/2 h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full bg-[var(--accent-strong)] shadow-[0_0_14px_rgba(167,139,250,0.9)] motion-safe:animate-respira" />
      </div>
      {label && <span className="font-mono text-[10px] uppercase tracking-wider text-[var(--accent-strong)]">{label}</span>}
    </div>
  );
}
