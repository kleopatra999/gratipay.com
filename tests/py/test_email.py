from __future__ import absolute_import, division, print_function, unicode_literals

import json
import sys

import urllib
from pytest import raises

from gratipay.exceptions import CannotRemovePrimaryEmail, EmailTaken, EmailNotVerified
from gratipay.exceptions import TooManyEmailAddresses, Throttled, EmailAlreadyVerified
from gratipay.exceptions import EmailNotOnFile, ProblemChangingEmail
from gratipay.testing import P, Harness
from gratipay.testing.email import QueuedEmailHarness, SentEmailHarness
from gratipay.models.participant import email as _email
from gratipay.utils import encode_for_querystring
from gratipay.cli import queue_branch_email as _queue_branch_email


class Alice(QueuedEmailHarness):

    def setUp(self):
        QueuedEmailHarness.setUp(self)
        self.alice = self.make_participant('alice', claimed_time='now')

    def add(self, participant, address, _flush=False):
        participant.start_email_verification(address)
        nonce = participant.get_email(address).nonce
        r = participant.verify_email(address, nonce)
        assert r == _email.VERIFICATION_SUCCEEDED
        if _flush:
            self.app.email_queue.flush()


class TestEndpoints(Alice):

    def hit_email_spt(self, action, address, user='alice', package_ids=[], should_fail=False):
        f = self.client.PxST if should_fail else self.client.POST

        # Hack to work around Aspen test client limitations.
        data = [ ('action', action)
               , ('address', address)
                ] + [('package_id', str(p)) for p in package_ids]
        body = urllib.urlencode(data)

        response = f( '/~alice/emails/modify.json'
                    , body=body
                    , content_type=b'application/x-www-form-urlencoded'
                    , auth_as=user
                    , HTTP_ACCEPT_LANGUAGE=b'en'
                     )
        if issubclass(response.__class__, (Throttled, ProblemChangingEmail)):
            response.render_body({'_': lambda a: a})
        return response

    def verify_email(self, email, nonce, username='alice', should_fail=False):
        # Email address is encoded in url.
        url = '/~%s/emails/verify.html?email2=%s&nonce=%s'
        url %= (username, encode_for_querystring(email), nonce)
        f = self.client.GxT if should_fail else self.client.GET
        return f(url, auth_as=username)

    def verify_and_change_email(self, old_email, new_email, username='alice', _flush=True):
        self.hit_email_spt('add-email', old_email)
        nonce = P(username).get_email(old_email).nonce
        self.verify_email(old_email, nonce)
        self.hit_email_spt('add-email', new_email)
        if _flush:
            self.app.email_queue.flush()

    def test_participant_can_start_email_verification(self):
        response = self.hit_email_spt('add-email', 'alice@gratipay.com')
        assert json.loads(response.body) == 'Check your inbox for a verification link.'

    def test_starting_email_verification_triggers_verification_email(self):
        self.hit_email_spt('add-email', 'alice@gratipay.com')
        assert self.count_email_messages() == 1
        last_email = self.get_last_email()
        assert last_email['to'] == 'alice <alice@gratipay.com>'
        expected = "We've received a request to connect alice@gratipay.com to the alice account"
        assert expected in last_email['body_text']

    def test_email_address_is_encoded_in_sent_verification_link(self):
        address = 'alice@gratipay.com'
        encoded = encode_for_querystring(address)
        self.hit_email_spt('add-email', address)
        last_email = self.get_last_email()
        assert "~alice/emails/verify.html?email2="+encoded in last_email['body_text']

    def test_verification_email_doesnt_contain_unsubscribe(self):
        self.hit_email_spt('add-email', 'alice@gratipay.com')
        last_email = self.get_last_email()
        assert "To stop receiving" not in last_email['body_text']

    def test_verifying_second_email_sends_verification_notice(self):
        self.verify_and_change_email('alice1@example.com', 'alice2@example.com', _flush=False)
        assert self.count_email_messages() == 3
        last_email = self.get_last_email()
        self.app.email_queue.flush()
        assert last_email['to'] == 'alice <alice1@example.com>'
        expected = "We are connecting alice2@example.com to the alice account on Gratipay"
        assert expected in last_email['body_text']

    def test_post_anon_returns_401(self):
        response = self.hit_email_spt('add-email', 'anon@example.com', user=None, should_fail=True)
        assert response.code == 401

    def test_post_with_no_at_symbol_is_400(self):
        response = self.hit_email_spt('add-email', 'gratipay.com', should_fail=True)
        assert response.code == 400

    def test_post_with_no_period_symbol_is_400(self):
        response = self.hit_email_spt('add-email', 'test@gratipay', should_fail=True)
        assert response.code == 400

    def test_post_with_long_address_is_okay(self):
        response = self.hit_email_spt('add-email', ('a'*242) + '@example.com')
        assert response.code == 200

    def test_post_with_looooong_address_is_400(self):
        response = self.hit_email_spt('add-email', ('a'*243) + '@example.com', should_fail=True)
        assert response.code == 400

    def test_post_too_quickly_is_400(self):
        self.hit_email_spt('add-email', 'alice@example.com')
        self.hit_email_spt('add-email', 'alice+a@example.com')
        self.hit_email_spt('add-email', 'alice+b@example.com')
        response = self.hit_email_spt('add-email', 'alice+c@example.com', should_fail=True)
        assert response.code == 400
        assert 'too quickly' in response.body

    def test_verify_email_without_adding_email(self):
        response = self.verify_email('', 'sample-nonce')
        assert 'Bad Info' in response.body

    def test_verify_email_wrong_nonce(self):
        self.hit_email_spt('add-email', 'alice@example.com')
        nonce = 'fake-nonce'
        r = self.alice.verify_email('alice@gratipay.com', nonce)
        assert r == _email.VERIFICATION_FAILED
        self.verify_email('alice@example.com', nonce)
        expected = None
        actual = P('alice').email_address
        assert expected == actual

    def test_verify_email_a_second_time_returns_redundant(self):
        address = 'alice@example.com'
        self.hit_email_spt('add-email', address)
        nonce = self.alice.get_email(address).nonce
        r = self.alice.verify_email(address, nonce)
        r = self.alice.verify_email(address, nonce)
        assert r == _email.VERIFICATION_REDUNDANT

    def test_verify_email_expired_nonce(self):
        address = 'alice@example.com'
        self.hit_email_spt('add-email', address)
        self.db.run("""
            UPDATE emails
               SET verification_start = (now() - INTERVAL '25 hours')
             WHERE participant_id = %s;
        """, (self.alice.id,))
        nonce = self.alice.get_email(address).nonce
        r = self.alice.verify_email(address, nonce)
        assert r == _email.VERIFICATION_EXPIRED
        actual = P('alice').email_address
        assert actual == None

    def test_verify_email(self):
        self.hit_email_spt('add-email', 'alice@example.com')
        nonce = self.alice.get_email('alice@example.com').nonce
        self.verify_email('alice@example.com', nonce)
        expected = 'alice@example.com'
        actual = P('alice').email_address
        assert expected == actual

    def test_email_verification_is_backwards_compatible(self):
        """Test email verification still works with unencoded email in verification link.
        """
        self.hit_email_spt('add-email', 'alice@example.com')
        nonce = self.alice.get_email('alice@example.com').nonce
        url = '/~alice/emails/verify.html?email=alice@example.com&nonce='+nonce
        self.client.GET(url, auth_as='alice')
        expected = 'alice@example.com'
        actual = P('alice').email_address
        assert expected == actual

    def test_verified_email_is_not_changed_after_update(self):
        self.verify_and_change_email('alice@example.com', 'alice@example.net')
        expected = 'alice@example.com'
        actual = P('alice').email_address
        assert expected == actual

    def test_get_emails(self):
        self.verify_and_change_email('alice@example.com', 'alice@example.net')
        emails = self.alice.get_emails()
        assert len(emails) == 2

    def test_verify_email_after_update(self):
        self.verify_and_change_email('alice@example.com', 'alice@example.net')
        nonce = self.alice.get_email('alice@example.net').nonce
        self.verify_email('alice@example.net', nonce)
        expected = 'alice@example.com'
        actual = P('alice').email_address
        assert expected == actual

    def test_nonce_is_not_reused_when_resending_email(self):
        self.hit_email_spt('add-email', 'alice@example.com')
        nonce1 = self.alice.get_email('alice@example.com').nonce
        self.hit_email_spt('resend', 'alice@example.com')
        nonce2 = self.alice.get_email('alice@example.com').nonce
        assert nonce1 != nonce2

    def test_emails_page_shows_emails(self):
        self.verify_and_change_email('alice@example.com', 'alice@example.net')
        body = self.client.GET("/~alice/emails/", auth_as="alice").body
        assert 'alice@example.com' in body
        assert 'alice@example.net' in body

    def test_set_primary(self):
        self.verify_and_change_email('alice@example.com', 'alice@example.net')
        self.verify_and_change_email('alice@example.net', 'alice@example.org')
        self.hit_email_spt('set-primary', 'alice@example.com')

    def test_cannot_set_primary_to_unverified(self):
        with self.assertRaises(EmailNotVerified):
            self.hit_email_spt('set-primary', 'alice@example.com')

    def test_remove_email(self):
        # Can remove unverified
        self.hit_email_spt('add-email', 'alice@example.com')
        self.hit_email_spt('remove', 'alice@example.com')

        # Can remove verified
        self.verify_and_change_email('alice@example.com', 'alice@example.net')
        self.verify_and_change_email('alice@example.net', 'alice@example.org')
        self.hit_email_spt('remove', 'alice@example.net')

        # Cannot remove primary
        with self.assertRaises(CannotRemovePrimaryEmail):
            self.hit_email_spt('remove', 'alice@example.com')


    def test_participant_can_verify_a_package_along_with_email(self):
        foo = self.make_package(name='foo', emails=['alice@gratipay.com'])
        response = self.hit_email_spt( 'start-verification'
                                     , 'alice@gratipay.com'
                                     , package_ids=[foo.id]
                                      )
        assert json.loads(response.body) == 'Check your inbox for a verification link.'
        assert self.db.all('select package_id from claims order by package_id') == [foo.id]

    def test_participant_cant_verify_packages_with_add_email_or_resend(self):
        foo = self.make_package(name='foo', emails=['alice@gratipay.com'])
        for action in ('add-email', 'resend'):
            assert self.hit_email_spt( action
                                     , 'alice@gratipay.com'
                                     , package_ids=[foo.id]
                                     , should_fail=True
                                      ).code == 400

    def test_participant_can_verify_multiple_packages_along_with_email(self):
        package_ids = [self.make_package(name=name, emails=['alice@gratipay.com']).id
                       for name in ('foo', 'bar', 'baz', 'buz')]
        response = self.hit_email_spt( 'start-verification'
                                     , 'alice@gratipay.com'
                                     , package_ids=package_ids
                                      )
        assert json.loads(response.body) == 'Check your inbox for a verification link.'
        assert self.db.all('select package_id from claims order by package_id') == package_ids

    def test_package_verification_fails_if_email_not_listed(self):
        foo = self.make_package()
        response = self.hit_email_spt( 'start-verification'
                                     , 'bob@gratipay.com'
                                     , package_ids=[foo.id]
                                     , should_fail=True
                                      )
        assert response.code == 400
        assert self.db.all('select package_id from claims order by package_id') == []

    def test_package_verification_fails_package_id_is_garbage(self):
        response = self.hit_email_spt( 'start-verification'
                                     , 'bob@gratipay.com'
                                     , package_ids=['cheese monkey']
                                     , should_fail=True
                                      )
        assert response.code == 400
        assert self.db.all('select package_id from claims order by package_id') == []


class TestFunctions(Alice):

    def test_cannot_update_email_to_already_verified(self):
        bob = self.make_participant('bob', claimed_time='now')
        self.add(self.alice, 'alice@gratipay.com')

        with self.assertRaises(EmailTaken):
            bob.start_email_verification('alice@gratipay.com')
            nonce = bob.get_email('alice@gratipay.com').nonce
            bob.verify_email('alice@gratipay.com', nonce)

        email_alice = P('alice').email_address
        assert email_alice == 'alice@gratipay.com'

    def test_html_escaping(self):
        self.alice.start_email_verification("foo'bar@example.com")
        last_email = self.get_last_email()
        assert 'foo&#39;bar' in last_email['body_html']
        assert '&#39;' not in last_email['body_text']

    def test_queueing_email_is_throttled(self):
        self.app.email_queue.put(self.alice, "verification")
        self.app.email_queue.put(self.alice, "branch")
        self.app.email_queue.put(self.alice, "verification-notice")
        raises(Throttled, self.app.email_queue.put, self.alice, "branch")

    def test_only_user_initiated_messages_count_towards_throttling(self):
        self.app.email_queue.put(self.alice, "verification")
        self.app.email_queue.put(self.alice, "verification", _user_initiated=False)
        self.app.email_queue.put(self.alice, "branch")
        self.app.email_queue.put(self.alice, "branch", _user_initiated=False)
        self.app.email_queue.put(self.alice, "verification-notice")
        self.app.email_queue.put(self.alice, "verification-notice", _user_initiated=False)
        raises(Throttled, self.app.email_queue.put, self.alice, "branch")

    def test_flushing_queue_resets_throttling(self):
        self.add(self.alice, 'alice@example.com')
        assert self.app.email_queue.flush() == 1
        self.app.email_queue.put(self.alice, "verification")
        self.app.email_queue.put(self.alice, "branch")
        self.app.email_queue.put(self.alice, "verification-notice")
        assert self.app.email_queue.flush() == 3
        self.app.email_queue.put(self.alice, "verification-notice")


class FlushEmailQueue(SentEmailHarness):

    def test_can_flush_an_email_from_the_queue(self):
        larry = self.make_participant('larry', email_address='larry@example.com')
        self.app.email_queue.put(larry, "verification")

        assert self.db.one("SELECT spt_name FROM email_queue") == "verification"
        self.app.email_queue.flush()
        assert self.count_email_messages() == 1
        last_email = self.get_last_email()
        assert last_email['to'] == 'larry <larry@example.com>'
        expected = "connect larry"
        assert expected in last_email['body_text']
        assert self.db.one("SELECT spt_name FROM email_queue") is None

    def test_flushing_an_email_without_address_just_skips_it(self):
        larry = self.make_participant('larry')
        self.app.email_queue.put(larry, "verification")

        assert self.db.one("SELECT spt_name FROM email_queue") == "verification"
        self.app.email_queue.flush()
        assert self.count_email_messages() == 0
        assert self.db.one("SELECT spt_name FROM email_queue") is None


class TestGetRecentlyActiveParticipants(QueuedEmailHarness):

    def check(self):
        return _queue_branch_email.get_recently_active_participants(self.db)

    def test_gets_recently_active_participants(self):
        alice = self.make_participant_with_exchange('alice')
        assert self.check() == [alice]

    def test_ignores_participants_with_no_exchanges(self):
        self.make_participant('alice', claimed_time='now', email_address='a@example.com')
        assert self.check() == []

    def test_ignores_participants_with_no_recent_exchanges(self):
        self.make_participant_with_exchange('alice')
        self.db.run("UPDATE exchanges SET timestamp = timestamp - '181 days'::interval")
        assert self.check() == []

    def test_keeps_participants_straight(self):
        alice = self.make_participant_with_exchange('alice')
        bob = self.make_participant_with_exchange('bob')
        self.make_participant_with_exchange('carl')
        self.db.run("UPDATE exchanges SET timestamp = timestamp - '181 days'::interval "
                    "WHERE participant='carl'")
        self.make_participant('dana', claimed_time='now', email_address='d@example.com')
        assert self.check() == [alice, bob]


class TestQueueBranchEmail(QueuedEmailHarness):

    def queue_branch_email(self, username, _argv=None, _input=None, _print=None):
        _argv = ['', username] if _argv is None else _argv
        _input = _input or (lambda prompt: 'y')
        stdout, stderr = [], []
        def _print(string, file=None):
            buf = stderr if file is sys.stderr else stdout
            buf.append(str(string))
        _print = _print or (lambda *a, **kw: None)
        try:
            _queue_branch_email.main(_argv, _input, _print, self.app)
        except SystemExit as exc:
            retcode = exc.args[0]
        else:
            retcode = 0
        return retcode, stdout, stderr


    def test_is_fine_with_no_participants(self):
        retcode, output, errors = self.queue_branch_email('all')
        assert retcode == 0
        assert output == ['Okay, you asked for it!', '0']
        assert errors == []
        assert self.count_email_messages() == 0

    def test_queues_for_one_participant(self):
        alice = self.make_participant_with_exchange('alice')
        retcode, output, errors = self.queue_branch_email('all')
        assert retcode == 0
        assert output == [ 'Okay, you asked for it!'
                         , '1'
                         , 'spotcheck: alice@example.com (alice={})'.format(alice.id)
                          ]
        assert errors == ['   1 queuing for alice@example.com (alice={})'.format(alice.id)]
        assert self.count_email_messages() == 1

    def test_queues_for_two_participants(self):
        alice = self.make_participant_with_exchange('alice')
        bob = self.make_participant_with_exchange('bob')
        retcode, output, errors = self.queue_branch_email('all')
        assert retcode == 0
        assert output[:2] == ['Okay, you asked for it!', '2']
        assert errors == [ '   1 queuing for alice@example.com (alice={})'.format(alice.id)
                         , '   2 queuing for bob@example.com (bob={})'.format(bob.id)
                          ]
        assert self.count_email_messages() == 2

    def test_constrains_to_one_participant(self):
        self.make_participant_with_exchange('alice')
        bob = self.make_participant_with_exchange('bob')
        retcode, output, errors = self.queue_branch_email('bob')
        assert retcode == 0
        assert output == [ 'Okay, just bob.'
                         , '1'
                         , 'spotcheck: bob@example.com (bob={})'.format(bob.id)
                          ]
        assert errors == ['   1 queuing for bob@example.com (bob={})'.format(bob.id)]
        assert self.count_email_messages() == 1

    def test_bails_if_told_to(self):
        retcode, output, errors = self.queue_branch_email('all', _input=lambda prompt: 'n')
        assert retcode == 1
        assert output == []
        assert errors == []
        assert self.count_email_messages() == 0


class StartEmailVerification(Alice):

    def test_starts_email_verification(self):
        self.alice.start_email_verification('alice@example.com')
        assert self.get_last_email()['subject'] == 'Connect to alice on Gratipay?'

    def test_raises_if_already_verified(self):
        self.add(self.alice, 'alice@example.com')
        raises(EmailAlreadyVerified, self.alice.start_email_verification, 'alice@example.com')

    def test_raises_if_already_taken(self):
        self.add(self.alice, 'alice@example.com')
        bob = self.make_participant('bob', claimed_time='now')
        raises(EmailTaken, bob.start_email_verification, 'alice@example.com')

    def test_maxes_out_at_10(self):
        for i in range(10):
            self.add(self.alice, 'alice-{}@example.com'.format(i), _flush=True)
        raises(TooManyEmailAddresses, self.alice.start_email_verification, 'alice@example.com')

    def test_can_include_packages_in_verification(self):
        foo = self.make_package()
        self.alice.start_email_verification('alice@example.com', foo)
        assert self.get_last_email()['subject'] == 'Connect to alice on Gratipay?'
        assert self.db.one('select package_id from claims') == foo.id

    def test_can_claim_package_even_when_address_already_verified(self):
        self.add(self.alice, 'alice@example.com')
        foo = self.make_package()
        self.alice.start_email_verification('alice@example.com', foo)
        assert self.get_last_email()['subject'] == \
                                               'Connecting alice@example.com to alice on Gratipay.'
        assert self.db.one('select package_id from claims') == foo.id

    def test_claiming_package_with_verified_address_doesnt_count_against_max(self):
        for i in range(10):
            self.add(self.alice, 'alice-{}@example.com'.format(i), _flush=True)
        foo = self.make_package(emails=['alice-4@example.com'])
        self.alice.start_email_verification('alice-4@example.com', foo)
        assert self.db.one('select package_id from claims') == foo.id

    def test_claiming_package_with_someone_elses_verified_address_is_a_no_go(self):
        self.add(self.alice, 'alice@example.com')
        bob = self.make_participant('bob', claimed_time='now')
        foo = self.make_package()
        raises(EmailTaken, bob.start_email_verification, 'alice@example.com', foo)

    def test_claiming_package_with_an_address_not_on_file_is_a_no_go(self):
        foo = self.make_package(emails=['bob@example.com'])
        raises(EmailNotOnFile, self.alice.start_email_verification, 'alice@example.com', foo)

    def test_restarting_verification_clears_old_claims(self):
        foo = self.make_package()
        start = lambda: self.alice.start_email_verification('alice@example.com', foo)
        nonce = lambda: self.db.one('select nonce from claims')
        start()
        nonce1 = nonce()
        start()
        assert nonce1 != nonce()


class RemoveEmail(Alice):

    def test_removing_email_clears_claims(self):
        foo = self.make_package()
        self.alice.start_email_verification('alice@example.com', foo)
        claims = lambda: self.db.all('select package_id from claims')
        assert claims() == [foo.id]
        self.alice.remove_email('alice@example.com')
        assert claims() == []


class GetEmailVerificationLink(Harness):

    def get_claims(self):
        return self.db.all('''
            SELECT name
              FROM claims c
              JOIN packages p
                ON c.package_id = p.id
          ORDER BY name
        ''')

    def test_returns_a_link(self):
        with self.db.get_cursor() as c:
            alice = self.make_participant('alice')
            link = alice.get_email_verification_link(c, 'alice@example.com')
        assert link.startswith('/~alice/emails/verify.html?email2=YWxpY2VAZXhhbXBsZS5jb20~&nonce=')

    def test_makes_no_claims_by_default(self):
        with self.db.get_cursor() as c:
            self.make_participant('alice').get_email_verification_link(c, 'alice@example.com')
        assert self.get_claims() == []

    def test_makes_a_claim_if_asked_to(self):
        alice = self.make_participant('alice')
        foo = self.make_package()
        with self.db.get_cursor() as c:
            alice.get_email_verification_link(c, 'alice@example.com', foo)
        assert self.get_claims() == ['foo']

    def test_can_make_two_claims(self):
        alice = self.make_participant('alice')
        foo = self.make_package()
        bar = self.make_package(name='bar')
        with self.db.get_cursor() as c:
            alice.get_email_verification_link(c, 'alice@example.com', foo, bar)
        assert self.get_claims() == ['bar', 'foo']

    def test_will_happily_make_competing_claims(self):
        foo = self.make_package()
        with self.db.get_cursor() as c:
            self.make_participant('alice').get_email_verification_link(c, 'alice@example.com', foo)
        with self.db.get_cursor() as c:
            self.make_participant('bob').get_email_verification_link(c, 'bob@example.com', foo)
        assert self.get_claims() == ['foo', 'foo']

    def test_adds_events(self):
        foo = self.make_package()
        with self.db.get_cursor() as c:
            self.make_participant('alice').get_email_verification_link(c, 'alice@example.com', foo)
        events = [e.payload['action'] for e in self.db.all('select * from events order by id')]
        assert events == ['add', 'start-claim']
