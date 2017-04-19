# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function, unicode_literals

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

    def test_package_team_is_none(self):
        foo = self.make_package()
        assert foo.team is None

    def test_team_package_is_none(self):
        foo = self.make_team()
        assert foo.package is None

    def test_can_link_to_a_new_team(self):
        alice = self.make_participant('alice')
        foo = self.make_package()
        with self.db.get_cursor() as c:
            foo.ensure_team(c, alice)
            team = foo._load_team(c)
        assert team.package == foo
        assert foo.team == team
        return alice, foo, team

    def test_linking_is_idempotent(self):
        alice, package, _team = self.test_can_link_to_a_new_team()
        for i in range(5):
            with self.db.get_cursor() as c:
                package.ensure_team(c, alice)
                team = package._load_team(c)
            assert team == _team

    def test_team_can_only_be_linked_from_one_package(self):
        alice, package, team = self.test_can_link_to_a_new_team()
        bar = self.make_package(name='bar')
        raises( IntegrityError
              , self.db.run
              , 'UPDATE packages SET team_id=%s WHERE id=%s'
              , (team.id, bar.id)
               )
