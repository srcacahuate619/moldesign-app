# Política de seguridad

MolDesign es un alpha con código fuente público que ejecuta un backend local y motores
científicos en Windows. La aplicación no debe exponerse directamente a Internet
ni utilizarse para tomar decisiones clínicas o farmacológicas sin revisión
humana.

## Cómo informar un problema

No publiques credenciales, archivos de casos, coordenadas privadas ni detalles
de una vulnerabilidad sin corregir en un issue público. Envía un informe
privado a `moldesign@amezcua-dev.com` o utiliza un aviso privado de seguridad de
GitHub cuando esté habilitado para el repositorio.

Incluye, si es posible:

- versión o commit de MolDesign;
- sistema operativo y modo de ejecución (desarrollo, runtime embebido o setup);
- pasos mínimos para reproducirlo;
- impacto observado;
- logs y archivos de ejemplo ya anonimizados;
- una propuesta de mitigación, si la tienes.

## Alcance prioritario

Se consideran especialmente importantes los problemas que permitan:

- ejecutar código fuera del backend local o escapar del directorio autorizado;
- sustituir silenciosamente un motor, peso, manifiesto o binario verificado;
- falsificar procedencia, hashes, estados de abstención o resultados persistidos;
- introducir una dependencia o artefacto con licencia incompatible;
- exfiltrar estructuras, casos, tokens o configuración local;
- convertir una abstención científica en una conclusión presentada como válida.

## Proceso

Confirmaremos la recepción cuando sea posible, reproduciremos el problema en un
entorno aislado y coordinaremos la publicación de una corrección o mitigación.
No se garantiza un plazo fijo de respuesta: el proyecto es mantenido por una
persona y se encuentra en alpha.

Las versiones publicadas deben verificarse mediante el SHA-256 del instalador y
el manifiesto de release. La ausencia de firma Authenticode se declara en cada
release y no debe confundirse con una validación de seguridad.

## Versiones soportadas

Sólo la rama y los artefactos publicados más recientes reciben revisión activa.
Las ramas experimentales y los checkpoints científicos no son canales de
distribución soportados.
