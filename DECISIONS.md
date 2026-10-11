# Decisiones metodológicas

Log de decisiones tomadas durante el proyecto: qué se decidió, por qué, y qué alternativas se descartaron.

---

## 2026-09-14 — Gestor de entorno y dependencias: `venv` + `pip` + `requirements.txt`

**Decisión:** usar el módulo estándar `venv` para el entorno virtual y `pip` con un `requirements.txt` para las dependencias.

**Por qué:** es la opción con menos piezas nuevas que aprender de golpe, viene incluida con Python (sin instalar nada extra) y tiene la documentación más extendida. El autor viene de R y está aprendiendo el ecosistema Python desde cero.

**Alternativas descartadas:**
- `uv`: más rápido y moderno, pero una herramienta adicional que aprender antes de tener el flujo básico dominado.
- `conda`/`miniforge`: más robusto con dependencias que compilan (geopandas), pero más pesado y no es necesario todavía.

**Reconsiderar si:** aparecen problemas de instalación con paquetes geoespaciales (`geopandas`) que `pip` no resuelva bien — en ese caso, revisar `conda`.

---

## 2026-09-14 — Layout del código: `src/` con paquete `andorra_housing`

**Decisión:** el código Python vive en `src/andorra_housing/` (paquete instalable), no como carpeta suelta en la raíz del repo.

**Por qué:** obliga a instalar el propio proyecto (`pip install -e .`) para importarlo, lo que evita imports que solo funcionan "por accidente" al ejecutar desde una carpeta concreta. Es el estándar actual en proyectos Python de portfolio.

**Alternativas descartadas:**
- Layout plano (`andorra_housing/` en la raíz): más simple de entender al principio, pero con más riesgo de imports frágiles.

---

## 2026-09-14 — Visibilidad del repositorio: público desde el inicio

**Decisión:** el repositorio de GitHub (`rental-housing-andorra`) es público desde el primer commit.

**Por qué:** así lo pide el plan del proyecto (portfolio para búsqueda de empleo); mostrar el proceso de construcción, no solo el resultado final, también tiene valor de cara a reclutadores.

**Alternativas descartadas:**
- Privado hasta cerrar la Fase 1: evita mostrar pasos intermedios desordenados, pero se descarta para no restar valor de mostrar el proceso completo.

---

## 2026-09-15 — Ubicación de los anuncios en pisos.ad: sin dirección exacta ni coordenadas

**Decisión:** para pisos.ad, usar como ubicación de cada anuncio la parroquia (`parish`) y, cuando esté disponible en la URL del anuncio, el núcleo de población (p. ej. `arinsal`, `el-tarter`, `soldeu`) como nivel intermedio de granularidad. No se dispone de dirección exacta ni de coordenadas para el inmueble en este portal.

**Por qué:** se comprobó, sobre dos anuncios reales, que pisos.ad no publica la dirección del inmueble como texto estructurado. El widget de ubicación (`fitxa__ubicacio`) solo contiene un `<div id="map">` vacío que se rellena con JavaScript en el navegador, invisible para `requests`/BeautifulSoup. Se descartó también la posibilidad de datos estructurados SEO: no hay ningún bloque `application/ld+json` en la página. La única dirección en texto plano que aparece en la ficha es la de la oficina de la inmobiliaria (bloque `fitxa__barraimmo`), no la del piso — usarla sería incorrecto. El núcleo de población en la URL de listado (ej. `/lloguer/pisos/tots-subtipus/la-massana/arinsal`) sí es información fiable y estructurada, y da más resolución que la parroquia sola.

**Alternativas descartadas:**
- Geocodificar la dirección de texto libre de la descripción: descartada porque la dirección rara vez aparece ahí de forma explícita y fiable (en el anuncio revisado, la descripción mencionaba una calle que resultó no estar en ningún otro campo de la ficha, y no puede darse por buena sin confirmación).
- Adelantar la revisión de idealista.com/fotocasa.es para resolver esto antes de seguir con pisos.ad: descartada por ahora para no romper el orden del plan ("no pasar al siguiente portal hasta que el anterior funcione de punta a punta").
- Usar Playwright para renderizar el mapa JS y capturar las coordenadas que carga: descartada por complejidad/coste no justificado en esta fase, cuando ya hay una solución parcial razonable.

**Limitación que queda documentada para el README:** `dist_parish_center` y `dist_escaldes` para los anuncios de pisos.ad tendrán menor precisión de la deseada (nivel núcleo de población, no vivienda exacta). Se investigará si idealista.com y/o fotocasa.es sí ofrecen dirección exacta o coordenadas cuando se llegue a esos portales (fase 1.1, portales 2 y 3); si la tienen, se cruzarán los anuncios duplicados entre portales (por precio, superficie, habitaciones y similitud de descripción, según la estrategia de deduplicación ya definida en el plan) para asignar la ubicación exacta también a los anuncios que solo aparecen en pisos.ad.

**Reconsiderar si:** al llegar a idealista.com o fotocasa.es se confirma que sí publican dirección exacta o coordenadas — en ese caso, evaluar cuántos anuncios de pisos.ad se pueden enriquecer por cruce de duplicados antes de aceptar la granularidad de núcleo de población como definitiva para el resto.

---

## 2026-09-15 — Ampliación puntual del esquema de extracción LLM: añadir `n_parking_spaces`

**Decisión:** añadir un sexto campo al esquema cerrado de extracción LLM (definido en el plan): `n_parking_spaces` (entero o `null`). El resto del esquema (`condition`, `construction_year`, `renovation_year`, `expenses_included`, `expenses_detail`, `furnished`) se mantiene sin cambios.

**Por qué:** al revisar `fitxa__descripcio` en los anuncios de ejemplo, se observó que el número de plazas de parking a veces aparece detallado en el texto libre (más preciso que el simple booleano/categórico de `fitxa__icos-parking`, que solo indica si está incluido, opcional o no disponible). Es un dato objetivo y verificable directamente en el texto, no una percepción subjetiva del anunciante — coherente con el resto del esquema LLM.

**Alternativas descartadas:**
- Añadir también un campo de "pista de ubicación" (calle/zona mencionada en la descripción) para mitigar la limitación de geolocalización de pisos.ad (ver decisión anterior): descartada. La dirección rara vez aparece de forma fiable en el texto libre (ya visto en un anuncio anterior), y no aporta nada que la granularidad de núcleo de población (URL) no dé ya de forma más consistente.

**Punto abierto, pendiente de decidir en el EDA (fase 1.2), NO en esta extracción:** si merece la pena que el LLM extraiga también "características cualitativas declaradas" en la descripción (cercanía a comercios, transporte, zona tranquila, vistas...). Son afirmaciones subjetivas del anunciante (posible sesgo de marketing, "cerca" no es una distancia medible), a diferencia de `services_500m` que se calculará de forma objetiva vía Overpass API — mezclarlas contaminaría una variable objetiva con marketing. Antes de fijar estos campos en el esquema, revisar en el EDA cuántas descripciones mencionan este tipo de cosas y de qué forma, igual que el plan ya hace con los umbrales de "estudios" y "chalets/casas".

---

## 2026-09-15 — `floor` en pisos.ad: sustituido por `is_penthouse`, sin planta numérica fiable

**Decisión:** para pisos.ad, no tratar `floor` (planta) como un campo estructurado esperado. Se usa `is_penthouse` (ya previsto en el plan como dummy) detectado por la palabra "àtic" en el título/slug de la URL, como sustituto parcial. `floor` en sí queda como campo numérico opcional vía extracción LLM de la descripción, aceptando que probablemente salga `null` en la mayoría de los anuncios de este portal.

**Por qué:** no existe ninguna clase HTML dedicada a la planta en la ficha de pisos.ad (revisado sobre dos anuncios). La única señal de planta disponible de forma consistente es si el anunciante clasificó el piso como "àtic", que ya está cubierto por la dummy `is_penthouse` del plan. Forzar una columna `floor` a partir solo de menciones ocasionales en texto libre daría una variable con cobertura muy baja y poco fiable.

**Alternativas descartadas:**
- Buscar un patrón de planta en la descripción libre con regex antes de intentar LLM: descartada por ahora, mismo problema de cobertura baja; si el LLM ya procesa la descripción para otros campos, puede intentar este a la vez sin coste adicional relevante.

**Reconsiderar si:** al revisar más anuncios (o al llegar a idealista/fotocasa) aparece un campo de planta estructurado y consistente — en ese caso, evaluar si se puede recuperar `floor` real para el subconjunto de anuncios que lo tengan, aunque sea con cobertura parcial.

---

## 2026-09-15 — Vocabulario de `fitxa__caracteristiques`: terraza y balcón sí son categorías distintas en pisos.ad

**Decisión:** tratar `has_terrace` y `has_balcony` como categorías separadas para pisos.ad (no fusionar en `outdoor_space` por defecto), pendiente de confirmar recuento real en el EDA como ya prevé el plan.

**Por qué:** el formulario de filtros de búsqueda de pisos.ad tiene casillas separadas para "Terrassa" y "Balcó" (`value` distinto para cada una), lo que confirma que el portal las trata como características distintas, no intercambiables. Es razonable esperar que "Balcó" aparezca dentro de `fitxa__caracteristiques` con el mismo mecanismo que "Terrassa" (visto en un anuncio real) cuando el anunciante lo marque, aunque no se ha confirmado todavía sobre un anuncio real con balcón.

**Aviso de metodología que motivó esta decisión:** al buscar la palabra "Balcó" directamente en el HTML de un anuncio (sin balcón real), apareció de todos modos — pero dentro de `<input id="formBalco" class="form-check-input">`, es decir, la casilla del formulario de filtros, no un dato del piso. Sirve de recordatorio: **la presencia de una palabra en el HTML no confirma que sea un dato del anuncio concreto**; hay que verificar la clase/contexto exacto, no solo el texto.

**Reconsiderar si:** en el EDA, el recuento de anuncios con `has_balcony=True` es muy bajo (<~50, umbral que ya usa el plan para terraza) — en ese caso, fusionar con `has_terrace` en `outdoor_space` tal como el plan ya contempla como alternativa.

---

## 2026-09-15 — `parish` no se extrae del texto de la ficha: se asigna desde el bucle de scraping de listados

**Decisión:** el campo `parish` de cada anuncio no se parsea del título ni de ningún texto de la ficha individual. Se asigna directamente durante el recorrido de las páginas de **listado** por parroquia (`.../lloguer/pisos/tots-subtipus/andorra-la-vella`, `.../canillo`, etc.): como el scraper visita cada parroquia por separado para recolectar los `portal_id`, la parroquia ya es conocida en ese momento y se propaga a cada anuncio encontrado en esa página, sin necesidad de volver a deducirla después.

**Por qué:** parsear la parroquia desde el título/texto de la ficha es frágil — puede aparecer con o sin acentos ("Sant Julià de Lòria" vs. variantes sin tilde), con o sin guión ("Escaldes-Engordany"), o abreviada ("Escaldes" en vez de "Escaldes-Engordany", "Andorra" en vez de "Andorra la Vella"), lo que obligaría a normalizar texto y a gestionar ambigüedades. El scraper ya tiene la parroquia disponible sin ambigüedad, porque es un parámetro de su propio bucle de recolección — usar esa fuente es más simple y no puede fallar por variaciones de texto.

**Alternativas descartadas:**
- Función `extraer_parroquia()` que busca en el título cuál de las 7 parroquias oficiales aparece como substring (con normalización de acentos/guiones): descartada por innecesaria, dado que la fuente del bucle de listados es estrictamente mejor y ya estará disponible en el mismo proceso de scraping.

**Nota relacionada:** el núcleo de población más fino (ver decisión de ubicación en pisos.ad, más arriba: `arinsal`, `el-tarter`...) sigue viniendo de la URL de listado cuando esté presente, por el mismo mecanismo — se propaga desde el bucle de recolección, no se parsea de la ficha individual.

---

## 2026-09-15 — Ampliación del esquema LLM: verificación cruzada de las características booleanas (`has_terrace`, `has_balcony`, `has_elevator`, `has_storage`)

**Decisión:** el LLM, además de los campos ya cerrados (`condition`, `construction_year`, `renovation_year`, `expenses_included`, `expenses_detail`, `furnished`, `n_parking_spaces`), también extrae de la descripción libre una versión propia de `has_terrace`, `has_balcony`, `has_elevator` y `has_storage` (booleano o `null` si no se menciona). El valor final de cada característica combina las dos fuentes: `True` si la casilla estructurada de `fitxa__caracteristiques` lo marca **o** si el LLM lo detecta mencionado en el texto libre.

**Por qué:** se detectó un caso real (anuncio `9581`) donde la descripción dice explícitamente "Traster inclós" pero la casilla estructurada de `fitxa__caracteristiques` no lo tenía marcado — es decir, el campo estructurado puede dar **falso negativo** (dice que no hay trastero cuando sí lo hay), no solo dejar el dato vacío. Esto es distinto del caso de `condition`/`construction_year` (donde el campo estructurado simplemente no existe): aquí sí existe un campo estructurado, pero no es fiable al 100%, así que el texto libre puede corregirlo en vez de solo complementarlo.

**Cómo se decidió tratar la discrepancia:** combinar con un OR (estructurado O detectado por LLM), no sustituir uno por el otro. Si el LLM detecta la característica pero la casilla no la marca, se considera que sí existe (el anunciante se olvidó de marcarla, no que la mencione por error) — es más probable omitir una casilla que inventar una característica en el texto de un anuncio real.

**Alternativas descartadas:**
- Aceptar el dato estructurado como definitivo y documentar la limitación sin corregirla: descartada tras decidir que, al ser una característica objetiva y verificable en el texto (a diferencia de las "características cualitativas declaradas" que sí se dejaron pendientes para el EDA), merece la pena el coste de verificarla ahora.
- Confiar solo en el LLM para estas 4 características, ignorando la casilla estructurada: descartada — la casilla sigue siendo la fuente principal (coherente con la regla general del plan "campo estructurado > extracción de texto"), el LLM es solo la corrección de sus falsos negativos.

**Implicación práctica, pendiente de implementar cuando se construya el paso de extracción LLM:** el prompt/esquema de extracción debe pedir estos 4 campos adicionales, y el código de combinación de datos debe aplicar el OR descrito antes de guardar el valor final de cada característica.

---

## 2026-09-18 — Modelo de Ollama para la extracción LLM: `qwen2.5:7b` en vez de `llama3.1:8b`

**Decisión:** usar `qwen2.5:7b` como modelo local de Ollama para la extracción de texto libre, sustituyendo el `llama3.1:8b` que el plan original tenía puesto por defecto.

**Por qué:** la familia Qwen2.5 está particularmente orientada a tareas de extracción estructurada/JSON y a idiomas no ingleses, que es exactamente el caso de uso (rellenar un esquema JSON cerrado a partir de descripciones en catalán/español). Tamaño de descarga similar (~4.7 GB vs ~4.9 GB) y velocidad esperada similar en el M2 del autor, así que el cambio no tiene coste — solo mejor ajuste al problema concreto.

**Alternativas descartadas:**
- `llama3.1:8b` (el original del plan): buena opción general, pero no tan orientada específicamente a fidelidad de esquema JSON como Qwen2.5.
- `mistral:7b`, `gemma2:9b`: descartados por menor fiabilidad siguiendo esquemas JSON estrictos (mistral) o tendencia a añadir texto fuera del JSON (gemma2).
- `llama3.2:3b`: descartado por riesgo de inventar datos en tareas con reglas finas tipo "solo `null` si no aparece explícitamente".

**Reconsiderar si:** al validar sobre la muestra manual de 100 anuncios (paso ya previsto en el plan), la precisión de `qwen2.5:7b` es baja — en ese caso, probar `qwen2.5:14b` antes de plantear alternativas de pago, siguiendo la misma escalera que el plan ya definía.

---

## 2026-09-17 — `property_type` tampoco se extrae del texto: se asigna desde el bucle de scraping, igual que `parish`

**Decisión:** al recorrer pisos.ad, el filtro de listado también permite fijar el subtipo de piso (`pis`, `atic`, `duplex`, `estudi`, `loft`) en la URL. Igual que con `parish`, `property_type` se asigna directamente desde qué combinación de parroquia+subtipo estaba pidiendo el scraper en ese momento, no se parsea del título ni de la descripción.

**Por qué:** mismo motivo que con `parish` — es una fuente sin ambigüedad, ya conocida por el propio bucle, frente a parsear texto libre (que podría no mencionar el subtipo explícitamente, o mencionarlo de forma distinta al vocabulario esperado).

**Slugs confirmados:** `pis`, `atic`, `duplex`, `estudi`, `loft`. Verificados sumando resultados de cada subtipo por separado y comprobando que coinciden con el total de "tots-subtipus" para una parroquia (29+5+0+0+0 = 34, igual al total).

**Implicación para el modelo (fase 1.4):** `is_penthouse` = `property_type == "atic"`, `is_duplex` = `property_type == "duplex"`, `is_studio` = `property_type == "estudi"`. El plan no anticipaba la categoría `"loft"` — queda como categoría propia, sin decidir todavía si se funde con otra o se trata aparte (pendiente de EDA, según cuántos casos haya).

**Nota relacionada:** el scraping cubre solo `/lloguer/pisos/...` (la categoría "pisos" de pisos.ad). El plan pide también scrapear `cases` (chalets/casas) para la composición del parque — pendiente, no cubierto todavía por `pisos_ad.py`.

---

## 2026-09-18 — Flujo de ingesta: no reprocesar anuncios ya conocidos, seguimiento de altas/bajas en una sola tabla

**Decisión:** el scraping de pisos.ad sigue este flujo en cada pasada:
1. Recorrer los listados (parroquia × subtipo × página) y sacar solo las URLs/IDs de anuncios — sin descargar la ficha todavía.
2. Por cada ID encontrado: si **ya existe** en la base de datos, no se descarga ni parsea nada, solo se actualiza `ultima_vez_visto` (y se reactiva si estaba de baja). Si es **nuevo**, se descarga la ficha completa, se parsea, se pasa por el LLM, y se inserta como fila nueva.
3. Al terminar toda la pasada: cualquier anuncio que estaba `activo` en la base de datos pero no ha aparecido en esta pasada se marca `activo = false`, con `fecha_baja` = hoy (se asume alquilado/retirado).

Todo esto vive en **una sola tabla** (`anuncios`), no en una tabla de "capturas históricas" separada — cada anuncio es una fila que se actualiza en el sitio, no se duplica en cada pasada.

**Por qué:** evita volver a descargar/parsear/pasar por el LLM anuncios que no han cambiado, que sería la mayoría en pasadas sucesivas (scraping semanal) — solo los anuncios genuinamente nuevos cuestan tiempo de verdad. Una sola tabla (en vez de un histórico de capturas) es suficiente porque no se pidió llevar seguimiento de cambios de precio a lo largo del tiempo (decisión explícita: no se quiere tracking de subida/bajada de precio del mismo piso, solo altas/bajas de anuncios).

**`dias_en_anuncio` usa `fecha_modificacion` (la señal del propio portal) como referencia, no `primera_captura`:**
- Mientras `activo = true`: `dias_en_anuncio = hoy - fecha_modificacion`
- Cuando se marca de baja: `dias_en_anuncio = fecha_baja - fecha_modificacion` (queda fijo desde ese momento)

`fecha_modificacion` se captura una sola vez (en la primera captura) y no se vuelve a actualizar — es un dato del portal en el momento en que se ve el anuncio por primera vez, no algo que sigamos refrescando. `primera_captura` se mantiene en la tabla solo como registro interno de cuándo el propio scraper empezó a hacer seguimiento de ese anuncio, no se usa para el cálculo de `dias_en_anuncio`.

**Alternativas descartadas:**
- Guardar cada captura como fila nueva en una tabla de histórico: descartada explícitamente — no se necesita ver evolución de precio, solo altas/bajas.
- Comprobar bajas visitando cada URL activa para ver si da 404: descartada — mucho más caro (una petición extra por cada anuncio activo, cada pasada) que comparar contra lo que aparece en los listados de esa misma pasada, que ya se recorren de todos modos.

---

## 2026-09-18 — Verificación cruzada LLM vs. estructurado: discrepancias van a una tabla `avisos`, no a un `print`

**Decisión:** cuando el valor combinado (estructurado OR LLM) de `has_terrace`/`has_balcony`/`has_elevator`/`has_storage` tiene una discrepancia real entre ambas fuentes, se guarda una fila en una tabla `avisos` (portal, portal_id, campo, valor_estructurado, valor_llm, descripción, fecha), consultable con SQL — no solo un `print` por pantalla, que se pierde en el scroll de una ejecución larga.

**Regla de qué cuenta como discrepancia real:** si el LLM devuelve `null` (no tiene información sobre esa característica), **no** se considera discrepancia, aunque el valor estructurado sea `True` o `False` — "no lo sé" no contradice nada. Solo se avisa cuando el LLM SÍ afirma algo (`true` o `false`) y no coincide con el dato estructurado. La primera versión de esta lógica trataba `None` como `False` al comparar, generando avisos falsos en la mayoría de los casos (el LLM no mencionaba una característica, y eso se interpretaba como "el LLM dice que no hay", contradiciendo un estructurado `True` sin ser una contradicción real).

**Por qué:** un aviso "para revisar" solo tiene valor si es fiable — con la lógica original, la mayoría de los ~190 anuncios generaban avisos, haciendo la lista inútil por volumen. Corregido, solo saltan avisos cuando hay una discrepancia genuina entre dos afirmaciones explícitas.

---

## 2026-09-20 — Motor de base de datos: DuckDB en vez de SQLite

**Decisión:** cambiar de SQLite a DuckDB para `data/andorra_housing.duckdb`, manteniendo el resto de la arquitectura igual (misma tabla `anuncios`, mismo flujo de altas/bajas).

**Por qué:** SQLite no tiene tipos de datos reales (`REAL` para todo lo numérico, sin `DATE` ni `BOOLEAN` — se guardan como `TEXT`/`INTEGER` con una convención, no con validación real). DuckDB sigue siendo una base de datos embebida (un archivo, sin servidor que instalar ni mantener corriendo — cero infraestructura añadida, coherente con el "coste 0€" del plan), pero con tipos reales (`DATE`, `BOOLEAN`, `DOUBLE`) y SQL más estándar.

**Diferencias de sintaxis encontradas al migrar** (documentadas también en `aprender.md`):
- Parámetros con nombre: `:nombre` (SQLite) → `$nombre` (DuckDB). Los parámetros posicionales `?` funcionan igual en los dos.
- `PRAGMA table_info(tabla)` funciona en ambos, pero en DuckDB conviene poner el nombre de tabla entre comillas: `PRAGMA table_info('tabla')`.
- `INSERT OR REPLACE` funciona igual en los dos.
- Sin tabla de histórico de capturas (ver decisión del flujo de ingesta), la migración no necesitó ningún script de traspaso de datos — se relanzó el scraping desde cero sobre la base de datos nueva.

**Alternativas descartadas:**
- MySQL / PostgreSQL: ambos requieren un servidor de base de datos instalado y corriendo en segundo plano (gestión de usuario/contraseña, proceso persistente), lo cual va contra el "coste 0€, sin piezas extra" del plan — desproporcionado para las necesidades del proyecto.
- Quedarse en SQLite: descartado porque los tipos "de mentira" dificultaban trabajar con fechas/booleanos con la confianza de que el dato realmente es lo que dice ser.

---

## 2026-09-20 — Dos reglas de limpieza/validación pendientes para el EDA

Dos comprobaciones de coherencia identificadas durante el scraping, que no se resuelven ahora (no bloquean el pipeline) pero quedan anotadas para aplicarse en la fase de EDA/limpieza:

**1. Coherencia `price` / `area_m2` / `price_m2`:** comprobar que `price ≈ price_m2 × area_m2` (redondeado, con margen de tolerancia por el redondeo que ya aplica el propio portal a `price_m2`). Sirve como validación cruzada de que estos tres campos numéricos se extrajeron bien — si `price_m2` viene de una fuente y `price`/`area_m2` de otra, deberían ser consistentes entre sí.
```sql
-- price_calculado = ROUND(price_m2 * area_m2); revisar filas donde |price - price_calculado| sea grande
```

**2. Coherencia `expenses_included` / `expenses_detail`:** el LLM a veces devuelve `expenses_included = "no"` (o `"todo"`/`"parcial"`) sin que el texto original mencione nada sobre gastos — un caso de alucinación que la calibración del prompt (ejemplos añadidos) no ha eliminado del todo. Como el prompt pide describir en `expenses_detail` el gasto concreto que motiva la categoría, si `expenses_included` tiene valor pero `expenses_detail` está vacío, es una señal fiable de que la categoría no tiene respaldo real en el texto:
```sql
SELECT portal_id, expenses_included, expenses_detail, descripcion_raw
FROM anuncios
WHERE expenses_included IS NOT NULL AND (expenses_detail IS NULL OR expenses_detail = '')
```

**Por qué se dejan para el EDA y no se arreglan ahora:** ambas son revisiones que se aplican mejor sobre el dataset ya completo (para ver cuántos casos hay de verdad, no solo suposiciones), y no bloquean que el scraping siga avanzando — corregirlas ahora, caso a caso, sería prematuro sin saber la escala real del problema.

---

## 2026-09-20 — `descargar_html` reintenta automáticamente ante fallos de red transitorios

**Decisión:** `descargar_html` reintenta hasta 3 veces (con 5s de espera entre intentos) cuando falla por `ConnectionError` (DNS, conexión rechazada/cortada) o `Timeout` (el servidor no responde a tiempo). Un error HTTP real del servidor (404, 500 — capturado por `raise_for_status()`) sigue sin reintentarse, para en seco como antes.

**Por qué:** durante la primera ejecución completa del scraping (~7 parroquias × 5 subtipos, más de 100 anuncios nuevos, ~2h de duración), el proceso se cayó **dos veces** por fallos de red puramente transitorios (una `NameResolutionError` al resolver `pisos.ad`, y un `ReadTimeout` del servidor) — ninguno de los dos tenía que ver con el contenido de la petición ni con el servidor rechazando la conexión de forma permanente. Sin reintento, un corte de wifi de un segundo tira una ejecución de horas entera, aunque todo lo ya procesado se mantenga guardado (se guarda anuncio a anuncio, no al final).

**Por qué NO reintentar ante errores HTTP:** un 404/500 es una respuesta real del servidor, no un problema de red — reintentarlo no cambiaría el resultado y podría interpretarse como forzar peticiones contra la voluntad del portal (mala práctica de scraping, contraria a la higiene que ya fija el plan).

**Reconsiderar si:** los cortes de red siguen siendo frecuentes incluso con el reintento — en ese caso, subir el número de intentos o el tiempo de espera entre ellos, o investigar si el corte viene del propio equipo/red del autor (wifi inestable) más que del servidor de pisos.ad.

---

## 2026-09-21 — Revisión manual de `avisos`: por qué la mayoría NO son alucinaciones, y cómo se registra el veredicto

**Hallazgo, sobre los primeros ~100 avisos generados por el scraping completo de pisos.ad:** agrupando por `campo`, el patrón está muy concentrado en una sola dirección — `has_terrace` (46 casos), `has_storage` (40) y `has_elevator` (2) son **siempre** "estructurado = No, LLM = Sí" (el LLM detecta la característica en el texto libre, pero la casilla de `fitxa__caracteristiques` no estaba marcada). Solo `has_balcony` tiene además 3 casos en la dirección contraria (estructurado = Sí, LLM = No).

**Interpretación:** la dirección dominante (casilla no marcada, texto sí lo menciona) **no es una alucinación del LLM** — es el mismo patrón que motivó construir la verificación cruzada desde el principio (el caso real de "Traster inclós" en la descripción sin la casilla marcada, visto en la fase de scraping). Refleja que los anunciantes no siempre rellenan las casillas con cuidado, pero sí lo escriben en el texto. El OR ya deja el valor final correcto (`True`) en `anuncios` para estos casos — no requieren corrección manual caso a caso. La dirección contraria (casilla marcada, LLM dice que no) sí es más sospechosa de ser un error real (de cualquiera de las dos fuentes) y merece revisión manual — pero **no se puede descartar a ciegas ninguna de las dos direcciones sin leer el texto**, la lectura manual es la única forma de confirmarlo con certeza.

**Decisión sobre cómo registrar la revisión manual:** se añade una columna `veredicto` (texto libre, ej. `"correcto"`/`"alucinacion"`) a la tabla `avisos` (con `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`, para que se pueda añadir de forma segura cada vez que se conecta). El bucle de revisión:
- Filtra por `portal` (para poder revisar pisos.ad, idealista y fotocasa por separado cuando lleguen).
- Solo trae los avisos que aún no tienen `veredicto` (`WHERE veredicto IS NULL`), así se puede interrumpir y continuar en otra sesión sin repetir revisión.
- Guarda el veredicto de cada caso **justo después de responder**, no en una lista en memoria para guardar todo al final — si la revisión se corta a mitad (con ~100 casos es fácil que pase), lo ya revisado no se pierde.

**Alternativas descartadas:**
- Asumir automáticamente que toda discrepancia "estructurado=No, LLM=Sí" es correcta sin revisión manual: descartada — aunque el patrón agregado apunta a eso, confirmarlo caso a caso da certeza real en vez de una suposición basada en el agregado, y permite detectar excepciones dentro del patrón dominante.
- Guardar los veredictos solo en un DataFrame de Python, no en la base de datos: descartada por la misma razón de robustez que ya aplicamos al scraping (no perder progreso ante una interrupción).

---

## 2026-09-22 — Conclusión de la revisión manual de `avisos`: regla de confianza por dirección de la discrepancia

**Decisión, tras revisar a mano los ~100 avisos generados por pisos.ad:** confirmado el patrón que se sospechaba en la entrada anterior, sin excepciones relevantes:
- **Estructurado = No, LLM = Sí** → el LLM tiene razón siempre. La casilla no estaba marcada, pero el texto libre sí menciona la característica. El OR ya deja esto bien en `anuncios`, sin más acción.
- **Estructurado = Sí, LLM = No** → el LLM alucina, la casilla tiene razón. En estos casos el LLM afirmó explícitamente la ausencia de una característica que el texto no mencionaba en absoluto (o mencionaba lo contrario), y la casilla estructurada resultó ser la fuente fiable.

**Implicación práctica para el futuro** (no implementada todavía, anotada para cuando se automatice más): en caso de discrepancia, se puede confiar en el LLM cuando dice que SÍ hay una característica, y desconfiar de él cuando dice que NO hay una que el estructurado afirma — es decir, el OR que ya aplicábamos (quedarse con `True` si cualquiera de las dos fuentes lo dice) queda validado como la regla correcta con los datos reales, no solo como supuesto de diseño.

---

## 2026-09-22 — Duplicados dentro del mismo portal: detección por hash de descripción, antes del paso LLM

**Hallazgo:** durante la revisión manual de avisos, se detectó que los anuncios `9209` y `9305` son el **mismo piso** publicado dos veces en pisos.ad (misma descripción, misma URL de fondo) — un duplicado dentro del propio portal, no entre portales distintos (ese caso ya estaba previsto en el plan para más adelante, pero este es distinto: ni siquiera hemos llegado a idealista/fotocasa y ya hay duplicados). Comprobando `hash_descripcion` sobre los 115 anuncios que ya lo tenían calculado, aparecieron **3 pares duplicados** en total (`8775/9545`, `9209/9305`, `9637/8646`) — más de los que se habían detectado a ojo.

**Por qué se necesita calcular el hash ANTES del paso LLM, no después (como se hace ahora):** actualmente `hash_descripcion` solo se rellena dentro de `guardar_extraccion_llm`, es decir, solo si la descripción se procesó con éxito por el LLM. De los 126 anuncios guardados, 11 no tienen `hash_descripcion` (fallos de LLM o sin descripción) — esos 11 no se pueden comprobar contra duplicados con el método actual. Calculando el hash en el momento de parsear la ficha (antes de decidir si se llama al LLM), todos los anuncios quedan cubiertos por la comprobación de duplicados, sin excepción.

**Decisión de diseño para la próxima vez que se toque el pipeline de scraping** (pendiente de implementar, no se ejecuta todavía):
1. Al parsear una ficha nueva, calcular `hash_descripcion` inmediatamente, antes de llamar al LLM.
2. Comparar ese hash contra los ya guardados en `anuncios`. Si ya existe → es un duplicado: no se guarda como anuncio nuevo, no se llama al LLM para él (ya sería trabajo repetido para un piso que ya tenemos).
3. En su lugar, se guarda una fila en una tabla nueva, `repetidos`: `url`, `portal_id` (el del duplicado encontrado), y qué `portal_id` es el que **sí** quedó guardado en `anuncios` (el original) — para poder auditar después cuántos duplicados hubo y cuáles eran.

**Alternativas descartadas:**
- Seguir calculando el hash solo tras el éxito del LLM: descartada — deja huecos de cobertura (los fallos de LLM nunca se comprueban contra duplicados), como ya se ha visto con los 11 casos sin hash.
- No guardar constancia de los duplicados encontrados (simplemente descartarlos en silencio): descartada — se pierde la trazabilidad de cuántos duplicados había y cuáles eran, útil para auditar la calidad del dataset final.

**Implementado el mismo día** (puntos 1-3 de arriba, en `pisos_ad.py`/`almacenamiento.py`):
- `procesar()` calcula `hash_descripcion` justo después de sacar la descripción, antes de decidir nada más.
- `guardar_ficha()` ya guarda `hash_descripcion` al insertar (columna añadida al `INSERT`) — `guardar_extraccion_llm()` ya no la toca, porque ya está puesta desde el principio.
- Tabla nueva `repetidos` (`portal`, `portal_id`, `url`, `portal_id_original`, `fecha`), con `guardar_repetido()` para registrar cada duplicado detectado.
- `reintentar_fallos()` también revisado: al reintentar un fallo antiguo (de los 11 sin hash), calcula el hash, comprueba si resulta ser un duplicado tardío (`portal_id_original`) y, si no lo es, rellena `hash_descripcion` con `actualizar_hash_descripcion()` — así los 11 casos antiguos quedan cubiertos la próxima vez que se reintenten, sin necesitar un script de migración aparte.

---

## 2026-09-25 — Dos correcciones más sobre la extracción LLM: prompt (condition/furnished) y reintento ante cortes de Ollama

**Corrección del prompt — el modelo confundía `condition` con `furnished`:** en varios fallos de `fallos_llm`, el modelo devolvía `"condition": "amueblado"` (copiando el valor de `furnished` también ahí) o, tras una primera corrección que nombraba explícitamente el campo `"furnished"` en la aclaración, empezó a devolver literalmente `"condition": "furnished"` — el modelo se quedó con esa palabra de la propia instrucción y la usó como valor. Arreglo final: la aclaración ya no nombra el otro campo por su nombre en inglés, ni muestra un ejemplo con las dos claves juntas (ni siquiera marcado como "MAL") — solo describe en prosa que son dos preguntas distintas, sin darle al modelo ningún token literal que pueda copiar por error.

**Lección general:** al corregir un prompt por un error de un modelo, cuidado con **introducir la propia palabra del error** en la aclaración — el modelo puede quedarse con esa palabra y repetirla en el sitio equivocado, en vez de entender la regla. Mejor describir la distinción sin nombrar directamente el campo/valor problemático, y evitar poner ejemplos "de lo que NO hay que hacer" con el formato exacto del error (aunque estén marcados como incorrectos).

**`extraer_de_descripcion` reintenta ante cortes con Ollama** (mismo patrón que `descargar_html` con pisos.ad): durante un reintento de `fallos_llm`, la petición a Ollama (`localhost:11434`) dio un `ReadTimeout` a los 60s, con el servidor y el modelo confirmados como activos justo después — un corte transitorio (posible recarga del modelo en memoria), no un problema de la descripción. Se añaden hasta 3 reintentos con 5s de espera, igual que en `descargar_html`.

---

## 2026-09-25 — Investigación: modelo de decisión "Kev" (alternativa open-source a Jev) para la extracción categórica — descartado por ahora

**Contexto:** tras la tercera vuelta de ajuste de prompt para el mismo bug (`condition` confundido con `furnished`), se investigó si un modelo de decisión tipo Jev/Kev (que responde preguntas tipadas con probabilidades calibradas, en un único forward pass, en vez de generar texto libre) resolvería el problema de raíz al hacer estructuralmente imposible que el modelo devuelva un valor fuera del esquema.

**Cómo funciona Kev (`jaredpalmer/kev`, Apache-2.0, familia de modelos sobre Qwen3.5/3.8, 0.8B/4B/9B/27B):** se le pasa un texto (`state`) y un diccionario de preguntas tipadas (`noul` = sí/no, `choice` = opción cerrada, `score` = nivel ordenado) en una sola petición HTTP (`POST /v1/systemone`); el modelo procesa el texto una vez y responde todas las preguntas en paralelo con probabilidades calibradas, sin generación autoregresiva. No hay tipo de pregunta para números libres ni texto libre.

**Por qué se descarta por ahora, a pesar de encajar conceptualmente:**
1. **Esquema partido en dos:** de nuestros 7 campos LLM, solo `condition`, `furnished`, `expenses_included` y los 4 `has_X_llm` encajan como preguntas `choice`/`noul`. `construction_year`, `renovation_year`, `n_parking_spaces` (números) y `expenses_detail` (texto libre) no tienen tipo de pregunta en Kev — seguiríamos necesitando un LLM generativo (Ollama) en paralelo para esos campos. Es decir, no sustituye la extracción actual, la duplica en dos servidores distintos.
2. **Dominio de entrenamiento no coincide:** el dataset de entrenamiento (`decision-v7`) es de datasets públicos en inglés (routing de tickets, entailment, preguntas de ciencia) — nada en catalán/español, nada de dominio inmobiliario. El propio README recomienda un fine-tune corto cuando el idioma o las preguntas son distintas a las de entrenamiento, que es exactamente nuestro caso.
3. **Hardware local insuficiente para la versión con precisión decente:** el Mac de desarrollo tiene 16 GB RAM (Apple M2). Kev-4B (accuracy ~0.82 en "new sources", el escenario más parecido al nuestro) necesita 32 GB. Solo cabría Kev-0.8B, con accuracy notablemente peor (~0.65-0.70 en "new sources") — justo el escenario donde más nos jugamos la precisión, porque nuestro dominio es "nuevo" para el modelo.
4. **Coste de infraestructura no proporcional al problema:** añadir un segundo servidor local (entorno Python 3.12/3.13 vía `uv`, `torch`, `peft`, `transformers`, MLX — el proyecto usa Python 3.14, no compatible con `torch` todavía) para resolver un bug que la limpieza defensiva en post-procesado (ver decisión de la misma fecha, más abajo) ya resuelve con cero dependencias nuevas.

**Alternativas descartadas:** ninguna otra investigada en profundidad — Kev fue la única opción concreta evaluada, precisamente porque encajaba mejor que cualquier otra en la lógica del problema (respuestas restringidas a un esquema cerrado).

**Reconsiderar si:** el proyecto crece a más portales (idealista, fotocasa) con volumen suficiente para justificar un fine-tune de Kev usando como datos de entrenamiento los ejemplos ya revisados manualmente en `avisos.veredicto` (que ya son, de facto, un pequeño dataset etiquetado); o si la limpieza defensiva en post-procesado no basta para otros campos categóricos que aparezcan más adelante.

---

## 2026-09-25 — Corrección definitiva de `condition`/`furnished`: limpieza defensiva en post-procesado, no más prompt engineering

**Problema:** tras tres rondas de ajustes de prompt (ver decisión anterior de la misma fecha), el modelo seguía devolviendo `"condition": "amueblado"` para descripciones que mencionan mobiliario — un sesgo persistente del modelo de 7B que el prompt no consigue eliminar de forma fiable, con retornos decrecientes en cada intento.

**Decisión:** en vez de seguir puliendo el prompt, se añade una limpieza defensiva **antes** de validar con Pydantic: si `datos["condition"]` llega con uno de los valores que sabemos que son intrusiones del campo `furnished` (`"amueblado"`, `"semi"`, `"vacio"`, `"furnished"`, `"sin muebles"`), se fuerza a `None` en vez de dejar que la validación de Pydantic rechace la extracción entera. Así no se pierden los demás campos (que sí suelen venir bien) solo porque `condition` vino mal, y se deja de depender de que el modelo obedezca perfectamente una instrucción negativa.

**Por qué no es lo mismo que "confiar menos en el dato":** los valores que se limpian nunca eran válidos para `condition` (no están en el `Literal` del esquema) — antes esos casos acababan en `fallos_llm` sin ningún valor aprovechable; ahora se recupera el resto de la extracción y `condition` queda como `null`, que es semánticamente correcto (el modelo no dio ninguna pista válida sobre el estado físico de la vivienda en ese intento).

**Alternativas descartadas:**
- Cuarta ronda de ajuste de prompt: descartada por los retornos decrecientes ya observados en las tres rondas anteriores.
- Migrar a un modelo de decisión tipo Kev: descartado por ahora (ver decisión anterior).
