"""Embedding providers. All vectors are float32 and L2-normalized so inner product == cosine."""
import hashlib
import logging
import math
import os
import re
from collections import Counter
from urllib.parse import urlparse

import httpx
import numpy as np


class EmbeddingError(RuntimeError):
    pass


def normalize(matrix):
    matrix = np.asarray(matrix, dtype=np.float32)
    norms = np.linalg.norm(matrix, axis=-1, keepdims=True)
    return matrix / np.where(norms == 0, 1, norms)


_CJK_RUN = re.compile(r'[\u3400-\u9fff\uf900-\ufaff]+')
_WORD = re.compile(r'[\u3400-\u9fff\uf900-\ufaffA-Za-z0-9]')
_STOPWORDS = frozenset('的 了 和 与 及 或 是 在 对 为 以 将 把 被 从 等 中 上 下 其 这 那 也 就 都 而 并 及其 进行 可以 应 应当'.split())


class HashEmbedder:
    """Offline lexical vectors (jieba words + CJK bigrams, feature hashing).
    Deterministic and free, for tests and key-less demos; it is NOT a semantic model."""

    provider = 'local'
    semantic = False

    def __init__(self, dim=1024, model='local-hash-v1'):
        self.dim = dim
        self.model = model

    @property
    def signature(self):
        return f'{self.provider}:{self.model}:{self.dim}'

    def _features(self, text):
        import jieba
        jieba.setLogLevel(logging.WARNING)
        text = text.lower()
        features = Counter()
        for token in jieba.lcut(text):
            token = token.strip()
            if token and token not in _STOPWORDS and _WORD.search(token):
                features[token] += 1.0
        for run in _CJK_RUN.findall(text):
            for i in range(len(run) - 1):
                features['#' + run[i:i + 2]] += 0.5
        return features

    def _vector(self, text):
        vector = np.zeros(self.dim, dtype=np.float32)
        for feature, count in self._features(text).items():
            digest = int.from_bytes(hashlib.blake2b(feature.encode('utf-8'), digest_size=8).digest(), 'big')
            sign = 1.0 if digest >> 63 else -1.0
            vector[digest % self.dim] += sign * math.log1p(count)
        return vector

    def embed_documents(self, texts):
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        return normalize(np.stack([self._vector(t) for t in texts]))

    def embed_query(self, text):
        return self.embed_documents([text])[0]


def _is_local_endpoint(url):
    host = (urlparse(url).hostname or '').lower()
    return host in ('localhost', '127.0.0.1', '::1') or host.endswith('.local')


class OpenAICompatibleEmbedder:
    """POST {base_url}/embeddings (DashScope compatible-mode, OpenAI, vLLM/Ollama/Xinference for bge etc.).
    Remote calls are reserved and settled on the classroom CNY ledger; loopback endpoints are free."""

    provider = 'openai_compatible'
    semantic = True

    def __init__(self, base_url, api_key_name, model, dim, batch_size=10, timeout=30, ledger=None):
        if not base_url.startswith('https://') and not _is_local_endpoint(base_url):
            raise EmbeddingError('Embedding 端点必须使用 HTTPS（本机端点除外），本次未发送密钥')
        self.base_url = base_url.rstrip('/')
        self.api_key_name = api_key_name
        self.model = model
        self.dim = dim
        self.batch_size = batch_size
        self.timeout = timeout
        self.ledger = (not _is_local_endpoint(base_url)) if ledger is None else ledger

    @property
    def signature(self):
        return f'{self.provider}:{self.model}:{self.dim}'

    def _reserve(self, texts):
        if not self.ledger:
            return None, 0.0
        from services import classroom_budget as budget
        try:
            rate = budget.price('RAG_EMBEDDING_CNY_PER_MILLION')
            # UTF-8 bytes conservatively bound token counts, matching the chat adapters.
            upper = sum(len(t.encode('utf-8')) for t in texts) + 64
            return budget.reserve('rag_embedding', upper * rate / 1e6), rate
        except ValueError as error:
            raise EmbeddingError(str(error)) from None

    def _settle(self, usage_id, rate, usage):
        if usage_id is None:
            return
        from services import classroom_budget as budget
        tokens = usage.get('total_tokens', usage.get('prompt_tokens'))
        if type(tokens) is int and tokens >= 0:
            budget.settle(usage_id, tokens * rate / 1e6, {'tokens': tokens, 'model': self.model})

    def _request(self, texts):
        token = os.getenv(self.api_key_name, '').strip()
        if not token and not _is_local_endpoint(self.base_url):
            raise EmbeddingError(f'尚未配置 {self.api_key_name}')
        usage_id, rate = self._reserve(texts)
        body = {'model': self.model, 'input': texts, 'encoding_format': 'float'}
        if self.dim:
            body['dimensions'] = self.dim
        headers = {'Authorization': f'Bearer {token}'} if token else {}
        try:
            response = httpx.post(self.base_url + '/embeddings', json=body, headers=headers, timeout=self.timeout)
        except httpx.HTTPError:
            raise EmbeddingError('Embedding 服务网络请求失败或超时，请重试') from None
        if response.status_code != 200:
            from services.classroom_providers import provider_http_error
            raise EmbeddingError(str(provider_http_error(response.status_code, 'Embedding', self.api_key_name)))
        try:
            payload = response.json()
            items = sorted(payload['data'], key=lambda item: item['index'])
            vectors = np.asarray([item['embedding'] for item in items], dtype=np.float32)
        except (ValueError, KeyError, TypeError):
            raise EmbeddingError('Embedding 服务返回结构无效') from None
        if vectors.shape != (len(texts), self.dim):
            raise EmbeddingError(f'Embedding 维度不符：期望 {self.dim}，请检查 RAG_EMBEDDING_DIM 与模型是否匹配')
        self._settle(usage_id, rate, payload.get('usage') or {})
        return vectors

    def embed_documents(self, texts):
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        parts = [self._request(texts[i:i + self.batch_size]) for i in range(0, len(texts), self.batch_size)]
        return normalize(np.concatenate(parts))

    def embed_query(self, text):
        return self.embed_documents([text])[0]


def build_embedder(settings):
    if settings.embedding_provider == 'local':
        return HashEmbedder(settings.embedding_dim, settings.embedding_model)
    return OpenAICompatibleEmbedder(settings.embedding_base_url, settings.embedding_api_key_name,
                                    settings.embedding_model, settings.embedding_dim,
                                    settings.embedding_batch_size, settings.embedding_timeout)
