"use client";

// Panel «Proveedores de IA»: elegir, pegar la clave y autorizar el envío.
//
// La lista (URL, modelos, qué sale) la pone MolChat en su llave verificada; la
// clave la guarda MolDesign por cuenta. Esta pantalla nunca muestra una clave:
// sólo la pista de los cuatro últimos caracteres, y el campo se vacía al guardar.

import React, { useCallback, useEffect, useState } from "react";

import { useLanguage } from "@/context/LanguageContext";
import { getAuthHeaders } from "@/lib/api";
import { fetchBackend } from "@/lib/backendFetch";

export interface ProveedorIA {
  id: string;
  nombre: string;
  host: string;
  remoto: boolean;
  requiere_clave: boolean;
  documentacion: string;
  que_sale: string;
  modelo: string;
  modelos_ejemplo: string[];
  clave: { configurada: boolean; pista: string } | null;
  autorizado: boolean | null;
  activo: boolean;
}

export interface EstadoProveedores {
  disponible: boolean;
  motivo: string;
  activo: string | null;
  proveedores: ProveedorIA[];
}

type Traducir = (clave: string, valores?: Record<string, string>) => string;

const CABECERAS_JSON = { "Content-Type": "application/json" };

/** Qué le decimos al usuario cuando MolDesign rechaza la operación. Nunca incluye la clave. */
async function mensajeDeRechazo(respuesta: Response, traducir: Traducir): Promise<string> {
  const cuerpo = await respuesta.json().catch(() => ({}));
  const detalle = cuerpo && typeof cuerpo === "object" ? cuerpo.detail : undefined;
  const motivo = detalle && typeof detalle === "object" ? String(detalle.motivo ?? "") : "";
  if (respuesta.status === 409 && motivo === "destino_cambiado") return traducir("ia_prov_error_destino");
  if (respuesta.status === 422) return traducir("ia_prov_error_formato");
  if (respuesta.status === 409) return traducir("ia_prov_necesita_clave");
  if (respuesta.status === 503 && typeof detalle === "string") return detalle;
  return traducir("ia_prov_error_generico");
}

export function ProveedoresIA() {
  const { t } = useLanguage();
  const traducir: Traducir = (clave, valores) => t(clave, valores);
  const [estado, setEstado] = useState<EstadoProveedores | null>(null);
  const [cargaError, setCargaError] = useState(false);
  const [aviso, setAviso] = useState<string | null>(null);

  const cargar = useCallback(async () => {
    try {
      const respuesta = await fetchBackend("/molchat-host/proveedores", { headers: getAuthHeaders() });
      if (!respuesta.ok) throw new Error(String(respuesta.status));
      setEstado((await respuesta.json()) as EstadoProveedores);
      setCargaError(false);
    } catch {
      setCargaError(true);
    }
  }, []);

  useEffect(() => {
    void cargar();
  }, [cargar]);

  const operar = async (ruta: string, metodo: string, cuerpo?: unknown, exito?: string) => {
    setAviso(null);
    try {
      const respuesta = await fetchBackend(ruta, {
        method: metodo,
        headers: { ...CABECERAS_JSON, ...getAuthHeaders() },
        body: cuerpo === undefined ? undefined : JSON.stringify(cuerpo),
      });
      if (!respuesta.ok) {
        setAviso(await mensajeDeRechazo(respuesta, traducir));
        return false;
      }
      if (exito) setAviso(exito);
      await cargar();
      return true;
    } catch {
      setAviso(traducir("ia_prov_error_generico"));
      return false;
    }
  };

  if (cargaError) {
    return <p role="alert" className="p-4 text-sm text-[var(--text-secondary)]">{traducir("ia_prov_error_carga")}</p>;
  }
  if (!estado) {
    return <p className="p-4 text-sm text-[var(--text-secondary)]" aria-busy="true">…</p>;
  }
  if (!estado.disponible) {
    return (
      <div className="space-y-2 p-4 text-sm text-[var(--text-secondary)]">
        <p>{traducir("ia_prov_no_disponible")}</p>
        <p className="text-xs">{estado.motivo}</p>
      </div>
    );
  }

  return (
    <div className="space-y-3 p-4">
      <p className="text-sm text-[var(--text-secondary)]">{traducir("ia_prov_intro")}</p>
      {aviso && (
        <p role="status" aria-live="polite" className="rounded-md border border-[var(--border)] p-2 text-sm">
          {aviso}
        </p>
      )}
      <ul className="space-y-3">
        {estado.proveedores.map((proveedor) => (
          <FilaProveedor
            key={proveedor.id}
            proveedor={proveedor}
            traducir={traducir}
            operar={operar}
          />
        ))}
      </ul>
    </div>
  );
}

interface FilaProps {
  proveedor: ProveedorIA;
  traducir: Traducir;
  operar: (ruta: string, metodo: string, cuerpo?: unknown, exito?: string) => Promise<boolean>;
}

function FilaProveedor({ proveedor, traducir, operar }: FilaProps) {
  const [clave, setClave] = useState("");
  const [modelo, setModelo] = useState(proveedor.modelo);
  const [enCurso, setEnCurso] = useState(false);
  const ruta = `/molchat-host/proveedores/${encodeURIComponent(proveedor.id)}/clave`;
  const claveGuardada = proveedor.clave?.configurada === true;
  const puedeUsarse = !proveedor.requiere_clave || (claveGuardada && proveedor.autorizado === true);
  const idModelo = `modelo-${proveedor.id}`;
  const idClave = `clave-${proveedor.id}`;

  const guardar = async (evento: React.FormEvent) => {
    evento.preventDefault();
    if (!clave.trim() || enCurso) return;
    setEnCurso(true);
    const ok = await operar(ruta, "PUT", {
      api_key: clave.trim(),
      host_visto: proveedor.host,
      modelo: modelo.trim() || null,
    }, traducir("ia_prov_guardado"));
    setEnCurso(false);
    // La clave no se conserva en la pantalla, la guarde o no el servidor.
    setClave("");
    return ok;
  };

  return (
    <li className="space-y-2 rounded-lg border border-[var(--border)] p-3">
      <div className="flex items-center justify-between gap-2">
        <strong className="text-sm text-[var(--text)]">{proveedor.nombre}</strong>
        {proveedor.activo && (
          <span className="rounded bg-[var(--bg-alt)] px-2 py-0.5 text-xs">{traducir("ia_prov_activo")}</span>
        )}
      </div>
      <p className="text-xs text-[var(--text-secondary)]">
        {proveedor.remoto
          ? traducir("ia_prov_sale_a", { host: proveedor.host })
          : traducir("ia_prov_local")}
      </p>
      {proveedor.requiere_clave && (
        <p className="text-xs text-[var(--text-secondary)]">
          {claveGuardada
            ? traducir("ia_prov_clave_guardada", { pista: proveedor.clave?.pista ?? "" })
            : traducir("ia_prov_sin_clave")}
          {" · "}
          {proveedor.autorizado
            ? traducir("ia_prov_autorizado")
            : traducir("ia_prov_sin_autorizar")}
        </p>
      )}
      <p className="text-xs text-[var(--text-dim)]">
        {traducir("ia_prov_que_sale")}: {proveedor.que_sale}
      </p>

      {proveedor.requiere_clave && (
        <form onSubmit={guardar} className="space-y-2" autoComplete="off">
          <label htmlFor={idClave} className="block text-xs">{traducir("ia_prov_clave_label")}</label>
          <input
            id={idClave}
            type="password"
            value={clave}
            onChange={(e) => setClave(e.target.value)}
            autoComplete="new-password"
            spellCheck={false}
            className="w-full rounded-md border border-[var(--border)] bg-transparent px-2 py-1 text-sm"
          />
          <label htmlFor={idModelo} className="block text-xs">{traducir("ia_prov_modelo_label")}</label>
          <input
            id={idModelo}
            list={`${idModelo}-ejemplos`}
            value={modelo}
            onChange={(e) => setModelo(e.target.value)}
            placeholder={traducir("ia_prov_modelo_vacio")}
            className="w-full rounded-md border border-[var(--border)] bg-transparent px-2 py-1 text-sm"
          />
          <datalist id={`${idModelo}-ejemplos`}>
            {proveedor.modelos_ejemplo.map((m) => <option key={m} value={m} />)}
          </datalist>
          <div className="flex flex-wrap gap-2">
            <button
              type="submit"
              disabled={!clave.trim() || enCurso}
              className="rounded-md border border-[var(--accent)] px-3 py-1 text-xs disabled:opacity-50"
            >
              {enCurso
                ? traducir("ia_prov_guardando")
                : traducir("ia_prov_guardar", { host: proveedor.host })}
            </button>
            {claveGuardada && (
              <button
                type="button"
                onClick={() => operar(ruta, "DELETE", undefined, traducir("ia_prov_retirado"))}
                className="rounded-md border border-[var(--border)] px-3 py-1 text-xs"
              >
                {traducir("ia_prov_retirar")}
              </button>
            )}
          </div>
        </form>
      )}

      <div className="flex flex-wrap gap-2">
        {proveedor.activo ? (
          <button
            type="button"
            onClick={() => operar("/molchat-host/proveedores/activo", "PUT", { proveedor: null })}
            className="rounded-md border border-[var(--border)] px-3 py-1 text-xs"
          >
            {traducir("ia_prov_dejar_de_usar")}
          </button>
        ) : (
          <button
            type="button"
            disabled={!puedeUsarse}
            onClick={() => operar("/molchat-host/proveedores/activo", "PUT", {
              proveedor: proveedor.id,
              modelo: modelo.trim() || null,
            })}
            className="rounded-md border border-[var(--accent)] px-3 py-1 text-xs disabled:opacity-50"
          >
            {traducir("ia_prov_usar")}
          </button>
        )}
      </div>
      {!puedeUsarse && (
        <p className="text-xs text-[var(--text-dim)]">{traducir("ia_prov_necesita_clave")}</p>
      )}
    </li>
  );
}
