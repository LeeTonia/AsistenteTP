from fastapi import APIRouter, Request, HTTPException, Response
import json

from app.config import Config
from app.services.bot_service import procesar_mensaje_prueba
from app.services.whatsapp_service import (
    extraer_mensaje_entrante,
    enviar_mensaje_whatsapp,
)

router = APIRouter(tags=["WhatsApp Webhook"])


@router.get("/webhook")
async def verificar_webhook(request: Request):
    params = request.query_params

    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    print("GET /webhook recibido:", dict(params), flush=True)

    if mode == "subscribe" and token == Config.WHATSAPP_VERIFY_TOKEN:
        return Response(content=challenge or "", media_type="text/plain")

    raise HTTPException(status_code=403, detail="Verify token incorrecto")


@router.post("/webhook")
async def recibir_webhook(request: Request):
    payload = await request.json()

    print("POST /webhook recibido:", json.dumps(payload, indent=2, ensure_ascii=False), flush=True)

    mensaje = extraer_mensaje_entrante(payload)

    if not mensaje:
        return {
            "ok": True,
            "detalle": "Evento recibido, pero no era un mensaje de usuario."
        }

    numero_cliente = mensaje.get("numero")
    tipo = mensaje.get("tipo")
    texto = mensaje.get("texto")

    if tipo != "text":
        enviar_mensaje_whatsapp(
            numero_cliente,
            "Por ahora solo puedo responder mensajes de texto."
        )
        return {
            "ok": True,
            "detalle": f"Mensaje tipo {tipo} recibido, pero no procesado."
        }

    respuesta_bot = procesar_mensaje_prueba(texto)

    resultado_envio = enviar_mensaje_whatsapp(numero_cliente, respuesta_bot)

    print("Resultado envío WhatsApp:", resultado_envio, flush=True)

    return {
        "ok": True,
        "mensaje_recibido": texto,
        "respuesta_enviada": respuesta_bot,
        "resultado_envio": resultado_envio
    }