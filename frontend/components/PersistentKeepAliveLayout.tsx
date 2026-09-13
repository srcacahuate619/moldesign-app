"use client";

import { useState } from "react";
import { usePathname } from "next/navigation";
import dynamic from "next/dynamic";
import { KeepAliveContext } from "../context/KeepAliveContext";

const KeepAliveLoader = () => (
  <div className="flex h-screen items-center justify-center bg-[#050508]">
    <div className="h-10 w-10 animate-spin rounded-full border-2 border-purple-500 border-t-transparent" />
  </div>
);

const EvaluationPage = dynamic(() => import("../app/evaluation/page"), {
  ssr: false,
  loading: KeepAliveLoader,
});
const MoldexPage = dynamic(() => import("../app/moldex/page"), {
  ssr: false,
  loading: KeepAliveLoader,
});
const HistoryPage = dynamic(() => import("../app/history/page"), {
  ssr: false,
  loading: KeepAliveLoader,
});
const BatchPage = dynamic(() => import("../app/evaluation/batch/page"), {
  ssr: false,
  loading: KeepAliveLoader,
});

type KeepAliveRoute = "/evaluation" | "/evaluation/batch" | "/moldex" | "/history";
const KEEP_ALIVE_ROUTES: KeepAliveRoute[] = ["/evaluation", "/evaluation/batch", "/moldex", "/history"];

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
  // Si NO es keep-alive (/evaluation/batch, /comunidad, /login, etc.), renderizamos
  // el children pero SIN desmontar las páginas keep-alive — quedan display:none.
  const showChildren = !isKeepAliveRoute;

  return (
    <div className="relative w-full flex-1">
      {/* Páginas keep-alive: siempre en el DOM, solo alternan display.
          Nunca se desmontan → preservan state y Molstar instance. */}
      {booted["/evaluation"] && (
        <div
          className="w-full flex-1"
          style={{ display: isActive("/evaluation") ? "block" : "none" }}
          aria-hidden={!isActive("/evaluation")}
        >
          <KeepAliveContext.Provider value={isActive("/evaluation")}>
            <EvaluationPage />
          </KeepAliveContext.Provider>
        </div>
      )}

      {booted["/evaluation/batch"] && (
        <div
          className="w-full flex-1"
          style={{ display: isActive("/evaluation/batch") ? "block" : "none" }}
          aria-hidden={!isActive("/evaluation/batch")}
        >
          <KeepAliveContext.Provider value={isActive("/evaluation/batch")}>
            <BatchPage />
          </KeepAliveContext.Provider>
        </div>
      )}
      {booted["/moldex"] && (
        <div
          className="w-full flex-1"
          style={{ display: isActive("/moldex") ? "block" : "none" }}
          aria-hidden={!isActive("/moldex")}
        >
          <MoldexPage />
        </div>
      )}

      {booted["/history"] && (
        <div
          className="w-full flex-1"
          style={{ display: isActive("/history") ? "block" : "none" }}
          aria-hidden={!isActive("/history")}
        >
          <HistoryPage />
        </div>
      )}

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
