"""数据库测试配置的无连接安全检查。"""

import os
import re
from pathlib import Path


def require_test_config_path():
    configured = os.environ.get('ATTENDANCE_TEST_CONFIG', '').strip()
    if not configured:
        raise ValueError('必须显式设置 ATTENDANCE_TEST_CONFIG，禁止使用业务配置')
    path = Path(configured).resolve()
    if path.name.lower() == 'attendance_config.ini':
        raise ValueError('禁止使用业务配置 attendance_config.ini')
    if not path.is_file():
        raise ValueError('测试专用配置文件不存在')
    return str(path)


def validate_test_database(config):
    database = config['database']
    if database.get('host') not in ('127.0.0.1', 'localhost', '::1'):
        raise ValueError('数据库测试只允许本机地址')
    if not re.fullmatch(r'attendance_test_[a-z0-9_]+', database.get('database', '')):
        raise ValueError('测试库名必须为 attendance_test_ 加小写字母、数字或下划线')
