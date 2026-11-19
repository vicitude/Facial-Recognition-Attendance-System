# SPEC-012 验收清单

- [x] TC-ENTRY-001：启动只显示签到，摄像头与识别均未开始。
- [x] TC-ENTRY-002：切换窗口释放相机，彩光尚在占用时保持原窗口。
- [x] PT-ENTRY-101：取消、关闭、Esc、凭据错误与无管理员结果均不建立后台。
- [x] PT-ENTRY-102：通过认证才建立 02–05，退出后回签到且下次重新验证。

- [x] TC-ENTRY-003：模拟受限屏幕工作区，签到窗口外框不越界，三个相机按钮及底部提示可完整显示或滚动到达。

专项验证：`py -3.12 -B -m pytest --noconftest -p no:cacheprovider -q tests/test_checkin_entry.py`，18 项通过。实际 Windows 任务栏布局和摄像头端到端验证未执行。
