"""El aviso de «Molécula grande» habla de Vina, no de la ruta de péptidos (RESULTS.md §5.9 del HOT FIX 1.0.3).

Salía también en moléculas que no son péptidos (warfarina, erlotinib): un fármaco pequeño y flexible recibía una frase
sobre ESMFold que no le aplica. Los péptidos tienen su propio aviso (`PEPTIDO_LINEAL_DETECTADO`).
"""

from __future__ import annotations

import inspect
import re

from services.docking import queue_handler
from services.pipeline import runner


def _avisos_de_molecula_grande(fuente: str) -> list[str]:
    return re.findall(r"Molécula grande \(.*?\)\s*[,\n]", fuente, flags=re.S)


def test_el_aviso_de_molecula_grande_no_menciona_esmfold():
    for modulo in (queue_handler, runner):
        avisos = _avisos_de_molecula_grande(inspect.getsource(modulo))
        assert avisos, modulo.__name__
        for aviso in avisos:
            assert "ESMFold" not in aviso, (modulo.__name__, aviso)
