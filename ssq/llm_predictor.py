#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
SSQ 大模型推理增强模块 — Claude/LLM 作为元推理器
=================================================

传统统计/ML 模型做"粗筛", 大模型做"精判"。
在预测 pipeline 中插入 LLM 推理校验层。

使用方式:
  A. CC Agent 调用 (本会话内):
     from llm_predictor import build_analysis_prompt
     prompt = build_analysis_prompt(analyzer, candidates)
     # 然后将 prompt 发送给 Claude Agent 获取推理结果

  B. 仅生成 Prompt (用于手动或外部调用):
     from llm_predictor import build_analysis_prompt, build_post_draw_prompt
"""

import json
import re
from typing import Dict, List, Optional


def build_analysis_prompt(
    analyzer,                    # FeatureEngineer instance
    strategy_candidates: Dict,   # {strategy_name: {'info':{...}, 'predictions':[...]}}
    previous_analysis: str = "",  # 上期 LLM 分析结果 (持续学习闭环)
) -> str:
    """构建预测分析 prompt, 发送给 Claude/LLM 进行推理"""

    # ---- 数据概况 ----
    latest = analyzer.history[-1] if analyzer.draw_count > 0 else None
    data_section = f"""## 数据概况
- 历史总期数：{analyzer.draw_count}
- 最新一期：{latest.issue if latest else 'N/A'} {latest.date if latest else ''}
- 开奖号码：{' '.join(f'{r:02d}' for r in latest.reds) if latest else 'N/A'} + {f'{latest.blue:02d}' if latest else 'N/A'}
"""

    # ---- 统计特征 ----
    freq_all = analyzer.red_freq
    top8_red = sorted(freq_all.items(), key=lambda x: -x[1])[:8]
    # red_freq 归一化后总和≈6（每期6红球），均值≈6/33≈0.18，
    # 热/冷阈值须相对均值判断（与 FeatureEngineer.hot_cold 的 1.5/0.5 约定一致）
    red_mean = sum(freq_all.values()) / 33
    hot_reds = [i for i in range(1, 34) if freq_all.get(i, 0) > red_mean * 1.5]
    cold_reds = [i for i in range(1, 34) if freq_all.get(i, 0) < red_mean * 0.5]

    stats_section = f"""## 统计特征
- 热号红球 (高频)：{hot_reds[:10] if hot_reds else '无'}
- 冷号红球 (低频)：{cold_reds[:10] if cold_reds else '无'}
- 红球频率 TOP8：{', '.join(f'{n}({freq_all.get(n,0)*100:.1f}%)' for n,_ in top8_red)}
- 和值：均值 {analyzer.sum_mean:.0f} +/- {analyzer.sum_std:.0f}
- 跨度：均值 {analyzer.span_mean:.0f} +/- {analyzer.span_std:.0f}
- 奇偶比：{analyzer.odd_ratio:.1%} (历史奇数占比)
- 连号概率：{analyzer.consecutive_prob:.1%}
- 区间分布：一区 {analyzer.zone_avg[0]*6:.1f} 二区 {analyzer.zone_avg[1]*6:.1f} 三区 {analyzer.zone_avg[2]*6:.1f}
"""

    # ---- 蓝球专项 ----
    bf = analyzer.blue_freq
    top_blue = sorted(bf.items(), key=lambda x: -x[1])[:5]
    last_blues = [str(d.blue) for d in analyzer.history[-10:]]
    blue_section = f"""## 蓝球专项
- 蓝球频率 TOP5：{', '.join(f'{n}({bf.get(n,0)*100:.1f}%)' for n,_ in top_blue)}
- 最近10期蓝球序列：{' -> '.join(last_blues)}
- 蓝球奇偶模式：{' '.join('奇' if int(b)%2==1 else '偶' for b in last_blues[-8:])}
"""

    # ---- 位置统计 ----
    pos_section = ""
    if hasattr(analyzer, 'pos_mean') and any(analyzer.pos_mean):
        pos_section = "## 位置特征 (6个位置独立统计)\n"
        for p in range(6):
            lo, hi = (analyzer.pos_bounds[p] if hasattr(analyzer, 'pos_bounds')
                      and analyzer.pos_bounds else (1, 33))
            pos_section += f"- 位置{p+1}：均值 {analyzer.pos_mean[p]:.1f} +/- {analyzer.pos_std[p]:.1f} 范围 [{lo}-{hi}]\n"

    # ---- 共现规则 ----
    assoc_section = ""
    if hasattr(analyzer, 'top_assoc_pairs') and analyzer.top_assoc_pairs:
        assoc_section = "## 显著共现对 (高 lift 值, 表示号码倾向于成对出现)\n"
        for (a, b), lift in analyzer.top_assoc_pairs[:8]:
            assoc_section += f"- ({a:02d}, {b:02d}) lift={lift:.2f}\n"

    # ---- 各策略候选 ----
    candidates_section = "## 各策略候选号码\n\n"
    for strategy_name, data in strategy_candidates.items():
        info = data.get('info', {})
        preds = data.get('predictions', [])
        display_name = info.get('name', strategy_name)
        algo = info.get('algorithm', strategy_name)
        candidates_section += f"### {display_name} ({algo})\n"
        for i, p in enumerate(preds[:3], 1):
            reds_str = ' '.join(f'{r:02d}' for r in p.reds)
            candidates_section += f"{i}. 红球 [{reds_str}] 蓝球 {p.blue:02d} 评分 {p.score:.1f}\n"
        candidates_section += "\n"

    # ---- 上期反馈 (持续学习闭环) ----
    prev_context = ""
    if previous_analysis:
        prev_context = f"""## 上期 LLM 分析反馈 (持续学习)
{previous_analysis}

"""

    # ---- 任务指令 ----
    task_section = """## 任务

你是一位经验丰富的双色球彩票分析师。基于以上完整统计数据和各策略候选号码，请完成：

### 第一步：态势判断
分析当前号码走势特征 (3-5句)：
- 当前是偏大号还是偏小号趋势？奇数偏多还是偶数偏多？
- 是否可能出现连号？区间分布倾向如何？
- 蓝球当前处于什么模式 (奇偶交替/大小轮换/冷号回补)？

### 第二步：策略评审
对每个策略的候选号码给出 1-5 星合理性评分并简评。

### 第三步：生成 10 组推荐号码
综合各策略优势生成最终推荐。每组 6 个红球(1-33升序) + 1 个蓝球(1-16)。
要求：10 组之间应有一定差异性 (覆盖不同可能)，每组给出推理依据。

### 输出格式 (JSON)
```json
{
  "situation_analysis": "态势判断文本...",
  "strategy_reviews": {"策略名": {"stars": 4, "comment": "简评"}},
  "predictions": [
    {"reds": [1,5,12,18,25,30], "blue": 8, "reasoning": "依据...", "confidence": 0.75}
  ]
}
```

注意：彩票为随机事件，以上分析仅供学术研究参考，不构成投注建议。
"""

    return (
        "你是双色球彩票数据分析专家。以下是基于 2500+ 期历史数据的完整统计分析和各策略模型候选预测。\n\n"
        + data_section + stats_section + blue_section
        + pos_section + assoc_section
        + prev_context + candidates_section + task_section
    )


def build_post_draw_prompt(
    predictions: List,       # 预测号码列表 (Prediction objects)
    actual_reds: List[int],  # 实际红球
    actual_blue: int,        # 实际蓝球
    issue: str,              # 期号
) -> str:
    """构建开奖后分析 prompt — 让 LLM 分析预测得失并给出下期建议"""

    # 统计命中
    best_red, best_blue = 0, 0
    best_pred, total_red, total_blue = None, 0, 0
    for p in predictions:
        red_hit = len(set(p.reds) & set(actual_reds))
        blue_hit = 1 if p.blue == actual_blue else 0
        total_red += red_hit
        total_blue += blue_hit
        if red_hit > best_red or (red_hit == best_red and blue_hit > best_blue):
            best_red, best_blue, best_pred = red_hit, blue_hit, p

    n = len(predictions) if predictions else 1
    actual_reds_str = ' '.join(f'{r:02d}' for r in sorted(actual_reds))

    prompt = f"""## 预测回顾 — 第 {issue} 期

### 概况
- 预测总数：{n} 组
- 平均红球命中：{total_red/n:.2f}/6
- 蓝球命中率：{total_blue/n:.1%}
- 最佳：红球 {best_red}/6 蓝球 {'命中' if best_blue else '未中'}

### 实际开奖
红球 [{actual_reds_str}] 蓝球 {actual_blue:02d}

### 各预测命中详情
"""
    for i, p in enumerate(predictions[:10], 1):
        red_hit = len(set(p.reds) & set(actual_reds))
        blue_hit = 'Y' if p.blue == actual_blue else 'N'
        matched = sorted(set(p.reds) & set(actual_reds))
        prompt += f"{i}. [{p.strategy}] 红球命中{red_hit}/6 {matched} 蓝球{blue_hit}\n"

    prompt += """
## 任务
1. 分析本期预测得失的原因 — 哪个统计信号与结果吻合/背离？
2. 哪些策略表现好/差？为什么？
3. 下期调整建议 (关注遗漏? 热号? 蓝球策略? 区间分配?)
4. 从本期学到了什么？

请用 3-5 段话提供 actionable 分析。
"""
    return prompt


def format_candidates_for_llm(predictions_by_strategy: Dict, max_per: int = 3) -> str:
    """将 predict_per_strategy 输出格式化为 LLM prompt 友好文本"""
    lines = []
    for name, data in predictions_by_strategy.items():
        info = data.get('info', {})
        preds = data.get('predictions', [])
        lines.append(f"\n### {info.get('name', name)} ({name})")
        lines.append(f"算法: {info.get('algorithm', name)}")
        for i, p in enumerate(preds[:max_per], 1):
            rs = ' '.join(f'{r:02d}' for r in p.reds)
            lines.append(f"  {i}. [{rs}] + {p.blue:02d} score:{p.score:.1f}")
    return '\n'.join(lines)


def parse_llm_response(response_text: str) -> Optional[Dict]:
    """解析 LLM 返回的 JSON 预测结果"""
    try:
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', response_text)
        if json_match:
            return json.loads(json_match.group(1))
        return json.loads(response_text)
    except (json.JSONDecodeError, AttributeError):
        return None


# ============================================================================
# 测试入口
# ============================================================================

if __name__ == '__main__':
    import sys
    sys.path.insert(0, '.')
    from ssq_database import get_all_results
    from ssq_prediction_v2 import (
        FeatureEngineer, LotteryDraw, predict_per_strategy,
    )

    history_dicts = get_all_results()
    draws = [LotteryDraw(
        issue=d['issue_number'], date=d['draw_date'],
        reds=[d['red_1'], d['red_2'], d['red_3'], d['red_4'], d['red_5'], d['red_6']],
        blue=d['blue'], year=d['year'],
    ) for d in history_dicts]

    analyzer = FeatureEngineer(draws)
    candidates = predict_per_strategy(history_dicts, fast_mode=True)

    prompt = build_analysis_prompt(analyzer, candidates)
    print(f"Prompt size: {len(prompt)} chars (~{len(prompt)//3} tokens)")
    print(f"Strategies included: {len(candidates)}")

    with open('llm_prediction_prompt.txt', 'w', encoding='utf-8') as f:
        f.write(prompt)
    print("[OK] Prompt saved to llm_prediction_prompt.txt")
    print("[Tip] Send this prompt to Claude via CC Agent for AI-enhanced predictions")
