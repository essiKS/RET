# CHANGED: copied the consumers from otree.channels into the parent folder
from consumers import _OTreeJsonWebsocketConsumer
# recopied the above line

# we need to import our Player model to get and put some data there
from minimum.models import Player
from asgiref.sync import async_to_sync

# ADDED
import json
import logging
logger = logging.getLogger(__name__)

ALWAYS_UNRESTRICTED = 'ALWAYS_UNRESTRICTED'
UNRESTRICTED_IN_DEMO_MODE = 'UNRESTRICTED_IN_DEMO_MODE'

print("consumers started")


class Minimum(_OTreeJsonWebsocketConsumer):
    # this is the path that should correspond to the one we use in our javascript file
    # the 'player_id' keyword helps us to retrieve the corresponding player data from the database
    # url_pattern = r'^/minimum/(?P<player_id>[0-9]+)$'
    print("TaskTracker started")
    # ADDED
    unrestricted_when = ALWAYS_UNRESTRICTED

    # ADDED
    def clean_kwargs(self, params):
        player_id = params
        print("all kwargs", player_id)
        return {
            'player_id': int(player_id),
        }

    # ADDED
    def group_name(self, player_id):
        print("group name ", player_id)
        return "minimum_player-" + str(player_id)

    # ADDED
    def minimum_message(self, event):
        print("minimum message", event)
        # Send message to WebSocket
        self.send(text_data=json.dumps(event))

    # ADDED
    def post_connect(self, player_id):
        # add them to the channel_layer
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

    # the following 'receive' method is executed automatically by Channels when a message is received from a client
    #def receive(self, text=None, bytes=None, **kwargs):
    # changed to post_receive_json

    def post_receive_json(self, text, player_id):
        print("post_receive_json activated")
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
