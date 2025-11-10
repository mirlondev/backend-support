# routing.py
from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/ticket/(?P<ticket_id>[^/]+)/chat/$', consumers.TicketChatConsumer.as_asgi()),
]