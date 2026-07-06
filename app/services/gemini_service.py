import json

from google import genai

from app.config import Config


_cliente_gemini = None


def gemini_disponible() -> bool:
    return bool(Config.GEMINI_API_KEY) and Config.USAR_GEMINI


def obtener_cliente_gemini():
    global _cliente_gemini

    if _cliente_gemini is None:
        _cliente_gemini = genai.Client(api_key=Config.GEMINI_API_KEY)

    return _cliente_gemini


def preparar_productos_para_gemini(productos: list[dict]) -> list[dict]:
    productos_limpios = []

    for producto in productos[:5]:
        productos_limpios.append({
            "codigo": producto.get("codigo"),
            "descripcion": producto.get("descripcion"),
            "cantidad": producto.get("cantidad"),
            "precio_cor": producto.get("precio_cor"),
            "precio_usd": producto.get("precio_usd"),
            "porcentaje_descuento": producto.get("porcentaje_descuento"),
        })

    return productos_limpios


def redactar_respuesta_productos(mensaje_cliente: str, busqueda_usada: str, productos: list[dict]) -> str | None:
    if not gemini_disponible():
        return None

    productos_limpios = preparar_productos_para_gemini(productos)

    prompt = f"""
Cliente escribió:
{mensaje_cliente}

Búsqueda usada en inventario:
{busqueda_usada}

Productos encontrados en la base de datos:
{json.dumps(productos_limpios, ensure_ascii=False, indent=2)}

Instrucciones:
- Respondé en español, como asistente amable de una tienda.
- No inventés productos, precios, descuentos ni cantidades.
- Usá únicamente los productos dados en la lista.
- Si hay varios productos, mostrales máximo 5 opciones.
- Mencioná código, disponibilidad, precio en córdobas y precio en dólares si existe.
- Si el producto parece relacionado pero no exacto, decí "encontré opciones relacionadas".
- No digás que consultaste una base de datos.
- No uses formato JSON.
- La respuesta debe ser clara para WhatsApp.
"""

    try:
        cliente = obtener_cliente_gemini()

        respuesta = cliente.models.generate_content(
            model=Config.GEMINI_MODEL,
            contents=prompt,
            config={
                "temperature": 0.3,
                "system_instruction": (
                    "Sos un asistente virtual de tienda. "
                    "Tu trabajo es redactar respuestas claras para clientes usando solo datos confirmados."
                ),
            },
        )

        texto = (respuesta.text or "").strip()

        if not texto:
            return None

        return texto

    except Exception as error:
        print(f"Error usando Gemini: {error}")
        return None