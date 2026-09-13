---
titulo: "Un conjunto que se usa una sola vez, custodiado antes de existir"
entradilla: "112 complejos separados del desarrollo por identidad, química de ligando y secuencia de receptor. Se selló antes de puntuar nada, y sólo puede consumirse una vez."
---

Casi todo lo que hace este programa es exploratorio. Se prueba una idea, se mide, se
declara el resultado, y el conocimiento acumulado guía la siguiente prueba. Ese ciclo es
legítimo, pero tiene un coste que casi nunca se contabiliza: cada vez que se mira un
conjunto de datos para decidir qué hacer después, ese conjunto queda un poco más gastado
como prueba independiente.

Un conjunto **confirmatorio** es la reserva contra ese desgaste. Se aparta antes de
empezar, no se toca, y se consume una sola vez al final para responder la pregunta
principal.

Este experimento lo construye y lo sella.

## Qué se exigió

La separación tenía que ser real por tres vías simultáneas, porque cualquiera de ellas por
separado deja pasar fuga:

| Criterio | Cómo |
|---|---|
| Por identidad | El mismo complejo no puede estar a los dos lados |
| Por química del ligando | Scaffold, clave de conectividad InChI, y huella ECFP con umbral 0.90 |
| Por receptor | Identidad y homología por cadena, con solapamiento de k-meros a 0.90 |

La tercera es la que faltaba en el conjunto original y la que la auditoría de fuga había
encontrado rota. Aquí se exige desde el diseño.

## Qué salió

| | |
|---|---:|
| Complejos totales | **112** |
| Estrato primario (drug-like) | **102** |
| Análisis secundario, descriptivo | 10 |

Los 10 restantes son 1 fragmento, 6 péptidos, 1 oligonucleótido y 2 casos de enlace
cruzado. Se apartan del gate primario porque su tamaño no permite inferencia fuerte, y se
declaran como análisis descriptivo **antes** de mirar nada. Meterlos en el numerador o
sacarlos después de ver los resultados serían dos formas de la misma trampa.

El determinismo y la cuarentena se verificaron. El manifiesto se selló **antes de puntuar
un solo complejo**.

## Lo que este sello sí garantiza, y lo que no

Conviene ser exacto, porque el proyecto usa la palabra «cegamiento» y merece decir de qué
tipo:

> El secuestro es **procedimental**, no técnico. Las etiquetas están apartadas por
> disciplina y por registro, no por control de acceso de máquina.

Es un holdout interno custodiado por un procedimiento, y el propio manifiesto lo declara
así: **sin control de acceso real, no se afirma cegamiento real**. Un solo mantenedor con
acceso a todo no puede demostrar que no miró; lo que puede hacer es dejar constancia
sellada de cuándo se fijó el conjunto y con qué criterio, de modo que cualquier cambio
posterior sea visible.

Esa es una garantía más débil que el cegamiento, y decirlo es parte de lo que hace que el
registro valga.

## Por qué sigue sin dispararse

La regla escrita antes es que un resultado negativo en el confirmatorio **se publica y
cierra el claim**: no se reintenta, no se reajusta el gate, y no se reclasifica a
posteriori como exploratorio.

Con esa regla en pie, disparar el confirmatorio sobre un candidato inmaduro destruye el
activo sin comprar nada. Hoy el selector empata o pierde contra la puntuación cruda de
Vina, así que la precondición no se cumple y el conjunto sigue guardado.

Hay además una reserva declarada: de los 440 candidatos elegibles, los 328 no
seleccionados quedan marcados como pool para un eventual segundo confirmatorio, con
prohibición expresa de usarlos para desarrollo o depuración — de modo que sigan siendo
elegibles si algún día hacen falta.

Preferible declarar el programa incompleto que gastar la única bala que hay.
