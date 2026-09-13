# Corridas doradas

Punto 6 de la Fase 0 de `docs/74_ARQUITECTURA_DISPATCHER_DE_PROTOCOLOS.md`, y
la especificación ejecutable del dossier.

## Qué son

Un snapshot sellado por protocolo, con las entradas exactas y el significado
científico que deben producir. No son «la salida que dio el programa el día que
se escribió el test»: son el contrato que el refactor de las Fases 3-6 no puede
romper.

    m4_small_molecule.json      M4: afinidad Vina cruda, poses, protocolo, procedencia
    m5_zn_ca2_3dc3.json         M5-Zn: el perfil más completo (Vina + XGB + GNN-D + UMS)
    m5_zn_replay.json           Replay matemático de los tres perfiles desde checkpoints
    peptide_sin_pesos.json      Péptidos: abstención limpia sin ESMFold instalado
    peptide_con_sidecar.json    Péptidos: corrida positiva con el sidecar disponible

## Qué se compara, y qué no

Se compara el **JSON canónico sellado**: claves ordenadas, sin campos
dependientes del reloj ni de la máquina. Un PDF con fecha o metadatos variables
no se compara byte a byte — para el PDF se comprueba contenido semántico,
secciones obligatorias y ausencia de contradicciones.

El criterio de cierre, tal como se acordó:

> Los mismos inputs producen el mismo snapshot científico, manifiesto y
> significado tanto desde el repositorio como desde el backend embebido.

## Cómo se regeneran

    python scripts/generate_goldens.py            # escribe
    python scripts/generate_goldens.py --check    # falla si difieren

Una diferencia **exige explicación**. No se actualiza el golden automáticamente
ni «porque el test falla»: el fallo es la señal de que algo cambió de
significado, y hay que decidir si ese cambio es correcto antes de sellarlo.

## Por qué el replay de M5-Zn está separado

`m5_zn_ca2_3dc3.json` ejercita el perfil sobre un caso; `m5_zn_replay.json`
reconstruye las AUC de los tres perfiles desde los checkpoints originales y las
compara con `data/molchamb_loto/delong_paired_report.json`. Son dos garantías
distintas: la primera dice que el código aplica la fórmula, la segunda que la
fórmula sigue siendo la que se publicó.
