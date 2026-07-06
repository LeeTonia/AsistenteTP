from app.utils.text_utils import limpiar_texto


def procesar_mensaje_prueba(mensaje: str) -> str:
    mensaje_limpio = limpiar_texto(mensaje)

    if not mensaje_limpio:
        return "No recibí ningún mensaje. ¿Podés escribir tu consulta?"

    if mensaje_limpio in ["hola", "buenas", "buenos dias", "buenas tardes", "buenas noches"]:
        return "¡Hola! Soy el asistente virtual del negocio. ¿En qué puedo ayudarte?"

    if (
        "hora" in mensaje_limpio
        or "horario" in mensaje_limpio
        or "abren" in mensaje_limpio
        or "cierran" in mensaje_limpio
    ):
        return "Nuestro horario de atención es de lunes a sábado, de 8:00 AM a 6:00 PM."

    if (
        "producto" in mensaje_limpio
        or "venden" in mensaje_limpio
        or "tienen" in mensaje_limpio
    ):
        return "Puedo ayudarte a consultar productos disponibles. Más adelante revisaré la base de datos del negocio."

    if (
        "precio" in mensaje_limpio
        or "cuesta" in mensaje_limpio
        or "vale" in mensaje_limpio
    ):
        return "Puedo ayudarte a consultar precios. Cuando conectemos la base de datos, responderé con precios reales."

    return "Entiendo tu consulta. En esta versión de prueba todavía estoy funcionando sin IA ni base de datos."