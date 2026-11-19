import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from attendance.test_safety import require_test_config_path, validate_test_database


class DatabaseSafetyTests(unittest.TestCase):
    def test_requires_explicit_configuration(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ValueError):
                require_test_config_path()

    def test_config_path_validation(self):
        with tempfile.TemporaryDirectory(prefix='temp_attendance_') as directory:
            for filename in ('attendance_config.ini', 'ATTENDANCE_CONFIG.INI', 'missing.ini'):
                path = Path(directory) / filename
                if filename != 'missing.ini':
                    path.touch()
                with patch.dict(os.environ, {'ATTENDANCE_TEST_CONFIG': str(path)}):
                    with self.assertRaises(ValueError):
                        require_test_config_path()
            path = Path(directory) / 'local_test.ini'
            path.touch()
            with patch.dict(os.environ, {'ATTENDANCE_TEST_CONFIG': str(path)}):
                self.assertEqual(require_test_config_path(), str(path.resolve()))

    def test_database_validation(self):
        for name in ('attendance_db', 'attendance_test_', 'attendance_test_x;drop', ''):
            with self.subTest(database=name):
                with self.assertRaises(ValueError):
                    validate_test_database({'database': {'host': '127.0.0.1', 'database': name}})
        with self.assertRaises(ValueError):
            validate_test_database({'database': {'host': '192.168.1.2', 'database': 'attendance_test_s0'}})
        for host in ('127.0.0.1', 'localhost', '::1'):
            validate_test_database({'database': {'host': host, 'database': 'attendance_test_s0'}})


if __name__ == '__main__':
    unittest.main(verbosity=2)
