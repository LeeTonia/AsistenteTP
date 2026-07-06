from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse

from app.config import Config
from app.services.chat_service import responder_chat
from app.services.whatsapp_service import (
    enviar_mensaje_whatsapp,
    extraer_mensaje_entrante
)


router = APIRouter(
    prefix="/whatsapp",
    tags=["WhatsApp"]
)


@router.get("/webhook")
def verificar_webhook(
    hub_mode: str | None = Query(default=None, alias="hub.mode"),
    hub_verify_token: str | None = Query(default=None, alias="hub.verify_token"),
    hub_challenge: str | None = Query(default=None, alias="hub.challenge")
):
    if (
        hub_mode == "subscribe"
        and hub_verify_token == Config.WHATSAPP_VERIFY_TOKEN
        and hub_challenge is not None
    ):
        return PlainTextResponse(content=hub_challenge)

    raise HTTPException(
        status_code=403,
        detail="Token de verificación inválido."
    )


@router.post("/webhook")
async def recibir_webhook(request: Request):
    payload = await request.json()

    mensaje_entrante = extraer_mensaje_entrante(payload)

    if not mensaje_entrante:
        return {
            "ok": True,
            "detalle": "Evento recibido, pero no había mensaje procesable."
        }

    numero_cliente = mensaje_entrante.get("numero")
    tipo = mensaje_entrante.get("tipo")
    texto = mensaje_entrante.get("texto")

    if not numero_cliente:
        return {
            "ok": True,
            "detalle": "Evento sin número de cliente."
        }

    if tipo != "text":
        respuesta = (
            "Gracias por tu mensaje. Por ahora puedo responder consultas por texto. "
            "Podés escribirme el nombre, código, color o tipo de producto que buscás."
        )

        envio = enviar_mensaje_whatsapp(numero_cliente, respuesta)

        return {
            "ok": True,
            "tipo": tipo,
            "respuesta_enviada": envio
        }

    resultado_chat = responder_chat(texto)
    respuesta_cliente = resultado_chat.get(
        "respuesta",
        "Disculpá, no pude procesar tu mensaje en este momento."
    )

    envio = enviar_mensaje_whatsapp(numero_cliente, respuesta_cliente)

    return {
        "ok": True,
        "tipo": "text",
        "mensaje_cliente": texto,
        "respuesta_bot": respuesta_cliente,
        "respuesta_enviada": envio
    }