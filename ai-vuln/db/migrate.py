#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SQLite → PostgreSQL 数据迁移 + 验证
用法: python -m db.migrate [--dry-run] [--verify]
"""
import os, sys, sqlite3, argparse, logging
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')
logger = logging.getLogger(__name__)

TABLE_FILE_MAP = {
    'scan_tasks':'scan_results.db','scan_results':'scan_results.db',
    'cve_database':'cve_database.db','vendor_advisories':'cve_database.db',
    'cvss_distribution':'cve_database.db',
    'cisa_kev':'threat_intel.db','epss_scores':'threat_intel.db',
    'threat_actors':'threat_intel.db','iocs':'threat_intel.db',
    'attack_patterns':'threat_intel.db','threat_feeds':'threat_intel.db',
    'weak_passwords':'threat_intel.db','threat_settings':'threat_intel.db',
    'audit_history':'audit_results.db','audit_issues':'audit_results.db',
    'assets':'assets_system.db','scan_policies':'assets_system.db',
    'reports':'assets_system.db','system_settings':'assets_system.db',
    'audit_logs':'assets_system.db',
}

SERIAL_TABLES = {
    'scan_tasks','scan_results','cve_database','vendor_advisories',
    'cisa_kev','threat_actors','iocs','threat_feeds','weak_passwords',
    'audit_history','audit_issues','assets','scan_policies','reports','audit_logs',
}

MIGRATION_ORDER = list(TABLE_FILE_MAP.keys())


def migrate(sqlite_dir=None, pg_conn=None, dry_run=False):
    if sqlite_dir is None:
        sqlite_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    import config, psycopg2
    from db.schema_postgres import create_all_tables
    if pg_conn is None:
        pg_conn = psycopg2.connect(host=config.PG_HOST, port=config.PG_PORT,
            database=config.PG_DATABASE, user=config.PG_USER, password=config.PG_PASSWORD)
    logger.info('Creating schema...')
    create_all_tables(pg_conn)
    total = 0
    for table in MIGRATION_ORDER:
        db_file = os.path.join(sqlite_dir, TABLE_FILE_MAP.get(table, f'{table}.db'))
        if not os.path.exists(db_file):
            logger.warning(f'  SKIP {table}: no file')
            continue
        sq = sqlite3.connect(db_file); sq.row_factory = sqlite3.Row
        try:
            rows = sq.execute(f'SELECT * FROM {table}').fetchall()
        except Exception:
            sq.close(); continue
        if not rows:
            sq.close(); continue
        cols = [d[0] for d in sq.execute(f'SELECT * FROM {table} LIMIT 0').description]
        # 保留原始 id 列（显式插入），避免 PG SERIAL 重排主键导致
        # scan_results.task_id / audit_issues.audit_id 等外键引用错挂。
        ph = ','.join(['%s']*len(cols))
        sql = f'INSERT INTO {table} ({",".join(cols)}) VALUES ({ph})'
        if dry_run:
            logger.info(f'  [DRY] {table}: {len(rows)} rows')
        else:
            cur = pg_conn.cursor()
            for r in rows:
                cur.execute(sql, [r[c] for c in cols])
            pg_conn.commit(); cur.close()
            # 显式插入 id 后重置序列，避免后续自动插入与已有主键冲突
            if table in SERIAL_TABLES and rows:
                try:
                    cur2 = pg_conn.cursor()
                    cur2.execute(
                        f"SELECT setval(pg_get_serial_sequence('{table}','id'), "
                        f"(SELECT COALESCE(MAX(id),1) FROM {table}))")
                    pg_conn.commit(); cur2.close()
                except Exception as e:
                    logger.warning(f'  重置序列 {table} 失败: {e}')
        logger.info(f'  OK {table}: {len(rows)} rows')
        total += len(rows)
        sq.close()
    logger.info(f'Done: {total} rows across {len(MIGRATION_ORDER)} tables')
    if not dry_run: pg_conn.close()
    return total


def verify(sqlite_dir=None, pg_conn=None):
    if sqlite_dir is None:
        sqlite_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    import config, psycopg2
    if pg_conn is None:
        pg_conn = psycopg2.connect(host=config.PG_HOST, port=config.PG_PORT,
            database=config.PG_DATABASE, user=config.PG_USER, password=config.PG_PASSWORD)
    for table in MIGRATION_ORDER:
        db_file = os.path.join(sqlite_dir, TABLE_FILE_MAP.get(table, f'{table}.db'))
        sq_c = 0
        if os.path.exists(db_file):
            sq = sqlite3.connect(db_file)
            try: sq_c = sq.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
            except: pass
            sq.close()
        pg_c = 0
        try:
            cur = pg_conn.cursor(); cur.execute(f'SELECT COUNT(*) FROM {table}')
            pg_c = cur.fetchone()[0]; cur.close()
        except: pass
        ok = 'OK' if sq_c == pg_c else 'MISMATCH'
        logger.info(f'  [{ok}] {table}: SQLite={sq_c} PG={pg_c}')
    pg_conn.close()


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--dry-run', action='store_true')
    p.add_argument('--verify', action='store_true')
    args = p.parse_args()
    verify() if args.verify else migrate(dry_run=args.dry_run)
