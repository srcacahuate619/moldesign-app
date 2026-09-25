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
    m5_zn_replay.json           Abstención verificable: checkpoints externos ausentes
    peptide_sin_pesos.json      Péptidos: abstención limpia sin ESMFold instalado
    peptide_con_sidecar.json    Péptidos: corrida positiva con el sidecar disponible
    e2e_vina_3f75.json          Vina real: perfiles PRO y normal, inputs y salida persistidos

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
    python scripts/generate_goldens.py --check    # pasa desde un clon limpio
    python scripts/generate_goldens.py --verify-m5-replay  # opcional con matrices locales

Una diferencia **exige explicación**. No se actualiza el golden automáticamente
ni «porque el test falla»: el fallo es la señal de que algo cambió de
significado, y hay que decidir si ese cambio es correcto antes de sellarlo.

## Replay de M5-Zn

Los tres checkpoints originales no se redistribuyen. El golden versionado
declara `NO_DISTRIBUIDO` e identifica ruta, SHA-256 y AUC de referencia; no
afirma haber reconstruido esa AUC en un clon que carece de los datos.

Con los tres archivos locales, `--verify-m5-replay` verifica primero sus SHA-256
y sólo entonces reconstruye las AUC. Devuelve 2 cuando faltan archivos y 1
cuando un hash o una AUC difiere. El gate ordinario no depende de ellos.

## Golden E2E de Vina

`python scripts/accept_evaluation_runtime.py` ejecuta Vina 1.2.7 sobre 3F75
con los perfiles PRO y normal. Contrasta afinidad, caja efectiva, semilla,
versiones, hashes de receptor, SDF/PDBQT de entrada y poses. Reinicia el
backend y vuelve a leer la corrida desde SQLite. Comprueba además que el ZIP
del dossier contiene los bytes exactos del ligando, receptor y log declarados
por la procedencia de la corrida. La referencia procede de dos ejecuciones
independientes en Windows x64 con Python embebido 3.11.9 el 2026-09-25.

Los logs incorporan rutas locales de ejecución; su SHA se comprueba contra
el archivo archivado en cada corrida, pero no se fija entre corridas.
