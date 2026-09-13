# SSQ 双色球预测算法优化计划

## Context

当前预测系统平均红球命中仅 **1.03/6**，蓝球命中率 **4.9%**（低于随机 6.25%），最高红球命中记录仅 **3/6**，且从未命中 4+ 红球。

**数据现状**：数据库含 2508 期历史开奖（2010-2026），350 条已评估预测。PyTorch 在此机器上因 `c10.dll` 错误无法加载，LSTM 策略实际一直降级为 MCMC。核心问题是：

1. **无视位置特征** — 6个红球位置各有独特分布（位置1偏小、位置6偏大），但被平等对待
2. **蓝球策略失效** — 比随机还差，完全未能捕捉蓝球规律
3. **策略高度同质** — 频率/遗漏/趋势本质是同一信号的不同变体
4. **忽视号码关联** — 号码组合的共现关系未被挖掘
5. **缺乏时间衰减** — 2020年数据与2026年等权重
6. **融合机制粗糙** — 权重近乎均匀（策略表现都在地板线），温度扰动只是随机噪声

## 优化方案

### 一、位置感知分析系统（最优先）

**原理**：双色球6个红球位置（从小到大排序后）各有独立的统计分布。历史上位置1从未出现过>18，位置6从未出现过<10。按位置独立建模可大幅缩小搜索空间。

**实现**：
1. 新增 `PositionalStats` 类，计算每个位置的：
   - 频率分布、遗漏、冷热状态
   - 移动平均趋势（10期/30期/50期）
   - 位置边界约束（如位置1不可能>18，位置6不可能<15）
2. 新增 `PositionAwareStrategy` 策略：逐位置采样 → 组合 → 验证，仅此一项即可替代 Frequency/Missing/Trend 三个策略
3. 修改 `_validate()` 增加位置边界检查

### 二、蓝球预测系统重建

**问题诊断**：当前蓝球策略严重低效（4.9% < 6.25%）。原因：
- 蓝球权重计算系数太小（`missing * 0.03`），信号被噪声淹没
- 未利用蓝球的短周期模式（奇偶交替、连续重复概率极低等）
- ML模型在蓝球上类别不均衡处理粗糙

**实现**：
1. 新增 `BlueBallAnalyzer` 类，专注蓝球模式：
   - 奇偶交替概率分析
   - 大小交替（1-8小、9-16大）
   - 012路（模3）分析
   - 蓝球遗漏后回补窗口（遗漏20期+后大概率回补）
   - 蓝球与上一期红球的关系（历史上蓝球=上期某个红球的概率~15%）
2. 新增 `BlueDedicatedStrategy`：综合6个独立蓝球信号加权
3. 调整融合权重：蓝球预测使用独立评分体系

### 三、共现/关联规则挖掘

**原理**：某些红球号码倾向于成对出现。例如，如果号码5出现，号码12的出现概率从基准的18%提升到35%。

**实现**：
1. 新增 `CooccurrenceMiner` 类：
   - 计算所有球对的共现频次和 lift 值
   - 计算三联体（triplet）共现
   - 按 lift 排序，选取显著关联（lift > 1.5）
2. 在融合阶段利用共现关系调整权重
3. 新增 `AssociationBoostStrategy`：基于高 lift 关联对生成候选组合

### 四、指数衰减时间加权

**实现**：
1. 所有统计分析器接受 `decay_factor` 参数（默认 0.98/期，半衰期~35期）
2. 加权后的频率：`freq[i] = Σ decay_factor^(total_draws - draw_idx) * indicator(draw contains i)`
3. 应用到：频率分析、冷热分析、转移矩阵、特征提取

### 五、模块化/谐波模式分析

**原理**：号码之间存在数学关系模式：
- 同尾号（2, 12, 22, 32）的出现概率关联
- 模3/模5/模7分布
- 斐波那契数的聚集效应

**实现**：
1. 新增 `ModularPatterns` 类
2. 新增 `PatternConstraintStrategy`：基于历史模式比例指导号码选择

### 六、LSTM 模型升级

**实现**：
1. 输入从49维升级为233维（复用 `FeatureEngineer.build_features()`）
2. 添加 attention 层替代最后时刻的简单输出
3. 添加 80/10/10 train/val/test 分割，早停机制
4. 添加 dropout=0.3 降低过拟合

### 七、Bootstrap 集成替代温度扰动

**实现**：
1. 对训练数据进行 bootstrap 重采样（有放回抽样，保留80%数据量）
2. 训练 N 个不同 bootstrap 版本
3. 每个 bootstrap 版本独立生成预测 → N组真正多样化的预测
4. 去重后按得分排序输出 TOP 10

### 八、策略重组——正交化

**重组后的策略体系**：

| 策略 | 核心方法 | 与其他的正交性 |
|------|---------|-------------|
| `position_aware` | 6位置独立频率+遗漏+趋势 | 新（替代freq+missing+trend+zone） |
| `mcmc_v2` | 升级版MH：目标含共现lift | 升级（目标函数含关联项） |
| `lstm_v2` | 233维+attention+早停 | 升级（时序深度特征） |
| `xgboost_v2` | 233维+位置特征 | 升级（特征增加位置标签） |
| `association_boost` | 共现关联驱动 | **全新** |
| `blue_dedicated` | 蓝球6信号融合 | **全新** |
| `llm_ensemble` | **★ 大模型推理融合 ★** | **全新（核心差异化）** |

### 九、大模型 AI 增强预测（Claude Code Agent 调用）

核心理念：传统统计/ML 模型做"粗筛"，大模型做"精判"。通过 CC SWITCH 调用 Claude 等大模型，在预测 pipeline 中插入一个**推理校验层**。

#### 9.1 整体架构

```
历史数据 → 统计特征提取 → 6个策略各自生成候选 →
┌─────────────────────────────────────────────┐
│  ★ 大模型推理层 (Claude via CC Agent) ★      │
│  1. 分析当前统计态势（冷热/遗漏/趋势/异常）    │
│  2. 评审各策略候选号码的合理性                │
│  3. 调整融合权重（哪个策略当前更可信）         │
│  4. 生成最终的 TOP 10 推荐号码                │
└─────────────────────────────────────────────┘
→ 保存预测 → GUI 展示
```

#### 9.2 大模型推理 Prompt 设计

新增 `llm_predictor.py` 模块，将统计特征 + 候选号码打包为结构化 prompt，通过 Agent 工具调用大模型：

**Prompt 模板**（每次预测发送给 Claude）：
```
你是双色球彩票分析专家。以下是基于历史数据的统计分析结果：

## 数据概况
- 历史总期数：{total_draws}
- 最新一期：{latest_issue} 开奖 {latest_reds} + {latest_blue}

## 统计特征
- 热号（最近30期高频）：{hot_numbers}
- 冷号（最近30期低频）：{cold_numbers}
- 红球遗漏TOP8：{missing_top8}
- 和值：均值{sum_mean}±{sum_std}
- 跨度：均值{span_mean}±{span_std}
- 奇偶比：{odd_ratio}
- 连号概率：{consecutive_prob}
- 区间分布：一区{zone1} 二区{zone2} 三区{zone3}
- 蓝球近期趋势：{blue_trend}

## 各策略候选号码
{strategy_candidates}

## 任务
1. 分析当前统计态势，判断本期可能的号码特征（偏大/偏小？奇多/偶多？有无连号？）
2. 评估各策略候选的合理性，给出1-5星评分
3. 综合各策略优势，生成10组最合理的预测号码（6红+1蓝）
4. 给出每组号码的推理依据
```

#### 9.3 实现方式

**方式A：Agent 调用（推荐，简单可靠）**
```python
class LLMEnsembleStrategy:
    """使用 Claude Agent 作为元推理器"""
    def predict(self, analyzer, strategy_candidates, n=10):
        # 1. 构建结构化 prompt
        prompt = self._build_analysis_prompt(analyzer, strategy_candidates)
        # 2. 通过 Agent 工具调用 Claude
        result = agent(prompt, schema=PREDICTION_SCHEMA)
        # 3. 解析返回的10组号码
        return self._parse_llm_response(result)
```

**方式B：直接 API 调用**
```python
import anthropic
client = anthropic.Anthropic()
response = client.messages.create(
    model="claude-sonnet-5",
    messages=[{"role": "user", "content": prompt}],
    response_format={"type": "json_schema", ...}
)
```

#### 9.4 大模型的具体增强点

| 增强点 | 传统方法 | +大模型 | 预期提升 |
|--------|---------|--------|---------|
| **态势判断** | 固定阈值（mean±3σ） | LLM 综合判断趋势方向 | 更精准的约束范围 |
| **策略选择** | EMA/Elo 权重 | LLM 根据态势推理该信任谁 | 更快适应变化 |
| **号码校验** | sum/span/parity 检查 | LLM 逻辑推理合理性 | 过滤不合理组合 |
| **多样性生成** | 随机温度扰动 | LLM 主动设计差异化方案 | 真正覆盖不同可能 |
| **蓝球决策** | 加权采样 | LLM 推理蓝球模式 | 蓝球命中率提升 |
| **后验分析** | 统计均值 | LLM 分析为什么没命中 | 持续改进方向 |

#### 9.5 LLM 后验分析（开奖后）

每次开奖后，将预测 vs 实际结果发给大模型分析：
```
## 本期预测回顾
预测号码: {predictions}
实际开奖: {actual_reds} + {actual_blue}
命中情况: 红球{red_hit}/6 蓝球{'✓' if blue_hit else '✗'}

## 任务
1. 分析为什么预测命中/未命中
2. 当前哪些策略的信号与结果吻合/背离
3. 建议下期调整方向（更关注遗漏？更关注热号？加大蓝球权重？）
```

这个分析结果反馈到下一期的 prompt 中，形成持续学习闭环。

#### 9.6 成本控制

- 每次预测调用 1 次大模型（约 2000 input + 1000 output tokens）
- 每次后验分析调用 1 次（约 1500 input + 500 output tokens）
- 每周 3 次开奖 = 每周约 6 次调用 ~15000 tokens/周
- 成本极低（Sonnet/Opus 按 token 计费）

### 十、权重更新机制修正

**修正**：
1. 使用相对排名替代绝对分数：每期对策略按命中数排名
2. 权重更新使用 Elo 评分系统：`Δ = K * (actual_score - expected_score)`，K=32
3. 结合 AI 元学习器的动态权重输出

## 修改文件清单

### 主要修改：`D:\projects\ssq\ssq_prediction_v2.py`

1. **新增类**（~900行）：
   - `PositionalStats` — 位置统计（~80行）
   - `BlueBallAnalyzer` — 蓝球专项分析（~120行）
   - `CooccurrenceMiner` — 共现挖掘（~100行）
   - `ModularPatterns` — 模数/谐波模式（~80行）
   - `PositionAwareStrategy(BaseStrategy)` — 位置感知策略（~100行）
   - `BlueDedicatedStrategy(BaseStrategy)` — 蓝球专项策略（~80行）
   - `AssociationBoostStrategy(BaseStrategy)` — 关联增强策略（~80行）
   - `ModularPatternStrategy(BaseStrategy)` — 模数韵律策略（~80行）
   - `BootstrapRFStrategy(BaseStrategy)` — Bootstrap集成策略（~120行）
   - `LSTMAttentionPredictor(nn.Module)` — 带Attention的LSTM替代原LSTMPredictor

2. **修改现有类/函数**：
   - `FeatureEngineer`：添加 `decay_factor`（半衰期180期）、位置特征(198维)、模数特征(25维)、周期特征(12维)；特征向量从233维扩展到约525维
   - `MCMCStrategy._target()`：加入共现lift项、位置约束项
   - `LSTMStrategy`：输入升级为525维、替换为LSTMAttentionPredictor、早停(patience=15)、梯度裁剪
   - `XGBoostStrategy._train()`：特征增加位置标签
   - `StackingEnsemble._diversify()`：结构化多样化（不同sum/span/odd-even组合替代温度扰动）
   - `BacktestEngineV2._update_weights()`：Elo评分 + 策略正交性奖励
   - `PREDICTORS`：新增5个预测员（位势大师、关系网、韵律师、蓝精灵、千面佛）

### 新增文件：`D:\projects\ssq\llm_predictor.py`

- `LLMEnsembleStrategy` — 通过 CC Agent 调用 Claude 大模型做推理融合（~200行）
- `build_analysis_prompt()` — 构建结构化分析 prompt
- `parse_llm_response()` — 解析大模型返回的预测结果
- `post_draw_analysis()` — 开奖后让大模型分析预测得失

### 次要修改：`D:\projects\ssq\ssq_database.py`

- 添加 `get_weighted_results(decay_factor)` 查询函数
- 新增 `strategy_performance` 表（记录策略相关性和权重变化）
- 新增 `association_rules` 表（缓存共现规则）

### 不改动：`D:\projects\ssq\ssq_gui_v2.py`

- GUI接口保持不变（`predict_per_strategy()` 签名兼容）

## 验证方案

1. **单元测试**：在历史数据上运行回测，对比新旧算法
2. **回测验证**：`python ssq_prediction_v2.py` 查看递推回测表现
3. **实际开奖跟踪**：预测 2026092 期（2026-08-11开奖）后对比

## 实施顺序

1. **Phase 1**：基础设施
   - `FeatureEngineer` 扩展：指数衰减加权、位置统计、模数分析、共现挖掘
   - `ssq_database.py`：新增表和查询函数

2. **Phase 2**：新策略实现
   - `PositionAwareStrategy`、`BlueDedicatedStrategy`、`AssociationBoostStrategy`、`ModularPatternStrategy`

3. **Phase 3**：现有策略升级
   - MCMC目标函数升级、LSTM→LSTMAttentionPredictor、XGBoost/RF特征扩展、BootstrapRFStrategy

4. **Phase 4**：融合层改造
   - `StackingEnsemble` 结构化多样化、权重 Elo + 正交性奖励

5. **Phase 5**：大模型推理层
   - 新建 `llm_predictor.py`、`LLMEnsembleStrategy`、后验分析闭环

6. **Phase 6**：测试验证
   - 回测对比新旧算法、预测 2026092 期（2026-08-11开奖）实际验证
