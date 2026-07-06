import re

from app.services.productos_service import buscar_productos


PALABRAS_IGNORADAS = {
    "hola", "buenas", "buenos", "dias", "días", "tardes", "noches",
    "tienen", "tiene", "hay", "venden", "vender", "busco", "buscar",
    "quiero", "quisiera", "necesito", "me", "puedes", "podrias", "podrías",
    "decir", "saber", "precio", "precios", "cuanto", "cuánto", "vale",
    "valen", "cuesta", "cuestan", "disponible", "disponibles",
    "en", "de", "del", "la", "el", "los", "las", "un", "una", "unos", "unas",
    "por", "favor", "favor?"
}


def limpiar_mensaje_para_busqueda(mensaje: str) -> str:
    texto = (mensaje or "").lower()

    texto = re.sub(r"[¿?¡!.,;:()\[\]{}\"']", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()

    palabras = [
        palabra
        for palabra in texto.split()
        if palabra not in PALABRAS_IGNORADAS and len(palabra) > 1
    ]

    return " ".join(palabras).strip()


def singularizar_basico(texto: str) -> str:
    palabras = []

    for palabra in texto.split():
        if len(palabra) > 4 and palabra.endswith("s"):
            palabras.append(palabra[:-1])
        else:
            palabras.append(palabra)

    return " ".join(palabras)


def crear_candidatos_busqueda(mensaje: str) -> list[str]:
    limpio = limpiar_mensaje_para_busqueda(mensaje)
    singular = singularizar_basico(limpio)

    candidatos = []

    for candidato in [limpio, singular]:
        if candidato and candidato not in candidatos:
            candidatos.append(candidato)

    for palabra in singular.split():
        if palabra and palabra not in candidatos:
            candidatos.append(palabra)

    return candidatos


def formatear_producto(producto: dict) -> str:
    descripcion = producto.get("descripcion") or "Producto sin descripción"
    codigo = producto.get("codigo") or producto.get("codigo_barra") or "Sin código"
    cantidad = producto.get("cantidad", 0)
    precio_cor = producto.get("precio_cor", 0)
    precio_usd = producto.get("precio_usd", 0)
    descuento = producto.get("porcentaje_descuento", 0)

    linea = (
        f"- {descripcion}\n"
        f"  Código: {codigo}\n"
        f"  Disponible: {cantidad} unidad(es)\n"
        f"  Precio: C$ {precio_cor:,.2f}"
    )

    if precio_usd and precio_usd > 0:
        linea += f" / US$ {precio_usd:,.2f}"

    if descuento and descuento > 0:
        linea += f"\n  Descuento: {descuento:.0f}%"

    return linea


def responder_chat(mensaje: str) -> dict:
    mensaje = (mensaje or "").strip()

    if not mensaje:
        return {
            "ok": False,
            "respuesta": "Escribí una consulta para poder ayudarte."
        }

    candidatos = crear_candidatos_busqueda(mensaje)

    if not candidatos:
        return {
            "ok": True,
            "tipo": "general",
            "respuesta": "Puedo ayudarte a consultar productos, precios y disponibilidad. Decime qué producto estás buscando."
        }

    ultima_respuesta = None

    for candidato in candidatos:
        resultado = buscar_productos(
            texto=candidato,
            solo_disponibles=True,
            limite=5
        )

        ultima_respuesta = resultado

        if resultado.get("ok") and resultado.get("total", 0) > 0:
            productos = resultado.get("productos", [])

            productos_formateados = "\n\n".join(
                formatear_producto(producto)
                for producto in productos
            )

            respuesta = (
                f"Sí, encontré estos productos relacionados con \"{candidato}\":\n\n"
                f"{productos_formateados}"
            )

            return {
                "ok": True,
                "tipo": "busqueda_producto",
                "busqueda_usada": candidato,
                "respuesta": respuesta,
                "productos": productos
            }

    return {
        "ok": True,
        "tipo": "busqueda_producto",
        "busqueda_usada": candidatos[0],
        "respuesta": (
            f"No encontré productos disponibles relacionados con \"{candidatos[0]}\". "
            "Podés probar con otro nombre, marca, tipo de prenda o código."
        ),
        "detalle": ultima_respuesta
    }