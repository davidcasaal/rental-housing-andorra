# Andorra Housing Index

Modelo hedónico de precios de alquiler en Andorra, replicado en ciudades europeas comparables, para estimar cuánto cuesta una vivienda equivalente en cada mercado y cuánta renta residual le queda a un trabajador tras pagarla.

## Contexto del autor

Graduado en Estadística (Universitat de Barcelona). Cómodo con Python, XGBoost, PyTorch, SQL, Optuna, econometría y modelos de series temporales. **Sin experiencia previa en web scraping ni en montar APIs** — explicar esa parte con más detalle del habitual. Mac con chip M2, VS Code, terminal.

Proyecto de portfolio para búsqueda de empleo en ML/Data Science. Dos objetivos simultáneos: demostrar rigor técnico ante reclutadores y generar un resultado con interés mediático.

## Restricciones

- **Coste total: 0 €.** Solo herramientas gratuitas, sin excepciones. La extracción con LLM se hace con **Ollama en local** (ya instalado en la máquina del autor; es software libre, no requiere cuenta, suscripción ni API key).
- Todo el código en Python. Repo público en GitHub.
- Código y commits en inglés. Documentación e informes en español o catalán.
- **No usar deep learning**: el volumen (~2.000 anuncios en Andorra) no lo justifica y XGBoost es la elección defendible.
- **Alcance del modelo: solo pisos.** Ver sección "Alcance tipológico".

## Stack

| Necesidad | Herramienta |
|---|---|
| HTTP | `requests` |
| Parsing HTML | `BeautifulSoup` |
| Webs con JS | `Playwright` (solo si `requests` devuelve vacío) |
| Almacenamiento | SQLite + Parquet |
| Geocodificación | Nominatim (OSM), límite 1 req/s |
| POIs | Overpass API (OSM) |
| Extracción de texto | **Ollama en local** (ya instalado). Validación con `pydantic` |
| Modelado | `statsmodels`, `scikit-learn`, `xgboost`, `pygam`, `shap` |
| Geoespacial | `geopandas`, `folium` |
| Scheduling | GitHub Actions (cron semanal) |
| Dashboard (fase 3) | Streamlit |

No se necesita montar ninguna API en las fases 1 y 2.

## Estructura del repositorio

```
config/
  parish_centers.yaml   # lat/lon del centro urbano de cada parroquia
  andorra.yaml          # portal, selectores, mapeo de campos
  zurich.yaml           # un YAML por ciudad en fase 2
data/
  raw/                  # HTML cacheado + volcados sin procesar
  interim/              # tras parseo, antes de deduplicar
  processed/            # dataset final modelable
src/
  scraping/
    base_scraper.py     # lógica común, rate limiting, caché
    parsers/            # un parser por portal
  features/
    geo.py              # derivadas geoespaciales
    llm_extraction.py   # enriquecimiento desde texto libre
  dedup/
  models/               # baseline, lineal, gam, xgboost, jerárquico
  eval/                 # validación temporal y espacial
notebooks/
reports/
DECISIONS.md            # log de decisiones metodológicas con fecha
```

---

# FASE 1 — Modelo hedónico de Andorra (semanas 1-8)

## Alcance tipológico: solo pisos

**Regla:** el modelo se restringe a pisos, incluyendo áticos y dúplex (son pisos con particularidades, comparten portal, comunidad, ascensor y estructura de precio → se tratan como dummies `is_penthouse`, `is_duplex`).

**Excluidos del modelo:** casas, chalets, bordas, masías.

Justificación: la homogeneidad del producto es un requisito del método hedónico, no una comodidad. Un chalet y un piso no comparten la misma función de precio (parcela, privacidad y vistas vs. planta, ascensor y comunidad). Mezclarlos produce una elasticidad de `log(area_m2)` que es una media de dos estructuras distintas y no describe bien ninguna.

**Dos decisiones a cerrar tras el EDA (paso 1.2), no antes:**
- **Estudios**: si hay <40 casos, excluirlos y subir el perfil "estudiante" de la fase 2 a 50-55 m². Si hay más, incluirlos.
- **Chalets/casas**: si resultan ser >200 (y no ~20 como se espera), reconsiderar: dos modelos separados comparando elasticidades sería un hallazgo interesante.

**Importante: scrapear TODAS las tipologías igualmente.** Filtrar es gratis; volver a scrapear no. Además, poder afirmar en el informe "el X% del parque andorrano son pisos, por eso restrinjo el análisis" justifica la exclusión con evidencia — y el dato de composición del parque es un resultado en sí mismo.

## 1.1 Scraping y dataset

### Portales, en este orden

| Portal | Volumen | Dificultad | Notas |
|---|---|---|---|
| **pisos.ad** | ~2.000 | Baja-media | Empezar aquí. Publica informes trimestrales agregados que sirven de validación externa |
| **idealista.com** (andorra-provincia) | ~1.700 | Alta (antibots) | Estructura limpia si se consigue acceso |
| **fotocasa.es** | ~1.000 | Media | Triangulación y detección de duplicados |
| Agencias locales | Bajo | Baja | Solo si hace falta cubrir Escaldes-Engordany |

Regla: no pasar al siguiente portal hasta que el anterior funcione de punta a punta y persista datos en disco.

### Higiene de scraping (obligatoria)

- Revisar `robots.txt` de cada portal antes de empezar
- Delay aleatorizado de 2-5 s entre peticiones
- User-agent identificable
- Cachear el HTML descargado en `data/raw/` para no repetir peticiones al depurar
- Si un portal bloquea, no forzar: cambiar de portal
- No publicar datos personales de anunciantes en el repo

### Variables directas del anuncio

| Variable | Tipo | Notas |
|---|---|---|
| `price` | num | Excluir "consultar precio" |
| `area_m2` | num | **Registrar si es útil o construida** — crítico para fase 2 |
| `parish` | cat (7) | A veces hay que inferirla de la dirección |
| `rooms`, `bathrooms` | num | |
| `property_type` | cat | Para filtrar; dentro de pisos: `is_penthouse`, `is_duplex`, `is_studio` |
| `floor` | num | "bajo" y "ático" como categorías propias |
| `has_elevator`, `has_storage` | bool | |
| `is_furnished` | cat | `amueblado` / `semi` / `vacio`. Campo estructurado primero; LLM solo como fallback |
| `parking` | cat | incluido / opcional con sobrecoste / no |
| `has_terrace` | bool | **No excluyente con balcón** |
| `has_balcony` | bool | Ver nota abajo |
| `published_date` | date | Si falta, usar fecha de primera captura |
| `url`, `portal_id` | str | Imprescindible para deduplicar y seguir el anuncio |

**Nota sobre terraza/balcón:** separadas por defecto, pero **verificar recuento en el EDA antes de fijarlo**. Regla: si ambas superan ~50 observaciones, separadas; si no, fusionar en `outdoor_space`. Muchos anuncios usan los términos indistintamente y algunos indican ambos — no son excluyentes en el parser.

### Variables derivadas

| Variable | Cómo |
|---|---|
| `dist_parish_center` | Distancia geodésica al centro de la parroquia, definido en `config/parish_centers.yaml` |
| `dist_escaldes` | Distancia a l'Illa Carlemany (Escaldes-Engordany) — centro comercial y de actividad real del país |
| `dist_ski_resort` | Coordenadas de Grandvalira y Vallnord |
| `services_500m` | Overpass API: supermercados, transporte, escuelas |
| `days_listed` | `capture_date - published_date`. Control importante: anuncios antiguos suelen estar sobrevalorados |

**Centros de parroquia:** fijar a mano en `config/parish_centers.yaml`. Criterio: **no** el centroide geográfico (en Canillo u Ordino cae en montaña), sino el **centro urbano funcional** — casa comuna o plaza principal del núcleo. Documentar el criterio en `DECISIONS.md`: afecta a todos los coeficientes de distancia.

**Colinealidad a vigilar:** `dist_parish_center` y `dist_escaldes` estarán muy correlacionadas en las parroquias centrales (en Escaldes son casi lo mismo). Revisar VIF. Si da problemas: usar `dist_parish_center` para todas y `dist_escaldes` solo interactuada con las parroquias periféricas.

**Descartadas explícitamente:** altitud (la parroquia ya absorbe la variación altitudinal), distancia a frontera (casi perfectamente correlacionada con parroquia en un país de 25 km; el caso de Pas de la Casa ya lo captura la dummy de Encamp).

### Extracción con LLM desde texto libre

**Regla general del enriquecimiento: campo estructurado > extracción de texto.** El LLM solo entra donde el portal no da el dato.

El año de construcción y el estado de reforma **no están en datos públicos andorranos** (SICAR y estadistica.ad publican solo agregados), así que el texto libre es la única fuente.

**Posición en el pipeline:** después del parseo HTML, antes de la deduplicación.

```
scraping → parseo HTML → [descripción en texto libre]
                              ↓
                      extracción LLM → columnas estructuradas
                              ↓
                      deduplicación → dataset final
```

**Esquema de salida (cerrado, 5 campos):**

```
- condition: "nuevo" | "reformado" | "buen_estado" | "a_reformar" | null
- construction_year: entero | null
- renovation_year: entero | null
- expenses_included: "todo" | "parcial" | "no" | null
- expenses_detail: texto breve | null
- furnished: "amueblado" | "semi" | "vacio" | null   # solo fallback
```

`expenses_included` importa más de lo que parece: un alquiler de 1.800 € con comunidad y calefacción incluidas no es comparable a uno de 1.800 € sin ellas, y en Andorra la calefacción es un coste real. Sin controlarlo, esa diferencia va a los residuos.

`expenses_detail` se recoge como texto libre en la primera pasada (sin modelar) para revisar a mano qué patrones aparecen — comunidad, agua, calefacción, internet — y decidir después si convertirlo en dummies separadas.

**Mecánica de implementación:**

1. **Lotes de 10-20 descripciones por llamada.** Con ~2.000 anuncios son ~130 llamadas.
2. **Prompt con esquema fijo y regla de `null` explícita:** *"si el dato NO aparece explícitamente, devuelve null; no infieras ni supongas"*. Sin esta regla el modelo rellena huecos con lo plausible y contamina el dataset con datos inventados indistinguibles de los reales.
3. **Validación de salida con Pydantic.** Si el JSON no valida o un enum sale fuera de rango: reintentar esa descripción o marcarla como fallida. Nunca aceptar la salida cruda.
4. **Cacheo por hash de la descripción** en SQLite (`hash(texto) → JSON`). Al reejecutar el pipeline solo se procesan descripciones nuevas.
5. **Validación manual sobre muestra de 100 anuncios**: extraer a mano, comparar contra el LLM, **reportar precisión por campo en el informe**. Este paso es lo que convierte "usé un LLM" en trabajo defendible — es exactamente la pregunta de entrevista.
6. **Baseline de regex/keywords** para los mismos campos. Comparar "regex vs. LLM" en la tabla de precisión es un mini-experimento que demuestra que el LLM se usó por ser mejor, no por defecto.

**Runtime: Ollama en local.** Ya está instalado en la máquina. No requiere cuenta, suscripción ni API key: el modelo se descarga una vez y se ejecuta en el propio Mac.

```bash
ollama pull llama3.1:8b     # ~5 GB, una sola vez
ollama serve                # servidor local en localhost:11434
```

Desde Python es una API HTTP normal:

```python
import requests

r = requests.post("http://localhost:11434/api/generate", json={
    "model": "llama3.1:8b",
    "prompt": prompt,
    "format": "json",      # fuerza salida JSON parseable
    "stream": False
})
```

`format: "json"` es importante: obliga al modelo a devolver JSON válido y reduce mucho los fallos de validación Pydantic.

Notas prácticas: el M2 mueve bien modelos de 7-8B. La velocidad ronda unos pocos segundos por lote, así que las ~130 llamadas se resuelven en minutos, no horas. Si la calidad de extracción es baja con 8B, probar `qwen2.5:14b` antes de plantearse alternativas de pago. **Ejecutar el paso de extracción una sola vez y cachear** (ver punto 4) para no repetir inferencia al reejecutar el pipeline.

**Manejo de nulos:** crear indicador `condition_unknown` como categoría propia. No imputar silenciosamente. Si se imputa, documentar el método y verificar que no altera los coeficientes principales.

**Proxies gratuitas de gama:** `n_photos` y `description_length`, sorprendentemente predictivas.

### Deduplicación (reservar 1 semana completa)

El mismo piso aparece en 2-3 portales. Sin deduplicar, el modelo sobrepondera los inmuebles más anunciados.

Estrategia: bloqueo por `(parish, rooms)` → dentro del bloque, comparar `area_m2` (±5%), `price` (±5%) y similitud textual de descripción (TF-IDF + coseno). Umbral calibrado revisando a mano una muestra.

## 1.2 EDA

- Nulos, outliers, correlaciones, VIF
- **Distribución de `price` vs `log(price)`** — el gráfico que justifica la transformación
- **Recuento por parroquia y tipología** — si una parroquia tiene <30 anuncios, su coeficiente no será fiable. **Condiciona la especificación del modelo: hacerlo antes de especificarlo**
- **Recuentos que cierran decisiones pendientes:** estudios, chalets, terraza vs. balcón
- Composición del parque por tipología (dato publicable en sí mismo, justifica la restricción a pisos)
- Boxplots de €/m² por parroquia
- Distribución temporal de capturas (determina si caben dummies mensuales o solo trimestrales)
- Mapa de calor de precios con coordenadas geocodificadas (`folium`)
- **Validación externa: comparar €/m² por parroquia contra SICAR y contra los informes de pisos.ad.** Documentar la brecha
- Precisión de la extracción LLM por campo

Outliers: distinguir errores evidentes (5 m², precio de 1 €) de extremos legítimos. Eliminar los primeros, conservar los segundos y controlarlos con el logaritmo.

## 1.3 Modelos (escalera, en este orden)

**M0 — Baseline.** Mediana de €/m² por parroquia. Guardar MAE/RMSE como referencia.

**M1 — Regresión log-lineal.**
```
log(price) ~ log(area_m2) + rooms + bathrooms + floor + has_elevator
           + parking + is_furnished + has_terrace + has_balcony
           + is_penthouse + is_duplex + condition + expenses_included
           + parish + dist_parish_center + dist_escaldes
           + dist_ski_resort + services_500m
           + days_listed + quarter
```
- `log(price)` obligatorio: distribución sesgada a la derecha, efectos multiplicativos. Un coeficiente de 0.08 se lee como "+8%", comparable entre segmentos.
- `log(area_m2)` da la elasticidad directamente.
- `parish` como dummy → prima de ubicación por parroquia.
- Dummies temporales → subproducto: índice hedónico de precios de Andorra.

**M2 — Interacciones.** Añadir **solo `parish × log(area_m2)`** inicialmente. Cada interacción con parroquia multiplica los parámetros por 7; con ~1.500 observaciones el resto sería ruido. Decidir con test F anidado o AIC/BIC, no a ojo.

Atajo metodológico: usar SHAP interaction values del XGBoost para detectar qué interacciones existen, y añadir a la lineal solo las que el bosque señale.

**M3 — GAM (opcional, alto valor diferencial).** Curvas no lineales interpretables para `dist_parish_center` y `dist_escaldes`.

**M4 — XGBoost.** Máxima precisión, necesaria para la fase 2. Optuna para hiperparámetros.

### Validación (crítico)

- **Split temporal**: entrenar con capturas antiguas, validar con recientes. **No aleatorio.**
- **Split espacial**: dejar fuera una parroquia y comprobar generalización
- CV solo dentro del bloque temporal de entrenamiento
- Métricas: MAE, RMSE, MAPE, R² — reportar las cuatro en tabla comparativa

## 1.4 Diagnóstico e insights

Diagnóstico econométrico de M1/M2:
- VIF (`area_m2`, `rooms` y `bathrooms` muy correlacionadas; también las dos distancias)
- **Errores estándar robustos** (heterocedasticidad casi garantizada)
- Residuos: normalidad, y **patrones espaciales** — si los residuos se agrupan geográficamente, falta una variable de ubicación
- Breusch-Pagan, RESET de Ramsey

Entregables:
1. Tabla de coeficientes con IC 95%, interpretados en %
2. Mapa de primas por parroquia
3. Elasticidad de la superficie
4. SHAP global y local
5. **Contraste lineal vs. SHAP**: efecto medio de la lineal frente al efecto heterogéneo que revela SHAP por parroquia
6. Índice hedónico temporal (si hay suficientes semanas de captura)
7. Efecto estacional de `dist_ski_resort`
8. Tabla de precisión de la extracción LLM vs. baseline regex

**Punto de corte seguro:** al final de la fase 1 ya existe un proyecto completo y publicable. Publicar aquí (GitHub + LinkedIn, tono técnico) antes de empezar la fase 2.

---

# FASE 2 — Comparación internacional (semanas 9-15)

## 2.0 Selección de ciudades

**Cuatro para empezar, seis como máximo.** Cada ciudad es un scraper nuevo con su portal y sus antibots.

| Ciudad | Grupo | Portal |
|---|---|---|
| Barcelona | Contraste | idealista / fotocasa |
| Zúrich | Comparable estructural | homegate.ch / immoscout24.ch |
| Luxemburgo | Comparable estructural | athome.lu |
| Múnich o Berlín | Contraste europeo | immobilienscout24.de |

Segunda tanda si el pipeline funciona: París, Estocolmo, Lisboa, Ginebra. **Descartar Mónaco**: mercado opaco, muy pocos anuncios públicos, resultado anecdótico.

Justificación a documentar: el grupo "comparables estructurales" responde a *¿es Andorra cara para lo que es?*; el grupo "contraste" responde a *¿es cara para lo que gana la gente?*

## 2.1 Pipeline multiciudad

**El entregable no son cuatro scrapers, es un pipeline parametrizable**: añadir una ciudad debe ser crear un YAML en `config/`, no escribir código nuevo. Este es el punto con más peso de cara a perfiles de ML Engineering.

### Conjunto mínimo común de variables (restricción innegociable)

Si el modelo de Zúrich usa año de construcción y el de Andorra no, los precios predichos **no son comparables** y toda la fase 2 queda invalidada.

Conjunto común: `price, area_m2, rooms, bathrooms, floor, has_elevator, parking, is_furnished, has_terrace, has_balcony, dist_center_percentile, city, quarter`.

**Restricción tipológica también aquí: solo pisos.** El piso urbano es la unidad comparable entre mercados; el chalet andorrano no tiene equivalente claro en Berlín.

### Normalizaciones obligatorias

- **`dist_center_percentile`**: la distancia al centro debe convertirse a percentil **dentro de cada ciudad**. "Céntrico" en Andorra la Vella son 800 m; en Berlín son 5 km.
- **Superficie útil vs. construida**: varía por país
- **Moneda**: CHF → EUR con tipo de cambio de la fecha de captura
- **Definición de habitación**: en Suiza el conteo incluye el salón. Un anuncio de "3.5 Zimmer" **no** son 3 dormitorios. No normalizar esto rompe toda la comparación con Zúrich.
- **Gastos incluidos**: en Alemania la distinción *Kaltmiete* / *Warmmiete* es sistemática y grande. Homogeneizar a precio sin gastos o con gastos, pero uno de los dos para todas las ciudades.

## 2.2 Análisis de variables

- **Soporte común**: ¿existen en cada ciudad inmuebles con las características de los perfiles definidos? Si no, cualquier predicción es extrapolación
- Comparación de distribuciones de m², precio y tipología entre ciudades
- Verificación de que las normalizaciones funcionaron
- Volumen por ciudad: por debajo de ~500 anuncios la ciudad entra al modelo global pero no soporta un modelo propio

## 2.3 Regresión global con interacciones — MOTOR DE LA FASE

```
log(price) ~ city
           + city × log(area_m2)
           + city × rooms
           + bathrooms + floor + has_elevator + parking
           + is_furnished + has_terrace + has_balcony
           + dist_center_percentile
           + quarter
```

**El coeficiente de la dummy `city` es la respuesta del proyecto**: la prima de precio por estar en esa ciudad, controlando por características.

Alternativas descartadas y por qué:
- *Un modelo por ciudad*: no comparables entre sí; las ciudades con pocos datos dan modelos malos
- *Global con solo dummy de ciudad*: asume que un baño vale +8% igual en Zúrich que en Lisboa — supuesto falso

**Versión avanzada recomendada:** modelo **jerárquico / mixed effects**, con los coeficientes de cada ciudad como efectos aleatorios de una distribución común. Es exactamente el caso de uso de los modelos multinivel (grupos de tamaño desigual, estimaciones estables en los pequeños), está al alcance de un perfil de Estadística, y es más diferenciador en portfolio que una red neuronal.

Test de significancia: contraste F anidado con y sin interacciones. Si las interacciones no son significativas, eso es un hallazgo publicable: la estructura de precios sería homogénea entre ciudades y solo cambiaría el nivel.

## 2.4 Perfiles de vivienda

Los perfiles no son un modelo: son los vectores de entrada a la regresión.

| Perfil | Especificación |
|---|---|
| Estudiante | 45 m², 1 hab, 1 baño, P20 distancia (ajustar a 50-55 m² si se excluyen estudios) |
| Pareja | 70 m², 2 hab, 1 baño, P50 |
| Familia | 100 m², 3 hab, 2 baños, parking, P60 |
| Gama alta | 160 m², 4 hab, 3 baños, parking, P20 |

**Regla de integridad: definir los perfiles antes de ver resultados**, con fecha en `DECISIONS.md`. Definirlos después expone el proyecto a la acusación de haberlos elegido para obtener el resultado deseado.

Salida: matriz de 4 perfiles × ciudades, con Andorra desglosada por parroquia.

Hipótesis a contrastar: Andorra resultará competitiva en gama alta y mala en gama baja → el mercado estaría calibrado para residentes de alto poder adquisitivo, no para quien trabaja allí.

**Verificación obligatoria por predicción**: comprobar si el perfil cae dentro del dominio de entrenamiento de esa ciudad. Reportar explícitamente las extrapolaciones.

## 2.5 Capa socioeconómica

Aquí está el argumento del proyecto, no en los precios brutos.

| Dato | Fuente |
|---|---|
| Salario **mediano neto** | Eurostat, OCDE; Dept. Estadística per Andorra |
| Salario mínimo | Eurostat / Govern d'Andorra |
| Tributación efectiva | OCDE Taxing Wages |
| Coste de vida, IPC, PPA | Eurostat |

Métricas:
1. **Ratio de esfuerzo**: alquiler / salario neto mediano. Umbral de referencia Eurostat: >30-40% es sobrecarga de costes de vivienda
2. **Renta residual**: `salario neto − alquiler − cesta básica`
3. **Renta residual ajustada por PPA**

Notas obligatorias:
- Usar salario **mediano**, no medio: la media la distorsionan los altos ingresos, especialmente en Andorra
- **Incluir explícitamente la ventaja fiscal andorrana** (IRPF bajo). Omitirla invalida el argumento ante cualquier lector informado. Trabajar con salario neto desde el principio
- **No construir un índice compuesto propio de "calidad de vida"** con pesos arbitrarios. Presentar las métricas por separado

## 2.6 RF proximity (opcional)

Rol: ilustrar con anuncios reales, no cuantificar.

Método: entrenar Random Forest de precio; definir similitud entre inmuebles como la frecuencia con que caen en la misma hoja terminal.

Justificación técnica (anticipando la crítica de "esto es un filtro SQL"): la métrica de distancia está **aprendida y ponderada por lo que determina el precio**, incluyendo interacciones. Una distancia euclídea asume que todas las variables pesan igual.

Incluir en el README una comparación explícita entre esta métrica y un baseline de filtro por rangos, mostrando casos donde difieren.

## 2.7 Segmentación GMM (opcional)

Rol: hallazgo estructural y gráfico principal para difusión.

Gaussian Mixture Model sobre el dataset multiciudad completo (mejor que KMeans: probabilidad de pertenencia y clusters de forma libre).

**Regla crítica: clusterizar sobre características físicas, NUNCA incluyendo el precio.** Incluirlo produce el hallazgo tautológico de que los pisos caros están juntos.

Después: qué precio tiene cada cluster en cada ciudad, y qué proporción del parque de cada parroquia cae en cada segmento.

Selección de `k`: silhouette + BIC. Visualización: PCA o UMAP en 2D.

Variante original complementaria: clustering sobre los **coeficientes estimados por zona** en lugar de sobre precios crudos — agrupa mercados por cómo se comportan, no por lo caros que son.

---

# FASE 3 — Publicación (semana 16)

Dashboard en Streamlit con tres vistas:
- A: este piso de X parroquia costaría Y en cada ciudad
- B: con este presupuesto, esto es lo que se obtiene en cada ciudad
- C: renta residual y capacidad de ahorro comparada

**Detector de extrapolación**: si la consulta cae fuera del dominio de entrenamiento, avisar en lugar de devolver una predicción inventada.

---

# Riesgos

| Riesgo | Prob. | Mitigación |
|---|---|---|
| Antibots bloquean idealista | Alta | Empezar por pisos.ad; delays generosos; no forzar |
| Deduplicación defectuosa | Media | Semana completa dedicada; validar muestra a mano |
| Extracción LLM alucina datos | Media | Regla de `null` explícita + validación Pydantic + muestra manual de 100 |
| Volumen bajo tras filtrar a pisos | Media | Suficiente para el modelo hedónico. No usar DL |
| Variables no comparables entre países | Alta | Conjunto mínimo común + sección de limitaciones en el README |
| Precio de anuncio ≠ precio de transacción | Alta | Reconocerlo explícitamente; calibrar contra datos oficiales |
| Abandono en fase 2 | Alta | Publicar la fase 1 como proyecto cerrado antes de empezar |

**Documentar las limitaciones en una sección propia del README.** Un proyecto que reconoce sus sesgos se lee como maduro; uno que los esconde se detecta en dos preguntas de entrevista.

---

# Calendario

| Semanas | Entregable |
|---|---|
| 1 | Repo, estructura, `DECISIONS.md`, `parish_centers.yaml` |
| 2-4 | Dataset Andorra limpio, enriquecido y deduplicado |
| 5 | EDA + validación contra SICAR + cierre de decisiones pendientes |
| 6-7 | Escalera de modelos + tabla comparativa |
| 8 | Insights, diagnóstico, SHAP → **publicación 1** |
| 9-11 | Pipeline parametrizable + 4 ciudades |
| 12 | Regresión global → primas por ciudad |
| 13 | Perfiles + capa socioeconómica |
| 14-15 | RF proximity y GMM (opcionales) |
| 16 | Dashboard + informe → **publicación 2** |
