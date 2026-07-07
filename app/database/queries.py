import pyodbc

from app.config import Config


def obtener_conexion_sql():
    if not Config.SQL_CONNECTION_STRING:
        raise Exception("No hay SQL_CONNECTION_STRING configurado en el .env")

    return pyodbc.connect(Config.SQL_CONNECTION_STRING)


def buscar_productos(texto_busqueda: str, limite: int = 5):
    texto_busqueda = (texto_busqueda or "").strip()

    if not texto_busqueda:
        return []

    limite_seguro = max(1, min(int(limite), 10))
    termino = f"%{texto_busqueda}%"

    query = f"""
        SELECT TOP ({limite_seguro})
            Categoria,
            Descripcion,
            Barcode,
            Cantidad,
            [PND C$],
            [PRISD C$],
            [U/M],
            Descuento
        FROM dbo.APPTIENDACHOWPAIZ
        WHERE
            Cantidad > 0
            AND (
                Descripcion LIKE ?
                OR Categoria LIKE ?
                OR Barcode LIKE ?
            )
        ORDER BY Descripcion;
    """

    conexion = obtener_conexion_sql()
    cursor = conexion.cursor()

    try:
        cursor.execute(query, termino, termino, termino)
        filas = cursor.fetchall()

        productos = []

        for fila in filas:
            categoria = fila[0]
            descripcion = fila[1]
            barcode = fila[2]
            cantidad = fila[3]
            precio_cordobas = fila[4]
            precio_sin_descuento = fila[5]
            unidad = fila[6]
            descuento = fila[7]

            productos.append({
                "categoria": categoria,
                "descripcion": descripcion,
                "barcode": barcode,
                "cantidad": cantidad,
                "precio_cordobas": precio_cordobas,
                "precio_sin_descuento": precio_sin_descuento,
                "unidad": unidad,
                "descuento": descuento,

                # Nombres que espera gemini_service.py
                "codigo": barcode,
                "precio_cor": precio_cordobas,
                "precio_usd": None,
                "porcentaje_descuento": descuento or 0,
            })

        return productos

    finally:
        cursor.close()
        conexion.close()