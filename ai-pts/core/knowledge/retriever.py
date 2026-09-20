"""
轻量 BM25 词法检索

自包含（无 torch/sqlite-vec 原生依赖）：英文/数字按词、中文按单字分词，TF-IDF 风格
计分，0 分 = 无重叠。留出可扩展空间，未来可替换为向量嵌入检索。
"""
from __future__ import annotations

import re
from collections import Counter
from math import log
from typing import Dict, List

_WORD_RE = re.compile(r"[a-z0-9]+")
_CJK_RE = re.compile(r"[一-鿿]")


def tokenize(text: str) -> List[str]:
    """简单分词：英文/数字按词（小写）、中文按单字，其它忽略。"""
    tokens: List[str] = []
    for m in _WORD_RE.finditer((text or "").lower()):
        tokens.append(m.group())
    tokens.extend(_CJK_RE.findall(text or ""))
    return tokens


class BM25:
    """TF-IDF 风格词法计分器（自包含，确定性）。"""

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.docs: List[List[str]] = []
        self.doc_len: List[int] = []
        self.df: Dict[str, int] = Counter()
        self.n = 0
        self.avgdl = 0.0

    def add(self, tokens: List[str]) -> None:
        self.docs.append(tokens)
        self.doc_len.append(len(tokens))
        for t in set(tokens):
            self.df[t] += 1
        self.n += 1
        self.avgdl = sum(self.doc_len) / self.n if self.n else 0.0

    def _idf(self, term: str) -> float:
        n = self.df.get(term, 0)
        return log((self.n - n + 0.5) / (n + 0.5) + 1.0)

    def score(self, query_tokens: List[str]) -> List[float]:
        """返回与 docs 对齐的每个文档得分。"""
        q = Counter(query_tokens)
        if not q or not self.docs:
            return [0.0] * self.n
        scores: List[float] = []
        for i, doc in enumerate(self.docs):
            tf = Counter(doc)
            dl = self.doc_len[i] or 1
            s = 0.0
            for t, qtf in q.items():
                f = tf.get(t, 0)
                if f == 0:
                    continue
                idf = self._idf(t)
                denom = (f + self.k1 * (1 - self.b + self.b * dl / self.avgdl)) if self.avgdl else (f + self.k1)
                s += idf * (f * (self.k1 + 1)) / denom * qtf
            scores.append(s)
        return scores
