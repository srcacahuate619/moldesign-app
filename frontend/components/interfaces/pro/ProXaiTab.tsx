"use client";

import React from "react";
import { ContactMapPanel } from "./ContactMapPanel";

/**
 * «Explicabilidad»: lo que el 3D no alcanza a explicar de la interacción
 * proteína-ligando. Hoy es el mapa de contactos de la pose, que sale de la
 * geometría del complejo y no depende de ningún modelo. Lo que cada modelo
 * devolvió —SHAP incluido— vive en «Modelos» (`ProModelsTab`).
 */
interface Props {
  moleculeId?: string | null;
  taskId?: string | null;
  poses?: readonly {rank:number}[] | null;
}

export function ProXaiTab({ moleculeId, taskId, poses }: Props) {
  return <ContactMapPanel key={`${moleculeId??""}:${taskId??""}`} moleculeId={moleculeId} taskId={taskId} poses={poses}/>;
}
