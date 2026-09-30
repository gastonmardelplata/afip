# Catálogos — relevamiento del tablero "Pericias 2026"

Relevamiento manual de las **76 tarjetas reales** del tablero Trello ["Pericias 2026"](https://trello.com/b/LXVxhiUl/pericias-2026) (2026-09-30), hecho para diseñar el modelo de datos del wizard de ingreso de causas descrito en la propuesta original, reemplazando supuestos por evidencia. Cada archivo dice qué está confirmado contra una tarjeta real y qué es solo inferido.

Todos los archivos son JSON con una clave `_fuente` (y a veces `_regla_de_diseno`) que explica el origen del dato. Los que terminan en `_hallazgos` no son catálogos de valores: documentan problemas concretos de datos que el modelo nuevo tiene que resolver.

## Paso 1 — Expediente

| Archivo | Contenido |
|---|---|
| `organismos.json` | 20 organismos reales (Juzgados Civil y Comercial, Tribunales del Trabajo, Juzgado de Familia, Cámara), con tipo/número/departamento/localidad. 11 confirmados literalmente, 9 inferidos por cruce con otra tarjeta del mismo juzgado. |
| `departamentos_judiciales.json` | Siglas de expediente confirmadas en uso real: **MP** (Mar del Plata), **NE** (Necochea). Tres Arroyos no tiene sigla propia (depende de Bahía Blanca) y nunca aparece con una en las tarjetas. |
| `fueros.json` | Catálogo **cerrado y completo** de los 7 fueros oficiales de la provincia (Civil y Comercial, Laboral, Familia, Penal, Responsabilidad Penal Juvenil, Contencioso Administrativo, Justicia de Paz). Solo los primeros 3 están en uso real. Fuero se deriva del tipo de organismo, no se tipea. |
| `materias.json` | 14 materias reales, cada una con las variantes de texto libre vistas y si está confirmada por cruce con el organismo o solo sugerida por la carátula. |
| `tipos_pericia.json` | 10 etiquetas atómicas (WhatsApp, redes sociales, correos, código de barras bancario, home banking/ciberfraude, sitio web y dominio, sistema corporativo, publicidad digital/YouTube, CCTV, evidencia digital sin precisar), pensadas para **selección múltiple** porque los datos reales ya combinan medios en un mismo campo. |

## Paso 2 — Partes y representantes

No son catálogos de valores (cada causa tiene sus propias personas); lo catalogable es el rol.

| Archivo | Contenido |
|---|---|
| `roles_parte.json` | Actor, Demandado, Citado en garantía, Tercero. |
| `tipos_representante.json` | Apoderado, Patrocinante, y **Consultor técnico / perito de parte** — rol no previsto en la propuesta original, evidenciado en una tarjeta donde la contraparte presentó su propio informe forense. |
| `partes_hallazgos.json` | 4 problemas reales: abogados sin rol ni parte asociada (3 de 4 casos), aseguradoras cargadas como demandado en vez de citadas en garantía, un actor fallecido cargado en vez de sus herederos, y partes múltiples metidas en un solo campo de texto. |

## Paso 3 — Pericia

| Archivo | Contenido |
|---|---|
| `prioridad.json` | Alta / Media / Baja (solo Alta y Media están en uso real). |
| `checklist_diligencia_base.json` | La única checklist estructurada encontrada en las 76 tarjetas (texto libre, ninguna usa el checklist nativo de Trello), separada en una base común y una parte específica según Tipo de pericia. |
| `paso3_hallazgos.json` | Número interno en 5 formatos distintos sin duplicados pero con huecos sin explicar (9, 48-52); aceptación de cargo cargada de dos formas y ausente en 72 de 76 tarjetas; anticipo de gastos y honorarios regulados mezclados bajo el mismo evento SCBA "DEPOSITA"; una tarjeta con 4 cifras de monto sin diferenciar; y confirmación de que la "bandeja de designaciones" no reemplaza ningún paso existente porque hoy no hay ninguno. |

## Estados y campos transversales

| Archivo | Contenido |
|---|---|
| `estados.json` | 9 estados del flujo principal + 4 laterales, cada uno mapeado a su lista real de Trello. Faltan como lista hoy: **Designada**, **Honorarios regulados** y **Excusada**. |
| `estados_hallazgos.json` | Corrige la propuesta original con datos reales: el retroceso de estado **ya es técnicamente posible hoy** (16 retrocesos reales encontrados en el historial de movimientos); el problema real es que ninguno tiene un motivo registrado. También documenta que el flujo real no es lineal (causas que saltan etapas) y un caso de ruido no procesal (5 movimientos en 2 minutos). |
| `banderas.json` | Urgente / En revisión / Listo — confirmado por el usuario como el significado de las etiquetas de color rojo/amarillo/verde. Es un atributo independiente del Estado y de la Prioridad. |
| `campos_nativos_trello_hallazgos.json` | Campos nativos de Trello (etiquetas, fecha due, miembros) que la primera pasada no había mirado por revisar solo el texto de las descripciones. |

## Revisión en profundidad (tarjetas archivadas y adjuntos)

| Archivo | Contenido |
|---|---|
| `tipos_documento.json` | Catálogo de tipos de documento/evidencia sacado de los **adjuntos reales** de al menos 17 tarjetas (informe pericial, anexos, puntos de pericia por parte, capturas de WhatsApp crudas y compiladas, fotos, audios, evidencia de geolocalización, contestación de impugnación). Nunca se había revisado esto antes; conecta directo con el módulo "Evidencias" del portal real. |
| `segunda_revision_profunda_hallazgos.json` | 3 tarjetas duplicadas encontradas al revisar archivadas (044, 045, 046: la archivada vacía, la abierta con los datos); confirmación de que la "bandeja de designaciones" ya existe hoy de forma **informal** (una tarjeta-lista manual que se archiva al procesarla), matizando el hallazgo anterior de que "no existe ningún paso de bandeja". |

## Los 5 hallazgos más importantes para el diseño

1. **Hay tres números distintos, no uno mal cargado**: `numero_mev` (ID interno del sistema SCBA/MEV, pelado, sin formato), `numero_causa` (`SIGLA-correlativo-año`, ej. MP-12931-2019) y `numero_interno` (el propio del estudio, ej. 061-2026). Una tarjeta real tiene los dos primeros juntos (`Expdte. 128703. MP-12931-2019`).
2. **Fuero debe derivarse del organismo, no tipearse**: cruzando cada tarjeta contra su propio juzgado encontramos que "Fuero: Daños y Perjuicios" y "Fuero: Bancaria" son materias mal cargadas, y la tarjeta 012 (FINAMOR) está cargada como Familia cuando el juzgado real es un Tribunal de Trabajo (Laboral) — un error real, no cosmético.
3. **El retroceso de estado ya funciona hoy**, técnicamente; lo que falta es el motivo y que el historial sea visible sin bucear en el log de actividad de Trello.
4. **La "bandeja de designaciones" no reemplaza nada existente en un estado del flujo**, pero sí existe hoy de forma informal: una tarjeta-lista manual acumula las notificaciones nuevas y se archiva cuando se procesan (convertidas en tarjetas 🆕 individuales). El diseño nuevo formaliza ese paso, no inventa uno.
5. **Ningún dato de representantes está completo**: en 76 tarjetas, cero traen CUIT, tipo de persona, tomo/folio completo o domicilio electrónico; solo 1 de 4 abogados mencionados dice a qué parte representa.
6. **Hay documentación sustancial que vive solo como adjunto de archivo**, nunca relevada hasta la revisión en profundidad: el informe pericial final, sus anexos, los puntos de pericia por parte (como PDF, no texto), y toda la evidencia (WhatsApp, fotos, audios, geolocalización). Cualquier migración tiene que llevarse también estos archivos, no solo los datos de texto de la ficha.

## Lo que todavía falta relevar

- El modelo de datos completo de Partes/Representantes como esquema (campos, no solo roles) — quedó extraído la evidencia pero no escrito el schema final.
- Migración de las 76 tarjetas actuales al modelo nuevo, incluyendo revisar el resto de las tarjetas archivadas (no está en el alcance de este relevamiento).
- Confirmar a mano los huecos de numeración interna (9, 48-52) antes de arrancar la numeración nueva.
- El significado de las 3 etiquetas de color usadas una sola vez cada una (naranja, azul, "Gris") — quedaron sin migrar.
- Traer el historial completo de adjuntos del tablero (el relevado cubre los últimos ~100 eventos de carga; hay más historial disponible sin traer).
