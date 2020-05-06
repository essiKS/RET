from consumers import _OTreeJsonWebsocketConsumer
from otree.models import Participant
from realefforttask.models import Player
from otree.models_concrete import ParticipantToPlayerLookup
import logging
# ADDED
import json
from asgiref.sync import async_to_sync

logger = logging.getLogger(__name__)

ALWAYS_UNRESTRICTED = 'ALWAYS_UNRESTRICTED'
UNRESTRICTED_IN_DEMO_MODE = 'UNRESTRICTED_IN_DEMO_MODE'


class TaskTracker(_OTreeJsonWebsocketConsumer):
    unrestricted_when = ALWAYS_UNRESTRICTED

    def clean_kwargs(self, params):
        participant_code = params
        participant = Participant.objects.get(code__exact=params)
        cur_page_index = participant._index_in_pages
        lookup = ParticipantToPlayerLookup.objects.get(participant=participant, page_index=cur_page_index)
        self.player_pk = lookup.player_pk
        return {
            'participant_code': participant_code,
        }

    # Gives the group name for each participant
    def group_name(self, participant_code):
        return "RETplayer-" + str(participant_code)

    # Handles the RET.message
    def RET_message(self, event):
        # Send message to WebSocket
        self.send(text_data=json.dumps(event))

    # ADDED
    def post_connect(self, participant_code):
        # add the groups to the channel_layer
        self.room_group_name = self.group_name(participant_code)
        async_to_sync(self.channel_layer.group_add)(
            self.room_group_name,
            self.channel_name
        )

    def get_player(self):
        return Player.objects.get(id=self.player_pk)

    # CHANGE TO post receive json
    def post_receive_json(self, text, participant_code, **kwargs):
        player = self.get_player()
        answer = text.get('answer')
        if answer:
            old_task = player.get_or_create_task()
            old_task.answer = answer
            old_task.save()
            new_task = player.get_or_create_task()
            reply = {
                'type': 'RET_message',
                'task_body':  new_task.html_body,
                'num_tasks_correct': player.num_tasks_correct,
                'num_tasks_total': player.num_tasks_total,
            }

            async_to_sync(self.channel_layer.group_send)(
                self.room_group_name,
                reply
            )
    # Haven't been able to make this work yet.
    #def connect(self, message, **kwargs):
    #    logger.info(f'Connected: {self.kwargs["participant_code"]}')