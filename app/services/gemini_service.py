import json
import re
import unicodedata
from decimal import Decimal
from typing import Any

from google import genai

from app.config import Config


_cliente_gemini = None

INTENCIONES_VALIDAS = {
    "producto",
    "precio",
    "stock",
    "horario",
    "ubicacion",
    "pagos",
    "envios",
    "promociones",
    "asesor",
    "pedido",
    "saludo",
    "agradecimiento",
    "despedida",
    "otro",
}


NEGOCIO_BASE = {
    "nombre": "Tienda Chow Paiz",
    "ubicacion": "Barrio Central calle comercio, Bluefields, Nicaragua",
    "horario": "Lunes a sábado de 9:00 AM a 6:00 PM",
    "feriados_no_abre": [
        "1 de enero",
        "Jueves a domingo de Semana Santa",
        "25 de diciembre",
    ],
    "feriados_si_abre": [
        "30 de mayo",
        "1 de mayo",
        "7 de noviembre",
        "26 de febrero",
    ],
    "pagos_en_linea": [
        "Transferencia BAC",
        "Transferencia LAFISE",
        "Transferencia BANPRO",
    ],
    "envios": [
        "CargoTrans dependiendo del peso",
        "Correos de Nicaragua",
    ],
    "promociones": "El enlace de promociones y descuentos está pendiente de configuración.",
    "departamentos": "El enlace de WhatsApp para departamentos corporativos está pendiente de configuración.",
}


def gemini_disponible() -> bool:
    """
    Indica si Gemini está habilitado y tiene API key configurada.
    """
    return bool(getattr(Config, "GEMINI_API_KEY", "")) and bool(
        getattr(Config, "USAR_GEMINI", True)
    )


def obtener_cliente_gemini():
    """
    Crea una sola instancia del cliente Gemini para reutilizarla.
    """
    global _cliente_gemini

    if _cliente_gemini is None:
        _cliente_gemini = genai.Client(api_key=Config.GEMINI_API_KEY)

    return _cliente_gemini


def _texto_respuesta_gemini(respuesta: Any) -> str:
    """
    Extrae texto de forma segura desde la respuesta del SDK.
    """
    texto = getattr(respuesta, "text", None)

    if texto:
        return str(texto).strip()

    return ""


def generar_contenido_gemini(
    prompt: str,
    *,
    temperature: float = 0.2,
    system_instruction: str = "",
) -> str | None:
    """
    Ejecuta Gemini con manejo centralizado de errores.
    """
    if not gemini_disponible():
        return None

    try:
        cliente = obtener_cliente_gemini()

        respuesta = cliente.models.generate_content(
            model=getattr(Config, "GEMINI_MODEL", "gemini-2.5-flash"),
            contents=prompt,
            config={
                "temperature": temperature,
                "system_instruction": system_instruction,
            },
        )

        texto = _texto_respuesta_gemini(respuesta)
        return texto or None

    except Exception as error:
        print(f"Error usando Gemini: {error}", flush=True)
        return None


def limpiar_json_gemini(texto: str | None) -> str:
    """
    Limpia respuestas tipo ```json ... ``` y extrae el primer objeto JSON.
    """
    texto = (texto or "").strip()
    texto = (
        texto.replace("```json", "")
        .replace("```JSON", "")
        .replace("```", "")
        .strip()
    )

    inicio = texto.find("{")
    fin = texto.rfind("}")

    if inicio != -1 and fin != -1 and fin > inicio:
        return texto[inicio : fin + 1].strip()

    return texto


def _quitar_tildes(texto: str) -> str:
    texto = unicodedata.normalize("NFD", texto or "")
    return "".join(
        caracter for caracter in texto if unicodedata.category(caracter) != "Mn"
    )


def normalizar_texto_basico(texto: str | None) -> str:
    texto = (texto or "").strip().lower()
    texto = _quitar_tildes(texto)
    texto = re.sub(r"[^a-z0-9ñáéíóúü\s/-]", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


def _valor_serializable(valor: Any) -> Any:
    """
    Convierte Decimal y otros valores raros a algo que json.dumps soporte.
    """
    if valor is None:
        return None

    if isinstance(valor, Decimal):
        return float(valor)

    if isinstance(valor, (int, float, str, bool)):
        return valor

    try:
        return float(valor)
    except Exception:
        return str(valor)


def _obtener_primero(producto: dict, *llaves: str) -> Any:
    for llave in llaves:
        if llave in producto and producto.get(llave) is not None:
            return producto.get(llave)

    return None


def _a_float(valor: Any) -> float | None:
    if valor is None:
        return None

    try:
        if isinstance(valor, str):
            valor = valor.replace("C$", "").replace("$", "").replace(",", "").strip()

            if not valor:
                return None

        return float(valor)

    except Exception:
        return None


def preparar_productos_para_gemini(
    productos: list[dict] | dict | None,
    limite: int = 5,
) -> list[dict]:
    """
    Limpia productos para pasarlos a Gemini sin exponer campos innecesarios.
    Soporta listas o diccionarios tipo {"productos": [...]}.
    """
    if productos is None:
        productos = []

    if isinstance(productos, dict):
        productos = productos.get("productos") or []

    productos_limpios: list[dict] = []

    for producto in list(productos)[:limite]:
        if not isinstance(producto, dict):
            continue

        precio_cor = _obtener_primero(
            producto,
            "precio_cor",
            "precio_cordobas",
            "precio",
            "pnd_cordobas",
            "PND C$",
        )

        precio_sin_descuento = _obtener_primero(
            producto,
            "precio_sin_descuento",
            "prisd_cordobas",
            "PRISD C$",
        )

        descuento = _obtener_primero(
            producto,
            "porcentaje_descuento",
            "descuento",
            "Descuento",
        )

        cantidad = _obtener_primero(
            producto,
            "cantidad",
            "Cantidad",
            "stock",
            "existencia",
        )

        cantidad_float = _a_float(cantidad)
        descuento_float = _a_float(descuento) or 0

        productos_limpios.append(
            {
                "codigo": _valor_serializable(
                    _obtener_primero(
                        producto,
                        "codigo",
                        "barcode",
                        "codigo_barra",
                        "Barcode",
                    )
                ),
                "descripcion": _valor_serializable(
                    _obtener_primero(
                        producto,
                        "descripcion",
                        "Descripcion",
                        "nombre",
                        "producto",
                    )
                ),
                "categoria": _valor_serializable(
                    _obtener_primero(producto, "categoria", "Categoria")
                ),
                "cantidad": _valor_serializable(cantidad),
                "unidad": _valor_serializable(
                    _obtener_primero(producto, "unidad", "U/M", "um")
                ),
                "precio_cordobas": _valor_serializable(precio_cor),
                "precio_sin_descuento": _valor_serializable(precio_sin_descuento),
                "precio_usd": _valor_serializable(
                    _obtener_primero(producto, "precio_usd", "precio_dolares")
                ),
                "descuento": _valor_serializable(descuento_float),
                "disponible": bool(cantidad_float is not None and cantidad_float > 0),
            }
        )

    return productos_limpios


def interpretar_mensaje_cliente(mensaje: str) -> dict | None:
    """
    Usa Gemini solo para entender intención.
    No redacta respuesta final al cliente en esta función.
    """
    if not gemini_disponible():
        return None

    prompt = f"""
Analizá el siguiente mensaje de un cliente de WhatsApp para Tienda Chow Paiz.

Mensaje del cliente:
"{mensaje}"

Tu tarea NO es responder al cliente.
Tu tarea es clasificar la intención y extraer una búsqueda limpia si aplica.

Respondé únicamente un JSON válido, sin markdown, sin texto extra.

Formato exacto:
{{
  "intencion": "producto | precio | stock | horario | ubicacion | pagos | envios | promociones | asesor | pedido | saludo | agradecimiento | despedida | otro",
  "busqueda": "producto, marca, categoría, código o referencia para buscar en inventario; vacío si no aplica",
  "requiere_asesor": false,
  "confianza": 0.0,
  "motivo": "explicación interna muy breve"
}}

Definiciones:
- saludo: hola, buenas, buenos días, buenas tardes, buenas noches.
- agradecimiento: gracias, muchas gracias, perfecto gracias, ok gracias.
- despedida: adiós, hasta luego, nos vemos.
- horario: pregunta por horario, cuándo abren, cuándo cierran, días de atención o feriados.
- ubicacion: pregunta dónde están, dirección, ubicación o referencia del local.
- pagos: pregunta por métodos de pago, transferencia, BAC, LAFISE, BANPRO, pago en línea.
- envios: pregunta por envíos, delivery, entregas, encomienda, CargoTrans, Correos de Nicaragua.
- promociones: pregunta por descuentos, promociones, ofertas o link de promociones.
- asesor: quiere hablar con una persona, asesor, vendedor, encargado o departamento específico.
- pedido: quiere hacer, confirmar o coordinar un pedido.
- producto: pregunta si venden, tienen o manejan un producto, categoría o marca.
- precio: pregunta cuánto cuesta, precio, vale, cotización o referencia de precio.
- stock: pregunta si hay existencia, disponibilidad, unidades o cantidad.
- otro: no se puede clasificar con seguridad.

Reglas para busqueda:
- Si la intención es producto, precio o stock, extraé únicamente el producto, categoría, marca, código o referencia.
- Si dice "qué tienen en joyería", busqueda: "joyeria".
- Si dice "qué hay en bebidas", busqueda: "bebidas".
- Si dice "precio de coca cola", busqueda: "coca cola".
- Si dice "tienen shampoo para perro", busqueda: "shampoo perro".
- Si dice "cuánto cuesta este producto" y no da nombre, marca, código ni referencia, busqueda: "".
- Si manda solo un código o referencia, busqueda debe ser ese código.
- Quitá palabras de relleno como: qué, tienen, hay, venden, precio, cuánto, cuesta, vale, quiero, necesito, busco, por favor.
- No inventés productos ni marcas.
- Si el cliente exige humano, requiere_asesor debe ser true.

Ejemplos:
Cliente: "Hola"
JSON: {{"intencion":"saludo","busqueda":"","requiere_asesor":false,"confianza":0.98,"motivo":"saludo"}}

Cliente: "¿Cuánto cuesta el aceite ideal?"
JSON: {{"intencion":"precio","busqueda":"aceite ideal","requiere_asesor":false,"confianza":0.95,"motivo":"pregunta precio"}}

Cliente: "¿Tienen joyería?"
JSON: {{"intencion":"producto","busqueda":"joyeria","requiere_asesor":false,"confianza":0.95,"motivo":"consulta categoría"}}

Cliente: "Quiero hablar con alguien"
JSON: {{"intencion":"asesor","busqueda":"","requiere_asesor":true,"confianza":0.98,"motivo":"pide humano"}}
"""

    texto = generar_contenido_gemini(
        prompt,
        temperature=0.05,
        system_instruction=(
            "Sos un clasificador de mensajes para una tienda. "
            "Devolvés únicamente JSON válido. No respondés al cliente."
        ),
    )

    if not texto:
        return None

    try:
        data = json.loads(limpiar_json_gemini(texto))

        intencion = normalizar_texto_basico(data.get("intencion") or "otro")
        busqueda = normalizar_texto_basico(data.get("busqueda") or "")
        requiere_asesor = bool(data.get("requiere_asesor", False))

        try:
            confianza = float(data.get("confianza", 0.0) or 0.0)
        except Exception:
            confianza = 0.0

        if intencion not in INTENCIONES_VALIDAS:
            intencion = "otro"

        return {
            "intencion": intencion,
            "busqueda": busqueda,
            "requiere_asesor": requiere_asesor,
            "confianza": confianza,
            "motivo": str(data.get("motivo") or "").strip()[:120],
        }

    except Exception as error:
        print(
            f"Error interpretando JSON de Gemini: {error}. Respuesta recibida: {texto}",
            flush=True,
        )
        return None


def redactar_respuesta_productos(
    mensaje_cliente: str,
    busqueda_usada: str,
    productos: list[dict] | dict | None,
    intencion: str = "producto",
    limite: int = 5,
) -> str | None:
    """
    Redacta la respuesta de productos usando únicamente datos reales encontrados.
    Gemini puede redactar, pero no puede inventar inventario.
    """
    if not gemini_disponible():
        return None

    productos_limpios = preparar_productos_para_gemini(productos, limite=limite)

    prompt = f"""
Sos el asistente virtual de WhatsApp de Tienda Chow Paiz.

Contexto fijo del negocio:
{json.dumps(NEGOCIO_BASE, ensure_ascii=False, indent=2)}

Mensaje original del cliente:
"{mensaje_cliente}"

Intención detectada:
"{intencion}"

Búsqueda usada en inventario:
"{busqueda_usada}"

Productos reales encontrados:
{json.dumps(productos_limpios, ensure_ascii=False, indent=2)}

Reglas obligatorias:
- Respondé en español natural de Nicaragua, amable y claro.
- La respuesta debe servir para WhatsApp.
- No digás que sos Gemini, IA, modelo, SQL, base de datos, API ni sistema.
- No inventés productos, marcas, precios, descuentos, códigos ni existencias.
- Usá únicamente los productos reales listados arriba.
- Si la lista de productos está vacía, decí que no encontraste coincidencias exactas para la búsqueda y pedí otro nombre, marca, categoría o referencia.
- Si hay productos, mostrales máximo {limite} opciones.
- Si el cliente pregunta precio, destacá el precio en córdobas si está disponible.
- Si no hay precio disponible, no inventés precio; decí que el precio no aparece disponible y sugerí consultar con asesor.
- Si cantidad es mayor que 0, podés decir que aparece disponible.
- Si cantidad es 0 o disponible es false, no digás que hay disponibilidad.
- Si hay descuento mayor que 0, podés mencionarlo.
- Si el producto tiene código, podés incluirlo como referencia.
- No uses tablas.
- No hagás párrafos largos.
- No terminés siempre con la misma frase.
- Si la pregunta es muy general, invitá al cliente a dar una marca, presentación o referencia.

Formato sugerido:
- Una frase inicial corta.
- Lista breve con viñetas si hay varios productos.
- Una pregunta final útil solo si aporta.

Tono:
- Profesional pero cercano.
- Nada exagerado.
- No uses emojis excesivos; máximo uno si queda natural.
"""

    texto = generar_contenido_gemini(
        prompt,
        temperature=0.28,
        system_instruction=(
            "Sos un asistente de atención al cliente para una tienda. "
            "Redactás respuestas breves para WhatsApp usando solo datos confirmados. "
            "Nunca inventás inventario, precios ni disponibilidad."
        ),
    )

    if not texto:
        return None

    return texto.strip()


def redactar_respuesta_informacion_negocio(
    mensaje_cliente: str,
    intencion: str,
    datos_autorizados: dict,
) -> str | None:
    """
    Redacta respuestas para horario, ubicación, pagos, envíos, promociones, etc.
    Solo puede usar datos_autorizados.
    """
    if not gemini_disponible():
        return None

    prompt = f"""
Sos el asistente virtual de WhatsApp de Tienda Chow Paiz.

Mensaje del cliente:
"{mensaje_cliente}"

Intención detectada:
"{intencion}"

Datos autorizados para responder:
{json.dumps(datos_autorizados, ensure_ascii=False, indent=2)}

Reglas:
- Respondé solo con la información autorizada.
- No agregués datos que no estén aquí.
- No inventés links, teléfonos, departamentos, promociones ni condiciones.
- Español natural, claro y breve para WhatsApp.
- No menciones que recibiste datos autorizados.
- Si algo está pendiente de configuración, decilo con naturalidad.
- Si conviene, invitá al cliente a escribir el producto, categoría o referencia.
"""

    texto = generar_contenido_gemini(
        prompt,
        temperature=0.25,
        system_instruction=(
            "Sos un asistente de tienda. Respondés de forma breve y amable usando solo datos autorizados."
        ),
    )

    if not texto:
        return None

    return texto.strip()