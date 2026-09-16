"""
AI-PTS 漏洞库导入工具
将24万+CVE数据导入SQLite数据库
"""
import sys
import os
import json
import sqlite3
import logging
from pathlib import Path
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 数据库路径：与扫描器（vendor/database.py 的 CVEDatabase）共用同一个库，
# 使"导入 CVE 数据"真正影响扫描结果，避免导入到无人读取的 data/vuln.db。
DB_PATH = Path(__file__).parent / "vendor" / "cve_database.db"


def get_db_path():
    """获取数据库路径"""
    return str(DB_PATH)


def init_database():
    """初始化数据库"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # CVE表（schema 与 vendor/database.py 的 CVEDatabase 对齐，保证与扫描器共用同一库）
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cve_database (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cve_id TEXT NOT NULL UNIQUE,
            name TEXT,
            description TEXT,
            cvss_score REAL,
            severity TEXT DEFAULT 'UNKNOWN',
            published_date TEXT,
            modified_date TEXT,
            affected_products TEXT,
            references_url TEXT,
            ai_analysis TEXT,
            exploit_available INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            cwe TEXT,
            patch_link TEXT
        )
    ''')

    # 索引
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_severity ON cve_database(severity)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_cvss ON cve_database(cvss_score)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_products ON cve_database(affected_products)')

    conn.commit()
    conn.close()

    logger.info(f"数据库初始化完成: {DB_PATH}")
    return DB_PATH


def import_from_json(json_path: str) -> int:
    """
    从JSON文件导入CVE数据

    Args:
        json_path: CVE JSON文件路径

    Returns:
        int: 导入数量
    """
    logger.info(f"从 {json_path} 导入CVE数据...")

    if not os.path.exists(json_path):
        logger.error(f"文件不存在: {json_path}")
        return 0

    # 读取JSON
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    count = 0

    # 解析高危漏洞
    high_vulns = data.get("高危漏洞", [])
    for v in high_vulns:
        cve_id = v.get("CVE", "")
        if not cve_id:
            continue

        cvss = v.get("CVSS", "未知")
        severity_map = {"高": "high", "中": "medium", "低": "low", "未知": "unknown"}

        # 解析CVSS分数
        cvss_score = 0.0
        if cvss == "高":
            cvss_score = 8.0
        elif cvss == "中":
            cvss_score = 5.0
        elif cvss == "低":
            cvss_score = 3.0

        cursor.execute('''
            INSERT OR REPLACE INTO cve_database (
                cve_id, name, description, cvss_score, severity,
                published_date, affected_products, exploit_available
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            cve_id,
            v.get("描述", ""),
            v.get("描述", ""),
            cvss_score,
            severity_map.get(cvss, "unknown"),
            v.get("发布时间", ""),
            v.get("厂商", ""),
            0
        ))
        count += 1

    # 解析厂商公告 - Debian
    for item in data.get("数据源", {}).get("厂商公告", {}).get("Debian", []):
        cve_id = f"DSA-{item.get('DSA', '')}"
        cursor.execute('''
            INSERT OR REPLACE INTO cve_database (
                cve_id, name, description, severity, published_date
            ) VALUES (?, ?, ?, ?, ?)
        ''', (
            cve_id,
            f"Debian {item.get('DSA', '')}",
            item.get("软件包", ""),
            "medium",
            item.get("日期", "")
        ))
        count += 1

    # 解析厂商公告 - Ubuntu
    for item in data.get("数据源", {}).get("厂商公告", {}).get("Ubuntu", []):
        cursor.execute('''
            INSERT OR REPLACE INTO cve_database (
                cve_id, name, description, severity
            ) VALUES (?, ?, ?, ?)
        ''', (
            f"UBUNTU-{item.get('软件包', '')}",
            item.get("描述", ""),
            item.get("软件包", ""),
            item.get("状态", "")
        ))
        count += 1

    conn.commit()
    conn.close()

    logger.info(f"导入完成: {count} 条记录")
    return count


def get_statistics() -> dict:
    """获取统计信息"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 总数
    cursor.execute("SELECT COUNT(*) FROM cve_database")
    total = cursor.fetchone()[0]

    # 按严重程度
    cursor.execute("SELECT severity, COUNT(*) FROM cve_database GROUP BY severity")
    by_severity = {row[0]: row[1] for row in cursor.fetchall()}

    # 平均CVSS
    cursor.execute("SELECT AVG(cvss_score) FROM cve_database WHERE cvss_score > 0")
    avg_cvss = cursor.fetchone()[0] or 0

    conn.close()

    return {
        "total": total,
        "by_severity": by_severity,
        "avg_cvss": round(avg_cvss, 2)
    }


def search_vulns(
    product: str = None,
    severity: str = None,
    min_cvss: float = None,
    limit: int = 100
) -> list:
    """搜索漏洞"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    query = "SELECT * FROM cve_database WHERE 1=1"
    params = []

    if product:
        query += " AND (name LIKE ? OR affected_products LIKE ?)"
        params.extend([f"%{product}%", f"%{product}%"])

    if severity:
        query += " AND severity = ?"
        params.append(severity)

    if min_cvss:
        query += " AND cvss_score >= ?"
        params.append(min_cvss)

    query += f" ORDER BY cvss_score DESC LIMIT {limit}"

    cursor.execute(query, params)
    rows = cursor.fetchall()

    conn.close()

    return [
        {
            "cve_id": row[0],
            "name": row[1],
            "description": row[2],
            "cvss_score": row[3],
            "severity": row[4],
            "published_date": row[5]
        }
        for row in rows
    ]


def export_to_json(output_path: str = "cve_export.json", limit: int = None):
    """导出为JSON"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    query = "SELECT * FROM cve_database"
    if limit:
        query += f" LIMIT {limit}"

    cursor.execute(query)
    rows = cursor.fetchall()

    data = [
        {
            "cve_id": row[0],
            "name": row[1],
            "description": row[2],
            "cvss_score": row[3],
            "severity": row[4],
            "published_date": row[5]
        }
        for row in rows
    ]

    conn.close()

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    logger.info(f"导出完成: {output_path}, {len(data)} 条")
    return len(data)


# 命令行工具
def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="AI-PTS 漏洞库工具")
    parser.add_argument("command", choices=["init", "import", "stats", "search", "export"])
    parser.add_argument("-f", "--file", help="CVE JSON文件")
    parser.add_argument("-o", "--output", help="输出文件")
    parser.add_argument("-p", "--product", help="产品名称")
    parser.add_argument("-s", "--severity", help="严重程度")
    parser.add_argument("-c", "--cvss", type=float, help="最低CVSS分数")
    parser.add_argument("-l", "--limit", type=int, default=100, help="数量限制")

    args = parser.parse_args()

    if args.command == "init":
        init_database()

    elif args.command == "import":
        if not args.file:
            print("错误: 需要指定 -f 参数")
            return

        # 查找CVE文件
        possible_paths = [
            args.file,
            Path(__file__).parent / "data" / "漏洞库.json",
        ]

        for path in possible_paths:
            if os.path.exists(str(path)):
                count = import_from_json(str(path))
                print(f"已导入 {count} 条记录")
                break

    elif args.command == "stats":
        stats = get_statistics()
        print(f"总数: {stats['total']}")
        print(f"平均CVSS: {stats['avg_cvss']}")
        print("按严重程度:", stats['by_severity'])

    elif args.command == "search":
        vulns = search_vulns(
            product=args.product,
            severity=args.severity,
            min_cvss=args.cvss,
            limit=args.limit
        )
        print(f"找到 {len(vulns)} 条:")
        for v in vulns[:10]:
            print(f"  {v['cve_id']} [{v['severity']}] {v['name']}")

    elif args.command == "export":
        output = args.output or "cve_export.json"
        count = export_to_json(output)
        print(f"已导出 {count} 条到 {output}")


if __name__ == "__main__":
    main()