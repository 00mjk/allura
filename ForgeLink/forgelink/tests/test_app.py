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

import tempfile
import json

from nose.tools import assert_equal

from allura.tests import decorators as td
from allura import model as M
from allura.lib import helpers as h
from alluratest.controller import setup_basic_test


class TestBulkExport(object):

    def setUp(self):
        setup_basic_test()

    @td.with_link
    def test_bulk_export(self):
        self.project = M.Project.query.get(shortname='test')
        self.link = self.project.app_instance('link')
        h.set_context(self.project._id, app_config_id=self.link.config._id)
        self.link.config.options['url'] = 'http://sf.net'
        f = tempfile.TemporaryFile()
        self.link.bulk_export(f)
        f.seek(0)
        assert_equal(json.loads(f.read())['url'], 'http://sf.net')
