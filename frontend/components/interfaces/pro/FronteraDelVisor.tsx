"use client";

import { Component, type ErrorInfo, type ReactNode } from "react";

/**
 * Frontera de errores de UN visor.
 *
 * EL FALLO QUE CUBRE. La única frontera de la aplicación envuelve el contenido
 * entero (`app/layout.tsx`). Una excepción al dibujar el visor 3D —three.js
 * lanza si no consigue contexto— subía hasta ella y sustituía TODA la pestaña
 * por «Algo salió mal»: el editor, la configuración y la línea de etapas de una
 * evaluación en marcha desaparecían por un fallo que sólo afecta a un recuadro.
 *
 * Aquí el fallo se queda en el recuadro: se avisa a quien montó el visor, que
 * abre otro, y mientras tanto se enseña `respaldo`.
 */
export class FronteraDelVisor extends Component<
  { readonly children: ReactNode; readonly onFallo: (error: Error) => void; readonly respaldo?: ReactNode },
  { readonly fallo: boolean }
> {
  state = { fallo: false };

  static getDerivedStateFromError(): { fallo: boolean } {
    return { fallo: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error("[FronteraDelVisor]", error.message, info.componentStack);
    this.props.onFallo(error);
  }

  render(): ReactNode {
    return this.state.fallo ? this.props.respaldo ?? null : this.props.children;
  }
}
