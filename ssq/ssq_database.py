"""
双色球数据库模块 - SQLite 数据库创建与数据管理
"""
import sqlite3
import json
import os
from typing import List, Optional, Dict

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ssq_lottery.db')


def get_connection() -> sqlite3.Connection:
    """获取数据库连接"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def create_database():
    """创建数据库表结构"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS lottery_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            issue_number VARCHAR(20) NOT NULL UNIQUE,
            draw_date DATE NOT NULL,
            red_1 INTEGER NOT NULL, red_2 INTEGER NOT NULL,
            red_3 INTEGER NOT NULL, red_4 INTEGER NOT NULL,
            red_5 INTEGER NOT NULL, red_6 INTEGER NOT NULL,
            blue INTEGER NOT NULL,
            year INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS frequency_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            year INTEGER NOT NULL,
            number_type VARCHAR(10) NOT NULL,
            number INTEGER NOT NULL,
            count INTEGER DEFAULT 0,
            frequency REAL DEFAULT 0.0,
            last_appeared_issue VARCHAR(20),
            missing_count INTEGER DEFAULT 0,
            hot_cold_score REAL DEFAULT 0.0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS prediction_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            target_issue VARCHAR(20) NOT NULL,
            prediction_date TIMESTAMP NOT NULL,
            predicted_reds VARCHAR(50) NOT NULL,
            predicted_blue INTEGER NOT NULL,
            actual_reds VARCHAR(50),
            actual_blue INTEGER,
            red_match_count INTEGER DEFAULT 0,
            blue_match INTEGER DEFAULT 0,
            algorithm_version VARCHAR(20),
            score REAL DEFAULT 0.0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS algorithm_params (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            version VARCHAR(20) NOT NULL,
            param_name VARCHAR(50) NOT NULL,
            param_value REAL NOT NULL,
            performance_score REAL DEFAULT 0.0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 预测员战绩表 (V3 GUI)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS predictor_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            target_issue VARCHAR(20) NOT NULL,
            predictor_name VARCHAR(20) NOT NULL,
            algorithm VARCHAR(50) NOT NULL,
            predicted_reds VARCHAR(50) NOT NULL,
            predicted_blue INTEGER NOT NULL,
            actual_reds VARCHAR(50),
            actual_blue INTEGER,
            red_match_count INTEGER DEFAULT 0,
            blue_match INTEGER DEFAULT 0,
            prize_level INTEGER DEFAULT 0,
            prize_name VARCHAR(20) DEFAULT '未中奖',
            prize_amount REAL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # V3 新增: 策略表现追踪表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS strategy_performance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            test_date DATE NOT NULL,
            strategy_name VARCHAR(50) NOT NULL,
            red_hit_avg REAL DEFAULT 0.0,
            blue_hit_rate REAL DEFAULT 0.0,
            weight REAL DEFAULT 0.0,
            elo_rating REAL DEFAULT 1500.0,
            UNIQUE(test_date, strategy_name)
        )
    ''')

    # V3 新增: 共现规则缓存表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS association_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rule_type VARCHAR(10) NOT NULL,
            ball_a INTEGER NOT NULL,
            ball_b INTEGER NOT NULL,
            lift REAL DEFAULT 0.0,
            computed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    conn.commit()
    conn.close()
    print(f"[OK] 数据库已创建: {DB_PATH}")


# === 预测员战绩操作 ===

def save_predictor_predictions(issue: str, predictions_by_strategy: dict):
    """保存各预测员的预测号码到 predictor_records 表"""
    conn = get_connection()
    cursor = conn.cursor()
    saved = 0
    for strategy_name, data in predictions_by_strategy.items():
        info = data['info']
        for p in data['predictions']:
            reds_str = ','.join(f'{r:02d}' for r in p.reds)
            cursor.execute('''
                INSERT INTO predictor_records
                (target_issue, predictor_name, algorithm,
                 predicted_reds, predicted_blue)
                VALUES (?, ?, ?, ?, ?)
            ''', (issue, info['name'], info['algorithm'],
                  reds_str, p.blue))
            saved += 1
    conn.commit()
    conn.close()
    return saved


def update_predictor_after_draw(issue: str, actual_reds: list, actual_blue: int):
    """开奖后更新预测员战绩：计算命中、奖金，返回PK结果"""
    from ssq_prediction_v2 import calculate_prize
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM predictor_records WHERE target_issue=? AND actual_reds IS NULL",
        (issue,))
    rows = cursor.fetchall()

    if not rows:
        conn.close()
        return None

    actual_reds_sorted = sorted(actual_reds)
    actual_reds_str = ','.join(f'{r:02d}' for r in actual_reds_sorted)
    pk_results = []

    for row in rows:
        pred_reds = [int(x) for x in row['predicted_reds'].split(',')]
        pred_blue = row['predicted_blue']
        red_hit = len(set(pred_reds) & set(actual_reds_sorted))
        blue_hit = 1 if pred_blue == actual_blue else 0
        prize = calculate_prize(red_hit, blue_hit)

        cursor.execute('''
            UPDATE predictor_records
            SET actual_reds=?, actual_blue=?, red_match_count=?, blue_match=?,
                prize_level=?, prize_name=?, prize_amount=?
            WHERE id=?
        ''', (actual_reds_str, actual_blue, red_hit, blue_hit,
              prize['level'], prize['name'], prize['amount'], row['id']))

        pk_results.append({
            'predictor_name': row['predictor_name'],
            'algorithm': row['algorithm'],
            'pred_reds': pred_reds,
            'pred_blue': pred_blue,
            'red_hit': red_hit,
            'blue_hit': blue_hit,
            'prize_level': prize['level'],
            'prize_name': prize['name'],
            'prize_amount': prize['amount'],
        })

    conn.commit()
    conn.close()
    return {
        'issue': issue,
        'actual_reds': actual_reds_sorted,
        'actual_blue': actual_blue,
        'results': pk_results,
    }


def get_predictor_rankings() -> list:
    """获取预测员累计排名 (按总奖金降序)"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('''
        SELECT predictor_name,
               COUNT(*) as total_predictions,
               SUM(CASE WHEN prize_level > 0 THEN 1 ELSE 0 END) as win_count,
               SUM(prize_amount) as total_prize,
               MAX(prize_level) as best_level,
               AVG(red_match_count) as avg_red_match,
               AVG(blue_match) as avg_blue_match
        FROM predictor_records
        WHERE actual_reds IS NOT NULL
        GROUP BY predictor_name
        ORDER BY total_prize DESC
    ''')
    rankings = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rankings


def import_from_json(json_path: str = 'ssq_history.json'):
    """从JSON文件导入历史数据到数据库"""
    if not os.path.exists(json_path):
        cwd = os.path.dirname(os.path.abspath(__file__))
        full_path = os.path.join(cwd, json_path)
        if not os.path.exists(full_path):
            print(f"[ERR] JSON文件不存在: {json_path}")
            return
        json_path = full_path

    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    conn = get_connection()
    cursor = conn.cursor()
    inserted = 0

    for item in data:
        try:
            reds = sorted([int(x.strip()) for x in item['reds'].split(',')])
            code = _normalize_issue(item['code'])
            year = int(code[:4])
            date_str = item['date'].split('(')[0]

            cursor.execute('''
                INSERT OR IGNORE INTO lottery_results
                (issue_number, draw_date, red_1, red_2, red_3, red_4, red_5, red_6, blue, year)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (code, date_str, reds[0], reds[1], reds[2], reds[3], reds[4], reds[5],
                  int(item['blue']), year))
            if cursor.rowcount > 0:
                inserted += 1
        except Exception as e:
            print(f"  [WARN] 跳过 {item.get('code', '?')}: {e}")

    conn.commit()
    conn.close()
    print(f"[OK] 导入完成: {inserted} 条记录（跳过 {len(data)-inserted} 条重复）")
    return inserted


def get_all_results(years: Optional[List[int]] = None) -> List[Dict]:
    """获取历史开奖结果（按日期升序）"""
    conn = get_connection()
    cursor = conn.cursor()
    if years:
        placeholders = ','.join('?' * len(years))
        cursor.execute(f'''
            SELECT * FROM lottery_results WHERE year IN ({placeholders})
            ORDER BY issue_number ASC
        ''', years)
    else:
        cursor.execute('SELECT * FROM lottery_results ORDER BY issue_number ASC')
    results = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return results


def get_results_before_issue(issue_number: str, limit: int = 200) -> List[Dict]:
    """获取指定期号之前的历史数据"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM lottery_results WHERE issue_number < ?
        ORDER BY issue_number DESC LIMIT ?
    ''', (issue_number, limit))
    results = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return results


def _normalize_issue(issue_str: str) -> str:
    """标准化期号：5位 'YYNNN'（如 '26082'）→ 7位 '20YYNNN'（'2026082'）；7位原样返回"""
    issue_str = str(issue_str).strip()
    if len(issue_str) == 5:
        return f"20{issue_str}"
    return issue_str


def save_draw_result(issue: str, draw_date: str, reds: list, blue: int) -> bool:
    """将开奖结果存入 lottery_results 表（已存在则忽略）"""
    conn = get_connection()
    cursor = conn.cursor()
    issue = _normalize_issue(issue)
    year = int(issue[:4])
    try:
        cursor.execute('''
            INSERT OR IGNORE INTO lottery_results
            (issue_number, draw_date, red_1, red_2, red_3, red_4, red_5, red_6, blue, year)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (issue, draw_date, reds[0], reds[1], reds[2], reds[3], reds[4], reds[5], blue, year))
        inserted = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return inserted
    except Exception:
        conn.close()
        raise


def get_latest_issue() -> Optional[Dict]:
    """获取最新一期数据"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM lottery_results ORDER BY issue_number DESC LIMIT 1')
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_statistics() -> Dict:
    """获取数据库概览"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) as total FROM lottery_results')
    total = cursor.fetchone()['total']
    cursor.execute('SELECT MIN(issue_number) as first, MAX(issue_number) as last FROM lottery_results')
    r = cursor.fetchone()
    cursor.execute('SELECT year, COUNT(*) as cnt FROM lottery_results GROUP BY year ORDER BY year')
    yearly = {str(row['year']): row['cnt'] for row in cursor.fetchall()}
    conn.close()
    return {'total_records': total, 'first_issue': r['first'],
            'last_issue': r['last'], 'yearly_counts': yearly}


if __name__ == '__main__':
    create_database()
    import_from_json()
    stats = get_statistics()
    print(f"\n数据库统计:")
    print(f"  总记录: {stats['total_records']} 期")
    print(f"  范围: {stats['first_issue']} ~ {stats['last_issue']}")
    for y, c in stats['yearly_counts'].items():
        print(f"  {y}年: {c} 期")
