from pylons import tmpl_context as c, app_globals as g

from nose.tools import assert_equal

from alluratest.controller import setup_basic_test, setup_global_objects
from allura import model as M
from allura.lib import security
from allura.tests import decorators as td

def setUp():
    setup_basic_test()
    setup_with_tools()

@td.with_wiki
def setup_with_tools():
    setup_global_objects()
    g.set_app('wiki')

def test_role_assignments():
    admin = M.User.by_username('test-admin')
    user = M.User.by_username('test-user')
    anon = M.User.anonymous()
    def check_access(perm):
        pred = security.has_access(c.app, perm)
        return pred(user=admin), pred(user=user), pred(user=anon)
    assert_equal(check_access('configure'), (True, False, False))
    assert_equal(check_access('read'), (True, True, True))
    assert_equal(check_access('create'), (True, False, False))
    assert_equal(check_access('edit'), (True, False, False))
    assert_equal(check_access('delete'), (True, False, False))
    assert_equal(check_access('unmoderated_post'), (True, True, False))
    assert_equal(check_access('post'), (True, True, False))
    assert_equal(check_access('moderate'), (True, False, False))
    assert_equal(check_access('admin'), (True, False, False))
