// =====================================================================
// Etiquetas ADMET: los códigos del backend, dichos en español
// =====================================================================
//
// EL FALLO QUE ARREGLA. `blood_ppb_category` vale `"extreme" | "high" | "low"`
// —son códigos, no texto para leer— y la interfaz los imprimía tal cual. En una
// pantalla íntegramente en español aparecía «PPB: high», y la ayuda contextual
// llegaba a explicarlo diciendo «Si es 'High' (Alta)…»: la propia ayuda estaba
// traduciendo el código a mano porque la celda no lo hacía.
//
// El código sigue viajando en el resultado y en el dossier; sólo cambia lo que
// se enseña. La traducción vive aquí, en un sitio, para que las dos pantallas
// que muestran PPB —`PropertiesPanel` y `ProParametersTab`— no puedan
// discrepar, que es como empezó esto.

/** Categoría de unión a proteínas plasmáticas, legible. */
export function etiquetaPPB(codigo: string | null | undefined): string | null {
  if (codigo == null) return null;
  switch (codigo.toLowerCase()) {
    case "extreme":
      return "Extrema (>99 %)";
    case "high":
      return "Alta (>90 %)";
    case "medium":
      return "Media";
    case "low":
      return "Baja (≤90 %)";
    default:
      // Un código nuevo se enseña crudo antes que desaparecer: preferimos que
      // se vea algo raro a que la fila se quede en blanco sin explicación.
      return codigo;
  }
}
