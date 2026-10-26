# E6 — animación por torsiones en vez de interpolación lineal: registro previo (2026-10-25)

Escrito y commiteado **antes** de medir. Resultados en `RESULTADOS.md`,
sección E6.

## Problema

El visor (`frontend/lib/elevacion.ts::proyectar`) lleva cada átomo en línea
recta desde su sitio en el dibujo hasta su sitio en el 3D alineado. A mitad de
camino los enlaces se estiran o se encogen y dos átomos lejanos en el grafo
pueden pasar uno a través del otro. Es una deformación que no existe en la
molécula. E1–E5 mostraron que en moléculas grandes el 3D no se parece al dibujo,
así que el camino recto es largo y la deformación debería crecer.

## Lo que se compara

- **A, el producto:** p(s) = (1 − s)·(dibujo, z = 0) + s·xyz, con s ∈ [0, 1].
- **B, por torsiones:** del conformador elegido C (con hidrógenos, el del
  producto) se fijan sus enlaces rotables —sencillos, fuera de anillo, con un
  vecino pesado más a cada lado— al diedro que tienen en el dibujo (0° o 180°,
  porque el dibujo es plano). Eso da F, con los anillos y los ángulos de C. El
  camino es:
  - s ∈ [0; 0,25]: línea recta del dibujo a F alineado al dibujo;
  - s ∈ [0,25; 1]: 16 fotogramas en los que cada diedro rotable va de su valor
    en F a su valor en C por el giro más corto; cada fotograma se alinea al
    dibujo con `_ajuste` y los pesos del producto, y entre fotogramas se
    interpola en línea recta.
  - El último fotograma es exactamente el xyz del producto.

Se mide en 3D con la rotación del visor en la identidad, en unidades del dibujo,
muestreando s en 101 puntos. L es la longitud media de enlace del dibujo.

## Métricas, por molécula

- **deformación:** el máximo, en s y en enlaces, de |d(s) − d_lin(s)| / L, donde
  d_lin es la interpolación lineal entre la longitud del enlace en s = 0 y en
  s = 1;
- **cruce:** el mínimo en s de la distancia entre átomos pesados a 3 o más
  enlaces, entre L, es < 0,5, y en los dos extremos es ≥ 0,5;
- **tiempo** de calcular el camino B (sólo para el conformador enseñado) y
  **tamaño** de los fotogramas en JSON con dos decimales.

Conjuntos: G37 y O167, como E1–E5; sólo cuentan las moléculas que el producto
levanta (fiel), que son las que se animan.

## Decisión

**GO** (vale la pena proponerlo para el visor) si se cumplen todas:

- G37: el producto tiene al menos 4 moléculas con cruce (si no, el problema no
  existe en la práctica) y B deja como mucho la mitad;
- O167: B no tiene más moléculas con cruce que A;
- en los dos conjuntos, la mediana de la deformación de B es ≤ 0,5 veces la de A;
- los extremos de B coinciden con los de A (≤ 0,01 unidades del dibujo);
- tiempo mediano de B ≤ 0,3 s y tamaño mediano ≤ 40 kB en G37.

Si no, **NO_GO**, con las cifras. Un GO no cambia el producto por sí solo: se
propone al propietario.
