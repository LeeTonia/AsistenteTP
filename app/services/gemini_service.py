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


def redactar_respuesta_productos(
    mensaje_cliente: str,
    busqueda_usada: str,
    productos: list[dict] | None
) -> str | None:
    if not gemini_disponible():
        return None

    if productos is None:
        productos = []

    productos_limpios = []

    for producto in productos[:5]:
        productos_limpios.append({
            "codigo": producto.get("codigo") or producto.get("barcode"),
            "descripcion": producto.get("descripcion"),
            "categoria": producto.get("categoria"),
            "cantidad": producto.get("cantidad"),
            "unidad": producto.get("unidad"),
            "precio_cor": producto.get("precio_cor") or producto.get("precio_cordobas"),
            "precio_usd": producto.get("precio_usd"),
            "descuento": producto.get("porcentaje_descuento") or producto.get("descuento") or 0,
        })

    prompt = f"""
Sos el asistente virtual de WhatsApp de una tienda.

El cliente escribió:
"{mensaje_cliente}"

La búsqueda usada fue:
"{busqueda_usada}"

Productos encontrados en el inventario real:
{json.dumps(productos_limpios, ensure_ascii=False, indent=2)}

Tu trabajo:
- Respondé de forma natural, como una persona amable atendiendo WhatsApp.
- No sonés como plantilla.
- No repitás siempre la misma estructura.
- Usá frases cortas y claras.
- Si hay productos encontrados, resumilos de forma útil.
- Si no hay productos encontrados, decí que no encontraste ese producto exacto y sugerí preguntar por otra marca, categoría o producto parecido.
- Podés hacer una pregunta de seguimiento si ayuda.
- Nunca inventés productos.
- Nunca inventés precios.
- Nunca digás que hay existencia si no aparece en los productos encontrados.
- No mencionés SQL, base de datos, Python ni Gemini.
- Respondé en español natural para WhatsApp.
"""

    try:
        cliente = obtener_cliente_gemini()

        respuesta = cliente.models.generate_content(
            model=Config.GEMINI_MODEL,
            contents=prompt,
            config={
                "temperature": 0.7,
                "system_instruction": (
                    "Sos un asistente virtual de tienda. "
                    "Tu trabajo es atender clientes por WhatsApp usando solo datos confirmados del inventario."
                ),
            },
        )

        texto = (respuesta.text or "").strip()

        if not texto:
            return None

        print("Respuesta generada con Gemini", flush=True)
        return texto

    except Exception as error:
        print(f"Error usando Gemini: {error}", flush=True)
        return None