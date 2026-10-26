---
titulo: "En PDBBind sí hay series para FEP: 3299 parejas en 313 dianas"
entradilla: "Los 203 complejos de molflex se armaron para la diversidad y apenas daban 91 parejas perturbables. PDBBind completo da treinta y seis veces más, y el recuento no depende del tiempo que se le conceda al MCS."
---

Un cálculo de energía libre relativa (FEP) no compara una molécula con el vacío:
compara dos ligandos parecidos en el mismo sitio. Necesita **series congenéricas**,
pocas dianas con muchos análogos. El conjunto de 203 complejos con el que se
auditó FEP-03 se había armado para lo contrario, para cubrir muchas dianas
distintas, y daba 91 parejas aptas repartidas en 18 dianas, con el grupo mayor
en 23 ligandos.

La pregunta de este experimento era si el problema era del conjunto o de la
fuente: si PDBBind completo, con los mismos criterios, contiene series útiles.

## Qué salió

Con los umbrales del sello (cobertura del MCS ≥ 0,70 y perturbación ≤ 10
átomos pesados):

| | molflex (203) | PDBBind |
|---|---:|---:|
| Parejas aptas | 91 | **3299** |
| Dianas con alguna pareja | 18 | **313** |
| Dianas con ≥ 10 ligandos conectados | — | **28** |
| Dianas con ≥ 20 ligandos conectados | — | **12** |

La hipótesis se sostiene: la escasez de series era una propiedad del conjunto,
no de la fuente.

## Dos comprobaciones antes de creerlo

**Réplica.** Antes de extender nada, se repitió la auditoría sobre los 203
originales. El resumen coincide con el sello y 486 de 487 parejas salen
idénticas. La que cambia (1ezq-1ksn) pasa de un MCS de 1 átomo a 27 sin
volverse apta, y enseña algo útil: **un MCS con límite de tiempo depende de la
carga de la máquina**.

**Sensibilidad al límite de tiempo, declarada antes de correr.** 163 MCS se
habían cortado a los 10 s. Se repitieron con 300 s: el MCS creció en 47, 32
siguieron cortados y **ninguna pareja cambió de veredicto** (23 aptas antes y
después). El recuento no depende del tiempo concedido. Un primer intento de
esta sensibilidad fue inválido —el límite se pasó como número decimal y las 163
fallaron— y se conserva como evidencia.

## La limitación, declarada

- Es una **cota superior**: la agrupación por diana usa k-meros de secuencia y
  no distingue mutantes puntuales de la misma proteína.
- El universo efectivo son **3887 de 5325** entradas, porque la copia local de
  PDBBind no trae el `_protein.pdb` de 1438.
- Para elegir cohorte hacen falta afinidades por ligando. Las añadidas desde
  BindingDB al índice local se emparejaron por diana y no por complejo, así que
  **no sirven**; con las de la fase A, la cohorte recomendada es galectina-3
  (6qln-6qlu, 7 ligandos de un mismo artículo).
- PDBBind **no permite redistribuir** sus estructuras ni sus afinidades sin
  permiso escrito. El artefacto guarda identificadores PDB, recuentos y
  agregados por diana; un paquete para terceros construido sobre esta cohorte
  tendría que reconstruirse desde los identificadores.

## Correcciones

**2026-10-20**, a raíz de la Fase B de la auditoría científica del producto. Ninguna cifra sellada cambia y no se repitió ningún cálculo; esto corrige lo que el texto afirmaba a partir de ellas. Detalle y procedencia en `docs/101_CORRIGENDA_SELLOS_AUDITORIA_20261020.md`.

- SCI-B-006. Igual que en FEP-03: el conteo de parejas es de candidatas con sesgos en las dos direcciones, no una cota superior demostrada.

**2026-10-22**, a raíz de la Fase B de la auditoría científica (fase 1b del plan de arreglos,
`docs/102_FASE_1B_CORRECCIONES.md`). Ninguna cifra sellada cambia.

- SCI-B-008. «Ligandos conectados» contaba los extremos de todas las parejas aptas de una
  diana: dos parejas sueltas A–B y C–D sumaban 4 aunque no haya camino entre A y D. Contando el
  **mayor componente conexo**, que es lo que necesita una red de FEP relativo, hay **11** dianas
  con 10 o más ligandos (no 28) y **4** con 20 o más (no 12); 73 de las 313 dianas tienen más de
  un componente. Un componente conexo tampoco es todavía una red parametrizable. Productor:
  `scripts/analisis_fep03pdbbind_componentes.py`.
