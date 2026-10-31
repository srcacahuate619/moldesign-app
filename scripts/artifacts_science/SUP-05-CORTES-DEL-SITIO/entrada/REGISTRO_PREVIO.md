# SUP-05-CORTES-DEL-SITIO — registro previo (2026-10-25)

Escrito y commiteado **antes** de medir ninguna distancia. Sale del inventario SUPUESTOS-01 (semilla S01 y S02; bloque 2 de
la fase 2, aprobado por el propietario el 2026-10-25).

## La pregunta

Preparación decide con dos cortes que nadie ha medido:
- **S01, 8 Å** (`UMBRAL_RESIDUO_A`, `services/dossier/contexto_estructural.py`): un hueco del esqueleto con un extremo a 8 Å o
  menos del ligando **abstiene**; el mismo corte decide qué cadenas laterales truncadas, His y altlocs se nombran. El
  argumento es «una Arg mide ~7 Å desde el Cα». El único falso bloqueo de ABS-TR-01-VALIDEZ-R1 (4JVB) fue un hueco a 6,09 Å.
- **S02, 6 Å** (`UMBRAL_ESPECIE_A`): un metal, cofactor u otra copia del ligando retirados a 6 Å o menos «está junto al sitio»
  y pide revisión.

La pregunta no es cuál es el corte correcto (eso pide un redocking con y sin el hueco, otro experimento), sino si **la
decisión depende del corte**: si moverlo un ångström cambia el estado de Preparación en muchas entradas del catálogo, el
número elegido a mano decide por el usuario y necesita una medida; si casi ninguna cambia, la elección es inocua.

## Datos (ya existen; no se acopla nada)

Las 381 entradas de `curated_targets.json`, con su depósito `data/targets/<PDB>.pdb.gz`. Para cada una, el script
(`scripts/sup05_cortes/medir.py`) reproduce con las funciones del producto, sin modificarlas, lo que hace `prepare_target`
antes de Meeko: la unidad biológica (`generar_unidad_biologica`), el filtro de cadenas (`_filter_pdb_content`, con la lista de
cofactores de la entrada), el truncado de cadenas laterales, la retirada de hidrógenos contradictorios y los huecos
(`huecos_del_esqueleto`). Mide desde el **ligando del cristal**: la copia de `site_ligand` más cercana al centro de la caja,
como `contexto_estructural`.
- **Hueco:** distancia mínima entre los átomos de sus dos residuos extremos (en el ensamblaje) y el ligando del cristal.
- **Truncada:** igual, con los átomos del residuo truncado.
- **Especie:** cada residuo HETATM del ensamblaje que no es agua, ni la copia elegida del ligando, ni un residuo modificado de
  la cadena (con N, CA y C); metal si su elemento está en `METALES_PDB`. Distancia mínima al ligando del cristal. Un metal
  coordinado por el ligando (N, O o S a ≤ 2,8 Å) abstiene con cualquier corte y se cuenta aparte.

## Medidas

Para cada corte T del hueco en {6, 7, 8, 9, 10} Å: entradas con algún hueco a ≤ T (abstienen) y con alguna truncada a ≤ T.
Para cada corte T de la especie en {5, 6, 7, 8} Å: entradas con alguna especie a ≤ T, por clase (metal, otra copia del
ligando, otra orgánica).

- **Primaria 1:** entradas cuyo estado por huecos cambia entre 7 y 9 Å (un ångström a cada lado del corte vigente).
- **Primaria 2:** entradas cuyo estado por especies cambia entre 5 y 7 Å.
- Declaradas, sin decidir: la tabla completa por corte; la distribución de la distancia del hueco más cercano; para los 28
  sistemas de ABS-TR-01-VALIDEZ-R1, en qué cortes cambia su estado por huecos y el veredicto de su panel (detener o no), es
  decir, falsos bloqueos por huecos en función del corte; la distancia que mide este script para 4JVB frente a los 6,09 Å
  publicados.

## Regla de decisión

El denominador es el de las entradas con ligando del cristal localizado y depósito legible (se publica cuántas quedan fuera).
- **GO** (los cortes no deciden por el usuario): las dos primarias son ≤ 5 % del denominador.
- **NO_GO** (alguno de los dos cortes es un filo): alguna primaria es > 5 %. El corte correspondiente necesita una medida
  (redocking con y sin el hueco o la especie) antes de seguir abstiniendo o pidiendo revisión con él.
- Menos de 300 entradas medibles: INCONCLUSIVE.

Consecuencia que se propondrá al propietario (no la decide este experimento): con NO_GO, diseñar el redocking que fija el
corte; con GO, declarar en Preparación la sensibilidad medida junto al número.

## Lo que no es ciego

Nada de esto se ha medido para los cortes alternativos. Del corte vigente se conocen casos sueltos (4JVB, 1RKP, 6KE5) y los
recuentos de la auditoría del 2026-10-08, que medía desde la caja con otra receta.

## Límites declarados de antemano

- Preparación mide desde el mínimo entre la pose top-1 y el ligando del cristal; aquí sólo desde el cristal. En un redocking que
  reproduce la pose son lo mismo; donde la pose se aleja, el producto puede bloquear más.
- Las especies se toman del ensamblaje, no del `species_diff` de una preparación con Meeko: es una reproducción geométrica de
  la regla, no una corrida del producto. 15 entradas no se preparan con Meeko y aquí sí se miden.
- Mide si la decisión es sensible al corte, no si el corte es correcto.
