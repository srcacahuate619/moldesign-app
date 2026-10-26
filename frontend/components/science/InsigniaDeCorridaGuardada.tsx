"use client";

import { useEffect, useState } from "react";
import { useCatalogoDeReceptores } from "@/hooks/useCatalogoDeReceptores";
import { getEvaluationResult } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { receptorPorPdbId, seccionDelReceptor } from "@/lib/seccionCatalogo";
import type { EvaluationResult } from "@/lib/types";
import { InsigniaDelCatalogo } from "./InsigniaDelCatalogo";

/** Las vistas con sólo IDs consultan el snapshot exacto si hay un sello que comparar. */
export function InsigniaDeCorridaGuardada({ pdbId, moleculeId, taskId }: {
  pdbId?: string | null;
  moleculeId?: string | null;
  taskId?: string | null;
}) {
  const { user } = useAuth();
  const userId = user?.user_id;
  const catalogo = useCatalogoDeReceptores(Boolean(pdbId));
  const verificado = seccionDelReceptor(receptorPorPdbId(pdbId, catalogo)) === "verificado";
  const [recibido, setRecibido] = useState<{ userId?: string; moleculeId: string; taskId: string; result: EvaluationResult } | null>(null);
  const corrida = recibido?.userId === userId && recibido?.moleculeId === moleculeId && recibido?.taskId === taskId ? recibido?.result : undefined;
  useEffect(() => {
    if (!verificado || !moleculeId || !taskId) return;
    let vigente = true;
    getEvaluationResult(moleculeId, taskId).then(result => {
      if (vigente) setRecibido({ userId, moleculeId, taskId, result });
    }, () => { /* Sin snapshot no se puede comprobar el sello; nunca consultar la proyección actual. */ });
    return () => { vigente = false; };
  }, [verificado, moleculeId, taskId, userId]);
  return <InsigniaDelCatalogo pdbId={pdbId} corrida={corrida ?? {}} />;
}
