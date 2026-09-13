# 双色球预测系统 - Code Wiki (V2.0)

> **项目名称**: 双色球预测系统 (Double Color Ball Prediction System)  
> **版本**: V2.0 - TOP 5 算法重构版  
> **语言**: Python 3.10+ (推荐 3.13)  
> **类型**: 桌面应用 (PyQt5 GUI) + 多模型融合预测引擎

---

## 目录

1. [项目概述](#1-项目概述)
2. [项目架构](#2-项目架构)
3. [模块详解](#3-模块详解)
   - 3.1 [预测引擎 V2 (ssq_prediction_v2.py)](#31-预测引擎-v2-ssq_prediction_v2py)
   - 3.2 [图形界面 (ssq_gui.py)](#32-图形界面-ssq_guipy)
   - 3.3 [数据获取 (ssq_data_fetcher.py)](#33-数据获取-ssq_data_fetcherpy)
   - 3.4 [数据库 (ssq_database.py)](#34-数据库-ssq_databasepy)
   - 3.5 [旧版引擎 (ssq_prediction.py)](#35-旧版引擎-ssq_predictionpy)
4. [数据库设计](#4-数据库设计)
5. [TOP 5 核心算法](#5-top-5-核心算法)
6. [依赖与环境](#6-依赖与环境)
7. [项目运行方式](#7-项目运行方式)
8. [数据流图](#8-数据流图)
9. [文件清单](#9-文件清单)
10. [V1 → V2 升级对比](#10-v1--v2-升级对比)

---

## 1. 项目概述

### 1.1 项目背景

本项目是基于统计学、概率论与机器学习的双色球彩票预测系统。V2.0 版本在 V1.0 的基础上全面重构预测引擎，采用**全网最流行的 TOP 5 算法**进行融合预测，并新增深度学习与时序建模能力。

### 1.2 核心功能

| 功能模块 | 描述 |
|---------|------|
| 数据获取 | 从中国福利彩票官网及备用数据源获取实时开奖数据 |
| 数据存储 | SQLite 数据库存储历史开奖、预测历史、频率统计、算法参数 |
| 特征工程 | 233 维多维度特征向量，支持机器学习模型输入 |
| **TOP 5 算法** | LSTM / MCMC / Stacking 融合 / 频率+遗漏+冷热 / XGBoost+随机森林 |
| 递推回测 | 逐年递推训练，动态调整策略权重 |
| 图形界面 | PyQt5 桌面应用，含开奖展示、预测号码、趋势图表、历史查询 |
| 优雅降级 | torch/xgboost/sklearn 缺失时自动降级到可用算法 |

### 1.3 设计原则

- **TOP 5 算法融合**: 集成当前最流行、最精准的 5 类预测算法
- **可选依赖**: 重型依赖(torch/xgboost)缺失时自动降级，保证可运行
- **递推优化**: 逐年回测，根据历史表现动态调整策略权重
- **容错设计**: 主数据源失败时自动切换备用源/缓存/数据库
- **免责声明**: 仅供学术研究，不构成投注建议

---

## 2. 项目架构

### 2.1 整体架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                          用户界面层                              │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              ssq_gui.py (PyQt5)                          │   │
│  │  本期概览 | 预测号码 | 趋势图表 | 往期查询                │   │
│  └───────────┬──────────────────────┬───────────────────────┘   │
│              │                      │                           │
└──────────────┼──────────────────────┼───────────────────────────┘
               │                      │
    ┌──────────▼─────────────┐   ┌────▼──────────────────┐
    │  ssq_prediction_v2.py  │   │ ssq_data_fetcher.py   │
    │   ★ V2 预测引擎 ★      │   │   数据获取模块         │
    │  ───────────────────   │   │  ──────────────────  │
    │  FeatureEngineer       │   │  主API: cwl.gov.cn    │
    │  ① FrequencyMissing    │   │  备用源: 500.com       │
    │  ② MCMC (MH采样)       │   │  本地缓存机制         │
    │  ③ LSTM (PyTorch)      │   └────────┬──────────────┘
    │  ④ XGBoost             │            │
    │  ⑤ RandomForest        │            │
    │  StackingEnsemble      │            │
    │  BacktestEngineV2      │            │
    └──────────┬─────────────┘            │
               │                          │
    ┌──────────▼──────────────────────────▼──────────┐
    │            ssq_database.py (SQLite)            │
    │  lottery_results | frequency_stats             │
    │  prediction_history | algorithm_params         │
    └────────────────────────────────────────────────┘
               ▲
               │ (V2 不可用时降级)
    ┌──────────┴─────────────┐
    │  ssq_prediction.py     │
    │   V1 旧版融合引擎      │
    └────────────────────────┘

    ┌────────────────────────────────────────────────┐
    │  packages/sklearn (内嵌 scikit-learn 1.9.0)   │
    │  随机森林、标准化、交叉验证等算法本地化        │
    └────────────────────────────────────────────────┘
```

### 2.2 模块依赖关系

```
ssq_gui.py
    ├── ssq_prediction_v2.py  ★ V2 主引擎 (优先)
    ├── ssq_prediction.py     ← V1 引擎 (降级回退)
    ├── ssq_data_fetcher.py
    └── ssq_database.py

ssq_prediction_v2.py
    ├── ssq_database.py        (历史数据读取)
    ├── numpy                  (必需)
    ├── scipy.special.softmax  (可选，缺失时用 numpy 实现)
    ├── sklearn                (可选，内嵌于 packages/)
    ├── xgboost                (可选)
    └── torch                  (可选)

ssq_data_fetcher.py
    └── (独立模块，无内部依赖)

ssq_database.py
    └── (独立模块，仅依赖 sqlite3)
```

### 2.3 调用层级

| 层级 | 模块 | 职责 |
|-----|------|------|
| L1 - 表现层 | ssq_gui.py | 用户交互、数据展示、后台线程调度 |
| L2 - 业务层 | **ssq_prediction_v2.py** | TOP 5 算法预测引擎、特征工程、回测优化 |
| L2 - 业务层 | ssq_data_fetcher.py | 网络请求、数据解析、缓存管理 |
| L3 - 数据层 | ssq_database.py | SQLite 数据库操作、数据持久化 |
| L4 - 依赖层 | packages/sklearn | 内嵌 scikit-learn 1.9.0，保证随机森林等算法可用 |

---

## 3. 模块详解

### 3.1 预测引擎 V2 (ssq_prediction_v2.py)

**文件路径**: [ssq_prediction_v2.py](file:///d:/pythonfiles/ssq/ssq_prediction_v2.py)

#### 3.1.1 模块概述

V2 核心模块，基于**当前最流行的 TOP 5 算法**重新设计。架构为：

```
FeatureEngineer → 5 Strategies → StackingEnsemble → BacktestEngine → Report
```

#### 3.1.2 常量配置

| 常量 | 值 | 说明 |
|-----|----|------|
| `RED_RANGE` | `[1..33]` | 红球范围 |
| `BLUE_RANGE` | `[1..16]` | 蓝球范围 |
| `TOP_N` | `25` | 输出预测组数 (5算法 × 5组) |
| `PER_STRATEGY` | `5` | 每种算法生成组数 |
| `SEQ_LEN` | `50` | LSTM 序列长度 |
| `N_SPLITS` | `5` | 交叉验证折数 |

#### 3.1.3 可选依赖探测

通过 `try/except` 探测重型依赖，设置 `HAS_XXX` 标志：

| 标志 | 依赖 | 缺失时行为 |
|-----|------|----------|
| `HAS_SCIPY` | `scipy.special.softmax` | 使用 numpy 自实现 `_softmax` |
| `HAS_SKLEARN` | `sklearn.ensemble.*` | 跳过随机森林策略 |
| `HAS_XGBOOST` | `xgboost` | 跳过 XGBoost 策略 |
| `HAS_TORCH` | `torch` | 跳过 LSTM 策略 |

> 💡 softmax 函数有优雅降级实现：[ssq_prediction_v2.py#L53-L59](file:///d:/pythonfiles/ssq/ssq_prediction_v2.py#L53-L59)

#### 3.1.4 数据类

##### `LotteryDraw`
- **位置**: [ssq_prediction_v2.py#L90-L99](file:///d:/pythonfiles/ssq/ssq_prediction_v2.py#L90-L99)
- **字段**: `issue`, `date`, `reds` (自动排序), `blue`, `year`

##### `Prediction`
- **位置**: [ssq_prediction_v2.py#L102-L111](file:///d:/pythonfiles/ssq/ssq_prediction_v2.py#L102-L111)
- **字段**: `reds`, `blue`, `score`, `strategy`, `confidence` (置信度)

#### 3.1.5 FeatureEngineer 类

**位置**: [ssq_prediction_v2.py#L118-L312](file:///d:/pythonfiles/ssq/ssq_prediction_v2.py#L118-L312)

多维度特征提取器，既作为统计分析器使用，又为机器学习模型构建特征。

| 方法 | 位置 | 功能说明 |
|-----|------|---------|
| `__init__(history)` | [L121-L123](file:///d:/pythonfiles/ssq/ssq_prediction_v2.py#L121-L123) | 初始化并自动计算所有统计量 |
| `_compute()` | [L125-L176](file:///d:/pythonfiles/ssq/ssq_prediction_v2.py#L125-L176) | 计算频率、和值、跨度、奇偶比、区间分布、连号概率、AC值 |
| `recent_window(window=30)` | [L178-L191](file:///d:/pythonfiles/ssq/ssq_prediction_v2.py#L178-L191) | 近N期窗口统计 |
| `missing_analysis()` | [L193-L207](file:///d:/pythonfiles/ssq/ssq_prediction_v2.py#L193-L207) | 遗漏分析（红/蓝） |
| `hot_cold(window=30)` | [L209-L223](file:///d:/pythonfiles/ssq/ssq_prediction_v2.py#L209-L223) | 冷热号分类（hot/cold/warm，阈值 1.5x / 0.5x） |
| `transition_matrix()` | [L225-L234](file:///d:/pythonfiles/ssq/ssq_prediction_v2.py#L225-L234) | 马尔可夫转移矩阵 |
| **`build_features(draw_index)`** | [L236-L312](file:///d:/pythonfiles/ssq/ssq_prediction_v2.py#L236-L312) | **构建233维ML特征向量** |

**233维特征向量构成**:

```
[ recent_red_freq(33) | recent_blue_freq(16) |   # 49维 - 近期频率
  red_missing(33)     | blue_missing(16)      |   # 49维 - 遗漏值
  global_red_freq(33) | global_blue_freq(16)  |   # 49维 - 全局频率
  last_red(33)        | last_blue(16)         |   # 49维 - 上期one-hot
  trans_red(33)       | trans_blue(16)         |   # 49维 - 转移概率
  odd_ratio(1)        | zone_dist(3) ]            #  4维 - 结构特征
                                              总计 = 233维
```

#### 3.1.6 策略基类 BaseStrategy

**位置**: [ssq_prediction_v2.py#L319-L345](file:///d:/pythonfiles/ssq/ssq_prediction_v2.py#L319-L345)

| 方法 | 功能 |
|-----|------|
| `predict(analyzer, n)` | 抽象方法，子类实现 |
| `evaluate(actual_reds, actual_blue, pred)` | 评分: 红球命中/6×0.85 + 蓝球命中×0.15 |
| `_sample(weights, k)` | 加权不放回抽样 |

#### 3.1.7 TOP 5 策略详解

##### 🥇 策略1: FrequencyMissingStrategy（频率+遗漏+冷热号三合一）

- **位置**: [ssq_prediction_v2.py#L352-L408](file:///d:/pythonfiles/ssq/ssq_prediction_v2.py#L352-L408)
- **策略名**: `frequency_missing`
- **核心思想**: 综合频率、遗漏、冷热号、趋势变化四因素
- **权重计算**:
  ```
  w = 1.0 + 全局频率×3 + 遗漏值×0.05
  w × (热号1.5 / 冷号0.4 / 温号1.0)
  w × (0.8 + 0.4 × 近期频率/全局频率)
  ```
- **约束**: 和值/跨度需在 3σ 范围内，否则重新采样（最多500次）

##### 🥈 策略2: MCMCStrategy（马尔可夫链蒙特卡洛）

- **位置**: [ssq_prediction_v2.py#L415-L491](file:///d:/pythonfiles/ssq/ssq_prediction_v2.py#L415-L491)
- **策略名**: `mcmc`
- **核心思想**: Metropolis-Hastings 采样，从复杂概率分布中抽样
- **参数**:
  - `iterations=10000` - 总迭代次数
  - `burn_in=2000` - 预烧期（丢弃）
- **目标分布**: 综合号码频率、遗漏值、和值正态分布、跨度正态分布
- **提议分布**: 每次随机替换1-2个号码
- **采样流程**: MCMC采样 → 丢弃预烧期 → 统计高频组合 → 按频率排序选号

##### 🥉 策略3: LSTMStrategy（LSTM 深度学习）

- **位置**: [ssq_prediction_v2.py#L504-L625](file:///d:/pythonfiles/ssq/ssq_prediction_v2.py#L504-L625)
- **策略名**: `lstm`
- **核心思想**: 长短期记忆网络捕捉时序依赖关系
- **依赖**: `torch` (可选)
- **网络结构** (`LSTMPredictor`): [L506-L520](file:///d:/pythonfiles/ssq/ssq_prediction_v2.py#L506-L520)
  - 输入维度: 49 (33红 + 16蓝 one-hot)
  - LSTM: 2层，hidden_dim=128，dropout=0.2
  - 红球输出头: Linear(128→64→33) + ReLU + Dropout
  - 蓝球输出头: Linear(128→32→16) + ReLU + Dropout
- **训练参数**: seq_len=50, epochs=100, batch_size=16, Adam(lr=0.001), BCEWithLogitsLoss
- **预测流程**: 取最近50期 → 模型前向 → sigmoid → softmax温度采样 → 多样化生成n组
- **降级**: torch缺失或数据不足时回退到 MCMCStrategy

##### 🏅 策略4: XGBoostStrategy（XGBoost 梯度提升树）

- **位置**: [ssq_prediction_v2.py#L632-L715](file:///d:/pythonfiles/ssq/ssq_prediction_v2.py#L632-L715)
- **策略名**: `xgboost`
- **核心思想**: 为33个红球各训练一个二分类器，蓝球训练多分类器
- **依赖**: `xgboost`, `sklearn`
- **特征**: FeatureEngineer.build_features() 生成的233维向量
- **模型参数**:
  - 红球: 33个 XGBClassifier (n_estimators=100, max_depth=4, lr=0.05, scale_pos_weight)
  - 蓝球: 1个 XGBClassifier (multi:softprob, num_class=16)
- **特殊处理**: 类别不完整时自动补齐缺失类别的样本
- **降级**: 依赖缺失时回退到 FrequencyMissingStrategy

##### 🏅 策略5: RandomForestStrategy（随机森林集成）

- **位置**: [ssq_prediction_v2.py#L722-L801](file:///d:/pythonfiles/ssq/ssq_prediction_v2.py#L722-L801)
- **策略名**: `random_forest`
- **核心思想**: 与XGBoost类似的建模思路，使用随机森林算法
- **依赖**: `sklearn`
- **模型参数**: 200棵树，max_depth=6，class_weight='balanced'
- **降级**: sklearn缺失时回退到 FrequencyMissingStrategy

#### 3.1.8 StackingEnsemble 类

**位置**: [ssq_prediction_v2.py#L808-L874](file:///d:/pythonfiles/ssq/ssq_prediction_v2.py#L808-L874)

Stacking 元学习器融合引擎。

**核心方法**:

| 方法 | 位置 | 功能 |
|-----|------|------|
| `__init__(strategies)` | [L811-L812](file:///d:/pythonfiles/ssq/ssq_prediction_v2.py#L811-L812) | 初始化策略列表 |
| `predict(analyzer, n=25)` | [L814-L840](file:///d:/pythonfiles/ssq/ssq_prediction_v2.py#L814-L840) | 融合生成n组预测 |
| `_get_weight(name)` | [L842-L847](file:///d:/pythonfiles/ssq/ssq_prediction_v2.py#L842-L847) | 查找策略权重 |
| `_diversify(n, red_scores, blue_scores, analyzer)` | [L849-L874](file:///d:/pythonfiles/ssq/ssq_prediction_v2.py#L849-L874) | 多样化生成（温度参数 0.3+i×0.08） |

**融合算法流程**:
1. 每个策略按权重生成 PER_STRATEGY(5) 组候选
2. 汇总所有候选，号码得分按 `策略权重 × 置信度` 累加
3. 使用温度参数 softmax 生成 25 组不同号码
4. 和值/跨度约束过滤（3σ范围）

#### 3.1.9 BacktestEngineV2 类

**位置**: [ssq_prediction_v2.py#L881-L993](file:///d:/pythonfiles/ssq/ssq_prediction_v2.py#L881-L993)

递推回测引擎，用于优化策略权重。

| 方法 | 位置 | 功能 |
|-----|------|------|
| `__init__(history)` | [L884-L890](file:///d:/pythonfiles/ssq/ssq_prediction_v2.py#L884-L890) | 初始化，将字典转为 LotteryDraw |
| `run(sample_every=10)` | [L892-L955](file:///d:/pythonfiles/ssq/ssq_prediction_v2.py#L892-L955) | 执行递推回测 |
| `_make_strategies(fast_mode=True)` | [L957-L974](file:///d:/pythonfiles/ssq/ssq_prediction_v2.py#L957-L974) | 创建策略实例 |
| `_update_weights(strategies, avg_scores)` | [L976-L982](file:///d:/pythonfiles/ssq/ssq_prediction_v2.py#L976-L982) | EMA更新权重 + 归一化 |
| `_simple(analyzer)` | [L984-L993](file:///d:/pythonfiles/ssq/ssq_prediction_v2.py#L984-L993) | 数据不足时的简化回测 |

**回测流程**:
```
年份2020数据 → 预测2021 → 调整权重
年份2020-2021数据 → 预测2022 → 调整权重
...
年份2020~2025数据 → 预测2026 → 最终权重 → 最终预测25组
```

**fast_mode 优化**:
- 回测过程中只用快速策略（frequency + mcmc），避免每次都训练LSTM/XGBoost
- 最终预测时启用所有可用策略

**返回数据结构**:
```python
{
    'yearly_performance': {年份: {strategy_perf, total_issues}},
    'weights_history': {年份: {策略名: 权重}},
    'final_predictions': [Prediction × 25],  # 最终25组预测
    'final_weights': {策略名: 权重},
    'analyzer': FeatureEngineer实例
}
```

#### 3.1.10 其他函数

| 函数 | 位置 | 功能 |
|-----|------|------|
| `generate_report_v2(result)` | [L1000-L1060](file:///d:/pythonfiles/ssq/ssq_prediction_v2.py#L1000-L1060) | 生成完整预测报告（5大板块） |
| `save_to_database_v2(result, db_path)` | [L1067-L1089](file:///d:/pythonfiles/ssq/ssq_prediction_v2.py#L1067-L1089) | 保存25组预测到数据库 |
| `update_after_draw_v2(issue, reds, blue, db_path)` | [L1092-L1130](file:///d:/pythonfiles/ssq/ssq_prediction_v2.py#L1092-L1130) | 开奖后更新预测命中率 |
| `main()` | [L1137-L1184](file:///d:/pythonfiles/ssq/ssq_prediction_v2.py#L1137-L1184) | 命令行入口 |

---

### 3.2 图形界面 (ssq_gui.py)

**文件路径**: [ssq_gui.py](file:///d:/pythonfiles/ssq/ssq_gui.py)

#### 3.2.1 V2 引擎集成

GUI 同时支持 V1 和 V2 引擎，优先使用 V2：

```python
# 导入 V2 引擎 (TOP 5 算法)
try:
    from ssq_prediction_v2 import (
        BacktestEngineV2, FeatureEngineer, StackingEnsemble,
        FrequencyMissingStrategy, MCMCStrategy,
        LSTMStrategy, XGBoostStrategy, RandomForestStrategy,
    )
    HAS_V2_ENGINE = True
except ImportError:
    HAS_V2_ENGINE = False
```

**代码位置**: [ssq_gui.py#L55-L64](file:///d:/pythonfiles/ssq/ssq_gui.py#L55-L64)

#### 3.2.2 PredictionThread 双引擎支持

**位置**: [ssq_gui.py#L385-L440](file:///d:/pythonfiles/ssq/ssq_gui.py#L385-L440)

| 方法 | 位置 | 功能 |
|-----|------|------|
| `__init__(parent, use_v2=True)` | [L390-L392](file:///d:/pythonfiles/ssq/ssq_gui.py#L390-L392) | 初始化，默认启用V2 |
| `_run_v2(all_results)` | [L411-L425](file:///d:/pythonfiles/ssq/ssq_gui.py#L411-L425) | **使用 TOP 5 算法 V2 引擎** |
| `_run_v1(all_results)` | [L427-L440](file:///d:/pythonfiles/ssq/ssq_gui.py#L427-L440) | V1 引擎回退 |
| `_random_predictions()` | [L442+](file:///d:/pythonfiles/ssq/ssq_gui.py#L442) | 随机预测（最终兜底） |

#### 3.2.3 UI 组件结构

```
MainWindow (主窗口)
├── 顶部标题栏 (标题 + 刷新按钮)
├── 本期开奖信息面板
│   ├── 左侧: 期号 + 日期
│   ├── 中间: 开奖号码球 (BallsDisplayWidget)
│   └── 右侧: 奖池 + 销售额 + 一等奖分布
├── Tab 页区域 (QTabWidget)
│   ├── Tab1: 本期概览 (奖级明细 + 地区分布)
│   ├── Tab2: 预测号码 (25组预测表格)
│   ├── Tab3: 趋势图表 (红球/蓝球累积概率图)
│   └── Tab4: 往期查询 (期号/年份查询)
└── 状态栏
```

#### 3.2.4 自定义控件

| 类名 | 位置 | 功能 |
|-----|------|------|
| `BallWidget` | [ssq_gui.py#L211-L269](file:///d:/pythonfiles/ssq/ssq_gui.py#L211-L269) | 单个号码球（径向渐变3D效果） |
| `BallsDisplayWidget` | [ssq_gui.py#L272-L299](file:///d:/pythonfiles/ssq/ssq_gui.py#L272-L299) | 6红球+1蓝球横向排列 |
| `MiniBallWidget` | [ssq_gui.py#L302-L337](file:///d:/pythonfiles/ssq/ssq_gui.py#L302-L337) | 小号球（表格内使用） |
| `TrendChartCanvas` | [ssq_gui.py#L426-L490](file:///d:/pythonfiles/ssq/ssq_gui.py#L426-L490) | 红球累积概率趋势图 |
| `BlueChartCanvas` | [ssq_gui.py#L493-L550](file:///d:/pythonfiles/ssq/ssq_gui.py#L493-L550) | 蓝球累积概率趋势图 |

---

### 3.3 数据获取 (ssq_data_fetcher.py)

**文件路径**: [ssq_data_fetcher.py](file:///d:/pythonfiles/ssq/ssq_data_fetcher.py)

#### 3.3.1 模块概述

负责从中国福利彩票官网及备用数据源获取双色球开奖数据，支持缓存机制、SSL容错、重试机制。

#### 3.3.2 核心常量

| 常量 | 值 | 说明 |
|-----|----|------|
| `CWL_API_URL` | `https://www.cwl.gov.cn/.../findDrawNotice` | 主数据源API |
| `BACKUP_URL` | `https://datachart.500.com/ssq/history/...` | 备用数据源 |
| `REQUEST_TIMEOUT` | `15` | 请求超时(秒) |
| `MAX_RETRIES` | `3` | 最大重试次数 |
| `CACHE_FILE` | `ssq_latest_cache.json` | 缓存文件路径 |

#### 3.3.3 核心函数

| 函数 | 位置 | 功能 |
|-----|------|------|
| `fetch_latest_draw()` | [L162-L177](file:///d:/pythonfiles/ssq/ssq_data_fetcher.py#L162-L177) | 获取最新一期开奖数据 |
| `fetch_recent_draws(count=30)` | [L153-L159](file:///d:/pythonfiles/ssq/ssq_data_fetcher.py#L153-L159) | 获取最近N期开奖数据 |
| `fetch_draw_by_issue(issue)` | [L180-L194](file:///d:/pythonfiles/ssq/ssq_data_fetcher.py#L180-L194) | 按期号查询 |
| `fetch_draws_by_date_range(start, end)` | [L197-L208](file:///d:/pythonfiles/ssq/ssq_data_fetcher.py#L197-L208) | 按日期范围查询 |
| `_api_request(params)` | [L76-L107](file:///d:/pythonfiles/ssq/ssq_data_fetcher.py#L76-L107) | API请求封装（重试+SSL降级） |
| `_fetch_from_backup()` | [L110-L150](file:///d:/pythonfiles/ssq/ssq_data_fetcher.py#L110-L150) | 从500.com备用源获取数据 |
| `_parse_draw(item)` | [L245-L300](file:///d:/pythonfiles/ssq/ssq_data_fetcher.py#L245-L300) | 原始数据解析为标准格式 |
| `load_cached_latest()` | [L214-L229](file:///d:/pythonfiles/ssq/ssq_data_fetcher.py#L214-L229) | 从缓存加载（24小时过期） |
| `format_money(amount)` | [L324-L338](file:///d:/pythonfiles/ssq/ssq_data_fetcher.py#L324-L338) | 金额格式化（元/万元/亿元） |

---

### 3.4 数据库 (ssq_database.py)

**文件路径**: [ssq_database.py](file:///d:/pythonfiles/ssq/ssq_database.py)

#### 3.4.1 核心函数

| 函数 | 位置 | 功能 |
|-----|------|------|
| `get_connection()` | [L12-L16](file:///d:/pythonfiles/ssq/ssq_database.py#L12-L16) | 获取数据库连接 |
| `create_database()` | [L19-L83](file:///d:/pythonfiles/ssq/ssq_database.py#L19-L83) | 创建所有表（幂等） |
| `import_from_json(json_path)` | [L86-L124](file:///d:/pythonfiles/ssq/ssq_database.py#L86-L124) | 从JSON导入历史数据 |
| `get_all_results(years=None)` | [L127-L141](file:///d:/pythonfiles/ssq/ssq_database.py#L127-L141) | 获取历史开奖（升序） |
| `get_results_before_issue(issue, limit=200)` | [L144-L154](file:///d:/pythonfiles/ssq/ssq_database.py#L144-L154) | 获取指定期号前数据（回测用） |
| `get_latest_issue()` | [L157-L164](file:///d:/pythonfiles/ssq/ssq_database.py#L157-L164) | 获取最新一期 |
| `get_statistics()` | [L167-L179](file:///d:/pythonfiles/ssq/ssq_database.py#L167-L179) | 数据库概览统计 |

---

### 3.5 旧版引擎 (ssq_prediction.py)

**文件路径**: [ssq_prediction.py](file:///d:/pythonfiles/ssq/ssq_prediction.py)

#### 3.5.1 定位

V1 旧版预测引擎，作为 V2 不可用时的降级方案保留。包含：

| 类 | 位置 | 功能 |
|---|------|------|
| `StatisticalAnalyzer` | [L62-L176](file:///d:/pythonfiles/ssq/ssq_prediction.py#L62-L176) | 统计分析器 |
| `FrequencyStrategy` | [L214-L239](file:///d:/pythonfiles/ssq/ssq_prediction.py#L214-L239) | 频率策略 |
| `MissingStrategy` | [L242-L259](file:///d:/pythonfiles/ssq/ssq_prediction.py#L242-L259) | 遗漏策略 |
| `MarkovStrategy` | [L262-L288](file:///d:/pythonfiles/ssq/ssq_prediction.py#L262-L288) | 马尔可夫策略 |
| `ZoneBalanceStrategy` | [L291-L309](file:///d:/pythonfiles/ssq/ssq_prediction.py#L291-L309) | 区间均衡策略 |
| `MonteCarloStrategy` | [L312-L359](file:///d:/pythonfiles/ssq/ssq_prediction.py#L312-L359) | 蒙特卡洛策略 |
| `TrendStrategy` | [L362-L386](file:///d:/pythonfiles/ssq/ssq_prediction.py#L362-L386) | 趋势策略 |
| `FusionPredictor` | [L392-L527](file:///d:/pythonfiles/ssq/ssq_prediction.py#L392-L527) | 融合预测器 |
| `BacktestEngine` | [L533-L639](file:///d:/pythonfiles/ssq/ssq_prediction.py#L533-L639) | 递推回测引擎 |

---

## 4. 数据库设计

### 4.1 数据库文件

- **文件**: `ssq_lottery.db` (SQLite)
- **路径**: 项目根目录

### 4.2 表结构

#### 4.2.1 lottery_results (开奖结果表)

| 字段 | 类型 | 约束 | 说明 |
|-----|------|------|------|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | 自增主键 |
| `issue_number` | VARCHAR(20) | NOT NULL UNIQUE | 期号 |
| `draw_date` | DATE | NOT NULL | 开奖日期 |
| `red_1` ~ `red_6` | INTEGER | NOT NULL | 6个红球 |
| `blue` | INTEGER | NOT NULL | 蓝球 |
| `year` | INTEGER | NOT NULL | 年份 |
| `created_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | 创建时间 |

#### 4.2.2 frequency_stats (频率统计表)

| 字段 | 类型 | 说明 |
|-----|------|------|
| `id` | INTEGER | 自增主键 |
| `year` | INTEGER | 年份 |
| `number_type` | VARCHAR(10) | 号码类型 (red/blue) |
| `number` | INTEGER | 号码 |
| `count` | INTEGER | 出现次数 |
| `frequency` | REAL | 频率 |
| `last_appeared_issue` | VARCHAR(20) | 最近出现期号 |
| `missing_count` | INTEGER | 遗漏期数 |
| `hot_cold_score` | REAL | 冷热评分 |

#### 4.2.3 prediction_history (预测历史表)

| 字段 | 类型 | 说明 |
|-----|------|------|
| `id` | INTEGER | 自增主键 |
| `target_issue` | VARCHAR(20) | 目标期号 |
| `prediction_date` | TIMESTAMP | 预测时间 |
| `predicted_reds` | VARCHAR(50) | 预测红球(逗号分隔) |
| `predicted_blue` | INTEGER | 预测蓝球 |
| `actual_reds` | VARCHAR(50) | 实际红球 |
| `actual_blue` | INTEGER | 实际蓝球 |
| `red_match_count` | INTEGER | 红球命中数 |
| `blue_match` | INTEGER | 蓝球是否命中 |
| `algorithm_version` | VARCHAR(20) | 算法版本（V2 用 `v2-YYYYMMDD`） |
| `score` | REAL | 综合得分 |

#### 4.2.4 algorithm_params (算法参数表)

| 字段 | 类型 | 说明 |
|-----|------|------|
| `id` | INTEGER | 自增主键 |
| `version` | VARCHAR(20) | 版本号 |
| `param_name` | VARCHAR(50) | 参数名 |
| `param_value` | REAL | 参数值 |
| `performance_score` | REAL | 性能评分 |

---

## 5. TOP 5 核心算法

### 5.1 算法全景图

```
                ┌──────────────────────────────┐
                │      StackingEnsemble         │
                │   (元学习器加权融合)          │
                └──────────────┬───────────────┘
                               │
       ┌───────────┬───────────┼───────────┬───────────┐
       │           │           │           │           │
   ┌───▼───┐   ┌───▼───┐   ┌───▼───┐   ┌───▼───┐   ┌───▼───┐
   │  ①   │   │  ②   │   │  ③   │   │  ④   │   │  ⑤   │
   │ 频率  │   │ MCMC │   │ LSTM │   │XGBoost│   │ 随机  │
   │ 遗漏  │   │      │   │      │   │      │   │ 森林  │
   │ 冷热  │   │      │   │      │   │      │   │      │
   └───────┘   └──────┘   └──────┘   └──────┘   └──────┘
```

### 5.2 算法对比

| 排名 | 算法 | 策略名 | 类型 | 依赖 | 复杂度 |
|-----|------|-------|------|-----|-------|
| 🥇 1 | **LSTM 神经网络** | `lstm` | 深度学习 | torch | O(n·epochs·seq_len) |
| 🥈 2 | **MCMC** | `mcmc` | 概率推断 | numpy | O(iterations) |
| 🥉 3 | **Stacking 融合** | `stacking` | 元学习 | - | O(Σ策略) |
| 🏅 4 | **频率+遗漏+冷热** | `frequency_missing` | 统计 | numpy | O(1) |
| 🏅 5 | **XGBoost+随机森林** | `xgboost`/`random_forest` | 树模型 | xgboost/sklearn | O(n·log n) |

### 5.3 融合算法流程

```
输入: 历史开奖数据
  │
  ├─→ 策略1: 频率+遗漏+冷热 ──→ 5组候选 ──┐
  ├─→ 策略2: MCMC采样       ──→ 5组候选 ──┤
  ├─→ 策略3: LSTM预测       ──→ 5组候选 ──┤
  ├─→ 策略4: XGBoost预测    ──→ 5组候选 ──┼→ StackingEnsemble
  └─→ 策略5: 随机森林预测    ──→ 5组候选 ──┘    │
                                                 ▼
                                    号码综合得分汇总
                                    (各策略加权 × 置信度)
                                                 │
                                                 ▼
                                    多样化生成25组号码
                                    (温度参数 0.3+i×0.08)
                                                 │
                                                 ▼
                                    约束过滤 (和值/跨度 3σ)
                                                 │
                                                 ▼
输出: 25组预测号码 + 评分 + 策略来源
```

### 5.4 递推回测优化

```
初始权重: 各策略均为 1.0
  │
  ├─ 2020数据 → 预测2021 → 对比实际 → EMA更新权重
  ├─ 2020-2021数据 → 预测2022 → 更新权重
  ├─ ...
  └─ 2020~2025数据 → 预测2026 → 最终权重
                            │
                            ▼
                    应用于最终 StackingEnsemble
```

**权重更新公式** (EMA 平滑):
```python
new_weight = max(old_weight * 0.7 + avg_score * 8 * 0.3, 0.05)
# 然后归一化
weights = {n: w / total for n, w in weights.items()}
```

**fast_mode 优化**: 回测过程只用 frequency + mcmc（避免每次训练 LSTM/XGBoost），最终预测时启用全部策略。

### 5.5 评分机制

**单组预测评分** (BaseStrategy.evaluate):
```
score = (红球命中数 / 6) × 0.85 + (蓝球是否命中) × 0.15
```

**LSTM/XGBoost/随机森林 评分**:
```python
score = red_probs[选中红球].sum() / 6 × 85 + blue_probs[选中蓝球] × 15
```

---

## 6. 依赖与环境

### 6.1 Python 版本

- Python 3.10+ (推荐 3.13)

### 6.2 依赖分级

#### 必需依赖

| 库名 | 用途 | 安装命令 |
|-----|------|---------|
| `numpy` | 数值计算 | `pip install numpy` |
| `requests` | HTTP网络请求 | `pip install requests` |
| `beautifulsoup4` | HTML解析（备用源） | `pip install beautifulsoup4` |
| `PyQt5` | 图形界面框架 | `pip install PyQt5` |
| `matplotlib` | 图表绘制 | `pip install matplotlib` |

#### 可选依赖（V2 算法）

| 库名 | 用途 | 启用算法 | 安装命令 |
|-----|------|---------|---------|
| `scipy` | softmax函数 | (优化) | `pip install scipy` |
| `scikit-learn` | 随机森林 | 随机森林策略 | `pip install scikit-learn` |
| `xgboost` | 梯度提升树 | XGBoost策略 | `pip install xgboost` |
| `torch` | 深度学习框架 | LSTM策略 | `pip install torch` |

> 💡 **项目已内嵌 scikit-learn 1.9.0** 于 `packages/sklearn`，但需要正确配置 Python 路径或安装到 site-packages。

#### 标准库依赖

`sqlite3`, `json`, `re`, `os`, `sys`, `time`, `datetime`, `random`, `math`, `collections`, `typing`, `dataclasses`, `itertools`, `ssl`, `urllib3`

### 6.3 依赖降级机制

V2 引擎通过 `HAS_XXX` 标志实现优雅降级：

```python
# 示例：LSTM 策略降级
def predict(self, analyzer, n=1):
    if not HAS_TORCH:
        return MCMCStrategy(iterations=3000).predict(analyzer, n)
    # ... 正常 LSTM 预测
```

| 缺失依赖 | 影响策略 | 降级方案 |
|---------|---------|---------|
| `scipy` | softmax计算 | 使用 numpy 自实现 |
| `sklearn` | 随机森林 | 跳过该策略 |
| `xgboost` | XGBoost | 跳过该策略 |
| `torch` | LSTM | 回退到 MCMC |
| `ssq_prediction_v2` 全部失败 | V2 引擎 | 回退到 V1 引擎 |

---

## 7. 项目运行方式

### 7.1 环境准备

#### 最小安装（基础功能）

```bash
pip install numpy requests beautifulsoup4 PyQt5 matplotlib
```

#### 完整安装（启用 TOP 5 算法）

```bash
pip install numpy requests beautifulsoup4 PyQt5 matplotlib
pip install scipy scikit-learn xgboost
pip install torch  # 或 torch+cuda 版本
```

### 7.2 启动图形界面

```bash
cd d:\pythonfiles\ssq
python ssq_gui.py
```

**启动流程**:
1. 创建/连接 SQLite 数据库
2. 若数据不足，从 `ssq_history.json` 导入历史数据
3. 后台获取最新开奖数据（网络→缓存→本地数据库降级）
4. **后台调用 V2 引擎生成 25 组预测号码**（如可用）
5. 显示主窗口

### 7.3 命令行运行 V2 引擎

```bash
# 完整预测（递推回测 + TOP 5 算法 + 生成报告）
python ssq_prediction_v2.py

# 开奖后更新模型
python ssq_prediction_v2.py <期号> <红球逗号分隔> <蓝球>
# 示例:
python ssq_prediction_v2.py 2026082 01,05,12,18,25,30 08
```

### 7.4 测试其他模块

```bash
# 测试数据获取
python ssq_data_fetcher.py

# 初始化数据库
python ssq_database.py

# 运行 V1 旧版引擎
python ssq_prediction.py
```

---

## 8. 数据流图

### 8.1 预测数据流（V2）

```
SQLite (lottery_results)
        │
        ▼
FeatureEngineer (233维特征 + 统计分析)
        │
        ├─→ FrequencyMissingStrategy ─→ 5组候选 ──┐
        ├─→ MCMCStrategy            ─→ 5组候选 ──┤
        ├─→ LSTMStrategy            ─→ 5组候选 ──┤
        ├─→ XGBoostStrategy         ─→ 5组候选 ──┼→ StackingEnsemble
        └─→ RandomForestStrategy    ─→ 5组候选 ──┘    │
                                                       ▼
                                            号码加权得分汇总
                                                  │
                                                  ▼
                                            多样化生成25组
                                                  │
                                                  ▼
                                            约束过滤 (3σ)
                                                  │
                                                  ▼
                                       prediction_history
                                       (存入数据库, version=v2-YYYYMMDD)
```

### 8.2 GUI 数据流

```
用户操作 (刷新/查询)
        │
        ▼
后台线程 PredictionThread
        │
        ├─→ 优先: BacktestEngineV2 (TOP 5 算法)
        │         └→ result['final_predictions'] (25组)
        │
        └─→ 降级: FusionPredictor (V1 引擎)
                  └→ predict() (10组)
        │
        ▼
信号回调 → UI 更新 (表格/图表/号码球)
```

### 8.3 回测优化数据流

```
BacktestEngineV2.run()
        │
        ├─ 对每一年:
        │   ├─ train_data = 历史到train_year
        │   ├─ test_data = train_year+1
        │   ├─ strategies = [FrequencyMissing, MCMC]  (fast_mode)
        │   ├─ 对 test_data 每10期采样:
        │   │   └─ 各策略预测 → evaluate → 记录得分
        │   └─ _update_weights() → EMA + 归一化
        │
        └─ 最终预测:
            ├─ strategies = [全部5种]  (非fast_mode)
            ├─ 应用最终权重
            └─ StackingEnsemble.predict(n=25)
```

---

## 9. 文件清单

| 文件名 | 类型 | 说明 |
|-------|------|------|
| **`ssq_prediction_v2.py`** | Python源码 | **★ V2 核心预测引擎 (TOP 5 算法)** |
| `ssq_gui.py` | Python源码 | 图形界面主程序 (集成 V1/V2 双引擎) |
| `ssq_data_fetcher.py` | Python源码 | 数据获取模块 |
| `ssq_database.py` | Python源码 | 数据库操作模块 |
| `ssq_prediction.py` | Python源码 | V1 旧版预测引擎 (降级备份) |
| `ssq_lottery.db` | SQLite数据库 | 开奖数据/预测历史/统计数据 |
| `ssq_history.json` | JSON | 历史开奖数据（初始导入用） |
| `ssq_latest_cache.json` | JSON | 最新开奖数据缓存（24小时过期） |
| `CODE_WIKI.md` | Markdown | 本 Code Wiki 文档 |
| `提示词.txt` | 文本 | 项目需求提示词 |
| `1.txt` | 文本 | 运行日志/错误记录 |
| `__pycache__/` | 目录 | Python字节码缓存 |
| **`packages/sklearn/`** | 目录 | **内嵌 scikit-learn 1.9.0** |

---

## 10. V1 → V2 升级对比

### 10.1 核心变化

| 维度 | V1 (ssq_prediction.py) | V2 (ssq_prediction_v2.py) |
|-----|------------------------|---------------------------|
| **算法数量** | 6种策略 | **5种顶级策略** |
| **算法类型** | 统计+概率 | 统计+概率+**深度学习+树模型** |
| **深度学习** | ❌ 无 | ✅ **LSTM 神经网络** |
| **梯度提升树** | ❌ 无 | ✅ **XGBoost** |
| **集成学习** | ❌ 无 | ✅ **随机森林** |
| **融合方式** | 加权融合 | **Stacking 元学习器** |
| **特征工程** | 统计量 | **233维 ML 特征向量** |
| **预测数量** | 10组 | **25组** (5算法×5组) |
| **降级机制** | 随机 | **逐策略降级** |
| **依赖处理** | 必需依赖 | **可选依赖 + 自动降级** |

### 10.2 算法对照

| V1 策略 | V2 对应 | 变化 |
|---------|---------|------|
| FrequencyStrategy | FrequencyMissingStrategy | **合并遗漏+冷热+趋势** |
| MissingStrategy | (合并到上述) | 整合 |
| MarkovStrategy | MCMCStrategy | **升级为 MCMC MH 采样** |
| MonteCarloStrategy | (被MCMC替代) | 升级 |
| ZoneBalanceStrategy | (移除) | - |
| TrendStrategy | (整合到频率策略) | 整合 |
| - | **LSTMStrategy** | **★ 新增** |
| - | **XGBoostStrategy** | **★ 新增** |
| - | **RandomForestStrategy** | **★ 新增** |

### 10.3 架构改进

| 方面 | V1 | V2 |
|-----|----|----|
| 特征工程 | StatisticalAnalyzer (仅统计) | FeatureEngineer (统计+**ML特征**) |
| 融合引擎 | FusionPredictor | **StackingEnsemble** |
| 回测引擎 | BacktestEngine | **BacktestEngineV2** (含 fast_mode 优化) |
| 报告生成 | generate_report | **generate_report_v2** (5大板块) |
| 数据库版本 | `v1-YYYYMMDD` | `v2-YYYYMMDD` |

---

## 附录：已知问题与注意事项

1. **网络环境**: 中国部分网络环境下访问 cwl.gov.cn 可能存在SSL证书问题，代码已做 SSL 降级处理
2. **PyTorch 安装**: Windows 下安装 torch 可能较大（2GB+），可根据需求选择 CPU/CUDA 版本
3. **数据时效**: 备用数据源(500.com)仅提供基本号码，不包含奖级明细和销售额
4. **随机性**: 彩票本质为随机事件，预测仅供学术研究参考
5. **sklearn 内嵌**: `packages/sklearn` 已内嵌但需要正确配置 sys.path 或安装到 site-packages 才能被 import
6. **fast_mode 优化**: 回测过程跳过重型模型训练（LSTM/XGBoost），仅最终预测时启用，大幅减少回测时间
7. **GUI 字体**: `BallWidget` 中 QFont 的 `pointSize` 参数需为 int 类型

---

*文档版本: V2.0  
生成时间: 2026-07-19  
基于源码: ssq_prediction_v2.py | ssq_gui_v2.py*

---

## 附录C: V3 GUI 预测员竞技场

### 五个预测员

| 算法 | 昵称 | Emoji | 标语 | 颜色 |
|------|------|-------|------|------|
| 频率+遗漏+冷热号 | 老江湖 | 🎯 | 二十年彩民经验 | #DC143C |
| MCMC | 概率大师 | 📐 | 数学不会骗人 | #8B5CF6 |
| LSTM | 深脑 | 🧠 | 深度学习洞察规律 | #06B6D4 |
| XGBoost | 树神 | 🌳 | 梯度提升精准打击 | #10B981 |
| 随机森林 | 林长老 | 🌲 | 众人拾柴火焰高 | #F59E0B |

### 新增文件

| 文件 | 说明 |
|------|------|
| `ssq_gui_v2.py` | 完全重写的GUI，预测员竞技场 |
| `ssq_prediction_v2.py` | 新增 predict_per_strategy(), PREDICTORS, calculate_prize() |
| `ssq_database.py` | 新增 predictor_records 表 + 战绩函数 |

### 运行
```bash
python ssq_gui_v2.py                           # 启动竞技场
python ssq_gui_v2.py 2026080 01,05,12,18,25,30 08  # 开奖PK
```
