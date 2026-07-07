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

    mode = params.get("hub.mode") or params.get("hub_mode")
    token = params.get("hub.verify_token") or params.get("hub_verify_token")
    challenge = params.get("hub.challenge") or params.get("hub_challenge")

    token_recibido = (token or "").strip()
    token_esperado = (Config.WHATSAPP_VERIFY_TOKEN or "").strip()

    print("GET /webhook recibido:", dict(params), flush=True)
    print("Token recibido:", repr(token_recibido), flush=True)
    print("Token esperado:", repr(token_esperado), flush=True)

    if mode == "subscribe" and token_recibido == token_esperado:
        return Response(
            content=challenge or "",
            media_type="text/plain"
        )

    raise HTTPException(status_code=403, detail="Verify token incorrecto")


@router.post("/webhook")
async def recibir_webhook(request: Request):
    payload = await request.json()

    print(
        "POST /webhook recibido:",
        json.dumps(payload, indent=2, ensure_ascii=False),
        flush=True
    )

    # Ignorar payload genérico de prueba de Meta
    try:
        value = payload["entry"][0]["changes"][0]["value"]
        metadata = value.get("metadata", {})
        phone_number_id = metadata.get("phone_number_id")

        if phone_number_id == "123456123":
            print("Payload genérico de prueba de Meta ignorado.", flush=True)
            return {
                "ok": True,
                "detalle": "Payload genérico de prueba de Meta ignorado."
            }
    except Exception:
        pass

    mensaje = extraer_mensaje_entrante(payload)

    if not mensaje:
        return {
            "ok": True,
            "detalle": "Evento recibido, pero no era un mensaje de usuario."
        }

    numero_cliente = mensaje.get("numero")
    tipo = mensaje.get("tipo")
    texto = mensaje.get("texto") or ""

    if not numero_cliente:
        return {
            "ok": False,
            "detalle": "No se encontró el número del cliente en el payload."
        }

    if tipo != "text":
        resultado_envio = enviar_mensaje_whatsapp(
            numero_cliente,
            "Por ahora solo puedo responder mensajes de texto."
        )

        print("Resultado envío WhatsApp:", resultado_envio, flush=True)

        return {
            "ok": True,
            "detalle": f"Mensaje tipo {tipo} recibido, pero no procesado.",
            "resultado_envio": resultado_envio
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