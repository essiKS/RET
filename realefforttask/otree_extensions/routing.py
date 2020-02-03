from django.conf.urls import url
from .consumers import TaskTracker
from otree.channels.routing import websocket_routes

websocket_routes += [
    url(r'^RETtasktracker/(?P<params>[\w,]+)/$',
        TaskTracker),
]
# for troubleshooting
print("websocket_routes="+str(websocket_routes))
