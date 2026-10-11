import argparse
import re
import time
from datetime import date

from bs4 import BeautifulSoup

from andorra_housing.features.llm_extraction import combinar_caracteristica, extraer_de_descripcion
from andorra_housing.scraping import almacenamiento
from andorra_housing.scraping.base_scraper import (
    calcular_hash,
    descargar_html,
    esperar_lo_que_falte,
    extraer_numero,
    extraer_parking,
    extraer_texto,
    guardar_html_crudo,
)

# Códigos de parroquia usados por el filtro "parro" de pisos.ad (obtenidos probando
# el desplegable de la web y mirando el número resultante en la URL de cada opción).
PARROQUIAS_AD = {
    0: "Todas",
    1: "Andorra la Vella",
    2: "Sant Julià de Lòria",
    3: "Escaldes-Engordany",
    4: "La Massana",
    5: "Encamp",
    6: "Ordino",
    7: "Canillo",
}

BASE_URL_LISTADO = "https://pisos.ad/lloguer/pisos"

# Slugs de subtipo confirmados: la suma de resultados de los 5 coincide con el total
# de "tots-subtipus" para Andorra la Vella (29+5+0+0+0 = 34), así que están bien escritos
# aunque estudi/loft dieran 0 resultados en esa prueba concreta.
SUBTIPOS_AD = ["pis", "atic", "duplex", "estudi", "loft"]


def extraer_campos_simples(soup: BeautifulSoup) -> dict:
    """Extrae los campos de texto simple de una ficha de pisos.ad. Valores en crudo, sin limpiar todavía."""
    # Sufijo _raw: son strings tal cual salen de la web (ej. "1.450 €"),
    # todavía no convertidos a número. La limpieza es un paso aparte.
    return {
        "price_raw": extraer_texto(soup, "fitxa__preu"),
        "price_m2_raw": extraer_texto(soup, "fitxa__preu-m2"),
        "area_m2_raw": extraer_texto(soup, "fitxa__icos-superficie"),
        "rooms_raw": extraer_texto(soup, "fitxa__icos-habitacions"),
        "bathrooms_raw": extraer_texto(soup, "fitxa__icos-banys"),
        "parking_raw": extraer_texto(soup, "fitxa__icos-parking"),
        "n_photos_raw": extraer_texto(soup, "fitxa__numimatges"),
        "title_raw": extraer_texto(soup, "fitxa__title"),
    }


def extraer_caracteristicas(soup: BeautifulSoup) -> list[str]:
    """Lista de características marcadas (ej. ['Terrassa', 'Ascensor']). Lista vacía si no hay ninguna."""
    contenedor = soup.find(class_="fitxa__caracteristiques")
    if contenedor is None:
        # No hay sección de características en este anuncio: lista vacía, no un error.
        return []

    resultado = []  # aquí vamos a ir acumulando cada característica encontrada
    for li in contenedor.find_all("li"):  # cada característica está en su propio <li>
        texto = li.get_text(strip=True)  # el texto de ese <li> en concreto, ej. "Terrassa"
        resultado.append(texto)  # lo añadimos a la lista que vamos construyendo
    return resultado


def mapear_caracteristicas(caracteristicas: list[str]) -> dict:
    """Convierte la lista de texto (ej. ['Terrassa', 'Ascensor']) en los booleanos que pide el plan."""
    texto = []  # aquí guardamos las mismas características, pero en minúsculas
    for c in caracteristicas:
        texto.append(c.lower())  # normalizamos a minúsculas para comparar sin importar mayúsculas

    return {
        "has_terrace": "terrassa" in texto,
        "has_balcony": "balcó" in texto,
        "has_elevator": "ascensor" in texto,
        "has_storage": "traster" in texto,
        "is_furnished": "moblat" in texto,
    }


def extraer_fecha_modificacion(soup: BeautifulSoup) -> date | None:
    """Saca la fecha de 'Darrera modificació' de fitxa__stats. None si no aparece."""
    texto = extraer_texto(soup, "fitxa__stats")
    if texto is None:
        return None

    coincidencia = re.search(r"(\d{2})/(\d{2})/(\d{4})", texto)
    if coincidencia is None:
        return None

    dia, mes, anyo = coincidencia.groups()  # groups() da cada trozo capturado por separado
    return date(int(anyo), int(mes), int(dia))  # date() espera (año, mes, día), orden distinto al texto original


def extraer_portal_id(url: str) -> str | None:
    """Saca el ID del anuncio: el número final de la URL. None si no encaja el patrón."""
    # $ = "final de la cadena": exige que el número esté al final, no en cualquier parte de la URL.
    coincidencia = re.search(r"/(\d+)$", url)
    if coincidencia is None:
        return None
    return coincidencia.group(1)  # group(1) = el contenido del primer grupo capturado, sin la barra "/"


def extraer_ficha(html: str, url: str) -> dict:
    """Parsea una ficha completa de pisos.ad y devuelve un diccionario con los campos limpios."""
    soup = BeautifulSoup(html, "html.parser")
    crudos = extraer_campos_simples(soup)
    caracteristicas = extraer_caracteristicas(soup)

    return {
        "portal": "pisos_ad",
        "portal_id": extraer_portal_id(url),
        "url": url,
        "price": extraer_numero(crudos["price_raw"]),
        "price_m2": extraer_numero(crudos["price_m2_raw"]),
        "area_m2": extraer_numero(crudos["area_m2_raw"]),
        "rooms": extraer_numero(crudos["rooms_raw"]),
        "bathrooms": extraer_numero(crudos["bathrooms_raw"]),
        "has_parking": extraer_parking(crudos["parking_raw"]),
        "n_photos": extraer_numero(crudos["n_photos_raw"]),
        "title": crudos["title_raw"],
        # Sin procesar todavía: será la entrada de la extracción LLM (fase posterior del pipeline).
        "descripcion_raw": extraer_texto(soup, "fitxa__descripcio"),
        "agencia": extraer_texto(soup, "fitxa__barraimmo-title"),
        "fecha_modificacion": extraer_fecha_modificacion(soup),
        # ** despliega el diccionario de booleanos aquí mismo, clave por clave,
        # en vez de anidarlo dentro de una sola clave "caracteristicas".
        **mapear_caracteristicas(caracteristicas),
    }


def extraer_urls_anuncios(html: str) -> list[str]:
    """Saca las URLs de anuncios individuales (no de categoría) de una página de listado."""
    soup = BeautifulSoup(html, "html.parser")
    urls = []
    for a in soup.find_all("a", href=True):  # solo <a> que tengan atributo href
        href = a["href"]
        # Patrón de anuncio individual: /lloguer/{slug}/{numero}, sin más barras en medio.
        # Las URLs de categoría (ej. /lloguer/pisos/tots-subtipus/andorra-la-vella) no encajan:
        # tienen más segmentos y no terminan en número.
        if re.search(r"^/lloguer/[^/]+/\d+$", href):
            urls.append("https://www.pisos.ad" + href)
    return sorted(set(urls))  # set() quita duplicados (un anuncio puede tener 2 enlaces a la misma URL)


def construir_url_listado(pagina: int, parroquia_codigo: int, subtipo: str) -> str:
    """URL de una página de listado, filtrada por parroquia, subtipo de piso y número de página."""
    return (
        f"{BASE_URL_LISTADO}/{subtipo}?&minrooms=0&minbanys=0&maxrooms=0&maxbanys=0"
        f"&minmetres=0&minprice=0&maxprice=0&reference=&caracteristiques="
        f"&order=&immo=0&parro={parroquia_codigo}&promocions=false&page={pagina}"
    )


def recorrer_todos_los_anuncios(ya_existe, procesar_ficha, marcar_visto) -> None:
    """Recorre las 7 parroquias x 5 subtipos, página a página.

    Por cada anuncio encontrado en un listado, decide ANTES de descargar la ficha:
    - si `ya_existe(portal_id)` es True: no se descarga nada, solo se llama a `marcar_visto(portal_id)`.
    - si es False (anuncio nuevo): se descarga, se parsea, y se llama a `procesar_ficha(ficha)`
      y a `marcar_visto(portal_id)`.
    """
    for parroquia_codigo, nombre_parroquia in PARROQUIAS_AD.items():
        if parroquia_codigo == 0:
            continue  # 0 = "Totes les parròquies", solo existe para el desplegable de la web

        for subtipo in SUBTIPOS_AD:
            pagina = 1
            num_nuevos = 0
            while True:
                inicio = time.monotonic()
                url_listado = construir_url_listado(pagina, parroquia_codigo, subtipo)
                html_listado = descargar_html(url_listado)
                urls_anuncios = extraer_urls_anuncios(html_listado)
                esperar_lo_que_falte(inicio)

                if not urls_anuncios:
                    break  # página vacía: no hay más anuncios en esta combinación

                for url_anuncio in urls_anuncios:
                    portal_id = extraer_portal_id(url_anuncio)

                    if ya_existe(portal_id):
                        print(f"  {portal_id}: ya existía, solo actualizo fecha de visto")
                        marcar_visto(portal_id)
                        continue  # anuncio ya conocido: no se descarga ni se parsea nada

                    print(f"  {portal_id}: nuevo, descargando y procesando...")
                    inicio = time.monotonic()
                    html_anuncio = descargar_html(url_anuncio)
                    ficha = extraer_ficha(html_anuncio, url_anuncio)
                    ficha["parish"] = nombre_parroquia  # asignada aquí, no parseada del HTML
                    ficha["property_type"] = subtipo  # idem
                    guardar_html_crudo(html_anuncio, "pisos_ad", ficha["portal_id"])
                    procesar_ficha(ficha)
                    marcar_visto(portal_id)
                    num_nuevos += 1
                    esperar_lo_que_falte(inicio)

                pagina += 1

            print(f"{nombre_parroquia} / {subtipo}: {num_nuevos} anuncios nuevos")


def _combinar_y_guardar_extraccion(
    conexion, portal_id: str, descripcion: str, extraccion, valores_estructurados: dict
) -> None:
    """Combina características (estructurado OR LLM), guarda avisos de discrepancia y la extracción final.

    valores_estructurados: dict con has_terrace/has_balcony/has_elevator/has_storage ya extraídos del HTML.
    Compartido entre el flujo normal (procesar) y el de reintento (reintentar_fallos).
    """
    combinados = {}
    for nombre_campo, valor_llm in [
        ("has_terrace", extraccion.has_terrace_llm),
        ("has_balcony", extraccion.has_balcony_llm),
        ("has_elevator", extraccion.has_elevator_llm),
        ("has_storage", extraccion.has_storage_llm),
    ]:
        valor_estructurado = valores_estructurados[nombre_campo]
        valor_combinado, hay_discrepancia = combinar_caracteristica(valor_estructurado, valor_llm)
        combinados[nombre_campo] = valor_combinado
        if hay_discrepancia:
            almacenamiento.guardar_aviso(
                conexion, "pisos_ad", portal_id, nombre_campo, valor_estructurado, valor_llm, descripcion
            )

    almacenamiento.guardar_extraccion_llm(
        conexion, "pisos_ad", portal_id, extraccion,
        combinados["has_terrace"], combinados["has_balcony"],
        combinados["has_elevator"], combinados["has_storage"],
    )


def ejecutar() -> None:
    """Recorre todo pisos.ad y guarda los resultados en la base de datos, marcando bajas al final."""
    conexion = almacenamiento.conectar()
    ids_vistos = set()
    contador_nuevos = 0

    def ya_existe(portal_id: str) -> bool:
        return almacenamiento.existe(conexion, "pisos_ad", portal_id)

    def procesar(ficha: dict) -> None:
        nonlocal contador_nuevos
        portal_id = ficha["portal_id"]
        descripcion = ficha["descripcion_raw"]

        if descripcion:
            hash_descripcion = calcular_hash(descripcion)
            portal_id_original = almacenamiento.buscar_por_hash(conexion, "pisos_ad", hash_descripcion)
            if portal_id_original is not None:
                # Mismo texto de descripción que un anuncio que YA tenemos guardado: es el mismo
                # piso publicado dos veces. No se guarda como fila nueva ni se llama al LLM para él.
                print(f"    -> DUPLICADO: {portal_id} = {portal_id_original}, no se guarda, va a repetidos")
                almacenamiento.guardar_repetido(conexion, "pisos_ad", ficha["url"], portal_id, portal_id_original)
                return
            ficha["hash_descripcion"] = hash_descripcion
        else:
            ficha["hash_descripcion"] = None

        almacenamiento.guardar_ficha(conexion, ficha)
        contador_nuevos += 1
        print(f"    -> guardado como nuevo (portal_id={portal_id})")

        if not descripcion:
            return  # sin descripción, no hay nada que pasarle al LLM

        extraccion, texto_crudo = extraer_de_descripcion(descripcion)
        if extraccion is None:
            print(f"    -> LLM: no se pudo extraer/validar para {portal_id}, guardado en fallos_llm")
            almacenamiento.guardar_fallo_llm(conexion, "pisos_ad", portal_id, descripcion, texto_crudo)
            return

        valores_estructurados = {
            "has_terrace": ficha["has_terrace"],
            "has_balcony": ficha["has_balcony"],
            "has_elevator": ficha["has_elevator"],
            "has_storage": ficha["has_storage"],
        }
        _combinar_y_guardar_extraccion(conexion, portal_id, descripcion, extraccion, valores_estructurados)

    def marcar_visto(portal_id: str) -> None:
        almacenamiento.marcar_visto(conexion, "pisos_ad", portal_id)
        ids_vistos.add(("pisos_ad", portal_id))

    recorrer_todos_los_anuncios(ya_existe, procesar, marcar_visto)
    contador_bajas = almacenamiento.marcar_bajas(conexion, "pisos_ad", ids_vistos)
    conexion.close()

    contador_sin_cambios = len(ids_vistos) - contador_nuevos
    print()
    print("=== Resumen ===")
    print(f"Anuncios vistos en esta pasada: {len(ids_vistos)}")
    print(f"Nuevos (procesados de verdad): {contador_nuevos}")
    print(f"Ya existían (sin cambios de contenido): {contador_sin_cambios}")
    print(f"Marcados de baja (ya no aparecen): {contador_bajas}")


def reintentar_fallos() -> None:
    """Reintenta los anuncios de pisos.ad cuyo procesado LLM había fallado antes.

    Se ejecuta aparte, cuando se quiera (no dentro de ejecutar()), para poder revisar
    primero qué había devuelto el modelo antes de reintentar.
    """
    conexion = almacenamiento.conectar()
    fallos = almacenamiento.obtener_fallos_llm(conexion, "pisos_ad")
    print(f"{len(fallos)} fallos pendientes de reintentar")

    for portal_id, descripcion, respuesta_cruda in fallos:
        print(f"\n--- {portal_id} ---")
        print("Respuesta anterior (fallida):")
        print(respuesta_cruda)

        extraccion, texto_crudo = extraer_de_descripcion(descripcion)
        if extraccion is None:
            print(f"Sigue fallando para {portal_id}.")
            almacenamiento.guardar_fallo_llm(conexion, "pisos_ad", portal_id, descripcion, texto_crudo)
            continue

        print(f"Ahora sí funciona para {portal_id}.")

        # Este anuncio nunca tuvo hash_descripcion calculado (falló antes de llegar a esa parte).
        # Al reintentar, aprovechamos para rellenarlo, y también para comprobar si resulta ser
        # un duplicado tardío de otro anuncio que sí se guardó bien.
        hash_descripcion = calcular_hash(descripcion)
        portal_id_original = almacenamiento.buscar_por_hash(conexion, "pisos_ad", hash_descripcion)
        fila = conexion.execute(
            "SELECT has_terrace, has_balcony, has_elevator, has_storage, url FROM anuncios"
            " WHERE portal = ? AND portal_id = ?",
            ("pisos_ad", portal_id),
        ).fetchone()
        has_terrace, has_balcony, has_elevator, has_storage, url = fila

        if portal_id_original is not None and portal_id_original != portal_id:
            print(f"    AVISO: duplicado tardío detectado, {portal_id} = {portal_id_original}")
            almacenamiento.guardar_repetido(conexion, "pisos_ad", url, portal_id, portal_id_original)
            almacenamiento.borrar_fallo_llm(conexion, "pisos_ad", portal_id)
            continue

        almacenamiento.actualizar_hash_descripcion(conexion, "pisos_ad", portal_id, hash_descripcion)
        valores_estructurados = {
            "has_terrace": has_terrace,
            "has_balcony": has_balcony,
            "has_elevator": has_elevator,
            "has_storage": has_storage,
        }
        _combinar_y_guardar_extraccion(conexion, portal_id, descripcion, extraccion, valores_estructurados)
        almacenamiento.borrar_fallo_llm(conexion, "pisos_ad", portal_id)

    conexion.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--accion",
        required=True,
        choices=["ejecutar", "reintentar_fallos"],
        help="Qué acción realizar: 'ejecutar' para recorrer todo pisos.ad, o "
             "'reintentar_fallos' para procesar los anuncios que fallaron antes con el LLM.",
    )
    args = parser.parse_args()

    if args.accion == "ejecutar":
        ejecutar()
    elif args.accion == "reintentar_fallos":
        reintentar_fallos()


if __name__ == "__main__":
    main()
    