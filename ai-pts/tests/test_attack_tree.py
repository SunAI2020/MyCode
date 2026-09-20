"""
core.agents.attack_tree 单元测试。
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.agents.attack_tree import AttackTree


def test_add_find_mark():
    tree = AttackTree("get_shell")
    nodes = tree.add_children("root", [{"goal": "获取 Web 权限", "exploit_type": "rce"}])
    assert len(nodes) == 1
    nid = nodes[0].node_id
    found = tree.find(nid)
    assert found is not None
    assert found.goal == "获取 Web 权限"
    tree.mark(nid, "succeeded")
    assert tree.find(nid).state == "succeeded"


def test_next_pending_leaf_skips_failed():
    tree = AttackTree("get_shell")
    a = tree.add_children("root", [{"goal": "A", "exploit_type": "rce"}])[0]
    b = tree.add_children("root", [{"goal": "B", "exploit_type": "msf"}])[0]
    assert tree.next_pending_leaf().node_id == a.node_id
    tree.mark(a.node_id, "failed")
    assert tree.next_pending_leaf().node_id == b.node_id


def test_all_succeeded():
    tree = AttackTree("get_shell")
    a = tree.add_children("root", [{"goal": "A", "exploit_type": "rce"}])[0]
    tree.mark(a.node_id, "succeeded")
    assert tree.all_succeeded() is True
    b = tree.add_children("root", [{"goal": "B", "exploit_type": "msf"}])[0]
    assert tree.all_succeeded() is False  # B pending
    tree.mark(b.node_id, "succeeded")
    assert tree.all_succeeded() is True


def test_to_text_and_snapshot():
    tree = AttackTree("get_shell")
    tree.add_children("root", [{"goal": "A", "exploit_type": "rce"}])
    text = tree.to_text()
    assert "get_shell" in text
    assert "A" in text
    assert "(rce)" in text
    snap = tree.snapshot()
    assert snap["node_id"] == "root"
    assert snap["children"][0]["goal"] == "A"
    json.dumps(snap)  # 可序列化


def test_root_is_pending_leaf_before_expansion():
    # 修复：根节点初始应为 pending，Planner 未 expand 前 select 也能选中根，避免死路
    tree = AttackTree("get_shell")
    node = tree.next_pending_leaf()
    assert node is not None
    assert node.node_id == "root"
