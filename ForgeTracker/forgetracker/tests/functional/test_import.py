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

import os
import json
from formencode.variabledecode import variable_encode
from datetime import datetime, timedelta
from nose.tools import assert_equal, assert_false

import ming
from pylons import app_globals as g
from pylons import tmpl_context as c

from allura import model as M
from allura.lib import helpers as h
from alluratest.controller import TestRestApiBase
from allura.tests import decorators as td


class TestImportController(TestRestApiBase):

    def new_ticket(self, mount_point='/bugs/', **kw):
        response = self.app.get(mount_point + 'new/')
        form = response.forms[1]
        for k, v in kw.iteritems():
            form['ticket_form.%s' % k] = v
        resp = form.submit()
        if resp.status_int == 200:
            resp.showbrowser()
            assert 0, "form error?"
        return resp.follow()

    def set_api_ticket(self, caps={'import': ['Projects', 'test']}):
        api_ticket = M.ApiTicket(user_id=c.user._id, capabilities=caps,
                                 expires=datetime.utcnow() + timedelta(days=1))
        ming.orm.session(api_ticket).flush()
        self.set_api_token(api_ticket)

    @td.with_tracker
    def test_no_capability(self):
        here_dir = os.path.dirname(__file__)

        self.set_api_ticket({'import2': ['Projects', 'test']})
        resp = self.api_post('/rest/p/test/bugs/perform_import',
                             doc=open(here_dir + '/data/sf.json').read(), options='{}')
        assert resp.status_int == 403

        self.set_api_ticket({'import': ['Projects', 'test2']})
        resp = self.api_post('/rest/p/test/bugs/perform_import',
                             doc=open(here_dir + '/data/sf.json').read(), options='{}')
        assert resp.status_int == 403

        self.set_api_ticket({'import': ['Projects', 'test']})
        resp = self.api_post('/rest/p/test/bugs/perform_import',
                             doc=open(here_dir + '/data/sf.json').read(), options='{}')
        assert resp.status_int == 200

    @staticmethod
    def time_normalize(t):
        return t.replace('T', ' ').replace('Z', '')

    def verify_ticket(self, from_api, org):
        assert_equal(from_api['status'], org['status'])
        assert_equal(from_api['description'], org['description'])
        assert_equal(from_api['summary'], org['summary'])
        assert_equal(from_api['ticket_num'], org['id'])
        assert_equal(from_api['created_date'],
                     self.time_normalize(org['date']))
        assert_equal(from_api['mod_date'],
                     self.time_normalize(org['date_updated']))
        assert_equal(from_api['custom_fields']
                     ['_resolution'], org['resolution'])
        assert_false('_cc' in from_api['custom_fields'])
        assert_equal(from_api['custom_fields']['_private'], org['private'])

    @td.with_tracker
    def test_validate_import(self):
        here_dir = os.path.dirname(__file__)
        doc_text = open(here_dir + '/data/sf.json').read()
        r = self.api_post('/rest/p/test/bugs/validate_import',
                          doc=doc_text, options='{}')
        assert not r.json['errors']

    @td.with_tracker
    def test_import_custom_field(self):
        params = dict(
            custom_fields=[
                dict(name='_resolution', label='Resolution', type='select',
                     options='oné "one and á half" two'),
            ],
            open_status_names='aa bb',
            closed_status_names='cc',
        )
        self.app.post(
            '/admin/bugs/set_custom_fields',
            params=variable_encode(params))
        here_dir = os.path.dirname(__file__)
        api_ticket = M.ApiTicket(
            user_id=c.user._id, capabilities={'import': ['Projects', 'test']},
            expires=datetime.utcnow() + timedelta(days=1))
        ming.orm.session(api_ticket).flush()
        self.set_api_token(api_ticket)

        doc_text = open(here_dir + '/data/sf.json').read()
        doc_json = json.loads(doc_text)
        ticket_json = doc_json['trackers']['default']['artifacts'][0]
        r = self.api_post('/rest/p/test/bugs/perform_import',
                          doc=doc_text, options='{"user_map": {"hinojosa4": "test-admin", "ma_boehm": "test-user"}}')
        assert r.json['status'], r.json

        ming.orm.ThreadLocalORMSession.flush_all()
        M.MonQTask.run_ready()
        ming.orm.ThreadLocalORMSession.flush_all()

        r = self.app.get('/p/test/bugs/204/')
        assert '<option selected value="fixed">fixed</option>' in r
        assert '<option value="one and á half">one and á half</option>' in r

    @td.with_tracker
    def test_import(self):
        here_dir = os.path.dirname(__file__)
        api_ticket = M.ApiTicket(
            user_id=c.user._id, capabilities={'import': ['Projects', 'test']},
            expires=datetime.utcnow() + timedelta(days=1))
        ming.orm.session(api_ticket).flush()
        self.set_api_token(api_ticket)

        doc_text = open(here_dir + '/data/sf.json').read()
        doc_json = json.loads(doc_text)
        ticket_json = doc_json['trackers']['default']['artifacts'][0]
        r = self.api_post('/rest/p/test/bugs/perform_import',
                          doc=doc_text, options='{"user_map": {"hinojosa4": "test-admin", "ma_boehm": "test-user"}}')
        assert r.json['status']
        assert r.json['errors'] == []

        ming.orm.ThreadLocalORMSession.flush_all()
        M.MonQTask.run_ready()
        ming.orm.ThreadLocalORMSession.flush_all()

        indexed_tickets = filter(
            lambda a: a['type_s'] == 'Ticket', g.solr.db.values())
        assert_equal(len(indexed_tickets), 1)
        assert_equal(indexed_tickets[0]['summary_t'], ticket_json['summary'])
        assert_equal(indexed_tickets[0]['ticket_num_i'], ticket_json['id'])

        r = self.app.get('/rest/p/test/bugs/204/')
        self.verify_ticket(r.json['ticket'], ticket_json)
        assert r.json['ticket']["reported_by"] == "test-user"
        assert r.json['ticket']["assigned_to"] == "test-admin"

        r = self.app.get('/rest/p/test/bugs/')
        assert len(r.json['tickets']) == 1
        assert_equal(r.json['tickets'][0]['ticket_num'], ticket_json['id'])
        assert_equal(r.json['tickets'][0]['summary'], ticket_json['summary'])

        r = self.app.get('/p/test/bugs/204/')
        assert '<option value="2.0">2.0</option>' in r
        assert '<option selected value="test_milestone">test_milestone</option>' in r
        assert ticket_json['summary'] in r
        r = self.app.get('/p/test/bugs/')
        assert ticket_json['summary'] in r

    @td.with_tracker
    def test_milestone_status(self):
        """When importing, if all tickets in a milestone are closed, the
        milestone itself should also be closed.

        """
        here_dir = os.path.dirname(__file__)
        api_ticket = M.ApiTicket(
            user_id=c.user._id, capabilities={'import': ['Projects', 'test']},
            expires=datetime.utcnow() + timedelta(days=1))
        ming.orm.session(api_ticket).flush()
        self.set_api_token(api_ticket)

        doc_text = open(here_dir + '/data/milestone-tickets.json').read()
        r = self.api_post('/rest/p/test/bugs/perform_import', doc=doc_text,
                          options='{"user_map": {"hinojosa4": "test-admin", "ma_boehm": "test-user"}}')
        assert r.json['status'], r.json

        ming.orm.ThreadLocalORMSession.flush_all()
        M.MonQTask.run_ready()
        ming.orm.ThreadLocalORMSession.flush_all()

        with h.push_context('test', mount_point='bugs', neighborhood='Projects'):
            for milestone_fld in c.app.globals.milestone_fields:
                milestone_names = [ms['name']
                                   for ms in milestone_fld['milestones']]
                assert 'open_milestone' in milestone_names, milestone_names
                assert 'closed_milestone' in milestone_names, milestone_names
                for milestone in milestone_fld['milestones']:
                    if milestone['name'] == 'open_milestone':
                        assert milestone['complete'] == False
                    if milestone['name'] == 'closed_milestone':
                        assert milestone['complete'] == True
