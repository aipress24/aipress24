import granian
from granian.constants import Interfaces, Loops

from . import settings

if __name__ == "__main__":
    print("Sqladmin app settings:\n")
    g = vars(settings)
    for k, v in g.items():
        if not k.isupper():
            continue
        print(f"{k}: {v}")
    print()

    granian.Granian(
        target="adminapp.main:create_app",
        factory=True,
        address="0.0.0.0",  # noqa: S104
        port=settings.APP_PORT,
        interface=Interfaces.ASGI,
        log_dictconfig={"root": {"level": "INFO"}} if not settings.DEBUG else {},
        log_level=settings.LOG_LEVEL,
        loop=Loops.uvloop,
        reload=True,
    ).serve()
