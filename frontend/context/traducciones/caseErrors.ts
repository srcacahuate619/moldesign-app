import type { ModuloDeTraduccion } from "./index";

/** Diagnósticos producidos localmente al gestionar casos; no traduce errores externos. */
export const caseErrors: ModuloDeTraduccion = {
  es: {
    ca_diag_no_storage: "No hay almacenamiento local disponible en este entorno.",
    ca_diag_open_folder_browser: "Abrir una carpeta del disco requiere la aplicación de escritorio. En el navegador los casos se guardan localmente en este equipo.",
    ca_diag_generated_name: "Caso {id}",
    ca_diag_case_not_found: "No existe un caso con id {id} en este navegador.",
    ca_diag_foreign_case: "Este caso pertenece a otra cuenta.",
    ca_diag_foreign_save: "No se puede guardar un caso de otra cuenta.",
    ca_diag_legacy_owner: "Este caso legacy todavía no está asignado a tu cuenta.",
    ca_diag_choose_folder: "Elige una carpeta donde crear el caso.",
    ca_diag_save_unstable: "El caso no dejó de cambiar mientras se guardaba.",
    ca_diag_no_backup: "Este almacenamiento no guarda copias de seguridad, así que no hay nada que restaurar.",
    ca_diag_relocate_desktop: "Relocalizar una carpeta requiere la aplicación de escritorio.",
    ca_diag_no_initialize: "Este entorno no puede inicializar carpetas.",
  },
  en: {
    ca_diag_no_storage: "Local storage is not available in this environment.",
    ca_diag_open_folder_browser: "Opening a folder on disk requires the desktop application. In the browser, cases are stored locally on this computer.",
    ca_diag_generated_name: "Case {id}",
    ca_diag_case_not_found: "There is no case with id {id} in this browser.",
    ca_diag_foreign_case: "This case belongs to another account.",
    ca_diag_foreign_save: "A case belonging to another account cannot be saved.",
    ca_diag_legacy_owner: "This legacy case has not yet been assigned to your account.",
    ca_diag_choose_folder: "Choose a folder where the case will be created.",
    ca_diag_save_unstable: "The case kept changing while it was being saved.",
    ca_diag_no_backup: "This storage does not keep backups, so there is nothing to restore.",
    ca_diag_relocate_desktop: "Relocating a folder requires the desktop application.",
    ca_diag_no_initialize: "This environment cannot initialize folders.",
  },
};
