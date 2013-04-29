# -*- coding: utf-8 -*-

#       Licensed to the Apache Software Foundation (ASF) under one
#       or more contributor license agreements.  See the NOTICE file
#       distributed with this work for additional information
#       regarding copyright ownership.  The ASF licenses this file
#       to you under the Apache License, Version 2.0 (the
#       "License"); you may not use this file except in compliance
#       with the License.  You may obtain a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#       Unless required by applicable law or agreed to in writing,
#       software distributed under the License is distributed on an
#       "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
#       KIND, either express or implied.  See the License for the
#       specific language governing permissions and limitations
#       under the License.

"""REST Controller"""
import logging

import oauth2 as oauth
from webob import exc
from tg import expose, flash, redirect
from pylons import tmpl_context as c, app_globals as g
from pylons import request

from ming.orm import session
from ming.utils import LazyProperty

from allura import model as M
from allura.lib import helpers as h
from allura.lib import security

log = logging.getLogger(__name__)
action_logger = h.log_action(log, 'API:')

class RestController(object):

    def __init__(self):
        self.oauth = OAuthNegotiator()

    def _authenticate_request(self):
        'Based on request.params or oauth, authenticate the request'
        if 'oauth_token' in request.params:
            return self.oauth._authenticate()
        elif 'api_key' in request.params:
            api_key = request.params.get('api_key')
            token = M.ApiTicket.get(api_key)
            if not token:
                token = M.ApiToken.get(api_key)
            else:
                log.info('Authenticating with API ticket')
            if token is not None and token.authenticate_request(request.path, request.params):
                return token
            else:
                log.info('API authentication failure')
                raise exc.HTTPForbidden
        else:
            return None

    @expose('json:')
    def index(self, **kw):
        """Return site summary information as JSON.

        Currently, the only summary information returned are any site_stats
        whose providers are defined as entry points under the
        'allura.site_stats' group in a package or tool's setup.py, e.g.::

            [allura.site_stats]
            new_users_24hr = allura.site_stats:new_users_24hr

        The stat provider will be called with no arguments to generate the
        stat, which will be included under a key equal to the name of the
        entry point.

        Example output::

            {
                'site_stats': {
                    'new_users_24hr': 10
                }
            }
        """
        summary = dict()
        stats = dict()
        for stat, provider in g.entry_points['site_stats'].iteritems():
            stats[stat] = provider()
        if stats:
            summary['site_stats'] = stats
        return summary

    @expose()
    def _lookup(self, name, *remainder):
        api_token = self._authenticate_request()
        c.api_token = api_token
        if api_token:
            c.user = api_token.user
        else:
            c.user = M.User.anonymous()
        neighborhood = M.Neighborhood.query.get(url_prefix = '/' + name + '/')
        if not neighborhood: raise exc.HTTPNotFound, name
        return NeighborhoodRestController(neighborhood), remainder

class OAuthNegotiator(object):

    @LazyProperty
    def server(self):
        result = oauth.Server()
        result.add_signature_method(oauth.SignatureMethod_PLAINTEXT())
        result.add_signature_method(oauth.SignatureMethod_HMAC_SHA1())
        return result

    def _authenticate(self):
        req = oauth.Request.from_request(
            request.method,
            request.url.split('?')[0],
            headers=request.headers,
            parameters=dict(request.params),
            query_string=request.query_string
            )
        consumer_token = M.OAuthConsumerToken.query.get(
            api_key=req['oauth_consumer_key'])
        access_token = M.OAuthAccessToken.query.get(
            api_key=req['oauth_token'])
        if consumer_token is None:
            log.error('Invalid consumer token')
            return None
            raise exc.HTTPForbidden
        if access_token is None:
            log.error('Invalid access token')
            raise exc.HTTPForbidden
        consumer = consumer_token.consumer
        try:
            self.server.verify_request(req, consumer, access_token.as_token())
        except:
            log.error('Invalid signature')
            raise exc.HTTPForbidden
        return access_token

    @expose()
    def request_token(self, **kw):
        req = oauth.Request.from_request(
            request.method,
            request.url.split('?')[0],
            headers=request.headers,
            parameters=dict(request.params),
            query_string=request.query_string
            )
        consumer_token = M.OAuthConsumerToken.query.get(
            api_key=req['oauth_consumer_key'])
        if consumer_token is None:
            log.error('Invalid consumer token')
            raise exc.HTTPForbidden
        consumer = consumer_token.consumer
        try:
            self.server.verify_request(req, consumer, None)
        except:
            log.error('Invalid signature')
            raise exc.HTTPForbidden
        req_token = M.OAuthRequestToken(
            consumer_token_id=consumer_token._id,
            callback=req.get('oauth_callback', 'oob')
            )
        session(req_token).flush()
        log.info('Saving new request token with key: %s', req_token.api_key)
        return req_token.to_string()

    @expose('jinja:allura:templates/oauth_authorize.html')
    def authorize(self, oauth_token=None):
        security.require_authenticated()
        rtok = M.OAuthRequestToken.query.get(api_key=oauth_token)
        rtok.user_id = c.user._id
        if rtok is None:
            log.error('Invalid token %s', oauth_token)
            raise exc.HTTPForbidden
        return dict(
            oauth_token=oauth_token,
            consumer=rtok.consumer_token)

    @expose('jinja:allura:templates/oauth_authorize_ok.html')
    def do_authorize(self, yes=None, no=None, oauth_token=None):
        security.require_authenticated()
        rtok = M.OAuthRequestToken.query.get(api_key=oauth_token)
        if no:
            rtok.delete()
            flash('%s NOT AUTHORIZED' % rtok.consumer_token.name, 'error')
            redirect('/auth/oauth/')
        if rtok.callback == 'oob':
            rtok.validation_pin = h.nonce(6)
            return dict(rtok=rtok)
        rtok.validation_pin = h.nonce(20)
        if '?' in rtok.callback:
            url = rtok.callback + '&'
        else:
            url = rtok.callback + '?'
        url+='oauth_token=%s&oauth_verifier=%s' % (
            rtok.api_key, rtok.validation_pin)
        redirect(url)

    @expose()
    def access_token(self, **kw):
        req = oauth.Request.from_request(
            request.method,
            request.url.split('?')[0],
            headers=request.headers,
            parameters=dict(request.params),
            query_string=request.query_string
            )
        consumer_token = M.OAuthConsumerToken.query.get(
            api_key=req['oauth_consumer_key'])
        request_token = M.OAuthRequestToken.query.get(
            api_key=req['oauth_token'])
        if consumer_token is None:
            log.error('Invalid consumer token')
            raise exc.HTTPForbidden
        if request_token is None:
            log.error('Invalid request token')
            raise exc.HTTPForbidden
        pin = req['oauth_verifier']
        if pin != request_token.validation_pin:
            log.error('Invalid verifier')
            raise exc.HTTPForbidden
        rtok = request_token.as_token()
        rtok.set_verifier(pin)
        consumer = consumer_token.consumer
        try:
            self.server.verify_request(req, consumer, rtok)
        except:
            log.error('Invalid signature')
            return None
        acc_token = M.OAuthAccessToken(
            consumer_token_id=consumer_token._id,
            request_token_id=request_token._id,
            user_id=request_token.user_id)
        return acc_token.to_string()

class NeighborhoodRestController(object):

    def __init__(self, neighborhood):
        self._neighborhood = neighborhood

    @expose()
    def _lookup(self, name, *remainder):
        if not h.re_path_portion.match(name):
            raise exc.HTTPNotFound, name
        name = self._neighborhood.shortname_prefix + name
        project = M.Project.query.get(shortname=name, neighborhood_id=self._neighborhood._id, deleted=False)
        if not project: raise exc.HTTPNotFound, name
        c.project = project
        return ProjectRestController(), remainder

class ProjectRestController(object):

    @expose()
    def _lookup(self, name, *remainder):
        if not name:
            return self, ()
        subproject = M.Project.query.get(shortname=c.project.shortname + '/' + name,
                                         neighborhood_id=c.project.neighborhood_id,
                                         deleted=False)
        if subproject:
            c.project = subproject
            c.app = None
            return ProjectRestController(), remainder
        app = c.project.app_instance(name)
        if app is None:
            raise exc.HTTPNotFound, name
        c.app = app
        if app.api_root is None:
            raise exc.HTTPNotFound, name
        action_logger.info('', extra=dict(
                api_key=request.params.get('api_key')))
        return app.api_root, remainder

    @expose('json:')
    def index(self, **kw):
        return dict(
            name=c.project.shortname,
            tools=[dict(name=t.tool_name, mount_point=t.options.mount_point, label=t.options.mount_label)
                   for t in c.project.app_configs if h.has_access(t, 'read')]
        )
