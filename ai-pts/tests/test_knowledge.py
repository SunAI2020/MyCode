"""
core.knowledge 单元测试：tokenize / KnowledgeStore / KnowledgeGraph / KnowledgeBase。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.knowledge import tokenize, KnowledgeStore, KnowledgeGraph, KnowledgeBase


def test_tokenize_mixed():
    t = tokenize("Apache 2.4.50 EternalBlue 远程代码执行")
    assert "apache" in t
    assert "eternalblue" in t
    assert "2" in t
    # 中文按单字
    assert "远" in t or "代" in t


def test_store_search_ranked():
    store = KnowledgeStore()
    store.add("attack_case", "MS17-010", "EternalBlue SMB 远程代码执行利用 msf", {"exploit_type": "msf"})
    store.add("attack_case", "SQLi", "SQL 注入用 sqlmap 检测", {"exploit_type": "sql_injection"})
    res = store.search("eternalblue ms17")
    assert res and res[0].title == "MS17-010"


def test_store_search_no_match_empty():
    store = KnowledgeStore()
    store.add("attack_case", "A", "eternalblue")
    assert store.search("zzzzz") == []


def test_store_top_k_truncation():
    store = KnowledgeStore()
    for i in range(5):
        store.add("attack_case", f"case{i}", "eternalblue")
    res = store.search("eternalblue", top_k=3)
    assert len(res) == 3


def test_graph_recommend_chain():
    g = KnowledgeGraph()
    g.add_node("v", "vuln", "MS17-010 EternalBlue", {"cve_id": "MS17-010"})
    g.add_node("t", "technique", "SMB RCE")
    g.add_node("tool", "tool", "msf ms17", {"exploit_type": "msf", "tool": "exploit/windows/smb/ms17_010_eternalblue"})
    g.add_edge("v", "t", "exploitable_by")
    g.add_edge("t", "tool", "uses")
    recs = g.recommend("ms17-010")
    assert len(recs) == 1
    assert recs[0]["exploit_type"] == "msf"
    assert "eternalblue" in recs[0]["tool"]


def test_knowledgebase_seeded_and_context_for():
    kb = KnowledgeBase()
    assert len(kb.store) > 0
    assert kb.recommend("ms17-010")  # 内置种子应命中
    ctx = kb.context_for("ms17-010 eternalblue")
    assert "ms17" in ctx.lower() or "eternalblue" in ctx.lower()
    # 无相关知识时不崩
    assert kb.context_for("完全无关的查询词xyzabc")
