# 课堂播放器与学生形象改版

更新时间：2026-09-10。接续 [上一轮技术交接](classroom-handoff-20260910.md)。本轮是前端改版，不改后端接口、真实课堂数据、报告门槛和费用配置。

## 使用变化

- 教学训练直接进入 `/classroom`；旧 `/training` 兼容重定向，不再经过旧演示舞台。`?mode=fragment` 预选 8 分钟，默认 10 分钟。导航不自动开摄像头、不开始授课。
- 当前真实课堂仍是“分数的初步认识”；旧链接的 `courseId` 不伪装成另一门已支持的实时课程。
- 授权条精简为小字。仅缺授权时一行提示；服务失败优先显示具体原因，全部阻止原因可展开，保留刷新和设置入口。
- 视频下沿固定播放器式控制栏：开始/结束、打断学生、暂停采集、学生音量、CC 字幕、清晰度、记录、设置、全屏。图标保留可访问名称、鼠标与键盘提示。
- 相机可以单独预览；全屏未授权时明确提示退出全屏完成授权。原有 10 秒结束门槛、报告数据量门槛、设备暂停与授权边界不变。
- 动作技术状态移到设置中，课堂主体不再重复堆叠说明文字。报告证据和记录查看不变。

## 形象与动效

用户提供六张角色图，小明紫衣、小雨橙衣、小林蓝衣，分别有听讲和举手版本。双图预载，减少首次响应时闪图。听讲轻微呼吸，思考/生成/等待语音时举手，实际发言显示声波条；终态回到听讲，文字仍保留 15 秒。

素材在 `frontend/public/assets/students/`：

| 学生 | 听讲 | 举手 |
| --- | --- | --- |
| 小明 | `ming-listening.png`（原图 4） | `ming-raised.png`（原图 7 抠图） |
| 小雨 | `yu-listening.png`（原图 5） | `yu-raised.png`（原图 8） |
| 小林 | `lin-listening.png`（原图 6） | `lin-raised.png`（原图 9） |

五张原图直接复制；原图 7 的灰白格已通过内置 imagegen 去除，未修改用户源文件。六张输出均为 1254×1254，已检查角落 alpha 为 0。资产来自用户提供，并非第三方图标库授权资产；公开分发前由项目方确认使用权。

抠图最终提示词（内置模式，非 CLI/API）：

> Use case: background-extraction. Edit target: the attached pixel-art schoolboy raising his hand in a purple sweater. Remove ONLY the baked-in gray/white checkerboard background. Output an actual RGBA transparent background, including empty gaps around the hand/body. Keep the exact same boy, facial features, expression, raised hand pose, pixel-art outlines, purple sweater, shorts and shoes, proportions and complete full body. Keep square framing and original placement and scale. No checkerboard, no solid background, no new shadows, no text, no additional objects. This is a web app character sprite; preserve sharp pixel edges and the supplied identity.

动效复用现有技术：Tabler 图标、NumberFlow 倒计时、CSS 呼吸/举手/光标/镜头呼吸环、Vue 气泡过渡。尊重 `prefers-reduced-motion`，不让动画改变主画面的几何尺寸。没有新增 npm 依赖或下载额外 skill。

## 1.2 倍速实现与边界

`ClassroomAudio` 使用固定 `STUDENT_PLAYBACK_RATE=1.2`。保持提供方 PCM 采样率不变，播放节点设置倍速，并按 `buffer.duration / 1.2` 调度下一块与完成回执。仅学生播放加速，不加速教师采集、ASR、课堂计时或动画计时。

这是 Web Audio 播放倍速，不是服务端合成语速，也不做保调时间拉伸，因此音调会略升。真实流式网络若供给速度不足，仍可能等待下一音频块。本轮合成静音测试验证调度与回执，不代替真人听感与回声测试。实现依据：[MDN playbackRate](https://developer.mozilla.org/en-US/docs/Web/API/AudioBufferSourceNode/playbackRate)、[MDN start 时间语义](https://developer.mozilla.org/en-US/docs/Web/API/AudioBufferSourceNode/start)。

布局参考播放器的时间/清晰度/音量/设置分组，不接入 B 站服务或复制其品牌资产；参考 [bilibili 播放器公开演示](https://www.w3.org/2019/03/23-chinese-web-zhaoxin-bilibili.pdf)。

## 验证与修复

- 单元测试先验证失败，再实现入口重定向、角色状态与 1.2 倍速 PCM 调度。前端共 86 项通过。
- 浏览器使用独立 Edge 会话，API mock、合成画面与静音音轨；未读取生产课堂数据、未触发真实设备或付费模型。
- `qa-classroom-ui.js`：权限、四档页面宽度、历史、设置、报告及证据跳转。
- `qa-classroom-start-hint.js`：HTTP 500、过期能力缓存、预算停止、缺少单价、授权与重连提示。
- `qa-classroom-camera-preview.js`：单独视频预览、拒绝后重试、关闭与撤权释放。
- `qa-classroom-motion.js`：骨架、字幕、固定三学生、流式内容与教态报告；原生及降级全屏。
- `qa-classroom-player.js`：旧入口直达、六图加载、听讲/举手切换、工具栏静音恢复、字幕/清晰度、320/768/1024/1440 宽度、焦点与 tooltip 越界回归。
- `qa-classroom-live-response.js`：真实 Vue/Web Audio + mock WebSocket，连续流式回复、播放完成回执、15 秒停留、844×390 横屏与设备释放。
- 浏览器检查中修复了 tooltip 撑宽 320px 全屏、横屏相对定位气泡越界；补齐已有 `NConfigProvider` / `NMessageProvider` 导入，消除组件未注册警告。

运行：`npm --prefix frontend test`、`npm --prefix frontend run build`。浏览器脚本用已有 Playwright CLI 执行，先跑 `qa-classroom-ui.js` 建立 mock 环境，再跑其他脚本。默认 Chrome 在本机无法启动时，可通过 `open about:blank --browser msedge` 使用独立测试会话；不修改用户浏览器配置。

截图保存在忽略目录 `output/playwright/`。前端构建仍有既有大包警告；并非发布性能认证。录像/预览保存仍未实现。本轮不自动 Git 提交或推送。

旧 `TrainingView.vue` 暂保留作历史参考，但已不挂载、不会进入本次构建的路由模块；旧训练 API 和历史报告没有删除，后续清理应独立确认。
