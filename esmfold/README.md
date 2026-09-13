# `esmfold/` — sólo el destino de los pesos

El **código** del servicio vive en [`backend/sidecars/esmfold/`](../backend/sidecars/esmfold/),
que es el árbol que el instalador copia. Aquí sólo queda `models/`, que es donde
el gestor de modelos deja el checkpoint descargado.

Esa separación es deliberada:

* el **código** pesa kilobytes y viaja en el instalador;
* los **pesos** pesan 8.4 GB y se descargan una vez, bajo demanda.

El backend le pasa al servicio la ruta de `models/` por la variable
`ESMFOLD_MODEL_DIR`, así que los dos no tienen que estar juntos. Quien enciende
el proceso es `backend/services/motores/sidecar.py`, no estos `.bat`, que se
conservan para arrancarlo a mano durante el desarrollo.
