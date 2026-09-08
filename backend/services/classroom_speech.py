"""Provider-neutral classroom speech contract; no silent fallback."""
import os
import time
import websocket
from services import classroom_providers as bailian


def provider():
    value = os.getenv('SPEECH_PROVIDER', 'bailian').strip().lower()
    if value not in ('bailian', 'xfyun'):
        raise bailian.ProviderError('SPEECH_PROVIDER 仅支持 bailian 或 xfyun')
    return value


def normalize(event):
    names = {'input_audio_buffer.speech_started': 'speech_started',
             'input_audio_buffer.speech_stopped': 'speech_stopped',
             'conversation.item.input_audio_transcription.text': 'partial',
             'conversation.item.input_audio_transcription.completed': 'final',
             'session.finished': 'finished'}
    return {**event, 'type': names.get(event.get('type'), event.get('type'))}


class BailianASR(bailian.ASR):
    def receive(self):
        return normalize(super().receive())

    def finish(self):
        self.send('session.finish')

    def probe(self):
        self.finish()


def ASR(session_id):
    if provider() == 'xfyun':
        from services.xfyun_asr import ASR as XfyunASR
        return XfyunASR(session_id)
    return BailianASR(session_id)


def speak(text, session_id, voice, cancelled, on_audio):
    if provider() == 'xfyun':
        from services.xfyun_speech import speak as xfyun_speak
        return xfyun_speak(text, session_id, voice, cancelled, on_audio)
    return bailian.speak(text, session_id, voice, cancelled, lambda audio: on_audio(audio, 24000))


def describe(service):
    if service in ('dialogue', 'vision'):
        return {'provider': 'deepseek', 'model': bailian.model(service),
                'configured': bool(os.getenv('DEEPSEEK_API_KEY', '').strip()), 'pricing_confirmed': True}
    selected = provider()
    if selected == 'bailian':
        return {'provider': selected, 'model': bailian.model(service),
                'configured': bool(os.getenv('DASHSCOPE_API_KEY', '').strip()), 'pricing_confirmed': True}
    names = ['XFYUN_APP_ID', 'XFYUN_API_KEY', 'XFYUN_API_SECRET']
    if service == 'tts':
        names.append('XFYUN_TTS_VOICE')
    from services.xfyun_speech import rate, voice_for
    try:
        rate(service)
        priced, message = True, ''
    except ValueError as exc:
        priced, message = False, str(exc)
    result = {'provider': selected, 'model': 'slm / iat-v1' if service == 'asr' else 'online-tts-v2',
              'configured': all(os.getenv(n, '').strip() for n in names),
              'pricing_confirmed': priced, 'message': message}
    if service == 'tts' and result['configured']:
        result['voices'] = {s: voice_for(v) for s, v in [('ming','Ethan'),('yu','Cherry'),('lin','Serena')]}
    return result


def probe_asr():
    asr = ASR(None)
    try:
        asr.probe()
        until = time.monotonic() + 12
        while time.monotonic() < until:
            try:
                if normalize(asr.receive())['type'] == 'finished':
                    asr.settle()
                    return
            except websocket.WebSocketTimeoutException:
                continue
        raise bailian.ProviderError('语音识别探针收尾超时')
    finally:
        asr.close()
