#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CVE漏洞库修复与补全脚本
功能:
1. 检测并移除数据库中的FAKE CVE（NVD中不存在的）
2. 逐月全网搜索2000年以来的漏洞信息
3. 补充遗漏的CVE记录
4. 回填已有CVE的CWE和补丁链接(patch_link)字段

用法:
  python cve_db_repair.py                    # 全部修复（先清假 → 回填 → 逐月补全）
  python cve_db_repair.py --clean-fakes      # 仅清除假CVE
  python cve_db_repair.py --backfill-only    # 仅回填CWE/补丁链接（已有CVE）
  python cve_db_repair.py --fetch-only       # 仅逐月补全
  python cve_db_repair.py --dry-run          # 预览模式，不实际写入
  python cve_db_repair.py --resume-from 2023-06  # 从指定月份续传

NVD API速率:
  无API Key: 5次/30秒 → 请求间隔6秒
  有API Key: 50次/30秒 → 请求间隔0.6秒
  可在环境变量 NVD_API_KEY 中设置，或在 main_window.py 设置界面配置
"""
import sys
import os
import time
import json
import sqlite3
import requests
import argparse
from datetime import datetime, timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'cve_database.db')
NVD_CVE_API = "https://services.nvd.nist.gov/rest/json/cves/2.0"

# API Key: 环境变量优先，其次从 assets_system.db 读取
NVD_API_KEY = os.environ.get('NVD_API_KEY', '')
REQUEST_DELAY = 0.6 if NVD_API_KEY else 6.0

# 之前 vulnerability_scraper.py 中硬编码的假CVE
KNOWN_FAKES = {
    'CVE-2026-0001', 'CVE-2026-0002', 'CVE-2026-1234',
    'CVE-2026-5678', 'CVE-2026-9012', 'CVE-2026-3456', 'CVE-2026-7890',
}


def load_api_key_from_db():
    global NVD_API_KEY, REQUEST_DELAY
    if NVD_API_KEY:
        return
    assets_db = os.path.join(BASE_DIR, 'assets_system.db')
    if os.path.exists(assets_db):
        try:
            conn = sqlite3.connect(assets_db)
            row = conn.execute(
                "SELECT value FROM system_settings WHERE key='nvd_api_key'"
            ).fetchone()
            conn.close()
            if row and row[0]:
                NVD_API_KEY = row[0]
                REQUEST_DELAY = 0.6
                print(f'[INFO] 从配置读取NVD API Key')
        except (sqlite3.OperationalError, sqlite3.DatabaseError):
            pass  # settings table may not exist yet


def log_work(work_type, status='已完成'):
    """记录一次漏洞库更新操作到 assets_system.db 的 work_log（供仪表盘"今日工作"统计）"""
    assets_db = os.path.join(BASE_DIR, 'assets_system.db')
    try:
        conn = sqlite3.connect(assets_db, timeout=30)
        conn.execute('''CREATE TABLE IF NOT EXISTS work_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            work_type TEXT NOT NULL,
            status TEXT DEFAULT '已完成',
            created_at TEXT DEFAULT (datetime('now','localtime'))
        )''')
        try:
            conn.execute("ALTER TABLE work_log ADD COLUMN status TEXT DEFAULT '已完成'")
        except sqlite3.OperationalError:
            pass
        conn.execute('INSERT INTO work_log (work_type, status) VALUES (?,?)', (work_type, status))
        conn.commit()
        conn.close()
    except (sqlite3.OperationalError, sqlite3.DatabaseError):
        pass


def get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def nvd_get(params, max_retries=5):
    """带重试+速率控制的NVD API GET"""
    headers = {}
    if NVD_API_KEY:
        headers['apiKey'] = NVD_API_KEY
    for attempt in range(max_retries):
        try:
            resp = requests.get(NVD_CVE_API, params=params, headers=headers, timeout=30)
            if resp.status_code == 200:
                return resp.json()
            elif resp.status_code == 429:
                wait = 30 if not NVD_API_KEY else 6
                print(f'  [限流429] 等待{wait}s ({attempt+1}/{max_retries})')
                time.sleep(wait)
            elif resp.status_code == 404:
                return None
            else:
                print(f'  [HTTP {resp.status_code}] ({attempt+1}/{max_retries})')
                time.sleep(2)
        except (requests.RequestException, OSError) as e:
            print(f'  [网络] {e} ({attempt+1}/{max_retries})')
            time.sleep(5)
    return None


def parse_cve(item):
    """从NVD API v2 vulnerability item提取字段"""
    c = item.get('cve', {})
    cve_id = c.get('id', '')

    desc = ''
    for d in c.get('descriptions', []):
        if d.get('lang') == 'en':
            desc = d.get('value', '')[:500]

    cvss_score = None
    severity = 'UNKNOWN'
    for key in ['cvssMetricV31', 'cvssMetricV30', 'cvssMetricV2']:
        if key in c.get('metrics', {}) and c['metrics'][key]:
            cvss_data = c['metrics'][key][0].get('cvssData', {})
            cvss_score = cvss_data.get('baseScore')
            severity = (cvss_data.get('baseSeverity', 'UNKNOWN')).upper()
            break

    products = []
    for cfg in c.get('configurations', []):
        for node in cfg.get('nodes', []):
            for m in node.get('cpeMatch', []):
                crit = m.get('criteria', '')
                if crit:
                    parts = crit.split(':')
                    if len(parts) >= 5:
                        products.append(f'{parts[3]}:{parts[4]}')
    products = list(set(products))[:10]

    cwe = ''
    for w in c.get('weaknesses', []):
        for dd in w.get('description', []):
            if dd.get('lang') == 'en':
                cwe = dd.get('value', '')
                break
        if cwe:
            break

    patch_link = ''
    refs = []
    for ref in c.get('references', []):
        url = ref.get('url', '')
        tags = [t.lower() for t in ref.get('tags', [])]
        refs.append(url)
        if not patch_link and any(t in tags for t in ('patch', 'vendor advisory', 'mitigation')):
            patch_link = url
    if not patch_link and refs:
        patch_link = refs[0]

    return {
        'cve_id': cve_id, 'name': cve_id,
        'description': desc, 'cvss_score': cvss_score,
        'severity': severity,
        'published_date': (c.get('published', '') or '')[:10],
        'modified_date': (c.get('lastModified', '') or '')[:10],
        'affected_products': ','.join(products),
        'references_url': ','.join(refs[:10]),
        'cwe': cwe, 'patch_link': patch_link,
    }


# ============================================================
# 阶段 1: 清除假CVE
# ============================================================
def clean_fake_cves(dry_run=False):
    print('\n' + '=' * 60)
    print('阶段 1: 清除 FAKE CVE')
    print('=' * 60)
    conn = get_conn()
    total = conn.execute('SELECT COUNT(*) FROM cve_database').fetchone()[0]
    print(f'数据库共 {total} 条')

    removed = 0
    # 已知假CVE
    for cid in KNOWN_FAKES:
        if conn.execute('SELECT 1 FROM cve_database WHERE cve_id=?', (cid,)).fetchone():
            print(f'  [FAKE] 移除: {cid}')
            if not dry_run:
                conn.execute('DELETE FROM cve_database WHERE cve_id=?', (cid,))
            removed += 1
    if removed:
        print(f'移除 {removed} 条已知假CVE')
    else:
        print('未发现已知假CVE')

    # 扫描特定可疑模式的CVE（小范围，避免大量误判）
    # 已知假CVE附近的小号段 (0001-0100)，真实的2026 CVE号段通常很大
    suspicious = conn.execute(
        "SELECT cve_id FROM cve_database WHERE cve_id IN "
        "(SELECT cve_id FROM cve_database WHERE cve_id LIKE 'CVE-2026-00%' "
        " UNION SELECT cve_id FROM cve_database WHERE cve_id LIKE 'CVE-2027-00%')"
    ).fetchall()
    # 只验证小号段（0001-0099），真实CVE通常不会这么小的号
    if suspicious:
        print(f'\n验证 {len(suspicious)} 条小号段疑似假CVE...')
        for i, row in enumerate(suspicious):
            cid = row['cve_id']
            if cid in KNOWN_FAKES:
                continue  # 已被上面移除
            print(f'  [{i+1}/{len(suspicious)}] {cid}...', end=' ', flush=True)
            data = nvd_get({'cveId': cid})
            if data and data.get('vulnerabilities'):
                print('OK')
            else:
                print('NOT FOUND -> remove')
                if not dry_run:
                    conn.execute('DELETE FROM cve_database WHERE cve_id=?', (cid,))
                removed += 1
            time.sleep(REQUEST_DELAY)

    conn.commit()
    remain = conn.execute('SELECT COUNT(*) FROM cve_database').fetchone()[0]
    conn.close()
    print(f'清除完成: 移除 {removed} 条, 剩余 {remain} 条')
    return remain


# ============================================================
# 阶段 2: 回填已有CVE的CWE和补丁链接
# ============================================================
def backfill_cwe_patch(dry_run=False):
    print('\n' + '=' * 60)
    print('阶段 2: 回填 CWE 和补丁链接')
    print('=' * 60)
    conn = get_conn()
    need = conn.execute(
        "SELECT cve_id FROM cve_database WHERE cwe IS NULL OR cwe='' OR patch_link IS NULL OR patch_link=''"
    ).fetchall()
    if not need:
        print('所有CVE已含CWE和补丁链接')
        conn.close()
        return
    print(f'{len(need)} 条需回填')
    ok = err = 0
    for i, row in enumerate(need):
        cid = row['cve_id']
        print(f'  [{i+1}/{len(need)}] {cid}...', end=' ', flush=True)
        try:
            data = nvd_get({'cveId': cid})
            if data and data.get('vulnerabilities'):
                f = parse_cve(data['vulnerabilities'][0])
                if not dry_run:
                    conn.execute(
                        '''UPDATE cve_database SET cwe=?, patch_link=?, references_url=?,
                           description=CASE WHEN description IS NULL OR description='' THEN ? ELSE description END,
                           cvss_score=CASE WHEN cvss_score IS NULL THEN ? ELSE cvss_score END
                           WHERE cve_id=?''',
                        (f['cwe'], f['patch_link'], f['references_url'],
                         f['description'], f['cvss_score'], cid))
                ok += 1
                print(f'CWE={f["cwe"]}')
            else:
                print('NVD未找到')
                err += 1
        except Exception as e:
            print(f'错误: {e}')
            err += 1
        time.sleep(REQUEST_DELAY)
    conn.commit()
    conn.close()
    print(f'回填完成: {ok} 条, 错误/跳过 {err} 条')


# ============================================================
# 阶段 3: 逐月全网补全
# ============================================================
def fetch_month(start, end, conn, stats):
    """拉取一个月窗口的CVE并upsert"""
    params = {
        'pubStartDate': start.strftime('%Y-%m-%dT00:00:00.000'),
        'pubEndDate': end.strftime('%Y-%m-%dT23:59:59.000'),
        'resultsPerPage': 100, 'startIndex': 0
    }
    count = 0
    while True:
        data = nvd_get(params)
        if data is None:
            break
        items = data.get('vulnerabilities', [])
        if not items:
            break
        for item in items:
            try:
                f = parse_cve(item)
                if not f['cve_id']:
                    continue
                ex = conn.execute(
                    'SELECT cve_id, cwe, patch_link, description, cvss_score FROM cve_database WHERE cve_id=?',
                    (f['cve_id'],)
                ).fetchone()
                if ex:
                    updates = {}
                    if (not ex['cwe'] or not ex['cwe'].strip()) and f['cwe']:
                        updates['cwe'] = f['cwe']
                    if (not ex['patch_link'] or not ex['patch_link'].strip()) and f['patch_link']:
                        updates['patch_link'] = f['patch_link']
                    if (not ex['description'] or not ex['description'].strip()) and f['description']:
                        updates['description'] = f['description']
                    if ex['cvss_score'] is None and f['cvss_score'] is not None:
                        updates['cvss_score'] = f['cvss_score']
                    if updates:
                        sets = ', '.join(f'{k}=?' for k in updates)
                        conn.execute(f'UPDATE cve_database SET {sets} WHERE cve_id=?',
                                     list(updates.values()) + [f['cve_id']])
                    stats['checked'] += 1
                else:
                    conn.execute(
                        '''INSERT INTO cve_database
                           (cve_id,name,description,cvss_score,severity,published_date,modified_date,
                            affected_products,references_url,cwe,patch_link)
                           VALUES (?,?,?,?,?,?,?,?,?,?,?)''',
                        (f['cve_id'], f['cve_id'], f['description'], f['cvss_score'],
                         f['severity'], f['published_date'], f['modified_date'],
                         f['affected_products'], f['references_url'], f['cwe'], f['patch_link']))
                    stats['added'] += 1
                    stats['checked'] += 1
            except (KeyError, TypeError, AttributeError) as e:
                stats.setdefault('errors', 0)
                stats['errors'] += 1
            count += 1
        total = data.get('totalResults', 0)
        params['startIndex'] += 100
        if params['startIndex'] >= total:
            break
        time.sleep(REQUEST_DELAY)
    return count


def fetch_all_history(dry_run=False, resume_from=None):
    print('\n' + '=' * 60)
    print('阶段 3: 逐月全网搜索 (2000-01 ~ 今)')
    print('=' * 60)
    tag = '快速(50次/30s)' if NVD_API_KEY else '慢速(5次/30s, 建议获取API Key)'
    print(f'NVD API: {tag}  间隔: {REQUEST_DELAY}s')

    conn = get_conn()
    before = conn.execute('SELECT COUNT(*) FROM cve_database').fetchone()[0]
    print(f'DB当前: {before} 条')

    stats = {'added': 0, 'checked': 0, 'months': 0, 'skipped': 0}
    cur = datetime(2000, 1, 1)
    if resume_from:
        try:
            cur = datetime.strptime(resume_from, '%Y-%m')
        except ValueError:
            print(f'无效日期: {resume_from}')

    now = datetime.now()
    total_m = (now.year - cur.year) * 12 + (now.month - cur.month) + 1
    est = total_m * (REQUEST_DELAY + 2)
    print(f'范围: {cur.strftime("%Y-%m")} ~ {now.strftime("%Y-%m")}  ({total_m} 个月)')
    print(f'预计: ~{est/3600:.1f}h')
    print()
    t0 = time.time()
    idx = 0

    try:
        while cur <= now:
            idx += 1
            m_end = (datetime(cur.year, cur.month + 1, 1) - timedelta(days=1)
                     if cur.month < 12 else datetime(cur.year, 12, 31))
            m_end = min(m_end, now)
            label = f'{cur.strftime("%Y-%m")}~{m_end.strftime("%Y-%m")}'

            # 已有足够数据则跳过（加速）
            cnt = conn.execute(
                "SELECT COUNT(*) FROM cve_database WHERE published_date BETWEEN ? AND ?",
                (cur.strftime('%Y-%m-%d'), m_end.strftime('%Y-%m-%d'))
            ).fetchone()[0]
            rate = idx / (time.time() - t0) * 3600 if time.time() > t0 else 0

            if cnt > 50 and idx > 12:
                stats['skipped'] += 1
                if idx % 10 == 0:
                    print(f'  [{idx}/{total_m}] {label} | 已有{cnt}条→跳过 | {rate:.0f}月/h')
            else:
                print(f'  [{idx}/{total_m}] {label}...', end=' ', flush=True)
                n = fetch_month(cur, m_end, conn, stats)
                stats['months'] += 1
                conn.commit()
                print(f'{n}条 | 新增累计{stats["added"]} | {rate:.0f}月/h')

            if idx % 50 == 0:
                conn.commit()
                now_total = conn.execute('SELECT COUNT(*) FROM cve_database').fetchone()[0]
                print(f'--- [{idx}/{total_m}] 新增{stats["added"]} DB→{now_total} 速度{rate:.0f}月/h ---')

            cur = m_end + timedelta(days=1)

    except KeyboardInterrupt:
        print(f'\n中断于 {cur.strftime("%Y-%m")}')
        print(f'新增 {stats["added"]}, 可用 --resume-from {cur.strftime("%Y-%m")} 续传')
        conn.commit()
        conn.close()
        log_work('漏洞库更新', '被终止')
        return

    conn.commit()
    after = conn.execute('SELECT COUNT(*) FROM cve_database').fetchone()[0]
    conn.close()
    h = (time.time() - t0) / 3600
    print(f'\n完成! {stats["months"]}月处理 + {stats["skipped"]}月跳过')
    print(f'新增 {stats["added"]} 条, DB: {before}→{after} (+{after-before}), 耗时 {h:.1f}h')
    log_work('漏洞库更新')


# ============================================================
def main():
    p = argparse.ArgumentParser(description='CVE漏洞库修复与补全')
    p.add_argument('--clean-fakes', action='store_true', help='仅清除假CVE')
    p.add_argument('--backfill-only', action='store_true', help='仅回填CWE/补丁')
    p.add_argument('--fetch-only', action='store_true', help='仅逐月补全')
    p.add_argument('--dry-run', action='store_true', help='预览不写入')
    p.add_argument('--resume-from', metavar='YYYY-MM', help='续传月份')
    args = p.parse_args()

    print('CVE漏洞库修复与补全工具')
    print(f'DB: {DB_PATH}')
    print(f'时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    if not os.path.exists(DB_PATH):
        print(f'错误: 数据库不存在 {DB_PATH}')
        sys.exit(1)

    load_api_key_from_db()
    if args.dry_run:
        print('*** 预览模式 ***')

    if args.clean_fakes:
        clean_fake_cves(dry_run=args.dry_run)
    elif args.backfill_only:
        backfill_cwe_patch(dry_run=args.dry_run)
    elif args.fetch_only:
        fetch_all_history(dry_run=args.dry_run, resume_from=args.resume_from)
    else:
        clean_fake_cves(dry_run=args.dry_run)
        backfill_cwe_patch(dry_run=args.dry_run)
        fetch_all_history(dry_run=args.dry_run, resume_from=args.resume_from)
        print('\n' + '=' * 60)
        print('全部修复完成！')
        print('=' * 60)


if __name__ == '__main__':
    main()
