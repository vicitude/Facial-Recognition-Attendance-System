from datetime import time
import pytest
from attendance.services import ScheduleService
from attendance.utils import InternalError


def args(**extra):
    value = dict(name="地点班次", work_start=time(9), work_end=time(18), check_in_start=time(8), late_end=time(12), check_out_end=time(23))
    value.update(extra)
    return value


def test_partial_location_is_rejected():
    with pytest.raises(InternalError, match="LOCATION_CONFIG_INVALID"):
        ScheduleService.create(**args(location_name="总部"))


def test_invalid_radius_is_rejected():
    with pytest.raises(InternalError, match="LOCATION_CONFIG_INVALID"):
        ScheduleService.create(**args(location_name="总部", location_latitude=39.9, location_longitude=116.4, location_radius_m=0))
