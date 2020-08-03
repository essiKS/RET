from channels.generic.websocket import JsonWebsocketConsumer
from minimum.models import Player
from asgiref.sync import async_to_sync
from django.conf import settings
import json
import logging
logger = logging.getLogger(__name__)

ALWAYS_UNRESTRICTED = 'ALWAYS_UNRESTRICTED'
UNRESTRICTED_IN_DEMO_MODE = 'UNRESTRICTED_IN_DEMO_MODE'

class GeneralTracker(JsonWebsocketConsumer):
    # Imposes a structure
    logger = logging.getLogger(__name__)

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
                and AUTH_LEVEL == 'STUDY')

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


class Minimum(GeneralTracker):
    unrestricted_when = ALWAYS_UNRESTRICTED

    # General variables for example for identification cleaned
    def clean_kwargs(self, params):
        player_id = params
        return {
            'player_id': int(player_id),
        }

    # Channel group name defined
    def group_name(self, player_id):
        print("group name ", player_id)
        return "minimum_player-" + str(player_id)

    # Handles the minimum.message sent through other files (for example models.py) - not used in this app?
    def minimum_message(self, event):
        print("minimum message", event)
        # Send message to WebSocket
        self.send(text_data=json.dumps(event))

    # ADDED
    def post_connect(self, player_id):
        # add a new channel layer
        print("post connect")
        self.room_group_name = self.group_name(player_id)
        async_to_sync(self.channel_layer.group_add)(
            self.room_group_name,
            self.channel_name
        )

    def pre_disconnect(self, player_id):
        print("pre_disconnect activated")
        # remove the player from their channel_layer
        self.room_group_name = self.group_name(player_id)
        async_to_sync(self.channel_layer.group_discard)(
            self.room_group_name,
            self.channel_name
        )

    def post_receive_json(self, text, player_id, **kwargs):
        # using the keyword we get the player
        p = Player.objects.get(id=player_id)
        # we receive the answer
        answer = text.get('answer')
        # if the answer is not empty....
        if answer:
            # ... then we increase the counter of total tasks attempted by 1
            p.num_tasks_total += 1
            # if the answer is correct...
            if int(answer) == p.last_correct_answer:
                # ... we increase the counter of correctly submitted tasks by 1
                p.num_tasks_correct += 1
            #  we create a new task
            p.create_task()
            # IMPORTANT: save the changes in the database
            p.save()
            # and send a new task with updated counters back to a user
            reply = {
                'type': 'minimum_message',
                'task_body': p.task_body,
                'num_tasks_correct': p.num_tasks_correct,
                'num_tasks_total': p.num_tasks_total,
            }
            async_to_sync(self.channel_layer.group_send)(
                self.room_group_name,
                reply
            )
