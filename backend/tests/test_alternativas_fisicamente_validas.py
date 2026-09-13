"""Doc 71, defecto E2: una pose que pasa los controles no puede desaparecer.

El informe de la VM: «la pose #2 supera los controles fisicos y es la que el
selector habria elegido, pero se excluye de "alternativas fisicamente validas"
aunque el dossier afirme que las nueve pasaron».

La causa esta en una exclusion que es correcta a medias:

    alternativas = [... for r, e in fisicos.items() if e == PASA and r != rank_sugerido]

Excluir `rank_sugerido` es lo correcto cuando el selector SI recomendo algo: esa
pose es la recomendacion, no una alternativa a si misma. Pero cuando se ABSTIENE,
`rank_sugerido` es la candidata que descarto -lo que el contrato llama
`would_have_suggested_rank`- y no hay recomendacion de la que sea alternativa.

Excluirla ahi la hacia desaparecer de las DOS listas a la vez: no era la
recomendada, porque no hubo ninguna, y tampoco figuraba entre las validas aunque
hubiera pasado los controles.
"""

from __future__ import annotations

import inspect

from services.chemistry import pose_selection


def test_la_exclusion_depende_de_que_haya_recomendacion():
    fuente = inspect.getsource(pose_selection)
    assert "_alternativas(None)" in fuente, (
        "la rama de abstencion volvio a excluir la pose que habria sugerido: "
        "desaparece de las dos listas a la vez"
    )


def test_la_rama_con_recomendacion_sigue_excluyendo_la_recomendada():
    """Listarla como alternativa de si misma seria ruido, no informacion."""
    fuente = inspect.getsource(pose_selection)
    assert "_alternativas(rank_sugerido)" in fuente


def test_el_helper_filtra_por_estado_fisico_y_no_por_otra_cosa():
    fuente = inspect.getsource(pose_selection)
    inicio = fuente.index("def _alternativas(")
    cuerpo = fuente[inicio:inicio + 400]
    # La condicion tiene que ser IGUALDAD con «pasa», no desigualdad con
    # «falla»: con `e != FISICO_FALLA`, una pose cuyo estado es `None` -nadie la
    # midio- entraria como valida. Es la distincion que sostiene toda la validez
    # fisica de este producto: no evaluado nunca es aprobado.
    assert "e == FISICO_PASA" in cuerpo, (
        "las alternativas dejaron de filtrarse por igualdad con el veredicto "
        "«pasa»: una pose sin medir podria colarse como valida"
    )
