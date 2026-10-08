export const TOUR_VERSION='2026-10-1'
export const tourKey=id=>`link_tour:${id}:${TOUR_VERSION}`
export function tourSeen(id,storage=localStorage){try{return Boolean(storage.getItem(tourKey(id)))}catch{return false}}
export function saveTour(id,status,storage=localStorage){try{storage.setItem(tourKey(id),status)}catch{/* Guide remains optional when storage is unavailable. */}}
export function startTour(){window.dispatchEvent(new Event('link:tour-start'))}
export const tourSteps=[
 {path:'/dashboard',target:'[data-tour="start"]',title:'从一次训练开始',text:'工作台可直接进入模拟课堂，也能继续上次训练。导览只介绍功能，不开启任何设备。'},
 {path:'/courses',target:'[data-tour="courses"]',title:'选择要练习的技能',text:'按分类浏览课程。旁边的小书册可以横向拖动、点击切换形态，双击复位；键盘也支持方向键、回车和 Home。'},
 {path:'/classroom',target:'.classroom-prep-trigger, .classroom-start-button, [data-tour="prepare"]',title:'准备与授权',text:'点击“准备开课”查看时长和设备设置。语音、摄像头和本机录像都由你主动授权。'},
 {path:'/classroom',target:'.classroom-stage, [data-tour="stage"]',title:'大屏授课与学生互动',text:'主屏显示授课画面，三个学生在下方。举手后可点击点名，控制栏支持暂停、继续、结束与字幕设置。'},
 {path:'/ai-review',target:'[data-tour="review"]',title:'用证据复盘',text:'选择已结束的课堂，查看各维度的证据和建议；证据不足时系统会说明。'},
 {path:'/growth',target:'[data-tour="growth"]',title:'安排下一次复练',text:'从课堂报告创建复练任务，在这里追踪目标与进步。轨道模型可以直接把玩。'},
 {path:'/resources',target:'[data-tour="resources"]',title:'随时查阅资料',text:'分类筛选资料，拖动资源墙卡片、点击阅读。知识库可检索已授权教学材料，助手教学回答也会引用来源。'},
 {path:'/profile?tab=settings',target:'[data-tour="profile"]',title:'你的偏好与数字人',text:'右上角头像进入个人中心和设置。点击页面边缘的数字人获取帮助或主动开启语音；授课时仅提供文字。这里可以重看导览。'}
]
