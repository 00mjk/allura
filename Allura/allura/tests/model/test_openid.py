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

"""
Model tests for openid_model
"""
import time

import mock
from pylons import tmpl_context as c, app_globals as g
from pylons import request
from webob import Request
from openid.association import Association

from ming.orm.ormsession import ThreadLocalORMSession

from allura.lib.app_globals import Globals
from allura import model as M
from allura.lib import helpers as h


def setUp():
    g._push_object(Globals())
    c._push_object(mock.Mock())
    request._push_object(Request.blank('/'))
    ThreadLocalORMSession.close_all()
    M.EmailAddress.query.remove({})
    M.OpenIdNonce.query.remove({})
    M.OpenIdAssociation.query.remove({})
    #conn = M.main_doc_session.bind.conn


def test_oid_model():
    oid = M.OpenIdAssociation(_id='http://example.com')
    assoc = mock.Mock()
    assoc.handle = 'foo'
    assoc.serialize = lambda: 'bar'
    assoc.getExpiresIn = lambda: 0
    with h.push_config(Association,
                       deserialize=staticmethod(lambda v: assoc)):
        oid.set_assoc(assoc)
        assert assoc == oid.get_assoc('foo')
        oid.set_assoc(assoc)
        oid.remove_assoc('foo')
        assert oid.get_assoc('foo') is None
        oid.set_assoc(assoc)
        assert oid.get_assoc('foo') is not None
        oid.cleanup_assocs()
        assert oid.get_assoc('foo') is None


def test_oid_store():
    assoc = mock.Mock()
    assoc.handle = 'foo'
    assoc.serialize = lambda: 'bar'
    assoc.getExpiresIn = lambda: 0
    store = M.OpenIdStore()
    with h.push_config(Association,
                       deserialize=staticmethod(lambda v: assoc)):
        store.storeAssociation('http://example.com', assoc)
        assert assoc == store.getAssociation('http://example.com', 'foo')
        assert assoc == store.getAssociation('http://example.com')
        store.removeAssociation('http://example.com', 'foo')
        t0 = time.time()
        assert store.useNonce('http://www.example.com', t0, 'abcd')
        ThreadLocalORMSession.flush_all()
        assert not store.useNonce('http://www.example.com', t0, 'abcd')
        assert not store.useNonce('http://www.example.com', t0 - 1e9, 'abcd')
        assert store.getAssociation('http://example.com') is None
        store.cleanupNonces()
