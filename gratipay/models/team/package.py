# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function, unicode_literals


class Package(object):
    """A :py:class:`~gratipay.models.team.Team` can be associated with :py:class:`Package`.
    """

    @property
    def package(self):
        """A computed attribute, the
        :py:class:`~gratipay.models.package.Package` linked to this team if
        there is one, otherwise ``None``. Makes a database call.
        """
        return self._load_package(self.db)


    def _load_package(self, cursor):
        return cursor.one( 'SELECT p.*::packages FROM packages p WHERE p.id='
                           '(SELECT package_id FROM teams_to_packages tp WHERE tp.team_id=%s)'
                         , (self.id,)
                          )
