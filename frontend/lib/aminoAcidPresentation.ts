import type { Translate } from "./frontendError";
const AA_INFO: Readonly<Record<string, { name: string; type: string; typeColor: string; desc: string; typeCode: string; nameKey: string; typeKey: string }>> = {
  "ALA": {
    "name": "Alanina",
    "type": "Hidrofóbico",
    "typeColor": "#fbbf24",
    "desc": "Residuo pequeño, contribuye al empaquetamiento hidrofóbico del bolsillo.",
    "typeCode": "hydrophobic",
    "nameKey": "pr_aa_ALA",
    "typeKey": "pr_aa_type_hydrophobic"
  },
  "VAL": {
    "name": "Valina",
    "type": "Hidrofóbico",
    "typeColor": "#fbbf24",
    "desc": "Cadena lateral ramificada; contactos de van der Waals con ligandos lipofílicos.",
    "typeCode": "hydrophobic",
    "nameKey": "pr_aa_VAL",
    "typeKey": "pr_aa_type_hydrophobic"
  },
  "LEU": {
    "name": "Leucina",
    "type": "Hidrofóbico",
    "typeColor": "#fbbf24",
    "desc": "Contacto hidrofóbico frecuente en bolsillos de unión.",
    "typeCode": "hydrophobic",
    "nameKey": "pr_aa_LEU",
    "typeKey": "pr_aa_type_hydrophobic"
  },
  "ILE": {
    "name": "Isoleucina",
    "type": "Hidrofóbico",
    "typeColor": "#fbbf24",
    "desc": "Hidrofóbico; define la forma del bolsillo.",
    "typeCode": "hydrophobic",
    "nameKey": "pr_aa_ILE",
    "typeKey": "pr_aa_type_hydrophobic"
  },
  "MET": {
    "name": "Metionina",
    "type": "Hidrofóbico",
    "typeColor": "#fbbf24",
    "desc": "Azufre en la cadena lateral; puede hacer contactos S-π o S-H.",
    "typeCode": "hydrophobic",
    "nameKey": "pr_aa_MET",
    "typeKey": "pr_aa_type_hydrophobic"
  },
  "PHE": {
    "name": "Fenilalanina",
    "type": "Aromático",
    "typeColor": "#a78bfa",
    "desc": "Anillo aromático; interacciones π-stacking con ligandos aromáticos.",
    "typeCode": "aromatic",
    "nameKey": "pr_aa_PHE",
    "typeKey": "pr_aa_type_aromatic"
  },
  "TRP": {
    "name": "Triptófano",
    "type": "Aromático",
    "typeColor": "#a78bfa",
    "desc": "Indol; π-stacking, cation-π y contactos hidrofóbicos fuertes.",
    "typeCode": "aromatic",
    "nameKey": "pr_aa_TRP",
    "typeKey": "pr_aa_type_aromatic"
  },
  "TYR": {
    "name": "Tirosina",
    "type": "Aromático",
    "typeColor": "#a78bfa",
    "desc": "Fenol; π-stacking + H-bond donor/acceptor por el OH.",
    "typeCode": "aromatic",
    "nameKey": "pr_aa_TYR",
    "typeKey": "pr_aa_type_aromatic"
  },
  "HIS": {
    "name": "Histidina",
    "type": "Aromático y polar",
    "typeColor": "#a78bfa",
    "desc": "Imidazol; coordina metales, pH-dependiente, H-bonds.",
    "typeCode": "aromatic_polar",
    "nameKey": "pr_aa_HIS",
    "typeKey": "pr_aa_type_aromatic_polar"
  },
  "SER": {
    "name": "Serina",
    "type": "Polar",
    "typeColor": "#60a5fa",
    "desc": "OH reactivo; H-bonds, a veces nucleófilo catalítico.",
    "typeCode": "polar",
    "nameKey": "pr_aa_SER",
    "typeKey": "pr_aa_type_polar"
  },
  "THR": {
    "name": "Treonina",
    "type": "Polar",
    "typeColor": "#60a5fa",
    "desc": "OH; H-bonds, geometría restringida por el metilo.",
    "typeCode": "polar",
    "nameKey": "pr_aa_THR",
    "typeKey": "pr_aa_type_polar"
  },
  "ASN": {
    "name": "Asparagina",
    "type": "Polar",
    "typeColor": "#60a5fa",
    "desc": "Amida; donor y acceptor de H-bonds.",
    "typeCode": "polar",
    "nameKey": "pr_aa_ASN",
    "typeKey": "pr_aa_type_polar"
  },
  "GLN": {
    "name": "Glutamina",
    "type": "Polar",
    "typeColor": "#60a5fa",
    "desc": "Amida más larga; donor y acceptor de H-bonds.",
    "typeCode": "polar",
    "nameKey": "pr_aa_GLN",
    "typeKey": "pr_aa_type_polar"
  },
  "ASP": {
    "name": "Aspartato",
    "type": "Ácido",
    "typeColor": "#f87171",
    "desc": "Carboxilato (−); iónico/sal bridge, acceptor fuerte de H-bond.",
    "typeCode": "acidic",
    "nameKey": "pr_aa_ASP",
    "typeKey": "pr_aa_type_acidic"
  },
  "GLU": {
    "name": "Glutamato",
    "type": "Ácido",
    "typeColor": "#f87171",
    "desc": "Carboxilato (−); sal bridge, reconocimiento de cationes.",
    "typeCode": "acidic",
    "nameKey": "pr_aa_GLU",
    "typeKey": "pr_aa_type_acidic"
  },
  "LYS": {
    "name": "Lisina",
    "type": "Básico",
    "typeColor": "#4ade80",
    "desc": "Amino (+); sal bridge con ligandos ácidos, cation-π.",
    "typeCode": "basic",
    "nameKey": "pr_aa_LYS",
    "typeKey": "pr_aa_type_basic"
  },
  "ARG": {
    "name": "Arginina",
    "type": "Básico",
    "typeColor": "#4ade80",
    "desc": "Guanidinio (+); sal bridge fuerte, reconocimiento de fosfatos.",
    "typeCode": "basic",
    "nameKey": "pr_aa_ARG",
    "typeKey": "pr_aa_type_basic"
  },
  "CYS": {
    "name": "Cisteína",
    "type": "Polar y reactivo",
    "typeColor": "#60a5fa",
    "desc": "Tiol; puede formar enlaces covalentes con warheads electrofílicos.",
    "typeCode": "polar_reactive",
    "nameKey": "pr_aa_CYS",
    "typeKey": "pr_aa_type_polar_reactive"
  },
  "PRO": {
    "name": "Prolina",
    "type": "Estructural",
    "typeColor": "#94a3b8",
    "desc": "Rígida; define giros, contribuye a la forma del sitio.",
    "typeCode": "structural",
    "nameKey": "pr_aa_PRO",
    "typeKey": "pr_aa_type_structural"
  },
  "GLY": {
    "name": "Glicina",
    "type": "Estructural",
    "typeColor": "#94a3b8",
    "desc": "Sin cadena lateral; permite espacios estrechos en el bolsillo.",
    "typeCode": "structural",
    "nameKey": "pr_aa_GLY",
    "typeKey": "pr_aa_type_structural"
  }
};
export function formatResidueLabel(name: string, t: Translate): string {
  const [chain, residue] = name.trim().toUpperCase().split(":");
  return residue ? t("pr_residue_chain", { residue, chain }) : chain;
}
export function aaInfoFromName(name: string, t?: Translate) {
  const clean = name.toUpperCase().split(":").pop() ?? "";
  const code = clean.replace(/\d+/g, "").slice(0, 3);
  const info = AA_INFO[code];
  if (!info) return { code, name: code, type: t?.("pr_aa_type_residue") ?? "Residuo", typeColor: "#94a3b8", typeCode: "residue", desc: t?.("Residuo del sitio activo.") ?? "Residuo del sitio activo." };
  return { ...info, code, name: t ? t(info.nameKey) : info.name, type: t ? t(info.typeKey) : info.type, desc: t ? t(info.desc) : info.desc };
}
