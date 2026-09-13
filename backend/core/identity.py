"""Identidades de servicio del producto.

El escritorio inicia sesión solo como una cuenta invitada (`/auth/desktop-login`)
para que se pueda evaluar sin registrarse. Esa cuenta es real —tiene `user_id` y
contraseña aleatoria— y es la única identidad sin registro del producto desde que
se retiró el usuario demo.

Se centraliza aquí porque varias capas necesitan reconocerla y repetir el correo
literal en cada una es como se pierden estas cosas.
"""

from __future__ import annotations

#: Correo de la cuenta invitada creada por `/auth/desktop-login`.
GUEST_EMAIL = "desktop@moldesign.local"


def es_invitado(user) -> bool:
    """True si la sesión es la cuenta invitada del escritorio.

    Se usa para decidir qué ve de lo heredado: las conversaciones anteriores a
    que existiera la columna `user_id` no tienen dueño conocido y **no se les
    asigna uno por suposición** (D-07). Se muestran al invitado, que es la
    identidad bajo la que se hizo ese trabajo sin registrarse.
    """
    return getattr(user, "email", None) == GUEST_EMAIL
