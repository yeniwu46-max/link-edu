# 第三方依赖与资源

`frontend-packages.json` 记录 npm 锁文件的版本、来源、完整性值及许可证字段；`licenses/` 保留已安装依赖包附带的许可证或声明原文。后端锁定版本见 `backend/requirements.lock.txt`，安装时须保留各 Python 分发包的 dist-info 许可证元数据。

`browser-models.json` 记录本次随包分发的 MediaPipe 模型及 WASM 文件哈希、官方下载来源。模型权利及使用条件以各自上游发布内容为准，不将第三方模型表述为团队自研权重。

资源库原有公开大纲与院校材料保留其作者、出处及资源入口，临客自编知识卡单独标注。公开可访问不等于放弃版权；对外再分发应遵循原作者许可。本包不授予超出原权利人的授权。

云端 DeepSeek、讯飞、OpenAI Next 等适配器属于调用代码，不包含供应商商业模型权重。具体服务权限和费用随账户与服务合同确定；有效密钥由项目持有人另行提供。

执行 `python scripts/export_dependency_inventory.py` 可在完成 `npm ci` 后重建清单。

2026-10-08 增加 Cesium Man 3D 人物资产：模型及原始 CC BY 4.0 许可位于 frontend/public/assets/models/，credits.json 记录作者、来源、固定提交、哈希和材质改编。Vue Bits 的完整 MIT + Commons Clause 条款保留于 licenses/vue-bits/LICENSE.md。集成范围见 [3D 与交互说明](../../docs/ui-effects-integration.md)。

2026-10-08 增加 Kenney Mini Characters 1.0（CC0）课堂学生：选用 character-male-a、character-female-b、character-male-e 及 aid-glasses。模型、贴图、完整 LICENSE.txt 与 credits.json 位于 frontend/public/assets/models/students/。scripts/prepare_student_models.py 固定官方下载包及 SHA-256，裁剪未使用动画并记录改编前后哈希；本地部署后运行时不请求 Kenney。Three.js 使用现有 MIT 依赖。改编与验收结果见 [教学训练升级说明](../../docs/classroom-ui-upgrade.md)。

2026-10-08 增加 @pixiv/three-vrm 3.5.5（MIT）及 Polygonal Mind 的 Olivia 1.0（VRM 元数据 CC0）。人物与透明封面本地部署在 frontend/public/assets/models/assistant/，SOURCE.md 记录来源、哈希与改编；完整运行库许可随 licenses/@pixiv/ 及锁文件清单保留。没有引入 TalkingHead 或 OpenAvatarChat 服务。说明及实际验收结果见 [数字人与新手导览](../../docs/ui-assistant-onboarding.md)。
