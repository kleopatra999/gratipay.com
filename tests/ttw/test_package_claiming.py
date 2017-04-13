# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function, unicode_literals

from gratipay.testing import BrowserHarness


class TestSendConfirmationLink(BrowserHarness):

    def check(self, choice=0):
        self.make_participant('bob', claimed_time='now')
        self.sign_in('bob')
        self.visit('/on/npm/foo/')
        self.css('label')[0].click() # activate select
        self.css('label')[choice].click()
        self.css('button')[0].click()
        assert self.has_element('.notification.notification-success', 1)
        assert self.has_text('Check your inbox for a verification link.')
        return self.db.one('select address from claims c join emails e on c.nonce = e.nonce')

    def test_appears_to_work(self):
        self.make_package()
        assert self.check() == 'alice@example.com'

    def test_works_when_there_are_multiple_addresses(self):
        self.make_package(emails=['alice@example.com', 'bob@example.com'])
        assert self.check() == 'alice@example.com'

    def test_can_send_to_second_email(self):
        self.make_package(emails=['alice@example.com', 'bob@example.com'])
        assert self.check(choice=1) == 'bob@example.com'
