import json
from typing import Literal

import requests
from pydantic import BaseModel, ValidationError


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


OLLAMA_URL = "http://localhost:11434/api/generate"
MODELO = "qwen2.5:7b"

PROMPT_BASE = """Analiza esta descripción de un anuncio inmobiliario en catalán o español y extrae la siguiente información en formato JSON con estos campos exactos:

- condition: estado general de la vivienda, según cómo se describe en el texto. Debe ser uno de:
    "nuevo" -> menciona obra nueva, a estrenar, recién construido
    "reformado" -> menciona reformado, renovado, reforma integral, actualizado recientemente
    "buen_estado" -> menciona buen estado, cuidado, bien conservado (sin decir que se ha reformado)
    "a_reformar" -> menciona que necesita reforma, para reformar, a reformar, estado a mejorar
    null -> si el texto no dice nada sobre el estado de la vivienda

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
- n_parking_spaces: número de plazas de parking (entero) o null
- has_terrace_llm: true si se menciona terraza, false si se menciona explícitamente que no hay, null si no se menciona
- has_balcony_llm: true si se menciona balcón, false si se menciona explícitamente que no hay, null si no se menciona
- has_elevator_llm: true si se menciona ascensor, false si se menciona explícitamente que no hay, null si no se menciona
- has_storage_llm: true si se menciona trastero, false si se menciona explícitamente que no hay, null si no se menciona

REGLA IMPORTANTE: si un dato no aparece explícitamente en el texto, devuelve null. No inventes
ni supongas valores. Pero si el texto SÍ da una pista explícita (aunque sea indirecta, como un
pago "a compte" de algo), úsala -- no la ignores por precaución.

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


def extraer_de_descripcion(descripcion: str) -> tuple[ExtraccionLLM | None, str]:
    """Llama a Ollama para extraer los campos de una descripción.

    Devuelve (resultado_validado, texto_crudo). resultado_validado es None si el JSON
    no es válido o no cumple el esquema -- texto_crudo se devuelve SIEMPRE, incluso
    cuando falla, para poder guardarlo y revisar/reintentar más tarde.
    """
    prompt = PROMPT_BASE.format(descripcion=descripcion)
    respuesta = requests.post(
        OLLAMA_URL,
        json={"model": MODELO, "prompt": prompt, "format": "json", "stream": False},
        timeout=60,
    )
    respuesta.raise_for_status()
    texto_json = respuesta.json()["response"]

    try:
        datos = json.loads(texto_json)
        return ExtraccionLLM(**datos), texto_json
    except (json.JSONDecodeError, ValidationError):
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
