"""签到/签退人员管理系统 - 配置加载.

ConfigService:
- load(): 读取 attendance_config.ini, 返回嵌套 dict
- ensure_exists(): 若 INI 不存在, 写入模板默认值
- _validate_loaded(d): 校验返回 dict 结构, 缺键或类型错抛 INIReadFailed

INI 路径可在测试中通过 monkeypatch 覆盖 ConfigService.INI_PATH.
"""

import configparser
import os

from attendance.utils import INIReadFailed, InternalError, logger


class ConfigService:
    INI_PATH: str = "attendance_config.ini"

    @staticmethod
    def load() -> dict:
        """读取并解析 INI.

        返回 dict 形如:
          {
            "database": {"host": str, "port": int, "user": str,
                         "password": str, "database": str, "charset": str},
            "schedule_seed": {"name": str, "work_start": str,
                              "work_end": str, "late": int, "early": int}
          }
        抛出: INIReadFailed
        """
        if not os.path.isfile(ConfigService.INI_PATH):
            raise INIReadFailed(
                f"无法读取 {ConfigService.INI_PATH}: 文件不存在"
            )

        parser = configparser.ConfigParser()
        try:
            parser.read(ConfigService.INI_PATH, encoding="utf-8")
        except configparser.Error as e:
            raise INIReadFailed(f"无法解析 {ConfigService.INI_PATH}: {e}")

        try:
            result = {
                "database": {
                    "host": parser.get("database", "host"),
                    "port": parser.getint("database", "port"),
                    "user": parser.get("database", "user"),
                    "password": parser.get("database", "password"),
                    "database": parser.get("database", "database"),
                    "charset": parser.get("database", "charset"),
                },
                "schedule_seed": {
                    "name": parser.get("schedule_seed", "name"),
                    "work_start": parser.get("schedule_seed", "work_start"),
                    "work_end": parser.get("schedule_seed", "work_end"),
                    "late": parser.getint("schedule_seed", "late"),
                    "early": parser.getint("schedule_seed", "early"),
                },
            }
        except (configparser.NoSectionError, configparser.NoOptionError, ValueError) as e:
            raise INIReadFailed(f"{ConfigService.INI_PATH} 内容缺键或类型错: {e}")

        ConfigService._validate_loaded(result)
        logger.info("action=ini.read path=%s", ConfigService.INI_PATH)
        return result

    @staticmethod
    def ensure_exists() -> None:
        """若 INI 不存在, 创建并写入模板默认值.

        模板内容与 T-002 attendance_config.ini 一致.
        """
        if os.path.isfile(ConfigService.INI_PATH):
            return

        content = (
            "; ============================================================\n"
            ";  签到/签退人员管理系统配置文件\n"
            ";  此文件包含数据库密码, 严禁提交到 git 仓库\n"
            ";  .gitignore 已排除此文件\n"
            "; ============================================================\n"
            "\n"
            "[database]\n"
            "host = 127.0.0.1\n"
            "port = 3306\n"
            "user = root\n"
            "password =\n"
            "database = attendance_db\n"
            "charset = utf8mb4\n"
            "\n"
            "[schedule_seed]\n"
            "name = 常规班\n"
            "work_start = 08:00:00\n"
            "work_end = 17:00:00\n"
            "late = 15\n"
            "early = 15\n"
        )
        try:
            with open(ConfigService.INI_PATH, "w", encoding="utf-8") as f:
                f.write(content)
            logger.info("action=ini.create path=%s", ConfigService.INI_PATH)
        except OSError as e:
            raise InternalError(f"无法写入 {ConfigService.INI_PATH}: {e}")

    @staticmethod
    def _validate_loaded(d: dict) -> None:
        """校验返回 dict 符合 §4.1.

        校验失败抛 INIReadFailed.
        """
        try:
            db = d["database"]
            assert isinstance(db["host"], str) and len(db["host"]) >= 1
            assert isinstance(db["port"], int) and 1 <= db["port"] <= 65535
            assert isinstance(db["user"], str) and len(db["user"]) >= 1
            assert isinstance(db["password"], str)
            assert isinstance(db["database"], str)
            assert db["charset"] in ("utf8", "utf8mb4")

            seed = d["schedule_seed"]
            assert isinstance(seed["name"], str) and 1 <= len(seed["name"]) <= 50
            assert isinstance(seed["work_start"], str)
            assert isinstance(seed["work_end"], str)
            assert isinstance(seed["late"], int) and 0 <= seed["late"] <= 240
            assert isinstance(seed["early"], int) and 0 <= seed["early"] <= 240
        except (KeyError, AssertionError) as e:
            raise INIReadFailed(f"{ConfigService.INI_PATH} 校验失败: {e}")
