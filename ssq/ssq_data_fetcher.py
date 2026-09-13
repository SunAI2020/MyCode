"""
双色球数据获取模块 - 从中国福利彩票官网获取实时开奖数据

数据来源: cwl.gov.cn (中国福利彩票官网)
开奖时间: 每周二、四、日 21:15
"""
import requests
import re
import json
import os
import time
import ssl
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from bs4 import BeautifulSoup

# SSL 问题抑制（中国部分网络环境下 cwl.gov.cn 证书可能有问题）
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ============================================================
# 常量配置
# ============================================================
# 主数据源: 中国福利彩票官网 API
CWL_API_URL = "https://www.cwl.gov.cn/cwl_admin/front/cwlkj/front/kjxx/findDrawNotice"
# 备用数据源: 500.com 历史数据页
BACKUP_URL = "https://datachart.500.com/ssq/history/newinc/history.php"
HEADERS = {
    "Referer": "https://www.cwl.gov.cn/ygkj/wqkjgg/ssq/",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
}
DRAW_TIME = "21:15"  # 双色球固定开奖时间（每周二、四、日）
REQUEST_TIMEOUT = 15  # 请求超时（秒）
MAX_RETRIES = 3  # 最大重试次数
CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          'ssq_latest_cache.json')

# 奖级信息
PRIZE_CONDITIONS: Dict[int, str] = {
    1: "6红+1蓝",
    2: "6红+0蓝",
    3: "5红+1蓝",
    4: "5红+0蓝 或 4红+1蓝",
    5: "4红+0蓝 或 3红+1蓝",
    6: "2红+1蓝 或 1红+1蓝 或 0红+1蓝",
}

PRIZE_NAMES: Dict[int, str] = {
    1: "一等奖", 2: "二等奖", 3: "三等奖",
    4: "四等奖", 5: "五等奖", 6: "六等奖",
}


# ============================================================
# 数据获取核心
# ============================================================
def _do_request(url: str, params: Dict) -> Optional[requests.Response]:
    """单次HTTP请求（SSL兜底：verify→no verify→bare except）"""
    for verify_ssl in (True, False):
        try:
            resp = requests.get(
                url, params=params, headers=HEADERS,
                timeout=REQUEST_TIMEOUT, verify=verify_ssl,
            )
            return resp
        except (requests.exceptions.SSLError, requests.exceptions.ConnectionError):
            if verify_ssl:
                continue  # 尝试关闭 SSL 验证
    return None


def _api_request(params: Dict) -> Optional[Dict]:
    """发送API请求（含重试 + SSL兜底）"""
    for attempt in range(MAX_RETRIES):
        try:
            resp = _do_request(CWL_API_URL, params)
            if resp is None:
                raise requests.exceptions.ConnectionError("所有SSL模式均失败")

            resp.raise_for_status()
            # 主源可能返回 HTML（如 404 页面），此时 content-type 非 JSON，说明接口已变更/失效
            if 'json' not in (resp.headers.get('content-type') or ''):
                print(f"[WARN] 主数据源返回非 JSON（content-type={resp.headers.get('content-type')}），接口可能已变更，切换备用源")
                return None
            data = resp.json()

            if data.get("state") != 0:
                print(f"[ERR] API返回错误: {data.get('message', 'Unknown')}")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(2)
                    continue
                return None

            return data
        except requests.exceptions.Timeout:
            print(f"[WARN] 请求超时 (尝试 {attempt+1}/{MAX_RETRIES})")
            if attempt < MAX_RETRIES - 1:
                time.sleep(2)
        except requests.exceptions.ConnectionError as e:
            print(f"[WARN] 连接失败 (尝试 {attempt+1}/{MAX_RETRIES}): {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(3)
        except Exception as e:
            print(f"[ERR] 请求异常: {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(2)
    return None


def _parse_int_cell(text: str) -> int:
    """解析带千分位逗号的数字，如 '833,007,469' -> 833007469；空值/异常返回 0"""
    text = (text or '').strip().replace(',', '')
    try:
        return int(text)
    except ValueError:
        return 0


def _fetch_from_backup() -> Optional[List[Dict]]:
    """从 500.com 备用数据源获取最近开奖数据（含奖池/销售额/一二等奖，无地区分布）。

    500.com 表格列（tbody#tdata）:
      0期号 1-6红球 7蓝球 8快乐星期天 9奖池 10一等奖注数 11一等奖奖金
      12二等奖注数 13二等奖奖金 14销售额 15开奖日期
    """
    try:
        # 起始期号按当前年份往前推2年动态计算（500.com 用 5 位 'YYNNN' 格式）
        start_issue = f"{str(datetime.now().year - 2)[-2:]}001"
        resp = _do_request(BACKUP_URL, {"start": start_issue, "end": ""})
        if resp is None:
            return None
        resp.encoding = 'gb2312'
        soup = BeautifulSoup(resp.text, 'html.parser')
        tbody = soup.find('tbody', id='tdata')
        if not tbody:
            return None

        results = []
        for row in tbody.find_all('tr')[:5]:  # 取最近5期
            cells = row.find_all('td')
            if len(cells) < 16:
                continue
            try:
                issue = cells[0].text.strip()
                reds = [int(cells[i].text.strip()) for i in range(1, 7)]
                blue = int(cells[7].text.strip())
                pool = _parse_int_cell(cells[9].text)       # 奖池
                w1 = _parse_int_cell(cells[10].text)        # 一等奖注数
                prize1 = _parse_int_cell(cells[11].text)    # 一等奖单注奖金
                w2 = _parse_int_cell(cells[12].text)        # 二等奖注数
                prize2 = _parse_int_cell(cells[13].text)    # 二等奖单注奖金
                sales = _parse_int_cell(cells[14].text)     # 销售额
                date_str = cells[15].text.strip()           # 开奖日期

                # 星期（由日期推导）
                weekday = ""
                try:
                    weekday = "一二三四五六日"[datetime.strptime(date_str, '%Y-%m-%d').weekday()]
                except ValueError:
                    weekday = ""

                # 奖级明细：一二等有真实数据，三~六等 500.com 未提供，补 0 占位
                prize_grades = [
                    {"level": 1, "name": PRIZE_NAMES[1], "condition": PRIZE_CONDITIONS[1],
                     "winners": w1, "prize_per": prize1},
                    {"level": 2, "name": PRIZE_NAMES[2], "condition": PRIZE_CONDITIONS[2],
                     "winners": w2, "prize_per": prize2},
                ]
                for level in range(3, 7):
                    prize_grades.append({
                        "level": level, "name": PRIZE_NAMES[level],
                        "condition": PRIZE_CONDITIONS[level],
                        "winners": 0, "prize_per": 0,
                    })

                results.append({
                    "issue": issue,
                    "date": date_str,
                    "weekday": weekday,
                    "time": DRAW_TIME,
                    "reds": reds,
                    "blue": blue,
                    "sales": sales,
                    "pool": pool,
                    "prize_grades": prize_grades,
                    "province_winners": [],
                    "province_raw": "",
                })
            except (ValueError, IndexError):
                continue

        return results if results else None
    except Exception as e:
        print(f"[WARN] 备用数据源获取失败: {e}")
        return None


def fetch_recent_draws(count: int = 30) -> Optional[List[Dict]]:
    """获取最近N期开奖数据"""
    data = _api_request({"name": "ssq", "issueCount": count})
    if data is None:
        return None
    results = data.get("result", [])
    return [_parse_draw(item) for item in results]


def fetch_latest_draw() -> Optional[Dict]:
    """获取最新一期开奖数据（主源失败时自动切换备用源）"""
    results = fetch_recent_draws(1)
    if results:
        return results[0]

    # 主源失败，尝试备用源
    print("[INFO] 主数据源不可用，尝试备用数据源(500.com)...")
    backup = _fetch_from_backup()
    if backup:
        save_cache(backup[0])
        print(f"[OK] 备用源获取成功: {backup[0]['issue']}期")
        return backup[0]

    print("[ERR] 所有数据源均不可用")
    return None


def fetch_draw_by_issue(issue: str) -> Optional[Dict]:
    """根据期号查询指定期数的开奖数据"""
    data = _api_request({
        "name": "ssq",
        "issueStart": issue,
        "issueEnd": issue,
        "issueCount": 1,
    })
    if data is None:
        return None
    results = data.get("result", [])
    if not results:
        print(f"[INFO] 未找到期号 {issue} 的数据")
        return None
    return _parse_draw(results[0])


def fetch_draws_by_date_range(start_date: str, end_date: str,
                              page_no: int = 1) -> Optional[List[Dict]]:
    """按日期范围查询开奖数据"""
    data = _api_request({
        "name": "ssq",
        "dayStart": start_date,
        "dayEnd": end_date,
        "pageNo": page_no,
    })
    if data is None:
        return None
    return [_parse_draw(item) for item in data.get("result", [])]


# ============================================================
# 缓存机制
# ============================================================
def load_cached_latest() -> Optional[Dict]:
    """从缓存文件加载最新数据"""
    if not os.path.exists(CACHE_FILE):
        return None
    try:
        with open(CACHE_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        # 检查缓存是否过期（超过24小时）
        cache_time = data.get("_cached_at", "")
        if cache_time:
            cached_dt = datetime.fromisoformat(cache_time)
            if (datetime.now() - cached_dt).total_seconds() > 86400:
                return None  # 缓存已过期
        return data
    except (json.JSONDecodeError, KeyError, ValueError):
        return None


def save_cache(data: Dict) -> None:
    """存储最新数据到缓存"""
    data["_cached_at"] = datetime.now().isoformat()
    try:
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except IOError as e:
        print(f"[WARN] 缓存写入失败: {e}")


# ============================================================
# 辅助函数
# ============================================================
def _parse_draw(item: Dict) -> Dict:
    """解析API返回的单条开奖数据为标准格式"""
    # 解析红球蓝球
    reds = [int(x) for x in item["red"].split(",")]
    blue = int(item["blue"])

    # 解析日期与星期
    date_raw = item.get("date", "")
    date_parts = date_raw.split("(")
    date_str = date_parts[0]  # "2026-07-09(四)" -> "2026-07-09"
    weekday = date_parts[1].rstrip(")") if len(date_parts) > 1 else ""

    # 解析奖级明细
    prize_grades = []
    for g in item.get("prizegrades", []):
        prize_grades.append({
            "level": g["type"],
            "name": PRIZE_NAMES.get(g["type"], f"奖级{g['type']}"),
            "condition": PRIZE_CONDITIONS.get(g["type"], ""),
            "winners": int(g.get("typenum", 0)),
            "prize_per": int(g.get("typemoney", 0)),
        })

    # 确保6个奖级都存在
    existing_levels = {g["level"] for g in prize_grades}
    for level in range(1, 7):
        if level not in existing_levels:
            prize_grades.append({
                "level": level,
                "name": PRIZE_NAMES[level],
                "condition": PRIZE_CONDITIONS[level],
                "winners": 0,
                "prize_per": 0,
            })
    prize_grades.sort(key=lambda x: x["level"])

    # 解析一等奖中奖地区
    province_winners = _parse_province_content(item.get("content", ""))

    # 处理 sales 和 poolmoney
    sales_val = item.get("sales", "0")
    pool_val = item.get("poolmoney", "0")

    return {
        "issue": item["code"],
        "date": date_str,
        "weekday": weekday,
        "time": DRAW_TIME,
        "reds": reds,
        "blue": blue,
        "sales": int(sales_val) if sales_val else 0,
        "pool": int(pool_val) if pool_val else 0,
        "prize_grades": prize_grades,
        "province_winners": province_winners,
        "province_raw": item.get("content", ""),
    }


def _parse_province_content(content: str) -> List[Dict]:
    """解析一等奖中奖地区文本

    示例输入: "河北1注,江苏1注,浙江1注,福建5注,山东1注,广东2注,深圳3注,四川1注"
    输出: [{"province": "河北", "count": 1}, ...]
    """
    if not content:
        return []

    provinces = []
    # 匹配模式: 省份名+数字+注
    for match in re.finditer(r"([^\d,，;；\s]+?)(\d+)注", content):
        province = match.group(1).strip()
        count = int(match.group(2))
        provinces.append({
            "province": province,
            "count": count,
        })
    return provinces


def format_money(amount) -> str:
    """金额格式化（元→万元/亿元），兼容 int/float/str 类型"""
    try:
        amount = int(amount)
    except (ValueError, TypeError):
        return "0元"
    if amount <= 0:
        return "0元"
    if amount >= 100000000:  # >= 1亿
        yi = amount / 100000000
        return f"{yi:.2f}亿元"
    if amount >= 10000:  # >= 1万
        wan = amount / 10000
        return f"{wan:.0f}万元"
    return f"{amount:,}元"


# ============================================================
# 测试入口
# ============================================================
if __name__ == '__main__':
    print("=" * 50)
    print("  双色球数据获取模块 - 测试")
    print("=" * 50)

    # 测试获取最新一期
    print("\n[1] 获取最新开奖数据...")
    latest = fetch_latest_draw()
    if latest:
        print(f"  期号: {latest['issue']}")
        print(f"  日期: {latest['date']}({latest.get('weekday', '')}) {latest['time']}")
        print(f"  红球: {' '.join(f'{r:02d}' for r in latest['reds'])}")
        print(f"  蓝球: {latest['blue']:02d}")
        print(f"  销售额: {format_money(latest['sales'])}")
        print(f"  奖池: {format_money(latest['pool'])}")
        print(f"  奖级明细:")
        for g in latest['prize_grades']:
            print(f"    {g['name']}({g['condition']}): "
                  f"{g['winners']}注, 每注{format_money(g['prize_per'])}")
        print(f"  一等奖分布: {latest['province_winners']}")
    else:
        print("  [FAIL] 获取失败（可能网络不通）")

    # 测试缓存
    print("\n[2] 测试缓存...")
    if latest:
        save_cache(latest)
        cached = load_cached_latest()
        if cached:
            print(f"  缓存加载成功: {cached['issue']} (缓存时间: {cached.get('_cached_at','?')})")
        else:
            print("  [FAIL] 缓存加载失败")

    print("\n[3] 测试按期号查询...")
    result = fetch_draw_by_issue("2026078")
    if result:
        print(f"  查询成功: {result['issue']} {result['date']}")
    else:
        print("  [INFO] 查询失败（该期号可能不存在或网络不通）")
