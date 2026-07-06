from urllib.parse import quote_plus

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from app.config import Config


_engine = None


def construir_url_conexion():
    if Config.SQL_CONNECTION_STRING:
        params = quote_plus(Config.SQL_CONNECTION_STRING)
        return f"mssql+pyodbc:///?odbc_connect={params}"

    if Config.DATABASE_URL:
        return Config.DATABASE_URL

    return ""


def get_engine():
    global _engine

    url_conexion = construir_url_conexion()

    if not url_conexion:
        return None

    if _engine is None:
        _engine = create_engine(
            url_conexion,
            pool_pre_ping=True
        )

    return _engine


def probar_conexion_bd():
    url_conexion = construir_url_conexion()

    if not url_conexion:
        return {
            "ok": False,
            "detalle": "No hay conexión configurada. Falta DATABASE_URL o SQL_CONNECTION_STRING en el archivo .env"
        }

    try:
        engine = get_engine()

        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))

        return {
            "ok": True,
            "detalle": "Conexión a la base de datos exitosa"
        }

    except SQLAlchemyError as error:
        return {
            "ok": False,
            "detalle": f"Error de SQLAlchemy: {str(error)}"
        }

    except Exception as error:
        return {
            "ok": False,
            "detalle": f"Error inesperado: {str(error)}"
        }
    
def obtener_drivers_odbc():
    try:
        import pyodbc

        return {
            "ok": True,
            "drivers": pyodbc.drivers()
        }

    except Exception as error:
        return {
            "ok": False,
            "detalle": f"No se pudieron obtener los drivers ODBC: {str(error)}"
        }