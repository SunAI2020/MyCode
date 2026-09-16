# -*- coding: utf-8 -*-
"""AI漏洞扫描系统 - 供应链安全检测模块（SCA）

解析多语言依赖清单文件（requirements.txt / package.json / go.mod / pom.xml /
Cargo.toml / Gemfile / Pipfile / poetry.lock），提取 (name, version)，按精确
版本区间匹配已知 CVE。对标 Trivy/Snyk 的 SCA 能力。

Layer 1（本模块）：确定性依赖解析 + CVE 版本区间匹配，零 AI 成本。
Layer 2（后续）：恶意依赖检测（typosquatting / 依赖混淆 / 后门）。
"""
import json
import logging
import os
import re
from typing import List, Dict, Optional, Tuple

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 复用 ai_scan_enhancer 的版本工具（版本字符串→元组 + 区间解析）
from ai_scan_enhancer import _parse_version, _parse_affected_range


# ============================================================
# 依赖清单解析器（各生态 → [{name, version, ecosystem}]）
# ============================================================

def _extract_version_from_constraint(constraint: str) -> str:
    """从版本约束里提取具体版本号。==1.2.3 → 1.2.3；>=1.0 → 1.0；无则空。"""
    if not constraint:
        return ''
    m = re.search(r'==\s*([0-9][A-Za-z0-9._+-]*)', constraint)
    if m:
        return m.group(1)
    m = re.search(r'([0-9]+\.[0-9][A-Za-z0-9._+-]*)', constraint)
    if m:
        return m.group(1)
    return ''


def parse_requirements(content: str) -> List[Dict]:
    """requirements.txt：name==version / name>=version 等，忽略注释/环境标记/选项行。"""
    deps = []
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith('#') or line.startswith('-'):
            continue
        line = line.split(';')[0].strip()  # 去掉 python_version 环境标记
        m = re.match(r'^([A-Za-z0-9._-]+)\s*(.*)$', line)
        if not m:
            continue
        name = m.group(1).lower()
        version = _extract_version_from_constraint(m.group(2).strip())
        if name:
            deps.append({'name': name, 'version': version, 'ecosystem': 'pypi'})
    return deps


def parse_package_json(content: str) -> List[Dict]:
    """package.json：dependencies + devDependencies，版本约束去 ^~>=< 前缀。"""
    try:
        data = json.loads(content)
    except (json.JSONDecodeError, ValueError):
        return []
    deps = []
    for section in ('dependencies', 'devDependencies'):
        for name, spec in (data.get(section) or {}).items():
            version = re.sub(r'^[\^~>=<\s]+', '', str(spec)).strip()
            if version.startswith(('workspace:', 'file:', 'link:', 'http:', 'https:', 'git+')):
                version = ''
            deps.append({'name': name.lower(), 'version': version, 'ecosystem': 'npm'})
    return deps


def parse_go_mod(content: str) -> List[Dict]:
    """go.mod：require 单行与 require (...) 块。"""
    deps = []
    in_block = False
    for line in content.splitlines():
        s = line.strip()
        if s.startswith('require ('):
            in_block = True
            continue
        if in_block and s == ')':
            in_block = False
            continue
        if in_block:
            parts = s.split()
            if len(parts) >= 2 and parts[1].startswith('v'):
                deps.append({'name': parts[0].lower(), 'version': parts[1].lstrip('v'), 'ecosystem': 'go'})
        elif s.startswith('require '):
            parts = s.split()
            if len(parts) >= 3 and parts[2].startswith('v'):
                deps.append({'name': parts[1].lower(), 'version': parts[2].lstrip('v'), 'ecosystem': 'go'})
    return deps


def parse_pom_xml(content: str) -> List[Dict]:
    """pom.xml：<dependency> 的 groupId:artifactId + version，含 <properties> 展开。"""
    deps = []
    props: Dict[str, str] = {}
    prop_block = re.search(r'<properties>(.*?)</properties>', content, re.DOTALL)
    if prop_block:
        for m in re.finditer(r'<([\w.]+)>\s*([^<]+?)\s*</\1>', prop_block.group(1)):
            props[m.group(1)] = m.group(2).strip()
    for dep in re.finditer(r'<dependency>(.*?)</dependency>', content, re.DOTALL):
        block = dep.group(1)
        gid = re.search(r'<groupId>([^<]+)</groupId>', block)
        aid = re.search(r'<artifactId>([^<]+)</artifactId>', block)
        ver = re.search(r'<version>([^<]+)</version>', block)
        if not aid:
            continue
        name = aid.group(1)
        if gid:
            name = f"{gid.group(1)}:{aid.group(1)}"
        version = ver.group(1).strip() if ver else ''
        if version.startswith('${') and version.endswith('}'):
            version = props.get(version[2:-1], '')
        deps.append({'name': name.lower(), 'version': version, 'ecosystem': 'maven'})
    return deps


def parse_cargo_toml(content: str) -> List[Dict]:
    """Cargo.toml：提取 [dependencies] 块里 name = "version"。"""
    deps = []
    m = re.search(r'\[dependencies\](.*?)(?=\n\[|\Z)', content, re.DOTALL)
    if not m:
        return deps
    for line in m.group(1).splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        mm = re.match(r'^([A-Za-z0-9_-]+)\s*=\s*["\']([^"\']+)["\']', line)
        if mm:
            name = mm.group(1).lower()
            version = mm.group(2).strip()
            if version.startswith(('=', '^', '~', '>', '<')):
                version = _extract_version_from_constraint(version)
            deps.append({'name': name, 'version': version, 'ecosystem': 'cargo'})
    return deps


def parse_gemfile(content: str) -> List[Dict]:
    """Gemfile：gem 'name', '~> x.y' 或 gem 'name', '= x.y' 或 gem 'name'。"""
    deps = []
    for line in content.splitlines():
        line = line.strip()
        if not line.startswith('gem '):
            continue
        m = re.match(r"^gem\s+['\"]([^'\"]+)['\"]", line)
        if not m:
            continue
        name = m.group(1).lower()
        version = _extract_version_from_constraint(line)
        deps.append({'name': name, 'version': version, 'ecosystem': 'rubygems'})
    return deps


def parse_pipfile(content: str) -> List[Dict]:
    """Pipfile：提取 [packages] 块里 name = "version"（或 "*"）。"""
    deps = []
    m = re.search(r'\[packages\](.*?)(?=\n\[|\Z)', content, re.DOTALL)
    if not m:
        return deps
    for line in m.group(1).splitlines():
        line = line.strip()
        mm = re.match(r'^([A-Za-z0-9._-]+)\s*=\s*["\']([^"\']*)["\']', line)
        if mm:
            version = mm.group(2).strip()
            if version in ('', '*'):
                version = ''
            deps.append({'name': mm.group(1).lower(), 'version': version, 'ecosystem': 'pypi'})
    return deps


def parse_poetry_lock(content: str) -> List[Dict]:
    """poetry.lock：[[package]] 块里 name/version 字段。"""
    deps = []
    for block in re.split(r'\[\[package\]\]', content)[1:]:
        nm = re.search(r'^name\s*=\s*"([^"]+)"', block, re.MULTILINE)
        vm = re.search(r'^version\s*=\s*"([^"]+)"', block, re.MULTILINE)
        if nm:
            deps.append({'name': nm.group(1).lower(), 'version': vm.group(1) if vm else '',
                         'ecosystem': 'pypi'})
    return deps


# 文件名 → 解析函数
DEPENDENCY_PARSERS = {
    'requirements.txt': parse_requirements,
    'package.json': parse_package_json,
    'package-lock.json': parse_package_json,
    'go.mod': parse_go_mod,
    'pom.xml': parse_pom_xml,
    'Cargo.toml': parse_cargo_toml,
    'Gemfile': parse_gemfile,
    'Pipfile': parse_pipfile,
    'poetry.lock': parse_poetry_lock,
}


def parse_dependency_files(path: str) -> List[Dict]:
    """递归扫描目录，解析依赖清单文件，返回 [{name, version, ecosystem, file, line}]。"""
    deps: List[Dict] = []
    if os.path.isfile(path):
        root, filename = os.path.dirname(path), os.path.basename(path)
        fnames = [filename] if filename in DEPENDENCY_PARSERS else []
        walk = [(root, fnames)]
    else:
        walk = []
        for root, dirs, fnames in os.walk(path):
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in
                       ['node_modules', '__pycache__', 'venv', '.git', 'dist', 'build', 'target']]
            walk.append((root, fnames))

    for root, fnames in walk:
        for fname in fnames:
            if fname not in DEPENDENCY_PARSERS:
                continue
            filepath = os.path.join(root, fname)
            try:
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
            except OSError:
                continue
            try:
                for dep in DEPENDENCY_PARSERS[fname](content):
                    dep['file'] = filepath
                    dep.setdefault('line', 0)
                    deps.append(dep)
            except Exception as e:
                logger.debug(f"解析依赖文件失败 {filepath}: {e}")
    return deps


# ============================================================
# 精确版本区间匹配（复用 ai_scan_enhancer 的版本工具）
# ============================================================

def _version_matches_spec(dep_ver: Tuple[int, ...], spec: str) -> bool:
    """判断 dep_ver 是否满足版本约束 spec。无法解析时返回 True（保守保留）。"""
    spec = spec.strip().lower()
    if not spec or spec in ('all versions', 'unspecified', 'all', '*', 'any'):
        return True
    # 精确版本（单个版本号，无比较符/区间词）
    if re.fullmatch(r'[v]?\d+(?:\.\d+){0,3}(?:[-+][\w.]+)?', spec):
        try:
            return dep_ver == _parse_version(spec)
        except ValueError:
            return True
    # 区间/比较符：复用 _parse_affected_range（< / <= / > / >= / through / to）
    min_ver, min_incl, max_ver, max_incl = _parse_affected_range(spec)
    if min_ver is None and max_ver is None:
        return True  # 无法解析 → 保守
    if min_ver is not None and (dep_ver < min_ver or (dep_ver == min_ver and not min_incl)):
        return False
    if max_ver is not None and (dep_ver > max_ver or (dep_ver == max_ver and not max_incl)):
        return False
    return True


def _version_in_affected(dep_version: str, affected_products: str, dep_name: str) -> bool:
    """判断 dep_version 是否落在 affected_products 里与 dep_name 匹配的版本约束内。

    保守：dep 无版本/版本不可解析/产品名未匹配到任何条目时返回 True（不排除）。
    仅当「产品名匹配 + 版本明确不在约束内」时才返回 False。
    """
    if not dep_version:
        return True
    try:
        dep_ver = _parse_version(dep_version)
    except ValueError:
        return True

    name_lower = (dep_name or '').lower()
    name_matched = False
    for entry in (affected_products or '').split(','):
        entry = entry.strip()
        if ':' not in entry:
            continue
        product, spec = entry.split(':', 1)
        product = product.strip()
        spec = spec.strip()
        if name_lower not in product.lower() and product.lower() not in name_lower:
            continue
        name_matched = True
        if _version_matches_spec(dep_ver, spec):
            return True
    return not name_matched


# ============================================================
# CVE 匹配 + 编排
# ============================================================

_SEV_NORMALIZE = {'CRITICAL': 'CRITICAL', 'HIGH': 'HIGH', 'MEDIUM': 'MEDIUM',
                  'LOW': 'LOW', 'NONE': 'INFO', 'UNKNOWN': 'MEDIUM'}


def match_dependencies_to_cves(deps: List[Dict], cve_db) -> List[Dict]:
    """对每个依赖召回候选 CVE，做精确版本区间过滤，产出 SCA 发现。"""
    findings: List[Dict] = []
    seen: set = set()
    for dep in deps:
        name = dep.get('name', '')
        version = dep.get('version', '')
        file = dep.get('file', '')
        if not name:
            continue
        try:
            candidates = cve_db.search_cve_by_product(name, limit=200)
        except Exception:
            continue
        for cve in candidates or []:
            cve_id = cve.get('cve_id')
            if not cve_id:
                continue
            affected = cve.get('affected_products', '') or ''
            if not _version_in_affected(version, affected, name):
                continue  # 版本明确不在受影响范围 → 排除
            key = (name, cve_id)
            if key in seen:
                continue
            seen.add(key)
            sev = _SEV_NORMALIZE.get(str(cve.get('severity', 'UNKNOWN')).upper(), 'MEDIUM')
            cvss = cve.get('cvss_score')
            findings.append({
                'file': file,
                'line': dep.get('line', 0),
                'dimension': 'supply_chain',
                'code': f'{name} {version}'.strip(),
                'category': '已知CVE依赖',
                'severity': sev,
                'problem': f'依赖 {name}=={version} 存在已知漏洞 {cve_id}（{cve.get("name", "")}）',
                'recommendation': f'升级 {name} 到不受影响的版本，参考 {cve.get("references_url", "")}',
                'evidence': {
                    'cve_id': cve_id,
                    'cvss_score': cvss,
                    'package': name,
                    'version': version,
                    'ecosystem': dep.get('ecosystem', ''),
                    'description': (cve.get('description', '') or '')[:300],
                },
            })
    return findings


# ============================================================
# Layer 2：恶意依赖检测（typosquatting / 依赖混淆，确定性）
# ============================================================

# 各生态高频知名包，用于 typosquatting 与依赖混淆检测（可扩展）
POPULAR_PACKAGES = {
    'pypi': {'requests', 'numpy', 'flask', 'django', 'pandas', 'scipy', 'matplotlib',
             'pytest', 'sqlalchemy', 'jinja2', 'pillow', 'cryptography', 'urllib3',
             'certifi', 'idna', 'setuptools', 'pip', 'wheel'},
    'npm': {'lodash', 'express', 'react', 'axios', 'moment', 'chalk', 'commander',
            'debug', 'typescript', 'vue', 'webpack', 'babel', 'eslint', 'jest'},
    'go': {'github.com/gin-gonic/gin', 'github.com/spf13/cobra', 'golang.org/x/net',
           'golang.org/x/crypto', 'github.com/pkg/errors'},
}


def _levenshtein(a: str, b: str) -> int:
    """Levenshtein 编辑距离。"""
    if len(a) < len(b):
        a, b = b, a
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        curr = [i]
        for j, cb in enumerate(b, 1):
            curr.append(min(prev[j] + 1, curr[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = curr
    return prev[-1]


def detect_typosquatting(dep: Dict) -> Optional[str]:
    """包名与知名包编辑距离 ≤1 → 返回相似知名包名，否则 None。"""
    name = dep.get('name', '')
    ecosystem = dep.get('ecosystem', '')
    if not name:
        return None
    for popular in POPULAR_PACKAGES.get(ecosystem, []):
        if name != popular and _levenshtein(name, popular) <= 1:
            return popular
    return None


def detect_dependency_confusion(dep: Dict) -> bool:
    """依赖混淆启发式：无版本固定 + 名称非知名公共包 → 疑似私有包被公共仓库抢占。"""
    name = dep.get('name', '')
    ecosystem = dep.get('ecosystem', '')
    if not name:
        return False
    if dep.get('version'):
        return False  # 有版本固定，通常是明确公共包
    return name not in POPULAR_PACKAGES.get(ecosystem, set())


def detect_suspicious_dependencies(deps: List[Dict]) -> List[Dict]:
    """恶意依赖检测（Layer 2）：typosquatting + 依赖混淆（确定性，零 AI 成本）。"""
    findings: List[Dict] = []
    for dep in deps:
        name = dep.get('name', '')
        file = dep.get('file', '')
        similar = detect_typosquatting(dep)
        if similar:
            findings.append({
                'file': file, 'line': dep.get('line', 0),
                'dimension': 'supply_chain', 'code': name,
                'category': '疑似恶意依赖', 'severity': 'HIGH',
                'problem': f'依赖 {name} 与知名包 {similar} 名称高度相似（编辑距离≤1），疑似 typosquatting 投毒',
                'recommendation': f'确认是否误引入拼写变体包，应为 {similar}',
                'evidence': {'package': name, 'suspicious_type': 'typosquatting',
                             'similar_to': similar, 'ecosystem': dep.get('ecosystem', '')},
            })
        elif detect_dependency_confusion(dep):
            findings.append({
                'file': file, 'line': dep.get('line', 0),
                'dimension': 'supply_chain', 'code': name,
                'category': '疑似恶意依赖', 'severity': 'MEDIUM',
                'problem': f'依赖 {name} 未固定版本且非知名公共包，疑似私有包依赖混淆风险',
                'recommendation': '确认包来源是否为内部私有仓库，避免被公共仓库同名包抢占',
                'evidence': {'package': name, 'suspicious_type': 'dependency_confusion',
                             'ecosystem': dep.get('ecosystem', '')},
            })
    return findings


def scan_dependencies(path: str, cve_db=None) -> List[Dict]:
    """供应链安全检测编排：解析依赖清单 → 恶意依赖检测 + 匹配 CVE。"""
    deps = parse_dependency_files(path)
    if not deps:
        return []
    findings = detect_suspicious_dependencies(deps)
    owns_db = False
    if cve_db is None:
        try:
            from database import CVEDatabase
            cve_db = CVEDatabase()
            owns_db = True
        except Exception as e:
            logger.warning(f"CVEDatabase 初始化失败: {e}")
            return findings
    try:
        findings.extend(match_dependencies_to_cves(deps, cve_db))
        return findings
    finally:
        # 仅关闭自己创建的连接，避免关闭调用方传入的共享 DB
        if owns_db and cve_db is not None and hasattr(cve_db, 'close'):
            try:
                cve_db.close()
            except Exception:
                pass


__all__ = [
    'DEPENDENCY_PARSERS', 'parse_dependency_files',
    'match_dependencies_to_cves', 'scan_dependencies',
    'detect_suspicious_dependencies', 'detect_typosquatting', 'detect_dependency_confusion',
    'POPULAR_PACKAGES', '_levenshtein',
    '_version_in_affected', '_version_matches_spec',
]
