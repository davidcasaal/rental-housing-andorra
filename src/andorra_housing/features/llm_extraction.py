import json
import os
import time
from typing import Literal

import requests
from dotenv import load_dotenv
from pydantic import BaseModel, ValidationError

from andorra_housing.scraping.base_scraper import PROJECT_ROOT

# Se ancla a PROJECT_ROOT (no al directorio actual) para que cargue el .env
# correcto sin importar desde dónde se ejecute el código (notebook, script, terminal...).
load_dotenv(PROJECT_ROOT / ".env")


class ExtraccionLLM(BaseModel):
    condition: Literal["nuevo", "reformado", "buen_estado", "a_reformar"] | None = None
    construction_year: int | None = None
    renovation_year: int | None = None
    expenses_included: Literal["todo", "parcial", "no"] | None = None
    expenses_detail: str | None = None
    furnished: Literal["amueblado", "semi", "vacio"] | None = None
    n_parking_spaces: int | None = None
    has_terrace_llm: bool | None = None
    has_balcony_llm: bool | None = None
    has_elevator_llm: bool | None = None
    has_storage_llm: bool | None = None


OLLAMA_URL = os.environ["OLLAMA_URL"]
MODELO = os.environ["MODELO"]

VALORES_FURNISHED_COLADOS_EN_CONDITION = {
    "amueblado", "semi", "vacio", "furnished", "sin muebles",
}

PROMPT_BASE = """Analiza esta descripción de un anuncio inmobiliario en catalán o español y extrae la siguiente información en formato JSON con estos campos exactos:

- condition: estado físico de la vivienda. SOLO puede valer una de estas 5 cosas exactas,
  ninguna otra palabra es válida aquí bajo ningún concepto:
    "nuevo" -> menciona obra nueva, a estrenar, recién construido
    "reformado" -> menciona reformado, renovado, reforma integral, actualizado recientemente
    "buen_estado" -> menciona buen estado, cuidado, bien conservado (sin decir que se ha reformado)
    "a_reformar" -> menciona que necesita reforma, para reformar, a reformar, estado a mejorar
    null -> si el texto no dice nada sobre el estado de la vivienda
    MUY IMPORTANTE: NO ESTAMOS HABLANDO DEL MOBILIARIO, ISNO DEL ESTADO DE LA VIVIENDO. NO PUEDES DEBOLVER:
"amueblado", "semi", "vacio", "furnished", "sin muebles", ....
- construction_year: año de construcción (entero) o null
- renovation_year: año de reforma (entero) o null

- expenses_included: uno de "todo" | "parcial" | "no" | null -- si los gastos del piso (comunidad,
  calefacción, luz, gas, agua, o cualquier otro) están incluidos en el precio del alquiler:
    "todo" -> se dice que todos los gastos están incluidos
    "parcial" -> se menciona que algunos gastos están incluidos, pero no todos
    "no" -> se dice explícitamente que los gastos NO están incluidos
    null -> no se menciona nada sobre gastos

- expenses_detail: texto breve y simple listando qué gastos concretos se mencionan
  (ej: "comunidad y agua", "calefacción incluida", "luz y gas no incluidos"), tal cual aparecen
  en el texto -- sin categorizar más, eso se hará más adelante. null si no se menciona ningún gasto.

- furnished: uno de "amueblado", "semi", "vacio", o null
    ESTA VARIABLE ES LA ÚNICA QUE TIENE QUE VER CON EL MOBILIARIO: "amueblado" -> se menciona que la vivienda está amueblada, "semi" -> se menciona que está semi-amueblada, "vacio" -> se menciona que está vacía, sin muebles. null si no se menciona nada sobre muebles.
- n_parking_spaces: número de plazas de parking (entero) o null
- has_terrace_llm: true si se menciona terraza, false si se menciona explícitamente que no hay, null si no se menciona
- has_balcony_llm: true si se menciona balcón, false si se menciona explícitamente que no hay, null si no se menciona
- has_elevator_llm: true si se menciona ascensor, false si se menciona explícitamente que no hay, null si no se menciona
- has_storage_llm: true si se menciona trastero, false si se menciona explícitamente que no hay, null si no se menciona

REGLA IMPORTANTE: si un dato no aparece explícitamente en el texto, devuelve el valor JSON null
(sin comillas), NUNCA el texto "null" entre comillas -- son cosas distintas: null (sin dato) no es
lo mismo que la palabra "null" como si fuera un valor de texto, que no es válida para ningún campo.
No inventes ni supongas valores. Pero si el texto SÍ da una pista explícita (aunque sea indirecta,
como un pago "a compte" de algo), úsala -- no la ignores por precaución.

RECUERDA: hay dos preguntas distintas sobre la vivienda que NO deben mezclarse: una es su estado
físico (reformada, nueva, a reformar...) y otra es si tiene muebles dentro. Cada una va en su
propio campo del esquema, con su propia lista de valores permitidos -- no copies el valor de uno
en el otro.

EJEMPLOS de expenses_included, para calibrar:
- Texto: "calefacción no incluida, se paga aparte" -> "no"
- Texto: "100€ a compte de calefacció" (se paga como anticipo, aparte del alquiler) -> "no"
- Texto: "todos los gastos incluidos en el precio" -> "todo"
- Texto: "piso de dos habitaciones con terraza" (no menciona gastos en absoluto) -> null

EJEMPLOS para has_terrace_llm / has_balcony_llm / has_elevator_llm / has_storage_llm, para calibrar
(la falta de mención NO es lo mismo que "no hay" -- son la mayoría de los casos, no lo olvides):
- Texto: "piso de 3 habitaciones en el centro" (no menciona el ascensor en absoluto) -> has_elevator_llm: null
- Texto: "edificio sin ascensor" -> has_elevator_llm: false
- Texto: "dispone de ascensor" -> has_elevator_llm: true
- Texto: "gran salón, cocina equipada, dos baños" (no menciona balcón) -> has_balcony_llm: null

Descripción:
\"\"\"{descripcion}\"\"\"

Devuelve SOLO el JSON, sin texto adicional."""


def extraer_de_descripcion(descripcion: str, intentos: int = 3) -> tuple[ExtraccionLLM | None, str]:
    """Llama a Ollama para extraer los campos de una descripción.

    Devuelve (resultado_validado, texto_crudo). resultado_validado es None si el JSON
    no es válido o no cumple el esquema -- texto_crudo se devuelve SIEMPRE, incluso
    cuando falla, para poder guardarlo y revisar/reintentar más tarde.
    """
    prompt = PROMPT_BASE.format(descripcion=descripcion)

    for intento in range(1, intentos + 1):
        try:
            respuesta = requests.post(
                OLLAMA_URL,
                json={"model": MODELO, "prompt": prompt, "format": "json", "stream": False},
                timeout=60,
            )
            respuesta.raise_for_status()
            break
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            # Corte transitorio hablando con Ollama en local (ej. el modelo se estaba
            # recargando en memoria) -- no es un error de la descripción en sí.
            if intento == intentos:
                raise
            print(f"    Ollama no responde (intento {intento}/{intentos}), reintentando en 5s...")
            time.sleep(5)
    texto_json = respuesta.json()["response"]

    try:
        datos = json.loads(texto_json)
    except json.JSONDecodeError:
        return None, texto_json

    # Limpieza defensiva: el modelo, a veces, copia el valor de "furnished" en
    # "condition" en vez de dejarlo en null. Esos valores nunca son válidos para
    # condition (no están en su Literal), así que en vez de perder toda la
    # extracción por este único campo, lo forzamos a None y aprovechamos el resto.
    if isinstance(datos.get("condition"), str) and datos["condition"].lower() in VALORES_FURNISHED_COLADOS_EN_CONDITION:
        datos["condition"] = None

    try:
        return ExtraccionLLM(**datos), texto_json
    except ValidationError:
        return None, texto_json


def combinar_caracteristica(
    valor_estructurado: bool | None, valor_llm: bool | None
) -> tuple[bool, bool]:
    """Combina el valor estructurado y el del LLM con un OR.

    Devuelve (valor_combinado, hay_discrepancia). Si el LLM no dice nada (None),
    no hay discrepancia que avisar -- "no sé" no contradice nada, se usa solo lo estructurado.
    """
    estructurado = bool(valor_estructurado)
    if valor_llm is None:
        return estructurado, False
    llm = bool(valor_llm)
    return estructurado or llm, estructurado != llm
