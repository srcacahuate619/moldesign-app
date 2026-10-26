# VISION-MOLECULAR-01 — acta de cierre

**Decisión: NO_GO.** Ninguna de las seis alternativas medidas para la elevación 2D → 3D de ligandos grandes cumple su registro
previo, y ninguna entra en el producto. Lo que el producto ya hace es lo que mejor se sostiene:
- la pose se enseña en 3D aunque no se levante desde el dibujo (`3ea0aa92`);
- se generan 16 candidatos por semilla (`26df919c`);
- el visor interpola en línea recta;
- el ΔE del conformador se declara.

- **Qué es la elevación.** La vista «visión molecular» del editor y de Moldex levanta el dibujo 2D de Ketcher a una geometría 3D
  que se le parezca. Se abstiene cuando ninguna lo hace sin mover átomos más de un enlace.
- **Producto de referencia:** `26df919c`, con 16 candidatos por semilla y 3 semillas.
- **Conjuntos:**
  - G37: 37 moléculas de 35 a 51 átomos pesados; con el producto se abstienen 8.
  - O167: las 167 del conjunto original; se abstiene 1.
- **Sellado al cerrar, el 2026-10-25, juntando los seis** (decisión del propietario). Cada uno se registró y se midió por separado.
  Su registro previo se commiteó antes que su resultado, y git lo acredita:

| | Alternativa | Registro previo | Resultado | Veredicto |
|---|---|---|---|---|
| E1 | Dibujo que se ajusta al 3D | `fcbb9d1e` (23:04) | `f526bae8` (23:39) | **NO_GO** |
| E2 | ΔE del conformador con xTB | `fcbb9d1e` | `f526bae8` | **parcial** |
| E3 | Plegado restringido al dibujo | `fcbb9d1e` | `f526bae8` | **NO_GO** |
| E4 | Ventana de energía de 5 kcal/mol | `4517768f` | `8f864f52` | **NO_GO** |
| E5 | Enderezar cadenas y girar colas, como MolTalk | `aa22435e` | `81ad8c82` | **NO_GO** |
| E6 | Animación por torsiones frente a línea recta | `74b2d17f` | `d7498799` | **NO_GO** |

## Lo que dice cada uno

- **E1 (NO_GO).** El dibujo ajustado rescata 10 de las 25 abstenciones de G37 con el proxy de pose, y hacía falta el 75 %. Con el
  conformador elegido es peor que el dibujo normal (14 frente a 6 de 37).
- **E2 (parcial).** El ΔE mediano del elegido baja de 11,5 kcal/mol (MMFF94, fase gas) a 8,0 con GFN2-xTB y ALPB en agua, es decir
  0,69 veces. El registro marcaba «exagera» por debajo de 0,5 y «se sostiene» por encima de 0,8. Con ALPB, 27 de 37 siguen por
  encima de 5 kcal/mol: MMFF exagera cerca de un tercio, pero no invierte el problema.
- **E3 (NO_GO).** Se abstienen 5 de 37 y hacían falta 4 o menos. Además, en 11 de las 29 moléculas restringidas no hay ningún
  embebido posible.
- **E4 (NO_GO).** Con una ventana de 5 kcal/mol la abstención sube de 8 a 23 en G37 y de 1 a 19 en O167; los límites eran +4 y +3.
  Parecerse al dibujo y tener baja energía son objetivos opuestos en moléculas flexibles.
- **E5 (NO_GO).** La abstención de G37 baja de 8 a 7, y hacía falta 4 o menos. No empeora nada ni cambia ningún centro R/S.
- **E6 (NO_GO).** El problema que debía resolver casi no existe: con la línea recta, sólo 2 de las 29 grandes que se levantan
  cruzan átomos a mitad de camino, y ninguna de las 166 de O167. Las torsiones dan 4 cruces y bajan la deformación un 14–19 %; hacía
  falta la mitad.

## Cómo se comprobó al sellar

- **Sin volver a medir.** `scripts/vision_molecular_01/resumir.py` aplica los criterios de cada registro a los datos escritos
  (`e1.jsonl` … `e6.jsonl`) con los resúmenes de los propios scripts, y reproduce los seis veredictos y todas las cifras de
  `docs/auditorias/elevacion-grandes-2026-10-24/RESULTADOS.md`.
- **Que los scripts reproducen al producto:** E1–E3 lo comprobaron en 5 moléculas antes de medir (`comun.comprobar_reproduccion`).

## Desviaciones

1. **Sellado después de medir y en un solo experimento.** Los seis no se sellaron uno a uno. La garantía de que el criterio
   precede al dato es el orden de los commits, no el sellado.
2. **Rutas de máquina corregidas antes de sellar.** Ninguna cambia un cálculo.
   - `e2_delta_e_xtb.py` buscaba xTB en `RAIZ.parents[1]/moldesign-build/…` y fallaba fuera del worktree donde se escribió. Ahora
     usa `XTB_DIR` o `tools/xtb/` del repositorio.
   - Tres scripts de la auditoría de abstención (`convergencia.py`, `medir_desajuste.py` y `validar_abstencion.py`) fijaban la raíz
     en `D:/moldesign-worktrees/audit-producto-1.0.4`. Ahora la calculan desde su propia ubicación.
3. **E2 no tenía consecuencia escrita para «parcial».** Se resolvió después de E4: el producto conserva el ΔE declarado (MMFF94, fase
   gas) y no cambia la elección.
4. **Proxy de pose, no poses reales.** E1 usa como pose el primer conformador ETKDGv3 + MMFF94 sin elegir por parecido. Lo que dice
   sobre Moldex es una aproximación.
