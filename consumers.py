# 3.2.2020 copied the version from the packages
# Thus this was otree.channels.consumers.py a while ago.
import json
import logging
import django.db
import django.utils.timezone
import traceback
import time
import urllib.parse
from asgiref.sync import sync_to_async
from channels.generic.websocket import (
    JsonWebsocketConsumer,
    AsyncJsonWebsocketConsumer,
    WebsocketConsumer,
)
from django.core.signing import Signer, BadSignature
import otree.session
from otree.channels.utils import get_chat_group
from otree.common import get_models_module
from otree.models import Participant, Session
from otree.models_concrete import (
    CompletedGroupWaitPage,
    CompletedSubsessionWaitPage,
    ChatMessage,
    WaitPagePassage,
)
import otree.channels.utils as channel_utils
from otree.models_concrete import ParticipantRoomVisit, BrowserBotsLauncherSessionCode
from otree.room import ROOM_DICT
import otree.bots.browser
from otree.export import export_wide, export_app
import io
import base64
import datetime
from django.conf import settings
from django.shortcuts import reverse
from otree.views.admin import CreateSessionForm
from otree.session import SESSION_CONFIGS_DICT
from channels.db import database_sync_to_async

# From the oTree cite: "If you are building your app for long-term stability, beware of importing anything from
# otree.channels into your code. Like anything outside of otree.api, it may be removed abruptly."
# Hence copying it here.

logger = logging.getLogger(__name__)

ALWAYS_UNRESTRICTED = 'ALWAYS_UNRESTRICTED'
UNRESTRICTED_IN_DEMO_MODE = 'UNRESTRICTED_IN_DEMO_MODE'


class _OTreeJsonWebsocketConsumer(JsonWebsocketConsumer):
    """
    This is not public API, might change at any time.
    """
    #ADDED FROM THE OTHER CHRIS

    def group_send_channel(self, type: str, groups=None, **event):
        for group in (groups or self.groups):
            channel_utils.sync_group_send(group, {'type': type, **event})

    def clean_kwargs(self, **kwargs):
        '''
        subclasses should override if the route receives a comma-separated params arg.
        otherwise, this just passes the route kwargs as is (usually there is just one).
        The output of this method is passed to self.group_name(), self.post_connect,
        and self.pre_disconnect, so within each class, all 3 of those methods must
        accept the same args (or at least take a **kwargs wildcard, if the args aren't used)
        '''
        return kwargs

    def group_name(self, **kwargs):
        raise NotImplementedError()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cleaned_kwargs = self.clean_kwargs(**self.scope['url_route']['kwargs'])
        group_name = self.group_name(**self.cleaned_kwargs)
        self.groups = [group_name] if group_name else []

    def connection_groups(self, **kwargs):
        group_name = self.group_name(**self.cleaned_kwargs)
        return [group_name]

    unrestricted_when = ''

    # there is no login_required for channels
    # so we need to make our own
    # https://github.com/django/channels/issues/1241
    def connect(self):
        AUTH_LEVEL = settings.AUTH_LEVEL

        auth_required = (
            (not self.unrestricted_when)
            and AUTH_LEVEL
            or self.unrestricted_when == UNRESTRICTED_IN_DEMO_MODE
            and AUTH_LEVEL == 'STUDY'
        )

        if auth_required and not self.scope['user'].is_staff:
            msg = 'rejected un-authenticated access to websocket path {}'.format(
                self.scope['path']
            )
            logger.warning(msg)
            # consider also self.accept() then send error message then self.close(code=1008)
            # this only affects otree core websockets.
        else:
            # need to accept no matter what, so we can at least send
            # an error message
            self.accept()
            self.post_connect(**self.cleaned_kwargs)

    def post_connect(self, **kwargs):
        pass

    def disconnect(self, message, **kwargs):
        self.pre_disconnect(**self.cleaned_kwargs)

    def pre_disconnect(self, **kwargs):
        pass

    def receive_json(self, content, **etc):
        self.post_receive_json(content, **self.cleaned_kwargs)

    def post_receive_json(self, content, **kwargs):
        pass


class _OTreeAsyncJsonWebsocketConsumer(AsyncJsonWebsocketConsumer):
    """
    This is not public API, might change at any time.
    """

    def clean_kwargs(self, **kwargs):
        '''
        subclasses should override if the route receives a comma-separated params arg.
        otherwise, this just passes the route kwargs as is (usually there is just one).
        The output of this method is passed to self.group_name(), self.post_connect,
        and self.pre_disconnect, so within each class, all 3 of those methods must
        accept the same args (or at least take a **kwargs wildcard, if the args aren't used)
        '''
        return kwargs

    def group_name(self, **kwargs):
        raise NotImplementedError()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cleaned_kwargs = self.clean_kwargs(**self.scope['url_route']['kwargs'])
        group_name = self.group_name(**self.cleaned_kwargs)
        self.groups = [group_name] if group_name else []

    unrestricted_when = ''

    # there is no login_required for channels
    # so we need to make our own
    # https://github.com/django/channels/issues/1241
    async def connect(self):

        AUTH_LEVEL = settings.AUTH_LEVEL

        auth_required = (
            (not self.unrestricted_when)
            and AUTH_LEVEL
            or self.unrestricted_when == UNRESTRICTED_IN_DEMO_MODE
            and AUTH_LEVEL == 'STUDY'
        )

        if auth_required and not self.scope['user'].is_staff:
            msg = 'rejected un-authenticated access to websocket path {}'.format(
                self.scope['path']
            )
            logger.warning(msg)
            # consider also self.accept() then send error message then self.close(code=1008)
            # this only affects otree core websockets.
        else:
            # need to accept no matter what, so we can at least send
            # an error message
            await self.accept()
            await self.post_connect(**self.cleaned_kwargs)

    async def post_connect(self, **kwargs):
        pass

    async def disconnect(self, message, **kwargs):
        await self.pre_disconnect(**self.cleaned_kwargs)

    async def pre_disconnect(self, **kwargs):
        pass

    async def receive_json(self, content, **etc):
        await self.post_receive_json(content, **self.cleaned_kwargs)

    async def post_receive_json(self, content, **kwargs):
        pass
