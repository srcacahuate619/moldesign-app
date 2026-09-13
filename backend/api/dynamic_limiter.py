from slowapi import Limiter
from slowapi.util import get_remote_address
from fastapi import Request

class _DynamicLimitCallable:
    """
    Callable compatible con SlowAPI 0.1.9 para límites dinámicos por tier.

    SlowAPI 0.1.9 llama al callable con `(request)` durante la ejecución real,
    pero también puede intentar llamarlo sin argumentos durante la introspección
    interna. Esta clase maneja ambos casos correctamente.
    """

    def __call__(self, request: Request = None) -> str:
        """
        Retorna el límite de requests basado en el nivel de suscripción del usuario.
        Si no hay request disponible (introspección interna de SlowAPI),
        retorna el límite más conservador como fallback seguro.
        """
        # Aplicación local single-user: suficiente para validación masiva de
        # targets, sin una política SaaS de tiers o workers remotos.
        return "3000/minute"


get_dynamic_limit = _DynamicLimitCallable()

limiter = Limiter(key_func=get_remote_address)
