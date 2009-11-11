from pylons import c
from tg import expose, redirect
from pyforge.app import Application
from pyforge.lib.dispatch import _dispatch

from helloforge import model as M

class HelloForgeApp(Application):
    '''This is the HelloWorld application for PyForge, showing
    all the rich, creamy goodness that is installable apps.
    '''
    default_config = dict(project_name='NoProject',
                          message='Custom message goes here')

    def __init__(self, config):
        self.config = config
        self.root = RootController()

    def install(self, project):
        self.config.config['project_name'] = project._id
        p = M.Page.upsert('Root')
        p.text = 'This is the root page.'
        p.m.save()

    def uninstall(self, project):
        for p in M.Page.m.find(dict(project_id=c.project._id)):
            p.m.delete()

class RootController(object):

    @expose('helloforge.templates.index')
    def index(self):
        return dict(message=c.app.config.config['message'])

    def _dispatch(self, state, remainder):
        return _dispatch(self, state, remainder)
        
    def _lookup(self, pname, *remainder):
        return PageController(pname), remainder

class PageController(object):

    def __init__(self, title):
        self.title = title

    def page(self, version=None):
        if version is None:
            return M.Page.upsert(self.title)
        else:
            return M.Page.upsert(self.title, version=int(version))

    @expose('helloforge.templates.page_view')
    def index(self, version=None):
        return dict(page=self.page(version))

    @expose('helloforge.templates.page_edit')
    def edit(self):
        return dict(page=self.page())

    @expose('helloforge.templates.page_history')
    def history(self):
        pages = M.Page.history(self.title)
        return dict(title=self.title, pages=pages)

    @expose()
    def revert(self, version):
        orig = self.page(version)
        current = self.page()
        current.text = orig.text
        current.m.save()
        redirect('.')

    @expose()
    def update(self, text):
        self.page.text = text
        self.page.m.save()
        redirect('.')
