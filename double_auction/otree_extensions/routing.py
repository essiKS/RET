from django.conf.urls import url
from .consumers import MarketTracker
from otree.channels.routing import websocket_routes

websocket_routes += [
    url(r'^market_channel/(?P<participant_code>.+)/(?P<page_index>\d+)$',
        MarketTracker)]

print("websocket_routes="+str(websocket_routes))

# don't start the rul r' with a slash.

# MarketTracker.url_pattern
