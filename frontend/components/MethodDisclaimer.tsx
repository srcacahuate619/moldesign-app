/**
 * Aviso breve reutilizable para cualquier vista que muestre señales del pipeline.
 * Mantiene la separación entre observaciones, interpretaciones y decisiones.
 */
export function MethodDisclaimer() {
  return (
    <section className="rounded-xl border border-blue-800/30 bg-blue-950/20 p-5 text-xs">
      <h3 className="mb-2 flex items-center gap-1.5 text-sm font-bold text-blue-300">
        <span aria-hidden="true">ℹ️</span> Limitaciones y metodología
      </h3>
      <ul className="list-disc space-y-1.5 pl-4 leading-relaxed text-surface-400">
        <li>
          AutoDock Vina devuelve un <strong className="text-gray-300">score empírico</strong> para ordenar poses dentro de la caja declarada. No equivale a energía libre experimental, afinidad medida ni validación clínica.
        </li>
        <li>
          XGBoost, CL-GNN y otras señales de rescoring sólo se interpretan cuando el perfil declara modelo, pesos, cohorte y dominio de aplicabilidad. Fuera de dominio prevalece la observación de Vina y la interpretación puede quedar en revisión.
        </li>
        <li>
          Las propiedades ADMET, drug-likeness y accesibilidad sintética son descriptores o heurísticas computacionales. No garantizan absorción, seguridad, actividad ni que una síntesis sea viable en laboratorio.
        </li>
        <li>
          UMS se integra únicamente en perfiles M5-Zn exactos. Si falta un componente o la diana está fuera del perfil, el resultado correcto es una abstención; no se redistribuyen pesos ni se fabrica un score.
        </li>
        <li>
          Un resultado computacional prioriza qué revisar después. No sustituye controles positivos, negativos y neutrales ni validación experimental independiente.
        </li>
      </ul>
    </section>
  );
}