# myproject/routing.py
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from drivers import routing as ride_routing

application = ProtocolTypeRouter({
    # Django still handles traditional HTTP requests
    "http": None,

    # WebSocket handler
    "websocket": AuthMiddlewareStack(
        URLRouter(
            ride_routing.websocket_urlpatterns
        )
    ),
})
