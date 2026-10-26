"use client";


import { useLanguage } from "@/context/LanguageContext";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "../lib/auth";
import { Menu, Settings, X } from "lucide-react";
import { useState, useRef } from "react";
import Image from "next/image";
import { OptionsMenu } from "./ui/OptionsMenu";
import { NativeJobNotifications } from "./NativeJobNotifications";
import { DownloadNotifications } from "./DownloadNotifications";
import { PildoraBeta } from "./ui/PildoraBeta";

export type Pestana = "inicio" | "preparacion" | "molcy" | "batch" | "evaluation" | "moldex" | "history";

/** La pestaña en la que está el usuario. Batch vive bajo /evaluation, así que se mira antes. */
export function pestanaActiva(pathname: string | null): Pestana | null {
  const ruta = (pathname || "/").replace(/\/+$/, "") || "/";
  if (ruta === "/") return "inicio";
  if (ruta === "/evaluation/batch" || ruta.startsWith("/evaluation/batch/")) return "batch";
  for (const pestana of ["preparacion", "molcy", "evaluation", "moldex", "history"] as const) {
    if (ruta === `/${pestana}` || ruta.startsWith(`/${pestana}/`)) return pestana;
  }
  return null;
}

export function Navigation() {
  const { t } = useLanguage();
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const [isOpen, setIsOpen] = useState(false);
  const [showOptions, setShowOptions] = useState(false);
  const optionsBtnRef = useRef<HTMLButtonElement>(null);
  const activa = pestanaActiva(pathname);

  // Tipografía y estilo uniforme para todas las etiquetas del menú
  const linkBaseClass = "text-xs font-mono font-bold uppercase tracking-[0.15em] transition-colors";
  // La pestaña activa se ve sombreada, no sólo en negrita: el usuario sabe dónde está (decisión del propietario, 2026-10-10).
  // El relleno lateral (px-3) va en todas y los grupos se anclan 12 px más cerca del logo, así que los textos no se mueven.
  const pestanaClass = (pestana: Pestana) => `${linkBaseClass} rounded-md px-3 py-1.5 ${activa === pestana
    ? "bg-accent-strong/15 font-extrabold text-theme ring-1 ring-inset ring-accent-strong/50 shadow-[0_0_14px_rgba(167,139,250,0.25)]"
    : "text-muted hover:bg-[var(--bg-secondary)] hover:text-theme"}`;
  const pestanaMovilClass = (pestana: Pestana) => `block rounded-md px-3 py-2 ${activa === pestana
    ? "bg-accent-strong/15 text-theme ring-1 ring-inset ring-accent-strong/50"
    : "text-muted hover:text-theme"}`;
  const actual = (pestana: Pestana) => (activa === pestana ? ("page" as const) : undefined);

  return (
    <>
      <nav className="sticky top-0 z-[100] border-b border-[var(--border)] bg-[var(--bg-alt)] font-mono">
        <div className="relative mx-auto flex h-14 max-w-[1600px] items-center justify-between px-3 py-3.5 sm:px-6">

          {/* Extremo izquierdo: panel utilitario único */}
          <div className="flex items-center gap-2 z-10">
            <button
              ref={optionsBtnRef}
              type="button"
              aria-expanded={showOptions}
              aria-haspopup="dialog"
              onClick={() => setShowOptions(true)}
              className={`${linkBaseClass} flex cursor-pointer items-center gap-2 ${showOptions ? "text-purple-400 dark:text-purple-300" : "text-theme hover:text-purple-500 dark:hover:text-purple-300"}`}
            >
              <Settings size={14} className="shrink-0" aria-hidden="true" />
              <span className="hidden sm:inline">{t("pg_nav_opciones")}</span>
            </button>
          </div>

          {/* Enlaces izquierdos: trabajo científico y comunicación visual.
              Las rutas históricas /comunidad y /ciencia siguen conservadas. */}
          <div className="hidden md:flex absolute right-[calc(50%+34px)] top-1/2 -translate-y-1/2 items-center gap-2 z-10">
            <Link href="/preparacion" aria-current={actual("preparacion")} className={pestanaClass("preparacion")}>
              {t("pg_nav_preparacion")}
            </Link>

            <Link href="/molcy" aria-current={actual("molcy")} className={pestanaClass("molcy")}>
              Molcy
              <PildoraBeta />
            </Link>

            <Link href="/evaluation/batch" aria-current={actual("batch")} className={pestanaClass("batch")}>
              {t("pg_nav_batch")}
            </Link>
          </div>

          {/* LOGO CIRCULAR (Centrado Matemático Absoluto) */}
          <Link
            href="/"
            aria-label={t("auto_69b7a67b0314")}
            aria-current={actual("inicio")}
            className={`absolute left-1/2 top-1/2 z-20 flex h-9 w-9 shrink-0 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full border bg-[var(--bg-alt)] p-1.5 transition-all hover:scale-105 hover:border-purple-400 ${activa === "inicio"
              ? "border-accent-strong ring-2 ring-accent-strong/40 shadow-[0_0_18px_rgba(167,139,250,0.45)]"
              : "border-[var(--border-light)] shadow-[0_0_15px_rgba(127,127,127,0.12)]"}`}
          >
            <Image
              src="/logo.png"
              alt={t("pg_nav_logo_alt")}
              width={24}
              height={24}
              className="object-contain"
            />
          </Link>

          {/* Enlaces derechos: flujo operativo principal */}
          <div className="hidden md:flex absolute left-[calc(50%+34px)] top-1/2 -translate-y-1/2 items-center gap-2 z-10">
            <Link href="/evaluation" aria-current={actual("evaluation")} className={pestanaClass("evaluation")}>
              {t("pn_evaluacion_mayus")}
            </Link>

            <Link href="/moldex" aria-current={actual("moldex")} className={pestanaClass("moldex")}>
              {t("pg_nav_moldex")}
            </Link>

            <Link href="/history" aria-current={actual("history")} className={pestanaClass("history")}>
              {t("pg_nav_historial")}
            </Link>
          </div>

          {/* Extremo Derecho: User & SALIR / ENTRAR */}
          <div className="z-10 flex items-center gap-2 sm:gap-5">
            <NativeJobNotifications />
            <DownloadNotifications />
            {/* Medido en el export (2026-10-04): a 1024 px —el ancho MÍNIMO de la ventana— «HISTORIAL» y este
                nombre se pisaban 20 px; se ocultó por debajo de 1100 px. Medido otra vez el 2026-10-10 con el texto
                largo, «USUARIO DE ESCRITORIO» (castellano, sin sesión): a 1100 px lo pisaba 63 px, y con el nombre
                visible la campana pisaba «HISTORIAL» hasta 1360 px (9 px); desde 1380 px, nada. Por eso no se enseña
                por debajo de 1440 px, con margen. Sin el nombre, de 1024 a 1420 px no se pisa nada. */}
            <span className={`${linkBaseClass} hidden font-normal text-dim min-[1440px]:inline`}>
              {user ? user.username : t("pg_nav_usuario_escritorio")}
            </span>

            {user ? (
              <button
                onClick={logout}
                className={`${linkBaseClass} cursor-pointer text-theme hover:text-purple-500 dark:hover:text-purple-300`}
              >
                {t("pg_nav_salir")}
              </button>
            ) : (
              <Link
                href="/login"
                className={`${linkBaseClass} text-theme hover:text-purple-500 dark:hover:text-purple-300`}
              >
                {t("pg_nav_entrar")}
              </Link>
            )}

            {/* Mobile Menu Button */}
            <button
              className="p-2 text-muted transition-colors hover:text-theme md:hidden"
              onClick={() => setIsOpen(!isOpen)}
              aria-label={isOpen ? t("c_cerrar_menu") : t("c_abrir_menu")}
              aria-expanded={isOpen}
            >
              {isOpen ? <X size={20} /> : <Menu size={20} />}
            </button>
          </div>

        </div>
      </nav>

      <OptionsMenu isOpen={showOptions} onClose={() => setShowOptions(false)} triggerRef={optionsBtnRef} />


      {/* Mobile Drawer Navigation */}
      {isOpen && (
        <div className="fixed inset-0 z-[200] md:hidden font-mono">
          <div className="absolute inset-0 bg-black/90 backdrop-blur-md" onClick={() => setIsOpen(false)} />

          <div className="absolute top-1/2 left-1/2 flex w-[90vw] max-w-sm -translate-x-1/2 -translate-y-1/2 flex-col overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--bg-card)] shadow-2xl">

            <div className="flex items-center justify-between border-b border-[var(--border)] bg-[var(--bg-alt)] px-6 py-4">
              <span className="font-mono text-xs font-bold uppercase tracking-widest text-purple-500 dark:text-purple-300">
                {t("pn_navegacion")}
              </span>
              <button onClick={() => setIsOpen(false)} aria-label={t("c_cerrar_menu")} className="text-muted transition-colors hover:text-theme">
                <X size={18} />
              </button>
            </div>

            <div className="p-6 space-y-4 text-xs font-mono font-bold uppercase tracking-widest">
              <button
                type="button"
                onClick={() => { setIsOpen(false); setShowOptions(true); }}
                className="block w-full cursor-pointer py-2 text-left text-muted hover:text-theme"
              >
                {t("pg_nav_opciones")}
              </button>
              <Link href="/preparacion" onClick={() => setIsOpen(false)} aria-current={actual("preparacion")} className={pestanaMovilClass("preparacion")}>
                {t("pg_nav_preparacion")}
              </Link>
              <Link href="/molcy" onClick={() => setIsOpen(false)} aria-current={actual("molcy")} className={pestanaMovilClass("molcy")}>
                Molcy
                <PildoraBeta />
              </Link>
              <Link href="/evaluation/batch" onClick={() => setIsOpen(false)} aria-current={actual("batch")} className={pestanaMovilClass("batch")}>
                {t("pg_nav_batch")}
              </Link>
              <Link href="/evaluation" onClick={() => setIsOpen(false)} aria-current={actual("evaluation")} className={pestanaMovilClass("evaluation")}>
                {t("pn_evaluacion_mayus")}
              </Link>
              <Link href="/moldex" onClick={() => setIsOpen(false)} aria-current={actual("moldex")} className={pestanaMovilClass("moldex")}>
                {t("pg_nav_moldex")}
              </Link>
              <Link href="/history" onClick={() => setIsOpen(false)} aria-current={actual("history")} className={pestanaMovilClass("history")}>
                {t("pg_nav_historial")}
              </Link>
              <div className="flex items-center justify-between border-t border-[var(--border)] pt-4">
                <span className="text-dim">{user ? user.username : t("pg_nav_usuario_escritorio")}</span>
                {user ? (
                  <button onClick={() => { logout(); setIsOpen(false); }} className="text-theme hover:text-purple-500 dark:hover:text-purple-300">
                    {t("pg_nav_salir")}
                  </button>
                ) : (
                  <Link href="/login" onClick={() => setIsOpen(false)} className="text-theme hover:text-purple-500 dark:hover:text-purple-300">
                    {t("pg_nav_entrar")}
                  </Link>
                )}
              </div>
            </div>

          </div>
        </div>
      )}
    </>
  );
}
