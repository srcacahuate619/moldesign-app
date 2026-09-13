# Estado de bloqueos legales de publicación

Este archivo resume sólo decisiones que pueden impedir distribuir el repositorio, los modelos o el instalador. La auditoría completa está en `docs/86_AUDITORIA_LEGAL_RELEASE_PUBLICO_Y_STORE.md`.

## PDBbind y derivados — resuelto por determinación del autor

Estado: **RESUELTO (2026-09-12)**.

Los pesos ligeros se distribuyen como **obra del autor** bajo PolyForm Noncommercial 1.0.0. El dataset PDBbind v2020 se reconoce como fuente de entrenamiento (atribución en `THIRD_PARTY_NOTICES.md`), pero **no se redistribuye** ni en estructuras de complejos ni en tablas de afinidades.

- Se **excluyen del canal de distribución** los artefactos que reproducen afinidades derivadas: `backend/data/benchmark_pdbbind*.json`, `pocket_dataset*.json` y `rescoring/artifacts/pdbbind_audit_report.json`. El empaquetado MSIX los retira del layout (`scripts/build_msix.py`).
- El registro Zenodo 7014096 sin `Rights` se cita únicamente como fuente; no se afirma `CC-BY`.

## Los textos de licencia que viajan — resuelto

Estado: **RESUELTO (2026-09-12)**.

El staging copia `frontend/public/legal/` a `resources/licenses/`: esa copia es la que lee el usuario, y durante un tiempo dijo algo distinto del original. `LICENSE-MODELS` afirmaba que los artefactos entrenados con PDBbind «no deben incluirse en un instalador» mientras el paquete incluía los pesos, y las copias enviadas de `MOLDESIGN-MODELS.txt` y `COMMERCIAL-LICENSE.md` se habían quedado en el texto anterior a `bf50af3`.

Los cuatro pares declarados en `PARES_LEGALES` —`LICENSE`, `LICENSE-MODELS`, `COMMERCIAL-LICENSE.md` y `PRIVACY.md`— coinciden byte a byte con su original. `DIVERGENCIAS_LEGALES_CONOCIDAS` está **vacía**, y el gate `test_las_copias_enviadas_no_se_desincronizan_del_original` falla en las dos direcciones: avisa si aparece una divergencia nueva y también si alguien deja enterrada en la lista una que ya se resolvió.

No se edita ningún texto de licencia desde el empaquetado: sigue siendo decisión del autor.

## Microsoft Store — condiciones pendientes

Estado: **pendiente de completar al enviar el MSIX**. Corte del 2026-09-13.

Resuelto desde el código:

- `PRIVACY.md` viaja en el paquete y su copia está atada al original por gate. Su §4 declara MolChat como texto generado por IA, qué sale cuando el usuario autoriza un proveedor en la nube, y que no se entrena nada con sus datos.
- **Divulgación de IA generativa y canal de reporte**: el panel de MolChat lleva un aviso permanente —no se puede cerrar— y cada respuesta un botón «Reportar respuesta» que abre el correo del usuario con la respuesta ya escrita. No se transmite nada por detrás: sería contradecir el propio aviso.
- **Ninguna salida a la red sin consentimiento por cuenta y destino.** Incluye la sonda de arranque, que sondeaba a Anthropic, Google y OpenAI con una llamada real antes de que nadie autorizara nada, y el reporte IA de una evaluación.
- Sólo se ofrecen los idiomas que están completos (español e inglés), con gate.

Pendiente, y ninguno depende de escribir código:

- Incluir la identidad exacta reservada en Partner Center.
- Proporcionar `LICENSE` como términos adicionales; no dejar el campo vacío.
- **Que los dos buzones existan y reciban.** Desde el 2026-09-13 el producto declara `moldesign@amezcua-dev.com` (privacidad, licencias, seguridad) y `soporte-moldesign@amezcua-dev.com` (soporte y reporte de respuestas de MolChat), en el mismo dominio que la identidad del paquete. Ya no hay dos direcciones para lo mismo; lo que queda es comprobar que ambas entregan antes de enviar, porque el revisor escribe a la de la ficha.
- Confirmar que avisos, textos y ofertas de fuente de terceros viajan en el MSIX.
- Ejecutar Windows App Certification Kit **sobre el paquete que se envía**: el informe que hay en `E:\rel\v1.0.0.0\wack-report.xml` es de las 21:50 del 2026-09-12 y el MSIX vigente se construyó a las 00:55 del 13. No corresponden.
- Al menos una captura de pantalla: el Store no acepta un envío sin ella.
- Instalación mediante audiencia privada antes de hacerla pública.

## Open Babel — frontera resuelta; cumplimiento por release

Estado arquitectónico: **resuelto**. Estado de entrega: **se verifica en cada release**.

Open Babel permanece como programa independiente GPL-2.0-only, fuera de `site-packages`, sin resolución por `PATH` y con hash verificado. Cada canal debe entregar su licencia y el código fuente correspondiente exacto u oferta válida. El paquete de Store no es una excepción.

## RTMScore — resuelto

Estado: **cerrado el 1 de septiembre de 2026**.

El repositorio oficial `sc8668/RTMScore` publica el código bajo licencia MIT. El snapshot integrado conserva el texto íntegro en `rescoring/RTMScore/LICENSE` y la atribución en `THIRD_PARTY_NOTICES.md`. El gate debe bloquear cualquier actualización que elimine esa licencia.

Fuente verificada: https://github.com/sc8668/RTMScore/blob/main/LICENSE

## Marca MolDesign — revisión recomendada

Estado: **no bloquea una alpha técnica, pero sí una inversión comercial significativa**.

Existen usos anteriores de “MolDesign” en software y literatura. No se ha realizado una búsqueda marcaria profesional. No usar `®` ni afirmar registro; revisar IMPI, USPTO, WIPO y EUIPO antes de consolidar la marca comercial.
