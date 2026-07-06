from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.config import Config
from app.database.connection import get_engine


def buscar_productos(texto: str, solo_disponibles: bool = True, limite: int = 10):
    texto = (texto or "").strip()

    if not texto:
        return {
            "ok": False,
            "detalle": "Debés enviar un texto para buscar productos."
        }

    limite = max(1, min(int(limite), 20))
    filtro = f"%{texto}%"

    condicion_existencia = "AND ISNULL(cantidad, 0) > 0" if solo_disponibles else ""

    consulta = text(f"""
        SELECT TOP {limite}
            CAST(codigoBarra AS VARCHAR(100)) AS codigo_barra,
            CAST(codigo AS NVARCHAR(100)) AS codigo,
            CAST(descripcion AS NVARCHAR(300)) AS descripcion,
            ISNULL(cantidad, 0) AS cantidad,
            ROUND(ISNULL(precioCOR, precio), 2) AS precio_cor,
            ISNULL(porcentajeDescuento, 0) AS porcentaje_descuento
        FROM dbo.app_DetalleInventario
        WHERE (
               descripcion LIKE :filtro
            OR codigo LIKE :filtro
            OR codigoBarra LIKE :filtro
        )
        {condicion_existencia}
        ORDER BY descripcion
    """)

    try:
        engine = get_engine()

        if engine is None:
            return {
                "ok": False,
                "detalle": "No hay conexión configurada con la base de datos."
            }

        with engine.connect() as connection:
            resultado = connection.execute(consulta, {"filtro": filtro})
            filas = resultado.mappings().all()

        productos = []

        for fila in filas:
            precio_cor = round(float(fila["precio_cor"] or 0), 2)

            precio_usd = 0
            if Config.MOSTRAR_PRECIO_USD and Config.TASA_CAMBIO_DOLAR > 0:
                precio_usd = round(precio_cor / Config.TASA_CAMBIO_DOLAR, 2)

            productos.append({
                "codigo_barra": fila["codigo_barra"],
                "codigo": fila["codigo"],
                "descripcion": fila["descripcion"],
                "cantidad": int(fila["cantidad"] or 0),
                "precio_cor": precio_cor,
                "precio_usd": precio_usd,
                "tasa_cambio_usada": Config.TASA_CAMBIO_DOLAR,
                "porcentaje_descuento": round(float(fila["porcentaje_descuento"] or 0), 0),
            })

        return {
            "ok": True,
            "busqueda": texto,
            "total": len(productos),
            "productos": productos
        }

    except SQLAlchemyError as error:
        return {
            "ok": False,
            "detalle": f"Error consultando productos: {str(error)}"
        }

    except Exception as error:
        return {
            "ok": False,
            "detalle": f"Error inesperado consultando productos: {str(error)}"
        }