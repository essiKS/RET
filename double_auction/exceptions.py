import json
# E: replacing the following "from channels import Group as ChannelGroup" with
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
channel_layer = get_channel_layer()


class NotEnoughFunds(Exception):
    def __init__(self, owner):
        # channel = ChannelGroup(owner.get_personal_channel_name())
        # channel.send({'text': json.dumps({'warning': 'You do not have enough funds to make this bid.'
        #                                              ' Please change the amount.'})})
        channel = owner.get_personal_channel_name()
        reply = {
            'warning': 'You do not have enough funds to make this bid. Please change the amount.'
        }
        async_to_sync(channel_layer.group_send)(channel,
                                                {
                                                    'type': "personal.message",
                                                    'reply': reply
                                                })
        super().__init__('Not enough money to create a new bid of this amount')


class NotEnoughItemsToSell(Exception):
    def __init__(self, owner):
        # channel = ChannelGroup(owner.get_personal_channel_name())
        # channel.send({'text': json.dumps({'warning': 'You do not have not enough items to make this ask.'
        #                                            ''
        #                                             })})
        channel = owner.get_personal_channel_name()
        reply = {
            'warning': 'You do not have not enough items to make this ask.'
        }
        async_to_sync(channel_layer.group_send)(channel,
                                                {
                                                    'type': "personal.message",
                                                    'reply': reply
                                                })
        super().__init__('Not enough items to sell')
