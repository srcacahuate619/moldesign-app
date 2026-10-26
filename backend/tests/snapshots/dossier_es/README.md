# Dossier reproducible · Serie A · exploración del bolsillo ortostérico

Paquete: `moldesign_case_caso-serie-a-001_run_task-complet`
Caso: `caso-serie-a-001`
Corrida: `task-completa-0001`
Receptor: 7E2Y · Receptor 5-HT1A acoplado a proteína G
Generado: 2026-08-24T12:00:00+00:00
Modelo del dossier: v1 · manifiesto v1

## Qué es esto

La contraparte verificable de `dossier.pdf`. El PDF es la lectura humana del
caso; este paquete permite comprobar que esa lectura se hizo sobre los archivos
que declara, y detectar si alguno falta o cambió.

**Ninguno sustituye al otro.**

## Qué NO es

No es una recomendación. No afirma que la molécula sea un fármaco, un candidato
clínico ni un compuesto seguro. Los índices 0-100 que aparecen en el apéndice
del PDF no son probabilidad, confianza ni calidad, y no son decisionales.

## Estructura

```
moldesign_case_caso-serie-a-001_run_task-complet/
├── README.md              este archivo
├── dossier.pdf            lectura humana del caso
├── manifest.json          rol, tamaño, SHA-256 y estado de cada archivo
├── checksums.sha256       índice ordenado de hashes
├── case/                  proyección del caso y modelo canónico
├── run/                   protocolo y receta de reproducción
├── inputs/                receptor y ligando, cuando existen
├── outputs/               poses y resultados serializados
├── evidencia/             evidencia estructural, selección y controles
├── preparacion/           auditoría de preparación: qué bloquea, qué revisar y qué se decidió
└── logs/                  advertencias y errores de ESTA corrida
```

## Integridad

Para verificar:

```
python scripts/verify_dossier_package.py <este-archivo>.zip
```

El verificador comprueba, sin extraer ni ejecutar nada: que ninguna entrada
escape del directorio raíz, que el manifiesto sea de una versión compatible,
que todos los archivos declarados existan, que sus SHA-256 y tamaños coincidan,
que no haya duplicados y que no haya archivos no declarados.

### Tres exclusiones deliberadas

1. **El ZIP no se contiene a sí mismo.** Un paquete que llevara su propia copia
   no podría cerrarse: su hash cambiaría al incluirlo.
2. **`checksums.sha256` no se hashea a sí mismo.** Escribir su hash dentro de sí
   mismo es imposible por la misma razón.
3. **`manifest.json` no se declara a sí mismo** dentro de `files`, por lo mismo.
   Su integridad **sí** queda cubierta: `checksums.sha256` se calcula después e
   incluye el manifiesto, así que una modificación del manifiesto se detecta.

El verificador conoce las tres y no las reporta como archivos no declarados.

### Qué demuestra un checksum, y qué no

Un checksum correcto demuestra **integridad, no validez**: prueba que los archivos
coinciden con el manifiesto y los checksums que trae el propio paquete; que no
cambiaron desde la exportación sólo se comprueba contra una huella guardada aparte.
No prueba que el método fuera
adecuado, que la preparación fuera correcta, que las poses sean físicamente
razonables ni que la conclusión sea cierta. Que el verificador diga `VÁLIDO` es
una afirmación sobre los ARCHIVOS, nunca sobre la ciencia — y nada en este
paquete afirma que el compuesto sea activo, eficaz o seguro.

## Artefactos ausentes

Un archivo ausente se declara; no se sustituye por un marcador que parezca el
artefacto.

- Ninguno: todos los artefactos declarados están presentes.

## Glosario de estados

- **NO DEFINIDO** — El caso no declaró este contexto.
- **NO EVALUADO** — El control no se ejecutó en esta corrida.
- **NO DISPONIBLE** — El resultado o artefacto esperado no está disponible.
- **NO APLICA** — El control no corresponde a este caso.
- **REVISAR** — Hay evidencia, pero no autoriza una conclusión por sí sola.
- **ABSTENCIÓN** — Falta evidencia indispensable o existe un bloqueo declarado.
- **REGISTRADO** — El dato existe y quedó serializado por la corrida.
- **PASA** — El control se ejecutó y lo superó.
