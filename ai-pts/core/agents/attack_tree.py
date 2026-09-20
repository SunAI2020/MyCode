"""
攻击树（PTT，Penetration Testing Tree）

借鉴 PentestGPT 的 PTT：Planner 把总目标分解为子目标树，叶子节点映射到能力目录的
exploit_type（或 "recon" 表示信息收集型节点）。节点状态 pending/active/succeeded/failed
持久化，供 Planner 选择"最可能成功的下一步"。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class PTTNode:
    node_id: str
    goal: str
    exploit_type: str = ""          # 能力目录 exploit_type 或 "recon"；空 = 中间/根节点
    state: str = "pending"          # pending / active / succeeded / failed
    children: List["PTTNode"] = field(default_factory=list)


class AttackTree:
    """攻击树：根 + 子目标节点，支持增删查改与渲染。"""

    def __init__(self, root_goal: str):
        # 根节点初始为 pending：Planner 未 expand 前，根本身可被 next_pending_leaf 选中，
        # 避免「首轮 select 无节点可用」死路。
        self.root = PTTNode(node_id="root", goal=root_goal, exploit_type="", state="pending")
        self._counter = 0

    def _new_id(self) -> str:
        self._counter += 1
        return f"n{self._counter}"

    def add_children(self, parent_id: str, sub_goals: List[Dict]) -> List[PTTNode]:
        """给指定节点添加子目标。sub_goals: [{goal, exploit_type}]。"""
        parent = self.find(parent_id) or self.root
        nodes: List[PTTNode] = []
        for sg in sub_goals or []:
            if not isinstance(sg, dict) or not sg.get("goal"):
                continue
            node = PTTNode(
                node_id=self._new_id(),
                goal=str(sg["goal"]),
                exploit_type=str(sg.get("exploit_type") or ""),
                state="pending",
            )
            parent.children.append(node)
            nodes.append(node)
        return nodes

    def find(self, node_id: str) -> Optional[PTTNode]:
        """深度优先查找节点。"""

        def _walk(n: PTTNode) -> Optional[PTTNode]:
            if n.node_id == node_id:
                return n
            for c in n.children:
                r = _walk(c)
                if r:
                    return r
            return None

        return _walk(self.root)

    def mark(self, node_id: str, state: str) -> Optional[PTTNode]:
        node = self.find(node_id)
        if node:
            node.state = state
        return node

    def _pending_leaves(self, node: PTTNode) -> List[PTTNode]:
        if not node.children:
            return [node] if node.state == "pending" else []
        out: List[PTTNode] = []
        for c in node.children:
            out.extend(self._pending_leaves(c))
        return out

    def next_pending_leaf(self) -> Optional[PTTNode]:
        leaves = self._pending_leaves(self.root)
        return leaves[0] if leaves else None

    @staticmethod
    def _leaves(node: PTTNode) -> List[PTTNode]:
        if not node.children:
            return [node]
        out: List[PTTNode] = []
        for c in node.children:
            out.extend(AttackTree._leaves(c))
        return out

    def all_succeeded(self) -> bool:
        """根的所有叶子节点均 succeeded（无 pending/failed 叶子）。"""
        leaves = self._leaves(self.root)
        return bool(leaves) and all(l.state == "succeeded" for l in leaves)

    def to_text(self) -> str:
        """缩进渲染攻击树。"""
        lines: List[str] = []
        mark_map = {"pending": "[ ]", "active": "[>]", "succeeded": "[✓]", "failed": "[✗]"}

        def _walk(n: PTTNode, depth: int) -> None:
            mark = mark_map.get(n.state, "[ ]")
            t = f" ({n.exploit_type})" if n.exploit_type else ""
            lines.append(f"{'  ' * depth}{mark} {n.node_id} {n.goal}{t}")
            for c in n.children:
                _walk(c, depth + 1)

        _walk(self.root, 0)
        return "\n".join(lines)

    def snapshot(self) -> Dict:
        def _to_dict(n: PTTNode) -> Dict:
            return {
                "node_id": n.node_id,
                "goal": n.goal,
                "exploit_type": n.exploit_type,
                "state": n.state,
                "children": [_to_dict(c) for c in n.children],
            }

        return _to_dict(self.root)
