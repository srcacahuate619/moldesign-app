# CAL-D-01-R4-2 — piloto de 4-67 (registro previo)

Firmado antes de medir, el 2026-10-24. Decisión del propietario: «prueba de 1 padre primero».

## Qué se pregunta

Si el producto actual (`codex/release-hygiene`, `efdf4438`, con la validación física en proceso hijo de `48b22820`)
completa la evaluación de **4-67** contra 8T69 con el protocolo congelado de R4, cuánto tarda y si el sistema que acopla
es el mismo que congeló R4. **No mide la calibración**: con un compuesto no hay ρ.

## Qué se fija

- Compuesto: 4-67 de `panel_congelado.csv` de R4 (SMILES y microestado esperado de ese fichero, carga +1).
- Receptor 8T69 cadena A, el del catálogo; parámetros de R4: exhaustividad 8, 9 poses, semilla 42, 4 CPU, Vina 1.2.7.
- Cápsula de API aislada de R4 (`scripts/cal_d01r4/capsula.mjs`), sin editar nada sellado.

## Qué se registra (y qué NO se mira)

Se registran estado final, segundos, versión de Vina, CPU, semilla, exhaustividad, poses, microestado acoplado, SHA-256 del
receptor preparado y el estado de la etapa de validación física del top-1.
**El score de Vina, el RMSD y la pose no se imprimen ni se leen**: el resultado completo se guarda en `piloto/crudo.json`
y queda sin abrir hasta que el panel completo tenga su propio registro previo firmado.

## Resultados posibles

- **COMPLETA:** SUCCESS dentro del tope del producto. Habilita proponer el panel de 89 padres con su registro previo.
- **NO_COMPLETA:** FAILURE o tiempo agotado. 4-67 sigue como límite declarado; no se propone el panel.
- **DERIVA:** completa, pero el microestado o los parámetros no son los congelados. Se declara antes de proponer nada.
  Un SHA del receptor distinto del de R4 (`8fc027ca…`) NO es deriva del piloto: el producto cambió desde `6f3ff1b5`
  (metales en dos niveles, receptor para el rescoring); se anota y el panel nuevo tendría que congelar el receptor nuevo.

Un solo intento. Si falla por causa ajena al cálculo (la cápsula no arranca), se anota en DESVIACIONES y se repite una vez.
