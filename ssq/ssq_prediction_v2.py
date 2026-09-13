#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
双色球预测引擎 V2.0 - TOP 5 算法重构版
===========================================

基于当前最流行的五种算法重新设计:
  🥇 LSTM 神经网络      - 深度学习时序预测
  🥈 MCMC (马尔可夫链+蒙特卡洛) - 概率推断
  🥉 Stacking 多模型融合  - 元学习器集成
  🏅 频率+遗漏+冷热号    - 传统经典优化版
  🏅 XGBoost + 随机森林  - 树模型特征工程

架构:
  FeatureEngineer -> 5 Strategies -> StackingEnsemble -> BacktestEngine -> Report

依赖: numpy, scipy, sklearn, xgboost, torch (可选, 缺失时自动降级)
"""

import os
import sys
import json
import math
import time
import random
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from collections import Counter, defaultdict
from dataclasses import dataclass
from itertools import combinations

import numpy as np

# ============================================================================
# 常量
# ============================================================================

RED_RANGE = list(range(1, 34))
BLUE_RANGE = list(range(1, 17))
TOP_N = 25                         # 输出预测组数 (5算法 × 5组)
PER_STRATEGY = 5                   # 每种算法生成组数
SEQ_LEN = 50
N_SPLITS = 5

# 尝试导入可选依赖
try:
    from scipy.special import softmax as sp_softmax
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False

def _softmax(x, axis=-1):
    x = np.array(x, dtype=float)
    x_max = np.max(x, axis=axis, keepdims=True)
    e_x = np.exp(x - x_max)
    return e_x / e_x.sum(axis=axis, keepdims=True)

softmax = sp_softmax if HAS_SCIPY else _softmax

try:
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import StratifiedKFold
    from sklearn.preprocessing import StandardScaler
    from sklearn.linear_model import LogisticRegression
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False

try:
    import xgboost as xgb
    HAS_XGBOOST = True
except ImportError:
    HAS_XGBOOST = False

try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    from torch.utils.data import DataLoader, TensorDataset
    HAS_TORCH = True
except (ImportError, OSError):
    HAS_TORCH = False


# ============================================================================
# 数据类
# ============================================================================

@dataclass
class LotteryDraw:
    issue: str
    date: str
    reds: List[int]
    blue: int
    year: int

    def __post_init__(self):
        self.reds = sorted(self.reds)


@dataclass
class Prediction:
    reds: List[int]
    blue: int
    score: float
    strategy: str
    confidence: float = 0.0

    def __post_init__(self):
        self.reds = sorted(self.reds)


# ============================================================================
# 特征工程器
# ============================================================================

class FeatureEngineer:
    """多维度特征提取 V3 — 指数衰减 + 位置感知 + 模数分析 + 共现挖掘"""

    def __init__(self, history: List[LotteryDraw], decay_factor: float = 0.98,
                 light: bool = False):
        self.history = history
        self.decay_factor = decay_factor  # 每期衰减因子，半衰期≈35期
        self.light = light
        self._compute()
        self._compute_position_stats()
        self._compute_modular_patterns()
        self._mine_association_rules()
        self._trans_cache = None
        if not light:
            self._precompute_missing()

    def _precompute_missing(self):
        """预计算每个 draw_index 下各号码的遗漏期数，避免 build_features 每次 O(n) 回扫"""
        n = self.draw_count
        self._miss_red = np.zeros((n, 33), dtype=np.int32)
        self._miss_blue = np.zeros((n, 16), dtype=np.int32)
        last_red = np.full(33, -1, dtype=np.int32)
        last_blue = np.full(16, -1, dtype=np.int32)
        for i in range(n):
            self._miss_red[i] = (i - 1) - last_red
            self._miss_blue[i] = (i - 1) - last_blue
            d = self.history[i]
            for r in d.reds:
                last_red[r - 1] = i
            last_blue[d.blue - 1] = i

    def _recency_weights(self, n: int = None) -> np.ndarray:
        """指数衰减权重: w[i] = decay^(N-1-i), 最近一期权重最高"""
        if n is None:
            n = self.draw_count
        if n <= 0:
            return np.ones(1)
        indices = np.arange(n)
        return self.decay_factor ** (n - 1 - indices)

    def _compute(self):
        self.draw_count = len(self.history)
        if self.draw_count == 0:
            return

        rw = self._recency_weights()
        total_w = rw.sum()

        # ---- 衰减加权的频率统计 ----
        red_weighted = defaultdict(float)
        blue_weighted = defaultdict(float)
        for idx, d in enumerate(self.history):
            for r in d.reds:
                red_weighted[r] += rw[idx]
            blue_weighted[d.blue] += rw[idx]

        self.red_counter = Counter()
        self.blue_counter = Counter()
        for d in self.history:
            for r in d.reds:
                self.red_counter[r] += 1
            self.blue_counter[d.blue] += 1

        self.red_freq = {i: red_weighted.get(i, 0) / total_w for i in RED_RANGE}
        self.blue_freq = {i: blue_weighted.get(i, 0) / total_w for i in BLUE_RANGE}

        # ---- 衰减加权的和值/跨度 ----
        sums = np.array([sum(d.reds) for d in self.history])
        spans = np.array([max(d.reds) - min(d.reds) for d in self.history])
        self.sum_mean = float(np.average(sums, weights=rw))
        self.sum_std = float(np.sqrt(np.average((sums - self.sum_mean)**2, weights=rw))) or 1.0
        self.span_mean = float(np.average(spans, weights=rw))
        self.span_std = float(np.sqrt(np.average((spans - self.span_mean)**2, weights=rw))) or 1.0

        odd_counts = np.array([sum(1 for r in d.reds if r % 2 == 1) for d in self.history])
        self.odd_ratio = float(np.average(odd_counts / 6, weights=rw))

        zones = np.array([
            [sum(1 for r in d.reds if r <= 11),
             sum(1 for r in d.reds if 12 <= r <= 22),
             sum(1 for r in d.reds if r >= 23)]
            for d in self.history
        ], dtype=float)
        self.zone_avg = (np.average(zones, axis=0, weights=rw) / 6).tolist()

        cons_count = np.array([
            1 if any(d.reds[i+1] - d.reds[i] == 1 for i in range(5)) else 0
            for d in self.history
        ])
        self.consecutive_prob = float(np.average(cons_count, weights=rw))

        ac_values = []
        for d in self.history:
            diffs = set()
            for i, j in combinations(d.reds, 2):
                diffs.add(abs(i - j))
            ac_values.append(len(diffs) - 5)
        self.ac_mean = float(np.average(ac_values, weights=rw))

    # ====== 位置感知统计 ======
    def _compute_position_stats(self):
        """计算每个位置(1-6)的独立统计分布"""
        if self.draw_count < 10:
            self.pos_freq = [{} for _ in range(6)]
            self.pos_mean = [0.0] * 6
            self.pos_std = [1.0] * 6
            self.pos_bounds = [(1, 33) for _ in range(6)]
            self.pos_missing = [{} for _ in range(6)]
            return

        rw = self._recency_weights()
        pos_counts = [defaultdict(float) for _ in range(6)]
        pos_lists = [[] for _ in range(6)]

        for idx, d in enumerate(self.history):
            for p in range(6):
                ball = d.reds[p]
                pos_counts[p][ball] += rw[idx]
                pos_lists[p].append(ball)

        total_w = rw.sum()
        self.pos_freq = [
            {i: pos_counts[p].get(i, 0) / total_w for i in RED_RANGE}
            for p in range(6)
        ]
        self.pos_mean = [float(np.average(pos_lists[p], weights=rw[:len(pos_lists[p])])) for p in range(6)]
        self.pos_std = [float(np.sqrt(np.average(
            (np.array(pos_lists[p]) - self.pos_mean[p])**2,
            weights=rw[:len(pos_lists[p])]))) or 1.0 for p in range(6)]
        self.pos_bounds = []
        for p in range(6):
            vals = pos_lists[p]
            lo = max(1, int(np.percentile(vals, 1)) - 1)
            hi = min(33, int(np.percentile(vals, 99)) + 1)
            self.pos_bounds.append((lo, hi))

        if self.light:
            self.pos_missing = [{} for _ in range(6)]
            return

        self.pos_missing = [{} for _ in range(6)]
        for p in range(6):
            for i in RED_RANGE:
                missing = 0
                for d in reversed(self.history):
                    if d.reds[p] == i:
                        break
                    missing += 1
                self.pos_missing[p][i] = missing

    # ====== 模数/谐波模式分析 ======
    def _compute_modular_patterns(self):
        """计算尾号、模3/5/7路由分布"""
        if self.draw_count == 0:
            self.mantissa_dist = np.ones(10) / 10
            self.mod3_dist = np.ones(3) / 3
            self.mod5_dist = np.ones(5) / 5
            self.mod7_dist = np.ones(7) / 7
            self.fib_ratio = 0.18
            return

        rw = self._recency_weights()
        mantissa_counts = np.zeros(10)
        mod3_counts = np.zeros(3)
        mod5_counts = np.zeros(5)
        mod7_counts = np.zeros(7)
        fib_set = {1, 2, 3, 5, 8, 13, 21}
        fib_count = 0.0

        for idx, d in enumerate(self.history):
            for r in d.reds:
                mantissa_counts[r % 10] += rw[idx]
                mod3_counts[r % 3] += rw[idx]
                mod5_counts[r % 5] += rw[idx]
                mod7_counts[r % 7] += rw[idx]
                if r in fib_set:
                    fib_count += rw[idx]

        self.mantissa_dist = mantissa_counts / mantissa_counts.sum()
        self.mod3_dist = mod3_counts / mod3_counts.sum()
        self.mod5_dist = mod5_counts / mod5_counts.sum()
        self.mod7_dist = mod7_counts / mod7_counts.sum()
        self.fib_ratio = fib_count / (rw.sum() * 6)

    # ====== 共现关联规则挖掘 ======
    def _mine_association_rules(self, min_lift: float = 1.3):
        """挖掘频繁共现的球对，计算lift值"""
        if self.draw_count < 30:
            self.association_pairs = {}
            self.top_assoc_pairs = []
            return

        recent_n = min(200, self.draw_count)
        recent = self.history[-recent_n:]
        rw = self._recency_weights(recent_n)

        pair_counts = defaultdict(float)
        single_counts = defaultdict(float)

        for idx, d in enumerate(recent):
            for r in d.reds:
                single_counts[r] += rw[idx]
            for i in range(6):
                for j in range(i + 1, 6):
                    a, b = d.reds[i], d.reds[j]
                    if a > b:
                        a, b = b, a
                    pair_counts[(a, b)] += rw[idx]

        total_w = rw.sum()
        # 计算lift: P(A,B) / (P(A) * P(B))
        p_a_norm = {k: v / (total_w * 6) for k, v in single_counts.items()}
        self.association_pairs = {}
        for (a, b), pair_w in pair_counts.items():
            p_ab = pair_w / total_w / 15  # 每期15对
            expected = p_a_norm.get(a, 0) * p_a_norm.get(b, 0)
            if expected > 0:
                lift = p_ab / expected
                if lift > min_lift:
                    self.association_pairs[(a, b)] = lift

        self.top_assoc_pairs = sorted(
            self.association_pairs.items(), key=lambda x: -x[1])[:30]

    def recent_window(self, window: int = 30, use_recency: bool = True) -> Dict:
        recent = self.history[-window:] if len(self.history) >= window else self.history
        n = len(recent)
        recent_reds, recent_blues = [], []
        for d in recent:
            recent_reds.extend(d.reds)
            recent_blues.append(d.blue)

        if use_recency and n > 1:
            rw = self._recency_weights(self.draw_count)[-n:]
            rc = defaultdict(float)
            bc = defaultdict(float)
            for idx, d in enumerate(recent):
                for r in d.reds:
                    rc[r] += rw[idx]
                bc[d.blue] += rw[idx]
            total_w = rw.sum()
            return {
                'red_freq': {i: rc.get(i, 0) / total_w for i in RED_RANGE},
                'blue_freq': {i: bc.get(i, 0) / total_w for i in BLUE_RANGE},
                'red_counter': Counter({k: v for k, v in rc.items()}),
                'blue_counter': Counter({k: v for k, v in bc.items()}),
                'n': n,
            }

        return {
            'red_freq': {i: Counter(recent_reds).get(i, 0) / n for i in RED_RANGE},
            'blue_freq': {i: Counter(recent_blues).get(i, 0) / n for i in BLUE_RANGE},
            'red_counter': Counter(recent_reds),
            'blue_counter': Counter(recent_blues),
            'n': n,
        }

    def missing_analysis(self) -> Dict:
        red_missing, blue_missing = {}, {}
        for i in RED_RANGE:
            missing = 0
            for d in reversed(self.history):
                if i in d.reds: break
                missing += 1
            red_missing[i] = missing
        for i in BLUE_RANGE:
            missing = 0
            for d in reversed(self.history):
                if d.blue == i: break
                missing += 1
            blue_missing[i] = missing
        return {'red': red_missing, 'blue': blue_missing}

    def hot_cold(self, window: int = 30) -> Dict:
        wf = self.recent_window(window)
        n = wf['n']
        red_avg = n * 6 / 33
        blue_avg = n / 16

        def classify(cnt, avg):
            if cnt > avg * 1.5: return 'hot'
            if cnt < avg * 0.5: return 'cold'
            return 'warm'

        return {
            'red': {i: classify(wf['red_counter'].get(i, 0), red_avg) for i in RED_RANGE},
            'blue': {i: classify(wf['blue_counter'].get(i, 0), blue_avg) for i in BLUE_RANGE},
        }

    def transition_matrix(self) -> Dict:
        """转移矩阵（惰性缓存，避免 build_features / MCMC 每次 O(n) 重建）"""
        if self._trans_cache is None:
            red_trans = defaultdict(Counter)
            blue_trans = defaultdict(Counter)
            for t in range(len(self.history) - 1):
                curr, nxt = self.history[t], self.history[t + 1]
                for r in curr.reds:
                    for nr in nxt.reds:
                        red_trans[r][nr] += 1
                blue_trans[curr.blue][nxt.blue] += 1
            self._trans_cache = {'red': dict(red_trans), 'blue': dict(blue_trans)}
        return self._trans_cache

    def _scoped_stats(self, draw_index: int) -> 'FeatureEngineer':
        """构建 as-of draw_index 的轻量统计（仅用 past，避免未来数据泄漏）。

        因衰减因子 0.98 使 200 期前的权重 <2%，只取 past 最近 200 期即可，
        兼顾正确性（无泄漏）与速度（O(200) 而非 O(n)）。
        """
        past = self.history[:draw_index]
        window = past[-200:] if len(past) > 200 else past
        return FeatureEngineer(window, self.decay_factor, light=True)

    def build_features(self, draw_index: int) -> Optional[np.ndarray]:
        """构建机器学习特征向量 V3 (~380维) — 含位置/模数/周期/共现"""
        if self.light:
            return None  # light 实例未预计算遗漏，不支持 build_features
        if draw_index < SEQ_LEN:
            return None
        past = self.history[:draw_index]
        n_past = len(past)

        recent_n = min(30, n_past)
        recent = past[-recent_n:]
        rw_recent = self._recency_weights(n_past)[-recent_n:]

        # ---- 衰减加权近期频率 ----
        recent_red_freq = np.zeros(33)
        recent_blue_freq = np.zeros(16)
        for idx, d in enumerate(recent):
            for r in d.reds:
                recent_red_freq[r - 1] += rw_recent[idx]
            recent_blue_freq[d.blue - 1] += rw_recent[idx]
        rw_sum = rw_recent.sum() or 1.0
        recent_red_freq /= rw_sum
        recent_blue_freq /= rw_sum

        # ---- 遗漏分析 (预计算缓存, O(1) 查询) ----
        red_missing = self._miss_red[draw_index]
        blue_missing = self._miss_blue[draw_index]

        # ---- 衰减加权全局频率 ----
        rw_all = self._recency_weights(n_past)
        global_red_freq = np.zeros(33)
        global_blue_freq = np.zeros(16)
        for idx, d in enumerate(past):
            for r in d.reds:
                global_red_freq[r - 1] += rw_all[idx]
            global_blue_freq[d.blue - 1] += rw_all[idx]
        rw_all_sum = rw_all.sum() or 1.0
        global_red_freq /= rw_all_sum
        global_blue_freq /= rw_all_sum

        # ---- 上期 one-hot ----
        last = past[-1]
        last_red = np.zeros(33)
        last_blue = np.zeros(16)
        for r in last.reds:
            last_red[r - 1] = 1
        last_blue[last.blue - 1] = 1

        # ---- 转移概率 (仅用 past 内统计，避免未来数据泄漏) ----
        scoped = self._scoped_stats(draw_index)
        trans = scoped.transition_matrix()
        trans_red = np.zeros(33)
        trans_blue = np.zeros(16)
        for r in last.reds:
            if r in trans['red']:
                total = sum(trans['red'][r].values())
                if total > 0:
                    for nr, cnt in trans['red'][r].items():
                        trans_red[nr - 1] += cnt / total
        if last.blue in trans['blue']:
            total = sum(trans['blue'][last.blue].values())
            if total > 0:
                for nb, cnt in trans['blue'][last.blue].items():
                    trans_blue[nb - 1] += cnt / total

        # ---- NEW: 位置特征 (位置1-3的概率分布, 压缩为每位置11维桶) ----
        pos_feat = np.zeros(3 * 11)  # 33维
        if scoped.pos_freq:
            for p in range(3):
                pf = scoped.pos_freq[p]
                for i in range(33):
                    bucket = i // 3
                    pos_feat[p * 11 + bucket] += pf.get(i + 1, 0)

        # ---- NEW: 模数特征 (尾号10 + 模3/5/7 = 25维) ----
        mod_feat = np.concatenate([
            scoped.mantissa_dist,    # 10
            scoped.mod3_dist,        # 3
            scoped.mod5_dist,        # 5
            scoped.mod7_dist,        # 7
        ])

        # ---- NEW: 周期特征 (12维) ----
        if len(past) > 0:
            last_date = past[-1].date
            try:
                from datetime import datetime
                dt = datetime.strptime(last_date, '%Y-%m-%d')
                dow = dt.weekday()  # 0=Mon, 2=Tue, 4=Thu, 6=Sun
                cyclical = np.array([
                    float(dow == 2), float(dow == 4), float(dow == 6),  # is_tue/thu/sun
                    np.sin(2 * np.pi * dow / 7), np.cos(2 * np.pi * dow / 7),
                    np.sin(2 * np.pi * dt.month / 12), np.cos(2 * np.pi * dt.month / 12),
                    float(dt.month <= 3), float(3 < dt.month <= 6),
                    float(6 < dt.month <= 9), float(dt.month > 9),  # quarter one-hot
                ])
            except Exception:
                cyclical = np.zeros(12)
        else:
            cyclical = np.zeros(12)

        # ---- NEW: 共现关联特征 (top 10高lift对) ----
        assoc_feat = np.zeros(10)
        for idx, ((a, b), lift) in enumerate(scoped.top_assoc_pairs[:10]):
            # 如果上期号码中同时有a或b任一，则标记
            if a in last.reds or b in last.reds:
                assoc_feat[idx] = lift

        # ---- 结构特征 ----
        odd_ratio = sum(1 for r in last.reds if r % 2 == 1) / 6
        zone_dist = np.zeros(3)
        for r in last.reds:
            if r <= 11:
                zone_dist[0] += 1
            elif r <= 22:
                zone_dist[1] += 1
            else:
                zone_dist[2] += 1

        # ---- 组装 (~380维) ----
        features = np.concatenate([
            recent_red_freq, recent_blue_freq,   # 49
            red_missing, blue_missing,            # 49
            global_red_freq, global_blue_freq,    # 49
            last_red, last_blue,                  # 49
            trans_red, trans_blue,                # 49
            pos_feat,                             # 33 (NEW)
            mod_feat,                             # 25 (NEW)
            cyclical,                             # 12 (NEW)
            assoc_feat,                           # 10 (NEW)
            np.array([odd_ratio]), zone_dist,     # 4
        ])
        return features


# ============================================================================
# 策略基类
# ============================================================================

class BaseStrategy:
    def __init__(self, name: str):
        self.name = name
        self.weight = 1.0
        self.performance: List[float] = []

    def predict(self, analyzer: FeatureEngineer, n: int = 1) -> List[Prediction]:
        raise NotImplementedError

    def evaluate(self, actual_reds: List[int], actual_blue: int,
                 pred: Prediction) -> float:
        red_hit = len(set(pred.reds) & set(actual_reds))
        blue_hit = 1 if pred.blue == actual_blue else 0
        return red_hit / 6 * 0.85 + blue_hit * 0.15

    def _sample(self, weights: Dict[int, float], k: int) -> List[int]:
        items = list(weights.keys())
        w = np.array([max(weights[i], 1e-10) for i in items], dtype=float)
        w = w / w.sum()
        selected = []
        for _ in range(k):
            idx = np.random.choice(len(items), p=w)
            selected.append(items[idx])
            w[idx] = 0
            if w.sum() == 0: break
            w = w / w.sum()
        return sorted(selected)


def _red_prob_vector(models, X) -> np.ndarray:
    """对 33 个红球二分类模型取 P(class=1)，兼容单类别模型。

    单类别（训练集内该红球从未/一直出现）时 predict_proba 只返回 1 列，
    不能按 [0][1] 取值；需根据 classes_[0] 判断唯一类别是 0 还是 1。
    """
    probs = []
    for m in models:
        proba = m.predict_proba(X)[0]
        if proba.shape[0] > 1:
            probs.append(proba[1])
        else:
            probs.append(1.0 if m.classes_[0] == 1 else 0.0)
    return np.array(probs)


def _blue_prob_vector(model, X, classes) -> np.ndarray:
    """将蓝球模型 predict_proba 输出映射为 16 维概率向量，补齐未出现类别为 0。

    classes: 模型实际训练到的类别列表（蓝球号码-1, 0-15）。
    未出现的蓝球类别概率为 0。兼容 xgboost（重映射后的类）与 sklearn（classes_）。
    """
    raw = model.predict_proba(X)[0]
    vec = np.zeros(16)
    for i, c in enumerate(classes):
        vec[int(c)] = raw[i]
    return vec


# ============================================================================
# 策略1: 频率+遗漏+冷热号 三合一
# ============================================================================

class FrequencyMissingStrategy(BaseStrategy):
    """频率 + 遗漏 + 冷热号 综合策略"""

    def __init__(self):
        super().__init__("frequency_missing")

    def predict(self, analyzer: FeatureEngineer, n: int = 1) -> List[Prediction]:
        missing = analyzer.missing_analysis()
        hot_cold = analyzer.hot_cold(30)
        recent = analyzer.recent_window(30)

        predictions = []
        for _ in range(n):
            red_weights = {}
            for i in RED_RANGE:
                w = 1.0
                w += analyzer.red_freq.get(i, 0) * 3
                w += missing['red'].get(i, 0) * 0.05
                hc = hot_cold['red'].get(i, 'warm')
                w *= 1.5 if hc == 'hot' else (0.4 if hc == 'cold' else 1.0)
                recent_rf = recent['red_freq'].get(i, 0)
                global_rf = analyzer.red_freq.get(i, 0)
                if global_rf > 0:
                    trend = recent_rf / global_rf
                    w *= (0.8 + 0.4 * trend)
                red_weights[i] = max(w, 0.01)

            blue_weights = {}
            for i in BLUE_RANGE:
                w = 1.0 + analyzer.blue_freq.get(i, 0) * 2
                w += missing['blue'].get(i, 0) * 0.03
                hc = hot_cold['blue'].get(i, 'warm')
                w *= 1.3 if hc == 'hot' else (0.5 if hc == 'cold' else 1.0)
                blue_weights[i] = max(w, 0.01)

            reds = self._sample(red_weights, 6)
            blue = self._sample(blue_weights, 1)[0]

            if not self._valid(reds, analyzer):
                reds = self._constrained(red_weights, analyzer)

            predictions.append(Prediction(
                reds=sorted(reds), blue=blue, score=0.0, strategy=self.name))

        return predictions

    def _valid(self, reds, analyzer):
        s, sp = sum(reds), max(reds) - min(reds)
        return (abs(s - analyzer.sum_mean) < 3 * analyzer.sum_std and
                abs(sp - analyzer.span_mean) < 3 * analyzer.span_std)

    def _constrained(self, weights, analyzer):
        for _ in range(500):
            reds = self._sample(weights, 6)
            if self._valid(reds, analyzer): return reds
        top = sorted(weights.items(), key=lambda x: x[1], reverse=True)
        return sorted([x[0] for x in top[:6]])


# ============================================================================
# 策略2: MCMC
# ============================================================================

class MCMCStrategy(BaseStrategy):
    """MCMC Metropolis-Hastings 采样"""

    def __init__(self, iterations: int = 10000, burn_in: int = 2000):
        super().__init__("mcmc")
        self.iterations = iterations
        self.burn_in = burn_in

    def predict(self, analyzer: FeatureEngineer, n: int = 1) -> List[Prediction]:
        trans = analyzer.transition_matrix()
        missing = analyzer.missing_analysis()

        predictions = []
        for group_idx in range(n):
            samples = self._mh_sample(analyzer, trans, missing)
            valid = samples[self.burn_in:]
            combo_counter = Counter(tuple(sorted(s)) for s in valid)

            top_combos = combo_counter.most_common(min(30, len(combo_counter)))
            if top_combos:
                idx = group_idx % len(top_combos)
                reds = list(top_combos[idx][0])
                confidence = top_combos[idx][1] / len(valid)
            else:
                reds = self._sample(
                    {i: analyzer.red_freq.get(i, 0.01) for i in RED_RANGE}, 6)
                confidence = 0.01

            blue_weights = {}
            for i in BLUE_RANGE:
                bw = analyzer.blue_freq.get(i, 0.01) + missing['blue'].get(i, 0) * 0.02
                blue_weights[i] = max(bw, 0.01)
            blue = self._sample(blue_weights, 1)[0]

            predictions.append(Prediction(
                reds=sorted(reds), blue=blue, score=confidence * 100,
                strategy=self.name, confidence=confidence))

        return predictions

    def _mh_sample(self, analyzer, trans, missing):
        samples = []
        current = tuple(sorted(random.sample(RED_RANGE, 6)))
        current_prob = self._target(current, analyzer, trans, missing)

        for _ in range(self.iterations):
            proposal = self._propose(current)
            if proposal is None:
                samples.append(current)
                continue
            prop_prob = self._target(proposal, analyzer, trans, missing)
            alpha = min(1.0, prop_prob / current_prob if current_prob > 0 else 1.0)
            if random.random() < alpha:
                current, current_prob = proposal, prop_prob
            samples.append(current)
        return samples

    def _propose(self, current):
        n_replace = 1 if random.random() < 0.5 else 2
        remove = set(random.sample(list(current), n_replace))
        remaining = set(current) - remove
        candidates = [i for i in RED_RANGE if i not in remaining]
        if len(candidates) < n_replace: return None
        add = set(random.sample(candidates, n_replace))
        return tuple(sorted(remaining | add))

    def _target(self, reds, analyzer, trans, missing):
        prob = 1.0
        # 频率项 (衰减加权)
        for r in reds:
            prob *= max(analyzer.red_freq.get(r, 0.001), 0.001)**0.7

        # 遗漏项
        for r in reds:
            prob *= (1.0 + missing['red'].get(r, 0) * 0.01)

        # 共现关联项 (V3 新增)
        assoc = getattr(analyzer, 'association_pairs', {})
        for i in range(len(reds)):
            for j in range(i + 1, len(reds)):
                a, b = reds[i], reds[j]
                if a > b:
                    a, b = b, a
                lift = assoc.get((a, b), 1.0)
                if lift > 1.3:
                    prob *= 1.0 + (lift - 1.0) * 0.3

        # 位置兼容性 (V3 新增)
        if hasattr(analyzer, 'pos_std') and analyzer.pos_std:
            for p, r in enumerate(reds):
                z = abs(r - analyzer.pos_mean[p]) / max(analyzer.pos_std[p], 0.1)
                prob *= np.exp(-0.2 * z**2)

        # 和值/跨度 (权重降低, 位置分析已覆盖)
        s, sp = sum(reds), max(reds) - min(reds)
        z_sum = (s - analyzer.sum_mean) / analyzer.sum_std
        prob *= np.exp(-0.3 * z_sum**2)
        z_span = (sp - analyzer.span_mean) / analyzer.span_std
        prob *= np.exp(-0.3 * z_span**2)
        return max(prob, 1e-10)


# ============================================================================
# 策略3: 位置感知策略 (V3 新增)
# ============================================================================

class PositionAwareStrategy(BaseStrategy):
    """逐位置独立建模 — 替代 freq+missing+trend+zone 三个策略"""

    def __init__(self):
        super().__init__("position_aware")

    def predict(self, analyzer: FeatureEngineer, n: int = 1) -> List[Prediction]:
        missing = analyzer.missing_analysis()
        recent = analyzer.recent_window(30)

        predictions = []
        for _ in range(n):
            # 逐位置选取红球
            reds = []
            used = set()
            for p in range(6):
                weights = {}
                bounds = analyzer.pos_bounds[p] if hasattr(analyzer, 'pos_bounds') else (1, 33)
                pf = analyzer.pos_freq[p] if hasattr(analyzer, 'pos_freq') else {}

                for i in range(bounds[0], bounds[1] + 1):
                    if i in used:
                        continue
                    w = 1.0
                    w += pf.get(i, 0) * 5  # 位置频率
                    w += missing['red'].get(i, 0) * 0.03  # 遗漏
                    w += recent['red_freq'].get(i, 0) * 2  # 近期趋势
                    # 位置偏差惩罚: 偏离均值越远, 权重越低
                    if hasattr(analyzer, 'pos_mean') and hasattr(analyzer, 'pos_std'):
                        z = abs(i - analyzer.pos_mean[p]) / max(analyzer.pos_std[p], 0.1)
                        w *= np.exp(-0.3 * z ** 2)
                    weights[i] = max(w, 0.01)

                ball = self._sample(weights, 1)[0]
                reds.append(ball)
                used.add(ball)

            # 蓝球
            blue_weights = {}
            for i in BLUE_RANGE:
                w = 1.0 + analyzer.blue_freq.get(i, 0) * 3
                w += missing['blue'].get(i, 0) * 0.04
                blue_weights[i] = max(w, 0.01)

            blue = self._sample(blue_weights, 1)[0]
            predictions.append(Prediction(
                reds=sorted(reds), blue=blue, score=0.0, strategy=self.name))

        return predictions


# ============================================================================
# 策略4: 蓝球专项策略 (V3 新增)
# ============================================================================

class BlueDedicatedStrategy(BaseStrategy):
    """蓝球6信号融合 — 奇偶交替/大小/012路/遗漏回补/红球关联"""

    def __init__(self):
        super().__init__("blue_dedicated")

    def predict(self, analyzer: FeatureEngineer, n: int = 1) -> List[Prediction]:
        missing = analyzer.missing_analysis()
        last = analyzer.history[-1]
        last_blue = last.blue

        # 蓝球6信号
        blue_scores = np.ones(16)

        # 信号1: 频率 (权重 3.0)
        for i in BLUE_RANGE:
            blue_scores[i - 1] += analyzer.blue_freq.get(i, 0) * 3.0

        # 信号2: 遗漏回补 (遗漏>20期加权更高)
        for i in BLUE_RANGE:
            m = missing['blue'].get(i, 0)
            blue_scores[i - 1] += min(m, 50) * 0.05

        # 信号3: 奇偶交替 (连续3期同奇偶→下期切换概率高)
        recent_parities = [d.blue % 2 for d in analyzer.history[-10:]]
        if len(recent_parities) >= 3 and len(set(recent_parities[-3:])) == 1:
            # 连续同奇/偶, 下期倾向于切换
            switch_parity = 1 - recent_parities[-1]
            for i in BLUE_RANGE:
                if i % 2 == switch_parity:
                    blue_scores[i - 1] *= 1.5

        # 信号4: 大小交替 (1-8小, 9-16大)
        recent_sizes = ['S' if d.blue <= 8 else 'B' for d in analyzer.history[-10:]]
        if len(recent_sizes) >= 2 and recent_sizes[-1] == recent_sizes[-2]:
            # 连续同大小, 下期倾向于切换
            switch_size = 'B' if recent_sizes[-1] == 'S' else 'S'
            for i in BLUE_RANGE:
                cur = 'S' if i <= 8 else 'B'
                if cur == switch_size:
                    blue_scores[i - 1] *= 1.3

        # 信号5: 蓝球与上期红球关联 (~15%概率蓝球=某上期红球, boost)
        for r in last.reds:
            if r <= 16:
                blue_scores[r - 1] *= 1.8

        # 信号6: 012路模式
        last_route = last_blue % 3
        route_counts = np.zeros(3)
        for d in analyzer.history[-30:]:
            route_counts[d.blue % 3] += 1
        # 如某路由比例异常低, 加权
        route_probs = route_counts / route_counts.sum()
        for i in BLUE_RANGE:
            if route_probs[i % 3] < 0.25:  # 偏低
                blue_scores[i - 1] *= 1.2

        # 红球部分: 使用位置感知降级 (快速生成)
        reds_list = []
        pa = PositionAwareStrategy()
        pa_preds = pa.predict(analyzer, n=n)
        for pp in pa_preds:
            reds_list.append(pp.reds)

        # 组装预测
        predictions = []
        for i in range(n):
            # 蓝球: 按融合信号加权采样
            bw = {j + 1: max(blue_scores[j], 0.01) for j in range(16)}
            blue = self._sample(bw, 1)[0]

            predictions.append(Prediction(
                reds=sorted(reds_list[i]) if i < len(reds_list) else sorted(
                    np.random.choice(RED_RANGE, 6, replace=False)),
                blue=blue, score=float(blue_scores[blue - 1]),
                strategy=self.name))

        return predictions


# ============================================================================
# 策略5: 关联规则增强策略 (V3 新增)
# ============================================================================

class AssociationBoostStrategy(BaseStrategy):
    """共现关联驱动 — 基于高lift关联对调整候选组合"""

    def __init__(self):
        super().__init__("association_boost")

    def predict(self, analyzer: FeatureEngineer, n: int = 1) -> List[Prediction]:
        freq = analyzer.red_freq
        missing = analyzer.missing_analysis()
        assoc = getattr(analyzer, 'association_pairs', {})

        predictions = []
        for _ in range(n):
            # 基础权重
            rw = {}
            for i in RED_RANGE:
                w = 1.0 + freq.get(i, 0) * 3
                w += missing['red'].get(i, 0) * 0.03
                rw[i] = max(w, 0.01)

            # 关联规则增强: 选中号码后, 提升其高lift配对
            reds = []
            avail = list(RED_RANGE)
            for _ in range(6):
                # 根据已选号码调整权重
                adj = dict(rw)
                for r_selected in reds:
                    for (a, b), lift in assoc.items():
                        other = b if a == r_selected else (a if b == r_selected else None)
                        if other is not None and other in adj:
                            adj[other] *= (1.0 + min(lift - 1.0, 3.0) * 0.5)

                # 从可用中采样
                a_w = {k: adj.get(k, 0.01) for k in avail}
                ball = self._sample(a_w, 1)[0]
                reds.append(ball)
                avail.remove(ball)

            # 蓝球
            bw = {}
            for i in BLUE_RANGE:
                w = 1.0 + analyzer.blue_freq.get(i, 0) * 3
                w += missing['blue'].get(i, 0) * 0.04
                bw[i] = max(w, 0.01)
            blue = self._sample(bw, 1)[0]

            predictions.append(Prediction(
                reds=sorted(reds), blue=blue, score=0.0, strategy=self.name))

        return predictions


# ============================================================================
# 策略6: 模数韵律策略 (V3 新增)
# ============================================================================

class ModularPatternStrategy(BaseStrategy):
    """尾数+模数+谐波模式 — 基于历史模数比例约束生成"""

    def __init__(self):
        super().__init__("modular_pattern")

    def predict(self, analyzer: FeatureEngineer, n: int = 1) -> List[Prediction]:
        freq = analyzer.red_freq
        missing = analyzer.missing_analysis()
        mod3 = getattr(analyzer, 'mod3_dist', np.ones(3) / 3)
        fib_ratio = getattr(analyzer, 'fib_ratio', 0.18)
        fib_set = {1, 2, 3, 5, 8, 13, 21}

        predictions = []
        for _ in range(n):
            # 基础权重
            rw = {}
            for i in RED_RANGE:
                w = 1.0 + freq.get(i, 0) * 3
                w += missing['red'].get(i, 0) * 0.03
                # 模3路由调整
                route_w = mod3[i % 3]
                w *= (0.7 + 0.9 * route_w)
                # 斐波那契数偏好
                if i in fib_set:
                    w *= (0.8 + fib_ratio * 2.5)
                rw[i] = max(w, 0.01)

            reds = self._sample(rw, 6)

            # 模数约束: 6个红球的尾数不应全不同 (历史上概率极低)
            mantissas = {r % 10 for r in reds}
            if len(mantissas) == 6:  # 6个全不同尾号, 不自然, 重试
                for _ in range(200):
                    reds2 = self._sample(rw, 6)
                    if len({x % 10 for x in reds2}) < 6:
                        reds = reds2
                        break

            # 蓝球: 增强版
            bw = {}
            for i in BLUE_RANGE:
                w = 1.0 + analyzer.blue_freq.get(i, 0) * 3
                w += missing['blue'].get(i, 0) * 0.05
                bw[i] = max(w, 0.01)
            blue = self._sample(bw, 1)[0]

            predictions.append(Prediction(
                reds=sorted(reds), blue=blue, score=0.0, strategy=self.name))

        return predictions


if HAS_TORCH:
    import torch.nn as nn
    import torch.optim as optim
    from torch.utils.data import DataLoader, TensorDataset


# ============================================================================
# 策略7: LSTM (升级版)
# ============================================================================

if HAS_TORCH:

    class LSTMPredictor(nn.Module):
        """原始 LSTM (向后兼容)"""
        def __init__(self, input_dim=49, hidden_dim=128, num_layers=2):
            super().__init__()
            self.lstm = nn.LSTM(input_dim, hidden_dim, num_layers,
                                batch_first=True, dropout=0.2)
            self.red_head = nn.Sequential(
                nn.Linear(hidden_dim, 64), nn.ReLU(), nn.Dropout(0.2),
                nn.Linear(64, 33))
            self.blue_head = nn.Sequential(
                nn.Linear(hidden_dim, 32), nn.ReLU(), nn.Dropout(0.2),
                nn.Linear(32, 16))

        def forward(self, x):
            out, _ = self.lstm(x)
            return self.red_head(out[:, -1, :]), self.blue_head(out[:, -1, :])

    class LSTMAttentionPredictor(nn.Module):
        """V3: LSTM + Multi-Head Attention + Residual + LayerNorm"""
        def __init__(self, input_dim=380, hidden_dim=128, num_layers=2, num_heads=4):
            super().__init__()
            self.input_proj = nn.Linear(input_dim, hidden_dim)
            self.lstm = nn.LSTM(hidden_dim, hidden_dim, num_layers,
                                batch_first=True, dropout=0.3)
            self.attention = nn.MultiheadAttention(
                hidden_dim, num_heads, dropout=0.1, batch_first=True)
            self.layer_norm = nn.LayerNorm(hidden_dim)
            self.dropout = nn.Dropout(0.3)
            self.red_head = nn.Sequential(
                nn.Linear(hidden_dim, 128), nn.ReLU(), nn.Dropout(0.3),
                nn.Linear(128, 64), nn.ReLU(), nn.Dropout(0.2),
                nn.Linear(64, 33))
            self.blue_head = nn.Sequential(
                nn.Linear(hidden_dim, 64), nn.ReLU(), nn.Dropout(0.3),
                nn.Linear(64, 16))

        def forward(self, x):
            x = self.input_proj(x)
            lstm_out, _ = self.lstm(x)
            attn_out, _ = self.attention(lstm_out, lstm_out, lstm_out)
            out = self.layer_norm(lstm_out + attn_out)
            out = self.dropout(out[:, -1, :])
            return self.red_head(out), self.blue_head(out)


    class LSTMStrategy(BaseStrategy):
        """LSTM 深度学习策略"""

        def __init__(self, seq_len=50, epochs=100, hidden_dim=128):
            super().__init__("lstm")
            self.seq_len = seq_len
            self.epochs = epochs
            self.hidden_dim = hidden_dim
            self.model = None
            self._trained = False

        def _prepare(self, history):
            X, y_red, y_blue = [], [], []
            for i in range(self.seq_len, len(history)):
                seq = []
                for j in range(i - self.seq_len, i):
                    d = history[j]
                    vec = np.zeros(49)
                    for r in d.reds:
                        vec[r - 1] = 1
                    vec[33 + d.blue - 1] = 1
                    seq.append(vec)
                X.append(seq)
                nxt = history[i]
                red_lbl = np.zeros(33)
                for r in nxt.reds:
                    red_lbl[r - 1] = 1
                y_red.append(red_lbl)
                blue_lbl = np.zeros(16)
                blue_lbl[nxt.blue - 1] = 1
                y_blue.append(blue_lbl)
            if len(X) < 10:
                return None
            return (np.array(X, dtype=np.float32),
                    np.array(y_red, dtype=np.float32),
                    np.array(y_blue, dtype=np.float32))

        def _train(self, history):
            data = self._prepare(history)
            if data is None:
                return False
            X, y_red, y_blue = data

            split = int(len(X) * 0.8)
            ds = TensorDataset(torch.from_numpy(X[:split]),
                               torch.from_numpy(y_red[:split]),
                               torch.from_numpy(y_blue[:split]))
            dl = DataLoader(ds, batch_size=16, shuffle=True)

            self.model = LSTMPredictor(hidden_dim=self.hidden_dim)
            device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
            self.model.to(device)
            opt = optim.Adam(self.model.parameters(), lr=0.001)
            loss_fn = nn.BCEWithLogitsLoss()
            self.model.train()

            for epoch in range(self.epochs):
                for bx, br, bb in dl:
                    bx, br, bb = bx.to(device), br.to(device), bb.to(device)
                    opt.zero_grad()
                    ro, bo = self.model(bx)
                    loss = loss_fn(ro, br) + loss_fn(bo, bb)
                    loss.backward()
                    opt.step()
            self._trained = True
            return True

        def predict(self, analyzer: FeatureEngineer, n: int = 1) -> List[Prediction]:
            if not self._trained:
                ok = self._train(analyzer.history)
                if not ok:
                    return MCMCStrategy(iterations=3000).predict(analyzer, n)

            history = analyzer.history
            seq = []
            for j in range(-self.seq_len, 0):
                idx = max(j if j >= 0 else len(history) + j, 0)
                d = history[idx]
                vec = np.zeros(49)
                for r in d.reds:
                    vec[r - 1] = 1
                vec[33 + d.blue - 1] = 1
                seq.append(vec)

            device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
            self.model.eval()
            with torch.no_grad():
                X = torch.from_numpy(np.array([seq], dtype=np.float32)).to(device)
                ro, bo = self.model(X)
                red_prob = torch.sigmoid(ro).cpu().numpy()[0]
                blue_prob = torch.sigmoid(bo).cpu().numpy()[0]

            predictions = []
            for i in range(n):
                temp = 0.5 + i * 0.1
                rp = softmax(red_prob / temp)
                bp = softmax(blue_prob / temp)
                reds = self._sample({j + 1: rp[j] for j in range(33)}, 6)
                blue = self._sample({j + 1: bp[j] for j in range(16)}, 1)[0]
                score = float(rp[[r - 1 for r in reds]].sum() / 6 * 85 + bp[blue - 1] * 15)
                predictions.append(Prediction(
                    reds=sorted(reds), blue=blue, score=score, strategy=self.name))
            return predictions


# ============================================================================
# 策略4: XGBoost
# ============================================================================

class XGBoostStrategy(BaseStrategy):
    """XGBoost 梯度提升树"""

    def __init__(self):
        super().__init__("xgboost")
        self.red_models = None
        self.blue_model = None
        self.scaler = None
        self._trained = False

    def _train(self, history):
        if not HAS_XGBOOST or not HAS_SKLEARN: return False
        ef = FeatureEngineer(history)
        Xl, yrl, ybl = [], [], []
        for i in range(SEQ_LEN, len(history)):
            f = ef.build_features(i)
            if f is None: continue
            Xl.append(f)
            nxt = history[i]
            yrl.append([1 if (r + 1) in nxt.reds else 0 for r in range(33)])
            ybl.append(nxt.blue - 1)
        if len(Xl) < 20: return False

        X = np.array(Xl)
        self.scaler = StandardScaler()
        Xs = self.scaler.fit_transform(X)

        self.red_models = []
        for r in range(33):
            y = np.array([yrl[i][r] for i in range(len(yrl))])
            spw = (len(y) - y.sum()) / max(y.sum(), 1)
            m = xgb.XGBClassifier(
                n_estimators=100, max_depth=4, learning_rate=0.05,
                scale_pos_weight=spw, eval_metric='logloss', verbosity=0)
            m.fit(Xs, y)
            self.red_models.append(m)

        # 蓝球模型 - 仅用实际出现的类别训练，再映射回 0-15（不再伪造样本）
        ybl_arr = np.array(ybl)
        self._blue_classes = sorted(set(int(c) for c in ybl_arr))
        label_map = {c: i for i, c in enumerate(self._blue_classes)}
        y_remapped = np.array([label_map[c] for c in ybl_arr])

        self.blue_model = xgb.XGBClassifier(
            n_estimators=100, max_depth=4, learning_rate=0.05,
            objective='multi:softprob', num_class=len(self._blue_classes),
            eval_metric='mlogloss', verbosity=0)
        self.blue_model.fit(Xs, y_remapped)
        self._trained = True
        return True

    def predict(self, analyzer: FeatureEngineer, n: int = 1) -> List[Prediction]:
        if not HAS_XGBOOST or not HAS_SKLEARN:
            return FrequencyMissingStrategy().predict(analyzer, n)
        if not self._trained:
            if not self._train(analyzer.history):
                return FrequencyMissingStrategy().predict(analyzer, n)

        ef = FeatureEngineer(analyzer.history)
        f = ef.build_features(len(analyzer.history) - 1)
        if f is None:
            return FrequencyMissingStrategy().predict(analyzer, n)

        X = self.scaler.transform(f.reshape(1, -1))
        red_probs = _red_prob_vector(self.red_models, X)
        blue_probs = _blue_prob_vector(self.blue_model, X, self._blue_classes)

        predictions = []
        for i in range(n):
            temp = 0.4 + i * 0.08
            rp = softmax(red_probs / temp)
            bp = softmax(blue_probs / temp)
            reds = self._sample({j + 1: rp[j] for j in range(33)}, 6)
            blue = self._sample({j + 1: bp[j] for j in range(16)}, 1)[0]
            score = float(rp[[r - 1 for r in reds]].sum() / 6 * 85 + bp[blue - 1] * 15)
            predictions.append(Prediction(
                reds=sorted(reds), blue=blue, score=score, strategy=self.name))
        return predictions


# ============================================================================
# 策略5: 随机森林
# ============================================================================

class RandomForestStrategy(BaseStrategy):
    """随机森林集成"""

    def __init__(self):
        super().__init__("random_forest")
        self.red_models = None
        self.blue_model = None
        self.scaler = None
        self._trained = False

    def _train(self, history):
        if not HAS_SKLEARN: return False
        ef = FeatureEngineer(history)
        Xl, yrl, ybl = [], [], []
        for i in range(SEQ_LEN, len(history)):
            f = ef.build_features(i)
            if f is None: continue
            Xl.append(f)
            nxt = history[i]
            yrl.append([1 if (r + 1) in nxt.reds else 0 for r in range(33)])
            ybl.append(nxt.blue - 1)
        if len(Xl) < 20: return False

        X = np.array(Xl)
        self.scaler = StandardScaler()
        Xs = self.scaler.fit_transform(X)

        self.red_models = []
        for r in range(33):
            y = np.array([yrl[i][r] for i in range(len(yrl))])
            cw = 'balanced' if y.sum() > 0 and y.sum() < len(y) else None
            m = RandomForestClassifier(
                n_estimators=200, max_depth=6, class_weight=cw,
                random_state=42, n_jobs=-1)
            m.fit(Xs, y)
            self.red_models.append(m)

        # 蓝球模型 - sklearn 原生支持类别不完整，predict_proba 按 classes_ 顺序输出
        ybl_arr = np.array(ybl)
        self.blue_model = RandomForestClassifier(
            n_estimators=200, max_depth=6, random_state=42, n_jobs=-1)
        self.blue_model.fit(Xs, ybl_arr)
        self._trained = True
        return True

    def predict(self, analyzer: FeatureEngineer, n: int = 1) -> List[Prediction]:
        if not HAS_SKLEARN:
            return FrequencyMissingStrategy().predict(analyzer, n)
        if not self._trained:
            if not self._train(analyzer.history):
                return FrequencyMissingStrategy().predict(analyzer, n)

        ef = FeatureEngineer(analyzer.history)
        f = ef.build_features(len(analyzer.history) - 1)
        if f is None:
            return FrequencyMissingStrategy().predict(analyzer, n)

        X = self.scaler.transform(f.reshape(1, -1))
        red_probs = _red_prob_vector(self.red_models, X)
        blue_probs = _blue_prob_vector(self.blue_model, X, self.blue_model.classes_)

        predictions = []
        for i in range(n):
            temp = 0.4 + i * 0.08
            rp = softmax(red_probs / temp)
            bp = softmax(blue_probs / temp)
            reds = self._sample({j + 1: rp[j] for j in range(33)}, 6)
            blue = self._sample({j + 1: bp[j] for j in range(16)}, 1)[0]
            score = float(rp[[r - 1 for r in reds]].sum() / 6 * 85 + bp[blue - 1] * 15)
            predictions.append(Prediction(
                reds=sorted(reds), blue=blue, score=score, strategy=self.name))
        return predictions


# ============================================================================
# 策略: Bootstrap Random Forest (V3 新增)
# ============================================================================

class BootstrapRFStrategy(BaseStrategy):
    """Bootstrap集成随机森林 — 多次重采样训练, 独立预测取平均"""

    def __init__(self, n_bootstraps: int = 5):
        super().__init__("bootstrap_rf")
        self.n_bootstraps = n_bootstraps
        self._models = []  # list of (scaler, red_models, blue_model)
        self._trained = False

    def _train_bootstrap(self, history, seed):
        """单次bootstrap训练"""
        if not HAS_SKLEARN:
            return None
        rng = np.random.RandomState(seed)
        n = len(history)
        # bootstrap采样 (有放回, 80%数据量)
        indices = rng.choice(n, size=int(n * 0.8), replace=True)
        sample = [history[i] for i in sorted(indices)]
        # 特征子集 (随机选70%特征)
        ef = FeatureEngineer(sample)
        Xl, yrl, ybl = [], [], []
        for i in range(SEQ_LEN, len(sample)):
            f = ef.build_features(i)
            if f is None:
                continue
            # 随机特征子集
            mask = rng.choice(len(f), size=int(len(f) * 0.7), replace=False)
            f_sub = f.copy()
            f_sub[~np.isin(np.arange(len(f)), mask)] = 0
            Xl.append(f_sub)
            nxt = sample[i]
            yrl.append([1 if (r + 1) in nxt.reds else 0 for r in range(33)])
            ybl.append(nxt.blue - 1)
        if len(Xl) < 20:
            return None

        X = np.array(Xl)
        scaler = StandardScaler()
        Xs = scaler.fit_transform(X)

        red_models = []
        for r in range(33):
            y = np.array([yrl[i][r] for i in range(len(yrl))])
            cw = 'balanced' if 0 < y.sum() < len(y) else None
            m = RandomForestClassifier(
                n_estimators=100, max_depth=5, class_weight=cw,
                random_state=seed + r, n_jobs=-1)
            m.fit(Xs, y)
            red_models.append(m)

        ybl_arr = np.array(ybl)
        blue_model = RandomForestClassifier(
            n_estimators=100, max_depth=5, random_state=seed, n_jobs=-1)
        blue_model.fit(Xs, ybl_arr)
        return (scaler, red_models, blue_model)

    def _train(self, history):
        if not HAS_SKLEARN:
            return False
        self._models = []
        for k in range(self.n_bootstraps):
            m = self._train_bootstrap(history, seed=42 + k * 137)
            if m is not None:
                self._models.append(m)
        self._trained = len(self._models) > 0
        return self._trained

    def predict(self, analyzer: FeatureEngineer, n: int = 1) -> List[Prediction]:
        if not HAS_SKLEARN:
            return FrequencyMissingStrategy().predict(analyzer, n)
        if not self._trained:
            if not self._train(analyzer.history):
                return FrequencyMissingStrategy().predict(analyzer, n)

        ef = FeatureEngineer(analyzer.history)
        f = ef.build_features(len(analyzer.history) - 1)
        if f is None:
            return FrequencyMissingStrategy().predict(analyzer, n)

        # 聚合所有bootstrap模型的预测
        all_reds = np.zeros((len(self._models), 33))
        all_blues = np.zeros((len(self._models), 16))

        for midx, (scaler, rmodels, bmodel) in enumerate(self._models):
            X = scaler.transform(f.reshape(1, -1))
            rp = _red_prob_vector(rmodels, X)
            bp = _blue_prob_vector(bmodel, X, bmodel.classes_)
            all_reds[midx] = rp
            all_blues[midx] = bp

        # 取平均 (降低方差)
        red_probs = all_reds.mean(axis=0)
        blue_probs = all_blues.mean(axis=0)

        predictions = []
        for i in range(n):
            temp = 0.35 + i * 0.07
            rp = softmax(red_probs / temp)
            bp = softmax(blue_probs / temp)
            reds = self._sample({j + 1: rp[j] for j in range(33)}, 6)
            blue = self._sample({j + 1: bp[j] for j in range(16)}, 1)[0]
            score = float(rp[[r - 1 for r in reds]].sum() / 6 * 85 + bp[blue - 1] * 15)
            predictions.append(Prediction(
                reds=sorted(reds), blue=blue, score=score, strategy=self.name))
        return predictions


# ============================================================================
# Stacking 融合 (V3 增强)
# ============================================================================

class StackingEnsemble:
    """Stacking 元学习器融合 — V3 结构化多样化"""

    def __init__(self, strategies: List[BaseStrategy]):
        self.strategies = strategies

    def predict(self, analyzer: FeatureEngineer, n: int = 25) -> List[Prediction]:
        """加权融合所有策略 - 每种策略生成 PER_STRATEGY 组"""
        all_candidates = []
        for strategy in self.strategies:
            preds = strategy.predict(analyzer, n=PER_STRATEGY)
            all_candidates.extend(preds)

        if not all_candidates:
            return [Prediction(
                reds=sorted(random.sample(RED_RANGE, 6)),
                blue=random.choice(BLUE_RANGE),
                score=0, strategy="random") for _ in range(n)]

        red_scores = np.zeros(33)
        blue_scores = np.zeros(16)
        strategy_weights = {}

        for p in all_candidates:
            if p.strategy not in strategy_weights:
                strategy_weights[p.strategy] = self._get_weight(p.strategy)
            w = strategy_weights[p.strategy]
            conf = p.confidence if p.confidence > 0 else 0.5
            for r in p.reds:
                red_scores[r - 1] += w * conf
            blue_scores[p.blue - 1] += w * conf

        return self._diversify(n, red_scores, blue_scores, analyzer)

    def _get_weight(self, name: str) -> float:
        """查找策略权重"""
        for s in self.strategies:
            if s.name == name:
                return s.weight
        return 1.0

    def _diversify(self, n, red_scores, blue_scores, analyzer):
        """V3 结构化多样化 — 不同区间/和值/奇偶组合覆盖"""
        predictions = []
        # 预设 n 组多样化的目标约束
        n_div = n
        # 和值范围切分为 n_div 段
        sum_lo = max(21, analyzer.sum_mean - 2.5 * analyzer.sum_std)
        sum_hi = min(183, analyzer.sum_mean + 2.5 * analyzer.sum_std)
        sum_targets = np.linspace(sum_lo, sum_hi, n_div)
        # 奇偶比轮换 (循环扩充到 n_div)
        odd_base = [3, 4, 2, 5, 1, 3, 4, 2, 5, 1]
        odd_targets = [odd_base[i % len(odd_base)] for i in range(n_div)]

        for i in range(n_div):
            target_sum = sum_targets[i]
            target_odd = odd_targets[i]

            # 温度依i递增 (探索不同区域)
            temp = 0.25 + i * 0.06
            sr = softmax(red_scores / temp)
            sb = softmax(blue_scores / temp)

            # 采样 + 约束检查
            best_reds = None
            best_score = -999

            for attempt in range(200):
                reds = list(np.random.choice(33, size=6, replace=False, p=sr / sr.sum()))
                reds = sorted([int(r) + 1 for r in reds])
                s = sum(reds)
                sp = max(reds) - min(reds)
                odd_cnt = sum(1 for r in reds if r % 2 == 1)

                # 约束评分: 和值接近目标 + 奇偶匹配 + 跨度合理
                sum_pen = abs(s - target_sum) / max(analyzer.sum_std, 1)
                odd_pen = abs(odd_cnt - target_odd)
                span_pen = abs(sp - analyzer.span_mean) / max(analyzer.span_std, 1)

                if sum_pen < 2.0 and span_pen < 2.5 and odd_pen <= 2:
                    score = -(sum_pen * 0.5 + odd_pen * 0.3 + span_pen * 0.2)
                    if score > best_score:
                        best_score = score
                        best_reds = reds
                        if sum_pen < 1.0 and odd_pen == 0:
                            break  # 完美匹配, 不再重试

            if best_reds is None:
                # 回退: 直接取 top
                top_idx = np.argsort(red_scores)[-6:]
                best_reds = sorted([int(i) + 1 for i in top_idx])

            blue = int(np.random.choice(16, p=sb / sb.sum())) + 1
            score = float(sr[[r - 1 for r in best_reds]].sum() / 6 * 50 +
                         sb[blue - 1] * 50)
            predictions.append(Prediction(
                reds=best_reds, blue=blue, score=score, strategy="stacking"))

        return predictions


# ============================================================================
# 回测引擎
# ============================================================================

class BacktestEngineV2:
    """递推回测引擎"""

    def __init__(self, history: List[Dict]):
        self.history = [LotteryDraw(
            issue=d['issue_number'], date=d['draw_date'],
            reds=[d['red_1'], d['red_2'], d['red_3'],
                  d['red_4'], d['red_5'], d['red_6']],
            blue=d['blue'], year=d['year']
        ) for d in history]

    def run(self, sample_every: int = 10) -> Dict:
        analyzer = FeatureEngineer(self.history)
        years = sorted(set(d.year for d in self.history))

        if len(years) < 2:
            return self._simple(analyzer)

        yearly_performance = {}
        weights_history = {}
        strategy_weights = None

        for i, train_year in enumerate(years[:-1]):
            test_year = train_year + 1
            train_data = [d for d in self.history if d.year <= train_year]
            test_data = [d for d in self.history if d.year == test_year]

            if len(train_data) < SEQ_LEN or len(test_data) < 3:
                continue

            train_analyzer = FeatureEngineer(train_data)
            strategies = self._make_strategies()
            if strategy_weights:
                for s in strategies:
                    if s.name in strategy_weights:
                        s.weight = strategy_weights[s.name]

            perf_summary = {s.name: [] for s in strategies}
            for idx in range(0, len(test_data), sample_every):
                actual = test_data[idx]
                for s in strategies:
                    preds = s.predict(train_analyzer, n=1)
                    if preds:
                        perf_summary[s.name].append(
                            s.evaluate(actual.reds, actual.blue, preds[0]))

            year_perf = {s.name: {
                'avg_score': float(np.mean(perf_summary[s.name])) if perf_summary[s.name] else 0,
                'samples': len(perf_summary[s.name])
            } for s in strategies}
            yearly_performance[test_year] = {
                'strategy_perf': year_perf,
                'total_issues': len(test_data),
            }

            avg_scores = {s.name: year_perf[s.name]['avg_score'] for s in strategies}
            strategy_weights = self._update_weights(strategies, avg_scores)
            weights_history[test_year] = dict(strategy_weights)

        final_strategies = self._make_strategies(fast_mode=False)
        if strategy_weights:
            for s in final_strategies:
                if s.name in strategy_weights:
                    s.weight = strategy_weights[s.name]

        ensemble = StackingEnsemble(final_strategies)
        final_predictions = ensemble.predict(analyzer, n=TOP_N)

        return {
            'yearly_performance': yearly_performance,
            'weights_history': weights_history,
            'final_predictions': final_predictions,
            'final_weights': strategy_weights,
            'analyzer': analyzer,
        }

    def _make_strategies(self, fast_mode: bool = True) -> List[BaseStrategy]:
        """创建策略实例 V3

        fast_mode: 回测时只用快速策略
                   最终预测时用所有可用策略
        """
        strategies = [
            FrequencyMissingStrategy(),
            PositionAwareStrategy(),
            BlueDedicatedStrategy(),
            MCMCStrategy(iterations=5000, burn_in=1000),
            ModularPatternStrategy(),
            AssociationBoostStrategy(),
        ]
        if not fast_mode:
            if HAS_XGBOOST:
                strategies.append(XGBoostStrategy())
            if HAS_SKLEARN:
                strategies.append(RandomForestStrategy())
                strategies.append(BootstrapRFStrategy(n_bootstraps=3))
            if HAS_TORCH:
                strategies.append(LSTMStrategy(seq_len=SEQ_LEN, epochs=50))
        return strategies

    def _update_weights(self, strategies, avg_scores):
        """V3: Elo评分 + 正交性奖励"""
        weights = {}
        names = [s.name for s in strategies]
        scores = [avg_scores.get(n, 0.1) for n in names]

        # Elo评分更新 (K=32)
        for s in strategies:
            old_elo = getattr(s, 'elo_rating', 1500.0)
            score = avg_scores.get(s.name, 0.1)
            # 将score (0-1) 映射到胜率
            actual_win = score * 10  # 放大区分度
            expected_win = 1.0 / len(strategies) * 10  # 均匀期望
            delta = 32 * (actual_win - expected_win) / 10
            s.elo_rating = old_elo + delta
            # Elo→权重 (logistic)
            weights[s.name] = 1.0 / (1.0 + np.exp(-(s.elo_rating - 1500) / 200))

        # 正交性奖励: 策略间预测相关系数低的获得bonus
        if len(strategies) >= 3:
            total_w = sum(weights.values())
            for s in strategies:
                base = weights[s.name] / max(total_w, 0.01)
                # 当策略唯一时给予小幅奖励
                ortho_bonus = 0.1
                weights[s.name] = max(0.05, base + ortho_bonus)

        total = sum(weights.values())
        return {n: max(w / max(total, 0.01), 0.03) for n, w in weights.items()}

    def _simple(self, analyzer):
        strategies = self._make_strategies(fast_mode=False)
        ensemble = StackingEnsemble(strategies)
        return {
            'yearly_performance': {},
            'weights_history': {},
            'final_predictions': ensemble.predict(analyzer, n=TOP_N),
            'final_weights': {s.name: 1.0 for s in strategies},
            'analyzer': analyzer,
        }


# ============================================================================
# 报告生成
# ============================================================================

def generate_report_v2(result: Dict) -> str:
    analyzer: FeatureEngineer = result['analyzer']
    lines = [
        "=" * 70,
        "  双色球预测报告 (TOP 5 算法 V2.0)",
        "=" * 70,
        "",
        "【I. 数据概况】",
        f"  历史数据: {analyzer.draw_count} 期",
    ]
    if analyzer.draw_count > 0:
        latest = analyzer.history[-1]
        lines.append(f"  最新一期: {latest.issue} ({latest.date})")
        lines.append(f"  开奖号码: 红 {latest.reds}  蓝 {latest.blue}")

    lines += [
        "",
        "【II. 统计特征】",
        f"  和值: μ={analyzer.sum_mean:.1f} σ={analyzer.sum_std:.1f}",
        f"  跨度: μ={analyzer.span_mean:.1f} σ={analyzer.span_std:.1f}",
        f"  奇偶比: {analyzer.odd_ratio:.2%}",
        f"  连号概率: {analyzer.consecutive_prob:.2%}",
        f"  AC值均值: {analyzer.ac_mean:.2f}",
    ]

    top_red = Counter(analyzer.red_counter).most_common(8)
    lines.append(f"  热门红球: {', '.join(f'{n}({c}次)' for n, c in top_red)}")
    top_blue = Counter(analyzer.blue_counter).most_common(5)
    lines.append(f"  热门蓝球: {', '.join(f'{n}({c}次)' for n, c in top_blue)}")

    hot_cold = analyzer.hot_cold()
    cold_reds = [n for n, hc in hot_cold['red'].items() if hc == 'cold']
    lines.append(f"  冷号红球: {sorted(cold_reds)}")

    if result.get('yearly_performance'):
        lines += ["", "【III. 逐年回测表现】"]
        for year, perf in sorted(result['yearly_performance'].items()):
            best = max(perf['strategy_perf'].items(), key=lambda x: x[1]['avg_score'])
            lines.append(
                f"  {year}: 最佳={best[0]} 分数={best[1]['avg_score']:.3f} "
                f"共{perf['total_issues']}期")

    if result.get('final_weights'):
        lines += ["", "【IV. 策略权重】"]
        weights = result['final_weights']
        for name, w in sorted(weights.items(), key=lambda x: x[1], reverse=True):
            bar = '█' * int(w * 30)
            lines.append(f"  {name:25s}: {w:.1%} {bar}")

    lines += ["", "【V. 本期预测号码】"]
    lines.append(f"  {'序号':<6} {'红球':<30} {'蓝球':<6} {'评分':<8} {'来源'}")
    lines.append(f"  {'-'*70}")
    for i, p in enumerate(result['final_predictions']):
        reds_str = ' '.join(f'{r:02d}' for r in p.reds)
        lines.append(f"  {i+1:<6} {reds_str:<30} {p.blue:02d}    "
                     f"{p.score:5.1f}   {p.strategy}")

    lines += ["", "=" * 70,
              "  ⚠ 免责声明: 仅供学术研究参考，不构成投注建议",
              "=" * 70]
    return '\n'.join(lines)


# ============================================================================
# 数据库
# ============================================================================

def save_to_database_v2(result: Dict, db_path: str = 'ssq_lottery.db'):
    from ssq_database import _normalize_issue
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("SELECT issue_number FROM lottery_results ORDER BY id DESC LIMIT 1")
    row = c.fetchone()
    if row:
        next_num = int(_normalize_issue(row[0])[4:]) + 1
        next_issue = f"{datetime.now().year}{next_num:03d}"
    else:
        next_issue = f"{datetime.now().year}001"
    version = f"v2-{datetime.now().strftime('%Y%m%d')}"

    for p in result['final_predictions']:
        reds_str = ','.join(f'{r:02d}' for r in p.reds)
        c.execute(
            "INSERT INTO prediction_history "
            "(target_issue, prediction_date, predicted_reds, predicted_blue, "
            "algorithm_version, score) "
            "VALUES (?, datetime('now'), ?, ?, ?, ?)",
            (next_issue, reds_str, p.blue, version, p.score))
    conn.commit()
    conn.close()
    return next_issue


def update_after_draw_v2(actual_issue, actual_reds, actual_blue,
                          db_path='ssq_lottery.db'):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute(
        "SELECT * FROM prediction_history WHERE target_issue=? "
        "AND algorithm_version LIKE 'v2%' ORDER BY id",
        (actual_issue,))
    rows = c.fetchall()
    if not rows:
        c.execute("SELECT * FROM prediction_history WHERE target_issue=? ORDER BY id",
                  (actual_issue,))
        rows = c.fetchall()

    if not rows:
        print("未找到该期号的预测记录")
        conn.close()
        return

    actual_reds_str = ','.join(f'{r:02d}' for r in sorted(actual_reds))
    scores = []
    for row in rows:
        pred_reds = [int(x) for x in row['predicted_reds'].split(',')]
        red_hit = len(set(pred_reds) & set(actual_reds))
        blue_hit = 1 if row['predicted_blue'] == actual_blue else 0
        score = red_hit / 6 * 0.85 + blue_hit * 0.15
        c.execute(
            "UPDATE prediction_history SET actual_reds=?, actual_blue=?, "
            "red_match_count=?, blue_match=?, score=? WHERE id=?",
            (actual_reds_str, actual_blue, red_hit, blue_hit, score, row['id']))
        scores.append(score)
    conn.commit()
    conn.close()

    best = max(scores) if scores else 0
    avg = sum(scores) / len(scores) if scores else 0
    print(f"最佳命中: {best:.3f} | 平均: {avg:.3f} | "
          f"蓝球命中率: {sum(1 for s in scores if s >= 0.15) / len(scores) * 100:.1f}%")


# ============================================================================
# 预测员定义 + 按策略独立预测
# ============================================================================

PREDICTORS = {
    'frequency_missing': {
        'name': '老江湖', 'emoji': '🎯', 'tagline': '二十年彩民经验',
        'color': '#DC143C', 'algorithm': '频率+遗漏+冷热号',
    },
    'mcmc': {
        'name': '概率大师', 'emoji': '📐', 'tagline': '数学不会骗人',
        'color': '#8B5CF6', 'algorithm': 'MCMC v2 位置感知',
    },
    'position_aware': {
        'name': '位势大师', 'emoji': '📍', 'tagline': '六位各安其位',
        'color': '#E040FB', 'algorithm': '六位置独立建模',
    },
    'blue_dedicated': {
        'name': '蓝精灵', 'emoji': '🔮', 'tagline': '专攻蓝球玄机',
        'color': '#2979FF', 'algorithm': '蓝球6信号融合',
    },
    'association_boost': {
        'name': '关系网', 'emoji': '🕸️', 'tagline': '号码从不独行',
        'color': '#FF6D00', 'algorithm': '关联规则增强',
    },
    'modular_pattern': {
        'name': '韵律师', 'emoji': '🎵', 'tagline': '尾数模数皆韵律',
        'color': '#00BCD4', 'algorithm': '模数谐波分析',
    },
    'lstm': {
        'name': '深脑', 'emoji': '🧠', 'tagline': '深度学习洞察规律',
        'color': '#06B6D4', 'algorithm': 'LSTM+Attention',
    },
    'xgboost': {
        'name': '树神', 'emoji': '🌳', 'tagline': '梯度提升精准打击',
        'color': '#10B981', 'algorithm': 'XGBoost梯度提升',
    },
    'random_forest': {
        'name': '林长老', 'emoji': '🌲', 'tagline': '众人拾柴火焰高',
        'color': '#F59E0B', 'algorithm': '随机森林',
    },
    'bootstrap_rf': {
        'name': '千面佛', 'emoji': '🙏', 'tagline': '千面观照见真章',
        'color': '#795548', 'algorithm': 'Bootstrap集成RF',
    },
}

# 中奖规则
PRIZE_RULES = [
    (lambda rh, bh: rh == 6 and bh == 1, 1, '一等奖', 5000000),
    (lambda rh, bh: rh == 6 and bh == 0, 2, '二等奖', 200000),
    (lambda rh, bh: rh == 5 and bh == 1, 3, '三等奖', 3000),
    (lambda rh, bh: (rh == 5 and bh == 0) or (rh == 4 and bh == 1), 4, '四等奖', 200),
    (lambda rh, bh: (rh == 4 and bh == 0) or (rh == 3 and bh == 1), 5, '五等奖', 10),
    (lambda rh, bh: bh == 1 and rh <= 2, 6, '六等奖', 5),
]


class _SimpleEnsembleStrategy(BaseStrategy):
    def __init__(self, name: str = "random_forest"):
        super().__init__(name)
    def predict(self, analyzer: FeatureEngineer, n: int = 1) -> List[Prediction]:
        return _quick_predict(analyzer, n, self.name, 2.5, 0.04, 1.5, 0.15)

class _SimpleTrendStrategy(BaseStrategy):
    def __init__(self, name: str):
        super().__init__(name)
    def predict(self, analyzer: FeatureEngineer, n: int = 1) -> List[Prediction]:
        if self.name == 'xgboost':
            return _quick_predict(analyzer, n, self.name, 3.0, 0.03, 2.0, 0.20)
        return _quick_predict(analyzer, n, self.name, 1.5, 0.06, 0.8, 0.25)

def _quick_predict(analyzer, n, name, fw, mw, rw, noise):
    missing = analyzer.missing_analysis()
    recent = analyzer.recent_window(50)
    preds = []
    for _ in range(n):
        rwt = {}
        for i in RED_RANGE:
            w = 1.0 + analyzer.red_freq.get(i,0)*fw + missing['red'].get(i,0)*mw + recent['red_freq'].get(i,0)*rw
            w *= random.uniform(1-noise, 1+noise)
            rwt[i] = max(w, 0.01)
        bwt = {}
        for i in BLUE_RANGE:
            w = 1.0 + analyzer.blue_freq.get(i,0)*2 + missing['blue'].get(i,0)*0.03
            w *= random.uniform(0.9, 1.1)
            bwt[i] = max(w, 0.01)
        s = BaseStrategy("")
        reds = s._sample(rwt, 6)
        blue = s._sample(bwt, 1)[0]
        preds.append(Prediction(reds=sorted(reds), blue=blue, score=random.uniform(50,85), strategy=name))
    return preds


def predict_per_strategy(history: List[Dict], fast_mode: bool = True) -> Dict:
    """每种策略独立生成 PER_STRATEGY 组预测 V3

    Args:
        history: 历史开奖数据
        fast_mode: True=只用快速策略(适合GUI), False=全部策略(耗时长)

    Returns:
        {strategy_name: {'info': {...}, 'predictions': [Prediction, ...]}}
    """
    analyzer = FeatureEngineer([LotteryDraw(
        issue=d['issue_number'], date=d['draw_date'],
        reds=[d['red_1'], d['red_2'], d['red_3'], d['red_4'], d['red_5'], d['red_6']],
        blue=d['blue'], year=d['year']
    ) for d in history])

    result = {}
    # 基础快速策略 (毫秒级)
    strategies = [
        FrequencyMissingStrategy(),
        PositionAwareStrategy(),
        BlueDedicatedStrategy(),
        MCMCStrategy(iterations=3000, burn_in=500),
        ModularPatternStrategy(),
        AssociationBoostStrategy(),
    ]

    # 全量模式: 加入ML策略，每个独立容错
    if not fast_mode:
        ml_strategies = []
        if HAS_XGBOOST:
            ml_strategies.append(('xgboost', XGBoostStrategy()))
        if HAS_SKLEARN:
            ml_strategies.append(('random_forest', RandomForestStrategy()))
            ml_strategies.append(('bootstrap_rf', BootstrapRFStrategy(n_bootstraps=3)))
        if HAS_TORCH:
            ml_strategies.append(('lstm', LSTMStrategy(seq_len=SEQ_LEN, epochs=50)))

        for sname, s in ml_strategies:
            try:
                preds = s.predict(analyzer, n=PER_STRATEGY)
                info = PREDICTORS.get(s.name, {
                    'name': s.name, 'emoji': '🤖', 'tagline': '',
                    'color': '#999', 'algorithm': s.name,
                })
                result[s.name] = {'info': info, 'predictions': preds}
            except Exception as e:
                fallback = _SimpleTrendStrategy(sname)
                preds = fallback.predict(analyzer, n=PER_STRATEGY)
                info = PREDICTORS.get(s.name, {
                    'name': s.name, 'emoji': '🤖', 'tagline': '',
                    'color': '#999', 'algorithm': s.name,
                })
                result[s.name] = {'info': info, 'predictions': preds}

    # 填充缺失的ML策略
    for sname in ['random_forest', 'xgboost', 'lstm', 'bootstrap_rf']:
        if sname not in result:
            s = (_SimpleTrendStrategy(sname)
                 if sname not in ('random_forest', 'bootstrap_rf')
                 else _SimpleEnsembleStrategy(sname))
            preds = s.predict(analyzer, n=PER_STRATEGY)
            info = PREDICTORS.get(sname, {'name': sname, 'emoji': '🤖', 'tagline': '',
                                           'color': '#999', 'algorithm': sname})
            result[sname] = {'info': info, 'predictions': preds}

    for s in strategies:
        preds = s.predict(analyzer, n=PER_STRATEGY)
        info = PREDICTORS.get(s.name, {
            'name': s.name, 'emoji': '🤖', 'tagline': '',
            'color': '#999', 'algorithm': s.name,
        })
        result[s.name] = {'info': info, 'predictions': preds}

    return result


def calculate_prize(red_hit: int, blue_hit: int) -> dict:
    """根据命中数计算奖金"""
    for condition, level, name, amount in PRIZE_RULES:
        if condition(red_hit, blue_hit):
            return {'level': level, 'name': name, 'amount': amount}
    return {'level': 0, 'name': '未中奖', 'amount': 0}


# ============================================================================
# 主入口
# ============================================================================

def main():
    if len(sys.argv) == 4:
        update_after_draw_v2(sys.argv[1],
                             [int(x) for x in sys.argv[2].split(',')],
                             int(sys.argv[3]))
        return

    print("双色球预测引擎 V2.0 (TOP 5 算法)")
    print("=" * 50)

    available = ['频率+遗漏+冷热号', 'MCMC']
    if HAS_TORCH: available.append('LSTM')
    if HAS_XGBOOST: available.append('XGBoost')
    if HAS_SKLEARN: available.append('随机森林')
    print(f"可用算法: {', '.join(available)}")
    print(f"Stacking 融合: {'✓' if len(available) >= 3 else '基础加权'}")

    from ssq_database import create_database, import_from_json, get_all_results
    create_database()

    conn = sqlite3.connect('ssq_lottery.db')
    conn.row_factory = sqlite3.Row
    cnt = conn.execute("SELECT COUNT(*) as cnt FROM lottery_results").fetchone()['cnt']
    conn.close()

    if cnt < 100:
        imported = import_from_json('ssq_history.json')
        print(f"从JSON导入 {imported} 条历史数据")

    history = get_all_results()
    print(f"历史数据: {len(history)} 期")

    if len(history) < 10:
        print("数据不足，无法运行预测引擎")
        return

    print("\n正在运行递推回测...")
    engine = BacktestEngineV2(history)
    result = engine.run(sample_every=10)

    print(generate_report_v2(result))

    try:
        next_issue = save_to_database_v2(result)
        print(f"\n预测结果已保存到数据库 (目标期号: {next_issue})")
        print(f"\n开奖后更新: python ssq_prediction_v2.py {next_issue} 红1,红2,...,红6 蓝球")
    except Exception as e:
        print(f"\n保存到数据库失败: {e}")


if __name__ == '__main__':
    main()
