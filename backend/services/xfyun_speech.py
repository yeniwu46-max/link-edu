"""XFYun streaming TTS and per-segment ASR accounting (never DashScope prices)."""
import base64
import json
import os
import time
import websocket
from services.classroom_budget import price, reserve, settle
from services.classroom_providers import ProviderError, key
from services import xfyun_wire as wire


def rate(service):
    if os.getenv('XFYUN_PRICING_CONFIRMED', '').lower() != 'true':
        raise ProviderError('请核对讯飞按次单价并配置 XFYUN_PRICING_CONFIRMED=true；未沿用百炼价格')
    return price(f'XFYUN_{service.upper()}_CNY_PER_CALL')


def book(service, sid):
    amount = rate(service)
    return reserve('xfyun_' + service, amount, sid), amount


def charge(usage_id, amount, service, **units):
    settle(usage_id, amount, {'provider': 'xfyun', 'model': 'slm' if service == 'asr' else 'online_tts',
                            'calls': 1, 'billing': 'configured_per_call_estimate', **units})


def voice_for(voice):
    student = {'Ethan': 'MING', 'Cherry': 'YU', 'Serena': 'LIN'}.get(voice)
    override = os.getenv('XFYUN_TTS_VOICE_' + student, '').strip() if student else ''
    return override or key('XFYUN_TTS_VOICE')


def speak(text, session_id, voice, cancelled, on_audio):
    for name in ('XFYUN_APP_ID', 'XFYUN_API_KEY', 'XFYUN_API_SECRET'):
        key(name)
    actual_voice = voice_for(voice)
    raw = text.encode('utf-8')
    if not 0 < len(raw) < 8000:
        raise ProviderError('讯飞合成文本长度无效')
    if cancelled():
        return
    usage_id, amount = book('tts', session_id)
    sock = None
    try:
        sock = wire.connect(wire.TTS_URL)
        sock.settimeout(0.5)
        if cancelled():
            settle(usage_id, 0, {'provider':'xfyun', 'calls':0, 'billing':'cancelled_before_send'})
            return
        sock.send(json.dumps({'common': {'app_id': key('XFYUN_APP_ID')},
            'business': {'aue': 'raw', 'auf': 'audio/L16;rate=16000', 'vcn': actual_voice, 'tte': 'UTF8'},
            'data': {'status': 2, 'text': base64.b64encode(raw).decode()}}))
        until, total = time.monotonic() + 25, 0
        while time.monotonic() < until and not cancelled():
            try:
                item = wire.receive(sock, '合成')
            except websocket.WebSocketTimeoutException:
                continue
            data = item.get('data') or {}
            if data.get('audio'):
                audio = base64.b64decode(data['audio'], validate=True)
                if len(audio) % 2:
                    raise ProviderError('讯飞返回PCM16音频长度无效')
                total += len(audio)
                if total > 16000 * 2 * 60:
                    raise ProviderError('单次学生声音超过一分钟，已停止')
                if not cancelled():
                    on_audio(data['audio'], 16000)
            if data.get('status') == 2:
                if not total:
                    raise ProviderError('讯飞未返回合成音频')
                charge(usage_id, amount, 'tts', characters=len(text), audio_seconds=total/32000, voice=actual_voice)
                return
        if not cancelled():
            raise ProviderError('讯飞语音合成超时')
    except ProviderError:
        raise
    except Exception:
        raise ProviderError('讯飞语音合成失败，未播放完的文字不视为已发言') from None
    finally:
        if sock:
            sock.close()
