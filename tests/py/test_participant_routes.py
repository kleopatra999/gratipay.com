# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function, unicode_literals

from gratipay.testing import Harness
from gratipay.models.exchange_route import ExchangeRoute


class GetPayoutRoutes(Harness):

    def test_gets_payout_routes(self):
        alice = self.make_participant('alice', claimed_time='now')
        route = ExchangeRoute.insert(alice, 'paypal', 'alice@example.com')
        assert alice.get_payout_routes() == [route]

    def test_gets_only_good_routes(self):
        alice = self.make_participant('alice', claimed_time='now')
        route = ExchangeRoute.insert(alice, 'paypal', 'alice@example.com')
        route.update_error('so erroneous')
        assert alice.get_payout_routes(good_only=True) == []

    def test_scopes_to_cursor(self):
        alice = self.make_participant('alice', claimed_time='now')
        with self.db.get_cursor() as cursor:
            route = ExchangeRoute.insert(alice, 'paypal', 'alice@example.com', cursor=cursor)
            assert alice.get_payout_routes() == []
            assert alice.get_payout_routes(cursor=cursor) == [route]
        assert alice.get_payout_routes() == [route]
