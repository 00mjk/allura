import unittest
from nose.tools import assert_equals

from pylons import c
from ming.orm import ThreadLocalORMSession

from alluratest.controller import setup_basic_test, setup_global_objects
from allura.lib import helpers as h
from forgegit.tests import with_git

class TestGitApp(unittest.TestCase):

    def setUp(self):
        setup_basic_test()
        self.setup_with_tools()

    @with_git
    def setup_with_tools(self):
        setup_global_objects()
        h.set_context('test', 'src-git', neighborhood='Projects')
        ThreadLocalORMSession.flush_all()
        ThreadLocalORMSession.close_all()

    def test_admin_menu(self):
        assert_equals(len(c.app.admin_menu()), 4)

    def test_uninstall(self):
        from allura import model as M
        M.MonQTask.run_ready()
        c.app.uninstall(c.project)
        M.main_orm_session.flush()
        task = M.MonQTask.get()
        assert task.task_name == 'allura.tasks.repo_tasks.uninstall', task.task_name
        task()
