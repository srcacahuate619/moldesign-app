# E4 — ventana de energía en la elección del conformador: registro previo (2026-10-24)

Escrito y commiteado **antes** de medir. Pedido por el propietario tras E2
(«parcial»: con xTB-ALPB el ΔE del elegido baja a 0,69 veces el de MMFF, pero 27
de 37 grandes siguen por encima de 5 kcal/mol). Resultados en `RESULTADOS.md`,
sección E4.

## Pregunta

Si la vista «Escrita» sólo elige entre candidatos a ≤ 5 kcal/mol (MMFF94, fase
gas) del más bajo encontrado, ¿cuánto empeora la abstención?

## Regla que se mide

Mismos candidatos que el producto (`26df919c`: 3 semillas, 16 por semilla hasta
60 átomos pesados, ETKDGv3 + MMFF94 200 iteraciones; `comun.candidatos`).

- E_min = la energía MMFF más baja de **todos** los candidatos (las tres semillas
  juntas), la misma referencia que el ΔE que declara el visor.
- Dentro de la ventana: E ≤ E_min + 5 kcal/mol.
- En cada semilla, su mejor candidato es el de menor desajuste **dentro de la
  ventana**. Si una semilla no tiene ninguno dentro, aporta su candidato de
  menor energía.
- Abstención: la mediana de los tres mejores, entre la longitud media de enlace
  del dibujo, > 1 (como el producto). La vista enseñaría el mejor de los tres.
- Moléculas sin energía MMFF (UFF o ninguna) quedan fuera y se cuentan.

Sensibilidad, que no decide: ventanas de 3 y 10 kcal/mol con la misma regla.

## Conjuntos

G37 (las 37 grandes) y O167 (las 167 originales), como en E1.

## Métricas

- abstención, producto frente a ventana, en cada conjunto;
- razón mediana;
- ΔE MMFF del enseñado (en la ventana es ≤ 5 por construcción, salvo semillas
  sin candidato dentro);
- en G37, también ΔE xTB-ALPB del enseñado, sobre el mínimo xTB-ALPB de los
  mismos candidatos (como E2), para ver si la ventana MMFF baja la energía en la
  otra superficie.

## Decisión

**Viable** (vale la pena proponer la ventana al propietario) si, con 5 kcal/mol:

- en O167 la abstención no sube más de 3 moléculas (de 1 a 4 como máximo), **y**
- en G37 no sube más de 4 (de 8 a 12 como máximo).

Si no, **NO_GO**, con la cifra de lo que costaría.

## Lo que no decide

Cambiar el producto: un «viable» se propone y se decide con el propietario.
