"""签到/签退人员管理系统 - 业务服务层 (SPEC-001-B v1.0.0).

4 个静态方法类,封装业务规则:
- ScheduleService: 班次查询
- EmployeeService: 人员 CRUD + 校验器
- CheckService: 打卡记录增查
- AdminService: 管理员认证 + 改密 + 默认账号

异常类与字段命名与 SPEC-001-A 逐字一致,本文件不新增任何异常类。
"""

import base64
import hashlib
import hmac
import os
import re
from datetime import date, datetime
from typing import Optional

import peewee
from attendance.attendance_rules import decide_check

from attendance.models import (
    Admin, AdminRegistrationCode, CheckRecord, Employee, EmployeeSchedule, FaceTemplate, Schedule,
)
from attendance.face_template_crypto import decrypt_vector, encrypt_vector
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
    """班次 CRUD 与员工多班次绑定服务。"""

    @staticmethod
    def _clock_minutes(value):
        return value.hour * 60 + value.minute

    @staticmethod
    def _relative_minutes(value, base):
        return (ScheduleService._clock_minutes(value) - ScheduleService._clock_minutes(base)) % 1440

    @staticmethod
    def _validate_window(work_start, work_end, check_in_start, late_end, check_out_end):
        # All windows are represented on the cyclic 24-hour clock. Endpoints
        # are inclusive; a zero-length interval is not a valid configuration.
        work_end_offset = ScheduleService._relative_minutes(work_end, work_start)
        check_in_offset = ScheduleService._relative_minutes(check_in_start, work_start)
        late_end_offset = ScheduleService._relative_minutes(late_end, work_start)
        check_out_end_offset = ScheduleService._relative_minutes(check_out_end, work_start)
        if work_end_offset == 0 or check_in_offset == 0:
            raise InternalError("SCHEDULE_TIME_INVALID")
        if late_end_offset < 0 or late_end_offset < 1:
            raise InternalError("SCHEDULE_TIME_INVALID")
        if check_in_offset == 0 or check_in_offset < 0:
            raise InternalError("SCHEDULE_TIME_INVALID")
        if check_out_end_offset < work_end_offset:
            raise InternalError("SCHEDULE_TIME_INVALID")

    @staticmethod
    def create(*, name, work_start, work_end, check_in_start, late_end, check_out_end, location_name=None, location_latitude=None, location_longitude=None, location_radius_m=None, duplicate_policy="reject", is_active=True):
        ScheduleService._validate_window(work_start, work_end, check_in_start, late_end, check_out_end)
        location_values = (location_name, location_latitude, location_longitude, location_radius_m)
        if any(value is not None for value in location_values):
            if not location_name or location_latitude is None or location_longitude is None or location_radius_m is None:
                raise InternalError("LOCATION_CONFIG_INVALID")
            from attendance.location_validation import AllowedLocation
            try:
                AllowedLocation(location_name, float(location_latitude), float(location_longitude), float(location_radius_m))
            except ValueError:
                raise InternalError("LOCATION_CONFIG_INVALID")
        if duplicate_policy != "reject": 
            raise InternalError("SCHEDULE_TIME_INVALID")
        try:
            return Schedule.create(
                name=name, work_start=work_start, work_end=work_end,
                check_in_start=check_in_start, late_end=late_end,
                check_out_end=check_out_end, location_name=location_name,
                location_latitude=location_latitude, location_longitude=location_longitude,
                location_radius_m=location_radius_m, duplicate_policy=duplicate_policy,
                is_active=is_active,
            )
        except peewee.PeeweeException as e:
            raise InternalError(f"创建班次失败: {e}")

    @staticmethod
    def update(schedule_id, **fields):
        schedule = ScheduleService.get(schedule_id)
        values = {key: value for key, value in fields.items() if value is not None}
        merged = {name: getattr(schedule, name) for name in (
            "work_start", "work_end", "check_in_start", "late_end", "check_out_end"
        )}
        merged.update({key: values[key] for key in merged if key in values})
        ScheduleService._validate_window(**merged)
        values["duplicate_policy"] = values.get("duplicate_policy", schedule.duplicate_policy)
        location_keys = ("location_name", "location_latitude", "location_longitude", "location_radius_m")
        location_values = {key: values.get(key, getattr(schedule, key, None)) for key in location_keys}
        if any(value is not None for value in location_values.values()):
            if not all(location_values.values()) or location_values["location_radius_m"] <= 0:
                raise InternalError("LOCATION_CONFIG_INVALID")
            from attendance.location_validation import AllowedLocation
            try:
                AllowedLocation(location_values["location_name"], float(location_values["location_latitude"]), float(location_values["location_longitude"]), float(location_values["location_radius_m"]))
            except ValueError:
                raise InternalError("LOCATION_CONFIG_INVALID")
        if values["duplicate_policy"] != "reject":
            raise InternalError("SCHEDULE_TIME_INVALID")
        candidate = ScheduleService.get(schedule_id)
        if values.get("is_active", candidate.is_active):
            for employee in Employee.select().join(EmployeeSchedule).where(EmployeeSchedule.schedule == candidate):
                others = [row.schedule for row in EmployeeSchedule.select().where((EmployeeSchedule.employee == employee) & (EmployeeSchedule.schedule != candidate))]
                try:
                    ScheduleService._validate_no_overlap(candidate, others)
                except InternalError:
                    raise InternalError("SCHEDULE_CONFLICT")
        Schedule.update(**values).where(Schedule.id == schedule_id).execute()
        return ScheduleService.get(schedule_id)

    @staticmethod
    def disable(schedule_id):
        schedule = ScheduleService.get(schedule_id)
        Schedule.update(is_active=False).where(Schedule.id == schedule_id).execute()
        return ScheduleService.get(schedule.id)

    @staticmethod
    def _validate_no_overlap(candidate, others):
        intervals = []
        for schedule in [candidate, *others]:
            start = ScheduleService._clock_minutes(schedule.work_start)
            end = start + ScheduleService._relative_minutes(schedule.work_end, schedule.work_start)
            intervals.append((start, end, schedule.id))
            if end > 1440:
                intervals.append((start - 1440, end - 1440, schedule.id))
        for index, (start, end, sid) in enumerate(intervals):
            for other_start, other_end, other_sid in intervals[index + 1:]:
                if sid != other_sid and max(start, other_start) <= min(end, other_end):
                    raise InternalError("SCHEDULE_CONFLICT")

    @staticmethod
    def bind_employee(employee_id, schedule_ids):
        emp = EmployeeService.get(employee_id)
        schedules = [ScheduleService.get(schedule_id) for schedule_id in schedule_ids]
        ScheduleService._validate_no_overlap(schedules[0], schedules[1:]) if schedules else None
        with EmployeeSchedule._meta.database.atomic():
            EmployeeSchedule.delete().where(EmployeeSchedule.employee == emp).execute()
            for schedule in schedules:
                EmployeeSchedule.create(employee=emp, schedule=schedule)
        return list(EmployeeSchedule.select().where(EmployeeSchedule.employee == emp))

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

    @staticmethod
    def list_for_employee(employee_id):
        emp = EmployeeService.get(employee_id)
        rows = (EmployeeSchedule.select(EmployeeSchedule.schedule)
                .join(Schedule)
                .where((EmployeeSchedule.employee == emp) & Schedule.is_active)
                .order_by(Schedule.id))
        schedules = [row.schedule for row in rows]
        if not schedules and emp.schedule is not None and emp.schedule.is_active:
            schedules = [emp.schedule]
        return schedules


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
        face_image_path: Optional[str] = None,
        schedule_id: Optional[int] = None,
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
        if face_image_path:
            EmployeeService._validate_face_image_path(face_image_path)
        schedule = None
        if schedule_id is not None:
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
        """删除员工及其打卡记录、加密模板（由 UI 二次确认后调用）。"""
        try:
            emp = Employee.get_by_id(employee_id)
        except Employee.DoesNotExist:
            raise EmployeeNotFound(f"员工 {employee_id} 不存在")

        try:
            # 用户已在 UI 二次确认；先删除业务关联，再删除员工主记录。
            FaceTemplate.delete().where(FaceTemplate.employee == emp).execute()
            CheckRecord.delete().where(CheckRecord.employee == emp).execute()
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
# FaceTemplateService (S4 research boundary)
# ============================================================


class FaceTemplateService:
    """保存和读取加密模板；不接受原图，也不返回持久化明文。"""

    MODEL_VERSION = "facenet-mobilenet-128-v1"
    VALID_POSES = ("frontal", "left_45", "right_45")

    @staticmethod
    def replace_employee_templates(employee_id: str, vectors: dict, key: bytes) -> list[FaceTemplate]:
        if set(vectors) != set(FaceTemplateService.VALID_POSES):
            raise ValueError("必须提供 frontal、left_45、right_45 三个姿态模板")
        emp = EmployeeService.get(employee_id)
        records = []
        with FaceTemplate._meta.database.atomic():
            FaceTemplate.delete().where(FaceTemplate.employee == emp).execute()
            for pose in FaceTemplateService.VALID_POSES:
                record = encrypt_vector(vectors[pose], key)
                records.append(FaceTemplate.create(
                    employee=emp, pose=pose,
                    ciphertext=base64.b64decode(record['ciphertext']),
                    nonce=base64.b64decode(record['nonce']),
                    format_version=record['format_version'],
                    model_version=FaceTemplateService.MODEL_VERSION,
                ))
        return records

    @staticmethod
    def load_employee_vectors(employee_id: str, key: bytes) -> dict:
        emp = EmployeeService.get(employee_id)
        rows = list(FaceTemplate.select().where(FaceTemplate.employee == emp))
        if {row.pose for row in rows} != set(FaceTemplateService.VALID_POSES):
            raise ValueError("员工三姿态模板不完整")
        result = {}
        for row in rows:
            result[row.pose] = decrypt_vector({
                "format_version": row.format_version,
                "vector_size": 128,
                "dtype": "float32",
                "nonce": base64.b64encode(row.nonce).decode('ascii'),
                "ciphertext": base64.b64encode(row.ciphertext).decode('ascii'),
            }, key)
        return result


# ============================================================
# CheckService (§3.3)
# ============================================================


class CheckService:
    """打卡记录增查服务。"""

    VALID_TYPES: tuple[str, ...] = ("check_in", "check_out")

    @staticmethod
    def admin_adjust(admin_id, employee_id, check_type, schedule_id):
        try:
            admin = Admin.get_by_id(admin_id)
        except Admin.DoesNotExist:
            raise InternalError("ADMIN_NOT_FOUND")
        emp = EmployeeService.get(employee_id)
        CheckService._validate_check_type(check_type)
        schedule = ScheduleService.get(schedule_id)
        if not schedule.is_active:
            raise InternalError("NO_SCHEDULE")
        now = datetime.now()
        sequence = decide_check(
            list(CheckRecord.select().where(CheckRecord.employee == emp)),
            check_type, now,
        )
        if not sequence.allowed:
            raise InternalError(sequence.reason)
        record = CheckRecord.create(employee=emp, schedule=schedule,
            check_type=check_type, check_timestamp=now, check_date=now.date(),
            status="manual_adjusted", anomaly_reason=None, adjusted_by=admin)
        return record

    @staticmethod
    def _validate_check_type(v: str) -> None:
        """§5.2 校验器: check_type 必须在 VALID_TYPES。"""
        if v not in CheckService.VALID_TYPES:
            raise CheckTypeInvalid(
                f"check_type 非法: {v!r}, "
                f"必须是 {CheckService.VALID_TYPES}"
            )

    @staticmethod
    def create_record(employee_id: str, check_type: str, schedule_id=None, confirmed_early_leave=False) -> CheckRecord:
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
        schedules = ScheduleService.list_for_employee(employee_id)
        if check_type == "check_in":
            if schedule_id is not None:
                schedule = ScheduleService.get(schedule_id)
                if schedule not in schedules:
                    raise InternalError("NO_SCHEDULE")
            elif len(schedules) == 1:
                schedule = schedules[0]
            elif not schedules:
                raise InternalError("NO_SCHEDULE")
            else:
                raise InternalError("SCHEDULE_SELECTION_REQUIRED")
        else:
            previous = (CheckRecord.select()
                .where((CheckRecord.employee == emp) & (CheckRecord.check_type == "check_in"))
                .order_by(CheckRecord.check_timestamp.desc()).first())
            if previous is None or previous.schedule is None:
                raise InternalError("INVALID_SEQUENCE")
            schedule = previous.schedule
        records = list(CheckRecord.select().where(CheckRecord.employee == emp))
        if schedule_id is None and check_type == "check_in":
            # 保持历史服务调用契约；新 UI 始终传入所选/自动选定的 schedule_id。
            decision = decide_check(records, check_type, now)
        else:
            decision = decide_check(
                records, check_type, now,
                work_start=schedule.work_start,
                work_end=schedule.work_end,
                check_in_start=schedule.check_in_start,
                late_end=schedule.late_end,
                check_out_end=schedule.check_out_end,
            )
        if decision.status == "early_leave" and not confirmed_early_leave:
            raise InternalError("EARLY_LEAVE_CONFIRM_REQUIRED")
        if not decision.allowed:
            raise InternalError(f"{decision.reason} (错误码: {decision.status.upper()})")
        try:
            record = CheckRecord.create(
                employee=emp,
                schedule=schedule,
                check_type=check_type,
                check_timestamp=now,
                check_date=now.date(),
                status=decision.status,
                anomaly_reason=None if decision.status == "normal" else decision.reason,
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
    def has_admins() -> bool:
        try:
            return Admin.select().exists()
        except peewee.PeeweeException as exc:
            raise InternalError('无法读取管理员状态') from exc

    @staticmethod
    def _registration_code_hash(code: str, salt: bytes) -> str:
        return hashlib.pbkdf2_hmac('sha256', code.encode('utf-8'), salt, 600_000).hex()

    @staticmethod
    def _registration_code_values(code: str) -> dict:
        salt = os.urandom(16)
        return {'salt': salt.hex(), 'code_hash': AdminService._registration_code_hash(code, salt)}

    @staticmethod
    def initialize_registration_code() -> None:
        if AdminRegistrationCode.get_or_none(AdminRegistrationCode.id == 1) is not None:
            return
        try:
            AdminRegistrationCode.create(id=1, **AdminService._registration_code_values('123456'))
        except peewee.IntegrityError:
            if AdminRegistrationCode.get_or_none(AdminRegistrationCode.id == 1) is None:
                raise

    @staticmethod
    def _locked_registration_code() -> AdminRegistrationCode:
        return AdminRegistrationCode.select().where(AdminRegistrationCode.id == 1).for_update().get()

    @staticmethod
    def register_with_code(code: str, username: str, password: str) -> Admin:
        username = username.strip()
        if not 1 <= len(username) <= 50 or not 12 <= len(password) <= 128 or not password.strip():
            raise InternalError('用户名或密码不符合要求')
        if not 1 <= len(code) <= 128 or not code.strip():
            raise AuthFailed('设置码不正确')
        try:
            with AdminRegistrationCode._meta.database.atomic():
                setting = AdminService._locked_registration_code()
                supplied = AdminService._registration_code_hash(code, bytes.fromhex(setting.salt))
                if not hmac.compare_digest(setting.code_hash, supplied):
                    raise AuthFailed('设置码不正确')
                return AdminService.create(username, password)
        except (peewee.PeeweeException, ValueError) as exc:
            raise InternalError('注册失败') from exc

    @staticmethod
    def change_registration_code(admin_id: int, password: str, new_code: str) -> None:
        if not 12 <= len(new_code) <= 128 or not new_code.strip():
            raise InternalError('新设置码不符合要求')
        try:
            with AdminRegistrationCode._meta.database.atomic():
                setting = AdminService._locked_registration_code()
                admin = Admin.get_or_none((Admin.id == admin_id) & Admin.is_super)
                if admin is None or not hmac.compare_digest(admin.password_hash, sha256_hex(password)):
                    raise AuthFailed('管理员密码不正确或账号无权更换设置码')
                supplied = AdminService._registration_code_hash(new_code, bytes.fromhex(setting.salt))
                if hmac.compare_digest(setting.code_hash, supplied):
                    raise InternalError('新设置码不能与当前设置码相同')
                values = AdminService._registration_code_values(new_code)
                AdminRegistrationCode.update(**values).where(AdminRegistrationCode.id == 1).execute()
        except (peewee.PeeweeException, ValueError) as exc:
            raise InternalError('设置码更换失败') from exc

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
