import os
from StringIO import StringIO

import mock
from tg import config
from pylons import g, c

from ming.orm.ormsession import ThreadLocalORMSession

from forgeforum.tests import TestController
from pyforge import model as M
from pyforge.command import reactor
from pyforge.lib import helpers as h

from forgeforum import model as FM

class TestForumReactors(TestController):

    def setUp(self):
        TestController.setUp(self)
        self.app.get('/Forum/')
        r = self.app.post('/admin/Forum/update_forums',
                          params={'new_forum.shortname':'test',
                                  'new_forum.create':'on',
                                  'new_forum.name':'Test Forum',
                                  'new_forum.description':'',
                                  'new_forum.parent':'',
                                  })
        r = self.app.get(r.location)
        assert 'error' not in r
        assert 'Test Forum' in r
        r = self.app.post('/admin/Forum/update_forums',
                          params={'new_forum.shortname':'test1',
                                  'new_forum.create':'on',
                                  'new_forum.name':'Test Forum 1',
                                  'new_forum.description':'',
                                  'new_forum.parent':'',
                                  })
        r = self.app.get(r.location)
        assert 'error' not in r
        assert 'Test Forum 1' in r
        conf_dir = getattr(config, 'here', os.getcwd())
        test_config = os.environ.get('SANDBOX') and 'sandbox-test.ini' or 'test.ini'
        test_file = os.path.join(conf_dir, test_config)
        cmd = reactor.ReactorCommand('reactor')
        cmd.args = [ test_config ]
        cmd.options = mock.Mock()
        cmd.options.dry_run = True
        cmd.options.proc = 1
        configs = cmd.command()
        self.cmd = cmd
        h.set_context('test', 'Forum')
        self.user_id = M.User.query.get(username='root')._id

    def test_has_access(self):
        assert False == c.app.has_access(M.User.anonymous(), 'test')
        assert True == c.app.has_access(M.User.query.get(username='root'), 'test')

    def test_post(self):
        self._post('Forum.test', 'Test Thread', 'Nothing here')

    def test_bad_post(self):
        self._post('Forumtest', 'Test Thread', 'Nothing here')

    def test_notify(self):
        self._post('Forum.test', 'Test Thread', 'Nothing here',
                   message_id='test@sf.net')
        self._post('Forum.test', 'Test Reply', 'Nothing here, either',
                   message_id='test1@sf.net',
                   in_reply_to=[ 'test@sf.net' ])
        self._notify('test@sf.net')
        self._notify('test1@sf.net')

    def test_reply(self):
        self._post('Forum.test', 'Test Thread', 'Nothing here',
                   message_id='test@sf.net')
        self._post('Forum.test', 'Test Reply', 'Nothing here, either',
                   message_id='test1@sf.net',
                   in_reply_to=[ 'test@sf.net' ])
        assert FM.Thread.query.find().count() == 1
        assert FM.Post.query.find().count() == 2

    def test_attach(self):
        self._post('Forum.test', 'Attachment Thread', 'This is a text file',
                   message_id='test.100@sf.net',
                   filename='test.txt',
                   content_type='text/plain')
        self._post('Forum.test', 'Test Thread', 'Nothing here',
                   message_id='test@sf.net')
        self._post('Forum.test', 'Attachment Thread', 'This is a text file',
                   message_id='test@sf.net',
                   content_type='text/plain')

    def test_threads(self):
        self._post('Forum.test', 'Test', 'test')
        thd = FM.Thread.query.find().first()
        url = str('/Forum/test/thread/%s/' % thd._id)
        r = self.app.get(url)
        # Test tags
        r = self.app.post(url + 'update_tags',
                          params={'new_tag.name':'foo bar'})
        r = self.app.get(r.location)
        r = self.app.get('/Forum/test/tag/foo/')
        assert len(r.html.findAll('tr')) == 2
        r = self.app.get('/Forum/test/tag/foo/bar/')
        assert len(r.html.findAll('tr')) == 2
        r = self.app.get('/Forum/test/tag/bar/foo/')
        assert len(r.html.findAll('tr')) == 2
        r = self.app.get('/Forum/test/tag/foo/bar/baz/')
        assert len(r.html.findAll('tr')) == 1
        self.app.post(url + 'update_tags',
                      params={
                'new_tag.name':'',
                'tag-0.delete':'on',
                'tag-1.name':'bar'})
        r = self.app.get('/Forum/test/tag/bar/')
        assert len(r.html.findAll('tr')) == 2
        r = self.app.get('/Forum/test/tag/foo/')
        assert len(r.html.findAll('tr')) == 1
        # Test moderate
        r = self.app.post(url + 'moderate',
                          params={'forum':'test12'})
        assert 'error' in self.app.get(r.location)
        r = self.app.post(url + 'moderate',
                          params={'forum':'test1'})
        assert 'test1' in r.location
        r = self.app.post(url + 'moderate',
                          params={'delete':'on'})
        r = self.app.get(r.location)
        assert len(r.html.findAll('tr')) == 1

    def test_posts(self):
        self._post('Forum.test', 'Test', 'test')
        thd = FM.Thread.query.find().first()
        thd_url = str('/Forum/test/thread/%s/' % thd._id)
        r = self.app.get(thd_url)
        p = FM.Post.query.find().first()
        url = str('/Forum/test/thread/%s/%s/' % (thd._id, p.slug))
        r = self.app.get(url)
        r = self.app.post(url, params=dict(subject='New Subject', text='Asdf'))
        assert 'Asdf' in self.app.get(url)
        r = self.app.get(url, params=dict(version=1))
        r = self.app.post(url + 'reply',
                          params=dict(subject='Reply', text='text'))
        self._post('Forum.test', 'Test Reply', 'Nothing here, either',
                   message_id='test1@sf.net',
                   in_reply_to=[ p._id ])
        reply = FM.Post.query.find().all()[-1]
        r = self.app.get(thd_url + reply.slug + '/')
        # Check attachments
        r = self.app.post(url + 'attach',
                          upload_files=[('file_info', 'test.txt', 'This is a textfile')])
        r = self.app.post(url + 'attach',
                          upload_files=[('file_info', 'test.asdfasdtxt', 'This is a textfile')])
        r = self.app.get(r.location.split('#')[0])
        for link in r.html.findAll('a'):
            if 'attachment' in link.get('href', ''):
                self.app.get(str(link['href']))
                self.app.post(str(link['href']), params=dict(delete='on'))
        # Moderate
        r = self.app.post(url + 'moderate',
                          params=dict(subject='New Thread', delete=''))
        r = self.app.post(r.location + str(reply.slug) + '/moderate',
                          params=dict(subject='', delete='on'))
        r = self.app.post(r.location + str(p.slug) + '/moderate',
                          params=dict(subject='', delete='on'))
        r = self.app.get(r.location, status=302)

    def _post(self, topic, subject, body, **kw):
        callback = self.cmd.route_audit(topic, c.app.auditor)
        msg = mock.Mock()
        msg.ack = lambda:None
        msg.delivery_info = dict(routing_key=topic)
        msg.data = dict(kw,
                        project_id=c.project._id,
                        mount_point='Forum',
                        headers=dict(Subject=subject),
                        user_id=self.user_id,
                        payload=body)
        callback(msg.data, msg)

    def _notify(self, post_id, **kw):
        callback = self.cmd.route_react('Forum.new_post', c.app.notify_subscribers)
        msg = mock.Mock()
        msg.ack = lambda:None
        msg.delivery_info = dict(routing_key='Forum.new_post')
        msg.data = dict(kw,
                        project_id=c.project._id,
                        mount_point='Forum',
                        post_id=post_id)
        callback(msg.data, msg)

class TestForum(TestController):

    def setUp(self):
        TestController.setUp(self)
        self.app.get('/Forum/')
        r = self.app.get('/admin/Forum/')
        r = self.app.post('/admin/Forum/update_forums',
                          params={'new_forum.shortname':'TestForum',
                                  'new_forum.create':'on',
                                  'new_forum.name':'Test Forum',
                                  'new_forum.description':'',
                                  'new_forum.parent':'',
                                  })
        r = self.app.get(r.location)
        assert 'error' not in r
        assert 'TestForum' in r
        h.set_context('test', 'Forum')
        frm = FM.Forum.query.get(shortname='TestForum')
        r = self.app.get('/admin/Forum/')
        r = self.app.post('/admin/Forum/update_forums',
                          params={'new_forum.shortname':'ChildForum',
                                  'new_forum.create':'on',
                                  'new_forum.name':'Child Forum',
                                  'new_forum.description':'',
                                  'new_forum.parent':str(frm._id),
                                  })
        r = self.app.get(r.location)
        assert 'error' not in r
        assert 'ChildForum' in r

    def test_forum_search(self):
        r = self.app.get('/Forum/search')
        r = self.app.get('/Forum/search', params=dict(q='foo'))

    def test_forum_subscribe(self):
        r = self.app.get('/Forum/subscribe', params={
                'forum-0.shortname':'TestForum',
                'forum-0.subscribed':'on',
                })
        r = self.app.get('/Forum/subscribe', params={
                'forum-0.shortname':'TestForum',
                'forum-0.subscribed':'',
                })

    def test_forum_index(self):
        r = self.app.get('/Forum/TestForum/')
        r = self.app.get('/Forum/TestForum/ChildForum/')

    def test_posting(self):
        r = self.app.get('/Forum/TestForum/thread/new', params=dict(
                subject='Test Thread',
                content='This is a *test thread*'))
        r = self.app.get(r.location)
        assert 'Message posted' in r

class TestForumAdmin(TestController):

    def setUp(self):
        TestController.setUp(self)
        self.app.get('/Forum/')

    def test_forum_CRUD(self):
        r = self.app.get('/admin/Forum/')
        r = self.app.post('/admin/Forum/update_forums',
                          params={'new_forum.shortname':'TestForum',
                                  'new_forum.create':'on',
                                  'new_forum.name':'Test Forum',
                                  'new_forum.description':'',
                                  'new_forum.parent':'',
                                  })
        r = self.app.get(r.location)
        assert 'error' not in r
        assert 'TestForum' in r
        h.set_context('test', 'Forum')
        frm = FM.Forum.query.get(shortname='TestForum')
        r = self.app.post('/admin/Forum/update_forums',
                          params={'new_forum.create':'',
                                  'forum-0.delete':'',
                                  'forum-0.id':str(frm._id),
                                  'forum-0.name':'New Test Forum',
                                  'forum-0.description':'My desc'})
        r = self.app.get(r.location)
        assert 'error' not in r
        assert 'New Test Forum' in r
        assert 'My desc' in r
        r = self.app.post('/admin/Forum/update_forums',
                          params={'new_forum.create':'',
                                  'forum-0.delete':'on',
                                  'forum-0.id':str(frm._id),
                                  'forum-0.name':'New Test Forum',
                                  'forum-0.description':'My desc'})
        r = self.app.get(r.location)
        assert 'error' not in r
        assert 'New Test Forum' not in r
        assert 'My desc' not in r

    def test_forum_CRUD_hier(self):
        r = self.app.get('/admin/Forum/')
        r = self.app.post('/admin/Forum/update_forums',
                          params={'new_forum.shortname':'TestForum',
                                  'new_forum.create':'on',
                                  'new_forum.name':'Test Forum',
                                  'new_forum.description':'',
                                  'new_forum.parent':'',
                                  })
        r = self.app.get(r.location)
        assert 'error' not in r
        assert 'TestForum' in r
        h.set_context('test', 'Forum')
        frm = FM.Forum.query.get(shortname='TestForum')
        r = self.app.get('/admin/Forum/')
        r = self.app.post('/admin/Forum/update_forums',
                          params={'new_forum.shortname':'ChildForum',
                                  'new_forum.create':'on',
                                  'new_forum.name':'Child Forum',
                                  'new_forum.description':'',
                                  'new_forum.parent':str(frm._id),
                                  })
        r = self.app.get(r.location)
        assert 'error' not in r
        assert 'ChildForum' in r
        r = self.app.post('/admin/Forum/update_forums',
                          params={'new_forum.create':'',
                                  'forum-0.delete':'on',
                                  'forum-0.id':str(frm._id),
                                  'forum-0.name':'New Test Forum',
                                  'forum-0.description':'My desc'})
        r = self.app.get(r.location)
        assert 'error' not in r
        assert 'TestForum' not in r
        assert 'ChildForum' not in r

    def test_bad_forum_names(self):
        r = self.app.post('/admin/Forum/update_forums',
                          params={'new_forum.shortname':'Test.Forum',
                                  'new_forum.create':'on',
                                  'new_forum.name':'Test Forum',
                                  'new_forum.description':'',
                                  'new_forum.parent':'',
                                  })
        r = self.app.get(r.location)
        assert 'error' in r
        r = self.app.post('/admin/Forum/update_forums',
                          params={'new_forum.shortname':'Test/Forum',
                                  'new_forum.create':'on',
                                  'new_forum.name':'Test Forum',
                                  'new_forum.description':'',
                                  'new_forum.parent':'',
                                  })
        r = self.app.get(r.location)
        assert 'error' in r


