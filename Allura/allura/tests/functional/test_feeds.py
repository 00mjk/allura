from formencode.variabledecode import variable_encode

from allura.tests import TestController
from allura.tests import decorators as td

class TestFeeds(TestController):
    def setUp(self):
        TestController.setUp(self)
        self._setUp()

    @td.with_wiki
    @td.with_tracker
    def _setUp(self):
        self.app.get('/wiki/')
        self.app.get('/bugs/')
        self.app.post(
            '/bugs/save_ticket',
            params=variable_encode(dict(
                    ticket_form=dict(
                    ticket_num='',
                    labels='',
                    assigned_to='',
                    milestone='',
                    summary='This is a ticket',
                    status='open',
                    description='This is a description'))),
            status=302)
        title = u'Descri\xe7\xe3o e Arquitetura'.encode('utf-8')
        self.app.post(
            '/wiki/%s/update' % title,
            params=dict(
                title=title,
                text="Nothing much",
                labels='',
                ),
            status=302)
        self.app.get('/wiki/%s/' % title)

    def test_project_feed(self):
        self.app.get('/feed.rss')
        self.app.get('/feed.atom')

    @td.with_wiki
    def test_wiki_feed(self):
        self.app.get('/wiki/feed.rss')
        self.app.get('/wiki/feed.atom')

    @td.with_wiki
    def test_wiki_page_feed(self):
        self.app.post('/wiki/Root/update', params={
                'title':'Root',
                'text':'',
                'labels':'',
                'viewable_by-0.id':'all'})
        self.app.get('/wiki/Root/feed.rss')
        self.app.get('/wiki/Root/feed.atom')

    @td.with_tracker
    def test_ticket_list_feed(self):
        self.app.get('/bugs/feed.rss')
        self.app.get('/bugs/feed.atom')

    @td.with_tracker
    def test_ticket_feed(self):
        self.app.get('/bugs/1/feed.rss')
        r = self.app.get('/bugs/1/feed.atom')
        self.app.post('/bugs/1/update_ticket', params=dict(
                assigned_to='',
                ticket_num='',
                labels='',
                summary='This is a new ticket',
                status='unread',
                milestone='',
                description='This is another description'), extra_environ=dict(username='root'))
        r = self.app.get('/bugs/1/feed.atom')
        assert '=&amp;gt' in r
        assert '\n+' in r

