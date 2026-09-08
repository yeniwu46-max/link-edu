# 2026-09-08：讯飞语音接入与联调

本机已选 `SPEECH_PROVIDER=xfyun`。DeepSeek 对话/视觉保持不变，百炼适配仍保留，但不自动回退。此文是 9 月 8 日状态入口，优先于 9 月 7 日历史记录。

## 配置与启动

仅在 `backend/.env` 配置：

```dotenv
SPEECH_PROVIDER=xfyun
XFYUN_APP_ID=本机填写
XFYUN_API_KEY=本机填写
XFYUN_API_SECRET=本机填写
XFYUN_TTS_VOICE=xiaoyan
XFYUN_ASR_CNY_PER_CALL=0.0023
XFYUN_TTS_CNY_PER_CALL=0.0058
XFYUN_PRICING_CONFIRMED=true
```

同时保留原 `AI_PRICING_CONFIRMED=true` 与 DeepSeek 单价。`XFYUN_TTS_VOICE_MING/YU/LIN` 可选，空值共享默认音色；目前只核验了默认 `xiaoyan`，不声称三音色均有权限。配置缺失或价格未确认时不发请求。不要整文件覆盖已有数据库/JWT/DeepSeek 设置。

修改配置后重启新版后端，再运行 `./scripts/start-classroom.ps1`。入口 `http://127.0.0.1:5188/classroom`，后端 5001，均仅绑定本机。脚本不自动停止占用端口的进程，需核对当前进程确实加载新版代码。

用户明确选择暂不轮换凭证；已按要求把 `yeniwu46-max/link-edu` 从 PUBLIC 改为 PRIVATE，并查询确认。密钥仍仅在忽略文件，不进入 Git；私有仓库不消除已有聊天暴露。本轮代码未推送远端。

## 协议和实现约束

- 识别：`wss://iat.xf-yun.com/v1`、`domain=slm`、中文、PCM16/16kHz；HMAC-SHA256 签名仅在服务器建立，签名 URL 不写日志。
- 合成：`wss://tts-api.xfyun.cn/v2/tts`、系统音色、UTF8 文本、PCM16/16kHz。前端按音频事件 `sample_rate` 播放；百炼仍为 24kHz。
- 本地 RMS 能量端点检测：40ms 帧，连续约80ms起音、600ms静音收尾、200ms预留音频；这是启发式语音活动检测，不是准确语音分类或情绪识别，须实测环境噪声和回声。
- 单识别段最长55秒，连续讲话滚动换段，不重置学生记忆，也不产生虚假教师停顿。发送队列最多250个命令（约10秒音频），积压过限停止并明确报错，不静默丢音。
- 发送采用固定40ms节拍，避免 Windows 定时器超时与发送耗时逐帧累积；连接延迟后最多追赶200ms，避免集中突发发送大量旧音频。只记录队列峰值、字节数和发送耗时，不记录音频内容到日志。
- 识别 `sn/pgs/rg` 做序号追加与范围替换，结果按分段顺序提交；最终文字才入档。`二分之一` 可被识别服务规范化为 `1/2`，保持原始返回文本。
- 尾部识别超时从结束帧实际发出后计算8秒，整段收尾最多30秒。重连需新票据；不会重播丢失的未确认音频。
- 合成取消后丢弃迟到声音；连接期间取消且尚未发送文本时，台账记0次/0元。发送后失败或用量未知则保留预留，不能当作供应商退款。
- `/capabilities` 新增服务商、语音价格确认、音色字段。适配层统一 `speech_started/speech_stopped/partial/final/finished`，浏览器业务协议与账号归属不变。
- 旧评课校正 API 对本人记录返回409、其他账号404；原记录不改分，旧页面只读。新报告异议仍携原证据重评。

## 价格来源与边界

核对日期2026-09-08。中文识别官方产品页中文套餐一为100万次2300元，即23元/万次；个人试用包2万次与用户截图一致。[官方识别产品页](https://www.xfyun.cn/services/speech_big_model)

在线合成官方页面列50万次2000元，另一官方区域站列100万次5800元。本机采用较高的0.0058元/次作为套餐折算估值，不假设用户已购买套餐，也不购买新音色。[合成产品页](https://www.xfyun.cn/services/online_tts?target=price)、[官方区域站套餐](https://qingdao.xfyun.cn/services/online_tts)

每段识别、每次合成分别记一次调用，`xfyun_asr/xfyun_tts` 与百炼区分，记录音频秒数或文本字符数。免费额度是否仍剩余以控制台为准；本地按正数套餐折算做保守记账，不冒充实际账单。保留总预算100元、80元提示、90元含在途停止，不自动充值。

## 已验证与待验证

- 46项后端测试通过（含收尾、取消、固定节拍和禁止静默回退回归）；前端构建通过，运行时依赖审计0漏洞。原大包提示、遗留弱JWT签名限制仍在。
- 真实讯飞识别静音探针0.844秒通过；真实合成0.680秒返回音频。识别静音探针不证明中文准确率。
- 真实合成9.329秒的自编分数教学句再送入识别，返回完整内容，`二分之一`规范化为`1/2`。首版脚本因只匹配汉字判失败，原结果保留，后续谓词接受等价写法，不篡改原始转写。
- 首次185秒循环因发送节拍逐帧累积延迟触发队列保护而失败，原记录保留在本机 `artifacts/private/speech-probe-20260908-120525/result.json`。修复发送节拍后第二次通过，记录为 `artifacts/private/speech-probe-20260908-120852/result.json`：185秒音频、11个最终分段、耗时185.122秒、发送5,920,000字节（等于全部输入）、队列峰值7，未报错。通过条件是链路结束及知识点关键词检查，不是逐字准确率或真人课堂验收。
- 第二次长测试后，本地累计费用与预留估计0.1474元，包含此前测试；不是供应商实际账单。测试音频是自编文本的系统音色合成，不包含真人录音。
- 浏览器工具读取控制台/页面超时，今日真人麦克风、摄像头、真实浏览器声音播放仍未验证。
- 三次真人10分钟课堂、20轮真实声学P95、真实长课堂报告60秒及录屏仍待执行；不能用合成音频循环代替。

```powershell
python -m pytest backend/tests -q --disable-warnings
npm run build --prefix frontend
# 下列命令实际消费接口用量；生成的音频与结果只写 artifacts/private
python scripts/probe_classroom.py asr tts
python scripts/validate_speech_loop.py
python scripts/validate_speech_loop.py --seconds 185
```

真人验收按 [现场验收记录模板](课堂现场验收.md) 与 [原验收清单](classroom-validation.md) 执行，语音供应商改为讯飞。接口详情与资料使用见 [技术沉淀](技术沉淀.md)。
