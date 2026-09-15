"""文档切分：按中文句读边界聚合，目标 chunk_size 字、overlap 重叠。纯函数，无第三方依赖。"""

import re
from typing import Protocol


class Chunker(Protocol):
    def chunk(self, text: str) -> list[str]: ...


_SENT_SPLIT = re.compile(r"(?<=[。！？!?；;\n])")


def split_sentences(text: str) -> list[str]:
    """按句读切分，保留分隔符；空句过滤。"""
    parts = _SENT_SPLIT.split(text)
    sentences: list[str] = []
    buf = ""
    for part in parts:
        buf += part
        if part and part[-1] in "。！？!?；;\n":
            sentences.append(buf)
            buf = ""
    if buf.strip():
        sentences.append(buf)
    return [s for s in sentences if s.strip()]


class SentenceChunker:
    """贪心聚合句子到目标长度；超长单句原样保留（避免截断语义）。"""

    def __init__(self, chunk_size: int = 480, overlap: int = 64) -> None:
        if overlap >= chunk_size:
            raise ValueError("overlap 必须小于 chunk_size")
        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk(self, text: str) -> list[str]:
        sentences = split_sentences(text)
        chunks: list[str] = []
        cur = ""
        for s in sentences:
            if not cur:
                cur = s
            elif len(cur) + len(s) <= self.chunk_size:
                cur += s
            else:
                chunks.append(cur)
                # ponytail: 重叠取上一段末尾 overlap 字，可能切在句中间；可接受
                cur = (cur[-self.overlap :] + s) if self.overlap else s
        if cur.strip():
            chunks.append(cur)
        return chunks
