"""Text normalization that keeps Chinese punctuation intact (no NFKC folding)."""
import re
from collections import Counter

CJK = '\u3400-\u9fff\uf900-\ufaff'
CJK_PUNCT = '，。；：！？、（）《》“”‘’【】'
_ZERO_WIDTH = re.compile('[\u200b-\u200f\u2028\u2029\u2060\ufeff\u00ad]')
_CONTROL = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]')
_SPACES = re.compile(r'[ \t\u3000\u00a0]+')
# PDF extraction often letter-spaces text ("教 学 评 价"); only runs of single characters are joined,
# so meaningful gaps such as "第一章 导入技能" survive.
_LETTER_SPACED = re.compile(rf'(?<!\S)[{CJK}{CJK_PUNCT}](?: [{CJK}{CJK_PUNCT}]){{2,}}(?!\S)')
_PAGE_NUMBER = re.compile(
    r'^(?:第\s*\d+\s*页(?:\s*[/／,，]?\s*共\s*\d+\s*页)?|[-—–·\s]*\d{1,4}[-—–·\s]*'
    r'|\d{1,4}\s*/\s*\d{1,4}|page\s*\d+(?:\s*of\s*\d+)?)$', re.I)
_MEANINGFUL = re.compile(rf'[{CJK}A-Za-z0-9]')


def clean_line(text):
    text = _ZERO_WIDTH.sub('', text or '')
    text = _CONTROL.sub('', text)
    text = _SPACES.sub(' ', text)
    return _LETTER_SPACED.sub(lambda m: m.group(0).replace(' ', ''), text).strip()


def clean_text(text):
    lines = [clean_line(line) for line in str(text or '').replace('\r\n', '\n').replace('\r', '\n').split('\n')]
    return '\n'.join(line for line in lines if line)


def is_noise(line):
    return not _MEANINGFUL.search(line) or bool(_PAGE_NUMBER.match(line))


def strip_page_furniture(pages):
    """Drop running headers/footers and page numbers from per-page line lists."""
    pages = [[clean_line(line) for line in page] for page in pages]
    pages = [[line for line in page if line] for page in pages]
    repeated = set()
    if len(pages) >= 3:
        counts = Counter()
        for page in pages:
            edge = set(page[:2] + page[-2:])
            counts.update(re.sub(r'\d+', '#', line) for line in edge)
        threshold = max(3, len(pages) // 2)
        repeated = {line for line, count in counts.items() if count >= threshold}
    return [[line for line in page if not is_noise(line) and re.sub(r'\d+', '#', line) not in repeated]
            for page in pages]
