# Rental Housing Andorra

Modelo hedónico de precios de alquiler en Andorra, replicado en ciudades europeas comparables, para estimar cuánto cuesta una vivienda equivalente en cada mercado y cuánta renta residual le queda a un trabajador tras pagarla.

> Proyecto en construcción. Plan completo: [plan_proyecto_andorra_housing.md](plan_proyecto_andorra_housing.md) · Decisiones metodológicas: [DECISIONS.md](DECISIONS.md)

**Estado actual:** funciona el scraping de **pisos.ad** (alquiler, 7 parroquias) con extracción de campos por LLM local (Ollama) y almacenamiento en DuckDB. Dedup, modelos y evaluación están como carpetas vacías (pendientes).

---

## 1. Estructura del repositorio

```
andorra_housing/
├── README.md                    ← este archivo
├── DECISIONS.md                 ← log de decisiones metodológicas (qué, por qué, alternativas)
├── plan_proyecto_andorra_housing.md  ← plan global del proyecto
├── pyproject.toml               ← paquete `andorra_housing` (layout src/)
├── requirements.txt             ← dependencias (pip)
├── .env                         ← variables locales (NO versionado, ver §3)
│
├── src/andorra_housing/         ← código del paquete
│   ├── scraping/
│   │   ├── base_scraper.py      ← utilidades comunes: descarga con reintentos, delays, hash, caché HTML
│   │   ├── almacenamiento.py    ← esquema y operaciones DuckDB (tablas, altas/bajas, avisos...)
│   │   └── parsers/
│   │       └── pisos_ad.py      ← parser + CLI de pisos.ad  (un fichero por portal)
│   ├── features/
│   │   └── llm_extraction.py    ← extracción de campos desde la descripción vía Ollama + pydantic
│   ├── dedup/                   ← (vacío) deduplicación entre portales
│   ├── models/                  ← (vacío) modelo hedónico / ajustes
│   └── eval/                    ← (vacío) evaluación y métricas
│
├── data/                        ← NADA de aquí se versiona (se regenera con el pipeline)
│   ├── andorra_housing.duckdb   ← base de datos principal
│   ├── raw/<portal>/<id>.html   ← HTML crudo de cada anuncio nuevo (caché para depurar)
│   ├── interim/                 ← datos intermedios (limpieza, joins)
│   └── processed/               ← datasets finales listos para modelar
│
├── notebooks/                   ← exploración (01_*, 01.2_*); outputs limpios antes de commitear
├── scripts/                     ← automatización (launchd + shell), ver §5
├── logs/                        ← un log por día: pisos_ad_YYYY-MM-DD.log (no versionado)
├── config/                      ← (vacío) configuración no secreta (ej. listas de ciudades, parámetros)
└── reports/                     ← (vacío) informes, figuras y tablas finales
```

**Qué va en cada carpeta**

| Carpeta | Debe contener |
|---|---|
| `src/andorra_housing/scraping/parsers/` | Un módulo por portal con su parser y su `main()` con `--accion`. |
| `src/andorra_housing/features/` | Transformaciones que crean variables (LLM, geografía, limpieza). |
| `src/andorra_housing/dedup/` | Lógica de duplicados *entre* portales (dentro de un portal ya se hace por hash). |
| `src/andorra_housing/models/` | Modelo hedónico, renta residual, comparación entre ciudades. |
| `src/andorra_housing/eval/` | Validación, métricas, revisión de calidad de datos. |
| `data/raw` → `interim` → `processed` | Flujo de datos: crudo → limpio parcial → listo para modelo. |
| `config/` | Ficheros de configuración sin secretos. Los secretos van en `.env`. |
| `reports/` | Salidas finales (gráficos, tablas, texto). |

---

## 2. Instalación

Requisitos: Python ≥ 3.11 y [Ollama](https://ollama.com) instalado.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .                 # instala el paquete andorra_housing (layout src/)

ollama pull qwen2.5:7b           # modelo usado para la extracción (ver DECISIONS.md, 2026-09-18)
```

---

## 3. Variables de entorno (`.env`)

Se crea a mano en la raíz (está en `.gitignore`). **Las tres son obligatorias**: si falta alguna, el código falla al importar con `KeyError`.

| Variable | Qué es | Ejemplo |
|---|---|---|
| `OLLAMA_URL` | Endpoint de generación de Ollama | `http://localhost:11434/api/generate` |
| `MODELO` | Modelo de Ollama a usar | `qwen2.5:7b` |
| `DB_PATH` | Ruta de la DuckDB, **relativa a la raíz del proyecto** | `data/andorra_housing.duckdb` |

El `.env` se carga siempre desde la raíz del proyecto, así que da igual desde qué directorio se ejecute.

---

## 4. Ejecutar el scraping de pisos.ad (paso a paso)

1. **Activar el entorno** (desde la raíz del repo):
   ```bash
   source .venv/bin/activate
   ```
2. **Comprobar el `.env`** (§3) y que **Ollama está sirviendo**:
   ```bash
   curl -s http://localhost:11434/api/tags >/dev/null && echo OK || ollama serve &
   ```
3. **Lanzar el scraping completo** (recorre 7 parroquias × 5 subtipos `pis, atic, duplex, estudi, loft`, página a página):
   ```bash
   python -m andorra_housing.scraping.parsers.pisos_ad --accion ejecutar
   ```
4. **Reintentar los anuncios en los que el LLM falló** (opcional, se puede hacer más tarde):
   ```bash
   python -m andorra_housing.scraping.parsers.pisos_ad --accion reintentar_fallos
   ```

### Qué hace `ejecutar`, por anuncio

```
listado (parroquia, subtipo, página)
   └─ por cada URL de anuncio
        ├─ ya en BD?  → solo actualiza ultima_vez_visto (no descarga nada)
        └─ nuevo →  descarga ficha → guarda HTML en data/raw/pisos_ad/
                  → hash de la descripción ── repetido? → tabla `repetidos` (fin)
                  → INSERT en `anuncios`
                  → LLM (Ollama) extrae condition, año, gastos, amueblado, parking...
                        ├─ falla → tabla `fallos_llm` (se reintenta con --accion reintentar_fallos)
                        └─ ok → combina estructurado OR LLM; si discrepan → tabla `avisos`
Al terminar: los activos que no se han visto en la pasada → activo=false + fecha_baja
```

Detalles: delay aleatorio de 2–5 s entre peticiones, 3 reintentos ante fallos de red, User-Agent identificado. La primera pasada tarda horas (LLM por anuncio); las siguientes son rápidas porque solo procesan los nuevos.

### Dónde se almacena todo

| Qué | Dónde |
|---|---|
| Base de datos | `data/andorra_housing.duckdb` (ruta según `DB_PATH`) |
| HTML crudo de anuncios nuevos | `data/raw/pisos_ad/<portal_id>.html` |
| Logs de ejecución automática | `logs/pisos_ad_YYYY-MM-DD.log`, `logs/launchd.err` |

**Tablas DuckDB** (se crean solas al conectar):

| Tabla | Contenido |
|---|---|
| `anuncios` | Un anuncio por fila (PK `portal, portal_id`): precio, m², habitaciones, extras, campos LLM, `primera_captura`, `ultima_vez_visto`, `activo`, `fecha_baja`. |
| `avisos` | Discrepancias entre dato estructurado y LLM en terraza/balcón/ascensor/trastero, con `veredicto` de revisión manual. |
| `fallos_llm` | Anuncios cuya extracción LLM falló, con la respuesta cruda del modelo. |
| `repetidos` | Anuncios descartados por tener la misma descripción que otro ya guardado. |

Consulta rápida:
```bash
python -c "import duckdb; print(duckdb.connect('data/andorra_housing.duckdb', read_only=True).sql('SELECT parish, count(*) n, round(avg(price)) precio FROM anuncios WHERE activo GROUP BY 1 ORDER BY 2 DESC'))"
```

---

## 5. Ejecución automática (macOS, launchd)

[scripts/ejecutar_pisos_ad.sh](scripts/ejecutar_pisos_ad.sh) arranca Ollama si no responde, y lanza `ejecutar` + `reintentar_fallos` con `caffeinate` (el Mac no se duerme). Escribe en `logs/pisos_ad_<fecha>.log`.

[scripts/com.andorrahousing.pisosad.plist](scripts/com.andorrahousing.pisosad.plist) lo programa **martes y viernes a las 08:00**.

```bash
cp scripts/com.andorrahousing.pisosad.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.andorrahousing.pisosad.plist   # activar
launchctl unload ~/Library/LaunchAgents/com.andorrahousing.pisosad.plist # desactivar
launchctl start com.andorrahousing.pisosad                               # lanzarlo ya
```

Las rutas del `.plist` y de `ollama` (`/usr/local/bin/ollama`) son específicas de esta máquina; ajústalas si cambias de equipo.

---

## 6. Otras notas

- **Añadir un portal nuevo:** crear `scraping/parsers/<portal>.py` reutilizando `base_scraper.py` y `almacenamiento.py`, usando el mismo esquema `anuncios` (el campo `portal` distingue el origen).
- **Reprocesar sin volver a descargar:** el HTML guardado en `data/raw/` permite depurar el parser sin nuevas peticiones.
- **Datos no versionados:** `data/*`, `.env`, `logs/` y `aprender.md` están en `.gitignore`; cualquier colaborador debe regenerar los datos ejecutando el pipeline.
- **Scraping responsable:** User-Agent identificado, delays de 2–5 s y no se reprocesan anuncios ya conocidos para minimizar carga en el portal.
- **Revisión de calidad:** las discrepancias en `avisos` se revisan a mano y el veredicto se guarda en la misma tabla (criterio en DECISIONS.md, 2026-09-21/22).
- **Cosas por decidir/hacer:** tests automáticos (no hay), dedup entre portales, otros portales y ciudades, y el modelo hedónico.
