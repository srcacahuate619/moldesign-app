---
titulo: "El sitio inter-cadena sobrevive a la preparación"
entradilla: "Veintiséis complejos tienen el bolsillo formado por varias cadenas, uno de ellos por cuatro. Ninguno pierde una sola cadena al preparar el receptor. El riesgo anotado hace meses no se materializa."
---

`FEP-02` midió que **43 de 203 complejos tienen el sitio de unión repartido entre más de una
cadena**, y su propio código dejó anotado el riesgo concreto: que la función que detecta la
cadena dominante recorte una sola y **destruya un sitio inter-cadena**.

Ese riesgo llevaba meses escrito y nunca se comprobó. Si se materializara, no sería un
problema de documentación como el resto de la cartera H: sería un **defecto de producción**,
y todo lo medido sobre los complejos afectados arrastraría un error no declarado.

Comprobarlo resultó costar once segundos, porque el material ya existía.

## Qué se comparó

Para cada complejo, dos lecturas y una resta:

1. **Cadenas que forman el sitio** — las que aportan algún residuo con un átomo a ≤ 8 Å de
   algún átomo pesado del ligando cristalográfico, medido sobre el PDB **original**.
2. **Cadenas presentes en el receptor preparado** — el `rec.pdbqt`, que es el que Vina
   realmente usa.
3. **Pérdida** — cadenas de (1) ausentes de (2).

El radio de 8 Å se reusó de `FEP-02` en lugar de elegir uno nuevo, para que las dos
mediciones sean comparables.

## Qué salió

> **0 de 116 complejos tienen el sitio mutilado.**

Y donde más podría haber dolido:

| | |
|---|---:|
| Complejos con sitio formado por más de una cadena | **26** |
| Máximo de cadenas en un mismo sitio | **4** |
| De esos 26, cuántos pierden alguna cadena | **0** |

El riesgo no ocurre. Es un negativo limpio, y es buena noticia: no hay nada que reparar por
esta vía.

## La limitación que sí importa

**Cobertura: 116 de 203, el 57%.**

Los 87 restantes son **todos de `valtest`**, y fallan por una causa única: **no existe
`rec.pdbqt` para ellos**. El receptor preparado sólo se generó para `train`.

Eso no es un fallo del análisis — es una asimetría real del material. La afirmación vale
para `train` y **no se extiende a `val` ni a `test`**.

Queda anotado porque cualquier experimento futuro que compare receptores preparados entre
splits se va a topar con lo mismo, y conviene saberlo antes de diseñarlo que después de
ejecutarlo.

## Lo que este resultado NO dice

Se compara **presencia de cadena**, no identidad residuo a residuo. Una cadena presente pero
**recortada en su extremo**, o con residuos ausentes en medio, no se detecta con este
criterio.

> El resultado es una **cota inferior** del daño: dice que no se pierden cadenas enteras, no
> que el receptor preparado sea idéntico al original en la región del sitio.

Medirlo exigiría comparación residuo a residuo. Es el paso natural si alguna vez aparece
sospecha de recorte fino, y no hay motivo para darlo mientras no aparezca.

## Por qué merecía ejecutarse aunque saliera negativo

Era un identificador declarado en la cartera de receptor que llevaba meses sin tocarse, con
un riesgo documentado y sin medir. Un riesgo escrito y no comprobado tiene el peor de los
dos comportamientos posibles: no protege de nada y sigue apareciendo en cada revisión como
una duda abierta.

Once segundos lo cerraron.
