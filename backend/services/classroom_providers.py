"""Provider adapters. No credentials or provider response bodies are exposed to clients."""
import base64
import json
import os
import time
import uuid
from urllib.parse import urlencode
import httpx
import websocket
from services.classroom_budget import reserve, settle, price


class ProviderError(ValueError):
    pass


def key(name):
    value = os.getenv(name, '').strip()
    if not value:
        raise ProviderError(f'尚未配置 {name}')
    return value


def model(service):
    return os.getenv({'dialogue': 'DEEPSEEK_CHAT_MODEL', 'vision': 'DEEPSEEK_VISION_MODEL',
                      'asr': 'DASHSCOPE_ASR_MODEL', 'tts': 'DASHSCOPE_TTS_MODEL'}[service],
                     {'dialogue': 'deepseek-v4-flash', 'vision': 'deepseek-v4-flash-vision-exp',
                      'asr': 'qwen3-asr-flash-realtime', 'tts': 'qwen3-tts-flash-realtime'}[service])


def chat(system, payload, session_id=None, image=None, max_tokens=600):
    token = key('DEEPSEEK_API_KEY')
    content = json.dumps(payload, ensure_ascii=False)
    input_price = price('AI_LLM_INPUT_CNY_PER_MILLION')
    output_price = price('AI_LLM_OUTPUT_CNY_PER_MILLION')
    # UTF-8 byte count conservatively bounds text tokens. Image allowance is separate.
    upper_input = len((system + content).encode('utf-8')) + (4096 if image else 0) + 1024
    usage_id = reserve('vision' if image else 'dialogue',
                       (upper_input * input_price + max_tokens * output_price) / 1e6, session_id)
    if image:
        content = [{'type': 'text', 'text': content},
                   {'type': 'image_url', 'image_url': {'url': image}}]
    try:
        response = httpx.post(os.getenv('DEEPSEEK_BASE_URL', 'https://api.deepseek.com').rstrip('/') + '/chat/completions',
            headers={'Authorization': f'Bearer {token}'}, timeout=45,
            json={'model': model('vision' if image else 'dialogue'),
                  'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': content}],
                  'thinking': {'type': 'disabled'}, 'max_tokens': max_tokens,
                  'response_format': {'type': 'json_object'}})
        if response.status_code != 200:
            raise ProviderError(f'DeepSeek 请求失败（HTTP {response.status_code}），请检查模型权限、余额或稍后重试')
        result = response.json()
        usage = result.get('usage', {})
        if 'prompt_tokens' in usage and 'completion_tokens' in usage:
            settle(usage_id, (usage['prompt_tokens'] * input_price + usage['completion_tokens'] * output_price) / 1e6, usage)
        output = json.loads(result['choices'][0]['message']['content'])
        if not isinstance(output, dict):
            raise ValueError()
        return output
    except ProviderError:
        raise
    except (httpx.HTTPError, ValueError, KeyError, IndexError):
        raise ProviderError('DeepSeek 超时或返回格式无效，请重试') from None


class SpeechSocket:
    def __init__(self, service):
        token = key('DASHSCOPE_API_KEY')
        url = os.getenv('DASHSCOPE_WS_URL', 'wss://dashscope.aliyuncs.com/api-ws/v1/realtime')
        if not url.startswith('wss://'):
            raise ProviderError('百炼端点必须使用 wss://')
        try:
            self.ws = websocket.create_connection(url + '?' + urlencode({'model': model(service)}),
                header={'Authorization': f'Bearer {token}'}, timeout=12, enable_multithread=True)
            self.wait_for('session.created')
        except Exception:
            raise ProviderError(f'百炼 {service} 连接失败，请检查同地域密钥、端点、权限和网络') from None

    def send(self, kind, **data):
        self.ws.send(json.dumps({'type': kind, 'event_id': uuid.uuid4().hex, **data}))

    def receive(self):
        value = self.ws.recv()
        if not value:
            raise ProviderError('语音服务连接已关闭')
        item = json.loads(value)
        if item.get('type') == 'error':
            raise ProviderError('语音服务返回错误，请检查模型权限、音频配置或余额')
        return item

    def wait_for(self, kind):
        until = time.monotonic() + 12
        while time.monotonic() < until:
            event = self.receive()
            if event.get('type') == kind:
                return event
        raise ProviderError('语音会话初始化超时')

    def close(self):
        try:
            self.ws.close()
        except Exception:
            pass


class ASR(SpeechSocket):
    def __init__(self, session_id):
        key('DASHSCOPE_API_KEY')
        self.rate = price('AI_ASR_CNY_PER_MINUTE')
        self.usage_id = reserve('asr', self.rate * 11, session_id)
        self.seconds = 0
        super().__init__('asr')
        self.send('session.update', session={'input_audio_format': 'pcm', 'sample_rate': 16000,
            'input_audio_transcription': {'language': 'zh'},
            'turn_detection': {'type': 'server_vad', 'threshold': 0.2, 'silence_duration_ms': 600}})
        self.wait_for('session.updated')
        self.ws.settimeout(1)

    def audio(self, encoded):
        raw = base64.b64decode(encoded, validate=True)
        if not 0 < len(raw) <= 32000 or len(raw) % 2:
            raise ProviderError('音频必须为 16kHz 单声道 PCM16，每块最多一秒')
        if self.seconds + len(raw) / 32000 > 660:
            raise ProviderError('语音会话超过最大时长')
        self.seconds += len(raw) / 32000
        self.send('input_audio_buffer.append', audio=encoded)

    def settle(self):
        settle(self.usage_id, self.rate * max(1, self.seconds) / 60,
               {'audio_seconds': self.seconds, 'billing': 'estimated_from_pcm_duration'})


def speak(text, session_id, voice, cancelled, on_audio):
    key('DASHSCOPE_API_KEY')
    rate = price('AI_TTS_CNY_PER_10K_CHARS')
    usage_id = reserve('tts', max(1, len(text.encode('utf-8'))) / 10000 * rate, session_id)
    sock = SpeechSocket('tts')
    try:
        sock.send('session.update', session={'mode': 'commit', 'voice': voice,
                  'response_format': 'pcm', 'sample_rate': 24000})
        sock.wait_for('session.updated')
        sock.ws.settimeout(1)
        sock.send('input_text_buffer.append', text=text)
        sock.send('input_text_buffer.commit')
        deadline = time.monotonic() + 25
        while time.monotonic() < deadline and not cancelled():
            try:
                item = sock.receive()
            except websocket.WebSocketTimeoutException:
                continue
            if item['type'] == 'response.audio.delta':
                if not cancelled():
                    on_audio(item['delta'])
            if item['type'] in ('response.done', 'response.audio.done'):
                sock.send('session.finish')
                settle(usage_id, len(text.encode('utf-8')) / 10000 * rate,
                       {'characters': len(text), 'billing': 'conservative_utf8_estimate'})
                return
        if not cancelled():
            raise ProviderError('语音合成超时')
    finally:
        sock.close()
