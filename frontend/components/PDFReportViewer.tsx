"use client";

import React, { useEffect, useState, useRef } from "react";
import { fetchCertificateBlobUrl, downloadCertificate } from "../lib/api";
import { Download, Maximize, FileText, Loader2, ShieldCheck, AlertCircle } from "lucide-react";
import { CertificationModal, type CertificationSuccess } from "./CertificationModal";

interface PDFReportViewerProps {
  moleculeId: string;
  isCertified: boolean;
  /** Actualiza el resultado local con una firma que el modal ya publicó. */
  onCertify?: (result: CertificationSuccess) => void | Promise<void>;
  isCertifying?: boolean;
}

export function PDFReportViewer({ moleculeId, isCertified, onCertify, isCertifying = false }: PDFReportViewerProps) {
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  // DOC 71, DEFECTO E1. La versión anterior tenía dos fugas encadenadas:
  //
  //   1. la petición descartada NO se cancelaba. React monta, desmonta y vuelve
  //      a montar el efecto en desarrollo, así que salían DOS generaciones del
  //      mismo certificado. Cada una es un render completo de ReportLab, y
  //      hasta este arreglo bloqueaban el bucle de eventos del backend: dos
  //      bloqueos encadenados, y el WebView cortando la petición en vuelo con
  //      `Failed to fetch`.
  //
  //   2. la URL del blob de la petición descartada nunca se revocaba: la
  //      limpieza leía `url` por cierre, y en la primera pasada `url` todavía
  //      era `""` porque el `await` no había resuelto. El objeto quedaba vivo
  //      hasta recargar la ventana.
  //
  // Se aborta con `AbortController` y se revoca contra una referencia que
  // sobrevive al cierre.
  const urlActual = useRef<string | null>(null);

  useEffect(() => {
    const control = new AbortController();
    let activo = true;

    (async () => {
      setIsLoading(true);
      setError(null);
      try {
        const url = await fetchCertificateBlobUrl(moleculeId, control.signal);
        if (!activo) {
          // Llegó después de que nadie la esperara: se libera aquí, que es el
          // único sitio donde todavía se conoce.
          URL.revokeObjectURL(url);
          return;
        }
        if (urlActual.current) URL.revokeObjectURL(urlActual.current);
        urlActual.current = url;
        setBlobUrl(url);
        setIsLoading(false);
      } catch (err: any) {
        // Abortar es lo que pedimos, no un fallo que mostrar.
        if (err?.name === "AbortError" || !activo) return;
        setError(err?.message || "Error al cargar el reporte");
        setIsLoading(false);
      }
    })();

    return () => {
      activo = false;
      control.abort();
    };
  }, [moleculeId, isCertified]);

  // La última URL viva se libera al desmontar de verdad, no en cada re-efecto.
  useEffect(() => () => {
    if (urlActual.current) URL.revokeObjectURL(urlActual.current);
  }, []);

  if (isLoading) {
    return (
      <div className="w-full h-full min-h-[400px] flex flex-col items-center justify-center bg-surface-900 border border-surface-800 rounded-lg">
        <Loader2 className="w-8 h-8 text-brand-500 animate-spin mb-4" />
        <div className="text-surface-400 font-mono text-xs uppercase tracking-wider">Generando vista previa…</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="w-full h-full min-h-[400px] flex flex-col items-center justify-center bg-red-500/5 border border-red-500/20 rounded-lg p-6 text-center">
        <AlertCircle className="w-10 h-10 text-red-400 mb-4" />
        <div className="text-red-400 font-bold mb-2">No se pudo cargar el dossier</div>
        <div className="text-surface-400 text-sm max-w-md">{error}</div>
      </div>
    );
  }

  return (
    <>
      <div ref={containerRef} className="flex flex-col w-full h-full min-h-[500px] bg-surface-950 border border-surface-800 rounded-lg overflow-hidden relative">
        {/* Dossier toolbar */}
        <div className="flex items-center justify-between px-4 py-3 bg-surface-900 border-b border-surface-800 z-10 shadow-sm relative">
          <div className="flex items-center gap-3">
            <FileText className="w-4 h-4 text-brand-400" />
            <span className="font-mono text-xs text-surface-300 tracking-wider">DOSSIER_{moleculeId.split('-')[0].toUpperCase()}.PDF</span>
          </div>
          
          <div className="flex items-center gap-2">
            <button
              onClick={() => {
                if (containerRef.current) {
                  if (document.fullscreenElement) {
                    document.exitFullscreen();
                  } else {
                    containerRef.current.requestFullscreen();
                  }
                }
              }}
              className="grid h-11 w-11 place-items-center rounded text-surface-400 transition-colors hover:bg-surface-800 hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-400"
              title="Pantalla completa"
            >
              <Maximize className="w-4 h-4" />
            </button>
            
            <div className="w-px h-4 bg-surface-700 mx-1" />
            
            <button
              onClick={() => downloadCertificate(moleculeId)}
              className="flex h-11 items-center gap-2 whitespace-nowrap rounded bg-surface-800 px-3 font-mono text-xs font-bold text-surface-300 transition-colors hover:bg-brand-500 hover:text-surface-950 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-400"
            >
              <Download className="w-3 h-3" />
              <span className="hidden sm:inline">DESCARGAR</span>
            </button>
          </div>
        </div>

        {/* PDF Viewer Canvas Area */}
        <div className="flex-1 overflow-hidden relative bg-[#0f1015]">
          {!isCertified && (
            <div className="absolute top-0 inset-x-0 z-20 bg-amber-500/10 border-b border-amber-500/20 px-4 py-2 flex items-center justify-between backdrop-blur-md">
              <div className="flex items-center gap-2 text-amber-500 text-sm font-medium">
                <AlertCircle className="w-4 h-4" />
                <span>La integridad de este dossier aún no está registrada</span>
              </div>
              {onCertify && (
                <button
                  onClick={() => setShowModal(true)}
                  disabled={isCertifying}
                  className="flex min-h-11 items-center gap-2 whitespace-nowrap rounded bg-amber-500 px-3 font-mono text-xs font-bold uppercase text-surface-950 transition-colors hover:bg-amber-400 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-amber-200 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <ShieldCheck className="w-3 h-3" />
                  Registrar integridad
                </button>
              )}
            </div>
          )}
          
          <div className="absolute inset-0 z-10 pt-[40px]">
            {blobUrl && (
              <iframe 
                src={`${blobUrl}#toolbar=0`} 
                className="w-full h-full border-none bg-transparent"
                title="Vista previa del dossier PDF"
              />
            )}
          </div>
        </div>
      </div>
      
      {showModal && (
        <CertificationModal 
          moleculeId={moleculeId} 
          onClose={() => setShowModal(false)}
          onSuccess={(result) => {
            void onCertify?.(result);
          }}
        />
      )}
    </>
  );
}
