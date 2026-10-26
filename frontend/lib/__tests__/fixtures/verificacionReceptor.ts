import type { VerificacionReceptor } from "../../seccionCatalogo";

/** Entrada ficticia: sólo se inyecta en componentes y pruebas, nunca en el registro. */
export const verificacionDePrueba: VerificacionReceptor = {
  receta_receptor: 7,
  receptor_sha256: "a".repeat(64),
  protocolo: { exhaustiveness: 8, num_poses: 9, semilla: 42 },
  condiciones: ["RECEPTOR_SIN_IONES", "SERIE_CONGENERICA", "CONDICIONES_DEL_ENSAYO_NO_DOCUMENTADAS"],
  pose: { semillas: 5, semillas_rmsd_ok: 4, rmsd_top1_A: [1.1, 1.4, 0.9, 2.6, 1.2], posebusters_valida: true, protocolo_h: "MF-33-H-COR" },
  calibracion: { metrica: "spearman", rho: 0.41, ic95: [0.17, 0.61], n: 57, endpoint: "Ki", panel: "CHEMBL853189", fallos: 0, artefacto: "fixture" },
  fecha: "2026-10-09",
};
