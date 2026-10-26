---
titulo: "El denominador estaba por debajo del listón que el propio programa se puso"
entradilla: "Con generador flexible, la cobertura de los 116 sube a 0.9224 y pasa el listón de 0.90 que MF-02D falló con 0.7931. Nueve complejos no se cubren con ningún presupuesto, y están enriquecidos en sistemas que otro diagnóstico ya había marcado."
---

Media docena de conclusiones del programa usan la misma referencia: *el conjunto de poses
candidatas de la cohorte de entrenamiento*. Cobertura del oráculo, techo del selector,
atribución de fallos — todas dividen por él.

`RC-F0-V2-EXT` midió que **el 93.9% de ese conjunto viene del protocolo rígido**. Y `MF-33`
acababa de medir que dockear flexible los mismos confórmeros cambia la cobertura del estrato
difícil de 1 a 26 sobre 33.

Si eso vale sobre los 48, el denominador de todo lo demás está mal puesto.

Este experimento lo mide sobre los **116 de entrenamiento**: mismo método que el brazo B de
`MF-33`, distinto alcance. Todos los `conf*.flex.pdbqt` del ensemble ETKDG ya en disco, con
los parámetros del brazo de control de `MF-28` —`exh=8`, `num_modes=9`, semilla 42, caja de
25 Å—. Los confórmeros **no** se regeneran. 12.76 h de reloj con 10 workers, unas 107 CPU-h.

## Qué salió

El listón no se inventó aquí: es el **G5 de `MF-02D`**, heredado tal cual. Y la línea base es
**0.7931**, la métrica de pocket, que es la primaria de `MF-02D` y la que falló su gate.

| | Cobertura del oráculo ≤2 Å |
|---|---:|
| Base rígida, conjunto v2 | 0.7931 |
| **Generador flexible, este experimento** | **107/116 = 0.9224** |
| Listón heredado del G5 de `MF-02D` | 0.90 |

**+12.93 puntos porcentuales**, y por encima del listón. La lectura preregistrada es `EL
GENERADOR FLEXIBLE ALCANZA EL LISTÓN`.

Lo que eso significa para el registro, dicho sin adornos: **`MF-02D` está sellado `NO_GO`
precisamente porque su G5 dio 0.7931 y no alcanzó**. Mismo listón, misma cohorte, misma
métrica, cambiando sólo la codificación del ligando: 0.9224.

Por estrato:

| Estrato | n | Cubiertos | Cobertura | Oráculo mediano |
|---|---:|---:|---:|---:|
| COLOCACION | 33 | 26 | 0.7879 | 1.184 Å |
| CONTROL | 15 | 15 | 1.0000 | 1.010 Å |
| RESTO | 68 | 66 | 0.9706 | 0.889 Å |

**Una comprobación de consistencia que no estaba planificada y salió perfecta:** en
COLOCACION da 26 de 33, exactamente el brazo B de `MF-33` sobre esos mismos complejos. Mismo
protocolo y misma semilla debían reproducir, y reproducen.

## La curva, que es el secundario

Cobertura acumulada según cuántos confórmeros se dockean, en orden de índice:

| K | 1 | 2 | 3 | 4 | 6 | 9 | 25 | 30 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Cubiertos | 80 | 94 | 101 | 103 | 104 | 106 | **107** | 107 |
| Cobertura | 0.690 | 0.810 | 0.871 | 0.888 | 0.897 | 0.914 | **0.922** | 0.922 |

Los tres primeros confórmeros compran 21 complejos. Los veintisiete siguientes compran seis.

Que la curva sea así de plana a partir de K≈9 dice algo sobre el coste: si hubiera que
elegir un presupuesto, está mucho antes de 30. Pero **no** dice que la ventaja del ensemble
sea presupuesto — eso lo midió `MF-33-A3`, igualando corridas, poses y CPU, y la ventaja
sigue en pie. Por eso el titular de este registro es la **cobertura final** y la curva es
descriptiva.

## Los nueve que no se cubren con ningún K

`1afl`, `1bq4`, `1d7i`, `1d9i`, `1dgm`, `1elb`, `1ew8`, `1fkh`, `1jq8`.

Siete están en la cohorte de 48; dos —`1bq4` y `1elb`— no.

Aquí hay que corregir una cuenta propia, y es un error que ya cometí antes. La versión
anterior de esta lectura hablaba de **tres** líneas independientes señalando el mismo
conjunto. Son **dos**.

Que los siete no convertidos de `MF-33-CRUCES` estén todos dentro de este grupo **no es
convergencia independiente**: `MF-33-CRUCES` define «no convertido» como que el brazo B no
alcanza ≤2 Å sobre esos 48, y este experimento reproduce el brazo B exactamente. Ese solape
de 7 sobre 7 es **reproducción**, no evidencia nueva.

La línea genuinamente independiente es `REC-09`, que midió el **scoring del cristal** y no el
docking:

| Grupo | n | Caen entre los nueve |
|---|---:|---:|
| Complejos con cristal que puntúa absurdamente mal | 6 | **4 — el 67%** |
| Los demás | 110 | 5 — el 4.5% |

Enriquecimiento **14.7×**, Fisher exacto unilateral **p = 2.45e-04**.

La afirmación defendible, y no más:

> Los fallos residuales tras un muestreo conformacional extenso están **enriquecidos** en
> complejos señalados de forma independiente por diagnósticos de preparación y puntuación.

Eso argumenta contra el muestreo conformacional adicional como **única** explicación del
conjunto de fallos residuales. No afirma que la preparación cause los nueve fallos, ni niega
que otro muestreador pudiera recuperarlos. Dice que esta intervención causal sobre el
muestreo llegó prácticamente a su límite, y que los mismos casos siguen apareciendo por otra
vía.

## Qué justifica y qué no

**La regeneración de la cohorte con docking flexible queda justificada** por la regla
preregistrada. Con la advertencia obvia: justificarla no es ejecutarla. Ejecutarla es un
programa con su propio re-sellado y el triaje de todos los consumidores del conjunto actual.

**Límites declarados:**

- el oráculo es **cota superior de lo alcanzable, no predicción**: no evalúa selector, y lo
  que llega al top-1 es otra cosa —`MF-33-TOP1` lo midió, y se atenúa;
- los confórmeros **no se regeneran**: si el techo fuese conformacional, esto no lo mueve;
- parte del techo puede ser **preparación** y no generador, que es justo lo que sugieren los
  nueve, y este experimento no los separa.

## Correcciones

**2026-10-22**, a raíz de la Fase B de la auditoría científica (fase 1b del plan de arreglos,
`docs/102_FASE_1B_CORRECCIONES.md`). Ninguna cifra sellada cambia.

- SCI-B-128. La relectura por identificador encuentra 116 unidades evaluables, coincidentes con
  MF-13, y 107 cubiertas: 0,9224 frente al listón 0,90. El resultado conservado supera ese
  umbral sobre la cohorte completa. La guarda original no exigía todos los miembros y podía leer
  un subconjunto; este reanálisis rechaza miembros ausentes, duplicados o etiquetas
  incoherentes. La cobertura sigue siendo de oráculo y no evalúa un selector. Productor:
  `scripts/analisis_fase1b_cohortes.py`.
- SCI-B-129. El sello fija el runner y referencias a MF-33 y MF-02D, mientras la selección
  ejecutada se lee de MF-13. No fija por hash esa selección efectiva ni las entradas
  estructurales, los mapas, el helper y el ejecutable Vina. El conteo posterior de las salidas
  confirma su denominador observado, pero no completa el grafo histórico de entradas ni la
  reproducción física de la corrida. La exigencia de sellado de SCI-B-045 se aplica a
  experimentos nuevos desde el 2026-10-23; no sanea este registro retroactivamente. Productor:
  `scripts/analisis_fase1b_procedencia.py`.
- SCI-B-130. Cruce exploratorio añadido después del protocolo: entre los cristales marcados por
  REC-09 hay 4 fallos de 6, frente a 5 de 110 en los no marcados; cociente descriptivo 14,67 y
  Fisher unilateral p = 0,0002454. En COLOCACION la tabla es 4/6 frente a 3/27, cociente 6,00.
  Los otros estratos no tienen cristales marcados. El contraste no estaba prerregistrado, no se
  ajusta aquí por las exploraciones del programa y no acredita causalidad ni independencia de
  los conjuntos solapados. Productor: `scripts/analisis_fase1b_cohortes.py`.
- SCI-B-131. El bloque externo no evaluó torsiones, enlaces rotables, diversidad y tamaño: sus
  valores están ausentes en las 68 unidades fuera de la cohorte inicial. El único predictor
  disponible, número de confórmeros, está ligado al presupuesto desigual de SINGLE y ENSEMBLE.
  Se mantiene INCONCLUSIVE para la política prospectiva; no se habilita una regla adaptativa ni
  se interpreta ausencia de medición como resultado negativo. Productor:
  `scripts/analisis_fase1b_limites.py`.
- SCI-B-132. El PRE fija por hash la lista de miembros de MF-33 y ese hash coincide con el
  archivo conservado hoy. El sello final de MOD fija MF-33-EXT y MF-33-DOSIS, pero no declara
  que consumiera exactamente aquella lista. Se puede reconstruir la partición conservada con el
  PRE; no se certifica por ello el vínculo omitido de la ejecución final. La exigencia de
  sellado de SCI-B-045 se aplica a experimentos nuevos desde el 2026-10-23; no sanea este
  registro retroactivamente. Productor: `scripts/analisis_fase1b_procedencia.py`.
- SCI-B-133. MF-33-EXT-MOD estimó 0,5815 como inversa de la media del primer acierto entre los
  107 cubiertos. No es la máxima verosimilitud con censura derecha de las 116 unidades. Una
  relectura posterior, bajo un modelo homogéneo de intentos independientes con K observado por
  unidad, incorpora los 193 intentos de los nueve casos censurados: 107/377 = 0,2838. La curva
  usa min(k, K_i). El ajuste es descriptivo y posterior: no valida independencia ni
  homogeneidad, no reproduce el chi-cuadrado añadido ni identifica una mezcla causal de
  poblaciones. Se mantiene INCONCLUSIVE. Productor: `scripts/analisis_fase1b_falsas.py`.
- SCI-B-134. El sello fija el analizador MOD y sus tablas; no fija un productor del
  chi-cuadrado y su p-valor añadidos después. Ese contraste tampoco quedó especificado
  formalmente en el PRE. Se retira su uso como rechazo confirmatorio de un proceso geométrico y
  la inferencia de poblaciones refractarias. El reanálisis con censura se presenta por separado
  como posterior, sin heredar el contraste ni el carácter prospectivo. La exigencia de sellado
  de SCI-B-045 se aplica a experimentos nuevos desde el 2026-10-23; no sanea este registro
  retroactivamente. Productor: `scripts/analisis_fase1b_procedencia.py`.
- SCI-B-135. El sello fija el script principal de MOD; no fija estadistica_fnd04.py ni
  versiones de las bibliotecas que determinan MDE, correlaciones y ajuste de multiplicidad. El
  campo de paquetes está vacío. Las versiones del entorno actual de reanálisis se registran
  ahora y no se atribuyen a la ejecución histórica. La exigencia de sellado de SCI-B-045 se
  aplica a experimentos nuevos desde el 2026-10-23; no sanea este registro retroactivamente.
  Productor: `scripts/analisis_fase1b_procedencia.py`.
- MF-33-EXT-MOD-R1 (2026-10-22, GO preregistrado) ejecutó el BLOQUE 3 que faltaba (SCI-B-131).
  En los 68 externos, `torsdof`, `rot_bonds`, `diversidad` y `n_heavy` sobreviven a BH contra el
  beneficio del ensemble (ρ 0.33–0.43), y pasan a ser candidatos según el PRE. Pero los cuatro
  van con el número de confórmeros (ρ 0.80–0.95), que es la dosis del ensemble: controlando por
  él, ninguno conserva asociación (ρ parcial −0.17 a −0.09, diagnóstico posterior declarado). No
  hay todavía un descriptor estático que prediga el beneficio más allá de K.
