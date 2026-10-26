"""Guion de dictado: 20 frases como las que alguien le diría a MolChat.

Cada frase lleva el término que tiene que salir bien escrito para que el
dictado sirva: un nombre de fármaco, un receptor, un concepto de la app. La
tasa de error por palabra cuenta igual una preposición que «Murcko»; el acierto
del término clave es la medida que decide si el dictado es usable aquí.

Escritas para esta prueba el 2026-10-10. Para medir de verdad hay que grabarlas
con voz humana (`grabar.html`); la voz sintética de Windows sólo prueba que la
cadena funciona y da una cota optimista.
"""

# (id, frase, término clave)
FRASES = [
    ("f01", "Calcula las propiedades del paracetamol.", "paracetamol"),
    ("f02", "Acopla la cafeína contra el receptor 5-HT2A.", "5-HT2A"),
    ("f03", "¿Qué significa que el receptor esté en revisión?", "revisión"),
    ("f04", "Muéstrame las corridas de esta semana con exhaustividad alta.", "exhaustividad"),
    ("f05", "Compara el ibuprofeno con el naproxeno.", "naproxeno"),
    ("f06", "Predice la toxicidad y la absorción de la metformina.", "metformina"),
    ("f07", "¿Por qué la preparación del receptor está bloqueada?", "preparación"),
    ("f08", "Genera análogos de la nicotina con menor peso molecular.", "análogos"),
    ("f09", "Explica el esqueleto de Murcko de la aspirina.", "Murcko"),
    ("f10", "¿Cuál fue la mejor afinidad contra el transportador de serotonina?", "serotonina"),
    ("f11", "Valida este SMILES antes de evaluarlo.", "SMILES"),
    ("f12", "¿El sitio de unión tiene metales o aguas estructurales?", "aguas estructurales"),
    ("f13", "Ordena las moléculas de la sesión por afinidad de Vina.", "Vina"),
    ("f14", "¿Qué tautómero se usó para el ligando?", "tautómero"),
    ("f15", "Busca compuestos similares a la teobromina.", "teobromina"),
    ("f16", "Resume la evidencia de la última evaluación.", "evidencia"),
    ("f17", "¿Cuántos enlaces rotables tiene el diazepam?", "diazepam"),
    ("f18", "Lanza un docking del haloperidol contra el receptor de dopamina D2.", "haloperidol"),
    ("f19", "¿Qué advertencias tiene el dossier de esta corrida?", "dossier"),
    ("f20", "Explícame la diferencia entre ligando y receptor en Moldex.", "Moldex"),
]

#: Vocabulario de la app para el `--prompt` de whisper.cpp: condiciona la
#: ortografía de los términos sin entrenar nada. Se mide con y sin él.
PROMPT_VOCABULARIO = (
    "MolDesign, MolChat, Moldex, Vina, docking, SMILES, receptor 5-HT2A, dopamina D2, "
    "tautómero, Murcko, exhaustividad, dossier, paracetamol, ibuprofeno, naproxeno, "
    "metformina, teobromina, haloperidol, diazepam."
)
