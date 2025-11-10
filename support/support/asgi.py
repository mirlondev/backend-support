# support/asgi.py
import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "support.settings")
django.setup()  # ⚠️ Initialise les apps

from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from channels.security.websocket import AllowedHostsOriginValidator
from tcikets import routing  # import direct, pas d'__import__

from support.middleware import JWTAuthMiddleware

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "support.settings")

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": JWTAuthMiddleware(
        URLRouter(routing.websocket_urlpatterns)
    ),
})
