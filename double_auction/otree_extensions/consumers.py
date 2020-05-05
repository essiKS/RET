# this replaced: from channels.generic.websockets import JsonWebsocketConsumer
from consumers import _OTreeJsonWebsocketConsumer
from double_auction.models import Player, Group
from double_auction.exceptions import NotEnoughFunds, NotEnoughItemsToSell
from otree.models import Participant
from otree.models_concrete import ParticipantToPlayerLookup
import logging
import json
from asgiref.sync import async_to_sync

logger = logging.getLogger(__name__)

ALWAYS_UNRESTRICTED = 'ALWAYS_UNRESTRICTED'
UNRESTRICTED_IN_DEMO_MODE = 'UNRESTRICTED_IN_DEMO_MODE'


class GeneralTracker(_OTreeJsonWebsocketConsumer):
    unrestricted_when = 'ALWAYS_UNRESTRICTED'

    # CHANGED
    # ADDED
    def group_name(self, participant_code, page_index):
        player = Player.objects.get(participant__code=participant_code)
        name = player.get_personal_channel_name()
        return str(name)

    def get_player(self):
        print("get_player")
        return Player.objects.get(id=self.player_pk)

    def RET_message(self, event):
        # Send message to WebSocket
        self.send(text_data=json.dumps(event))

    def post_connect(self, participant_code, page_index):
        # add them to the channel_layer
        self.room_group_name = self.group_name(participant_code, page_index)
        async_to_sync(self.channel_layer.group_add)(
            self.room_group_name,
            self.channel_name
        )


class MarketTracker(GeneralTracker):
    print("Market Tracker Started")
    unrestricted_when = 'ALWAYS_UNRESTRICTED'
    # url_pattern = r'^/market_channel/(?P<participant_code>.+)/(?P<page_index>\d+)$'

    def clean_kwargs(self, participant_code, page_index):
        participant = Participant.objects.get(code__exact=participant_code)
        cur_page_index = participant._index_in_pages
        #lookup = ParticipantToPlayerLookup.objects.get(participant=participant, page_index=cur_page_index)
        #participant = Participant.objects.get(code__exact=self.kwargs['participant_code'])
        #cur_page_index = self.kwargs['page_index']
        #lookup = ParticipantToPlayerLookup.objects.get(participant=participant, page_index=cur_page_index)
        #self.player_pk = lookup.player_pk
        lookup = ParticipantToPlayerLookup.objects.get(participant=participant, page_index=cur_page_index)
        self.player_pk = lookup.player_pk
        print("participant_code", participant_code)
        print("cur_page_index", cur_page_index)
        return {
            'participant_code': participant_code,
            'page_index': cur_page_index
        }

    def connection_groups(self, **kwargs):
        print("connection_groups started")
        group_name = self.get_group().get_channel_group_name()
        async_to_sync(self.channel_layer.group_add)(group_name, self.channel_name)
        personal_channel = self.get_player().get_personal_channel_name()
        async_to_sync(self.channel_layer.group_add)(personal_channel, self.channel_name)
        print("connection groups over")
        return [group_name, personal_channel]

    def get_player(self):
        print("get player")
        return Player.objects.get(pk=self.player_pk)

    def get_group(self):
        print("get group")
        player = self.get_player()
        return Group.objects.get(pk=player.group.pk)

    def auction_message(self, event):
        print("auction message")
        # Handles the "auction.message" type when it's sent.
        print("grp_msg", event)
        self.send(text_data=json.dumps(event['grp_msg']))

    def personal_message(self, event):
        print("personal message")
        print("reply event", event)
        self.send(text_data=json.dumps(event['reply']))

    def post_receive_json(self, text, **kwargs):
        # removing text=None, bytes=None,
        print("receive")
        msg = text
        player = self.get_player()
        group = self.get_group()
        # Some ideas:
        # Each seller in the beginning has slots (like a deposit cells) filled with goods from his repo.
        # Each buyer also has empty slots (deposit cells) to fill in.
        # Each seller slot is associated with a certain cost of production.
        # Each buyer slot is associated with a certain value of owning the item in it (sounds strange)
        # buyer costs are associated with increasing cost of production (?)
        # seller values with diminishing marginal value
        # when two persons make a contract, an item is moved from  seller's cell to buyer's cell.

        if msg['action'] == 'new_statement':
            if player.role() == 'buyer':
                try:
                    bid = player.bids.create(price=msg['price'], quantity=msg['quantity'])

                except NotEnoughFunds:
                    logger.warning('not enough funds')
            else:
                try:
                    ask = player.asks.create(price=msg['price'], quantity=msg['quantity'])

                except NotEnoughItemsToSell:
                    logger.warning('not enough items to sell')

        if msg['action'] == 'retract_statement':
            to_del = player.get_last_statement()
            if to_del:
                to_del.delete()

        spread = group.get_spread_html()
        for p in group.get_players():
            reply = {
                'asks': p.get_asks_html(),
                'bids': p.get_bids_html()
            }
            async_to_sync(self.channel_layer.group_send)(
                p.get_personal_channel_name(),
                {
                    "type": "personal.message",
                    "reply": reply
                }
            )
            #self.group_send(p.get_personal_channel_name(), {'asks': p.get_asks_html(),
            #                                                'bids': p.get_bids_html()})
        group_msg = {
            'spread': spread
        }
        for p in group.get_players():
            async_to_sync(self.channel_layer.group_send)(
                group.get_channel_group_name(),
                {
                    "type": "auction.message",
                    "group_msp": group_msg
                }

            )
        #self.group_send(group.get_channel_group_name(), {
        #    'spread': spread,
        #})
        reply = {}
        last_statement = player.get_last_statement()
        if last_statement:
            reply['last_statement'] = last_statement.as_dict()
        reply['form'] = player.get_form_html()
        for p in group.get_players():
            async_to_sync(self.channel_layer.group_send)(
                p.get_personal_channel_name(),
                {
                    "type": "personal.message",
                    "reply": reply
                }
            )
        #self.send(msg)

