import json
from datetime import datetime, timedelta

from werkzeug.security import generate_password_hash

from extensions import db
from models import AiFeedback, Course, Resource, TrainingSession, User
from services.training import build_review_report


def seed_if_empty():
    if User.query.first():
        return

    demo_user = User(
        account='demo',
        password_hash=generate_password_hash('link123'),
        name='林晓',
        role='student',
    )
    db.session.add(demo_user)
    db.session.flush()

    courses = [_course_from_item(item) for item in EXTRA_COURSES]
    db.session.add_all(courses)
    db.session.flush()
    by_title = {course.title: course for course in courses}

    now = datetime.utcnow()
    sessions = [
        TrainingSession(
            user_id=demo_user.id,
            course_id=by_title['导入技能'].id,
            status='in_progress',
            progress_percent=68,
            duration_minutes=32,
            started_at=now - timedelta(days=3),
            last_trained_at=now - timedelta(days=1, hours=3, minutes=24),
        ),
        TrainingSession(
            user_id=demo_user.id,
            course_id=by_title['板书板画技能'].id,
            status='completed',
            progress_percent=100,
            duration_minutes=28,
            started_at=now - timedelta(days=6),
            last_trained_at=now - timedelta(days=5),
        ),
        TrainingSession(
            user_id=demo_user.id,
            course_id=by_title['组织教学技能'].id,
            status='completed',
            progress_percent=100,
            duration_minutes=26,
            started_at=now - timedelta(days=2),
            last_trained_at=now - timedelta(days=2, hours=5),
        ),
    ]
    db.session.add_all(sessions)
    db.session.flush()

    def make_feedback(session, overall, clarity, pace, interaction, suggestion, created_at, scene='导入', minutes=8):
        title = session.course.title if session.course else None
        report = build_review_report(minutes, scene, 'fragment', title)
        report['overall_score'] = overall
        report['clarity_score'] = clarity
        report['pace_score'] = pace
        report['interaction_score'] = interaction
        report['suggestion'] = suggestion
        report['next_action'] = suggestion
        score_map = {
            'clarity': clarity,
            'pace': pace,
            'interaction': interaction,
        }
        for item in report['dimensions']:
            if item['key'] in score_map:
                item['score'] = score_map[item['key']]
        return AiFeedback(
            user_id=demo_user.id,
            session_id=session.id,
            overall_score=overall,
            clarity_score=clarity,
            pace_score=pace,
            interaction_score=interaction,
            suggestion=suggestion,
            report_json=json.dumps(report, ensure_ascii=False),
            created_at=created_at,
        )

    feedbacks = [
        make_feedback(sessions[0], 72, 74, 70, 71, '注意语速控制，适当增加停顿。', now - timedelta(days=6), '导入', 6),
        make_feedback(sessions[1], 76, 78, 74, 75, '提问后给学生更多思考时间。', now - timedelta(days=5), '提问', 8),
        make_feedback(sessions[2], 79, 81, 77, 78, '互动环节可再增加一次追问。', now - timedelta(days=4), '互动', 8),
        make_feedback(sessions[0], 81, 83, 79, 80, '板书结构清晰，继续保持。', now - timedelta(days=3), '板书', 8),
        make_feedback(sessions[0], 80, 82, 78, 79, '可减少连续讲述，增加等待时间。', now - timedelta(days=2), '导入', 7),
        make_feedback(sessions[0], 84, 86, 82, 83, '课堂节奏更稳定，互动更自然。', now - timedelta(days=1), '完整', 10),
        make_feedback(sessions[0], 86, 90, 82, 85, '减少连续讲述，增加等待时间', now - timedelta(hours=8), '提问', 8),
    ]
    db.session.add_all(feedbacks)

    resources = [
        Resource(
            title='分数微格教案样例',
            category='教案',
            description='8–10 分钟样例；训练用，非正式国标',
            file_url='/library/original/fraction-micro-lesson.md',
        ),
        Resource(
            title='开课设备与授权检查',
            category='素材',
            description='训前设备与授权清单',
            file_url='/library/original/device-preflight-checklist.md',
        ),
        Resource(
            title='六维评课量规说明',
            category='报告',
            description='六维与证据原则',
            file_url='/library/original/review-six-dimensions.md',
        ),
        Resource(
            title='公开教学资料索引',
            category='档案',
            description='公开链接索引，不转载全文',
            file_url='/library/original/public-sources-index.md',
        ),
    ]
    db.session.add_all(resources)
    db.session.commit()
    ensure_demo_catalog()


OUTLINE_SOURCE = '《教师职业技能训练大纲（试行）》改编'
OUTLINE_URL = 'https://jnzx.zznu.edu.cn/info/1051/3771.htm'
NTCE_URL = 'https://ntce.neea.edu.cn/html1/category/1511/692-1.htm'
MOE_PRACTICE_URL = 'http://www.moe.gov.cn/srcsite/A10/s7011/201604/t20160407_237042.html'

STUB_TITLES = ('课堂导入与提问设计', '板书设计与课堂节奏', '互动反馈与课堂管理')
STUB_REMAP = {
    '课堂导入与提问设计': '导入技能',
    '板书设计与课堂节奏': '板书板画技能',
    '互动反馈与课堂管理': '组织教学技能',
}


def _skill_outline(task_lines, checks):
    tasks = '\n'.join(f'{index}. {line}' for index, line in enumerate(task_lines, 1))
    points = '\n'.join(f'- {line}' for line in checks)
    return f'8 分钟上台任务\n{tasks}\n\n自评要点（对照六维评课）\n{points}'


EXTRA_COURSES = [
    {
        'title': '导入技能',
        'aliases': ['导入技能：引起注意与建立联系'],
        'category': '微格教学 · 专项',
        'stage': '专项01 · 导入',
        'source': OUTLINE_SOURCE,
        'source_url': OUTLINE_URL,
        'lesson_count': 6,
        'description': '新课开始时把学生带进课题。常见做法有直接点题、温故、实例、教具、故事、设问、实验。程序是先集中注意，再激起兴趣，然后亮出目标，自然进入新知。',
        'outline': _skill_outline(
            [
                '用生活问题或旧知，在 30 秒内抓住注意',
                '用一句话说清本节要解决什么',
                '检查一两处前备知识',
                '过渡句接到新课，不要停在热闹上',
            ],
            ['节奏：开场是否拖沓', '结构：目标是否说清', '互动：是否把问题抛给学生'],
        ),
    },
    {
        'title': '板书板画技能',
        'aliases': ['板书与强化技能'],
        'category': '微格教学 · 专项',
        'stage': '专项02 · 板书',
        'source': OUTLINE_SOURCE,
        'source_url': OUTLINE_URL,
        'lesson_count': 6,
        'description': '用精炼文字和图表把教学信息留在黑板上。可用提纲、语词、表格、线索或图示。要求写得规范、布局清楚，板画简单，能帮助学生看见结构。',
        'outline': _skill_outline(
            [
                '课前划好左结构、右例证两个区',
                '边讲边写关键词，不整板抄写',
                '用一种强调方式标出重点',
                '小结时回指板书，让学生看见线索',
            ],
            ['结构：分区是否清楚', '表达：关键词是否准确', '教态：写字时是否长时间背对学生'],
        ),
    },
    {
        'title': '演示技能',
        'aliases': [],
        'category': '微格教学 · 专项',
        'stage': '专项03 · 演示',
        'source': OUTLINE_SOURCE,
        'source_url': OUTLINE_URL,
        'lesson_count': 5,
        'description': '把实物、标本、模型、挂图或媒体展示出来，帮助学生看见过程。程序是先做心理准备，再出示对象，说明要点，配合讲解，最后总结并核查是否看懂。',
        'outline': _skill_outline(
            [
                '演示前先提出观察问题和看什么',
                '出示材料，给学生足够感知时间',
                '边指边讲，不要被材料抢走讲解',
                '收回材料后用一句话核对观察结果',
            ],
            ['结构：观察任务是否明确', '表达：说明是否跟演示同步', '互动：是否核查学生看懂了'],
        ),
    },
    {
        'title': '讲解技能',
        'aliases': ['讲解与变化技能'],
        'category': '微格教学 · 专项',
        'stage': '专项04 · 讲解',
        'source': OUTLINE_SOURCE,
        'source_url': OUTLINE_URL,
        'lesson_count': 8,
        'description': '用语言和媒体帮学生形成概念、原理或事实。事实性内容走「叙述—要点—核查」；抽象内容用正例、反例再概括。重点要突出，并及时巩固。',
        'outline': _skill_outline(
            [
                '先给出定义或事实，不超过两句',
                '举一个正例和一个反例',
                '请学生用自己的话复述要点',
                '用一道小应用题检查是否听懂',
            ],
            ['表达：概念是否一次能听懂', '结构：例子是否服务要点', '提问：核查有没有落到学生'],
        ),
    },
    {
        'title': '提问技能',
        'aliases': ['提问技能：候答、追问与叫答'],
        'category': '微格教学 · 专项',
        'stage': '专项05 · 提问',
        'source': OUTLINE_SOURCE,
        'source_url': OUTLINE_URL,
        'lesson_count': 8,
        'description': '用问题检查学习、推动思维。问题可从回忆、理解、运用，到分析、综合、评价。流程是引入、陈述、介入、评价。问题要简明，并给学生思考和反馈。',
        'outline': _skill_outline(
            [
                '设计一个核心问题，避免连珠炮',
                '提问后候答约 8 秒，再请人回答',
                '根据回答做一次追问或澄清',
                '请第二位同学复述或评价',
            ],
            ['提问：层次是否从确认走到思考', '节奏：候答有没有被自己填掉', '互动：评价是否具体'],
        ),
    },
    {
        'title': '反馈和强化技能',
        'aliases': [],
        'category': '微格教学 · 专项',
        'stage': '专项06 · 强化',
        'source': OUTLINE_SOURCE,
        'source_url': OUTLINE_URL,
        'lesson_count': 5,
        'description': '从观察、提问或练习里收回学生反应，再用语言、动作、符号或活动把正确行为稳住。反馈要及时，强化以表扬进步为主，分量适中。',
        'outline': _skill_outline(
            [
                '讲完一个点后停下来看全班反应',
                '对正确回答给出具体强化，不只说「很好」',
                '对偏差回答先指出对的部分，再引导',
                '用一次全班活动把要点再钉住',
            ],
            ['互动：反馈是否跟得上学生', '表达：强化语是否具体', '教态：是否看见后排反应'],
        ),
    },
    {
        'title': '结束技能',
        'aliases': ['结束技能：总结、作业与激励'],
        'category': '微格教学 · 专项',
        'stage': '专项07 · 结束',
        'source': OUTLINE_SOURCE,
        'source_url': OUTLINE_URL,
        'lesson_count': 5,
        'description': '一个内容告一段落时，把知识收成系统。可用归纳、比较、活动、练习或延伸。程序是简单回忆、点出要点，再巩固或拓出去。',
        'outline': _skill_outline(
            [
                '回扣开场时的学习目标',
                '请学生用一句话总结',
                '布置一道当堂能完成的小作业',
                '用一句激励或预告收口，不要突然停掉',
            ],
            ['结构：收口是否回到目标', '节奏：结束是否仓促', '互动：总结是否出自学生'],
        ),
    },
    {
        'title': '组织教学技能',
        'aliases': [],
        'category': '微格教学 · 专项',
        'stage': '专项08 · 组织',
        'source': OUTLINE_SOURCE,
        'source_url': OUTLINE_URL,
        'lesson_count': 6,
        'description': '在课堂上维持注意、安排学习、处理纪律，形成能继续上课的秩序。组织可以是管理性、指导性或诱导性的，要尊重学生并灵活应变。',
        'outline': _skill_outline(
            [
                '给出一次清晰的活动指令（做什么、多久、如何汇报）',
                '小组活动开始后巡视，不站在讲台发呆',
                '用 10 秒全班回收，避免讨论散掉',
                '对一次走神或插话做低声处理，再回到课题',
            ],
            ['互动：指令是否可执行', '节奏：回收是否及时', '教态：管理时是否仍面向全班'],
        ),
    },
    {
        'title': '变化技能',
        'aliases': [],
        'category': '微格教学 · 专项',
        'stage': '专项09 · 变化',
        'source': OUTLINE_SOURCE,
        'source_url': OUTLINE_URL,
        'lesson_count': 5,
        'description': '用动作、表情、眼神和声调辅助口语，帮助学生保持注意。变化要服务于内容，幅度适中，不能变成表演。',
        'outline': _skill_outline(
            [
                '重点句放慢并加重音，次要句收轻',
                '讲解时有一次有意识的站位移动',
                '提问时把视线从前排转到后排',
                '转折处停半拍，再用手势提示新段落',
            ],
            ['教态：变化是否为内容服务', '表达：声调是否有层次', '节奏：停顿是否帮人听清'],
        ),
    },
    {
        'title': '综合模拟授课（10 分钟）',
        'aliases': [],
        'category': '微格教学 · 综合',
        'stage': '综合10 · 模拟授课',
        'source': '大纲综合训练 · 教师〔2016〕2号',
        'source_url': MOE_PRACTICE_URL,
        'lesson_count': 10,
        'description': '大纲要求单项过关后再做综合训练。把导入、提问、讲解、板书、互动和结束串成一节 10 分钟微格课，对应见习实习前的模拟教学。',
        'outline': (
            '10 分钟上台任务\n'
            '1. 导入 2 分钟：注意、目标、进入课题\n'
            '2. 提问与讲解 4 分钟：一个核心问题 + 正反例\n'
            '3. 板书与互动 3 分钟：关键词上板，回收一次回答\n'
            '4. 结束 1 分钟：回扣目标并布置作业\n'
            '\n'
            '自评要点（对照六维评课）\n'
            '- 结构：六个环节是否都出现\n'
            '- 节奏：10 分钟是否前松后紧\n'
            '- 提问 / 互动 / 表达 / 教态：是否还记得专项要求'
        ),
    },
    {
        'title': '教资面试模拟授课（10 分钟）',
        'aliases': [],
        'category': '微格教学 · 综合',
        'stage': '综合11 · 教资试讲',
        'source': '中小学教师资格考试面试大纲（试行）',
        'source_url': NTCE_URL,
        'lesson_count': 8,
        'description': '按教师资格面试的无生试讲来练：配合板书、设计提问、带过程性评价。演示环境不使用真题原文，自选一小节课标教材内容即可。',
        'outline': (
            '10 分钟上台任务\n'
            '1. 导入后点明本节目标\n'
            '2. 新授中至少一次面向「学生」的提问\n'
            '3. 对学生可能的对/错回答给出过程性评价\n'
            '4. 板书随讲展开，收束时回指\n'
            '\n'
            '自评要点（对照面试考查）\n'
            '- 结构：是否像上课而不是说课\n'
            '- 提问：问题是否进教学过程\n'
            '- 表达：指令能否被「学生」执行'
        ),
    },
]

def _course_fields(item):
    return {
        'title': item['title'],
        'category': item['category'],
        'description': item['description'],
        'lesson_count': item['lesson_count'],
        'stage': item.get('stage'),
        'outline': item.get('outline'),
        'source': item.get('source'),
        'source_url': item.get('source_url'),
    }


def _course_from_item(item):
    return Course(**_course_fields(item))


def _apply_course_item(course, item):
    changed = False
    for key, value in _course_fields(item).items():
        if getattr(course, key) != value:
            setattr(course, key, value)
            changed = True
    if not course.is_active:
        course.is_active = True
        changed = True
    return changed


def _match_course(item, courses):
    names = {item['title'], *item.get('aliases', [])}
    for course in courses:
        if course.title in names:
            return course
    return None


EXTRA_RESOURCES = [
    {
        'title': '分数微格教案样例',
        'category': '教案',
        'description': '8–10 分钟《分数的初步认识》样例；自编训练用，非正式国标',
        'file_url': '/library/original/fraction-micro-lesson.md',
    },
    {
        'title': '分数核心知识卡',
        'category': '教案',
        'description': '平均分、单位分数、同一整体；训练摘要，非正式国标',
        'file_url': '/library/original/fraction-knowledge-card.md',
    },
    {
        'title': '10 分钟时间分配表',
        'category': '教案',
        'description': '导入—新授—追问—小结分钟建议',
        'file_url': '/library/original/time-allocation-10min.md',
    },
    {
        'title': '分数典型误解对照表',
        'category': '素材',
        'description': '纠错与追问对照；训练用，非正式国标',
        'file_url': '/library/original/fraction-misconceptions.md',
    },
    {
        'title': '开课设备与授权检查',
        'category': '素材',
        'description': '麦克风、摄像头、本机录像等训前检查',
        'file_url': '/library/original/device-preflight-checklist.md',
    },
    {
        'title': '板书自检 8 条',
        'category': '素材',
        'description': '课题、平均分、单位分数与分区自检',
        'file_url': '/library/original/board-self-check.md',
    },
    {
        'title': '公开教学资料索引',
        'category': '素材',
        'description': '大纲目录与分数策略文链接；不转载全文',
        'file_url': '/library/original/public-sources-index.md',
    },
    {
        'title': '六维评课量规说明',
        'category': '报告',
        'description': '六维看什么、何时暂不评分；非教资官方量表',
        'file_url': '/library/original/review-six-dimensions.md',
    },
    {
        'title': '证据门槛一页纸',
        'category': '报告',
        'description': '有效时长、转写与完整播放门槛摘要',
        'file_url': '/library/original/review-evidence-threshold.md',
    },
    {
        'title': '成长档案填写说明',
        'category': '档案',
        'description': '近 30 天回放、热力图与训练日志怎么记（站内成长页）',
        'file_url': '/growth',
    },
    {
        'title': '教师职业技能训练大纲导读',
        'category': '档案',
        'description': '九项技能先分项再综合；公开大纲改编，不替代原文件',
        'file_url': 'https://jnzx.zznu.edu.cn/info/1051/3771.htm',
    },
]


def ensure_demo_catalog():
    added = False
    courses = Course.query.all()
    for item in EXTRA_COURSES:
        course = _match_course(item, courses)
        if course is None:
            course = _course_from_item(item)
            db.session.add(course)
            courses.append(course)
            added = True
        elif _apply_course_item(course, item):
            added = True

    db.session.flush()
    by_title = {course.title: course for course in Course.query.all()}

    for stub in Course.query.filter(Course.title.in_(STUB_TITLES)).all():
        target = by_title.get(STUB_REMAP.get(stub.title, ''))
        if target:
            moved = TrainingSession.query.filter_by(course_id=stub.id).update({'course_id': target.id})
            if moved:
                added = True
        if stub.is_active:
            stub.is_active = False
            added = True

    resources_by_title = {resource.title: resource for resource in Resource.query.all()}
    for item in EXTRA_RESOURCES:
        resource = resources_by_title.get(item['title'])
        if resource is None:
            db.session.add(Resource(
                title=item['title'],
                category=item['category'],
                description=item['description'],
                file_url=item.get('file_url'),
            ))
            added = True
            continue
        if resource.category != item['category']:
            resource.category = item['category']
            added = True
        if resource.description != item['description']:
            resource.description = item['description']
            added = True
        if item.get('file_url') and resource.file_url != item['file_url']:
            resource.file_url = item['file_url']
            added = True

    demo = User.query.filter_by(account='demo').first()
    if demo and not demo.school:
        demo.school = '师范学院（演示）'
        demo.major = '小学教育'
        demo.bio = '关注课堂导入、提问候答与板书结构。'
        added = True

    if added:
        db.session.commit()
