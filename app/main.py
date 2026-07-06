from fastapi import FastAPI
from app.database.connection import probar_conexion_bd, obtener_drivers_odbc
from app.database.connection import probar_conexion_bd
from pydantic import BaseModel

from app.config import Config
from app.services.bot_service import procesar_mensaje_prueba


app = FastAPI(
    title="Asistente Virtual de WhatsApp",
    description="Bot para atención automática de clientes usando WhatsApp, SQL e IA.",
    version="1.0.0"
)


class MensajeEntrada(BaseModel):
    mensaje: str


@app.get("/")
def home():
    return {
        "status": "ok",
        "message": "Asistente virtual funcionando correctamente",
        "negocio": Config.NOMBRE_NEGOCIO
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "asistente-whatsapp"
    }


@app.post("/chat/test")
def chat_test(data: MensajeEntrada):
    respuesta = procesar_mensaje_prueba(data.mensaje)

    return {
        "mensaje_recibido": data.mensaje,
        "respuesta": respuesta
    }

@app.get("/db/test")
def db_test():
    return probar_conexion_bd()

@app.get("/db/drivers")
def db_drivers():
    return obtener_drivers_odbc()