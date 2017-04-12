# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function, unicode_literals

import mock
from gratipay.exceptions import OutOfOptions
from gratipay.models.package import NPM, Package
from gratipay.testing import Harness
from psycopg2 import IntegrityError
from pytest import raises


class TestPackage(Harness):

    def test_can_be_instantiated_from_id(self):
        p = self.make_package()
        assert Package.from_id(p.id).id == p.id

    def test_can_be_instantiated_from_names(self):
        self.make_package()
        assert Package.from_names(NPM, 'foo').name == 'foo'


class Linking(Harness):

    def link(self):
        alice = self.make_participant('alice')
        package = self.make_package()
        with self.db.get_cursor() as c:
            team = package.get_or_create_linked_team(c, alice)
        return alice, package, team

    def test_package_team_is_none(self):
        assert self.make_package().team is None

    def test_team_package_is_none(self):
        assert self.make_team().package is None

    def test_can_link_to_a_new_team(self):
        _, package, team = self.link()
        assert team.package == package
        assert package.team == team

    def test_linking_is_idempotent(self):
        alice, package, team = self.link()
        for i in range(5):
            with self.db.get_cursor() as c:
                assert package.get_or_create_linked_team(c, alice) == team

    def test_team_can_only_be_linked_from_one_package(self):
        _ , _, team = self.link()
        bar = self.make_package(name='bar')
        raises( IntegrityError
              , self.db.run
              , 'UPDATE packages SET team_id=%s WHERE id=%s'
              , (team.id, bar.id)
               )

    def test_linked_team_takes_package_name(self):
        _, _, team = self.link()
        assert team.slug == 'foo'

    def test_linking_team_tries_other_names(self):
        self.make_team(name='foo')
        _, _, team = self.link()
        assert team.slug == 'foo-1'

    @mock.patch('gratipay.models.package.uuid')
    def test_linking_team_gives_up_on_names_eventually(self, uuid):
        self.make_team(name='foo')                  # take `foo`
        for i in range(1, 10):
            self.make_team(name='foo-{}'.format(i)) # take `foo-{1-9}`
        self.make_team(name='deadbeef')             # take `deadbeef`(!)
        uuid.uuid4.return_value = 'deadbeef'        # force-try `deadbeef`
        raises(OutOfOptions, self.link)

    def test_linked_team_takes_package_description(self):
        _, _, team = self.link()
        assert team.product_or_service == 'Foo fooingly.'

    def test_linked_team_has_remote_package_url_as_homepage(self):
        _, _, team = self.link()
        assert team.homepage == 'https://www.npmjs.com/package/foo'

    def test_review_url_doesnt_get_set_here(self):
        _, _, team = self.link()
        assert team.review_url is None
