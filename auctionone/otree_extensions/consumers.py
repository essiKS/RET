# First changed
from channels.generic.websocket import JsonWebsocketConsumer
from auctionone.models import Player, Group, JobOffer
from otree.models import Participant
from otree.models_concrete import ParticipantToPlayerLookup
import logging
from django.conf import settings
import json
from asgiref.sync import async_to_sync
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
            # need to accept no matter what, so we can at least send an error message
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


class TaskTracker(GeneralTracker):
    unrestricted_when = 'ALWAYS_UNRESTRICTED'
    # url_pattern = r'^/auction_one_tasktracker/(?P<participant_code>.+)$'

    def clean_kwargs(self, params):
        participant_code = params
        participant = Participant.objects.get(code__exact=params)
        cur_page_index = participant._index_in_pages
        lookup = ParticipantToPlayerLookup.objects.get(participant=participant, page_index=cur_page_index)
        self.player_pk = lookup.player_pk
        return {
            'participant_code': participant_code,
        }

    def group_name(self, participant_code):
        return "RETplayer-" + str(participant_code)

    def RET_message(self, event):
        # Send message to WebSocket
        self.send(text_data=json.dumps(event))

    def post_connect(self, participant_code):
        # add them to the channel_layer
        self.room_group_name = self.group_name(participant_code)
        async_to_sync(self.channel_layer.group_add)(
            self.room_group_name,
            self.channel_name
        )

    def get_player(self):
        return Player.objects.get(id=self.player_pk)

    def post_receive_json(self, text, **kwargs):
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

    def clean_kwargs(self, params):
        group_id, participant_code = params.split(',')
        participant = Participant.objects.get(code__exact=participant_code)
        cur_page_index = participant._index_in_pages
        lookup = ParticipantToPlayerLookup.objects.get(participant=participant, page_index=cur_page_index)
        self.player_pk = lookup.player_pk
        return {
            'group_id': group_id,
            'participant_code': participant_code,
        }

    def group_name(self, group_id, participant_code):
        return "RETplayer-" + str(participant_code)

    def get_player(self):
        return Player.objects.get(id=self.player_pk)

    def get_group(self):
        player = self.get_player()
        return Group.objects.get(pk=player.group.pk)

    def connection_groups(self, **kwargs):
        group_name = self.get_group().get_channel_group_name()
        async_to_sync(self.channel_layer.group_add)(group_name, self.channel_name)
        personal_channel = self.get_player().get_personal_channel_name()
        async_to_sync(self.channel_layer.group_add)(personal_channel, self.channel_name)
        return [group_name, personal_channel]

    def post_connect(self, group_id, participant_code):
        # Needs to be defined - not sure what it does.
        group_name = self.get_group().get_channel_group_name()
        async_to_sync(self.channel_layer.group_add)(group_name, self.channel_name)

    def auction_message(self, event):
        # Handles the "auction.message" type when it's sent.
        self.send(text_data=json.dumps(event['grp_msg']))

    def personal_message(self, event):
        # Handles the personal.message" type when it's sent.
        self.send(text_data=json.dumps(event['reply']))

    def post_receive_json(self, text, **kwargs):
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
