> **Documento histórico — julio de 2026.** Escrito para el árbol anterior del
> proyecto (`moldesign-app`) y traído aquí por trazabilidad. Puede describir un
> estado que ya no es el vigente: la versión 1.0.0 es una aplicación de
> escritorio y no tiene componente en la nube. No se ha reescrito su contenido.

# Libreria de Targets Offline — v1.5

> **386 targets en 20 areas terapeuticas, 273 validados, listos para docking sin conexion a internet.**

---

## Arquitectura

```
data/target_library/
  01_gpcr/            (5 PDBs)
  02_kinase/          (5 PDBs)
  ...
  20_aging_senescence/ (18 PDBs)
  targets_manifest.json

~/MolDesign/data/
  moldesign_local.db   (386 targets registrados)
  targets/{PDB_ID}/
    raw.pdb
    prepared.pdbqt
```

Los PDBs se descargan via RCSB y se organizan por area. La DB SQLite registra cada target con grid center, size, familia estructural y estado de preparacion.

---

## 20 Areas Terapeuticas

| # | Area | Targets | Ejemplos |
|---|------|:-------:|----------|
| 1 | GPCR | 20 | 5-HT1A, mu-Opioid, CB1, CCR5, GLP-1R |
| 2 | Kinase | 20 | CDK2, EGFR, BRAF, JAK2, PI3K |
| 3 | Protease | 20 | HIV-1, HCV NS3, BACE1, DPP-4, Furin |
| 4 | Nuclear Receptor | 20 | ER-alpha, AR, PPAR-gamma, FXR, VDR |
| 5 | Ion Channel | 20 | hERG, NaV1.5, GABA-A, CFTR, CaV |
| 6 | Phosphodiesterase | 20 | PDE3A, PDE4B, PDE5A, PDE10 |
| 7 | Epigenetica | 16 | HDAC2, Sirtuins, DNMT, BRD4, EZH2 |
| 8 | Inmuno-Oncologia | 14 | PD-L1, STING, TLR, IDO1, A2AR |
| 9 | Transportadores | 17 | SERT, SGLT2, P-gp, SLC |
| 10 | Metabolismo | 14 | PPAR, FXR, AMPK, GLP-1R, FASN |
| 11 | Ubiquitina-Proteasoma | 18 | Proteasome, E3 ligases, DUBs |
| 12 | Antibacterianos | 18 | DNA Gyrase, PBP, RNAP, Beta-Lactamase |
| 13 | Antivirales | 19 | HIV, HCV, SARS-CoV-2, Influenza |
| 14 | Enfermedades Raras | 18 | CFTR, Huntingtin, SOD1, SMN |
| 15 | Neurodegeneracion | 17 | Tau, LRRK2, Alpha-Synuclein, TREM2 |
| 16 | Inflamacion / Dolor | 18 | COX-2, NLRP3, P2X, p38 MAPK |
| 17 | Fibrosis | 19 | TGF-betaR, Integrin, Galectin-3, LOX |
| 18 | Cardiovascular | 15 | ACE, Factor XIa, Cardiac Myosin, Renin |
| 19 | Endocrinologia | 17 | TSH-R, IGF-1R, Aromatase, GHRH |
| 20 | Senescencia / Aging | 18 | Telomerase, SIRT6, FOXO, PARP |

---

## Niveles de Calidad

| Nivel | Cantidad | Grid | UI |
|-------|:-------:|------|----|
| ⭐ Validado | 273 | Curado + ligando co-cristalizado | `is_hot=True`, estrella dorada |
| 🟡 Centroide | 113 | Centro geometrico + grid 30A | Sin marca, tooltip "Grid aproximado" |

---

## Pipeline de Ingestion

Cuando un usuario selecciona un target nuevo (via RCSB search o PDB ID directo):

1. `download_pdb_from_rcsb()` — descarga del RCSB o cache local
2. `discover_pocket_from_pdb()` — detecta el bolsillo de binding
3. `prepare_target()` — PDBFixer + Meeko → PDBQT
4. `TargetORM` — registra en DB con grid center/size

El PDBQT se cachea en `~/MolDesign/data/targets/{PDB_ID}/prepared.pdbqt` para reuso.

---

## Scripts

| Script | Proposito |
|--------|-----------|
| `scripts/curate_target_library.py` | Descargar PDBs del RCSB organizados por area |
| `scripts/seed_target_library.py` | Registrar todos los PDBs en la DB con grid detection |
| `scripts/seed_curated_targets.py` | Registrar los 80 targets de curated_targets.csv |
| `scripts/seed_all_targets.py` | Registrar los 19 targets principales |
| `scripts/validate_targets_fast.py` | Smoke test: preparar receptor PDBQT para todos |
| `scripts/validate_targets.py` | Validacion completa: redocking + RMSD |
| `scripts/discover_new_targets.py` | Estimar targets disponibles en RCSB sin descargar |
| `scripts/discover_remaining_areas.py` | Buscar targets en areas terapeuticas nuevas |

---

## Para el build de Steam

1. Incluir `data/target_library/` en el instalador (~60 MB)
2. Incluir `data/targets/*.pdb` (94 PDBs pre-descargados)
3. Ejecutar `seed_all_targets.py` + `seed_curated_targets.py` + `seed_target_library.py` en primer arranque
4. Ejecutar `validate_targets_fast.py` para preparar receptores PDBQT

Resultado: 386 targets listos para docking, cero dependencia de internet.
