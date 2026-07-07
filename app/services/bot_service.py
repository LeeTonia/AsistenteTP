import json
import re

from app.database.queries import buscar_productos
from app.services.gemini_service import (
    redactar_respuesta_productos,
    gemini_disponible,
    obtener_cliente_gemini,
)
from app.utils.text_utils import limpiar_texto
from app.config import Config


def limpiar_json_gemini(texto: str) -> str:
    texto = (texto or "").strip()
    texto = texto.replace("```json", "").replace("```", "").strip()
    return texto


def interpretar_mensaje_con_gemini(mensaje: str) -> dict | None:
    """
    Gemini NO responde al cliente aquí.
    Solo interpreta intención y extrae una búsqueda limpia.
    """

    if not gemini_disponible():
        return None

    prompt = f"""
Analizá este mensaje de un cliente de WhatsApp para una tienda:

"{mensaje}"

Respondé únicamente un JSON válido, sin explicación y sin markdown.

Formato exacto:
{{
  "intencion": "producto | horario | saludo | agradecimiento | otro",
  "busqueda": "texto corto para buscar en inventario o vacío"
}}

Reglas:
- Si pregunta "qué tienen en joyería", la intención es "producto" y busqueda es "joyeria".
- Si pregunta "qué hay en bebidas", la intención es "producto" y busqueda es "bebidas".
- Si pregunta "precio de coca cola", busqueda es "coca cola".
- Si pregunta "tienen shampoo para perro", busqueda es "shampoo perro".
- Quitá palabras de relleno como: qué, tienen, hay, venden, precio, cuánto, cuesta, en, de, del, la, el.
- No inventés productos.
- No respondás al cliente.
- Solo devolvé JSON.
"""

    try:
        cliente = obtener_cliente_gemini()

        respuesta = cliente.models.generate_content(
            model=Config.GEMINI_MODEL,
            contents=prompt,
            config={
                "temperature": 0.1,
                "system_instruction": (
                    "Sos un clasificador de mensajes. "
                    "Tu única tarea es devolver JSON válido para que otro sistema busque en inventario."
                ),
            },
        )

        texto = limpiar_json_gemini(respuesta.text)
        data = json.loads(texto)

        intencion = (data.get("intencion") or "otro").strip().lower()
        busqueda = (data.get("busqueda") or "").strip().lower()

        print(f"Interpretación Gemini: intencion={intencion}, busqueda={busqueda}", flush=True)

        return {
            "intencion": intencion,
            "busqueda": busqueda,
        }

    except Exception as error:
        print(f"Error interpretando mensaje con Gemini: {error}", flush=True)
        return None


def extraer_busqueda_producto_fallback(mensaje_limpio: str) -> str:
    """
    Plan B si Gemini falla.
    """

    texto = mensaje_limpio

    texto = re.sub(r"[¿?.,:;!¡]", " ", texto)
    texto = " ".join(texto.split())

    palabras_a_quitar = {
        "hola",
        "buenas",
        "buenos",
        "dias",
        "días",
        "tardes",
        "noches",
        "que",
        "qué",
        "producto",
        "productos",
        "tienen",
        "tiene",
        "venden",
        "vende",
        "hay",
        "precio",
        "precios",
        "cuanto",
        "cuánto",
        "cuesta",
        "cuestan",
        "vale",
        "valen",
        "disponible",
        "disponibilidad",
        "busco",
        "quiero",
        "necesito",
        "ocupo",
        "en",
        "de",
        "del",
        "la",
        "el",
        "los",
        "las",
        "un",
        "una",
        "por",
        "favor",
    }

    tokens = texto.split()
    tokens_limpios = [token for token in tokens if token not in palabras_a_quitar]

    return " ".join(tokens_limpios).strip()


def formatear_respuesta_productos_python(busqueda: str, productos: list[dict]) -> str:
    respuesta = f"Encontré estos productos relacionados con '{busqueda}':\n\n"

    for producto in productos:
        descripcion = producto.get("descripcion") or "Producto sin nombre"
        categoria = producto.get("categoria") or "Sin categoría"
        cantidad = producto.get("cantidad") or 0
        unidad = producto.get("unidad") or ""
        precio = producto.get("precio_cordobas")

        if precio is None:
            precio_texto = "precio no disponible"
        else:
            precio_texto = f"C$ {float(precio):,.2f}"

        respuesta += (
            f"• {descripcion}\n"
            f"  Categoría: {categoria}\n"
            f"  Disponible: {cantidad} {unidad}\n"
            f"  Precio: {precio_texto}\n\n"
        )

    return respuesta.strip()


def procesar_mensaje_prueba(mensaje: str) -> str:
    mensaje_limpio = limpiar_texto(mensaje)

    if not mensaje_limpio:
        return "No recibí ningún mensaje. ¿Podés escribir tu consulta?"

    interpretacion = interpretar_mensaje_con_gemini(mensaje)

    if interpretacion:
        intencion = interpretacion.get("intencion", "otro")
        busqueda = interpretacion.get("busqueda", "")
    else:
        intencion = "producto"
        busqueda = extraer_busqueda_producto_fallback(mensaje_limpio)

    if intencion == "saludo":
        return (
            "¡Hola! Soy el asistente virtual del negocio. "
            "Podés preguntarme por productos, precios o disponibilidad."
        )

    if intencion == "agradecimiento":
        return "¡Con gusto! Estoy para ayudarte."

    if intencion == "horario":
        return "Nuestro horario de atención es de lunes a sábado, de 8:00 AM a 6:00 PM."

    if intencion == "producto":
        if not busqueda:
            return (
                "Claro, puedo ayudarte a buscar productos. "
                "Decime el nombre, marca o categoría que querés consultar."
            )

        try:
            productos = buscar_productos(busqueda)

            respuesta_gemini = redactar_respuesta_productos(
                mensaje_cliente=mensaje,
                busqueda_usada=busqueda,
                productos=productos,
            )

            if respuesta_gemini:
                print("Respuesta final generada con Gemini", flush=True)
                return respuesta_gemini

            if not productos:
                return (
                    f"No encontré productos relacionados con '{busqueda}'. "
                    "Podés intentar con otro nombre, marca o categoría."
                )

            return formatear_respuesta_productos_python(busqueda, productos)

        except Exception as error:
            print("Error consultando productos:", error, flush=True)
            return (
                "Tuve un problema consultando los productos en el inventario. "
                "Por favor revisá la conexión con SQL Server."
            )

    return (
        "Puedo ayudarte principalmente con productos, precios, disponibilidad y horarios. "
        "Probá preguntándome por una categoría o producto específico."
    )