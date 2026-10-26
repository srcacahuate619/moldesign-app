"use client";

import { useState } from "react";
import { usePathname } from "next/navigation";
import dynamic from "next/dynamic";
import { KeepAliveContext } from "../context/KeepAliveContext";

const KeepAliveLoader = () => (
  <div className="flex h-screen items-center justify-center bg-[var(--bg)]">
    <div className="h-10 w-10 animate-spin rounded-full border-2 border-purple-500 border-t-transparent" />
  </div>
);

/**
 * Pestañas que no se desmontan al salir de ellas. Molcy y Preparación entran el 2026-10-10 (decisión del propietario): al
 * volver se recargaban enteras y perdían lo elegido (Preparación, el caso abierto y su auditoría). Cada una decide qué
 * refresca al volver, en silencio, con `KeepAliveContext`.
 */
const PAGINAS = {
  "/evaluation": dynamic(() => import("../app/evaluation/page"), { ssr: false, loading: KeepAliveLoader }),
  "/evaluation/batch": dynamic(() => import("../app/evaluation/batch/page"), { ssr: false, loading: KeepAliveLoader }),
  "/moldex": dynamic(() => import("../app/moldex/page"), { ssr: false, loading: KeepAliveLoader }),
  "/history": dynamic(() => import("../app/history/page"), { ssr: false, loading: KeepAliveLoader }),
  "/molcy": dynamic(() => import("../app/molcy/page"), { ssr: false, loading: KeepAliveLoader }),
  "/preparacion": dynamic(() => import("../app/preparacion/page"), { ssr: false, loading: KeepAliveLoader }),
} as const;

type KeepAliveRoute = keyof typeof PAGINAS;
export const KEEP_ALIVE_ROUTES = Object.keys(PAGINAS) as KeepAliveRoute[];

export function PersistentKeepAliveLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  // Lazy-boot: cada página keep-alive se carga solo al visitarla por primera vez.
  // Una vez cargada, NUNCA se desmonta — solo se alterna display:block/none.
  // Esto preserva el state (SMILES, target, Molstar instance, scroll, etc.)
  // incluso al navegar a sub-rutas (/evaluation/batch) o rutas externas (/comunidad).
  const [booted, setBooted] = useState<Record<string, boolean>>({});

  // Marcar ruta como booted en el primer render (idempotente)
  if (KEEP_ALIVE_ROUTES.includes(pathname as KeepAliveRoute) && !booted[pathname]) {
    setBooted(prev => ({ ...prev, [pathname]: true }));
  }

  // Una ruta keep-alive está "activa" solo cuando el pathname coincide EXACTAMENTE.
  // Sub-rutas como /evaluation/batch NO activan /evaluation (quedaría display:none)
  // para no colapsar visualmente con el children que se renderiza aparte.
  const isActive = (route: KeepAliveRoute) => pathname === route;
  const isKeepAliveRoute = KEEP_ALIVE_ROUTES.includes(pathname as KeepAliveRoute);

  // Si la ruta actual es keep-alive, el children de Next.js NO debe renderizarse
  // (ya está cubierto por la página keep-alive correspondiente). Evitamos duplicar.
  // Si NO es keep-alive (Inicio, /comunidad, /login, etc.), renderizamos
  // el children pero SIN desmontar las páginas keep-alive — quedan display:none.
  const showChildren = !isKeepAliveRoute;

  return (
    <div className="relative w-full flex-1">
      {/* Páginas keep-alive: siempre en el DOM, solo alternan display. Nunca se desmontan → preservan state y Molstar
          instance. TODAS reciben `KeepAliveContext`: Moldex e Historial lo leían para recargar al volver, pero no se
          lo daban (sólo Evaluación y Batch) y con el valor por defecto, `true`, la recarga nunca ocurría. */}
      {KEEP_ALIVE_ROUTES.map((route) => {
        if (!booted[route]) return null;
        const Pagina = PAGINAS[route];
        return (
          <div
            key={route}
            data-keep-alive={route}
            className="w-full flex-1"
            style={{ display: isActive(route) ? "block" : "none" }}
            aria-hidden={!isActive(route)}
          >
            <KeepAliveContext.Provider value={isActive(route)}>
              <Pagina />
            </KeepAliveContext.Provider>
          </div>
        );
      })}

      {/* Rutas NO keep-alive: se renderizan AQUÍ, al lado de las keep-alive
          (que quedan display:none). Así no se desmontan las keep-alive. */}
      {showChildren && (
        <div className="w-full flex-1">
          {children}
        </div>
      )}
    </div>
  );
}

export default PersistentKeepAliveLayout;
