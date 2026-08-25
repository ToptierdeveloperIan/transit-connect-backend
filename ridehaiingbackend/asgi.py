import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from drivers import routing as driver_routing  # change if your app is named differently

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ridehaiingbackend.settings')

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack(
        URLRouter(
            driver_routing.websocket_urlpatterns
        )
    ),
})
