"""
知识库存储：KnowledgeEntry + KnowledgeStore（BM25 检索）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from core.knowledge.retriever import BM25, tokenize


@dataclass
class KnowledgeEntry:
    id: str
    kind: str          # attack_case / cve / cwe / technique / tool
    title: str
    text: str
    meta: Dict = field(default_factory=dict)


class KnowledgeStore:
    """自包含知识库：条目 + BM25 检索（无外部向量库）。"""

    def __init__(self):
        self._entries: Dict[str, KnowledgeEntry] = {}
        self._order: List[str] = []
        self._bm25 = BM25()
        self._counter = 0

    def add(self, kind: str, title: str, text: str, meta: Optional[Dict] = None,
            entry_id: Optional[str] = None) -> KnowledgeEntry:
        eid = entry_id or f"{kind}-{self._counter}"
        self._counter += 1
        entry = KnowledgeEntry(id=eid, kind=kind, title=title, text=text, meta=meta or {})
        self._entries[eid] = entry
        self._order.append(eid)
        self._bm25.add(tokenize(f"{title} {text}"))
        return entry

    def get(self, entry_id: str) -> Optional[KnowledgeEntry]:
        return self._entries.get(entry_id)

    def search(self, query: str, top_k: int = 5) -> List[KnowledgeEntry]:
        """按 BM25 分数降序返回 >0 分的条目，最多 top_k 条。"""
        qt = tokenize(query)
        if not qt:
            return []
        scores = self._bm25.score(qt)
        ranked = sorted(range(len(scores)), key=lambda i: -scores[i])
        out: List[KnowledgeEntry] = []
        for i in ranked:
            if scores[i] <= 0 or len(out) >= top_k:
                break
            out.append(self._entries[self._order[i]])
        return out

    def __len__(self) -> int:
        return len(self._entries)
