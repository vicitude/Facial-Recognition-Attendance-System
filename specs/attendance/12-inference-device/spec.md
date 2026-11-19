# SPEC-009：统一 CUDA/CPU 推理设备

## 0 元数据
状态：已实现（自动化验证完成，现场效果未验收）；版本 v1.0.0；PO：用户；TL/QA：当前 Agent。关联 attendance/inference_device.py、attendance/liveness_research.py、facenet/facenet.py、tests/test_inference_device.py。无 HTTP API、数据库迁移和新业务字段。门禁：pytest tests/test_inference_device.py 与既有活体专项通过后才移除独立 GPU 环境。例：CUDA 可用时输出设备 cuda:0。本地 Python 契约由 pytest 执行，不声明 OpenAPI 或 Gherkin 运行器存在。

## 1 术语
|术语|英文名|类型|定义|代码映射|数据库映射|示例|
|---|---|---|---|---|---|---|
|设备|device|值对象|torch.device|模型.device|无|cpu、cuda:0|
|自动选择|auto|策略|CUDA 可用则 CUDA，否则 CPU|resolve_device|无|None|

## 2 验收场景
```gherkin
Given CUDA 不可用
When resolve_device(None)
Then 返回 cpu
Given CUDA 可用
When resolve_device(None)
Then 返回 cuda:0
Given 显式 device 为 cpu
When 构造两个推理模型
Then 参数和输入均在 CPU
```
权限边界：安装和删除环境仅执行用户本次授权；不打开正式库和相机。例：CUDA 推理异常不得静默重试 CPU。

## 3 Python 接口
resolve_device(device=None) 返回 torch.device；None 自动选择，其余传给 torch.device，不改变异常。LivenessResearch(assets=DEFAULT_ASSETS, device=None) 新增末尾可选参数。Facenet(**kwargs) 保持签名；默认 cuda=None 表示自动，cuda=False 强制CPU，cuda=True 在 CUDA 不可用时使用CPU。例：LivenessResearch(device='cpu')。

## 4 数据与校验
self.device 为 torch.device，构造时必赋值；FaceNet self.cuda 为实际 CUDA bool。现有128维float32返回、BGR/0-255/三类概率均不变；不增加持久化字段。模型权重先在 CPU 加载，load_state_dict 后 model.to(self.device).eval()；输入在调用模型前 .to(self.device)，返回 .cpu().numpy()。例：输出向量仍为 numpy float32 (128,)。

## 5 规则与 Properties
设备状态固定于模型构造，推理期间不自动切换。resolve_device返回CUDA前设置torch.backends.cudnn.allow_tf32=False及torch.backends.cuda.matmul.allow_tf32=False，保持FP32精度；该进程级设置也影响YOLO，不改变模型权重与阈值。真实对照发现默认TF32使FaceNet最大误差0.000571683，关闭后0.000000395，因此必须关闭。Yolo旧逻辑不改，MediaPipe仍CPU。P-DEV-01：∀ available∈{False,True}，resolve_device(None).type == ('cuda' if available else 'cpu')；P-DEV-02：显式CPU始终CPU。由 PT-DEV-01 参数化验证。GPU错误向上传播，不降低任何活体/匹配阈值。例：显存不足仍报错。

## 6 错误与日志
沿用 torch 的无效设备、权重、CUDA异常，无新增业务错误码。验证记录只输出设备、版本、时延、最大数值误差；不得记录密钥/人脸向量/精确位置/凭证。例：cuda_available=True。

## 7 覆盖矩阵
|需求|ID|类型|测试|状态|
|---|---|---|---|---|
|选择策略/P-DEV-01/02|REQ-DEV-01|属性|PT-DEV-01|实现时自动化|
|模型与输入同设备、CPU/CUDA结果|REQ-DEV-02|模型集成|CT-DEV-02|实施时自动化|
|现有活体契约|REQ-DEV-03|回归|既有活体专项|已有自动化|
CT-DEV-02无CUDA时跳过CUDA部分，CPU部分不跳过；本次清理环境的门禁必须在真实CUDA上通过。

## 8 非功能与环境门禁
仅升级 opencv4 的 torch==2.8.0+cu126、torchvision==0.23.0+cu126，保留其他包；安装前保存freeze/pip check结果，安装后对比。真实模型使用合成图测试FaceNet和两MiniFASNet CPU/CUDA一致性：向量最大绝对误差<=1e-4，概率<=1e-4；有限值且归一化。GUI离屏构造不进入登录/正式库；导入加密/定位依赖成功。删除前核对目标venv配置、运行中进程、路径不是链接，验证全部通过才删除 opencv4_gpu，禁止删除其他环境。例：pip check若原有冲突则记录前后差异，不称全绿。

## 9 假设与约束
用户授权替换依赖和验证后删除独立环境；NVIDIA驱动支持cu126。无commit/push/reset/clean，不改ui.py/recognition.py/get_name.py主体，不改数据库，不承诺现场攻击验收。现场效果仍由用户验收。版本历史由未来Git提交生成；当前未提交，不虚构Commit。
