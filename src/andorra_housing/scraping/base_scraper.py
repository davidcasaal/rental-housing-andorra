import hashlib
import random
import re
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

USER_AGENT = "AndorraHousingIndex/0.1 (+https://github.com/davidcasaal/rental-housing-andorra)"

# __file__ es la ruta de este propio archivo .py. .resolve() la hace absoluta,
# y .parents[3] sube 3 niveles de carpeta (scraping -> andorra_housing -> src -> raíz del proyecto).
# Así calculamos la raíz sin depender de desde dónde se ejecute el código.
PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATA_RAW_DIR = PROJECT_ROOT / "data" / "raw"


def descargar_html(url: str, intentos: int = 3) -> str:
    for intento in range(1, intentos + 1):
        try:
            respuesta = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=10)
            # Corta la ejecución si el servidor devolvió un error (404, 500...),
            # en vez de seguir con el HTML de una página de error como si fuera válido.
            respuesta.raise_for_status()
            return respuesta.text
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            # Fallo de RED (DNS, timeout, conexión cortada) -- probablemente transitorio,
            # a diferencia de un error HTTP real (que sí debe parar en seco, más arriba).
            if intento == intentos:
                raise  # se acabaron los reintentos, ahora sí dejamos que falle de verdad
            print(f"    Fallo de conexión (intento {intento}/{intentos}), reintentando en 5s...")
            time.sleep(5)


def extraer_texto(soup: BeautifulSoup, clase: str) -> str | None:
    """Busca la primera etiqueta con `clase` y devuelve su texto, o None si no existe."""
    tag = soup.find(class_=clase)
    if tag is None:
        # Defensivo: algunas clases no aparecen en todos los anuncios
        # (ej. fitxa__caracteristiques vacía si el piso no tiene extras).
        # Devolver None aquí evita que el programa falle; quien llame decide qué hacer con el hueco.
        return None
    return tag.get_text(strip=True)


def extraer_numero(texto: str | None) -> float | None:
    """Saca el primer número de un texto tipo '2.200 €' o '25,74 €/m2'. None si no hay texto o no hay número."""
    if texto is None:
        return None
    coincidencia = re.search(r"[\d.,]+", texto)
    if coincidencia is None:
        return None
    # "." es separador de miles (se quita) y "," es el decimal (se convierte a punto).
    # Orden importa: quitar puntos primero, luego pasar la coma a punto.
    numero = coincidencia.group().replace(".", "").replace(",", ".")
    return float(numero)


def extraer_parking(texto: str | None) -> bool | None:
    """True si hay parking, False si no, None si no hay dato.

    Heurística simple sobre el vocabulario visto hasta ahora en pisos.ad
    (Inclòs/No Inclòs) — revisar si aparece una tercera categoría tipo
    "opcional" en más anuncios; de momento se trata como booleano, no
    como la categórica de 3 valores que pide el plan.
    """
    if texto is None or texto.strip() == "":
        return None
    return "no" not in texto.lower()


def esperar_lo_que_falte(inicio: float, minimo: float = 2, maximo: float = 5) -> None:
    """Duerme solo lo necesario para completar un delay aleatorio entre minimo y maximo,
    contando desde 'inicio' (un time.monotonic() tomado antes de la petición/proceso)."""
    transcurrido = time.monotonic() - inicio
    delay_objetivo = random.uniform(minimo, maximo)
    if transcurrido < delay_objetivo:
        time.sleep(delay_objetivo - transcurrido)


def guardar_html_crudo(html: str, portal: str, portal_id: str) -> Path:
    """Guarda el HTML crudo en data/raw/<portal>/<portal_id>.html, para no repetir peticiones al depurar."""
    carpeta = DATA_RAW_DIR / portal
    carpeta.mkdir(parents=True, exist_ok=True)  # crea la carpeta si no existe, sin fallar si ya está
    ruta = carpeta / f"{portal_id}.html"
    ruta.write_text(html, encoding="utf-8")
    return ruta


def calcular_hash(texto: str) -> str:
    """Huella digital (hash) de un texto, para identificar contenido idéntico entre anuncios/portales."""
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()
