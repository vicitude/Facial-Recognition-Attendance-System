"""SPEC-003 管理员补签服务契约。"""
from attendance.models import Admin
from attendance.services import CheckService, EmployeeService


def test_admin_adjust_marks_manual(sample_schedule):
    admin = Admin.create(username="adjust_admin", password_hash="x")
    EmployeeService.create(employee_id="300001", name="补签员工", department=None, position=None, phone=None, email=None, face_image_path=None, schedule_id=sample_schedule.id)
    rec = CheckService.admin_adjust(admin.id, "300001", "check_in", sample_schedule.id)
    assert rec.status == "manual_adjusted"
    assert rec.adjusted_by_id == admin.id
    assert rec.schedule_id == sample_schedule.id
