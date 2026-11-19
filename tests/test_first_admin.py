"""配置与隔离 MySQL 的管理员设置码验收。"""

import pytest

from attendance.config import ConfigService
from attendance.models import Admin, AdminRegistrationCode
from attendance.services import AdminService
from attendance.utils import AuthFailed, InternalError, UsernameExists


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


@pytest.fixture
def initial_registration_code():
    # _db_session has validated the isolated MySQL database before this fixture.
    db = AdminRegistrationCode._meta.database
    with db.atomic() as tx:
        AdminRegistrationCode.delete().where(AdminRegistrationCode.id == 1).execute()
        AdminService.initialize_registration_code()
        try:
            yield '123456'
        finally:
            tx.rollback()


@pytest.mark.parametrize('username,password', [('', 'a' * 12), ('a' * 51, 'a' * 12),
                                               ('owner', 'short'), ('owner', ' ' * 12),
                                               ('owner', 'a' * 129)])
def test_registration_rejects_invalid_input(username, password, initial_registration_code):
    with pytest.raises(InternalError):
        AdminService.register_with_code(initial_registration_code, username, password)
    assert not AdminService.has_admins()


def test_PT_CODE_101_and_102_registration_and_rotation(initial_registration_code):
    password = 'fixture-password'
    new_code = 'new-fixture-code'
    assert not AdminService.has_admins()
    with pytest.raises(AuthFailed):
        AdminService.register_with_code('incorrect', 'owner', password)
    assert not AdminService.has_admins()
    owner = AdminService.register_with_code(initial_registration_code, 'owner', password)
    peer = AdminService.register_with_code(initial_registration_code, 'peer', password)
    direct = AdminService.create('direct', 'direct-password')
    assert owner.is_super and peer.is_super and direct.is_super
    assert AdminService.authenticate(peer.username, password).id == peer.id
    with pytest.raises(UsernameExists):
        AdminService.register_with_code(initial_registration_code, 'peer', password)
    with pytest.raises(AuthFailed):
        AdminService.register_with_code('incorrect', 'not-created', password)
    assert Admin.select().count() == 3
    original_hash = AdminRegistrationCode.get_by_id(1).code_hash
    with pytest.raises(AuthFailed):
        AdminService.change_registration_code(peer.id, 'incorrect', new_code)
    with pytest.raises(AuthFailed):
        AdminService.change_registration_code(0, password, new_code)
    assert AdminRegistrationCode.get_by_id(1).code_hash == original_hash
    AdminService.change_registration_code(peer.id, password, new_code)
    saved = AdminRegistrationCode.get_by_id(1)
    assert saved.code_hash != new_code
    AdminService.initialize_registration_code()
    assert AdminRegistrationCode.get_by_id(1).code_hash == saved.code_hash
    with pytest.raises(AuthFailed):
        AdminService.register_with_code(initial_registration_code, 'after', password)
    assert Admin.select().count() == 3
    assert AdminService.register_with_code(new_code, 'after', password).is_super
    assert AdminService.authenticate(owner.username, password).id == owner.id
