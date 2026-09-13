"use client";

// =====================================================================
// /evaluation — anfitrión del espacio de trabajo de CASOS
// =====================================================================
//
// QUE CAMBIO Y QUE NO. Esta pagina contenia todo el estado de una evaluacion
// suelta —SMILES, target, taskId, polling— y lo pasaba a `ProEvaluation`. Ese
// cuerpo se movio TAL CUAL a `components/evaluation/CaseEvaluationRunner.tsx`.
// No se reescribio `ProEvaluation`, no cambio ningun endpoint y el pipeline no
// se toco. Lo unico nuevo aqui es que la evaluacion ahora vive DENTRO de un
// caso: la unidad del producto dejo de ser una evaluacion suelta (docs/53 §5).
//
// POR QUE EL PROVEEDOR VIVE AQUI Y NO MAS ARRIBA. `PersistentKeepAliveLayout`
// monta esta pagina una sola vez y nunca la desmonta: solo alterna
// `display`. Poniendo `CaseProvider` aqui dentro, el caso activo y el estado de
// la corrida sobreviven a navegar a /moldex, /history o /comunidad y volver,
// sin tocar el layout ni ampliar el alcance del keep-alive.

import { CaseProvider } from "../../context/CaseContext";
import { CaseWorkspace } from "../../components/cases/CaseWorkspace";
import { useAuth } from "../../lib/auth";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

export default function EvaluationPage() {
  const { isLoading, user } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading && !user) {
      router.replace("/login?returnTo=%2Fevaluation");
    }
  }, [isLoading, router, user]);

  if (isLoading || !user) {
    return (
      <div className="flex min-h-[50vh] items-center justify-center text-sm text-muted-foreground">
        Cargando sesión…
      </div>
    );
  }

  return (
    <CaseProvider key={user.user_id} ownerUserId={user.user_id}>
      {/* SIN altura aquí: el único propietario es `CaseWorkspace`, que resta la
          navegación global. Dos wrappers fijando altura discrepaban y el
          workspace se salía por debajo del viewport. */}
      <CaseWorkspace />
    </CaseProvider>
  );
}
