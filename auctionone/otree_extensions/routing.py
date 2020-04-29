from django.conf.urls import url
from .consumers import TaskTracker, AuctionTracker
from otree.channels.routing import websocket_routes

websocket_routes += [
    url(r'^auction_one_tasktracker/(?P<params>[\w,]+)/$',
        TaskTracker),
    url(r'^auction_channel/(?P<params>[\w,]+)/$',
        AuctionTracker)
]
# If troubleshooting, test with this:
# print("websocket_routes="+str(websocket_routes))
