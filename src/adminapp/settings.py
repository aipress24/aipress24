from granian.log import LogLevels
from starlette.config import Config

config = Config(".env")

# For Heroku and similar PaaS
APP_PORT = config("PORT", cast=int, default=8000)

# App-specific settings
DEBUG = config("DEBUG", cast=bool, default=False)
LOG_LEVEL = config("LOG_LEVEL", cast=LogLevels, default=LogLevels.info)
SQLALCHEMY_DATABASE_URI = config(
    "SQLALCHEMY_DATABASE_URI",
    cast=str,
    default="postgresql+asyncpg://localhost/aipress24",
)
