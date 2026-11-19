"""SPEC-013：配置与隔离 MySQL 首建验收。"""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from attendance.config import ConfigService
from attendance.models import Admin
from attendance.services import AdminService
from attendance.utils import AuthFailed, InternalError


@pytest.mark.parametrize('legacy_section', [False, True])
def test_TC_SETUP_001(tmp_path, monkeypatch, legacy_section):
    ini = tmp_path / 'attendance.ini'
    monkeypatch.setattr(ConfigService, 'INI_PATH', str(ini))
    ConfigService.ensure_exists()
    text = ini.read_text(encoding='utf-8')
    assert '[admin]' not in text
    if legacy_section:
        ini.write_text(text + '\n[admin]\ndefault_password = ignored\n', encoding='utf-8')
    assert set(ConfigService.load()) == {'database', 'schedule_seed'}


@pytest.mark.parametrize('username,password', [('', 'a' * 12), ('a' * 51, 'a' * 12),
                                               ('owner', 'short'), ('owner', ' ' * 12),
                                               ('owner', 'a' * 129)])
def test_first_admin_rejects_invalid_input(username, password):
    with pytest.raises(InternalError):
        AdminService.create_first(username, password)
    assert not AdminService.has_admins()


def test_PT_SETUP_101():
    password = 'fixture-password'
    assert not AdminService.has_admins()
    barrier = Barrier(2, timeout=10)
    db = Admin._meta.database

    def attempt(username):
        with db.connection_context():
            barrier.wait()
            return AdminService.create_first(username, password)

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(attempt, ('owner-one', 'owner-two')))
    created, = [admin for admin in results if admin is not None]
    assert created.is_super
    assert AdminService.has_admins()
    assert AdminService.create_first('other-owner', 'different-password') is None
    assert AdminService.create_first(created.username, 'different-password') is None
    assert Admin.select().count() == 1
    assert AdminService.authenticate(created.username, password).id == created.id
    with pytest.raises(AuthFailed):
        AdminService.authenticate(created.username, 'different-password')
