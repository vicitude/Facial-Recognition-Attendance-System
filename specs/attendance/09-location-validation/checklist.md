# SPEC-005 Checklist
- [ ] CHK-LOC-001 坐标范围校验。
- [ ] CHK-LOC-002 Haversine 距离与闭边界。
- [ ] CHK-LOC-003 越界和不可用定位拒绝。
- [ ] CHK-LOC-004 多地点取最近允许点。
- [x] CHK-LOC-005 模拟测试与编译通过。
- [x] CHK-LOC-006 定位来源契约可用且不调用网络/Windows API。
- [x] CHK-LOC-007 签到前判定服务覆盖允许、越界、不可用和未配置地点。
- [x] CHK-LOC-008 Windows Runtime 缺失时安全降级为不可用定位。
