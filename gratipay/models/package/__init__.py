# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function, unicode_literals

import uuid

from gratipay.models.team import Team
from gratipay.exceptions import OutOfOptions
from postgres.orm import Model


NPM = 'npm'  # We are starting with a single package manager. If we see
             # traction we will expand.


class Package(Model):
    """Represent a gratipackage. :-)

    Packages are entities on open source package managers; `npm
    <https://www.npmjs.com/>`_ is the only one we support so far. Each package
    on npm has a page on Gratipay with an URL of the form ``/on/npm/foo/``.
    Packages can be claimed by Gratipay participants, at which point we create
    a :py:class:`~gratipay.models.team.Team` for them under the hood so they
    can start accepting payments.

    """

    typname = 'packages'

    def __eq__(self, other):
        if not isinstance(other, Package):
            return False
        return self.id == other.id

    def __ne__(self, other):
        if not isinstance(other, Package):
            return True
        return self.id != other.id


    @property
    def url_path(self):
        """The path part of the URL for this package on Gratipay.
        """
        return '/on/{}/{}/'.format(self.package_manager, self.name)


    # Constructors
    # ============

    @classmethod
    def from_id(cls, id):
        """Return an existing package based on id.
        """
        return cls.db.one("SELECT packages.*::packages FROM packages WHERE id=%s", (id,))

    @classmethod
    def from_names(cls, package_manager, name):
        """Return an existing package based on package manager and package names.
        """
        return cls.db.one("SELECT packages.*::packages FROM packages "
                          "WHERE package_manager=%s and name=%s", (package_manager, name))


    @property
    def team(self):
        """A computed attribute, the :py:class:`~gratipay.models.team.Team`
        linked to this package if there is one, otherwise ``None``. Makes a
        database call.
        """
        return self.load_team(self.db)


    def load_team(self, cursor):
        """Given a database cursor, return a
        :py:class:`~gratipay.models.team.Team` if there is one linked to this
        package, or ``None`` if not.
        """
        return cursor.one('SELECT t.*::teams FROM teams t WHERE t.id=%s', (self.team_id,))


    def get_or_create_linked_team(self, cursor, owner):
        """Given a db cursor and :py:class:`participant`, return a
        :py:class:`~gratipay.models.team.team`.
        """
        return self.load_team(cursor) or self.create_linked_team(cursor, owner)


    def create_linked_team(self, cursor, owner):
        """Given a db cursor and :py:class:`participant`, return a
        :py:class:`~gratipay.models.team.team`.
        """

        def slug_options():
            yield self.name
            for i in range(1, 10):
                yield '{}-{}'.format(self.name, i)
            yield str(uuid.uuid4()).lower()

        for slug in slug_options():
            if cursor.one('SELECT count(*) FROM teams WHERE slug=%s', (slug,)) > 0:
                continue
            team = Team.insert( slug=slug
                              , slug_lower=slug.lower()
                              , name=slug
                              , homepage=''
                              , product_or_service=''
                              , owner=owner
                              , _cursor=cursor
                               )
            break
        else:
            raise OutOfOptions()

        cursor.run('UPDATE packages SET team_id=%s WHERE id=%s', (team.id, self.id))
        self.set_attributes(team_id=team.id)
        return team
