# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function, unicode_literals

import base64

import aspen
from aspen.website import Website as BaseWebsite

from . import utils, security, version
from .security import authentication, csrf
from .utils import erase_cookie, http_caching, i18n, set_cookie, set_version_header, timer
from .renderers import csv_dump, jinja2_htmlescaped, eval_, scss


class Website(BaseWebsite):
    """Represent the website at gratipay.com.
    """

    def __init__(self, app):
        BaseWebsite.__init__(self)
        self.app = app
        self.version = version.get_version()
        self.configure_renderers()

        # TODO Can't do remaining config here because of lingering wireup
        # confustication up in Application.__init__.

    def init_more(self, env, db, tell_sentry):
        self.env = env
        self.db = db
        self.tell_sentry = tell_sentry

    def init_even_more(self):
        self.modify_algorithm(self.tell_sentry)
        self.monkey_patch_response()


    def configure_renderers(self):
        self.renderer_default = 'unspecified'  # require explicit renderer, to avoid escaping bugs

        self.renderer_factories['csv_dump'] = csv_dump.Factory(self)
        self.renderer_factories['eval'] = eval_.Factory(self)
        self.renderer_factories['jinja2_htmlescaped'] = jinja2_htmlescaped.Factory(self)
        self.renderer_factories['scss'] = scss.Factory(self)
        self.default_renderers_by_media_type['text/html'] = 'jinja2_htmlescaped'
        self.default_renderers_by_media_type['text/plain'] = 'jinja2'  # unescaped is fine here
        self.default_renderers_by_media_type['text/css'] = 'scss'
        self.default_renderers_by_media_type['image/*'] = 'eval'

        self.renderer_factories['jinja2'].Renderer.global_context = {
            # This is shared via class inheritance with jinja2_htmlescaped.
            'b64encode': base64.b64encode,
            'enumerate': enumerate,
            'filter': filter,
            'filter_profile_nav': utils.filter_profile_nav,
            'float': float,
            'len': len,
            'map': map,
            'range': range,
            'str': str,
            'to_javascript': utils.to_javascript,
            'type': type,
            'unicode': unicode,
        }


    def modify_algorithm(self, tell_sentry):
        noop = lambda: None
        algorithm = self.algorithm
        algorithm.functions = [
            timer.start,
            algorithm['parse_environ_into_request'],
            algorithm['parse_body_into_request'],

            utils.help_aspen_find_well_known,
            utils.use_tildes_for_participants,
            algorithm['redirect_to_base_url'],
            i18n.set_up_i18n,
            authentication.start_user_as_anon,
            authentication.authenticate_user_if_possible,
            security.only_allow_certain_methods,
            csrf.extract_token_from_cookie,
            csrf.reject_forgeries,

            algorithm['dispatch_request_to_filesystem'],

            http_caching.get_etag_for_file if self.cache_static else noop,
            http_caching.try_to_serve_304 if self.cache_static else noop,

            algorithm['apply_typecasters_to_path'],
            algorithm['get_resource_for_request'],
            algorithm['extract_accept_from_request'],
            algorithm['get_response_for_resource'],

            tell_sentry,
            algorithm['get_response_for_exception'],

            set_version_header,
            authentication.add_auth_to_response,
            csrf.add_token_to_response,
            http_caching.add_caching_to_response,
            security.add_headers_to_response,

            algorithm['log_traceback_for_5xx'],
            algorithm['delegate_error_to_simplate'],
            tell_sentry,
            algorithm['log_traceback_for_exception'],
            algorithm['log_result_of_request'],

            timer.end,
            tell_sentry,
        ]


    def monkey_patch_response(self):

        if hasattr(aspen.Response, 'set_cookie'):
            raise Warning('aspen.Response.set_cookie() already exists')
        def _set_cookie(response, *args, **kw):
            set_cookie(response.headers.cookie, *args, **kw)
        aspen.Response.set_cookie = _set_cookie

        if hasattr(aspen.Response, 'erase_cookie'):
            raise Warning('aspen.Response.erase_cookie() already exists')
        def _erase_cookie(response, *args, **kw):
            erase_cookie(response.headers.cookie, *args, **kw)
        aspen.Response.erase_cookie = _erase_cookie
