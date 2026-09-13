"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "../lib/auth";
import { Menu, Settings, X } from "lucide-react";
import { useState, useRef } from "react";
import Image from "next/image";
import { OptionsMenu } from "./ui/OptionsMenu";
import { DownloadNotifications } from "./DownloadNotifications";

export function Navigation() {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const [isOpen, setIsOpen] = useState(false);
  const [showOptions, setShowOptions] = useState(false);
  const optionsBtnRef = useRef<HTMLButtonElement>(null);

  // Tipografía y estilo uniforme para todas las etiquetas del menú
  const linkBaseClass = "text-xs font-mono font-bold uppercase tracking-[0.15em] transition-colors";

  return (
    <>
      <nav className="sticky top-0 z-[100] border-b border-zinc-800/80 bg-black font-mono">
        <div className="relative mx-auto flex max-w-[1600px] items-center justify-between px-6 py-3.5 h-14">

          {/* Extremo izquierdo: panel utilitario único */}
          <div className="flex items-center gap-2 z-10">
            <button
              ref={optionsBtnRef}
              type="button"
              aria-expanded={showOptions}
              aria-haspopup="dialog"
              onClick={() => setShowOptions(true)}
              className={`${linkBaseClass} flex cursor-pointer items-center gap-2 ${showOptions ? "text-purple-300" : "text-white hover:text-purple-300"}`}
            >
              <Settings size={14} className="shrink-0" aria-hidden="true" />
              <span>OPCIONES</span>
            </button>
          </div>

          {/* Enlaces izquierdos: tres destinos de producto */}
          <div className="hidden md:flex absolute right-[calc(50%+46px)] top-1/2 -translate-y-1/2 items-center gap-8 z-10">
            <Link
              href="/comunidad"
              className={`${linkBaseClass} ${
                pathname === "/comunidad" ? "text-white font-extrabold" : "text-zinc-400 hover:text-white"
              }`}
            >
              COMUNIDAD
            </Link>

            <Link
              href="/ciencia"
              className={`${linkBaseClass} ${
                pathname === "/ciencia" ? "text-white font-extrabold" : "text-zinc-400 hover:text-white"
              }`}
            >
              CIENCIA
            </Link>

            <Link
              href="/evaluation/batch"
              className={`${linkBaseClass} ${
                pathname === "/evaluation/batch" ? "text-white font-extrabold" : "text-zinc-400 hover:text-white"
              }`}
            >
              BATCH
            </Link>
          </div>

          {/* LOGO CIRCULAR (Centrado Matemático Absoluto) */}
          <Link
            href="/"
            aria-label="MolDesign — ir al inicio"
            className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 h-9 w-9 rounded-full border border-white/80 flex items-center justify-center p-1.5 bg-black hover:border-purple-400 hover:scale-105 transition-all shadow-[0_0_15px_rgba(255,255,255,0.1)] shrink-0 z-20"
          >
            <Image
              src="/logo.png"
              alt="MolDesign AI Logo"
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
                pathname === "/evaluation" ? "text-white font-extrabold" : "text-zinc-400 hover:text-white"
              }`}
            >
              EVALUACIÓN
            </Link>

            <Link
              href="/moldex"
              className={`${linkBaseClass} ${
                pathname === "/moldex" ? "text-white font-extrabold" : "text-zinc-400 hover:text-white"
              }`}
            >
              MOLDEX
            </Link>

            <Link
              href="/history"
              className={`${linkBaseClass} ${
                pathname === "/history" ? "text-white font-extrabold" : "text-zinc-400 hover:text-white"
              }`}
            >
              HISTORIAL
            </Link>
          </div>

          {/* Extremo Derecho: User & SALIR / ENTRAR */}
          <div className="flex items-center gap-5 z-10">
            <DownloadNotifications />
            <span className={`${linkBaseClass} text-zinc-500 font-normal`}>
              {user ? user.username : "Desktop User"}
            </span>

            {user ? (
              <button
                onClick={logout}
                className={`${linkBaseClass} text-white hover:text-purple-300 cursor-pointer`}
              >
                SALIR
              </button>
            ) : (
              <Link
                href="/login"
                className={`${linkBaseClass} text-white hover:text-purple-300`}
              >
                ENTRAR
              </Link>
            )}

            {/* Mobile Menu Button */}
            <button
              className="md:hidden p-2 text-zinc-400 hover:text-white transition-colors"
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

          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[90vw] max-w-sm bg-zinc-950 border border-zinc-800 rounded-2xl shadow-2xl flex flex-col overflow-hidden">

            <div className="flex items-center justify-between px-6 py-4 border-b border-zinc-800 bg-black">
              <span className="text-xs font-mono tracking-widest text-purple-300 uppercase font-bold">
                Navegación
              </span>
              <button onClick={() => setIsOpen(false)} className="text-zinc-400 hover:text-white transition-colors">
                <X size={18} />
              </button>
            </div>

            <div className="p-6 space-y-4 text-xs font-mono font-bold uppercase tracking-widest">
              <button
                type="button"
                onClick={() => { setIsOpen(false); setShowOptions(true); }}
                className="block w-full cursor-pointer py-2 text-left text-zinc-300 hover:text-white"
              >
                OPCIONES
              </button>
              <Link href="/comunidad" onClick={() => setIsOpen(false)} className="block py-2 text-zinc-300 hover:text-white">
                COMUNIDAD
              </Link>
              <Link href="/ciencia" onClick={() => setIsOpen(false)} className="block py-2 text-zinc-300 hover:text-white">
                CIENCIA
              </Link>
              <Link href="/evaluation/batch" onClick={() => setIsOpen(false)} className="block py-2 text-zinc-300 hover:text-white">
                BATCH
              </Link>
              <Link href="/evaluation" onClick={() => setIsOpen(false)} className="block py-2 text-zinc-300 hover:text-white">
                EVALUACIÓN
              </Link>
              <Link href="/moldex" onClick={() => setIsOpen(false)} className="block py-2 text-zinc-300 hover:text-white">
                MOLDEX
              </Link>
              <Link href="/history" onClick={() => setIsOpen(false)} className="block py-2 text-zinc-300 hover:text-white">
                HISTORIAL
              </Link>
              <div className="pt-4 border-t border-zinc-800 flex items-center justify-between">
                <span className="text-zinc-500">{user ? user.username : "Desktop User"}</span>
                {user ? (
                  <button onClick={() => { logout(); setIsOpen(false); }} className="text-white hover:text-purple-300">
                    SALIR
                  </button>
                ) : (
                  <Link href="/login" onClick={() => setIsOpen(false)} className="text-white hover:text-purple-300">
                    ENTRAR
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
