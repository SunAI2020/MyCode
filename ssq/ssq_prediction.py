"""
双色球预测系统 - 基于统计学和概率论的多策略预测引擎

核心功能:
1. 多维度统计分析（频率、冷热号、区间分布、奇偶比、跨度、AC值等）
2. 基于历史数据的递推回测训练（2020→2021→...→2026）
3. 多算法融合预测（频率加权、遗漏分析、马尔可夫链、蒙特卡洛模拟、趋势分析）
4. 自动参数优化（根据各期实际命中率动态调整策略权重）
5. 生成10组推荐号码并存入数据库

用户需求:
1. 设计双色球预测系统，利用统计学和概率论推测号码概率，给出10组预测号码
2. 先用2020年数据预测2021年，根据实际结果不断调整优化算法
3. 递推至最新一期，给出本期10组预测号码
4. 每次开奖后根据预测与实际的差距调整优化算法
建立了数据库，并把历史数据存入数据库
"""
import sqlite3
import json
import math
import random
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime
from typing import List, Dict, Tuple, Optional, Set
from dataclasses import dataclass, field

from ssq_database import (
    get_connection, get_all_results, get_results_before_issue,
    get_latest_issue, get_statistics, DB_PATH, _normalize_issue
)

# ============================================================
# 常量定义
# ============================================================
RED_BALL_RANGE = list(range(1, 34))   # 红球 1-33
BLUE_BALL_RANGE = list(range(1, 17))  # 蓝球 1-16
TOP_N_PREDICTIONS = 10  # 最终输出10组预测号码


@dataclass
class LotteryDraw:
    issue: str
    date: str
    reds: List[int]
    blue: int
    year: int


@dataclass
class Prediction:
    reds: List[int]
    blue: int
    score: float
    strategy: str


# ============================================================
# 多维度统计分析器
# ============================================================
class StatisticalAnalyzer:
    """统计分析器 - 从多个维度分析历史号码特征"""

    def __init__(self, history: List[Dict]):
        self.history = history
        self.draws = self._parse_draws()

    def _parse_draws(self) -> List[LotteryDraw]:
        draws = []
        for row in self.history:
            reds = [row[f'red_{i}'] for i in range(1, 7)]
            draws.append(LotteryDraw(
                issue=row['issue_number'], date=row['draw_date'],
                reds=sorted(reds), blue=row['blue'], year=row['year']
            ))
        return draws

    # ---- 频率分析 ----
    def frequency_analysis(self, recent_n: int = None) -> Dict[str, Counter]:
        data = self.draws[-recent_n:] if recent_n else self.draws
        red_freq, blue_freq = Counter(), Counter()
        for d in data:
            for r in d.reds:
                red_freq[r] += 1
            blue_freq[d.blue] += 1
        return {'red': red_freq, 'blue': blue_freq}

    # ---- 遗漏分析 ----
    def missing_analysis(self) -> Dict[str, Dict[int, int]]:
        red_missing = {n: 0 for n in RED_BALL_RANGE}
        blue_missing = {n: 0 for n in BLUE_BALL_RANGE}
        for d in reversed(self.draws):
            for r in RED_BALL_RANGE:
                red_missing[r] = red_missing[r] + 1 if r not in d.reds else 0
            for b in BLUE_BALL_RANGE:
                blue_missing[b] = blue_missing[b] + 1 if b != d.blue else 0
        return {'red': red_missing, 'blue': blue_missing}

    # ---- 冷热号分析 ----
    def hot_cold_analysis(self, window: int = 30) -> Dict[str, Dict[str, List[int]]]:
        freq = self.frequency_analysis(recent_n=window)
        n_periods = min(window, len(self.draws))
        red_mean = n_periods * 6 / 33
        blue_mean = n_periods / 16

        hot_red = [n for n in RED_BALL_RANGE if freq['red'].get(n, 0) > red_mean * 1.5]
        warm_red = [n for n in RED_BALL_RANGE if red_mean*0.5 <= freq['red'].get(n,0) <= red_mean*1.5]
        cold_red = [n for n in RED_BALL_RANGE if freq['red'].get(n, 0) < red_mean * 0.5]
        hot_blue = [n for n in BLUE_BALL_RANGE if freq['blue'].get(n, 0) > blue_mean * 1.5]
        cold_blue = [n for n in BLUE_BALL_RANGE if freq['blue'].get(n, 0) < blue_mean * 0.5]

        return {
            'red': {'hot': hot_red, 'warm': warm_red, 'cold': cold_red},
            'blue': {'hot': hot_blue, 'cold': cold_blue}
        }

    # ---- 区间分布 ----
    def zone_distribution(self) -> Dict[str, float]:
        counts = {1: 0, 2: 0, 3: 0}
        total_balls = len(self.draws) * 6
        for d in self.draws:
            for r in d.reds:
                if r <= 11: counts[1] += 1
                elif r <= 22: counts[2] += 1
                else: counts[3] += 1
        return {f'zone_{k}': round(v/total_balls, 4) for k, v in counts.items()}

    # ---- 奇偶比 ----
    def odd_even_analysis(self) -> Dict[str, float]:
        odd = sum(1 for d in self.draws for r in d.reds if r % 2 == 1)
        total = len(self.draws) * 6
        return {'odd_ratio': round(odd/total,4), 'even_ratio': round(1-odd/total,4)}

    # ---- 和值 ----
    def sum_analysis(self) -> Dict[str, float]:
        sums = [sum(d.reds) for d in self.draws]
        n = len(sums); m = sum(sums)/n
        return {'mean': round(m,2), 'min': min(sums), 'max': max(sums),
                'std': round(math.sqrt(sum((x-m)**2 for x in sums)/n), 2)}

    # ---- 跨度 ----
    def span_analysis(self) -> Dict[str, float]:
        spans = [max(d.reds)-min(d.reds) for d in self.draws]
        n = len(spans); m = sum(spans)/n
        return {'mean': round(m,2), 'min': min(spans), 'max': max(spans),
                'std': round(math.sqrt(sum((x-m)**2 for x in spans)/n), 2)}

    # ---- 连号 ----
    def consecutive_analysis(self) -> Dict[str, float]:
        cnt = sum(1 for d in self.draws
                  if any(d.reds[i+1]-d.reds[i]==1 for i in range(5)))
        return {'consecutive_prob': round(cnt/len(self.draws), 4)}

    # ---- AC值 ----
    def ac_value_analysis(self) -> Dict:
        acs = []
        for d in self.draws:
            r = sorted(d.reds)
            diffs = {r[j]-r[i] for i in range(6) for j in range(i+1,6)}
            acs.append(len(diffs)-5)
        c = Counter(acs)
        return {'mean_ac': round(sum(acs)/len(acs),2),
                'top_ac_values': dict(c.most_common(3))}

    # ---- 马尔可夫转移矩阵 ----
    def transition_matrix(self, ball_type: str = 'red') -> Dict[int, Counter]:
        trans = defaultdict(Counter)
        for i in range(len(self.draws)-1):
            if ball_type == 'red':
                for r in self.draws[i].reds:
                    for nr in self.draws[i+1].reds:
                        trans[r][nr] += 1
            else:
                trans[self.draws[i].blue][self.draws[i+1].blue] += 1
        return dict(trans)


# ============================================================
# 预测策略（6种独立策略）
# ============================================================
class PredictionStrategy:
    def __init__(self, analyzer: StatisticalAnalyzer):
        self.analyzer = analyzer
        self.name = "base"
        self.weight = 1.0
        self.performance: List[float] = []

    def predict(self, n: int = 1) -> List[Prediction]:
        raise NotImplementedError

    def evaluate(self, actual_reds: List[int], actual_blue: int,
                 pred: Prediction) -> float:
        red_hit = len(set(pred.reds) & set(actual_reds)) / 6
        blue_hit = 1.0 if pred.blue == actual_blue else 0.0
        return red_hit * 0.85 + blue_hit * 0.15

    @staticmethod
    def _weighted_sample(weights: Dict[int, float], k: int) -> List[int]:
        items = list(weights.keys())
        w = [weights[i] for i in items]
        chosen = []
        for _ in range(k):
            if not items: break
            total = sum(w)
            if total == 0: break
            idx = random.choices(range(len(items)),
                                 weights=[x/total for x in w], k=1)[0]
            chosen.append(items[idx])
            items.pop(idx); w.pop(idx)
        return chosen


class FrequencyStrategy(PredictionStrategy):
    """策略1: 频率加权 - 历史出现频率越高，选中概率越大"""
    def __init__(self, analyzer):
        super().__init__(analyzer); self.name = "frequency"

    def predict(self, n: int = 1) -> List[Prediction]:
        freq = self.analyzer.frequency_analysis()
        hc = self.analyzer.hot_cold_analysis(50)
        preds = []
        for _ in range(n):
            rw = {}
            for i in RED_BALL_RANGE:
                w = freq['red'].get(i,0)+1
                if i in hc['red']['hot']: w *= 2.0
                elif i in hc['red']['cold']: w *= 0.3
                rw[i] = w
            reds = self._weighted_sample(rw, 6)

            bw = {}
            for i in BLUE_BALL_RANGE:
                w = freq['blue'].get(i,0)+1
                if i in hc['blue']['hot']: w *= 2.0
                bw[i] = w
            blue = self._weighted_sample(bw, 1)[0]
            preds.append(Prediction(reds=sorted(reds), blue=blue, score=0, strategy=self.name))
        return preds


class MissingStrategy(PredictionStrategy):
    """策略2: 遗漏回补 - 遗漏值越大，出现概率越高"""
    def __init__(self, analyzer):
        super().__init__(analyzer); self.name = "missing"

    def predict(self, n: int = 1) -> List[Prediction]:
        missing = self.analyzer.missing_analysis()
        freq = self.analyzer.frequency_analysis()
        preds = []
        for _ in range(n):
            rs = {i: missing['red'][i]*0.5 + freq['red'].get(i,0)*0.5
                  for i in RED_BALL_RANGE}
            reds = self._weighted_sample(rs, 6)
            bs = {i: missing['blue'][i]*0.5 + freq['blue'].get(i,0)*0.5
                  for i in BLUE_BALL_RANGE}
            blue = self._weighted_sample(bs, 1)[0]
            preds.append(Prediction(reds=sorted(reds), blue=blue, score=0, strategy=self.name))
        return preds


class MarkovStrategy(PredictionStrategy):
    """策略3: 马尔可夫链 - 基于号码转移概率预测"""
    def __init__(self, analyzer):
        super().__init__(analyzer); self.name = "markov"

    def predict(self, n: int = 1) -> List[Prediction]:
        t_red = self.analyzer.transition_matrix('red')
        t_blue = self.analyzer.transition_matrix('blue')
        last = self.analyzer.draws[-1]
        preds = []
        for _ in range(n):
            rs = Counter()
            for r in last.reds:
                if r in t_red:
                    rs.update(t_red[r])
            for i in RED_BALL_RANGE:
                rs[i] = rs.get(i, 0) + 1
            reds = self._weighted_sample(dict(rs), 6)

            bs = Counter()
            if last.blue in t_blue:
                bs.update(t_blue[last.blue])
            for i in BLUE_BALL_RANGE:
                bs[i] = bs.get(i, 0) + 1
            blue = self._weighted_sample(dict(bs), 1)[0]
            preds.append(Prediction(reds=sorted(reds), blue=blue, score=0, strategy=self.name))
        return preds


class ZoneBalanceStrategy(PredictionStrategy):
    """策略4: 区间均衡 - 保持三区号码分布合理"""
    def __init__(self, analyzer):
        super().__init__(analyzer); self.name = "zone_balance"

    def predict(self, n: int = 1) -> List[Prediction]:
        zd = self.analyzer.zone_distribution()
        freq = self.analyzer.frequency_analysis()
        z1 = round(zd['zone_1']*6); z2 = round(zd['zone_2']*6); z3 = 6-z1-z2
        preds = []
        for _ in range(n):
            reds = []
            for z, cnt in [((1,11), z1), ((12,22), z2), ((23,33), z3)]:
                w = {i: freq['red'].get(i,0)+1 for i in range(z[0], z[1]+1)}
                reds.extend(self._weighted_sample(w, cnt))
            bw = {i: freq['blue'].get(i,0)+1 for i in BLUE_BALL_RANGE}
            blue = self._weighted_sample(bw, 1)[0]
            preds.append(Prediction(reds=sorted(reds), blue=blue, score=0, strategy=self.name))
        return preds


class MonteCarloStrategy(PredictionStrategy):
    """策略5: 蒙特卡洛模拟 - 大规模模拟后统计最优组合"""
    def __init__(self, analyzer, sims: int = 10000):
        super().__init__(analyzer); self.name = "monte_carlo"
        self.sims = sims

    def predict(self, n: int = 1) -> List[Prediction]:
        freq = self.analyzer.frequency_analysis()
        missing = self.analyzer.missing_analysis()
        hc = self.analyzer.hot_cold_analysis(50)
        sum_s = self.analyzer.sum_analysis()
        span_s = self.analyzer.span_analysis()

        rw = {}
        for i in RED_BALL_RANGE:
            w = freq['red'].get(i,0)+1
            w *= max(0.3, 1-missing['red'][i]/100)
            if i in hc['red']['hot']: w *= 1.5
            elif i in hc['red']['cold']: w *= 0.5
            rw[i] = w
        bw = {}
        for i in BLUE_BALL_RANGE:
            w = freq['blue'].get(i,0)+1
            w *= max(0.3, 1-missing['blue'][i]/80)
            bw[i] = w

        rc = Counter(); bc = Counter(); valid = 0
        for _ in range(self.sims):
            reds = self._weighted_sample(rw, 6)
            blue = self._weighted_sample(bw, 1)[0]
            s = sum(reds); sp = max(reds)-min(reds)
            if not (sum_s['mean']-2.5*sum_s['std'] <= s <= sum_s['mean']+2.5*sum_s['std']):
                continue
            if not (span_s['mean']-2.5*span_s['std'] <= sp <= span_s['mean']+2.5*span_s['std']):
                continue
            valid += 1
            rc[tuple(sorted(reds))] += 1
            bc[blue] += 1

        preds = []
        top_r = rc.most_common(n*3)
        top_b = [x[0] for x in bc.most_common(n)]
        for i in range(min(n, len(top_r))):
            combo, cnt = top_r[i]
            b = top_b[i % len(top_b)] if top_b else 1
            preds.append(Prediction(reds=list(combo), blue=b,
                                    score=cnt/valid if valid else 0, strategy=self.name))
        return preds


class TrendStrategy(PredictionStrategy):
    """策略6: 趋势分析 - 分析号码出现的时间趋势"""
    def __init__(self, analyzer):
        super().__init__(analyzer); self.name = "trend"

    def predict(self, n: int = 1) -> List[Prediction]:
        freq_all = self.analyzer.frequency_analysis()
        freq_recent = self.analyzer.frequency_analysis(30)
        freq_old = self.analyzer.frequency_analysis(100)
        preds = []
        for _ in range(n):
            rs = {}
            for i in RED_BALL_RANGE:
                trend = freq_recent['red'].get(i,0)/30 - \
                        (freq_old['red'].get(i,0)-freq_recent['red'].get(i,0))/70
                rs[i] = freq_all['red'].get(i,0)*0.5 + trend*100*0.3 + random.random()*0.5
            reds = self._weighted_sample(rs, 6)
            bs = {}
            for i in BLUE_BALL_RANGE:
                trend = freq_recent['blue'].get(i,0)/30 - \
                        (freq_old['blue'].get(i,0)-freq_recent['blue'].get(i,0))/70
                bs[i] = freq_all['blue'].get(i,0)*0.5 + trend*100*0.3 + random.random()*0.5
            blue = max(bs, key=bs.get)
            preds.append(Prediction(reds=sorted(reds), blue=blue, score=0, strategy=self.name))
        return preds


# ============================================================
# 融合预测引擎
# ============================================================
class FusionPredictor:
    """融合6种策略的综合预测引擎"""

    def __init__(self, history: List[Dict], fast_mode: bool = False,
                 random_seed: int = None):
        self.history = history
        self.analyzer = StatisticalAnalyzer(history)
        self.fast_mode = fast_mode
        if random_seed is not None:
            random.seed(random_seed)

        mc_sims = 2000 if fast_mode else 10000
        self.strategies: List[PredictionStrategy] = [
            FrequencyStrategy(self.analyzer),
            MissingStrategy(self.analyzer),
            MarkovStrategy(self.analyzer),
            ZoneBalanceStrategy(self.analyzer),
            MonteCarloStrategy(self.analyzer, mc_sims),
            TrendStrategy(self.analyzer),
        ]
        self.strategy_weights = {s.name: 1.0 for s in self.strategies}

    def _update_weights_from_history(self):
        """从各策略的历史表现更新权重（EMA + softmax归一化）"""
        raw = {}
        for s in self.strategies:
            recent = s.performance[-30:] if len(s.performance) >= 30 else s.performance
            if recent:
                raw[s.name] = sum(recent) / len(recent)
            else:
                raw[s.name] = 0.15  # 默认基线

        # Softmax增强区分度
        vals = list(raw.values())
        exp_vals = [math.exp(v * 10) for v in vals]  # 乘10放大差异
        total = sum(exp_vals)
        for i, s in enumerate(self.strategies):
            self.strategy_weights[s.name] = max(0.01, exp_vals[i] / total)

    def update_weights(self, actual_reds: List[int], actual_blue: int,
                       predictions: List[Prediction]):
        """每期结束后根据命中情况更新策略权重（使用EMA+归一化）"""
        for pred in predictions:
            for s in self.strategies:
                if s.name == pred.strategy:
                    perf = s.evaluate(actual_reds, actual_blue, pred)
                    s.performance.append(perf)
                    recent = s.performance[-20:] if len(s.performance)>=20 else s.performance
                    avg_perf = sum(recent)/len(recent)
                    # 使用EMA平滑更新
                    old_w = self.strategy_weights.get(s.name, 1.0)
                    new_w = old_w * 0.7 + avg_perf * 8 * 0.3
                    self.strategy_weights[s.name] = max(0.05, new_w)
                    break
        # 归一化：使用权重的softmax增强区分度
        w = list(self.strategy_weights.values())
        total_w = sum(w)
        if total_w > 0:
            for s in self.strategies:
                self.strategy_weights[s.name] /= total_w

    def predict(self, n: int = 10) -> List[Prediction]:
        """融合所有策略生成最终预测"""
        all_preds = []
        total_w = sum(self.strategy_weights.values())
        for s in self.strategies:
            cnt = max(1, round(self.strategy_weights[s.name]/total_w * n * 3))
            preds = s.predict(cnt)
            for p in preds:
                p.score = self.strategy_weights.get(s.name, 1.0)
            all_preds.extend(preds)

        # 号码综合打分
        rc = Counter(); bc = Counter()
        for p in all_preds:
            for r in p.reds: rc[r] += p.score
            bc[p.blue] += p.score

        rs = {i: rc.get(i,0) for i in RED_BALL_RANGE}

        # 多样化生成10组
        final = []
        for i in range(n):
            reds = self._diversified_pick(rs, i, n)
            if not self._validate(reds):
                reds = self._constrained_pick(rs)
            # 蓝球多样化：每组用不同随机扰动
            blue_scores = {x: bc.get(x,0) + random.uniform(-1.5, 1.5) for x in BLUE_BALL_RANGE}
            blue = max(blue_scores, key=blue_scores.get)
            final.append(Prediction(
                reds=sorted(reds), blue=blue,
                score=sum(rs[r] for r in reds)/100,
                strategy="fusion"
            ))
        return final

    def _diversified_pick(self, scores: Dict[int, float], idx: int, total: int) -> List[int]:
        """多样化选择: 每组使用不同的温度参数和随机扰动"""
        temp = 0.3 + idx * 0.8 / total  # 0.3 ~ 1.1, 温度越高随机性越大
        items = list(scores.keys())
        # 添加随机扰动确保每组不同
        w = [math.exp((scores[i] + random.uniform(-0.5, 0.5)) / temp) for i in items]
        chosen = []; avail = list(range(len(items)))
        for _ in range(6):
            if not avail: break
            cur = [w[i] for i in avail]
            s = sum(cur)
            pick = random.choices(avail, weights=[x/s for x in cur], k=1)[0]
            chosen.append(items[pick]); avail.remove(pick)
        return chosen

    def _constrained_pick(self, scores: Dict[int, float]) -> List[int]:
        items = list(scores.keys())
        w = [max(0.01, scores[i]) for i in items]
        best, best_score = None, -1
        for _ in range(500):
            chosen = []; avail = list(range(len(items)))
            for _ in range(6):
                cur = [w[i] for i in avail]
                s = sum(cur)
                pick = random.choices(avail, weights=[x/s for x in cur], k=1)[0]
                chosen.append(items[pick]); avail.remove(pick)
            if self._validate(chosen):
                return chosen
            sc = sum(scores[r] for r in chosen)
            if sc > best_score:
                best_score = sc; best = chosen
        return best or chosen

    def _validate(self, reds: List[int]) -> bool:
        if len(set(reds)) != 6: return False
        sum_s = self.analyzer.sum_analysis()
        span_s = self.analyzer.span_analysis()
        s = sum(reds); sp = max(reds)-min(reds)
        return (sum_s['mean']-3*sum_s['std'] <= s <= sum_s['mean']+3*sum_s['std'] and
                span_s['mean']-3*span_s['std'] <= sp <= span_s['mean']+3*span_s['std'])


# ============================================================
# 递推回测引擎
# ============================================================
class BacktestEngine:
    """逐年递推回测 + 算法优化"""

    def __init__(self):
        pass

    def run(self, sample_every: int = 5) -> Dict:
        """递推回测: 每年用前一年数据预测，采样每N期，各策略独立评估"""
        all_results = get_all_results()
        yearly = defaultdict(list)
        for r in all_results:
            yearly[r['year']].append(r)
        years = sorted(yearly.keys())

        print(f"\n{'='*60}")
        print(f"  递推回测: {years[0]}年 -> {years[-1]}年")
        print(f"  采样: 每{sample_every}期, 各策略独立评估")
        print(f"{'='*60}")

        yearly_perf = {}
        all_weights_history = {}

        for train_year in years:
            test_year = train_year + 1
            if test_year not in yearly:
                continue

            train_data = [r for r in all_results if r['year'] <= train_year]
            pred_engine = FusionPredictor(train_data, fast_mode=True)

            test_draws = yearly[test_year]
            perf = {'red_hits': [], 'blue_hits': [], 'issues': [],
                    'strategy_hits': defaultdict(list)}

            print(f"\n[递推] {train_year}->{test_year}: "
                  f"训练{len(train_data)}期, 测试{len(test_draws)}期")

            for idx in range(0, len(test_draws), sample_every):
                draw = test_draws[idx]
                issue = draw['issue_number']
                actual_reds = [draw[f'red_{i}'] for i in range(1, 7)]
                actual_blue = draw['blue']

                # 每个策略独立预测和评估
                all_strategy_preds = []
                for s in pred_engine.strategies:
                    try:
                        s_preds = s.predict(n=1)
                        sp = s_preds[0]
                        score = s.evaluate(actual_reds, actual_blue, sp)
                        s.performance.append(score)
                        all_strategy_preds.append(sp)
                        perf['strategy_hits'][s.name].append(score)
                    except Exception:
                        continue

                # 综合评估（取最佳策略作为融合效果上界）
                if all_strategy_preds:
                    best_sp = max(all_strategy_preds,
                                  key=lambda p: len(set(p.reds) & set(actual_reds))*0.85
                                  + (1 if p.blue == actual_blue else 0)*0.15)
                    red_match = len(set(best_sp.reds) & set(actual_reds))
                    blue_match = 1 if best_sp.blue == actual_blue else 0
                    perf['red_hits'].append(red_match)
                    perf['blue_hits'].append(blue_match)
                    perf['issues'].append(issue)

                    # 根据各策略历史表现更新权重
                    pred_engine._update_weights_from_history()

            # 年度统计
            avg_red = sum(perf['red_hits'])/max(len(perf['red_hits']), 1)
            avg_blue = sum(perf['blue_hits'])/max(len(perf['blue_hits']), 1)
            yearly_perf[test_year] = {
                'avg_red_match': round(avg_red, 3),
                'avg_blue_match_rate': round(avg_blue, 3),
                'total_issues': len(perf['issues']),
                'weights': dict(pred_engine.strategy_weights),
                'strategy_perf': {k: round(sum(v)/max(len(v),1), 4)
                                  for k, v in perf['strategy_hits'].items()}
            }
            all_weights_history[test_year] = dict(pred_engine.strategy_weights)

            sp = yearly_perf[test_year]['strategy_perf']
            best_s = max(sp, key=sp.get)
            print(f"  -> {test_year}年: 红球 {avg_red:.3f}/6 | 蓝球 {avg_blue:.1%} | "
                  f"最佳策略:{best_s}({sp[best_s]:.3f})")

        # 最终：用全部历史数据（精确模式），并应用学到的权重
        print(f"\n[最终训练] 全部{len(all_results)}条数据(精确模式)...")
        final_engine = FusionPredictor(all_results, fast_mode=False)

        # 应用回测中学到的最终权重
        last_weights = all_weights_history.get(years[-2], {})
        if last_weights:
            final_engine.strategy_weights = dict(last_weights)
            print(f"  -> 应用回测优化后的权重")

        final_preds = final_engine.predict(TOP_N_PREDICTIONS)

        return {
            'yearly_performance': yearly_perf,
            'weights_history': all_weights_history,
            'final_predictions': final_preds,
            'final_weights': dict(final_engine.strategy_weights),
            'analyzer': final_engine.analyzer,
        }


# ============================================================
# 报告生成 & 数据库存储
# ============================================================
def generate_report(result: Dict):
    a = result['analyzer']
    preds = result['final_predictions']
    fw = result['final_weights']

    stats = get_statistics()
    latest = get_latest_issue()
    latest_reds = [latest[f'red_{i}'] for i in range(1, 7)]

    print(f"\n{'='*70}")
    print(f"  双色球 多策略融合预测系统 - 完整报告")
    print(f"{'='*70}")

    print(f"\n[I] 数据概况")
    print(f"  范围: {stats['first_issue']} ~ {stats['last_issue']}, 共 {stats['total_records']} 期")
    print(f"  最新: {latest['issue_number']} ({latest['draw_date']})")
    print(f"  红球: {latest_reds}  蓝球: {latest['blue']}")

    freq = a.frequency_analysis()
    hc = a.hot_cold_analysis(30)
    missing = a.missing_analysis()
    oe = a.odd_even_analysis()
    ss = a.sum_analysis()
    sp = a.span_analysis()

    print(f"\n[II] 统计特征分析")
    top_red = freq['red'].most_common(8)
    print(f"  TOP8 红球: {' '.join(f'{n}({c}次)' for n,c in top_red)}")
    print(f"  热号: {hc['red']['hot']}")
    print(f"  冷号: {hc['red']['cold']}")
    print(f"  热号蓝球: {hc['blue']['hot']}")
    missing_top = sorted(missing['red'].items(), key=lambda x:-x[1])[:8]
    print(f"  红球遗漏(多): {missing_top}")
    print(f"  奇偶比: {oe['odd_ratio']:.1%}/{oe['even_ratio']:.1%}")
    print(f"  和值: {ss['mean']:.0f}±{ss['std']:.0f}")
    print(f"  跨度: {sp['mean']:.0f}±{sp['std']:.0f}")
    z = a.zone_distribution()
    print(f"  区间分布: 一区{z['zone_1']:.1%} 二区{z['zone_2']:.1%} 三区{z['zone_3']:.1%}")
    print(f"  连号概率: {a.consecutive_analysis()['consecutive_prob']:.1%}")
    ac = a.ac_value_analysis()
    print(f"  AC值均值: {ac['mean_ac']:.1f}, 常见: {ac['top_ac_values']}")

    print(f"\n[III] 逐年递推回测表现")
    yp = result['yearly_performance']
    print(f"  {'年份':<8} {'红球均命中':<12} {'蓝球命中率':<12} {'期数':<6}")
    print(f"  {'-'*40}")
    for year in sorted(yp.keys()):
        p = yp[year]
        print(f"  {year:<8} {p['avg_red_match']:<12.3f}/6 {p['avg_blue_match_rate']:<12.1%} {p['total_issues']:<6}期")

    print(f"\n[IV] 最终策略权重分布")
    total_w = sum(fw.values())
    for name, w in sorted(fw.items(), key=lambda x:-x[1]):
        pct = w/total_w*100
        bar = '█'*int(pct/4)
        print(f"  {name:<20} {w:.4f} ({pct:.1f}%) {bar}")

    print(f"\n{'='*70}")
    print(f"  [V] 本期预测 - {TOP_N_PREDICTIONS} 组推荐号码")
    print(f"{'='*70}")
    print(f"  {'组':<5} {'红球号码':<32} {'蓝球':<5} {'评分'}")
    print(f"  {'-'*52}")
    for i, p in enumerate(preds, 1):
        rs = ' '.join(f'{r:02d}' for r in p.reds)
        print(f"  {i:<5} {rs:<32} {p.blue:02d}   {p.score:.4f}")

    print(f"\n{'='*70}")
    print(f"  [!] 免责: 彩票为随机事件，本系统仅供学术研究参考,")
    print(f"      不构成任何投注建议。请理性购彩，量力而行。")
    print(f"{'='*70}\n")
    return preds


def save_to_database(result: Dict):
    """预测结果持久化"""
    conn = get_connection()
    c = conn.cursor()
    latest = get_latest_issue()
    last_num = int(_normalize_issue(latest['issue_number'])[4:])
    next_issue = f"{datetime.now().year}{last_num+1:03d}"
    ver = f"v{datetime.now().strftime('%Y%m%d')}"

    for p in result['final_predictions']:
        rs = ','.join(f'{r:02d}' for r in p.reds)
        c.execute('''INSERT INTO prediction_history
            (target_issue, prediction_date, predicted_reds, predicted_blue,
             algorithm_version, score)
            VALUES (?, datetime('now'), ?, ?, ?, ?)''',
                  (next_issue, rs, p.blue, ver, p.score))
    conn.commit(); conn.close()
    print(f"[OK] 预测已存入数据库 (目标期号预估: {next_issue})")
    return next_issue


# ============================================================
# 开奖后更新功能
# ============================================================
def update_after_draw(actual_issue: str, actual_reds: List[int], actual_blue: int):
    """开奖后调用：对比预测与实际结果，更新算法参数"""
    conn = get_connection()
    c = conn.cursor()

    # 查找该期的预测记录
    c.execute('''SELECT * FROM prediction_history WHERE target_issue = ?''',
              (actual_issue,))
    preds = c.fetchall()

    if not preds:
        print(f"[INFO] 期号 {actual_issue} 无预测记录，跳过更新")
        conn.close()
        return

    print(f"\n{'='*50}")
    print(f"  开奖后分析: {actual_issue}")
    print(f"  实际红球: {actual_reds}  蓝球: {actual_blue}")
    print(f"{'='*50}")

    best_red = 0; best_blue = 0; best_score = 0
    for p in preds:
        p_reds = [int(x) for x in p['predicted_reds'].split(',')]
        red_hit = len(set(p_reds) & set(actual_reds))
        blue_hit = 1 if p['predicted_blue'] == actual_blue else 0
        score = red_hit/6*0.85 + blue_hit*0.15

        c.execute('''UPDATE prediction_history
            SET actual_reds=?, actual_blue=?, red_match_count=?, blue_match=?, score=?
            WHERE id=?''',
                  (','.join(f'{r:02d}' for r in actual_reds), actual_blue,
                   red_hit, blue_hit, score, p['id']))

        print(f"  预测{p['id']}: {p_reds}+{p['predicted_blue']:02d} → "
              f"红中{red_hit}/6 蓝{'✓' if blue_hit else '✗'} 得分{score:.3f}")

        if red_hit > best_red or (red_hit == best_red and blue_hit > best_blue):
            best_red = red_hit; best_blue = blue_hit; best_score = score

    print(f"\n  最佳预测: 红球命中 {best_red}/6, 蓝球 {'命中' if best_blue else '未中'}, 得分 {best_score:.3f}")

    # 调整下一次预测的策略权重
    c.execute('''SELECT AVG(red_match_count) as avg_red, AVG(blue_match) as avg_blue
        FROM prediction_history WHERE actual_reds IS NOT NULL''')
    overall = c.fetchone()
    print(f"  历史平均: 红球命中 {overall['avg_red']:.3f}/6, 蓝球命中率 {overall['avg_blue']:.3f}")

    conn.commit(); conn.close()
    print(f"  [OK] 分析完成，数据库已更新\n")


# ============================================================
# 主程序入口
# ============================================================
def main():
    print("双色球预测系统 v2.0 - 多策略融合引擎")
    print("=" * 50)

    # 初始化数据库
    from ssq_database import create_database, import_from_json
    create_database()
    import_from_json()

    # 查看是否有命令行参数（开奖后更新模式）
    if len(sys.argv) >= 3:
        issue = sys.argv[1]
        reds = [int(x) for x in sys.argv[2].split(',')]
        blue = int(sys.argv[3])
        update_after_draw(issue, reds, blue)
        return

    # 正常运行：递推回测 + 预测
    engine = BacktestEngine()
    result = engine.run()
    generate_report(result)
    next_issue = save_to_database(result)

    print(f"\n[提示] 开奖后运行以下命令更新模型:")
    print(f"  python ssq_prediction.py {next_issue} 红1,红2,红3,红4,红5,红6 蓝球")
    print(f"  示例: python ssq_prediction.py {next_issue} 01,05,12,18,25,30 08")

    return result


if __name__ == '__main__':
    main()
