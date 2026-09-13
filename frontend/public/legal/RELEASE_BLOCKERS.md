# Estado de bloqueos legales de publicación

Este archivo resume sólo decisiones que pueden impedir distribuir el repositorio, los modelos o el instalador. La auditoría completa está en `docs/86_AUDITORIA_LEGAL_RELEASE_PUBLICO_Y_STORE.md`.

## PDBbind y derivados — resuelto por determinación del autor

Estado: **RESUELTO (2026-09-12)**.

Los pesos ligeros se distribuyen como **obra del autor** bajo PolyForm Noncommercial 1.0.0. El dataset PDBbind v2020 se reconoce como fuente de entrenamiento (atribución en `THIRD_PARTY_NOTICES.md`), pero **no se redistribuye** ni en estructuras de complejos ni en tablas de afinidades.

- Se **excluyen del canal de distribución** los artefactos que reproducen afinidades derivadas: `backend/data/benchmark_pdbbind*.json`, `pocket_dataset*.json` y `rescoring/artifacts/pdbbind_audit_report.json`. El empaquetado MSIX los retira del layout (`scripts/build_msix.py`).
- El registro Zenodo 7014096 sin `Rights` se cita únicamente como fuente; no se afirma `CC-BY`.

## Los textos de licencia que viajan están un commit atrasados — decisión del autor

Estado: **abierto (detectado el 2026-09-12)**. Bloquea el envío, no el build.

El staging copia `frontend/public/legal/` a `resources/licenses/`: esa copia es la que lee el usuario. Dos textos no se actualizaron cuando `bf50af3` los modificó en la raíz del repositorio, y en ambos casos el párrafo que falta es la limitación sobre PDBbind:

| Texto que viaja | Falta respecto al original |
|---|---|
| `licenses/MOLDESIGN-MODELS.txt` | «*Some current manifests describe artifacts trained or evaluated with PDBbind v2020. Their public redistribution remains `REVIEW_REQUIRED`… those artifacts must not be included in a public repository, model hub or installer*» |
| `licenses/COMMERCIAL-LICENSE.md` | «*PDBbind-derived artifacts remain excluded until their rights are documented*» |

Hay dos cosas que resolver, y ninguna es automatizable:

1. **`LICENSE-MODELS` de la raíz contradice la determinación del 2026-09-12.** Dice que los artefactos entrenados con PDBbind «no deben incluirse en un instalador», y el paquete incluye los pesos. El resto de documentos (`docs/78`, `docs/86`, este fichero, `THIRD_PARTY_NOTICES.md`) se actualizaron ese día; `LICENSE-MODELS` no. Enviar a Store con la licencia de modelos diciendo lo contrario de lo que hace el paquete es un riesgo evitable en una revisión.
2. **Sincronizar las copias que viajan** una vez decidido el texto definitivo.

No se edita ningún texto de licencia desde el empaquetado: es decisión del autor. El gate `test_las_copias_enviadas_no_se_desincronizan_del_original` mantiene la lista de divergencias conocidas y avisa si aparece una tercera o si una queda resuelta.

## Microsoft Store — condiciones pendientes

Estado: **pendiente de completar al enviar el MSIX**.

- Incluir la identidad exacta reservada en Partner Center.
- Proporcionar `LICENSE` como términos adicionales; no dejar el campo vacío.
- Publicar y enlazar `PRIVACY.md` y un contacto de soporte.
- Confirmar que avisos, textos y ofertas de fuente de terceros viajan en el MSIX.
- Ejecutar Windows App Certification Kit y una instalación mediante audiencia privada antes de hacerla pública.

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
