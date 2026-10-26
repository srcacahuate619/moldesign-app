---
titulo: "Con la cisteína catalítica en su sitio, el grid recomendado para 5TUN no lleva al inhibidor a ella"
entradilla: "REC-07 había validado un grid de 5TUN con contacto 5 de 5 a la Cys25. Su receptor no tenía la Cys25. Repetido con ella dentro, el grid recomendado deja el E64c a 13 Å en las cinco semillas: NO_GO."
---

**NO_GO.** La recomendación de REC-07 (`G_ADAPT`) queda refutada. El catálogo no cambia:
REC-07 tampoco lo había cambiado.

## Por qué se repitió

REC-07 comparó tres cajas para la catepsina K (5TUN, sin ligando en el cristal) y validó la
elegida con un control de docking: el inhibidor E64c debía quedar a 5 Å o menos del azufre de
la Cys25, el nucleófilo catalítico. Salió 5 de 5 en las tres cajas, con distancias de
0,4 a 1,2 Å.

Esas distancias eran imposibles, y la auditoría científica encontró por qué (SCI-B-022). En
5TUN la Cys25 tiene la cadena lateral en dos conformaciones (A y B) y la cadena principal sin
alternativa. El filtro de REC-07 elegía por residuo la variante más frecuente **contando los
átomos sin alternativa**: ganó el vacío, se quedaron N, C y O, y Meeko descartó el residuo
incompleto. **El receptor acoplado en REC-07 no tenía la Cys25.** El ligando se acomodaba en
el hueco que dejaba, justo donde se medía la distancia.

El preparador del producto no tiene este defecto: conserva siempre los átomos sin
alternativa. Era un error del experimento, no de lo que ve el usuario.

## Qué cambió, y qué no

- La regla de alternativas es la del producto: los átomos comunes siempre y, de cada residuo,
  la variante de mayor ocupación (A en caso de empate).
- Un control nuevo, G0, comprueba antes de acoplar que la Cys25 SG, la His162 NE2 y la Asn182
  ND2 están en el receptor, donde las pone el cristal. Pasó con desviación 0,0 Å.
- Todo lo demás se importó del código sellado de REC-07: las tres cajas, las cinco semillas,
  `exhaustiveness = 32`, el umbral de 5 Å y **el mismo fichero de ligando** (mismo SHA-256).
  El preregistro se escribió y se versionó antes de la primera corrida.

## Qué pasó

| Caja | Contacto top-1 (≤ 5 Å) | Distancia top-1 a Cys25 SG | Score top-1 (mediana) |
|---|---:|---|---:|
| `G_DB` (la del catálogo) | 4 de 5 | 2,46–5,89 Å, mediana 3,09 | −2,64 |
| `G_MP` (propuesta del doc. 35) | 0 de 5 | 12,91–13,06 Å | −5,30 |
| **`G_ADAPT` (la recomendada)** | **0 de 5** | **12,95–13,06 Å** | **−5,30** |

Las cajas grandes encuentran, en las cinco semillas, el mismo sitio a 13 Å de la cisteína, con
mejor score que cualquier pose cerca de ella. La caja del catálogo, más pequeña, no contiene
ese sitio y deja al ligando cerca de la Cys25, pero con scores muy débiles, de −0,9 a
−3,2 kcal/mol, y menos de nueve modos. Dos de sus distancias bajan de 3 Å, lo que el
preregistro ya advertía que puede ser un choque más que un contacto.

La regla congelada recomienda `G_ADAPT` por geometría (contiene los 15 puntos calientes y la
tríada), y esa caja falla el control: G4 (0 de 5) y G5 (peor que la del catálogo). Las demás
comprobaciones pasan, incluida la repetición de la semilla 42 en las tres cajas, que da el
mismo resultado byte a byte.

## Qué significa

- La validación funcional del grid de 5TUN que daba REC-07 **no existe**. Contener los
  puntos calientes no basta: con la cisteína presente, Vina prefiere otro sitio.
- La caja del catálogo es la única que acerca el inhibidor al nucleófilo, y lo hace con
  scores que no indican una unión. Tampoco queda validada.
- E64c es un inhibidor covalente y Vina hace docking no covalente. El control mide si la caja
  lleva al ligando al sitio catalítico, no si reproduce el aducto. 5TUN no tiene pose de
  referencia.

## Qué no dice

- No dice que el sitio a 13 Å sea un sitio real de unión de E64c.
- No generaliza a otros receptores sin ligando en el cristal.
- No cambia el catálogo ni recomienda una caja nueva.
