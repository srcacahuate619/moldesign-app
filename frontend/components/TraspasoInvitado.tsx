"use client";


import { useLanguage } from "@/context/LanguageContext";
/**
 * El ofrecimiento de traspaso, que era la pieza que faltaba.
 *
 * `POST /auth/traspaso` existe y funciona desde el sprint anterior, pero nada
 * en la interfaz lo llamaba: quien probaba la aplicación como invitado y luego
 * se registraba veía su cuenta nueva vacía y su trabajo desaparecido. No lo
 * estaba —seguía siendo del invitado, aislado y correcto— pero desde la pantalla
 * era indistinguible de haberlo perdido.
 *
 * Tres reglas de esta superficie:
 *
 * 1. **No mueve nada solo.** Aparece, dice exactamente qué movería, y espera.
 *    Un traspaso automático al registrarse mezclaría el trabajo de quien sólo
 *    estaba probando la máquina de otro.
 * 2. **Cuenta lo que hay, no lo que suena bien.** Los casos sin resultado se
 *    cuentan aparte: «3 casos, 1 con resultado» y no «3 evaluaciones».
 * 3. **Se puede decir que no.** Descartar olvida el ofrecimiento sin tocar el
 *    trabajo del invitado, que sigue donde estaba.
 */

import { useCallback, useEffect, useState } from "react";

import { useAuth } from "../lib/auth";
import { traspasarDelInvitado } from "../lib/api";
import { crearRepositorioDeCasos } from "../lib/cases/factory";
import {
  ejecutarTraspaso,
  inventarioDelInvitado,
  invitadoPendienteDeTraspaso,
  olvidarInvitado,
  type IdentidadInvitada,
  type InventarioInvitado,
  type ResultadoTraspaso,
} from "../lib/traspaso";

type Fase = "oculto" | "ofreciendo" | "moviendo" | "hecho" | "error";

export function TraspasoInvitado() {
  const { t } = useLanguage();
  const { user } = useAuth();
  const [invitado, setInvitado] = useState<IdentidadInvitada | null>(null);
  const [inventario, setInventario] = useState<InventarioInvitado | null>(null);
  const [fase, setFase] = useState<Fase>("oculto");
  const [resultado, setResultado] = useState<ResultadoTraspaso | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let vivo = true;
    const pendiente = invitadoPendienteDeTraspaso(user?.user_id ?? null);
    if (!pendiente) {
      setFase("oculto");
      return;
    }
    // El inventario se lee del cliente porque la cuenta nueva NO puede listar el
    // trabajo del invitado: el aislamiento entre cuentas lo impide, y así debe
    // ser. Quien sabe qué hay en este equipo es este equipo.
    (async () => {
      try {
        const repo = crearRepositorioDeCasos(pendiente.user_id);
        const inv = await inventarioDelInvitado(repo);
        if (!vivo) return;
        if (inv.casos.length === 0) {
          // Nada que ofrecer: no se molesta al investigador con un aviso vacío.
          olvidarInvitado();
          setFase("oculto");
          return;
        }
        setInvitado(pendiente);
        setInventario(inv);
        setFase("ofreciendo");
      } catch {
        // Si no se puede leer el inventario, no se inventa uno. El trabajo sigue
        // siendo del invitado y el ofrecimiento se reintenta en otra sesión.
        if (vivo) setFase("oculto");
      }
    })();
    return () => {
      vivo = false;
    };
  }, [user?.user_id]);

  const aceptar = useCallback(async () => {
    if (!invitado || !inventario || !user?.user_id) return;
    setFase("moviendo");
    setError(null);
    try {
      const repoInvitado = crearRepositorioDeCasos(invitado.user_id);
      const repoDestino = crearRepositorioDeCasos(user.user_id);
      const res = await ejecutarTraspaso({
        destinoUserId: user.user_id,
        repoInvitado,
        repoDestino,
        moleculeIds: inventario.moleculeIds,
        llamarBackend: (payload) =>
          traspasarDelInvitado(payload.molecule_ids, payload.cohort_ids),
      });
      setResultado(res);
      setFase("hecho");
    } catch (e) {
      // El backend es transaccional: si falló, no se movió nada, y los casos
      // siguen siendo del invitado. Reintentar es seguro.
      setError(e instanceof Error ? e.message : String(e));
      setFase("error");
    }
  }, [invitado, inventario, user?.user_id]);

  const descartar = useCallback(() => {
    olvidarInvitado();
    setFase("oculto");
  }, []);

  if (fase === "oculto" || !inventario) return null;

  const conResultado = inventario.casos.length - inventario.casosSinResultado;

  return (
    <div
      role="region"
      aria-label={t("pn_traspaso_titulo")}
      className="mx-auto my-4 max-w-4xl rounded-xl border border-brand-500/40 bg-brand-500/5 px-5 py-4"
    >
      {fase === "hecho" && resultado ? (
        <div className="text-sm text-surface-200">
          <p className="font-semibold">Trabajo traspasado a tu cuenta.</p>
          <p className="mt-1 text-surface-400">
            {resultado.moleculasTraspasadas} {t("auto_384a1af1c5dc")}
            {resultado.moleculasTraspasadas === 1 ? "" : "s"} y {resultado.casosMovidos} caso
            {resultado.casosMovidos === 1 ? "" : "s"}.
            {resultado.casosNoMovidos.length > 0 && (
              <>
                {" "}
                <span className="text-yellow-400">
                  {resultado.casosNoMovidos.length} caso
                  {resultado.casosNoMovidos.length === 1 ? "" : "s"} {t("auto_b2869e46ca45")}
                </span>
              </>
            )}
          </p>
        </div>
      ) : (
        <>
          <p className="text-sm font-semibold text-surface-100">
            {t("pn_traspaso_tienes")}
          </p>
          <p className="mt-1 text-sm text-surface-400">
            {inventario.casos.length} caso{inventario.casos.length === 1 ? "" : "s"}
            {conResultado > 0
              ? `, ${conResultado} con resultado guardado`
              : t("auto_8ff2cb920103")}
            {t("auto_ea64cf436cb0")}
          </p>
          {inventario.casos.length > 0 && (
            <ul className="mt-2 space-y-0.5 text-xs text-surface-500">
              {inventario.casos.slice(0, 5).map((c) => (
                <li key={c.id}>· {c.name}</li>
              ))}
              {inventario.casos.length > 5 && (
                <li>· y {inventario.casos.length - 5} {t("auto_917ac7093911")}</li>
              )}
            </ul>
          )}
          {fase === "error" && error && (
            <p className="mt-2 rounded-lg border border-red-900/50 bg-red-950/30 px-3 py-2 text-xs text-red-300">
              {t("auto_f56cc2a1ae4e")} {error}{t("auto_3cbb86a7ea90")}
            </p>
          )}
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <button
              onClick={aceptar}
              disabled={fase === "moviendo"}
              className="rounded-lg bg-brand-600 px-3 py-1.5 text-xs font-semibold text-white transition-colors hover:bg-brand-500 disabled:opacity-50"
            >
              {fase === "moviendo" ? t("auto_fa66f6444d99") : "Llevarlo a mi cuenta"}
            </button>
            <button
              onClick={descartar}
              disabled={fase === "moviendo"}
              className="rounded-lg border border-surface-700 px-3 py-1.5 text-xs text-surface-300 transition-colors hover:bg-surface-800 disabled:opacity-50"
            >
              {t("pn_traspaso_ahora_no")}
            </button>
            <span className="text-xs text-surface-600">
              {t("pn_traspaso_sin_batch")}
            </span>
          </div>
        </>
      )}
    </div>
  );
}
