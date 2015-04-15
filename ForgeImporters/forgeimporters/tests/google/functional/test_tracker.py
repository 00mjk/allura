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

from unittest import TestCase
import pkg_resources
from datetime import datetime

from BeautifulSoup import BeautifulSoup
import mock
from pylons import tmpl_context as c
from IPython.testing.decorators import module_not_available, skipif
from datadiff.tools import assert_equal

from alluratest.controller import setup_basic_test
from allura.tests.decorators import without_module
from allura import model as M
from forgetracker import model as TM
from forgeimporters import base
from forgeimporters import google
import forgeimporters.google.tracker


class TestGCTrackerImporter(TestCase):

    def _make_extractor(self, html):
        with mock.patch.object(base.h, 'urlopen') as urlopen:
            urlopen.return_value = ''
            extractor = google.GoogleCodeProjectExtractor(
                'allura-google-importer', 'project_info')
        extractor.page = BeautifulSoup(html)
        extractor.url = "http://test/issue/?id=1"
        # iter_comments will make more get_page() calls but we don't want the real thing to run an mess up the .page
        # and .url attributes, make it a no-op which works with these tests (since its just the same page being
        # fetched really)
        extractor.get_page = lambda *a, **kw: ''
        return extractor

    def _make_ticket(self, issue, issue_id=1):
        self.assertIsNone(self.project.app_instance('test-issue'))
        with mock.patch.object(base.h, 'urlopen') as urlopen,\
                mock.patch.object(google.tracker, 'GoogleCodeProjectExtractor') as GPE,\
                mock.patch.object(google.tracker.M, 'AuditLog') as AL,\
                mock.patch('forgetracker.tasks.update_bin_counts') as ubc:
            urlopen.side_effect = lambda req, **kw: mock.Mock(
                read=req.get_full_url,
                info=lambda: {'content-type': 'text/plain'})
            GPE.iter_issues.return_value = [(issue_id, issue)]
            gti = google.tracker.GoogleCodeTrackerImporter()
            gti.import_tool(self.project, self.user,
                            'test-issue-project', mount_point='test-issue')
        c.app = self.project.app_instance('test-issue')
        query = TM.Ticket.query.find({'app_config_id': c.app.config._id})
        self.assertEqual(query.count(), 1)
        ticket = query.all()[0]
        return ticket

    def setUp(self, *a, **kw):
        super(TestGCTrackerImporter, self).setUp(*a, **kw)
        setup_basic_test()
        self.empty_issue = self._make_extractor(
            open(pkg_resources.resource_filename('forgeimporters', 'tests/data/google/empty-issue.html')).read())
        self.test_issue = self._make_extractor(
            open(pkg_resources.resource_filename('forgeimporters', 'tests/data/google/test-issue.html')).read())
        c.project = self.project = M.Project.query.get(shortname='test')
        c.user = self.user = M.User.query.get(username='test-admin')

    def test_empty_issue(self):
        ticket = self._make_ticket(self.empty_issue)
        self.assertEqual(ticket.summary, 'Empty Issue')
        self.assertEqual(ticket.description,
                         '*Originally created by:* john...@gmail.com\n\nEmpty')
        self.assertEqual(ticket.status, '')
        self.assertEqual(ticket.milestone, '')
        self.assertEqual(ticket.custom_fields, {})
        assert c.app.config.options.get('EnableVoting')
        open_bin = TM.Bin.query.get(
            summary='Open Tickets', app_config_id=c.app.config._id)
        self.assertItemsEqual(open_bin.terms.split(' && '), [
            '!status:Fixed',
            '!status:Verified',
            '!status:Invalid',
            '!status:Duplicate',
            '!status:WontFix',
            '!status:Done',
        ])
        closed_bin = TM.Bin.query.get(
            summary='Closed Tickets', app_config_id=c.app.config._id)
        self.assertItemsEqual(closed_bin.terms.split(' or '), [
            'status:Fixed',
            'status:Verified',
            'status:Invalid',
            'status:Duplicate',
            'status:WontFix',
            'status:Done',
        ])

    @without_module('html2text')
    def test_issue_basic_fields(self):
        anon = M.User.anonymous()
        ticket = self._make_ticket(self.test_issue)
        self.assertEqual(ticket.reported_by, anon)
        self.assertIsNone(ticket.assigned_to_id)
        self.assertEqual(ticket.summary, 'Test "Issue"')
        assert_equal(ticket.description,
                     '*Originally created by:* [john...@gmail.com](http://code.google.com/u/101557263855536553789/)\n'
                     '*Originally owned by:* [john...@gmail.com](http://code.google.com/u/101557263855536553789/)\n'
                     '\n'
                     'Test \\*Issue\\* for testing\n'
                     '\n'
                     '&nbsp; 1\\. Test List\n'
                     '&nbsp; 2\\. Item\n'
                     '\n'
                     '\\*\\*Testing\\*\\*\n'
                     '\n'
                     ' \\* Test list 2\n'
                     ' \\* Item\n'
                     '\n'
                     '\\# Test Section\n'
                     '\n'
                     '&nbsp;&nbsp;&nbsp; p = source\\.test\\_issue\\.post\\(\\)\n'
                     '&nbsp;&nbsp;&nbsp; p\\.count = p\\.count \\*5 \\#\\* 6\n'
                     '&nbsp;&nbsp;&nbsp; if p\\.count &gt; 5:\n'
                     '&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; print "Not &lt; 5 &amp; \\!= 5"\n'
                     '\n'
                     'References: [issue 1](#1), [r2]\n'
                     '\n'
                     'That\'s all'
                     )
        self.assertEqual(ticket.status, 'Started')
        self.assertEqual(ticket.created_date, datetime(2013, 8, 8, 15, 33, 52))
        self.assertEqual(ticket.mod_date, datetime(2013, 8, 8, 15, 36, 57))
        self.assertEqual(ticket.custom_fields, {
            '_priority': 'Medium',
            '_opsys': 'All, OSX, Windows',
            '_component': 'Logic',
            '_type': 'Defect',
            '_milestone': 'Release1.0'
        })
        self.assertEqual(ticket.labels, ['Performance', 'Security'])
        self.assertEqual(ticket.votes_up, 1)
        self.assertEqual(ticket.votes, 1)

    def test_import_id(self):
        ticket = self._make_ticket(self.test_issue, issue_id=6)
        self.assertEqual(ticket.app.config.options.import_id, {
            'source': 'Google Code',
            'project_name': 'test-issue-project',
        })
        self.assertEqual(ticket.ticket_num, 6)
        self.assertEqual(ticket.import_id, {
            'source': 'Google Code',
            'project_name': 'test-issue-project',
            'source_id': 6,
        })

    @skipif(module_not_available('html2text'))
    def test_html2text_escaping(self):
        ticket = self._make_ticket(self.test_issue)
        assert_equal(ticket.description,
                     '*Originally created by:* [john...@gmail.com](http://code.google.com/u/101557263855536553789/)\n'
                     '*Originally owned by:* [john...@gmail.com](http://code.google.com/u/101557263855536553789/)\n'
                     '\n'
                     'Test \\*Issue\\* for testing\n'
                     '\n'
                     '&nbsp; 1. Test List\n'
                     '&nbsp; 2. Item\n'
                     '\n'
                     '\\*\\*Testing\\*\\*\n'
                     '\n'
                     ' \\* Test list 2\n'
                     ' \\* Item\n'
                     '\n'
                     '\\# Test Section\n'
                     '\n'
                     '&nbsp;&nbsp;&nbsp; p = source.test\\_issue.post\\(\\)\n'
                     '&nbsp;&nbsp;&nbsp; p.count = p.count \\*5 \\#\\* 6\n'
                     '&nbsp;&nbsp;&nbsp; if p.count &gt; 5:\n'
                     '&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; print "Not &lt; 5 &amp; \\!= 5"\n'
                     '\n'
                     'References: [issue 1](#1), [r2]\n'
                     '\n'
                     'That\'s all'
                     )

    def _assert_attachments(self, actual, *expected):
        self.assertEqual(len(actual), len(expected))
        atts = set((a.filename, a.content_type, a.rfile().read())
                   for a in actual)
        self.assertEqual(atts, set(expected))

    def test_attachments(self):
        ticket = self._make_ticket(self.test_issue)
        self._assert_attachments(ticket.attachments,
                                 ('at1.txt', 'text/plain',
                                  'http://allura-google-importer.googlecode.com/issues/attachment?aid=70000000&name=at1.txt&token=3REU1M3JUUMt0rJUg7ldcELt6LA%3A1376059941255'),
                                 )

    @without_module('html2text')
    def test_comments(self):
        anon = M.User.anonymous()
        ticket = self._make_ticket(self.test_issue)
        actual_comments = ticket.discussion_thread.find_posts()
        expected_comments = [
            {
                'timestamp': datetime(2013, 8, 8, 15, 35, 15),
                'text': (
                    '*Originally posted by:* [john...@gmail.com](http://code.google.com/u/101557263855536553789/)\n'
                    '\n'
                    'Test \\*comment\\* is a comment\n'
                    '\n'
                    '**Labels:** -OpSys-Linux OpSys-Windows\n'
                    '**Status:** Started'
                ),
                'attachments': [
                    ('at2.txt', 'text/plain',
                     'http://allura-google-importer.googlecode.com/issues/attachment?aid=60001000&name=at2.txt&token=JOSo4duwaN2FCKZrwYOQ-nx9r7U%3A1376001446667'),
                ],
            },
            {
                'timestamp': datetime(2013, 8, 8, 15, 35, 34),
                'text': (
                    '*Originally posted by:* [john...@gmail.com](http://code.google.com/u/101557263855536553789/)\n'
                    '\n'
                    'Another comment with references: [issue 2](#2), [r1]\n\n'
                ),
            },
            {
                'timestamp': datetime(2013, 8, 8, 15, 36, 39),
                'text': (
                    '*Originally posted by:* [john...@gmail.com](http://code.google.com/u/101557263855536553789/)\n'
                    '\n'
                    'Last comment\n\n'
                ),
                'attachments': [
                    ('at4.txt', 'text/plain',
                     'http://allura-google-importer.googlecode.com/issues/attachment?aid=60003000&name=at4.txt&token=6Ny2zYHmV6b82dqxyoiH6HUYoC4%3A1376001446667'),
                    ('at1.txt', 'text/plain',
                     'http://allura-google-importer.googlecode.com/issues/attachment?aid=60003001&name=at1.txt&token=NS8aMvWsKzTAPuY2kniJG5aLzPg%3A1376001446667'),
                ],
            },
            {
                'timestamp': datetime(2013, 8, 8, 15, 36, 57),
                'text': (
                    '*Originally posted by:* [john...@gmail.com](http://code.google.com/u/101557263855536553789/)\n'
                    '\n'
                    'Oh, I forgot one \\(with an inter\\-project reference to [issue other\\-project:1](https://code.google.com/p/other-project/issues/detail?id=1)\\)\n'
                    '\n'
                    '**Labels:** OpSys-OSX'
                ),
            },
        ]
        self.assertEqual(len(actual_comments), len(expected_comments))
        for actual, expected in zip(actual_comments, expected_comments):
            self.assertEqual(actual.author(), anon)
            self.assertEqual(actual.timestamp, expected['timestamp'])
            self.assertEqual(actual.text, expected['text'])
            if 'attachments' in expected:
                self._assert_attachments(
                    actual.attachments, *expected['attachments'])

    def test_globals(self):
        globals = self._make_ticket(self.test_issue, issue_id=6).globals
        self.assertEqual(globals.open_status_names, 'New Accepted Started')
        self.assertEqual(globals.closed_status_names,
                         'Fixed Verified Invalid Duplicate WontFix Done')
        self.assertEqual(globals.last_ticket_num, 6)
        self.assertItemsEqual(globals.custom_fields, [
            {
                'label': 'Milestone',
                'name': '_milestone',
                'type': 'milestone',
                'options': '',
                'milestones': [
                    {'name': 'Release1.0', 'due_date':
                     None, 'complete': False},
                ],
            },
            {
                'label': 'Type',
                'name': '_type',
                'type': 'select',
                'options': 'Defect',
            },
            {
                'label': 'Priority',
                'name': '_priority',
                'type': 'select',
                'options': 'Medium',
            },
            {
                'label': 'OpSys',
                'name': '_opsys',
                'type': 'string',
                'options': '',
            },
            {
                'label': 'Component',
                'name': '_component',
                'type': 'string',
                'options': '',
            },
        ])
