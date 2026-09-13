# -*- coding: utf-8 -*-
"""AI漏洞扫描系统 - 资产批量导入模块（CSV / Excel）

解析 CSV（stdlib）与 Excel（openpyxl 可选）文本为资产字典列表，
行级容错：单行缺字段仅记错误不中断整体导入。
"""
import csv
import io
import logging
from typing import Dict, List, Tuple

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 表头别名 → 规范字段名
HEADER_ALIASES = {
    'name': 'name', '名称': 'name', '资产名称': 'name',
    'ip': 'ip', 'ip地址': 'ip', '地址': 'ip',
    'url': 'url', '网址': 'url',
    'mac': 'mac', 'mac地址': 'mac',
    'type': 'type', '类型': 'type',
    'os': 'os', '操作系统': 'os',
    'status': 'status', '状态': 'status',
    'tags': 'tags', '标签': 'tags',
    'owner': 'owner', '负责人': 'owner',
    'department': 'department', '部门': 'department',
    'location': 'location', '位置': 'location',
    'importance': 'importance', '重要性': 'importance',
}


def parse_tags(tags_str) -> List[str]:
    """标签字符串（逗号/分号/空格分隔）→ 去重去空列表"""
    if not tags_str:
        return []
    text = str(tags_str).replace('，', ',').replace('；', ';')
    parts = []
    for seg in text.split(';'):
        parts.extend(seg.split(','))
    seen = set()
    out = []
    for p in parts:
        t = p.strip()
        if t and t not in seen:
            seen.add(t)
            out.append(t)
    return out


def _map_row(row: Dict) -> Dict:
    """按表头别名归一化一行"""
    asset = {}
    for k, v in row.items():
        canon = HEADER_ALIASES.get(str(k).strip().lower()) or HEADER_ALIASES.get(str(k).strip())
        if canon:
            asset[canon] = str(v or '').strip()
    return asset


def _normalize(asset: Dict) -> Dict:
    if asset.get('tags'):
        asset['tags'] = ','.join(parse_tags(asset['tags']))
    return asset


def parse_csv(text: str) -> Tuple[List[Dict], List[Dict]]:
    """解析 CSV 文本，返回 (assets, errors)"""
    reader = csv.DictReader(io.StringIO(text))
    assets: List[Dict] = []
    errors: List[Dict] = []
    for i, row in enumerate(reader, start=2):
        asset = _map_row(row)
        if not asset.get('name') or not asset.get('ip'):
            errors.append({'line': i, 'error': '缺少 name 或 ip 字段'})
            continue
        assets.append(_normalize(asset))
    return assets, errors


def parse_excel(data: bytes) -> Tuple[List[Dict], List[Dict]]:
    """解析 Excel (.xlsx) 字节，返回 (assets, errors)；需 openpyxl"""
    try:
        from openpyxl import load_workbook
    except ImportError:
        raise RuntimeError('未安装 openpyxl，无法解析 Excel（pip install openpyxl）')
    wb = load_workbook(io.BytesIO(data), read_only=True)
    ws = wb.active
    it = ws.iter_rows(values_only=True)
    try:
        headers_row = next(it)
    except StopIteration:
        return [], []
    headers = [str(h).strip() if h is not None else '' for h in headers_row]
    assets: List[Dict] = []
    errors: List[Dict] = []
    for i, values in enumerate(it, start=2):
        row = dict(zip(headers, values))
        asset = _map_row(row)
        if not asset.get('name') or not asset.get('ip'):
            errors.append({'line': i, 'error': '缺少 name 或 ip 字段'})
            continue
        assets.append(_normalize(asset))
    return assets, errors


def import_assets(db, assets: List[Dict]) -> Dict:
    """将解析出的资产写入 DB，返回统计 {inserted, duplicate, failed}"""
    ok = dup = fail = 0
    for a in assets:
        try:
            aid = db.add_asset(a)
            if aid == -1:
                dup += 1
            else:
                ok += 1
        except Exception as e:
            logger.warning(f'资产导入失败 {a.get("ip")}: {e}')
            fail += 1
    return {'inserted': ok, 'duplicate': dup, 'failed': fail}
