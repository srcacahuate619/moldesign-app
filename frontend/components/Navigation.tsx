"use client";


import { useLanguage } from "@/context/LanguageContext";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "../lib/auth";
import { Menu, Settings, X } from "lucide-react";
import { useState, useRef } from "react";
import Image from "next/image";
import { OptionsMenu } from "./ui/OptionsMenu";
import { DownloadNotifications } from "./DownloadNotifications";

export function Navigation() {
  const { t } = useLanguage();
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const [isOpen, setIsOpen] = useState(false);
  const [showOptions, setShowOptions] = useState(false);
  const optionsBtnRef = useRef<HTMLButtonElement>(null);

  // Tipografía y estilo uniforme para todas las etiquetas del menú
  const linkBaseClass = "text-xs font-mono font-bold uppercase tracking-[0.15em] transition-colors";

  return (
    <>
      <nav className="sticky top-0 z-[100] border-b border-[var(--border)] bg-[var(--bg-alt)] font-mono">
        <div className="relative mx-auto flex max-w-[1600px] items-center justify-between px-6 py-3.5 h-14">

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
              <span>{t("pg_nav_opciones")}</span>
            </button>
          </div>

          {/* Enlaces izquierdos: tres destinos de producto */}
          <div className="hidden md:flex absolute right-[calc(50%+46px)] top-1/2 -translate-y-1/2 items-center gap-8 z-10">
            <Link
              href="/comunidad"
              className={`${linkBaseClass} ${
                pathname === "/comunidad" ? "text-theme font-extrabold" : "text-muted hover:text-theme"
              }`}
            >
              {t("pg_nav_comunidad")}
            </Link>

            <Link
              href="/ciencia"
              className={`${linkBaseClass} ${
                pathname === "/ciencia" ? "text-theme font-extrabold" : "text-muted hover:text-theme"
              }`}
            >
              {t("pg_nav_ciencia")}
            </Link>

            <Link
              href="/evaluation/batch"
              className={`${linkBaseClass} ${
                pathname === "/evaluation/batch" ? "text-theme font-extrabold" : "text-muted hover:text-theme"
              }`}
            >
              {t("pg_nav_batch")}
            </Link>
          </div>

          {/* LOGO CIRCULAR (Centrado Matemático Absoluto) */}
          <Link
            href="/"
            aria-label={t("auto_69b7a67b0314")}
            className="absolute left-1/2 top-1/2 z-20 flex h-9 w-9 shrink-0 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full border border-[var(--border-light)] bg-[var(--bg-alt)] p-1.5 shadow-[0_0_15px_rgba(127,127,127,0.12)] transition-all hover:scale-105 hover:border-purple-400"
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
          <div className="hidden md:flex absolute left-[calc(50%+46px)] top-1/2 -translate-y-1/2 items-center gap-8 z-10">
            <Link
              href="/evaluation"
              className={`${linkBaseClass} ${
                pathname === "/evaluation" ? "text-theme font-extrabold" : "text-muted hover:text-theme"
              }`}
            >
              {t("pn_evaluacion_mayus")}
            </Link>

            <Link
              href="/moldex"
              className={`${linkBaseClass} ${
                pathname === "/moldex" ? "text-theme font-extrabold" : "text-muted hover:text-theme"
              }`}
            >
              {t("pg_nav_moldex")}
            </Link>

            <Link
              href="/history"
              className={`${linkBaseClass} ${
                pathname === "/history" ? "text-theme font-extrabold" : "text-muted hover:text-theme"
              }`}
            >
              {t("pg_nav_historial")}
            </Link>
          </div>

          {/* Extremo Derecho: User & SALIR / ENTRAR */}
          <div className="flex items-center gap-5 z-10">
            <DownloadNotifications />
            <span className={`${linkBaseClass} text-dim font-normal`}>
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
              <button onClick={() => setIsOpen(false)} className="text-muted transition-colors hover:text-theme">
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
              <Link href="/comunidad" onClick={() => setIsOpen(false)} className="block py-2 text-muted hover:text-theme">
                {t("pg_nav_comunidad")}
              </Link>
              <Link href="/ciencia" onClick={() => setIsOpen(false)} className="block py-2 text-muted hover:text-theme">
                {t("pg_nav_ciencia")}
              </Link>
              <Link href="/evaluation/batch" onClick={() => setIsOpen(false)} className="block py-2 text-muted hover:text-theme">
                {t("pg_nav_batch")}
              </Link>
              <Link href="/evaluation" onClick={() => setIsOpen(false)} className="block py-2 text-muted hover:text-theme">
                {t("pn_evaluacion_mayus")}
              </Link>
              <Link href="/moldex" onClick={() => setIsOpen(false)} className="block py-2 text-muted hover:text-theme">
                {t("pg_nav_moldex")}
              </Link>
              <Link href="/history" onClick={() => setIsOpen(false)} className="block py-2 text-muted hover:text-theme">
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
