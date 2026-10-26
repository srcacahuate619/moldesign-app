---
titulo: "El índice de 0 a 100 no sabe más que Vina: ordena igual en una serie y peor en otra"
entradilla: "MolDesign enseña un total_score de 0 a 100 como índice de calidad, construido con constantes que nadie había medido. Contra 146 afinidades experimentales de dos dianas, no ordena mejor que el score de Vina del que sale."
---

**NO_GO.** El `total_score` no demuestra ningún valor sobre el score de Vina sin transformar.

## Qué se midió

El `total_score` se ve en la tabla SAR, en Comunidad y como score certificado de Moldex. Sale de una curva de eficiencia de ligando,
una penalización por potencia y otra por tamaño, con constantes elegidas a mano. El inventario SUPUESTOS-01 lo marcó por las dos vías
independientes: la de Claude y la de Sol.

Se comparó, con el criterio escrito antes de calcular, con qué fuerza ordena cada número las afinidades medidas. Hay dos series con
datos: VMAT2 (8T69, 89 Ki de una patente) y NET (8HFI, 57 Ki de ChEMBL). No se corrió nada nuevo: los dos números ya estaban en las
corridas guardadas.

| Serie | Correlación del total_score | Correlación de Vina | Diferencia (IC 95 %) |
|---|---:|---:|---|
| VMAT2 | 0,40 | 0,39 | +0,005 (−0,06; +0,06) |
| NET | 0,03 | 0,13 | −0,10 (−0,33; +0,13) |

## Qué dice y qué no dice

- **En VMAT2 es casi el mismo número que Vina** (correlación 0,97 entre los dos), así que no añade nada.
- **En NET se aparta de Vina y no hacia el orden experimental.** La causa no se midió.
- **No demuestra daño:** ningún intervalo excluye el cero por debajo.
- **No prueba que nunca ayude** entre familias químicas distintas. Prueba que no está demostrado donde hay datos.
- **La consecuencia la decide el propietario:** dejar de presentarlo como índice de calidad, o rotularlo en todas partes como
  «índice heredado», igual que ya hace el PDF.
