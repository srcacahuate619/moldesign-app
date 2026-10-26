# CAL-D-01, ronda 4 — registro previo de la campaña sobre VMAT2 / 8T69

**Fecha:** 2026-10-21. **Lo adopta:** el propietario de MolDesign («sí a CAL-D-01»: P1 como criterio
de éxito, P2 como sensibilidad). **Lo escribe:** Claude.
**Anclaje del repositorio:** `6f3ff1b5` (rama `claude/auditoria-ciencia-arreglos`).
**Se escribe antes de cualquier score.** Nadie en el proyecto ha visto un score de Vina de un
compuesto de este panel ni de 8T69. Su SHA-256 se anota fuera de esta carpeta al escribirlo; si no
coincide, se tocó después.

## 1. De dónde viene

| Ronda | Resultado |
|---|---|
| R1 (`CAL_D_01_datos`) | NO_GO_DATOS: 1IAS sin ligando orgánico; 8WRE con sustrato en otro estado |
| R2 (`CAL_D_01_R2`) | 8T69 sirve con condiciones; panel NO_GO_DATOS por la regla 8: Ki con Kd de 2,5 o 4,06 nM según el lote, sin asignación por compuesto |
| R3 (`CAL_D_01_R3`) | RESCATABLE CON REGLA NUEVA: no hay mapa de lotes en 41 miembros de la familia ni en las bases que la copian; con F = 1015/703, la ρ mínima exacta entre los dos órdenes de Ki es 0,9914 (89 padres) |

**Esta regla está informada por el NO_GO de R2 y por los Ki ya leídos.** Es el cuarto intento de
decisión de CAL-D-01 (1IAS → 8WRE → 8T69 → regla nueva), no una réplica independiente ni un holdout.
Multiplicidad de resultados computacionales: M = 1 (ninguno mirado todavía).

## 2. Qué se afirma, y qué no

Si todo sale bien: **8T69, con este receptor preparado, esta receta, Vina 1.2.7, Q = −E(top-1) y esta
configuración, ordena los Ki publicados de las tablas 15A/15B de US11718618B2 (Example 11, plaquetas
humanas, [³H]DTBZ 10 nM), y la conclusión resiste la peor asignación de lotes posible.**

No se afirma: una condición experimental homogénea, una afinidad corregida por MolDesign, la
comparabilidad entre lotes, una afinidad absoluta, la probabilidad de un compuesto, otra serie u otra
diana, ni preparación para FEP. La sensibilidad al factor F no cubre el resto de la variabilidad
experimental (el duplicado 4-31/4-118 difiere 8×).

## 3. Panel (fijado antes de scores)

`panel_89_8T69.csv` en esta carpeta, SHA-256
`ff5e0c69eda2fea39e143db5360a384ff183baa02124f40f717f508560722ca9`: los 90 padres nominales de la
cascada de R2 menos 4-31 (y su duplicado 4-118, ya fuera), apartados por identidad o réplica no
adjudicada y **no por su potencia**. Fuente: `universo_8T69_auditado.csv` de R2, SHA-256
`b63c0763ebd64e1f02a6ddab7598bb659b1f8ee791cf09179493e58b557460cd`. Los 89 son Ki puntuales con `=`.
Censurados, no ensayados y estéreo sin resolver siguen fuera, como en R2. Entrada química:
`smiles_isomerico_completo`, forma parental sin contraión.

**Endpoint orientado:** pKi = −log10(Ki [M]), mayor = más potente. Ningún Ki se vuelve a corregir.

## 4. Sistema y configuración (fijados antes de scores)

- **Receptor:** 8T69 del catálogo, cadena A, caja del catálogo (centro 127,862; 123,474; 104,225;
  30 Å), `cofactors_whitelist` vacía, receta de receptor vigente en el anclaje. El SHA-256 del
  receptor preparado se registra en la congelación y se comprueba en cada corrida; una deriva para
  la campaña.
- **Motor:** Vina 1.2.7 del producto, exhaustividad 8, 9 poses, un conformador, 4 CPU por proceso.
  **Score primario Q = −E_Vina(top-1).** Ningún modelo ML ni índice compuesto como endpoint.
- **Ligandos:** el microestado que acopla el producto a pH 7,4 se congela antes de scores, en dos
  procesos (la protonación no es determinista). En cada corrida se comprueba que el acoplado es el
  congelado; una deriva es un fallo técnico, no se reacopla con otro.
- **Semillas:** redocking del cristal (`YHL`) con 42, 43, 44, 45 y 46; panel con semilla 42 única
  por compuesto.
- **Validez física:** PoseBusters 0.6.5 `dock`, con la reconstrucción de hidrógenos de MF-33-H-COR.

## 5. Criterios de decisión

**Gate de pose (primero, y si falla se para sin acoplar el panel):** top-1 a RMSD simétrico de
átomos pesados, sin alinear, ≤ 2 Å en al menos 3 de 5 semillas, y todas las que cumplen RMSD con
PoseBusters válido. Se publican las 5. Si falla: NO_GO, sin receptor alternativo.

**Criterio primario (P1).** Se calculan:

1. ρ = Spearman(Q, pKi publicado), rangos medios en los empates.
2. ρ_peor = mín sobre todas las asignaciones b_i ∈ {0, 1} de Spearman(Q, pKi_i − b_i·log10 F),
   con F = 1015/703.
3. IC 95 % de ρ y de ρ_peor por bootstrap percentil, pareado por padre, **10 000 réplicas, semilla
   20261021**. En cada réplica, ρ_peor se recalcula, y todas las copias de un mismo padre llevan la
   misma b_i.

**GO** sólo si el límite inferior del IC 95 % de ρ **y** el de ρ_peor son mayores que 0, con el gate de
pose superado, cero fallos persistentes y cero desviaciones críticas. Si no: NO_GO. Si los fallos
técnicos dejan menos de 85 padres evaluados: EXPLORATORIO, sin promoción.

**Sensibilidad P2 (secundaria, no decide):** concordancia de orden sólo en los pares con cociente de
Ki estrictamente mayor que F (3584 de 3916 en los 89), con bootstrap por padre; los pares no se tratan
como observaciones independientes. Se publican también ρ con 4-31, con 4-118 y con la mediana de ambos,
como sensibilidad. Ninguna sustituye al primario.

## 6. Lo que tiene que existir antes de lanzar la campaña

1. **El estadístico ρ_peor contra los scores, implementado y probado.** R3 sólo lo resolvió entre dos
   órdenes de Ki. La implementación se valida contra enumeración exhaustiva de las 2^n asignaciones
   en casos pequeños, incluidos empates y valores junto al umbral, antes de ver un solo score real.
2. **El arnés parametrizado** (copia de `scripts/calibracion_receptor.py` en un experimento nuevo, sin
   cambiar métrica ni gates), probado con transporte simulado, que rechace sobrescribir una salida.
3. **El presupuesto:** tope de 168 CPU-core-h del protocolo CAL-D-01. Al alcanzarlo, se conservan los
   parciales y el resultado es INCONCLUSIVE; el tope no se mueve.

Un timeout o fallo técnico permite un reintento idéntico; los dos se conservan.

## 7. Qué cambia en el producto según el resultado

- **NO_GO o EXPLORATORIO:** se publica como intento (`intentos_de_verificacion.json` y su paper), igual
  que CAL-8HFI-01. Ningún receptor cambia.
- **GO:** antes de escribir `receptores_verificados.json`, el gate `supera_el_protocolo` y la interfaz
  (catálogo, dossier y su PDF, Preparación, vistas de resultados, en los dos idiomas) tienen que poder
  llevar ρ_peor y la condición de lote, con su guardián de pruebas. Sin eso no se promociona. El sello
  sólo describe corridas con el mismo receptor preparado y los mismos parámetros.

## 8. Parada

- Gate de pose fallido → NO_GO; no se prueba otra estructura.
- Ningún cambio de regla después de ver un score. Si hiciera falta uno, sería otro registro y otro
  intento, declarado.
- Las variantes de curación no se cuentan como experimentos independientes.
