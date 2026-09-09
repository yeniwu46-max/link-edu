# 课堂动作捕捉与教态评价

实现日期：2026-09-09。适用入口：模拟课堂 `/classroom`。这是对在线课堂动作证据链的增强；不改变历史报告，不增加数据库表，不给演示页填入真实评分。

后续同日更新：镜头不再可选，开始前需双授权，关闭镜头会一同暂停音频采集；新在线报告还需通过整课最低数据检查。下文早期流程保留作实现记录，当前流程以 [摄像主画面与评课数据门槛](classroom-camera-first.md) 为准。

## 已实现

复用项目已有的 [Google MediaPipe](https://github.com/google-ai-edge/mediapipe)，增加 Gesture Recognizer 和 Face Landmarker。沿用现有 `@mediapipe/tasks-vision` 依赖及锁文件，没有再引入另一套运行框架。MediaPipe 仓库采用 Apache-2.0；部署模型时应同时保留上游模型说明与适用条款。

```text
可选摄像头（本地）
  → 身体 Worker + 手势 Worker + 面部 Worker
  → 白名单动作摘要 → 现有 pose 事件（服务端时间戳、事件 ID）
  → motion_evidence 观察 / 上下文建议 / 可用性
  → 最终评课 AI 的 posture「教态与站位」维度
  → 报告展示、证据时间点跳转、教师补充说明后重评
```

仍保留原有六个维度，不重复添加第七个分数，也不设固定动作加减分。最终 AI 接收动作证据及课堂转写、播放状态、教学参考资料，结合语境作出评价。离线评测的报告生成和规则检查也同步接入同一动作证据逻辑。

## 检测能力与评价映射

| 检测内容 | 服务端观察 | 供评课 AI 使用的教态建议 / 边界 |
| --- | --- | --- |
| 肩、髋与腕位置 | 肩髋可见时计算画面内躯干侧倾；手腕高于肩部 | 联系板书、演示与互动语境；坐姿只见上半身时不虚构躯干角度 |
| 展开手掌 | `Open_Palm` | 核对是否帮助呈现概念或操作过程，示范部位是否保持入镜 |
| 食指向上 | `Pointing_Up` | 核对是否与当前重点或问题一致；不能判断实际指向对象 |
| 拇指向上 / 下 | `Thumb_Up` / `Thumb_Down` | 结合反馈语判断是否具体解释正确点、错因与改进方向 |
| 握拳、V 形、特定三指手形 | 对应手形标签 | 只记录形状，结合内容审阅，不直接解释意图或态度 |
| 鼻部相对双眼位置、双眼连线倾角 | 面部朝向镜头的几何线索、画面内头部倾斜 | 不等同看向学生或目光交流，不推断自信、情绪、疲倦、人格 |
| `jawOpen` 形变系数 | 口部张开线索 | 不单独证明讲话时长、发音质量或情绪，需结合实际授课证据 |

几何角度均为二维画面线索，不是医学体态测量，也不是三维动作捕捉或视线追踪。不会进行身份识别、人脸比对或情绪分类。

首版启发式规则版本：`motion-rubric-1`。身体关键点 visibility 阈值 0.6；手形类别分数阈值 0.7；面部只检查关键点几何有效性，不编造 API 未返回的检测置信度。躯干角度 ≤15° 记接近竖直，>20° 记侧倾线索；鼻部偏移比 ≤0.25 记大致朝向镜头，>0.35 记偏离线索；头部画面倾角 >20°、口部张开形变 ≥0.5 分别记录。这些是可调整的工程阈值，**未经教师标注校准，不是教育学质量标准**。

## 证据与评分保护

- 前端最多约 10Hz 处理画面，只保留一个在途帧；发给后端的摘要约 2.1 秒一次，后端原有 2 秒限流继续生效。超过 1.5 秒的过期推理不上传；本地骨架超过 750ms 自动隐藏。
- 原始身体/手/面部关键点仅在 Worker 与本地画布之间传递，不写入课堂事件。后端只允许结构化状态、有限数值和已知手形，不接受客户端自报分数、任意评价文本、图片或身份字段。
- `observed / no_detection / low_confidence / multiple / failed / loading / disabled` 分开记录；每个模态保留有效数、总数及状态分布。模型文件存在只表示已安装，不表示检测成功。
- 身体或面部检测到多人时，整帧不归属某位教师；不尝试身份跟踪。手部可用而身体不可用时，可只提供手势证据，反之亦然。
- 新版动作证据至少有 3 个可观察样本且首尾相隔至少 4 秒才可支持该维度评分。它是最低证据门槛，不代表整堂课充分覆盖；无证据仍为 `null`。旧版姿态和既有云端视觉证据沿用原有校验规则。
- 每条观察显示匹配样本数 / 该指标适用的有效样本数，以及代表性事件 ID。坐姿下无法计算角度的样本不进入躯干角度分母。间隔超过 4 秒或出现不匹配样本会中断连续采样跨度；跨度并不证明动作持续了这么久，比例也不等于整堂课时长比例。
- 生成报告前从完整事件集汇总，再压缩重复事件；所有代表性引用保留在 AI 输入中。最终报告校验仍对完整事件集进行，伪造 ID、证据不足不能产生教态分数。
- 语义评价由 AI 辅助生成，提示词限制并非绝对保证；需人工核对是否过度解释动作，并可通过“补充说明”按证据重评。客户端摘要是训练辅助证据，不提供防作弊或传感器真实性证明。

## 安装与使用

在项目根目录执行：

```powershell
npm --prefix frontend ci
node scripts/prepare-pose.mjs
npm --prefix frontend run dev
```

安装阶段需访问官方模型下载地址。现有机器已安装身体、手势、面部模型；部署时也要运行准备脚本，随后构建 `npm --prefix frontend run build`。模型与 WASM 位于 `frontend/public/models/`，被 Git 忽略但会进入 Vite 构建产物；部署时不可遗漏。运行时使用本地同源文件，不走模型 CDN。

新增模型固定使用官方 `float16/1` 路径：

- [Gesture Recognizer 模型](https://storage.googleapis.com/mediapipe-models/gesture_recognizer/gesture_recognizer/float16/1/gesture_recognizer.task)，8,373,440 字节，SHA-256 `97952348cf6a6a4915c2ea1496b4b37ebabc50cbbf80571435643c455f2b0482`。
- [Face Landmarker 模型](https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task)，3,758,596 字节，SHA-256 `64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff`。

打开模拟课堂 → 按原流程同意语音识别与 AI 评课 → 开启“老师镜头”。身体/手势/面部状态分别展示；失败可“重新加载动作模型”。关闭镜头会释放摄像头及检测线程，不关闭语音会话。

结束课堂后，在“教态与站位”查看 AI 评价，展开“教态动作证据”检查样本、建议和事件跳转。若旧报告没有此字段，需由用户主动重新评课；不会自动修改历史结果。

本地动作推理不调用付费模型。最终 AI 评课仍走项目原有授课额度及预算控制；仅当另外开启“云端画面分析”时才沿用原有截图上传链路。默认镜头和云端画面分析均关闭。

## 验证与真人验收

已完成：

- 前端单元测试：几何计算、坐姿、遮挡、多人、手势置信度、面部非情绪输出、Worker 重启竞态与超时、关闭镜头及过期响应隔离。
- 后端和离线评测：白名单过滤、NaN / 非法结构、单帧 / 不可用不评分、报告 AI 输入含完整汇总及合法代表性引用，既有课堂测试无回归。
- Edge 浏览器：开发模式及生产构建的三个真实模型均在 Worker 中加载并推理合成空白帧，结果均为 `no_detection`；生产构建本次加载与首帧共约 2.7 秒（仅本机一次检查，不是性能基准）。无摄像头或云服务调用。MediaPipe 有 XNNPACK 初始化与反馈张量等日志，不是任务失败。
- 合成课堂 UI：320 / 768 / 1024 / 1440px 无横向溢出，全屏、面部轮廓、状态标签、失败重载入口、报告时间点跳转通过。截图在 `output/playwright/`（本地忽略目录）。

复现：

```powershell
npm --prefix frontend test
npm --prefix frontend run build
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
artifacts/private/eval-venv/Scripts/python.exe -m pytest -p evals.offline_guard --eval-allow-loopback backend/tests evals/tests -q
# 在开发服务上打开 /diagnostics.html，点击合成空白帧测试，不会开摄像头
# 独立 Playwright 会话：先 qa-classroom-ui.js，再 qa-classroom-motion.js
# 生产构建：在 5191 端口启动 Vite preview，打开页面后运行 qa-motion-bundle.js
```

本次回归结果：前端 52 项、后端及离线评测 182 项通过，生产构建通过（仍有既有主包大小提示）。测试未调用真实付费 AI，未对真实课堂数据库做写入。

尚未宣称通过：真人检测准确率、低端设备持续运行性能、不同光照/肤色/眼镜/机位/活动方式的覆盖、公平性或教育评分效度。正式使用前，经参与者同意采样：坐姿、站姿、板书侧身、双手演示、部分遮挡、多人误入、逆光与模型加载失败；人工逐时间点核对误检漏检，审查 AI 是否把动作误解为心理状态。不要为提高检测覆盖率要求教师始终站立或保持某种表情。

## 代码与来源

- `frontend/src/services/motionFeatures.js`：本地动作摘要。
- `pose.worker.js / hands.worker.js / faces.worker.js / motionTaskClient.js`：独立任务与恢复。
- `backend/services/classroom_motion.py`：白名单、规则映射、覆盖率与时间点。
- `backend/services/classroom_reports.py`：最终 AI 输入、引用及评分校验。
- `ClassroomCamera.vue / ClassroomReport.vue`：本地可视化与证据展示。
- [官方手势 Web 指南](https://developers.google.com/edge/mediapipe/solutions/vision/gesture_recognizer/web_js)与[面部 Web 指南](https://developers.google.com/edge/mediapipe/solutions/vision/face_landmarker/web_js)：自定义本地任务接入所依据的 API 文档。

此前两份研究文档中的“可观察事实与语义评审分层、证据引用、人工复核”原则用于本实现；OpenMAIC 的课堂框架及 DeepEval 不进入浏览器在线动作检测。已有 DeepEval 离线体系仍用于回放评审，详见 `classroom-offline-evaluation.md`。
