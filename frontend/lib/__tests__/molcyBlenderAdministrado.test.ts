import { describe, expect, it } from "vitest";
import { molcy } from "@/context/traducciones/molcy";

/**
 * El Blender administrado se instala en la carpeta de DATOS del usuario, sin elevación (2026-10-04): la carpeta del programa
 * es de sólo lectura en la build de la Microsoft Store. Los textos no pueden seguir prometiendo una solicitud de Windows
 * que ya no existe, ni hablar de una «carpeta de instalación» que MolDesign ya no necesita que Rust le comunique.
 */
describe("Molcy: textos del Blender administrado", () => {
  // Desde el 2026-10-12 la descarga la explica la tarjeta del paquete (en Descargas y en el estudio de Molcy), no la
  // configuración: `cy_blender_reason` desapareció con su botón. La regla es la misma para los textos que la sustituyen.
  it.each(["es", "en"] as const)("(%s) no promete permisos de Windows y dice dónde se instala", (idioma) => {
    for (const clave of ["cy_pack_description", "cy_pack_studio_where"]) {
      const texto = molcy[idioma][clave];
      expect(texto).not.toMatch(/Windows/);
      expect(texto).toMatch(idioma === "es" ? /carpeta de datos de MolDesign/ : /MolDesign data folder/);
      expect(texto).toMatch(idioma === "es" ? /sin permisos de administrador/ : /without administrator permissions/);
    }
  });

  it.each(["es", "en"] as const)("(%s) las claves de la elevación y de la carpeta de instalación ya no existen", (idioma) => {
    expect(molcy[idioma]).not.toHaveProperty("cy_install_permissions");
    expect(molcy[idioma]).not.toHaveProperty("cy_install_path_missing");
  });
});
