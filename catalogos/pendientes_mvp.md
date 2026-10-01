# Qué falta para el primer MVP de portaldepericias.com

Esto es una lectura honesta de lo que se puede afirmar con lo que efectivamente se vio (2 capturas del formulario Expediente + el menú lateral) cruzado contra todo el relevamiento del Trello en `catalogos/`. No es un diagnóstico completo de la app — hay secciones enteras (Pericias, Representantes legales, Evidencias, Honorarios, Agenda) que no se llegaron a ver, y eso se marca como tal, no se inventa.

## Bloqueador inmediato, antes de evaluar cualquier otra cosa

La cuenta con la que entraste tiene el cartel: **"Tu inscripción está pendiente de validación del administrador. Hasta entonces no vas a poder crear pericias."** Si "pericia" es una entidad separada de "expediente" (parece serlo, por el menú), hoy **no podés probar el flujo completo vos mismo** hasta que alguien apruebe esa cuenta. Antes de seguir evaluando el MVP, resolver esto — si el "administrador" sos vos mismo con otro usuario, aprobarla; si es un tercero, pedirle que lo haga.

## Confirmado que funciona bien (por lo que se vio)

- Alta/edición de Expediente con cascada Jurisdicción → Departamento Judicial → Organismo Judicial.
- Materia filtrada por organismo, con escape hatch ("¿No está en la lista? Agregar materia") para no bloquear la carga si falta una materia del catálogo — resuelve justo el problema que anticipamos en `materias.json`.
- Fuero no es un campo editable: se deriva del organismo. Correcto, evita el error que encontramos en la tarjeta 012-FINAMOR del Trello (cargada como Familia siendo en realidad Laboral).
- La app ya distingue Jurisdicción (provincia/nacional), algo que el Trello nunca modeló explícitamente pero que hace falta para el caso real de Justicia Nacional que encontramos (032-GONZALEZ SANABRIA).

## Gaps confirmados por el relevamiento (evidencia concreta, no suposición)

1. **No hay campo para el número interno del estudio** (el "027", "045" que ya usás hace tiempo, 71% de las 76 tarjetas lo tienen). El identificador que se ve en la URL es un ID de base de datos, no ese número. Sin esto, perdés la numeración que ya existe y con la que tus clientes/colegas conocen tus causas.
2. **Un solo campo "Nro. Expediente" para lo que en la práctica son hasta 3 números distintos** (numero_mev interno de la SCBA, numero_causa con sigla-departamento-año, y el propio del estudio). Ya encontramos un error concreto por esto: el expediente de LANDIN (027) muestra el número de otra causa (028-GHIOLDI) cargado por error.
3. **"Tipo de proceso" y, en parte, "Jurisdicción" son datos nuevos que ninguna de las 76 tarjetas tiene cargados.** Si vas a migrar las causas del Trello, estos campos quedan vacíos y hay que completarlos a mano, causa por causa — no es automatizable con lo que hay hoy.
4. **Partes (Actor/Demandado) no están en el formulario de Expediente.** Si viven en otra pantalla, falta ver que contemplen lo que el Trello ya mostró como necesario: múltiples partes por rol, aseguradoras citadas en garantía (no como demandado más), y actores que litigan por sucesión de alguien fallecido (ver `partes_hallazgos.json`).
5. **Representantes/abogados**: en el Trello, 0 de 76 tarjetas tienen CUIT, tomo/folio o domicilio electrónico de un abogado, y la mayoría no dice ni siquiera a qué parte representan. Si la sección "Representantes legales" del menú no fuerza esos campos, el problema se migra tal cual al sistema nuevo.

## No se pudo confirmar — pantallas no vistas todavía

Antes de decir "falta" hay que ver estas secciones del menú, porque puede que ya resuelvan lo que sigue:

- **Pericias** (Listado, Nueva pericia): ¿tiene Tipo de pericia (multi-select, como recomendamos en `tipos_pericia.json`), Prioridad, aceptación de cargo con plazo calculado, puntos de pericia por parte?
- **Evidencias** (Listado, Nueva evidencia, Por pericia, Por tipo) y **Cadena de custodia**: ¿el catálogo de tipos de evidencia se parece a lo que encontramos en los adjuntos reales del Trello (`tipos_documento.json`: informe pericial, anexos, puntos por parte, capturas de WhatsApp, fotos, audios, geolocalización)?
- **Honorarios** (Listado, Registrar regulación): ¿separa monto reclamado / honorarios regulados / honorarios cobrados, el problema que vimos mezclado en una sola tarjeta del Trello (003-ALBORNOZ)?
- **Agenda** (Vencimientos, Alertas, Tareas, Audiencias): ¿calcula el vencimiento de un plazo a partir de la aceptación de cargo? Solo 1 de 76 tarjetas del Trello tenía esto resuelto, y sin poder ver la regla.
- **Estados de la pericia**: ¿existe un flujo de estados tipo el de `estados.json`? ¿permite retroceder con motivo?

## Fuera del dato: qué más hace falta para un MVP real, no solo para la ficha

- **Plan de migración del Trello**, no solo el modelo de datos: las 76 tarjetas tienen datos de calidad desigual (ver todos los `*_hallazgos.json`), 3 duplicados archivados, y adjuntos reales (informes, anexos, evidencia) que hay que llevar también, no solo el texto.
- **Qué pasa con la automatización de notificaciones SCBA**: hoy alimenta tarjetas de Trello. Para el MVP hay que decidir si sigue alimentando Trello en paralelo, se apaga, o se redirige a crear directamente en el portal — y si se redirige, el portal necesita algo parecido a la "bandeja de designaciones" que hoy existe de forma manual (ver `segunda_revision_profunda_hallazgos.json`).
- **Flujo de aprobación de usuarios**: ya existe (el cartel que viste), pero no se sabe si tiene una pantalla de administración usable o si hoy se aprueba a mano en la base de datos.

## Siguiente paso más útil

Compartime capturas de **Pericias > Nueva pericia** y de **Evidencias**, que son las dos secciones que más preguntas abiertas tienen (Tipo de pericia, Prioridad, puntos de pericia, tipos de evidencia) y las que más se pueden cruzar directamente contra lo que ya sacamos del Trello.
