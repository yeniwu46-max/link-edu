# 原版视觉恢复与 3D 交互集成

日期：2026-10-08。基线：c6480da。

## 恢复范围

按此前 UI 改动涉及的文件恢复原布局，移除 redesign.css 及其引用。保留深色背景、紫橙渐变、玻璃面板、胶囊导航、主卡片比例与默认可拖拽资源墙。后端、知识库与其他文档的工作区改动不属于本次回退范围。

## 引入来源与许可

| 来源 | 本地用途与改编 | 版本与许可 |
|---|---|---|
| [Khronos glTF Sample Assets / Cesium Man](https://github.com/KhronosGroup/glTF-Sample-Assets/tree/main/Models/CesiumMan) | 引入 GLB 的人物几何、骨骼及原有动画；替换带品牌的材质，适配暗金属、紫橙灯光、低透明度线框、镜头及播放速度 | 固定提交 edc7c9e67c639d230715049ee31f9a96a6babbbe；作者 Cesium；CC BY 4.0；资产旁保留原 LICENSE.md 和 credits.json |
| [Three.js](https://github.com/mrdoob/three.js) | 沿用已安装依赖，GLTFLoader、单 WebGL 画布、AnimationMixer、透视镜头、双色灯光与静态投影 | 已安装 0.186.0；锁文件为准；MIT；未新增安装 |
| [Vue Bits](https://github.com/DavidHDev/vue-bits) | 沿用并改编 ClickSpark、Magnet；借鉴 TiltedCard 的指针映射与透视分层思路，转换为 Vue JavaScript、插槽及普通 CSS | 对照提交 07c0f76d5567db022c2e3185dd97a2311e056c0c；MIT + Commons Clause；完整许可保留于 deploy/third-party/licenses/vue-bits/LICENSE.md |
| [Motion for Vue](https://github.com/motiondivision/motion-vue) | 沿用 motion-v，处理卡片弹簧回弹、分组进入及评分/计时组件的连续反馈 | 已安装 motion-v 2.4.0；锁文件为准；MIT；未新增安装 |

CesiumMan.glb 大小 438,044 字节；SHA-256：B7001EAEEA8254BD44773BCD247E78696D94169388FBB2A1800FC69434E777D9。人物资产并非团队自建；模型署名入口保留在主卡片右上角。原品牌贴图不参与显示。

Vue Bits 的 Commons Clause 对销售该软件或其主要价值来自该软件的产品有额外条件，完整条款随项目保留。此次适配作为应用内交互组件使用，未将其打包成独立组件商品。

## 核心改编

- HeroAvatar3D.vue 接收模型、封面和失败回退媒体地址。首屏先显示原封面，主卡片可见且浏览器空闲时再动态导入 3D 引擎并请求本地模型。
- heroAvatarScene.js 保留现成人物骨骼和动画，替换材质及品牌贴图；模型归一化，增加紫橙轮廓光与局部线框表现。原动画减速至 0.4 倍，镜头和光源小幅跟随指针。
- ambientUi.js 在原卡片上添加透视、光影、一次性可视区进入动画。普通卡片最多 4°，主卡片最多 6°；悬停抬升 3px。资源拖拽继续作用于外层，内层承担透视，拖动时关闭倾斜。
- Magnet 限制按钮偏移在 4px 内；ClickSpark 仅处理操作控件点击，最多 96 个粒子，结束即停止刷新。触屏不启用磁吸及指针倾斜。
- 页面转场为 260ms 进入、180ms 离开。课堂路由继续使用 route.path 作为组件键，其他页面使用 route.fullPath，避免课堂会话参数变化重建录音组件。
- 课堂动态背景继续播放。装饰光效作用于边框和控制区域，摄像头内容、字幕及计时布局沿用原版。
- 成长档案延迟到图表区域首次可见才挂载图表。成长档案及工作台统计图遵循减少动态效果设置，初次绘制与数据更新动画分别为 450ms 和 250ms。AI 评课分数环和维度条随面板进入可视区绘制，评分变化时通过局部键更新重播动画，不重建课堂或报告业务组件。

## 加载与生命周期

- motionPreferences.js 共享并引用计数管理减少动态效果、页面可见性和精细指针设置，最后一个订阅卸载后移除监听器。
- 桌面最高 60fps、像素比 1.5；触屏最高 30fps、像素比 1。持续低帧率下降至 30fps；持续恢复后返回正常质量。
- 背景视频使用本地 login-bg-lite.mp4：1278×720、24fps、H.264、无音轨、faststart；3,135,214 字节，比原 31,626,234 字节减少约 90.1%。轻量文件失败时回退原视频。
- AmbientVideo、人物画布按可见区与页面可见性暂停。系统减少动态效果时视频暂停、人物静态，关闭自动运动、指针视差及火花。
- 指针更新合并到动画帧；Aurora 以低分辨率 30fps 绘制，隐藏即暂停。卸载取消 RAF/延迟加载，终止模型请求，释放纹理、材质、几何、骨骼、渲染器、观察器和监听器。
- 模型错误、WebGL 创建失败或上下文丢失均回退原人物媒体，不阻塞训练入口。

## 检查方式

在 frontend 目录运行 npm test 和 npm run build。新 motionEffects.test.mjs 覆盖共享偏好生命周期、动态设置变化、指针边界及质量策略；原有课堂和资源交互回归用例继续执行。

浏览器夹具入口：http://127.0.0.1:5188/tests/effects-browser.html。提供减少动态效果、页面隐藏、模型失败、WebGL 不可用/上下文丢失、人物重复挂载及 10 秒合成录制检查。仅使用 canvas.captureStream 和 MediaRecorder，不访问真实摄像头、麦克风或后端接口；该夹具不是生产构建入口。

结果及未确认项见 [验收记录](ui-effects-acceptance.md)。
