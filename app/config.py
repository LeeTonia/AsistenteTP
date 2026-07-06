import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    NOMBRE_NEGOCIO = os.getenv("NOMBRE_NEGOCIO", "Negocio")

    APP_HOST = os.getenv("APP_HOST", "0.0.0.0")
    APP_PORT = int(os.getenv("APP_PORT", "8000"))

    DATABASE_URL = os.getenv("DATABASE_URL", "")
    SQL_CONNECTION_STRING = os.getenv("SQL_CONNECTION_STRING", "")

    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

    WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN", "")
    WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
    WHATSAPP_VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "")

    TASA_CAMBIO_DOLAR = float(os.getenv("TASA_CAMBIO_DOLAR", "36.62"))
    MOSTRAR_PRECIO_USD = os.getenv("MOSTRAR_PRECIO_USD", "true").lower() == "true"