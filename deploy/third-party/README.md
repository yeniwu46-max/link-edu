# 第三方依赖与资源

`frontend-packages.json` 记录 npm 锁文件的版本、来源、完整性值及许可证字段；`licenses/` 保留已安装依赖包附带的许可证或声明原文。后端锁定版本见 `backend/requirements.lock.txt`，安装时须保留各 Python 分发包的 dist-info 许可证元数据。

`browser-models.json` 记录本次随包分发的 MediaPipe 模型及 WASM 文件哈希、官方下载来源。模型权利及使用条件以各自上游发布内容为准，不将第三方模型表述为团队自研权重。

资源库原有公开大纲与院校材料保留其作者、出处及资源入口，临客自编知识卡单独标注。公开可访问不等于放弃版权；对外再分发应遵循原作者许可。本包不授予超出原权利人的授权。

云端 DeepSeek、讯飞、OpenAI Next 等适配器属于调用代码，不包含供应商商业模型权重。具体服务权限和费用随账户与服务合同确定；有效密钥由项目持有人另行提供。

执行 `python scripts/export_dependency_inventory.py` 可在完成 `npm ci` 后重建清单。
