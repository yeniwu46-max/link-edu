"""Official XFYun WSS wire format; never log signed URLs or response bodies."""
import base64
import hashlib
import hmac
import json
import os
from datetime import datetime, timezone
from email.utils import format_datetime
from urllib.parse import urlencode, urlsplit
import websocket
from services.classroom_providers import ProviderError, key

ASR_URL = 'wss://iat.xf-yun.com/v1'
TTS_URL = 'wss://tts-api.xfyun.cn/v2/tts'


def signed_url(url, now=None):
    if url not in (ASR_URL, TTS_URL):
        raise ProviderError('讯飞端点不在允许的WSS列表，本次未发送凭证')
    key('XFYUN_APP_ID')
    parsed = urlsplit(url)
    date = format_datetime(now or datetime.now(timezone.utc), usegmt=True)
    source = f'host: {parsed.netloc}\ndate: {date}\nGET {parsed.path} HTTP/1.1'
    signature = base64.b64encode(hmac.new(key('XFYUN_API_SECRET').encode(), source.encode(), hashlib.sha256).digest()).decode()
    auth = f'api_key="{key("XFYUN_API_KEY")}", algorithm="hmac-sha256", headers="host date request-line", signature="{signature}"'
    return url + '?' + urlencode({'authorization': base64.b64encode(auth.encode()).decode(), 'date': date, 'host': parsed.netloc})


def connect(url):
    address = signed_url(url)
    try:
        return websocket.create_connection(address, timeout=8, enable_multithread=True)
    except Exception:
        raise ProviderError('讯飞连接失败，请检查APPID、密钥、服务权限、系统时间和网络') from None


def receive(sock, service):
    try:
        raw = sock.recv()
        item = json.loads(raw)
        code = item.get('header', {}).get('code', item.get('code', 0))
        if code:
            safe_code = str(code) if isinstance(code, int) else 'unknown'
            raise ProviderError(f'讯飞{service}返回错误（{safe_code}），请核对服务/音色授权及余额')
        return item
    except websocket.WebSocketTimeoutException:
        raise
    except ProviderError:
        raise
    except Exception:
        raise ProviderError(f'讯飞{service}连接中断或返回格式无效') from None


def asr_frame(raw, status, seq):
    item = {'header': {'app_id': key('XFYUN_APP_ID'), 'status': status},
            'payload': {'audio': {'encoding': 'raw', 'sample_rate': 16000, 'channels': 1,
                'bit_depth': 16, 'seq': seq, 'status': status, 'audio': base64.b64encode(raw).decode()}}}
    if status == 0:
        item['parameter'] = {'iat': {'domain': 'slm', 'language': 'zh_cn', 'accent': 'mandarin',
            'eos': 6000, 'dwa': 'wpgs', 'result': {'encoding': 'utf8', 'compress': 'raw', 'format': 'json'}}}
    return item


class Transcript:
    """Apply sequence replacement, not string dedup (repeated words can be correct)."""
    def __init__(self):
        self.parts = {}

    def update(self, result):
        sn = result['sn']
        if type(sn) is not int or sn < 0:
            raise ProviderError('讯飞识别序号无效')
        if result.get('pgs') == 'rpl':
            bounds = result.get('rg')
            if not isinstance(bounds, list) or len(bounds) != 2 or any(type(i) is not int for i in bounds):
                raise ProviderError('讯飞识别修订范围无效')
            self.parts = {i: t for i, t in self.parts.items() if not bounds[0] <= i <= bounds[1]}
        self.parts[sn] = ''.join(w.get('cw', [{}])[0].get('w', '') for w in result.get('ws', []))
        return ''.join(self.parts[i] for i in sorted(self.parts))
