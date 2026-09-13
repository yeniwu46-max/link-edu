# LINK 真实课堂升级：学习状态、教态证据与录像复盘

2026-09-13。本说明覆盖旧文档中“没有真实课堂录像”“视觉不足整份拒评”和“暂停仍按墙钟计时”的旧行为。没有迁移业务数据库，没有增加视频上传 API，没有自动重评历史课堂。

## 如何使用

1. 打开 `/classroom`，分别确认语音评课、摄像头授权。想录像时在开课前勾选 **本机录像**，默认关闭；云端截图分析仍需单独授权。
2. 打开摄像头后进行约 5 秒本地取景检查，可重新检查或直接继续。坐姿上半身即可；手不入镜不是错误，不要求持续举手、微笑。
3. 开始后可暂停/继续。暂停关闭设备采集、取消待播放内容、暂停录像和有效计时；继续由教师主动操作并重新准备设备。证据时间仍保留原墙钟坐标。
4. 点名优先；全班提问仅小明/小雨一人回应，小林只被点名时回应。被打断后显示“等待邀请续答”，教师说“继续”匹配最近中断对象；明确点名优先。换题关闭旧续答，不当作交流完成。
5. 有效授课至少 10 秒才可结束。结束后即使报告数据不足，也可预览录像，选择保存到本机、下载或放弃。预览前不自动保存、不自动下载。
6. 历史课堂跳转 AI 评课页。点击证据或“录像与课堂记录”，同时查看事件和本机视频。未录到的时段显示“该时段无录像”，不会跳到无关片段。

## 评课口径

整份报告仅检查：有效授课至少 10 秒；至少两段有效最终转写、合计至少 80 字；至少一次不少于 10 字且实际完整播放的学生回应。实现会去重，排除空白/无效转写以及中断、失败、未确认的播放。

动作与场景属于教态维度门槛：不足时教态为未评分，其余可被文字证据支持的维度继续。保持六维，不增加动作数量分。新报告保存 `data_readiness.version=classroom-readiness-2`，动作规则为 `motion-rubric-2`；旧报告不自动改分，当前规则允许的旧拒评报告可主动重评。

动作观察关联前后 5 秒的最终转写和实际完整播放回应，提供观察、候选上下文、边界及事件编号。这只是时间邻近，不证明动作教学意图，不识别指向目标，不从表情推断紧张、自信或投入程度。校准帧和开课前迟到的检测帧不进入正式证据。

学生状态 `version=2` 包含理解、概念、误解、纠正来源、待回答问题、中断上下文和互动状态；仅本节继承。模型在同一次流式请求返回 `state_version`、`intent`、`state_updates`、严格布尔 `topic_changed`。更新必须引用本轮最终转写，不能仅凭“不对”“懂了吗”更新。原模型单次输出上限由 600 调整为 1200 tokens，仍受既有预算预留控制，不额外新增独立判断请求。

## 时间与接口

所有接口沿用 JWT 与课堂归属校验：

| 入口 | 行为 |
| --- | --- |
| `POST /api/classroom/sessions/{id}/pause` | 幂等暂停；结束处理中返回冲突，关闭旧连接 |
| `POST /api/classroom/sessions/{id}/resume` | 幂等恢复；已结束或旧连接仍在退出时返回 409 |
| `GET /api/classroom/sessions/{id}` | 新增 `active_elapsed`、`wall_elapsed`、`report_stage`；`elapsed` 使用有效时长 |
| `POST /api/classroom/sessions/{id}/finish` | 重复结束不重新评审失败结果 |
| `POST /api/classroom/sessions/{id}/report` | 仅教师明确重试/重评后调用，保留预算控制 |

服务端确认断线时写入暂停，不由浏览器补算重连时长。暂停/恢复、学习更新、报告阶段均复用事件表。报告阶段是检查证据、整理证据、AI 评审、校验结果、完成/失败/证据不足，无推算进度百分比。

## 录像规格、保存与清理

- 固定 1280×720、24fps，优先 WebM/VP8/Opus，运行时尝试浏览器支持的 WebM 或 MP4；不申请屏幕共享。
- 合成教师、三个学生、气泡和当前显示字幕；不录设置窗口或其他桌面内容。教师麦克风和实际播放学生音频混音，学生保持 1.2 倍与输出音量；混音不送回 ASR。
- 暂停时关闭设备及录制，继续重新连接音轨。等待音轨就绪的延迟记录为空档，不伪装成完整录像。
- 单节 250 MiB 上限，接近上限预留尾部编码空间后停止录制；课堂继续。本机总额 1 GiB，空间不足不自动删除旧录像，可下载或手动清理。
- IndexedDB：`link-classroom-recordings` / `recordings`，键为 `[origin, userId, sessionId]`；不使用旧训练页的录像库。`localhost`、`127.0.0.1`、不同端口/协议属于不同站点。
- 在报告的“录像与课堂记录 → 管理本机录像”删除。关闭/删除释放当前 Blob URL；删除不能恢复，不影响已下载副本。清理浏览器数据会删除本机保存，换设备不会同步。
- 刷新或离开会提示未保存数据可能丢失；浏览器对离开提示有自身限制，不承诺崩溃恢复。退出/切换账户时释放尚未保存的录像，避免串账户展示。

## 自动化验证

测试使用隔离数据库、mock 模型、合成媒体及专用浏览器配置，不调用付费服务、不读取真实课堂。项目已有配置和私有数据不应复制到测试环境。

```powershell
python -m pytest backend/tests -q --disable-warnings
npm test --prefix frontend
npm run build --prefix frontend
python scripts/evaluate_classroom.py check
# 使用已安装独立评测依赖的 Python，不将 DeepEval 加入生产环境
artifacts/private/eval-venv/Scripts/python.exe -m pytest -p evals.offline_guard --eval-allow-loopback evals/tests -q
```

浏览器使用已安装的 Playwright CLI，在专用 session 运行（先安装项目依赖、启动 Vite 5188）：

```powershell
npx --no-install --package @playwright/cli playwright-cli -s=link-upgrade-qa open http://127.0.0.1:5188 --browser msedge
npx --no-install --package @playwright/cli playwright-cli -s=link-upgrade-qa run-code --filename scripts/qa-classroom-ui.js --raw
npx --no-install --package @playwright/cli playwright-cli -s=link-upgrade-qa run-code --filename scripts/qa-classroom-player.js --raw
npx --no-install --package @playwright/cli playwright-cli -s=link-upgrade-qa run-code --filename scripts/qa-classroom-recording.js --raw
npx --no-install --package @playwright/cli playwright-cli -s=link-upgrade-qa run-code --filename scripts/qa-classroom-upgrade-flow.js --raw
npx --no-install --package @playwright/cli playwright-cli -s=link-upgrade-qa close
```

`qa-classroom-ui.js` 必须先运行以安装网络/账户隔离 fixture。完整流程脚本使用假设备和假 REST/WebSocket，但真实 Canvas、Web Audio、MediaRecorder、IndexedDB 及页面逻辑。报告布局脚本 `qa-classroom-review.js` 自带另一套 fixture，建议另开 session，避免 mock 相互覆盖。

合成录制脚本检查 440Hz 教师声、学生 880Hz PCM 在 1.2 倍速后的 1056Hz 声音；使用视频播放时钟检测闪白帧与音频起点，不将 `decodeAudioData` 丢弃容器时间戳后的结果当作音画同步证明。同时验证暂停空档、恢复片段的红色标记和账户隔离。结果是当前浏览器/机器样本，不保证所有设备达到同样延迟。

## 真人验收清单（未由 mock 替代）

### 本轮自动化结果

- 后端 211 项、前端 147 项、独立 DeepEval 评测环境 30 项通过。
- 默认断网 `check`：19 项规则通过，0 失败/错误，101 项未评估（包含语义与人工入口）；不能将 19/19 宣称为全场景质量通过率。
- Edge 隔离浏览器：课堂/报告 320、768、1024、1440px，全屏稳定性、键盘焦点与减少动画检查通过；开始→暂停→继续→预览→保存→报告回放→下载→删除合成录像通过。
- 最新合成标记样本：音画偏差约 108ms、证据定位偏差约 82ms，暂停后红色标记定位正确。不是跨浏览器或真机性能承诺。
- 生产构建通过，仍存在既有的大包提示（主包约 1.19MB，另有约 539KB 特效包）；后端有既有日期/依赖弃用警告，未掩盖这些提示。

### 人工项

- [ ] 摄像头权限拒绝/撤销、麦克风拔出、网络中断后手动恢复，暂停期间指示灯和声音采集确实停止。
- [ ] 坐姿、手未入镜、多人、遮挡、模型加载失败的模态提示正确；姿态不足不阻止其他维度。
- [ ] 姓名与问题分段、点名小林、反问、自言自语、无效纠正和有效解释；真实模型不虚构认知更新。
- [ ] 教师打断、邀请继续、换题、TTS 失败和回声；没有未播放文字被认定为完整互动。
- [ ] 真实镜头/师生声音/字幕同步、1.2 倍速、调节音量，长时间授课及全屏/后台切换的编码稳定性。
- [ ] 单节容量停止、浏览器配额不足、下载/放弃/刷新提示、跨账户与清理缓存后的降级。
- [ ] 目标浏览器和设备上测量音画及证据定位误差 ≤500ms；不支持音轨处理器时也需验证降级路径。

设计原因见 [ADR-003](decisions/003-learning-clock-local-replay.md)。本次不自动调整提示词之外的教学策略、不修改旧评分、不执行生产部署或 GitHub 推送。
