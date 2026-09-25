"""Section-level parent context for multi-granularity retrieval."""


def section_summaries(chunks):
    """Map section_key -> short parent summary from grouped chunks."""
    groups = {}
    for chunk in chunks:
        key = tuple(chunk.heading_path or [])
        groups.setdefault(key, []).append(chunk.text)
    summaries = {}
    for key, texts in groups.items():
        joined = '\n'.join(texts)
        summary = joined[:280] + ('…' if len(joined) > 280 else '')
        summaries[key] = summary
    return summaries
