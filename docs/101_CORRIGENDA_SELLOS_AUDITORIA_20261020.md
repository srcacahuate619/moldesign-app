# Corrigenda de los experimentos sellados — auditoría científica, Fase B (2026-10-20)

**Fuente:** Fase B de la auditoría científica anclada en `bef67706`
(`D:\moldesign-audits\AUDIT_ciencia_bef67706\revision_integral\ENTREGA_AUDITOR\`,
`LEDGER_VIGENTE.json`). Revisó los 171 sellos presentes en ese commit.

**Qué es este documento.** La lista de conclusiones que **dejan de valer** en los
registros C0 de la Fase B: los que se arreglan redactando, sin cómputo. Los artefactos
sellados de `scripts/artifacts_science/` **no se editan** (restricción 5 de
`AGENTS.md`): sus `LECTURA.md`, `README.md` y manifiestos conservan el texto original, y
esta corrigenda es la que manda al citarlos. Donde el experimento tiene paper en
`docs/papers/`, el paper lleva además una sección «Correcciones» fechada que remite aquí.

**Qué no es.** Ninguna cifra medida cambia y no se repitió ningún cálculo. Los registros
C1 a C3 de la Fase B (reparar analizadores, reconstruir productores, repetir diseños) no
están aquí: van a las fases siguientes del plan (`docs/100`).

**Columna «Verificado».** «Sí» significa que lo comprobé en el árbol antes de escribirlo.
«Auditoría» significa que el texto descansa en la evidencia que cita el ledger, sin
recalcularla aquí.

| Experimento | ID | Deja de valer | Se conserva | Corregido en | Verificado |
|---|---|---|---|---|---|
| CAL-8HFI-01 | SCI-B-001 (SUSTENTADA) | leer el NO_GO como equivalencia con el azar o ausencia de asociación | el NO_GO del panel y el protocolo declarados | paper (fase 0, `9f60b4cd`) | Sí |
| FEP-01 | SCI-B-004 | «48 alcanzan el tope de 10»: es la clase «10 o más» del histograma; el enumerador corta en 32 (`MAX_TAUT = 32`) | 164 ambiguos, 39 que pasan | paper | Sí |
| FEP-02-EXT | SCI-B-005 | que use «el mismo radio» que FEP-02: usa 8 Å y FEP-02 usa 6 Å (`R_SITIO`) | el 41 como conteo a 8 Å | paper | Sí |
| FEP-03 y FEP-03-PDBBIND | SCI-B-006 | que el conteo de parejas sea una cota superior: un MCS cortado por tiempo también puede excluir parejas | el conteo de candidatas, con sesgos en las dos direcciones | papers | Auditoría |
| FEP-02 | SCI-B-007 | que 9 de 9 y 0,424⁹ **confirmen** los cortes de cadena como causa de los fallos de MF-10 | la asociación 9 de 9 | paper | Auditoría |
| MF-10 / MF-10-CAL | SCI-B-009 | que el PASS de C3 demuestre que las 714 minimizaciones convergieron | el PASS numérico de C3 y el NO_GO | papers | Auditoría |
| MF-10-CAL | SCI-B-010 | que 0,401 Å sea un «suelo» de resolución del instrumento | la deriva nativa medida y el PASS de C1 y C2 | paper | Auditoría |
| MF-10 | SCI-B-011 | que la merma (9 complejos, 164 poses) sea inocua y no sesgue hacia el NO_GO | el NO_GO, G2 y G3 observados | paper | Auditoría |
| MF-10 | SCI-B-012 | que el RMSD pareado por índice garantice invariancia frente a la simetría | G2 fallido y NO_GO operativo | paper | Auditoría |
| MF-33-A3 | SCI-B-013 | «no mueve un solo complejo»: dos complejos cambian con saldo cero | el saldo 19 contra 19 y el primario 7 a 0 | paper | Auditoría |
| MF-33-A3 | SCI-B-014 | que la conformación de partida sea la única diferencia controlada | una diferencia observada entre dos regímenes | paper | Auditoría |
| MF-33-A3 | SCI-B-015 | que el GO en la cohorte de entrenamiento autorice un claim externo | las cifras descriptivas, con su condición | paper | Auditoría |
| MF-33-H-COR | SCI-B-017 | leer el IC de Wilson por pose (99,30–99,61 %) como precisión sobre complejos nuevos | 8181 de 8224 bajo el protocolo de H, como censo | paper | Auditoría |
| MF-33-MIN-PRE | SCI-B-019 (S5) | que «no hay degradación significativa» baste para decir que la geometría no se degrada | la cancelación del experimento; no hubo corrida (n = 0) | sólo aquí | Auditoría |
| MF-33-TOP1 | SCI-B-020 | «de los 31 ganados sobreviven 18 al top-5 y 13 al top-1»: el flujo por complejo da 20 y 9 | los saldos +18 y +13, la cobertura +31 | paper | Auditoría |
| MF-33-B-RET-R2 | SCI-B-021 | «el fallo de R1 era ambiental» como causa identificada | la reparación técnica; fallo transitorio de causa no identificada, compatible con contención | sólo aquí | Auditoría |
| REC-07 | SCI-B-022 (parte C0) | que 0,773 Å y 5 de 5 validen el contacto con Cys25: su SG no está en el receptor acoplado | la geometría de las cajas | paper | Auditoría |
| MF-33-PB, MF-33-H-COR, MF-33-MIN, MF-33-TOP1 y PROD-PV-H-01 (los que usan `scripts/posebusters_metrica.py`) | SCI-B-016 (parte C0) | leer sus tasas de `pb_valid_fisica` como «batería completa superada»: la envoltura daba True con checks en NaN, con una carga fallida o sin checks físicos | las tasas, condicionadas a los checks booleanos que cada fila retuvo (`checks`, `checks_que_fallan`); la regla nueva vive en `scripts/posebusters_veredicto.py` (fase 1, `docs/100`); el módulo viejo es productor sellado y no se toca, y una recalificación retrospectiva sería C2 | sólo aquí | Auditoría |
| REC-07 | SCI-B-024 | que G3 detecte químicamente el defecto de conservar las aguas | G3 como comprobación de éxito y lectura | paper | Auditoría |
| RS-14 | SCI-B-027 | «empata dentro del ruido», «espacio de características agotado» | el NO_GO: este protocolo no demuestra superioridad | paper | Auditoría |
| RS-14-R1 | SCI-B-028 | la dirección garantizada del sesgo de las 1143 poses y que la brecha real sea «todavía mayor» | `rmsd_sym ≤ rmsd` y los 92 cubiertos | paper | Auditoría |
| RS-14 | SCI-B-029 | que se cumplieran los cuatro gates: G4 (determinismo) no se midió | los dos NO_GO por G2 | paper | Auditoría |
| MF-09 / RS-14 | SCI-B-030 | «8 de 15 recuperables en el top-5»: son 7; el 8 es el margen del oráculo | el margen del oráculo y G2 de RS-14 | papers | Auditoría |
| AF-01 | SCI-B-031 | el 0,3626 atribuido a las proteínas «no relacionadas» (es el estrato casi idéntico) y los estratos supersedidos por AF-01-R1 | la ρ global 0,6094 | paper (entradilla y correcciones) | Sí |
| AF-01 | SCI-B-032 | que la asociación por estrato cuantifique cuánta métrica es «memoria» | la asociación observada | paper | Auditoría |
| FEP-07 | SCI-B-046 | que las 19 parejas cumplan un criterio completo de receptor | 19 parejas que pasan el filtro de huecos y sitio multicadena de FEP-02 | paper | Auditoría |
| FEP-07-PDBBIND | SCI-B-048 | «2243 parejas ejecutables hoy» en la nota de 1.0.2 | 2243 parejas sin los dos flags medidos: cota de cribado, no readiness FEP | `docs/versions/1.0.2_cambios.md` | Sí |
| MF-11-R1 | SCI-B-073 | la línea de commit de su README (`2f617ec1…`) como identidad del checkout: el manifiesto registra `ad9ebcaa…` | el manifiesto, con `dirty = true` | sólo aquí | Sí |
| MF-13-ESCALA | SCI-B-081 | «no relee MF-13» y «metrics.json sólo con agregados»: el runner lee `MF-13/per_complex.jsonl` y emite resultados por caso | el cálculo, que no se invalida por esto | sólo aquí | Auditoría |

## Una inconsistencia dentro del ledger

En **SCI-B-031**, el título, la evidencia y el arreglo hablan del 0,3626 y de una ρ
global de 0,6094, que es lo que dice el paper. El campo `conclusion_que_deja_de_valer`
del mismo registro cita en cambio 0,639 y 0,824, cifras que no aparecen en el paper ni en
`AF-01-R1/metrics_estratos.json`. La corrección de arriba sigue al paper y al
`metrics_estratos.json` sellado. Se anota para el auditor.
