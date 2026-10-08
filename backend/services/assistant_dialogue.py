"""Cancellable assistant JSON stream using the existing provider and reservation ledgers."""
import json
import os
import time
import httpx
from flask import current_app
from services.classroom_providers import key, model, llm_provider, ProviderError, provider_http_error, deepseek_credential
from services.classroom_budget import price, reserve, settle
from services.classroom_stream import StreamCancelled, sse_events, unique_object, partial_string


class AssistantDraft:
    def __init__(self):
        self.buffer = ''
    def feed(self, delta):
        self.buffer += delta
        if len(self.buffer) > 16000:
            raise ValueError('answer too long')
        match = __import__('re').match(r'\s*\{\s*"text"\s*:\s*(.*)', self.buffer, __import__('re').S)
        return partial_string(match.group(1)) if match else ''

def validate_answer(output):
    if not isinstance(output, dict) or not isinstance(output.get('text'), str) or not 0 < len(output['text']) <= 2400:
        raise ValueError('invalid answer')
    ids = output.get('source_ids', [])
    if not isinstance(ids, list) or len(ids) > 8 or not all(isinstance(i, str) for i in ids):
        raise ValueError('invalid citations')
    return {'text': output['text'], 'source_ids': ids}

def chat_stream(system, payload, control, on_draft, max_tokens=800):
    session_id = None
    control.check()
    is_next = llm_provider() == 'openai_next'
    content = json.dumps(payload, ensure_ascii=False)
    selected = model('dialogue')
    if is_next:
        from services import classroom_credits as ledger
        account = 'test' if current_app.config.get('CLASSROOM_API_PROFILE') == 'test' else 'dialogue'
        token = key(f'OPENAI_NEXT_{account.upper()}_API_KEY')
        endpoint = os.getenv('OPENAI_NEXT_BASE_URL', 'https://api.openai-next.com/v1').rstrip('/')
        if endpoint != 'https://api.openai-next.com/v1' or selected not in ('deepseek-v4-flash', 'deepseek-v4-flash-vision-exp'):
            raise ProviderError('请检查对话端点、模型及单价配置')
        ip, op = price('OPENAI_NEXT_DIALOGUE_INPUT_USD_PER_MILLION'), price('OPENAI_NEXT_DIALOGUE_OUTPUT_USD_PER_MILLION')
    else:
        credential = deepseek_credential()
        token = key(credential)
        endpoint = os.getenv('DEEPSEEK_BASE_URL', 'https://api.deepseek.com').rstrip('/')
        if not endpoint.startswith('https://'):
            raise ProviderError('对话端点必须使用 HTTPS')
        ip, op = price('AI_LLM_INPUT_CNY_PER_MILLION'), price('AI_LLM_OUTPUT_CNY_PER_MILLION')
    upper = ((len((system + content).encode('utf-8')) + 1024) * ip + max_tokens * op) / 1e6
    usage_id = ledger.reserve(account, 'dialogue', selected, upper, session_id) if is_next else reserve('dialogue', upper, session_id)
    parser, settled, done, finished = AssistantDraft(), False, False, False
    started = time.monotonic()
    try:
        control.check()
        with httpx.stream('POST', endpoint + '/chat/completions',
                headers={'Authorization': f'Bearer {token}'}, timeout=45,
                json={'model': selected, 'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': content}],
                      'thinking': {'type': 'disabled'}, 'max_tokens': max_tokens,
                      'response_format': {'type': 'json_object'}, 'stream': True,
                      'stream_options': {'include_usage': True}}) as response:
            control.bind(response)
            if response.status_code != 200:
                raise provider_http_error(
                    response.status_code, 'OpenAI Next' if is_next else 'DeepSeek',
                    f'OPENAI_NEXT_{account.upper()}_API_KEY' if is_next else credential)
            for raw in sse_events(response.iter_lines()):
                control.check()
                if time.monotonic() - started > 45:
                    raise ProviderError('助手回复生成超时，请重试')
                if raw == '[DONE]':
                    done = True
                    break
                item = json.loads(raw)
                if item.get('error'):
                    raise ProviderError('流式回复中断，请检查连接后重试')
                usage = item.get('usage') or {}
                counts = [usage.get('prompt_tokens'), usage.get('completion_tokens')]
                if not settled and all(type(n) is int and n >= 0 for n in counts):
                    cost = (counts[0] * ip + counts[1] * op) / 1e6
                    safe = {'prompt_tokens': counts[0], 'completion_tokens': counts[1]}
                    if is_next:
                        ledger.settle(usage_id, cost, {**safe, 'billing': 'estimated_peak_cache_miss', 'input_usd_per_million': ip, 'output_usd_per_million': op})
                    else:
                        settle(usage_id, cost, safe)
                    settled = True
                for choice in item.get('choices', []):
                    if choice.get('index', 0) != 0:
                        continue
                    reason = choice.get('finish_reason')
                    if reason and reason != 'stop':
                        raise ProviderError('助手回复未完整生成，请重试')
                    finished |= reason == 'stop'
                    delta = choice.get('delta', {}).get('content') or ''
                    if not isinstance(delta, str):
                        raise ValueError('invalid delta')
                    if delta:
                        draft = parser.feed(delta)
                        if draft:
                            on_draft(draft)
            control.check()
            if not done or not finished:
                raise ProviderError('流式回复连接中断，未播放不完整回复')
        return validate_answer(json.loads(parser.buffer, object_pairs_hook=unique_object))
    except (StreamCancelled, ProviderError):
        raise
    except Exception as exc:
        control.check()
        if isinstance(exc, httpx.HTTPError):
            raise ProviderError('流式回复网络失败或超时，请重试') from None
        raise ProviderError('流式回复格式无效或服务不支持，请检查后重试') from None
