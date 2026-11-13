import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-insecure-change-me")
    ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "ZYELEO")
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "@Saberps4")
    FILEWALE_API = os.getenv("FILEWALE_API", "https://filewale.com/api/v1")
    BKASH_NUMBER = os.getenv("BKASH_NUMBER", "01739124825")
    NAGAD_NUMBER = os.getenv("NAGAD_NUMBER", "01739124825")
    ENC_KEY = os.getenv("ENC_KEY", "")
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024
    BRAND = "FILEWALE PREMIUM"