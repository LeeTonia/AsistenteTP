import requests

from app.config import Config


def extraer_mensaje_entrante(payload: dict) -> dict | None:
    try:
        entry = payload.get("entry", [])[0]
        changes = entry.get("changes", [])[0]
        value = changes.get("value", {})

        mensajes = value.get("messages", [])

        if not mensajes:
            return None

        mensaje = mensajes[0]
        numero_cliente = mensaje.get("from")
        tipo_mensaje = mensaje.get("type")

        if tipo_mensaje == "text":
            texto = mensaje.get("text", {}).get("body", "")

            return {
                "numero": numero_cliente,
                "tipo": "text",
                "texto": texto
            }

        return {
            "numero": numero_cliente,
            "tipo": tipo_mensaje,
            "texto": None
        }

    except Exception as error:
        print(f"Error extrayendo mensaje de WhatsApp: {error}")
        return None


def enviar_mensaje_whatsapp(numero_destino: str, mensaje: str) -> dict:
    if not Config.WHATSAPP_TOKEN:
        return {
            "ok": False,
            "detalle": "WHATSAPP_TOKEN no está configurado."
        }

    if not Config.WHATSAPP_PHONE_NUMBER_ID:
        return {
            "ok": False,
            "detalle": "WHATSAPP_PHONE_NUMBER_ID no está configurado."
        }

    url = (
        f"https://graph.facebook.com/{Config.WHATSAPP_API_VERSION}/"
        f"{Config.WHATSAPP_PHONE_NUMBER_ID}/messages"
    )

    headers = {
        "Authorization": f"Bearer {Config.WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }

    data = {
        "messaging_product": "whatsapp",
        "to": numero_destino,
        "type": "text",
        "text": {
            "preview_url": False,
            "body": mensaje[:4000]
        }
    }

    try:
        respuesta = requests.post(
            url,
            headers=headers,
            json=data,
            timeout=20
        )

        try:
            cuerpo = respuesta.json()
        except Exception:
            cuerpo = respuesta.text

        return {
            "ok": respuesta.ok,
            "status_code": respuesta.status_code,
            "respuesta_meta": cuerpo
        }

    except Exception as error:
        return {
            "ok": False,
            "detalle": f"Error enviando mensaje por WhatsApp: {str(error)}"
        }