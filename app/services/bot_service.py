import re
import unicodedata
from typing import Any

from app.config import Config
from app.database.queries import buscar_productos
from app.services.gemini_service import (
    interpretar_mensaje_cliente,
    redactar_respuesta_informacion_negocio,
    redactar_respuesta_productos,
)
from app.utils.text_utils import limpiar_texto


# =========================
# Datos fijos del negocio
# =========================

NOMBRE_NEGOCIO = (getattr(Config, "NOMBRE_NEGOCIO", "") or "Tienda Chow Paiz").strip()

if NOMBRE_NEGOCIO.lower() == "negocio":
    NOMBRE_NEGOCIO = "Tienda Chow Paiz"


INFO_NEGOCIO = {
    "nombre": NOMBRE_NEGOCIO,
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
    "direccion": "Barrio Central calle comercio, Bluefields, Nicaragua",
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
    "regla_precios": (
        "Para consultar precios, el cliente debe proporcionar referencia, "
        "nombre, marca o código del producto."
    ),
}


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


LIMITE_PRODUCTOS_RESPUESTA = 5
LIMITE_CONSULTAS_PRECIO_ANTES_ASESOR = 10

_consultas_precio_por_cliente: dict[str, int] = {}


# =========================
# Utilidades generales
# =========================

def _quitar_tildes(texto: str) -> str:
    texto = unicodedata.normalize("NFD", texto or "")
    return "".join(
        caracter for caracter in texto if unicodedata.category(caracter) != "Mn"
    )


def normalizar_texto(texto: str | None) -> str:
    texto = (texto or "").strip().lower()
    texto = _quitar_tildes(texto)
    texto = re.sub(r"[^a-z0-9ñ\s/-]", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


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


def _obtener_primero(producto: dict, *llaves: str) -> Any:
    for llave in llaves:
        if llave in producto and producto.get(llave) is not None:
            return producto.get(llave)

    return None


def normalizar_interpretacion(
    interpretacion: dict | None,
    mensaje_limpio: str,
) -> dict:
    if not interpretacion:
        return detectar_intencion_fallback(mensaje_limpio)

    intencion = normalizar_texto(interpretacion.get("intencion") or "otro")
    busqueda = normalizar_texto(interpretacion.get("busqueda") or "")
    requiere_asesor = bool(interpretacion.get("requiere_asesor", False))

    if intencion not in INTENCIONES_VALIDAS:
        intencion = "otro"

    # Si Gemini quedó inseguro o no extrajo búsqueda en una consulta de producto/precio/stock,
    # usamos el extractor local como respaldo.
    if intencion in {"producto", "precio", "stock"} and not busqueda:
        busqueda = extraer_busqueda_producto_fallback(mensaje_limpio)

    # Evita búsquedas basura cuando el cliente realmente no dio producto.
    busquedas_invalidas = {
        "este",
        "esto",
        "ese",
        "eso",
        "producto",
        "productos",
        "precio",
        "precios",
        "cuanto",
        "cuesta",
        "vale",
        "referencia",
    }

    if busqueda in busquedas_invalidas:
        busqueda = ""

    return {
        "intencion": intencion,
        "busqueda": busqueda,
        "requiere_asesor": requiere_asesor,
        "confianza": interpretacion.get("confianza", 0),
        "motivo": interpretacion.get("motivo", ""),
    }


# =========================
# Fallback sin Gemini
# =========================

def extraer_busqueda_producto_fallback(mensaje_limpio: str) -> str:
    texto = normalizar_texto(mensaje_limpio)

    palabras_a_quitar = {
        "hola",
        "buenas",
        "buenos",
        "dias",
        "tardes",
        "noches",
        "que",
        "producto",
        "productos",
        "articulo",
        "articulos",
        "tienen",
        "tiene",
        "tendran",
        "manejan",
        "venden",
        "vende",
        "hay",
        "precio",
        "precios",
        "cuanto",
        "cuanta",
        "cuantos",
        "cuantas",
        "cuesta",
        "cuestan",
        "vale",
        "valen",
        "disponible",
        "disponibilidad",
        "existencia",
        "stock",
        "busco",
        "buscar",
        "quiero",
        "quisiera",
        "necesito",
        "ocupo",
        "me",
        "puede",
        "pueden",
        "dar",
        "decir",
        "consultar",
        "saber",
        "en",
        "de",
        "del",
        "la",
        "el",
        "los",
        "las",
        "un",
        "una",
        "unos",
        "unas",
        "por",
        "favor",
        "porfa",
        "porfavor",
    }

    tokens = texto.split()
    tokens_limpios = [token for token in tokens if token not in palabras_a_quitar]
    busqueda = " ".join(tokens_limpios).strip()

    # Si el cliente manda un código con guiones o números, lo preservamos.
    return busqueda


def detectar_intencion_fallback(mensaje_limpio: str) -> dict:
    texto = normalizar_texto(mensaje_limpio)

    if not texto:
        return {
            "intencion": "otro",
            "busqueda": "",
            "requiere_asesor": False,
        }

    if any(
        frase in texto
        for frase in [
            "muchas gracias",
            "gracias",
            "ok gracias",
            "perfecto gracias",
        ]
    ):
        return {
            "intencion": "agradecimiento",
            "busqueda": "",
            "requiere_asesor": False,
        }

    if any(
        frase in texto
        for frase in [
            "hasta luego",
            "adios",
            "nos vemos",
            "bye",
        ]
    ):
        return {
            "intencion": "despedida",
            "busqueda": "",
            "requiere_asesor": False,
        }

    if any(
        frase in texto
        for frase in [
            "hola",
            "buenas",
            "buenos dias",
            "buenas tardes",
            "buenas noches",
        ]
    ):
        # Si dice "hola, tienen arroz", no queremos quedarnos solo en saludo.
        palabras_producto = [
            "tienen",
            "venden",
            "hay",
            "precio",
            "cuanto",
            "cuesta",
            "busco",
            "necesito",
        ]

        if not any(palabra in texto for palabra in palabras_producto):
            return {
                "intencion": "saludo",
                "busqueda": "",
                "requiere_asesor": False,
            }

    if any(
        palabra in texto
        for palabra in [
            "asesor",
            "humano",
            "persona",
            "vendedor",
            "encargado",
            "departamento",
            "atencion",
            "atención",
        ]
    ):
        return {
            "intencion": "asesor",
            "busqueda": "",
            "requiere_asesor": True,
        }

    if any(
        palabra in texto
        for palabra in [
            "horario",
            "hora",
            "abren",
            "abre",
            "cierran",
            "cierra",
            "atienden",
            "feriado",
            "feriados",
        ]
    ):
        return {
            "intencion": "horario",
            "busqueda": "",
            "requiere_asesor": False,
        }

    if any(
        palabra in texto
        for palabra in [
            "direccion",
            "ubicacion",
            "donde estan",
            "donde queda",
            "local",
            "tienda",
            "lugar",
        ]
    ):
        return {
            "intencion": "ubicacion",
            "busqueda": "",
            "requiere_asesor": False,
        }

    if any(
        palabra in texto
        for palabra in [
            "pago",
            "pagos",
            "transferencia",
            "bac",
            "lafise",
            "banpro",
            "tarjeta",
            "deposito",
        ]
    ):
        return {
            "intencion": "pagos",
            "busqueda": "",
            "requiere_asesor": False,
        }

    if any(
        palabra in texto
        for palabra in [
            "envio",
            "envios",
            "delivery",
            "entrega",
            "mandan",
            "cargo",
            "cargotrans",
            "correos",
            "encomienda",
        ]
    ):
        return {
            "intencion": "envios",
            "busqueda": "",
            "requiere_asesor": False,
        }

    if any(
        palabra in texto
        for palabra in [
            "promocion",
            "promociones",
            "descuento",
            "descuentos",
            "oferta",
            "ofertas",
            "rebaja",
        ]
    ):
        return {
            "intencion": "promociones",
            "busqueda": "",
            "requiere_asesor": False,
        }

    if any(
        palabra in texto
        for palabra in [
            "pedido",
            "pedir",
            "orden",
            "comprar",
            "apartar",
            "reservar",
        ]
    ):
        return {
            "intencion": "pedido",
            "busqueda": extraer_busqueda_producto_fallback(texto),
            "requiere_asesor": False,
        }

    if any(
        palabra in texto
        for palabra in [
            "precio",
            "precios",
            "cuanto",
            "cuesta",
            "vale",
            "cotizacion",
            "cotizar",
        ]
    ):
        return {
            "intencion": "precio",
            "busqueda": extraer_busqueda_producto_fallback(texto),
            "requiere_asesor": False,
        }

    if any(
        palabra in texto
        for palabra in [
            "disponible",
            "disponibilidad",
            "existencia",
            "stock",
            "cantidad",
            "unidades",
        ]
    ):
        return {
            "intencion": "stock",
            "busqueda": extraer_busqueda_producto_fallback(texto),
            "requiere_asesor": False,
        }

    return {
        "intencion": "producto",
        "busqueda": extraer_busqueda_producto_fallback(texto),
        "requiere_asesor": False,
    }


# =========================
# Control de consultas de precio
# =========================

def registrar_consulta_precio(cliente_id: str | None) -> int:
    llave = (cliente_id or "anonimo").strip() or "anonimo"
    _consultas_precio_por_cliente[llave] = (
        _consultas_precio_por_cliente.get(llave, 0) + 1
    )
    return _consultas_precio_por_cliente[llave]


def reiniciar_contador_precio(cliente_id: str | None) -> None:
    llave = (cliente_id or "anonimo").strip() or "anonimo"
    _consultas_precio_por_cliente.pop(llave, None)


def respuesta_asesor(motivo: str = "") -> str:
    if motivo:
        motivo = f" {motivo.strip()}"

    return (
        f"Claro, puedo ayudarte a contactar con un asesor humano.{motivo} "
        "Por ahora el enlace directo al departamento correspondiente está pendiente de configuración."
    ).strip()


# =========================
# Respuestas de información fija
# =========================

def respuesta_fija_por_intencion(intencion: str) -> str | None:
    respuestas = {
        "saludo": (
            f"¡Hola! Soy el asistente virtual de {NOMBRE_NEGOCIO}. "
            "Podés preguntarme por productos, precios, disponibilidad, horarios, ubicación, pagos o envíos."
        ),
        "agradecimiento": "¡Con gusto! Estoy para ayudarte.",
        "despedida": "¡Gracias por escribirnos! Que tengás un excelente día.",
        "horario": (
            "Nuestro horario de atención es de lunes a sábado, de 9:00 AM a 6:00 PM. "
            "No abrimos el 1 de enero, de jueves a domingo de Semana Santa ni el 25 de diciembre. "
            "Sí abrimos el 30 de mayo, 1 de mayo, 7 de noviembre y 26 de febrero."
        ),
        "ubicacion": (
            "Estamos ubicados en Barrio Central calle comercio, Bluefields, Nicaragua."
        ),
        "pagos": (
            "Aceptamos pagos en línea por transferencia a BAC, LAFISE y BANPRO."
        ),
        "envios": (
            "Para pedidos en línea, los envíos pueden realizarse por CargoTrans dependiendo del peso "
            "o por Correos de Nicaragua."
        ),
        "promociones": (
            "Por el momento el enlace de promociones y descuentos está pendiente. "
            "Podés consultarme por un producto específico y reviso si aparece con descuento."
        ),
        "asesor": respuesta_asesor(),
        "pedido": (
            "Puedo orientarte con productos, precios y disponibilidad. "
            "Para avanzar con un pedido, enviame el producto, cantidad y una referencia clara. "
            "Luego un asesor puede ayudarte a finalizarlo."
        ),
    }

    return respuestas.get(intencion)


def responder_informacion_negocio(intencion: str, mensaje_cliente: str) -> str | None:
    respuesta_base = respuesta_fija_por_intencion(intencion)

    if not respuesta_base:
        return None

    # Para datos críticos, Gemini solo pule el texto con datos controlados.
    # Si falla, se usa respuesta_base.
    datos_autorizados = {
        "intencion": intencion,
        "respuesta_base": respuesta_base,
        "negocio": INFO_NEGOCIO,
    }

    respuesta_gemini = redactar_respuesta_informacion_negocio(
        mensaje_cliente=mensaje_cliente,
        intencion=intencion,
        datos_autorizados=datos_autorizados,
    )

    return respuesta_gemini or respuesta_base


# =========================
# Productos
# =========================

def normalizar_resultado_productos(resultado: Any) -> tuple[list[dict], str | None]:
    if isinstance(resultado, dict):
        if resultado.get("ok") is False:
            return [], (
                resultado.get("detalle")
                or resultado.get("error")
                or "No se pudo consultar el inventario."
            )

        productos = resultado.get("productos") or resultado.get("data") or []

        if isinstance(productos, list):
            return productos, None

        return [], "La consulta de productos no devolvió una lista válida."

    if isinstance(resultado, list):
        return resultado, None

    if resultado is None:
        return [], None

    return [], "La consulta de productos devolvió un formato no reconocido."


def formatear_precio(precio: Any) -> str:
    precio_float = _a_float(precio)

    if precio_float is None:
        return "precio no disponible"

    return f"C$ {precio_float:,.2f}"


def formatear_cantidad(cantidad: Any, unidad: Any = "") -> str:
    cantidad_float = _a_float(cantidad)

    if cantidad_float is None:
        return "disponibilidad no indicada"

    if cantidad_float <= 0:
        return "sin disponibilidad indicada"

    unidad_texto = str(unidad or "").strip()

    if unidad_texto:
        return f"{cantidad_float:g} {unidad_texto} disponible(s)"

    return f"{cantidad_float:g} disponible(s)"


def formatear_respuesta_productos_python(
    busqueda: str,
    productos: list[dict],
    intencion: str = "producto",
) -> str:
    if not productos:
        return (
            f"No encontré coincidencias exactas para '{busqueda}'. "
            "Podés intentar con otro nombre, marca, categoría o referencia."
        )

    if intencion == "precio":
        respuesta = f"Encontré estas opciones relacionadas con '{busqueda}':\n\n"
    elif intencion == "stock":
        respuesta = f"Revisé disponibilidad relacionada con '{busqueda}':\n\n"
    else:
        respuesta = f"Encontré productos relacionados con '{busqueda}':\n\n"

    for producto in productos[:LIMITE_PRODUCTOS_RESPUESTA]:
        descripcion = (
            _obtener_primero(producto, "descripcion", "Descripcion", "nombre")
            or "Producto sin nombre"
        )
        categoria = (
            _obtener_primero(producto, "categoria", "Categoria")
            or "Sin categoría"
        )
        codigo = _obtener_primero(
            producto,
            "codigo",
            "barcode",
            "codigo_barra",
            "Barcode",
        )
        cantidad = _obtener_primero(
            producto,
            "cantidad",
            "Cantidad",
            "stock",
            "existencia",
        )
        unidad = _obtener_primero(producto, "unidad", "U/M", "um") or ""
        precio = _obtener_primero(
            producto,
            "precio_cor",
            "precio_cordobas",
            "precio",
            "PND C$",
        )
        descuento = _obtener_primero(
            producto,
            "porcentaje_descuento",
            "descuento",
            "Descuento",
        )

        respuesta += f"• {descripcion}\n"
        respuesta += f"  Categoría: {categoria}\n"

        if codigo:
            respuesta += f"  Referencia: {codigo}\n"

        respuesta += f"  Disponibilidad: {formatear_cantidad(cantidad, unidad)}\n"
        respuesta += f"  Precio: {formatear_precio(precio)}\n"

        descuento_float = _a_float(descuento)

        if descuento_float and descuento_float > 0:
            respuesta += f"  Descuento: {descuento_float:g}%\n"

        respuesta += "\n"

    respuesta += "¿Querés que revise otra marca, presentación o referencia?"
    return respuesta.strip()


def respuesta_sin_busqueda(intencion: str) -> str:
    if intencion == "precio":
        return (
            "Claro, puedo ayudarte con precios. "
            "Por favor enviame la referencia, nombre, marca o código del producto que querés consultar."
        )

    if intencion == "stock":
        return (
            "Claro, puedo revisar disponibilidad. "
            "Decime el nombre, marca, categoría o referencia del producto."
        )

    if intencion == "pedido":
        return (
            "Claro, puedo orientarte con un pedido. "
            "Enviame el producto, cantidad y referencia para revisar disponibilidad."
        )

    return (
        "Claro, puedo ayudarte a buscar productos. "
        "Decime el nombre, marca, categoría o referencia que querés consultar."
    )


def buscar_y_responder_productos(
    mensaje: str,
    busqueda: str,
    intencion: str,
) -> str:
    try:
        resultado_busqueda = buscar_productos(busqueda)
        productos, error_busqueda = normalizar_resultado_productos(resultado_busqueda)

        if error_busqueda:
            print(f"Error consultando productos: {error_busqueda}", flush=True)
            return (
                "Tuve un problema consultando los productos en el inventario. "
                "Por favor intentá de nuevo o consultá con un asesor."
            )

        respuesta_gemini = redactar_respuesta_productos(
            mensaje_cliente=mensaje,
            busqueda_usada=busqueda,
            productos=productos,
            intencion=intencion,
            limite=LIMITE_PRODUCTOS_RESPUESTA,
        )

        if respuesta_gemini:
            print("Respuesta final generada con Gemini", flush=True)
            return respuesta_gemini

        return formatear_respuesta_productos_python(
            busqueda,
            productos,
            intencion=intencion,
        )

    except Exception as error:
        print(f"Error consultando productos: {error}", flush=True)
        return (
            "Tuve un problema consultando los productos en el inventario. "
            "Por favor revisá la conexión con SQL Server."
        )


# =========================
# Entrada principal del bot
# =========================

def procesar_mensaje_cliente(
    mensaje: str,
    cliente_id: str | None = "anonimo",
) -> str:
    mensaje_limpio = limpiar_texto(mensaje or "")

    if not mensaje_limpio:
        return "No recibí ningún mensaje. ¿Podés escribir tu consulta?"

    interpretacion_gemini = interpretar_mensaje_cliente(mensaje)
    interpretacion = normalizar_interpretacion(interpretacion_gemini, mensaje_limpio)

    intencion = interpretacion.get("intencion", "otro")
    busqueda = interpretacion.get("busqueda", "")
    requiere_asesor = bool(interpretacion.get("requiere_asesor", False))

    print(
        (
            "Interpretación final: "
            f"intencion={intencion}, "
            f"busqueda={busqueda}, "
            f"requiere_asesor={requiere_asesor}"
        ),
        flush=True,
    )

    if requiere_asesor or intencion == "asesor":
        return respuesta_asesor()

    if intencion in {
        "saludo",
        "agradecimiento",
        "despedida",
        "horario",
        "ubicacion",
        "pagos",
        "envios",
        "promociones",
    }:
        respuesta_info = responder_informacion_negocio(intencion, mensaje)

        if respuesta_info:
            return respuesta_info

    if intencion == "pedido" and not busqueda:
        return (
            responder_informacion_negocio("pedido", mensaje)
            or respuesta_fija_por_intencion("pedido")
        )

    if intencion == "precio":
        consultas_precio = registrar_consulta_precio(cliente_id)

        if consultas_precio > LIMITE_CONSULTAS_PRECIO_ANTES_ASESOR:
            return respuesta_asesor(
                "Como ya realizaste varias consultas de precio, lo mejor es que un asesor continúe la atención."
            )

    if intencion in {"producto", "precio", "stock", "pedido"}:
        if not busqueda:
            return respuesta_sin_busqueda(intencion)

        return buscar_y_responder_productos(mensaje, busqueda, intencion)

    return (
        "Puedo ayudarte con productos, precios, disponibilidad, horarios, ubicación, pagos y envíos. "
        "Probá preguntándome por un producto, marca, categoría o referencia específica."
    )


def procesar_mensaje_prueba(
    mensaje: str,
    cliente_id: str | None = "test",
) -> str:
    """
    Función usada por /chat/test.
    Se conserva el nombre para no romper main.py ni el endpoint actual.
    """
    return procesar_mensaje_cliente(mensaje, cliente_id=cliente_id)