from datetime import date

import duckdb

from andorra_housing.scraping.base_scraper import PROJECT_ROOT

DB_PATH = PROJECT_ROOT / "data" / "andorra_housing.duckdb"


def conectar() -> duckdb.DuckDBPyConnection:
    """Abre (o crea si no existe) la base de datos DuckDB del proyecto."""
    conexion = duckdb.connect(str(DB_PATH))
    conexion.execute("""
        CREATE TABLE IF NOT EXISTS anuncios (
            portal TEXT NOT NULL,
            portal_id TEXT NOT NULL,
            parish TEXT,
            property_type TEXT,
            price DOUBLE,
            price_m2 DOUBLE,
            area_m2 DOUBLE,
            rooms DOUBLE,
            bathrooms DOUBLE,
            has_parking BOOLEAN,
            has_terrace BOOLEAN,
            has_balcony BOOLEAN,
            has_elevator BOOLEAN,
            has_storage BOOLEAN,
            is_furnished BOOLEAN,
            n_photos DOUBLE,
            title TEXT,
            descripcion_raw TEXT,
            hash_descripcion TEXT,
            agencia TEXT,
            url TEXT,
            fecha_modificacion DATE,
            primera_captura DATE NOT NULL,
            ultima_vez_visto DATE NOT NULL,
            activo BOOLEAN NOT NULL,
            fecha_baja DATE,
            condition TEXT,
            construction_year INTEGER,
            renovation_year INTEGER,
            expenses_included TEXT,
            expenses_detail TEXT,
            furnished_llm TEXT,
            n_parking_spaces INTEGER,
            has_terrace_llm BOOLEAN,
            has_balcony_llm BOOLEAN,
            has_elevator_llm BOOLEAN,
            has_storage_llm BOOLEAN,
            PRIMARY KEY (portal, portal_id)
        )
    """)
    conexion.execute("""
        CREATE TABLE IF NOT EXISTS avisos (
            portal TEXT NOT NULL,
            portal_id TEXT NOT NULL,
            campo TEXT NOT NULL,
            valor_estructurado BOOLEAN,
            valor_llm BOOLEAN,
            descripcion TEXT,
            fecha_aviso DATE NOT NULL,
            PRIMARY KEY (portal, portal_id, campo)
        )
    """)
    # Columna añadida después de crear la tabla: ALTER ... IF NOT EXISTS para que
    # conectar() se pueda llamar siempre igual, sin fallar si ya se había añadido antes.
    conexion.execute("ALTER TABLE avisos ADD COLUMN IF NOT EXISTS veredicto TEXT")
    conexion.execute("""
        CREATE TABLE IF NOT EXISTS fallos_llm (
            portal TEXT NOT NULL,
            portal_id TEXT NOT NULL,
            descripcion TEXT,
            respuesta_cruda TEXT,
            fecha DATE NOT NULL,
            PRIMARY KEY (portal, portal_id)
        )
    """)
    conexion.execute("""
        CREATE TABLE IF NOT EXISTS repetidos (
            portal TEXT NOT NULL,
            portal_id TEXT NOT NULL,
            url TEXT,
            portal_id_original TEXT NOT NULL,
            fecha DATE NOT NULL,
            PRIMARY KEY (portal, portal_id)
        )
    """)
    conexion.commit()
    return conexion


def guardar_fallo_llm(
    conexion: duckdb.DuckDBPyConnection,
    portal: str,
    portal_id: str,
    descripcion: str,
    respuesta_cruda: str,
) -> None:
    """Guarda (o actualiza, si ya existía) un fallo de extracción LLM, con el texto crudo del modelo."""
    conexion.execute(
        """
        INSERT OR REPLACE INTO fallos_llm (portal, portal_id, descripcion, respuesta_cruda, fecha)
        VALUES (?, ?, ?, ?, ?)
        """,
        (portal, portal_id, descripcion, respuesta_cruda, date.today()),
    )
    conexion.commit()


def guardar_veredicto_aviso(
    conexion: duckdb.DuckDBPyConnection, portal: str, portal_id: str, campo: str, veredicto: str
) -> None:
    """Guarda el veredicto de la revisión manual de un aviso concreto (portal, portal_id, campo)."""
    conexion.execute(
        "UPDATE avisos SET veredicto = ? WHERE portal = ? AND portal_id = ? AND campo = ?",
        (veredicto, portal, portal_id, campo),
    )
    conexion.commit()


def obtener_avisos(
    conexion: duckdb.DuckDBPyConnection,
    portal: str,
    solo_sin_revisar: bool = True,
    campo: str | None = None,
) -> list:
    """Devuelve los avisos de un portal, para revisarlos. Por defecto, solo los que aún no tienen veredicto."""
    condicion = "AND veredicto IS NULL" if solo_sin_revisar else ""
    parametros = [portal]
    if campo:
        condicion += " AND campo = ?"
        parametros.append(campo)

    return conexion.execute(
        f"""
        SELECT portal_id, campo, valor_estructurado, valor_llm, descripcion
        FROM avisos
        WHERE portal = ? {condicion}
        ORDER BY campo, portal_id
        """,
        parametros,
    ).fetchall()



def obtener_fallos_llm(conexion: duckdb.DuckDBPyConnection, portal: str) -> list:
    """Devuelve todas las filas de fallos_llm de un portal, para reintentarlas o revisarlas."""
    return conexion.execute(
        "SELECT portal_id, descripcion, respuesta_cruda FROM fallos_llm WHERE portal = ?",
        (portal,),
    ).fetchall()


def borrar_fallo_llm(conexion: duckdb.DuckDBPyConnection, portal: str, portal_id: str) -> None:
    """Borra un fallo de fallos_llm, normalmente porque se ha resuelto reintentando con éxito."""
    conexion.execute(
        "DELETE FROM fallos_llm WHERE portal = ? AND portal_id = ?",
        (portal, portal_id),
    )
    conexion.commit()


def guardar_aviso(
    conexion: duckdb.DuckDBPyConnection,
    portal: str,
    portal_id: str,
    campo: str,
    valor_estructurado: bool,
    valor_llm: bool,
    descripcion: str,
) -> None:
    """Guarda un aviso de discrepancia entre el dato estructurado y el detectado por el LLM."""
    conexion.execute(
        """
        INSERT OR REPLACE INTO avisos (
            portal, portal_id, campo, valor_estructurado, valor_llm, descripcion, fecha_aviso
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (portal, portal_id, campo, valor_estructurado, valor_llm, descripcion, date.today()),
    )
    conexion.commit()


def existe(conexion: duckdb.DuckDBPyConnection, portal: str, portal_id: str) -> bool:
    """True si ya hay una fila guardada para este (portal, portal_id)."""
    fila = conexion.execute(
        "SELECT 1 FROM anuncios WHERE portal = ? AND portal_id = ?",
        (portal, portal_id),
    ).fetchone()
    return fila is not None


def buscar_por_hash(conexion: duckdb.DuckDBPyConnection, portal: str, hash_descripcion: str) -> str | None:
    """Devuelve el portal_id de un anuncio ya guardado con esta misma huella de descripción, o None."""
    fila = conexion.execute(
        "SELECT portal_id FROM anuncios WHERE portal = ? AND hash_descripcion = ?",
        (portal, hash_descripcion),
    ).fetchone()
    return fila[0] if fila else None


def guardar_repetido(
    conexion: duckdb.DuckDBPyConnection, portal: str, url: str, portal_id: str, portal_id_original: str
) -> None:
    """Registra un anuncio detectado como duplicado (misma descripción) de otro ya guardado."""
    conexion.execute(
        "INSERT OR REPLACE INTO repetidos (portal, url, portal_id, portal_id_original, fecha) VALUES (?, ?, ?, ?, ?)",
        (portal, url, portal_id, portal_id_original, date.today()),
    )
    conexion.commit()


def actualizar_hash_descripcion(
    conexion: duckdb.DuckDBPyConnection, portal: str, portal_id: str, hash_descripcion: str
) -> None:
    """Rellena hash_descripcion en una fila que ya existe (para los fallos_llm antiguos, sin hash)."""
    conexion.execute(
        "UPDATE anuncios SET hash_descripcion = ? WHERE portal = ? AND portal_id = ?",
        (hash_descripcion, portal, portal_id),
    )
    conexion.commit()


def guardar_ficha(conexion: duckdb.DuckDBPyConnection, ficha: dict) -> None:
    """Inserta una ficha NUEVA. Asume que ya se comprobó con existe() que no estaba guardada."""
    hoy = date.today()
    datos = {
        **ficha,
        "primera_captura": hoy,
        "ultima_vez_visto": hoy,
        "activo": True,
        "fecha_baja": None,
    }
    conexion.execute(
        """
        INSERT INTO anuncios (
            portal, portal_id, parish, property_type, price, price_m2, area_m2,
            rooms, bathrooms, has_parking, has_terrace, has_balcony, has_elevator,
            has_storage, is_furnished, n_photos, title, descripcion_raw, hash_descripcion,
            agencia, url, fecha_modificacion, primera_captura, ultima_vez_visto, activo, fecha_baja
        ) VALUES (
            $portal, $portal_id, $parish, $property_type, $price, $price_m2, $area_m2,
            $rooms, $bathrooms, $has_parking, $has_terrace, $has_balcony, $has_elevator,
            $has_storage, $is_furnished, $n_photos, $title, $descripcion_raw, $hash_descripcion,
            $agencia, $url, $fecha_modificacion, $primera_captura, $ultima_vez_visto, $activo, $fecha_baja
        )
        """,
        datos,
    )
    conexion.commit()


def marcar_visto(conexion: duckdb.DuckDBPyConnection, portal: str, portal_id: str) -> None:
    """Actualiza 'ultima_vez_visto' de un anuncio ya existente, y lo reactiva si estaba de baja."""
    hoy = date.today()
    conexion.execute(
        "UPDATE anuncios SET ultima_vez_visto = ?, activo = true, fecha_baja = NULL WHERE portal = ? AND portal_id = ?",
        (hoy, portal, portal_id),
    )
    conexion.commit()


def marcar_bajas(conexion: duckdb.DuckDBPyConnection, portal: str, ids_vistos: set) -> int:
    """Marca como inactivos los anuncios de un portal que ya no se han visto en esta pasada.
    Devuelve cuántos se han marcado de baja."""
    hoy = date.today()
    activos_en_bd = conexion.execute(
        "SELECT portal_id FROM anuncios WHERE portal = ? AND activo = true",
        (portal,),
    ).fetchall()

    contador = 0
    for (portal_id,) in activos_en_bd:
        if (portal, portal_id) not in ids_vistos:
            conexion.execute(
                "UPDATE anuncios SET activo = false, fecha_baja = ? WHERE portal = ? AND portal_id = ?",
                (hoy, portal, portal_id),
            )
            contador += 1

    conexion.commit()
    return contador


def guardar_extraccion_llm(
    conexion: duckdb.DuckDBPyConnection,
    portal: str,
    portal_id: str,
    extraccion,
    has_terrace: bool,
    has_balcony: bool,
    has_elevator: bool,
    has_storage: bool,
) -> None:
    """Guarda los campos extraídos por el LLM y las características ya combinadas (estructurado OR LLM).

    hash_descripcion NO se toca aquí -- se guarda al insertar la ficha (guardar_ficha), antes del LLM.
    """
    conexion.execute(
        """
        UPDATE anuncios SET
            condition = $condition,
            construction_year = $construction_year,
            renovation_year = $renovation_year,
            expenses_included = $expenses_included,
            expenses_detail = $expenses_detail,
            furnished_llm = $furnished,
            n_parking_spaces = $n_parking_spaces,
            has_terrace_llm = $has_terrace_llm,
            has_balcony_llm = $has_balcony_llm,
            has_elevator_llm = $has_elevator_llm,
            has_storage_llm = $has_storage_llm,
            has_terrace = $has_terrace,
            has_balcony = $has_balcony,
            has_elevator = $has_elevator,
            has_storage = $has_storage
        WHERE portal = $portal AND portal_id = $portal_id
        """,
        {
            **extraccion.model_dump(),
            "has_terrace": has_terrace,
            "has_balcony": has_balcony,
            "has_elevator": has_elevator,
            "has_storage": has_storage,
            "portal": portal,
            "portal_id": portal_id,
        },
    )
    conexion.commit()
