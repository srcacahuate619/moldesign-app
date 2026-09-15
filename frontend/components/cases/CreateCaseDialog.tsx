"use client";

// =====================================================================
// CreateCaseDialog — crear un caso pide lo mínimo
// =====================================================================
//
// Solo nombre, tipo aproximado y ubicacion. Las preguntas cientificas NO
// bloquean la creacion: se responden despues, desde «Detalles del caso» dentro
// de la evaluacion, y pueden quedar como "No definido". Un formulario que exige
// la hipotesis antes de dejar empezar es un peaje, no un metodo.
//
// Accesibilidad: `role="dialog"` + `aria-modal`, foco inicial al primer campo,
// foco devuelto al abridor al cerrar, trampa de foco con Tab/Shift+Tab, y
// Escape cierra SOLO si no hay una creacion en curso — interrumpir a mitad de
// una escritura en disco dejaria una carpeta a medias.

import { useCallback, useEffect, useId, useRef, useState } from "react";
import { useLanguage } from "../../context/LanguageContext";
import { FolderOpen, X } from "lucide-react";

import {
  CASE_STUDY_KINDS,
  CASE_STUDY_KIND_LABELS,
  type CaseStudyKind,
} from "../../lib/cases/types";
import { isSafeFolderName, sanitizeFolderName } from "../../lib/cases/schema";

export interface CreateCaseDialogProps {
  readonly open: boolean;
  readonly onClose: () => void;
  /**
   * Crea el caso. **Debe devolver `true` sólo si el caso existe de verdad.**
   * El diálogo se cierra con esa confirmación y no antes: un drenaje fallido
   * que cerrara el diálogo se vería exactamente igual que una creación
   * correcta.
   */
  readonly onCreate: (
    name: string,
    studyKind: CaseStudyKind,
    parentDirectory?: string,
  ) => Promise<boolean>;
  /** Modo carpeta exige elegir dónde. En navegador no aplica. */
  readonly requiresDirectory: boolean;
  readonly storageLabel: string;
  /**
   * Abre el selector nativo de carpeta CONTENEDORA.
   *
   * Devuelve `token` —autoridad opaca— y `displayPath` —sólo presentación—.
   * Van separados a propósito: mezclarlos hacía que se enseñara el UUID del
   * token donde debía ir la ubicación.
   */
  readonly onPickDirectory?: () => Promise<{ token: string; displayPath: string } | null>;
}

const FOCUSABLE =
  'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

export function CreateCaseDialog({
  open,
  onClose,
  onCreate,
  requiresDirectory,
  storageLabel,
  onPickDirectory,
}: CreateCaseDialogProps) {
  const { t } = useLanguage();
  const [name, setName] = useState("");
  const [studyKind, setStudyKind] = useState<CaseStudyKind>("explore-hypothesis");
  const [directory, setDirectory] = useState<{ token: string; displayPath: string } | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const dialogRef = useRef<HTMLDivElement | null>(null);
  const nameRef = useRef<HTMLInputElement | null>(null);
  const openerRef = useRef<HTMLElement | null>(null);

  const titleId = useId();
  const descriptionId = useId();
  const nameErrorId = useId();

  // Recuerda quien abrio el modal para devolverle el foco al cerrar.
  useEffect(() => {
    if (open) {
      openerRef.current = (document.activeElement as HTMLElement) ?? null;
      setName("");
      setStudyKind("explore-hypothesis");
      setDirectory(null);
      setError(null);
      setSubmitting(false);
      // El foco va al primer campo, no al contenedor: quien navega con teclado
      // debe poder escribir sin un Tab extra.
      window.setTimeout(() => nameRef.current?.focus(), 0);
    } else if (openerRef.current) {
      openerRef.current.focus?.();
      openerRef.current = null;
    }
  }, [open]);

  const handleKeyDown = useCallback(
    (event: React.KeyboardEvent<HTMLDivElement>) => {
      if (event.key === "Escape") {
        // Escape NO cierra durante la creacion: hay escritura en disco en curso.
        if (submitting) {
          event.preventDefault();
          return;
        }
        event.stopPropagation();
        onClose();
        return;
      }
      if (event.key !== "Tab") return;
      const root = dialogRef.current;
      if (!root) return;
      const items = Array.from(root.querySelectorAll<HTMLElement>(FOCUSABLE)).filter(
        (el) => el.offsetParent !== null || el === document.activeElement,
      );
      if (items.length === 0) return;
      const first = items[0];
      const last = items[items.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    },
    [onClose, submitting],
  );

  if (!open) return null;

  const trimmed = name.trim();
  const nameProblem =
    trimmed.length === 0
      ? null
      : !isSafeFolderName(trimmed) && requiresDirectory
        ? "Ese nombre no puede convertirse en una carpeta válida. Evita caracteres reservados del sistema."
        : null;

  // Nombre REAL de la carpeta, no el visible sin transformar. Enseñar
  // `Serie A/B` como ruta previa cuando en disco se creará `Serie A-B` es una
  // ruta que no existe.
  let folderPreview: string | null = null;
  if (requiresDirectory && trimmed.length > 0) {
    try {
      folderPreview = sanitizeFolderName(trimmed);
    } catch {
      folderPreview = null;
    }
  }

  const canSubmit =
    trimmed.length > 0 && !nameProblem && !submitting && (!requiresDirectory || Boolean(directory));

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!canSubmit) return;
    setSubmitting(true);
    setError(null);
    try {
      const ok = await onCreate(trimmed, studyKind, directory?.token);
      if (!ok) {
        // No se creó. El diálogo SE QUEDA con lo escrito: cerrarlo aquí haría
        // pasar un fallo por un éxito.
        setError(
          "No se pudo crear el caso. Revisa el aviso de arriba: puede haber un cambio sin guardar en el caso actual.",
        );
        setSubmitting(false);
        return;
      }
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setSubmitting(false);
    }
  };

  const pickDirectory = async () => {
    if (!onPickDirectory) return;
    setError(null);
    try {
      const picked = await onPickDirectory();
      if (picked) setDirectory(picked);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 px-4 py-8"
      onKeyDown={handleKeyDown}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={descriptionId}
        className="w-full max-w-md rounded-lg border border-surface-700 bg-surface-900 p-6 shadow-xl"
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 id={titleId} className="text-base font-semibold tracking-tight text-zinc-100">
              Nuevo caso
            </h2>
            <p id={descriptionId} className="mt-1 text-xs leading-relaxed text-zinc-500">
              {t("ca_solo_lo_minimo")}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={submitting}
            aria-label="Cerrar"
            className="rounded p-1 text-zinc-500 transition-colors hover:text-zinc-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400 disabled:opacity-40"
          >
            <X className="h-4 w-4" aria-hidden="true" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="mt-5 space-y-5">
          <div>
            <label htmlFor="case-name" className="block text-xs font-medium uppercase tracking-wider text-zinc-400">
              Nombre
            </label>
            <input
              id="case-name"
              ref={nameRef}
              value={name}
              onChange={(event) => setName(event.target.value)}
              aria-invalid={Boolean(nameProblem)}
              aria-describedby={nameProblem ? nameErrorId : undefined}
              className="mt-2 w-full rounded-md border border-surface-700 bg-surface-950 px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-600 focus-visible:border-brand-500 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-brand-500"
              placeholder={t("ca_ejemplo_nombre")}
            />
            {nameProblem && (
              <p id={nameErrorId} className="mt-2 text-xs text-amber-400">
                {nameProblem}
              </p>
            )}
          </div>

          <fieldset>
            <legend className="block text-xs font-medium uppercase tracking-wider text-zinc-400">
              Tipo aproximado
            </legend>
            <div className="mt-2 space-y-1.5">
              {CASE_STUDY_KINDS.map((kind) => (
                <label
                  key={kind}
                  className="flex cursor-pointer items-center gap-2.5 rounded px-1 py-1 text-sm text-zinc-300 has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-brand-400"
                >
                  <input
                    type="radio"
                    name="study-kind"
                    value={kind}
                    checked={studyKind === kind}
                    onChange={() => setStudyKind(kind)}
                    className="h-3.5 w-3.5 accent-brand-500"
                  />
                  {CASE_STUDY_KIND_LABELS[kind]}
                </label>
              ))}
            </div>
          </fieldset>

          <div>
            <span className="block text-xs font-medium uppercase tracking-wider text-zinc-400">
              {t("ca_ubicacion")}
            </span>
            {requiresDirectory ? (
              <div className="mt-2">
                <button
                  type="button"
                  onClick={pickDirectory}
                  className="inline-flex items-center gap-2 rounded-md border border-surface-700 px-3 py-1.5 text-xs text-zinc-300 transition-colors hover:border-surface-600 hover:text-zinc-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400"
                >
                  <FolderOpen className="h-3.5 w-3.5" aria-hidden="true" />
                  Elegir carpeta…
                </button>
                <p className="mt-2 break-all font-mono text-[11px] text-zinc-500">
                  {directory
                    ? `${directory.displayPath}${folderPreview ? ` › ${folderPreview}` : ""}`
                    : "Sin carpeta elegida."}
                </p>
                {folderPreview && folderPreview !== trimmed && (
                  <p className="mt-1 text-[11px] leading-relaxed text-zinc-500">
                    {t("ca_carpeta_se_llamara")} <span className="font-mono">{folderPreview}</span>{t("ca_nombre_visible_conserva")}
                  </p>
                )}
              </div>
            ) : (
              <p className="mt-2 font-mono text-[11px] text-zinc-500">{storageLabel}</p>
            )}
          </div>

          {error && (
            <p role="alert" className="rounded border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-300">
              {error}
            </p>
          )}

          <div className="flex justify-end gap-2 border-t border-surface-800 pt-4">
            <button
              type="button"
              onClick={onClose}
              disabled={submitting}
              className="rounded-md px-3 py-1.5 text-sm text-zinc-400 transition-colors hover:text-zinc-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400 disabled:opacity-40"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={!canSubmit}
              className="rounded-md border border-brand-500/40 bg-brand-600 px-4 py-1.5 text-sm font-medium text-white transition-colors hover:bg-brand-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400 disabled:cursor-not-allowed disabled:opacity-40"
            >
              {submitting ? "Creando…" : "Crear caso"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default CreateCaseDialog;
