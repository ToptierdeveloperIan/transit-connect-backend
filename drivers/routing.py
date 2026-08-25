from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/driver-bookingupdates/$', consumers.DriverConsumer.as_asgi()),
    re_path(r'ws/driver/(?P<driver_id>\d+)/location/$', consumers.DriverConsumer.as_asgi()),
    re_path(r'ws/user/(?P<driver_id>\d+)/track/$', consumers.UserConsumer.as_asgi()),


]
