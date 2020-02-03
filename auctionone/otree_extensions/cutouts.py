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
