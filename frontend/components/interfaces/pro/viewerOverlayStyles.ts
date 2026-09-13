/* Hallmark - component: viewer overlay labels - genre: atmospheric - theme: existing MolDesign
 * states: default - hover - focus - active - disabled - loading - error - success
 * contrast: pass - pre-emit critique: P5 H5 E5 S5 R5 V4
 */

/** Chrome propio de MolDesign; nunca estiliza canvas ni controles nativos. */
export const VIEWER_LABEL_BUTTON_CLASS =
  "inline-flex h-8 items-center gap-2 rounded-lg border border-surface-700 bg-surface-950/90 px-3 " +
  "font-mono text-[10px] font-bold uppercase tracking-[0.1em] text-slate-300 shadow-lg backdrop-blur-md " +
  "transition-[background-color,border-color,color,opacity] duration-150 " +
  "hover:border-brand-400/40 hover:bg-surface-900 hover:text-white " +
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400 " +
  "active:bg-surface-800 disabled:cursor-not-allowed disabled:opacity-45";

/** Mismo tamaño en ambos visores: alternar no produce un salto visual. */
export const VIEWER_SWITCH_BUTTON_CLASS =
  `${VIEWER_LABEL_BUTTON_CLASS} w-[124px] shrink-0 justify-center whitespace-nowrap`;

export const VIEWER_LABEL_PANEL_CLASS =
  "rounded-lg border border-surface-700 bg-surface-950/95 shadow-xl backdrop-blur-md";
