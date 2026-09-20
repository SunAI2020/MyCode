"""
轻量知识图谱（自研邻接表，无 networkx 依赖）。

实体：漏洞(vuln) / 攻击技术(technique) / 工具(tool)，边：漏洞→技术(exploitable_by)、
技术→工具(uses)。recommend(query) 命中节点后沿边收集攻击路径建议。
"""
from __future__ import annotations

from typing import Dict, List, Optional

from core.knowledge.retriever import tokenize


class KnowledgeGraph:
    def __init__(self):
        self._nodes: Dict[str, Dict] = {}       # node_id -> {kind, label, meta}
        self._out: Dict[str, List[tuple]] = {}  # src -> [(relation, dst), ...]

    def add_node(self, node_id: str, kind: str, label: str, meta: Optional[Dict] = None) -> None:
        self._nodes[node_id] = {"kind": kind, "label": label, "meta": meta or {}}

    def add_edge(self, src: str, dst: str, relation: str) -> None:
        self._out.setdefault(src, []).append((relation, dst))

    def _match(self, query: str) -> List[str]:
        """按关键词匹配节点 id/label/meta，返回命中 node_id。"""
        qt = set(tokenize(query))
        if not qt:
            return []
        hits: List[str] = []
        for nid, node in self._nodes.items():
            meta = node.get("meta", {})
            blob = set(tokenize(
                f"{nid} {node['label']} {meta.get('cve_id', '')} {meta.get('product', '')}"
            ))
            if qt & blob:
                hits.append(nid)
        return hits

    def recommend(self, query: str) -> List[Dict]:
        """命中漏洞/技术/工具节点，返回去重后的攻击路径建议。"""
        recs: List[Dict] = []
        for nid in self._match(query):
            node = self._nodes[nid]
            if node["kind"] == "vuln":
                # 漏洞 →(exploitable_by)→ 技术 →(uses)→ 工具
                for _rel, tech_id in self._out.get(nid, []):
                    tech = self._nodes.get(tech_id)
                    if not tech:
                        continue
                    for r, tool_id in self._out.get(tech_id, []):
                        if r != "uses":
                            continue
                        tool = self._nodes.get(tool_id)
                        if not tool:
                            continue
                        recs.append({
                            "exploit_type": tool["meta"].get("exploit_type", ""),
                            "tool": tool["meta"].get("tool", tool_id),
                            "technique": tech["label"],
                            "description": f"{node['label']} → {tech['label']} → {tool['label']}",
                        })
            elif node["kind"] in ("technique", "tool"):
                # 直接命中技术/工具节点
                meta = node["meta"]
                recs.append({
                    "exploit_type": meta.get("exploit_type", ""),
                    "tool": meta.get("tool", nid),
                    "technique": node["label"],
                    "description": f"直接命中：{node['label']}",
                })

        seen = set()
        out: List[Dict] = []
        for r in recs:
            # 按 (exploit_type, tool) 去重：同一工具同时被漏洞链与直接命中时，保留先出现的链式结果
            key = (r["exploit_type"], r["tool"])
            if key in seen:
                continue
            seen.add(key)
            out.append(r)
        return out

    def to_context(self) -> str:
        """渲染漏洞→技术→工具 关系（供展示/调试）。"""
        lines = ["知识图谱（漏洞 → 技术 → 工具）:"]
        for nid, node in self._nodes.items():
            if node["kind"] != "vuln":
                continue
            for rel, tech_id in self._out.get(nid, []):
                tech = self._nodes.get(tech_id, {})
                tools = [self._nodes.get(d, {}).get("label", d)
                         for r, d in self._out.get(tech_id, []) if r == "uses"]
                lines.append(f"  {node['label']} --{rel}--> {tech.get('label', tech_id)}"
                             + (f" --> {', '.join(tools)}" if tools else ""))
        return "\n".join(lines)
