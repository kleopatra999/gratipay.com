# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function, unicode_literals

import braintree

from ..exchange_route import ExchangeRoute
from ...billing.instruments import CreditCard
from ...utils import is_card_expiring


class Routes(object):
    """Participants have payment routes to get money into and out of Gratipay.
    """

    def get_paypal_error(self):
        """Return the error associated with the participant's PayPal account, or ``None``.
        """
        return getattr(ExchangeRoute.from_network(self, 'paypal'), 'error', None)

    def get_credit_card_error(self):
        """Return the error associated with the participant's credit card, or ``None``.
        """
        return getattr(ExchangeRoute.from_network(self, 'braintree-cc'), 'error', None)

    @property
    def has_payout_route(self):
        """A boolean computed property, whether the participant has a known-working payout route.
        """
        return bool(self.get_payout_routes(good_only=True))

    def get_payout_routes(self, good_only=False, cursor=None):
        """Return a list of payout routes. If ``good_only`` evaluates to rue then only
        known-working payout routes are included.
        """
        out = []
        for network in ('paypal',):
            route = ExchangeRoute.from_network(self, network, cursor)
            if not route:
                continue
            if good_only and route.error:
                continue
            out.append(route)
        return out

    def get_braintree_account(self):
        """Fetch or create a braintree account for this participant.
        """
        if not self.braintree_customer_id:
            customer = braintree.Customer.create({
                'custom_fields': {'participant_id': self.id}
            }).customer

            r = self.db.one("""
                UPDATE participants
                   SET braintree_customer_id=%s
                 WHERE id=%s
                   AND braintree_customer_id IS NULL
             RETURNING id
            """, (customer.id, self.id))

            if not r:
                return self.get_braintree_account()
        else:
            customer = braintree.Customer.find(self.braintree_customer_id)
        return customer

    def get_braintree_token(self):
        """Return the braintree token for this participant.
        """
        account = self.get_braintree_account()

        token = braintree.ClientToken.generate({'customer_id': account.id})
        return token

    def credit_card_expiring(self):
        """Return a boolean, whether the participant's credit card is set to expire soon.
        """
        route = ExchangeRoute.from_network(self, 'braintree-cc')
        if not route:
            return
        card = CreditCard.from_route(route)
        year, month = card.expiration_year, card.expiration_month
        if not (year and month):
            return False
        return is_card_expiring(int(year), int(month))
