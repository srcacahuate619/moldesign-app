# Panel de anti-dianas de Bowes et al. 2012

**Generado por `scripts/build_bowes44_panel.py --write`. No editar a mano.**

Referencia: Bowes et al. 2012, Nat Rev Drug Discov 11:909-922, tabla 1.

## Qué mide cada fila, y qué no

- **Sitio**: distancia entre el centroide de la primera pose de redocking y
  el del ligando cristalizado. Es el criterio de admisión (≤ 4.0 Å) y
  valida la **estructura**: dice que la caja describe la cavidad de ese ligando.
- **Pose**: RMSD simétrico de esa pose. Mide a **Vina**, no a la estructura, y
  **no decide**. Un ligando alargado puede quedar girado en la misma cavidad:
  ambrisentán en ETA da 3,2 Å de centroide con 4,2 Å de RMSD.
- Ninguna de las dos dice que el sitio sea el **relevante para la reacción
  adversa**. Eso lo adjudica una persona, y por eso todas las filas salen con
  `sitio_adjudicado: false`.
- El ligando de cada fila es un fármaco o un agonista endógeno, nunca un
  cofactor, lípido, detergente o tampón: cuatro filas lo fueron y el redocking
  «confirmaba» el bolsillo equivocado.

## Estado

| Estado | Dianas |
|---|---:|
| ofrecible (`validada`) | 38 |
| ya en el panel por defecto (`en_el_panel_por_defecto`) | 2 |
| sin estructura humana (`sin_estructura`) | 2 |
| sin sitio confirmado (`sin_estructura_preparable`) | 2 |
| **total** | **44** |

## Las 44

| Ensayo | Gen | Familia | Estado | PDB | Ligando | Sitio (Å) | Pose (Å) | Pose ≤2 Å |
|---|---|---|---|---|---|---:|---:|:-:|
| A2A | ADORA2A | GPCR | ofrecible | 5NM4 | ZMA | 2.58 | 9.15 | no |
| alpha1A | ADRA1A | GPCR | ofrecible | 8THK | CGZ | 0.43 | 2.74 | no |
| alpha2A | ADRA2A | GPCR | ofrecible | 6KUX | E3F | 0.32 | 1.34 | sí |
| beta1 | ADRB1 | GPCR | ofrecible | 7BVQ | CAU | 0.29 | 0.55 | sí |
| beta2 | ADRB2 | GPCR | ofrecible | 2RH1 | CAU | 0.39 | 0.96 | sí |
| CB1 | CNR1 | GPCR | ofrecible | 5U09 | 7DY | 1.35 | 4.24 | no |
| CB2 | CNR2 | GPCR | ofrecible | 5ZTY | 9JU | 0.24 | 0.82 | sí |
| CCK1 (CCKA) | CCKAR | GPCR | ofrecible | 7F8Y | 1OZ | 0.09 | 1.19 | sí |
| D1 | DRD1 | GPCR | ofrecible | 9LLJ | LDP | 0.33 | 2.01 | no |
| D2S | DRD2 | GPCR | ofrecible | 9BS9 | 7LD | 0.17 | 0.71 | sí |
| ETA | EDNRA | GPCR | ofrecible | 8XVK | A1D5J | 3.16 | 4.22 | no |
| H1 | HRH1 | GPCR | ofrecible | 8X5Y | XB7 | 0.74 | 2.06 | no |
| H2 | HRH2 | GPCR | ofrecible | 8YUT | A1D67 | 0.20 | 0.36 | sí |
| M1 | CHRM1 | GPCR | ofrecible | 6ZFZ | QJT | 0.58 | 1.35 | sí |
| M2 | CHRM2 | GPCR | ofrecible | 5ZKC | 3C0 | 0.14 | 0.38 | sí |
| M3 | CHRM3 | GPCR | ofrecible | 8EA0 | IXO | 0.22 | 0.81 | sí |
| delta2 (DOP) | OPRD1 | GPCR | ofrecible | 4N6H | EJ4 | 0.19 | 0.29 | sí |
| kappa (KOP) | OPRK1 | GPCR | ofrecible | 7UL2 | Q6Q | 0.33 | 0.82 | sí |
| mu (MOP) | OPRM1 | GPCR | ofrecible | 8Y72 | VV9 | 1.65 | 5.89 | no |
| 5-HT1A | HTR1A | GPCR | ofrecible | 8PJK | ZL9 | 1.12 | 10.99 | no |
| 5-HT1B | HTR1B | GPCR | ofrecible | 4IAR | ERM | 0.92 | 3.93 | no |
| 5-HT2A | HTR2A | GPCR | ofrecible | 7WC8 | 92S | 1.10 | 2.17 | no |
| 5-HT2B | HTR2B | GPCR | ya en el panel por defecto | 4NC3 (medida: 4IB4) | ERM | 0.12 | 1.05 | sí |
| V1a | AVPR1A | GPCR | ofrecible | 9UWL | A1EQN | 0.82 | 6.69 | no |
| dopamine transporter | SLC6A3 | Transportador | ofrecible | 9EO4 | COC | 0.16 | 0.89 | sí |
| norepinephrine transporter | SLC6A2 | Transportador | ofrecible | 8ZP2 | A1LX4 | 0.47 | 1.03 | sí |
| 5-HT transporter | SLC6A4 | Transportador | ofrecible | 9HCO | YG7 | 0.61 | 1.90 | sí |
| N neuronal alpha4beta2 | CHRNA4 | Canal iónico | sin estructura humana | — | — | — | — |  |
| 5-HT3 | HTR3A | Canal iónico | ofrecible | 8BLA | VTX | 0.67 | 1.77 | sí |
| hERG | KCNH2 | Canal iónico | ya en el panel por defecto | 5VA1 (medida: 8ZYQ) | 1II | 0.70 | 1.70 | sí |
| KV channel | — | Canal iónico | sin estructura humana | — | — | — | — |  |
| Na+ channel (site 2) | SCN5A | Canal iónico | ofrecible | 6LQA | QDN | 2.35 | 5.72 | no |
| AR | AR | Receptor nuclear | ofrecible | 8E1A | 3E0 | 0.30 | 2.24 | no |
| COX2 | PTGS2 | Enzima | ofrecible | 5IKR | ID8 | 0.45 | 1.93 | sí |
| acetylcholinesterase | ACHE | Enzima | ofrecible | 4M0E | 1YL | 0.16 | 0.24 | sí |
| PDE3A | PDE3A | Enzima | ofrecible | 7KWE | X5M | 1.19 | 2.70 | no |
| PDE4D2 | PDE4D | Enzima | ofrecible | 1Y2K | 7DE | 1.26 | 7.18 | no |
| BZD (central) | GABRA1 | Canal iónico | ofrecible | 9EQG | A1H6W | 0.45 | 2.33 | no |
| NMDA | GRIN1 | Canal iónico | ofrecible | 9GJ1 | A1IME | 0.23 | 0.43 | sí |
| Ca2+ channel (L, dihydropyridine site) | CACNA1C | Canal iónico | ofrecible | 8WE8 | 6UB | 1.19 | 2.40 | no |
| GR | NR3C1 | Receptor nuclear | ofrecible | 4UDD | CV7 | 0.45 | 0.60 | sí |
| Lck kinase | LCK | Quinasa | ofrecible | 4C3F | 7KW | 3.07 | 5.97 | no |
| COX1 | PTGS1 | Enzima | sin sitio confirmado | — | — | — | — |  |
| MAO-A | MAOA | Enzima | sin sitio confirmado | — | — | — | — |  |

## Las que no entran, y por qué

- **N neuronal alpha4beta2** (CHRNA4): sin estructura X-RAY DIFFRACTION/ELECTRON MICROSCOPY ≤3.5 Å con ligando drug-like. Las estructuras de α4β2 son crio-EM por encima de 3,5 Å, el tope del filtro. Subir el tope es una decisión que hay que medir, no asumir.
- **KV channel** (—): la ficha no identifica el subtipo; hay que fijarlo a mano. La tabla 1 de Bowes dice «KV channel» sin subtipo, y KCNQ1, KCNA5 o KCNH2 no comparten sitio. Fijar el subtipo es una decisión de quien use el panel.
- **COX1** (PTGS1): Ninguna estructura pasó: su único ligando no es un fármaco (cofactor, lípido, detergente, tampón o análogo de nucleótido). El criterio es el centroide de la primera pose a ≤ 4.0 Å del ligando cristalizado. La única entrada humana del PDB con ligando bajo los filtros es 6Y3C (3,36 Å) y su único HETATM es citrato: la COX-1 cristalizada con inhibidor es casi siempre ovina, y sustituir de especie cambia el sitio. Queda abierto: fijar a mano una estructura y adjudicar el sitio.
- **MAO-A** (MAOA): Ninguna estructura pasó: su único ligando no es un fármaco (cofactor, lípido, detergente, tampón o análogo de nucleótido); Meeko no pudo preparar el receptor. El criterio es el centroide de la primera pose a ≤ 4.0 Å del ligando cristalizado. En las cuatro entradas (2Z5Y, 2Z5X, 2BXR, 2BXS) Meeko avisa «matched with excess inter-residue bond(s)» sobre el residuo del FAD y aborta con «adjacent_mol doesn't contain the mapped atoms». El enlace de más es el que une el FAD covalentemente a una cisteína del sitio activo, propio de las monoamino-oxidasas. No es la caja: el producto no prepara cofactores covalentes. Queda declarado, no sorteado.
