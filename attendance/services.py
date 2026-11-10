"""签到/签退人员管理系统 - 业务服务层 (SPEC-001-B v1.0.0).

4 个静态方法类,封装业务规则:
- ScheduleService: 班次查询
- EmployeeService: 人员 CRUD + 校验器
- CheckService: 打卡记录增查
- AdminService: 管理员认证 + 改密 + 默认账号

异常类与字段命名与 SPEC-001-A 逐字一致,本文件不新增任何异常类。
"""

import os
import re
from datetime import date, datetime
from typing import Optional

import peewee

from attendance.models import Admin, CheckRecord, Employee, Schedule
from attendance.utils import (
    AdminNotFound,
    AuthFailed,
    CheckTypeInvalid,
    DateRangeInvalid,
    EmployeeHasRecords,
    EmployeeIdExists,
    EmployeeIdInvalid,
    EmployeeInactive,
    EmployeeNotFound,
    FaceImageNotFound,
    InternalError,
    LastAdminForbidden,
    PasswordTooShort,
    ScheduleNotFound,
    SelfDeleteForbidden,
    UsernameExists,
    logger,
    sha256_hex,
)


# ============================================================
# ScheduleService (§3.1)
# ============================================================


class ScheduleService:
    """班次查询服务。"""

    @staticmethod
    def get(schedule_id: int) -> Schedule:
        """按 id 查询。

        抛出: ScheduleNotFound
        """
        try:
            return Schedule.get_by_id(schedule_id)
        except Schedule.DoesNotExist:
            raise ScheduleNotFound(f"班次 id={schedule_id} 不存在")

    @staticmethod
    def list_all() -> list[Schedule]:
        """按 id 升序。"""
        return list(Schedule.select().order_by(Schedule.id))


# ============================================================
# EmployeeService (§3.2)
# ============================================================


class EmployeeService:
    """人员 CRUD 服务。"""

    EMPLOYEE_ID_PATTERN: str = r"^\d{6}$"
    FACE_IMAGE_PATH_PATTERN: str = r"^face_datasets/[^/]+\.(jpg|jpeg|png)$"

    # --- §5.2 校验器 ---

    @staticmethod
    def _validate_employee_id(v: str) -> None:
        """工号格式 ^\\d{6}$。失败抛 EmployeeIdInvalid。"""
        if not isinstance(v, str) or not re.fullmatch(
            EmployeeService.EMPLOYEE_ID_PATTERN, v
        ):
            raise EmployeeIdInvalid(
                f"工号格式错误: {v!r}, 必须是 6 位数字"
            )

    @staticmethod
    def _validate_face_image_path(v: str) -> None:
        """人脸照片路径格式 + 文件存在性。失败抛 FaceImageNotFound。"""
        if not isinstance(v, str) or not re.fullmatch(
            EmployeeService.FACE_IMAGE_PATH_PATTERN, v
        ):
            raise FaceImageNotFound(
                f"人脸照片路径格式错误: {v!r}"
            )
        if not os.path.isfile(v):
            raise FaceImageNotFound(
                f"人脸照片文件不存在: {v!r}"
            )

    # --- 公开工厂方法 ---

    @staticmethod
    def create(
        *,
        employee_id: str,
        name: str,
        department: Optional[str],
        position: Optional[str],
        phone: Optional[str],
        email: Optional[str],
        face_image_path: str,
        schedule_id: int,
        is_active: bool = True,
    ) -> Employee:
        """B-BR-001 决策表: id 格式 / id 唯一 / 照片 / schedule。

        抛出: EmployeeIdInvalid / EmployeeIdExists /
              FaceImageNotFound / ScheduleNotFound
        """
        EmployeeService._validate_employee_id(employee_id)
        if Employee.select().where(
            Employee.employee_id == employee_id
        ).exists():
            raise EmployeeIdExists(f"工号 {employee_id} 已存在")
        EmployeeService._validate_face_image_path(face_image_path)
        try:
            schedule = Schedule.get_by_id(schedule_id)
        except Schedule.DoesNotExist:
            raise ScheduleNotFound(f"班次 id={schedule_id} 不存在")

        try:
            emp = Employee.create(
                employee_id=employee_id,
                name=name,
                department=department,
                position=position,
                phone=phone,
                email=email,
                face_image_path=face_image_path,
                schedule=schedule,
                is_active=is_active,
            )
        except peewee.PeeweeException as e:
            raise InternalError(f"插入员工失败: {e}")

        logger.info(
            "action=employee.create employee_id=%s name=%s",
            employee_id, name,
        )
        return emp

    @staticmethod
    def update(
        employee_id: str,
        *,
        name: Optional[str] = None,
        department: Optional[str] = None,
        position: Optional[str] = None,
        phone: Optional[str] = None,
        email: Optional[str] = None,
        face_image_path: Optional[str] = None,
        schedule_id: Optional[int] = None,
        is_active: Optional[bool] = None,
    ) -> Employee:
        """仅更新非 None 字段;updated_at 自动刷新。

        抛出: EmployeeNotFound / FaceImageNotFound / ScheduleNotFound
        """
        try:
            emp = Employee.get_by_id(employee_id)
        except Employee.DoesNotExist:
            raise EmployeeNotFound(f"员工 {employee_id} 不存在")

        update_fields = {}
        if name is not None:
            update_fields["name"] = name
        if department is not None:
            update_fields["department"] = department
        if position is not None:
            update_fields["position"] = position
        if phone is not None:
            update_fields["phone"] = phone
        if email is not None:
            update_fields["email"] = email
        if face_image_path is not None:
            EmployeeService._validate_face_image_path(face_image_path)
            update_fields["face_image_path"] = face_image_path
        if schedule_id is not None:
            try:
                schedule = Schedule.get_by_id(schedule_id)
            except Schedule.DoesNotExist:
                raise ScheduleNotFound(
                    f"班次 id={schedule_id} 不存在"
                )
            update_fields["schedule"] = schedule
        if is_active is not None:
            update_fields["is_active"] = is_active

        if update_fields:
            update_fields["updated_at"] = datetime.now()
            try:
                Employee.update(**update_fields).where(
                    Employee.employee_id == employee_id
                ).execute()
            except peewee.PeeweeException as e:
                raise InternalError(f"更新员工失败: {e}")
            emp = Employee.get_by_id(employee_id)

        logger.info(
            "action=employee.update employee_id=%s fields=%s",
            employee_id, sorted(update_fields.keys()),
        )
        return emp

    @staticmethod
    def delete(employee_id: str) -> None:
        """B-BR-002 决策表: 员工存在 / 无 check_records。

        抛出: EmployeeNotFound / EmployeeHasRecords
        """
        try:
            emp = Employee.get_by_id(employee_id)
        except Employee.DoesNotExist:
            raise EmployeeNotFound(f"员工 {employee_id} 不存在")

        if CheckRecord.select().where(
            CheckRecord.employee == emp
        ).count() > 0:
            raise EmployeeHasRecords(
                f"员工 {employee_id} 存在打卡记录, 不可删除"
            )

        try:
            emp.delete_instance()
        except peewee.PeeweeException as e:
            raise InternalError(f"删除员工失败: {e}")

        logger.info(
            "action=employee.delete employee_id=%s", employee_id,
        )

    @staticmethod
    def get(employee_id: str) -> Employee:
        """按工号查询。

        抛出: EmployeeNotFound
        """
        try:
            return Employee.get_by_id(employee_id)
        except Employee.DoesNotExist:
            raise EmployeeNotFound(f"员工 {employee_id} 不存在")

    @staticmethod
    def get_by_face_image_name(name: str) -> Employee:
        """按人脸照片文件名查找员工 (face_datasets/xxx.ext 的 basename, 无扩展名).

        用于签到流程: get_name.rec 返回 face_datasets/xxx.{jpg,png}
        的文件名 (无扩展名), 反查 DB 找对应员工 (face_image_path 字段).

        抛出: EmployeeNotFound
        """
        if not name:
            raise EmployeeNotFound("人脸照片文件名为空")
        try:
            return Employee.select().where(
                Employee.face_image_path.startswith(
                    f"face_datasets/{name}."
                )
            ).get()
        except Employee.DoesNotExist:
            raise EmployeeNotFound(
                f"未找到人脸照片文件名为 {name!r} 的员工"
            )

    @staticmethod
    def list_all(is_active: Optional[bool] = None) -> list[Employee]:
        """列出所有;is_active 为 None 时不过滤。"""
        query = Employee.select().order_by(Employee.employee_id)
        if is_active is not None:
            query = query.where(Employee.is_active == is_active)
        return list(query)

    @staticmethod
    def search(keyword: str) -> list[Employee]:
        """按 employee_id 包含 keyword OR name 包含 keyword。

        keyword 长度 0 返回空列表。
        """
        if keyword is None or len(keyword) == 0:
            return []
        return list(
            Employee.select()
            .where(
                (Employee.employee_id.contains(keyword))
                | (Employee.name.contains(keyword))
            )
            .order_by(Employee.employee_id)
        )


# ============================================================
# CheckService (§3.3)
# ============================================================


class CheckService:
    """打卡记录增查服务。"""

    VALID_TYPES: tuple[str, ...] = ("check_in", "check_out", "middle")

    @staticmethod
    def _validate_check_type(v: str) -> None:
        """§5.2 校验器: check_type 必须在 VALID_TYPES。"""
        if v not in CheckService.VALID_TYPES:
            raise CheckTypeInvalid(
                f"check_type 非法: {v!r}, "
                f"必须是 {CheckService.VALID_TYPES}"
            )

    @staticmethod
    def create_record(employee_id: str, check_type: str) -> CheckRecord:
        """B-BR-003 决策表: 员工存在 / 在职 / type 合法。

        抛出: EmployeeNotFound / EmployeeInactive / CheckTypeInvalid
        """
        try:
            emp = Employee.get_by_id(employee_id)
        except Employee.DoesNotExist:
            raise EmployeeNotFound(f"员工 {employee_id} 不存在")

        if not emp.is_active:
            raise EmployeeInactive(
                f"员工 {employee_id} 已离职, 不可打卡"
            )

        CheckService._validate_check_type(check_type)

        now = datetime.now()
        try:
            record = CheckRecord.create(
                employee=emp,
                check_type=check_type,
                check_timestamp=now,
                check_date=now.date(),
            )
        except peewee.PeeweeException as e:
            raise InternalError(f"写入打卡记录失败: {e}")

        logger.info(
            "action=checkin.%s employee_id=%s record_id=%s",
            check_type, employee_id, record.id,
        )
        return record

    @staticmethod
    def list_records(
        *,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        employee_id: Optional[str] = None,
        check_type: Optional[str] = None,
    ) -> list[CheckRecord]:
        """B-BR-004 决策表: 全部条件可选。

        抛出: DateRangeInvalid / CheckTypeInvalid
        """
        if (
            date_from is not None
            and date_to is not None
            and date_from > date_to
        ):
            raise DateRangeInvalid(
                f"日期范围反向: date_from={date_from} > date_to={date_to}"
            )

        if check_type is not None:
            CheckService._validate_check_type(check_type)

        query = CheckRecord.select()
        conds = []
        if date_from is not None:
            conds.append(CheckRecord.check_date >= date_from)
        if date_to is not None:
            conds.append(CheckRecord.check_date <= date_to)
        if employee_id is not None:
            conds.append(CheckRecord.employee == employee_id)
        if check_type is not None:
            conds.append(CheckRecord.check_type == check_type)

        if conds:
            query = query.where(*conds)
        return list(query.order_by(CheckRecord.check_timestamp.desc()))


# ============================================================
# AdminService (§3.4)
# ============================================================


class AdminService:
    """管理员认证 + 默认账号服务。"""

    MIN_PASSWORD_LENGTH: int = 6

    @staticmethod
    def _validate_new_password(v: str) -> None:
        """§5.2 校验器: 新密码长度 >= 6。"""
        if not isinstance(v, str) or len(v) < AdminService.MIN_PASSWORD_LENGTH:
            raise PasswordTooShort(
                f"新密码长度 < {AdminService.MIN_PASSWORD_LENGTH}"
            )

    @staticmethod
    def authenticate(username: str, password: str) -> Admin:
        """SHA-256 hex 校验。

        抛出: AuthFailed
        """
        admin = Admin.select().where(
            Admin.username == username
        ).get_or_none()
        if admin is None:
            raise AuthFailed("用户名不存在或密码错")
        if admin.password_hash != sha256_hex(password):
            raise AuthFailed("用户名不存在或密码错")

        logger.info(
            "action=admin.login username=%s success=true", username,
        )
        return admin

    @staticmethod
    def change_password(
        admin_id: int, old_password: str, new_password: str
    ) -> None:
        """先校验旧密码,再校验新密码长度,再更新。

        抛出: AuthFailed / PasswordTooShort
        """
        try:
            admin = Admin.get_by_id(admin_id)
        except Admin.DoesNotExist:
            raise AuthFailed("用户名不存在或密码错")

        if admin.password_hash != sha256_hex(old_password):
            raise AuthFailed("用户名不存在或密码错")

        AdminService._validate_new_password(new_password)

        try:
            Admin.update(password_hash=sha256_hex(new_password)).where(
                Admin.id == admin_id
            ).execute()
        except peewee.PeeweeException as e:
            raise InternalError(f"改密失败: {e}")

        logger.info(
            "action=admin.change_password admin_id=%s username=%s",
            admin_id, admin.username,
        )

    @staticmethod
    def create(username: str, password: str) -> Admin:
        """创建新管理员。

        校验顺序: 1. username 长度 (InternalError / USERNAME_TOO_LONG, ≤ 50)
                  2. password 长度 (PasswordTooShort, ≥ MIN_PASSWORD_LENGTH)
                  3. username 唯一 (UsernameExists)
        DB 写失败转 InternalError。

        Raises:
            InternalError: username 长度 > 50 (USERNAME_TOO_LONG)
            PasswordTooShort: 密码长度 < MIN_PASSWORD_LENGTH (沿用 _validate_new_password)
            UsernameExists: username 已被注册
            InternalError: DB 写失败
        """
        # 校验 1: username 长度 ≤ 50 (不依赖 MySQL strict mode, 业务层兜底)
        if not isinstance(username, str) or len(username) > 50:
            raise InternalError(
                f"username 长度 {len(username) if isinstance(username, str) else 'N/A'} > 50"
            )
        # 校验 2: password 长度 ≥ 6
        AdminService._validate_new_password(password)
        # 校验 3: username 唯一
        existing = Admin.select().where(
            Admin.username == username
        ).get_or_none()
        if existing is not None:
            raise UsernameExists(f"用户名 {username} 已存在")
        try:
            admin = Admin.create(
                username=username,
                password_hash=sha256_hex(password),
                is_super=True,
            )
        except peewee.PeeweeException as e:
            raise InternalError(f"创建管理员失败: {e}")
        logger.info(
            "action=admin.create username=%s admin_id=%s",
            username, admin.id,
        )
        return admin

    @staticmethod
    def list_all() -> list:
        """按 id 升序列出所有管理员.

        返回 list[Admin] (空表返 []).
        """
        return list(Admin.select().order_by(Admin.id))

    @staticmethod
    def delete(
        admin_id: int, current_admin_id: int = None,
    ) -> None:
        """删除管理员.

        校验顺序: 1. admin_id 存在 (AdminNotFound)
                   2. 非自己 (SelfDeleteForbidden, 当 current_admin_id 不为 None)
                   3. 系统至少剩 1 个 admin (LastAdminForbidden)
        DB 删失败转 InternalError.

        Args:
            admin_id: 要删除的 admin id
            current_admin_id: 当前登录 admin id (用于自删保护, 默认可为 None)

        Raises:
            AdminNotFound: admin_id 不存在
            SelfDeleteForbidden: 试图删除当前登录 admin
            LastAdminForbidden: 仅剩 1 个 admin
            InternalError: DB 删失败
        """
        try:
            admin = Admin.get_by_id(admin_id)
        except Admin.DoesNotExist:
            raise AdminNotFound(f"管理员 {admin_id} 不存在")
        if (
            current_admin_id is not None
            and admin_id == current_admin_id
        ):
            raise SelfDeleteForbidden(
                f"不能删除当前登录的管理员 {admin_id}"
            )
        if Admin.select().count() <= 1:
            raise LastAdminForbidden("系统至少保留 1 个管理员")
        try:
            Admin.delete().where(Admin.id == admin_id).execute()
        except peewee.PeeweeException as e:
            raise InternalError(f"删除管理员失败: {e}")
        logger.info(
            "action=admin.delete admin_id=%s username=%s",
            admin_id, admin.username,
        )

    @staticmethod
    def ensure_default(default_username: str, default_password: str) -> None:
        """admins 表为空时插入默认账号;否则无操作。

        抛出: InternalError
        """
        if Admin.select().count() > 0:
            return

        try:
            Admin.create(
                username=default_username,
                password_hash=sha256_hex(default_password),
                is_super=True,
            )
        except peewee.PeeweeException as e:
            raise InternalError(f"插入默认管理员失败: {e}")

        logger.info(
            "action=admin.ensure_default username=%s", default_username,
        )
