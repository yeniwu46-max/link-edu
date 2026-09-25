"""Query expansion for oral teacher phrasing; optional HyDE via LLM (cost)."""
import re

# 口语/别名 → 检索增强词（可随语料 manifest 扩展）
TERM_EXPANSIONS = {
    '候答': ['候答时间', '等待', '沉默', '思考时间'],
    '导入': ['激趣', '引入', '开场', '情境导入'],
    '提问': ['问题设计', '追问', '理答'],
    '平均分': ['等分', '分数', '几分之一', '整体'],
    '教态': ['站姿', '面向学生', '肢体语言'],
    '互动': ['提问', '讨论', '全班回收'],
    '课标': ['课程标准', '学业质量', '核心素养'],
    '量表': ['评价指标', '评分标准', 'rubric'],
}


def expand_query(text, *, mode='expand'):
    text = re.sub(r'\s+', ' ', (text or '').strip())
    if not text or mode in (None, '', 'off', 'false'):
        return text
    extra = []
    for key, values in TERM_EXPANSIONS.items():
        if key in text:
            extra.extend(values[:2])
    if mode == 'hyde':
        # HyDE 需要 LLM；此处仅做术语扩展，真正 HyDE 在 service 中可选调用
        pass
    if extra:
        return f'{text} {" ".join(dict.fromkeys(extra))}'
    return text


def hyde_passage(llm, question, max_tokens=180):
    """Hypothetical document snippet for embedding the query (uses LLM budget)."""
    system = (
        '你是教学知识库检索助手。根据用户问题，写一段可能出现在课标、量表或教学理论中的短条文（80–150 字）。'
        '只返回 JSON：{"passage":"条文正文"}。若无法推断则 passage 为“暂无对应条文”。'
    )
    try:
        out = llm.complete_json(system, {'question': question}, max_tokens)
        if isinstance(out, dict):
            text = str(out.get('passage') or out.get('text') or '')
        else:
            text = ''
    except Exception:
        text = ''
    text = text.strip()
    return text if text and '暂无' not in text else ''
