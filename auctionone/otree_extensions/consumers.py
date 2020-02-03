# First changed
from consumers import _OTreeJsonWebsocketConsumer
from auctionone.models import Player, Group, JobOffer
from otree.models import Participant
from realefforttask.models import Player
from otree.models import Participant
from otree.models_concrete import ParticipantToPlayerLookup
import logging
# ADDED
import json
from asgiref.sync import async_to_sync

logger = logging.getLogger(__name__)

ALWAYS_UNRESTRICTED = 'ALWAYS_UNRESTRICTED'
UNRESTRICTED_IN_DEMO_MODE = 'UNRESTRICTED_IN_DEMO_MODE'

print("consumers started")


class GeneralTracker(_OTreeJsonWebsocketConsumer):
    unrestricted_when = 'ALWAYS_UNRESTRICTED'

    #CHANGED

    # ADDED
    def group_name(self, participant_code):
        print("group name ", participant_code)
        return "RETplayer-" + str(participant_code)

    # ADDED
    def RET_message(self, event):
        print("RET message")
        # Send message to WebSocket
        self.send(text_data=json.dumps(event))

    def Auction_message(self,event):
        print("Auction message")

    # ADDED
    def post_connect(self, participant_code):
        # add them to the channel_layer
        print("post connect")
        self.room_group_name = self.group_name(participant_code)
        async_to_sync(self.channel_layer.group_add)(
            self.room_group_name,
            self.channel_name
        )

    def get_player(self):
        return Player.objects.get(id=self.player_pk)

################################################
# TRANSFORMATION LEFT HERE
################################################


class TaskTracker(GeneralTracker):
    unrestricted_when = 'ALWAYS_UNRESTRICTED'
    #url_pattern = r'^/auction_one_tasktracker/(?P<participant_code>.+)$'

    def clean_kwargs(self, params):
        participant_code = params
        print("all kwargs", participant_code)
        participant = Participant.objects.get(code__exact=params)
        cur_page_index = participant._index_in_pages
        lookup = ParticipantToPlayerLookup.objects.get(participant=participant, page_index=cur_page_index)
        self.player_pk = lookup.player_pk
        return {
            'participant_code': participant_code,
        }

    # CHANGE TO post receive json
    def post_receive_json(self, text, participant_code):
        player = self.get_player()
        answer = text.get('answer')
        if answer:
            old_task = player.get_or_create_task()
            old_task.answer = answer
            old_task.save()
            if old_task.answer == old_task.correct_answer:
                feedback = "Your answer was correct."
            else:
                feedback = "Your previous answer " + old_task.answer + " was wrong, the correct answer was " + \
                           old_task.correct_answer + "."
            new_task = player.get_or_create_task()

            reply = {
                'type': 'RET_message',
                'task_body':  new_task.html_body,
                'num_tasks_correct': player.num_tasks_correct,
                'num_tasks_total': player.num_tasks_total,
                'feedback': feedback,
            }

            async_to_sync(self.channel_layer.group_send)(
                self.room_group_name,
                reply
            )


class AuctionTracker(GeneralTracker):
    unrestricted_when = 'ALWAYS_UNRESTRICTED'
    #url_pattern = r'^/auction_channel/(?P<participant_code>.+)$'

    def clean_kwargs(self, params):
        group_id, participant_code = params.split(',')
        print("all kwargs", group_id, participant_code)
        participant = Participant.objects.get(code__exact=params)
        cur_page_index = participant._index_in_pages
        lookup = ParticipantToPlayerLookup.objects.get(participant=participant, page_index=cur_page_index)
        self.player_pk = lookup.player_pk
        return {
            'group_id': int(group_id),
            'participant_code': participant_code,
        }

    def connection_groups(self, **kwargs):
        group_name = self.get_group().get_channel_group_name()
        personal_channel = self.get_player().get_personal_channel_name()
        return [group_name, personal_channel]

    def get_group(self):
        player = self.get_player()
        return Group.objects.get(pk=player.group.pk)

    # CHANGE TO post receive json
    def post_receive_json(self, text, participant_code):
        self.clean_kwargs()
        player = self.get_player()
        if text.get('offer_made') and player.role() == 'employer':
            wage_offer = text['wage_offer']
            open_offers = player.offer_made.filter(worker__isnull=True)
            if open_offers.exists():
                recent_offer = open_offers.first()
                recent_offer.amount = wage_offer
                recent_offer.save()
            else:
                player.offer_made.create(amount=wage_offer, group=player.group)

        if text.get('offer_accepted') and player.role() == 'worker':
            offer_id = text['offer_id']
            try:
                offer = JobOffer.objects.get(id=offer_id, worker__isnull=True)
                offer.worker = player
                offer.save()
            except JobOffer.DoesNotExist:
                return
