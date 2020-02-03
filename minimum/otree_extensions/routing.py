from django.conf.urls import url
from .consumers import Minimum
from otree.channels.routing import websocket_routes

websocket_routes += [
    url(r'^minimum/(?P<params>[\w,]+)/$',
        Minimum),
]
# for troubleshooting
# print("websocket_routes="+str(websocket_routes))
