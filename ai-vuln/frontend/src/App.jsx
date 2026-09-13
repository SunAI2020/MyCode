import React, { useState, useEffect } from 'react'

const API_BASE = '/api/v1'

async function api(path, options = {}) {
    const token = localStorage.getItem('token')
    const headers = { 'Content-Type': 'application/json', ...(options.headers || {}) }
    if (token) headers['Authorization'] = 'Bearer ' + token
    const resp = await fetch(API_BASE + path, { ...options, headers })
    const data = await resp.json().catch(() => ({}))
    if (resp.status === 401) { localStorage.removeItem('token'); window.location.reload() }
    return data
}

// ===== 登录 =====
function Login({ onLogin }) {
    const [username, setUsername] = useState('')
    const [password, setPassword] = useState('')
    const [err, setErr] = useState('')
    async function submit(e) {
        e.preventDefault(); setErr('')
        const r = await api('/auth/login', { method: 'POST', body: JSON.stringify({ username, password }) })
        if (r.success !== false && r.data?.token) {
            localStorage.setItem('token', r.data.token)
            localStorage.setItem('user', JSON.stringify(r.data.user))
            onLogin(r.data.user)
        } else {
            setErr(r.message || '登录失败')
        }
    }
    return (
        <div className="login-wrap">
            <form className="login-card" onSubmit={submit}>
                <h1>AI漏洞扫描系统 Pro</h1>
                <div className="sub">山西有信网安科技有限公司</div>
                <div className="field"><label>用户名</label>
                    <input value={username} onChange={e => setUsername(e.target.value)} autoFocus /></div>
                <div className="field"><label>密码</label>
                    <input type="password" value={password} onChange={e => setPassword(e.target.value)} /></div>
                <button type="submit">登录</button>
                {err && <div className="error">{err}</div>}
                <div className="muted" style={{ marginTop: 14, fontSize: 12 }}>默认账号 admin / admin123</div>
            </form>
        </div>
    )
}

// ===== 修改密码 =====
function ChangePassword({ user, onDone, inline }) {
    const [oldPw, setOldPw] = useState('')
    const [newPw, setNewPw] = useState('')
    const [err, setErr] = useState('')
    const [ok, setOk] = useState('')
    async function submit(e) {
        e.preventDefault(); setErr(''); setOk('')
        const r = await api('/auth/change-password', { method: 'POST', body: JSON.stringify({ old_password: oldPw, new_password: newPw }) })
        if (r.success !== false) {
            const u = { ...user, must_change_password: 0 }
            localStorage.setItem('user', JSON.stringify(u))
            setOk('密码已修改'); setOldPw(''); setNewPw('')
            if (onDone) onDone(u)
        } else setErr(r.message || '修改失败')
    }
    const form = (
        <div className="card" style={{ maxWidth: 420 }}>
            <h3>修改密码</h3>
            {user.must_change_password ? <div className="error" style={{ marginBottom: 10 }}>首次登录需先修改初始密码</div> : null}
            <div className="field" style={{ marginBottom: 10 }}><label>旧密码</label>
                <input type="password" value={oldPw} onChange={e => setOldPw(e.target.value)} /></div>
            <div className="field" style={{ marginBottom: 10 }}><label>新密码（≥6位）</label>
                <input type="password" value={newPw} onChange={e => setNewPw(e.target.value)} /></div>
            <button onClick={submit}>确认修改</button>
            {err && <div className="error">{err}</div>}
            {ok && <div style={{ color: '#22c55e', marginTop: 8 }}>{ok}</div>}
        </div>
    )
    if (inline) return form
    return (<div className="login-wrap"><div style={{ width: 420 }}>{form}</div></div>)
}

// ===== 仪表盘 =====
function Dashboard() {
    const [stats, setStats] = useState(null)
    useEffect(() => { api('/dashboard/summary').then(r => setStats(r.data)) }, [])
    if (!stats) return <div className="muted">加载中...</div>
    const cards = [
        ['漏洞总数', stats.total_vulns], ['资产数', stats.total_assets],
        ['高危漏洞', stats.critical_count], ['扫描任务', stats.total_tasks],
    ]
    return (
        <div>
            <div className="grid">
                {cards.map(([l, n]) => (
                    <div className="stat" key={l}><div className="num">{n ?? 0}</div><div className="label">{l}</div></div>
                ))}
            </div>
            <div className="card" style={{ marginTop: 20 }}>
                <h3>CVE 漏洞库概览</h3>
                <div className="muted">CVE 总数：{stats.total_cves ?? 0} · AI 审计问题：{stats.total_audit_issues ?? 0}</div>
            </div>
        </div>
    )
}

// ===== 资产 =====
function Assets({ onWebScan }) {
    const [items, setItems] = useState([])
    const [name, setName] = useState('')
    const [ip, setIp] = useState('')
    const [url, setUrl] = useState('')
    const [type, setType] = useState('SERVER')
    useEffect(() => { load() }, [])
    async function load() { api('/assets').then(r => setItems(r.items || [])) }
    async function create(e) {
        e.preventDefault()
        const r = await api('/assets', { method: 'POST', body: JSON.stringify({ name, ip, url: url || null, type }) })
        if (r.success !== false) { setName(''); setIp(''); setUrl(''); load() }
    }
    return (
        <div>
            <div className="card">
                <h3>添加资产</h3>
                <form className="row" onSubmit={create}>
                    <input placeholder="名称 *" value={name} onChange={e => setName(e.target.value)} required />
                    <input placeholder="IP *" value={ip} onChange={e => setIp(e.target.value)} required />
                    <input placeholder="网址 http(s)://..." value={url} onChange={e => setUrl(e.target.value)} />
                    <select value={type} onChange={e => setType(e.target.value)}>
                        <option value="SERVER">SERVER</option>
                        <option value="WEB">WEB</option>
                        <option value="WORKSTATION">WORKSTATION</option>
                        <option value="PRINTER">PRINTER</option>
                    </select>
                    <button type="submit">添加</button>
                </form>
            </div>
            <div className="card">
                <h3>资产列表（{items.length}）</h3>
                <table><thead><tr><th>名称</th><th>IP</th><th>网址</th><th>类型</th><th>状态</th><th>操作</th></tr></thead>
                    <tbody>{items.map(a => (
                        <tr key={a.id}><td>{a.name}</td><td>{a.ip}</td>
                            <td>{a.url ? (/^https?:\/\//i.test(a.url) ? <a href={a.url} target="_blank" rel="noreferrer">{a.url}</a> : a.url) : '-'}</td>
                            <td>{a.type}</td><td>{a.status}</td>
                            <td>{a.url ? <button className="secondary" onClick={() => onWebScan && onWebScan(a.url)}>Web扫描</button> : '-'}</td></tr>
                    ))}</tbody></table>
            </div>
        </div>
    )
}

// ===== 扫描任务 =====
function Scans() {
    const [items, setItems] = useState([])
    useEffect(() => { api('/scans').then(r => setItems(r.items || [])) }, [])
    return (
        <div className="card">
            <h3>扫描任务（{items.length}）</h3>
            <table><thead><tr><th>目标</th><th>类型</th><th>状态</th><th>漏洞数</th></tr></thead>
                <tbody>{items.map(t => (
                    <tr key={t.id}><td>{t.target}</td><td>{t.scan_type}</td>
                        <td>{t.status}</td><td>{t.vuln_count}</td></tr>
                ))}</tbody>
            </table>
        </div>
    )
}

// ===== Web 扫描（异步 + 轮询）=====
function WebScan({ initialUrl }) {
    const [url, setUrl] = useState(initialUrl || '')
    const [result, setResult] = useState(null)
    const [busy, setBusy] = useState(false)
    const [jobMsg, setJobMsg] = useState('')
    const [history, setHistory] = useState([])
    useEffect(() => { api('/webscan/results').then(r => setHistory(r.data || [])) }, [])
    async function run() {
        setBusy(true); setResult(null); setJobMsg('任务提交中...')
        const r = await api('/webscan', { method: 'POST', body: JSON.stringify({ target_url: url, do_directory: true, do_zap: false }) })
        const jobId = r.data && r.data.job_id
        if (!jobId) { setBusy(false); setJobMsg(r.message || '提交失败'); return }
        const timer = setInterval(async () => {
            const j = await api(`/webscan/jobs/${jobId}`)
            const job = j.data
            if (!job) return
            if (job.status === 'completed') {
                clearInterval(timer); setResult(job.result); setBusy(false); setJobMsg('')
                api('/webscan/results').then(x => setHistory(x.data || []))
            } else if (job.status === 'failed') {
                clearInterval(timer); setBusy(false); setJobMsg('扫描失败: ' + (job.error || ''))
            } else {
                setJobMsg(job.status === 'running' ? '扫描中...' : '等待中...')
            }
        }, 1500)
    }
    return (
        <div>
            <div className="card">
                <h3>Web 应用安全扫描</h3>
                <div className="row">
                    <input placeholder="https://target.example.com" value={url} onChange={e => setUrl(e.target.value)} />
                    <button onClick={run} disabled={busy}>{busy ? '扫描中...' : '开始扫描'}</button>
                </div>
                {jobMsg && <div className="muted" style={{ marginBottom: 8 }}>{jobMsg}</div>}
                {result && (
                    <div style={{ marginTop: 14 }}>
                        <div className="muted">指纹：{(result.fingerprint?.products || []).map(p => p.product + (p.version ? ' ' + p.version : '')).join(', ') || '无'}</div>
                        <h3 style={{ marginTop: 12 }}>发现（{result.findings?.length || 0}）</h3>
                        <table><thead><tr><th>类别</th><th>标题</th><th>严重度</th></tr></thead>
                            <tbody>{(result.findings || []).map((f, i) => (
                                <tr key={i}><td>{f.category}</td><td>{f.title}</td>
                                    <td><span className={'badge ' + f.severity}>{f.severity}</span></td></tr>
                            ))}</tbody></table>
                        {result.zap && !result.zap.available && <div className="muted" style={{ marginTop: 8 }}>ZAP 未启用：{result.zap.reason}</div>}
                    </div>
                )}
            </div>
            <div className="card"><h3>历史扫描结果</h3>
                <table><thead><tr><th>目标</th><th>类别</th><th>标题</th><th>严重度</th></tr></thead>
                    <tbody>{history.map(h => (
                        <tr key={h.id}><td>{h.target}</td><td>{h.category}</td><td>{h.title}</td>
                            <td><span className={'badge ' + h.severity}>{h.severity}</span></td></tr>
                    ))}</tbody></table>
            </div>
        </div>
    )
}

// ===== 弱口令（异步 + 轮询）=====
function WeakPass() {
    const [host, setHost] = useState('')
    const [port, setPort] = useState('80')
    const [protocol, setProtocol] = useState('http')
    const [result, setResult] = useState(null)
    const [busy, setBusy] = useState(false)
    async function run() {
        setBusy(true); setResult(null)
        const r = await api('/weakpass/scan', { method: 'POST', body: JSON.stringify({ host, port: parseInt(port), protocol }) })
        const jobId = r.data && r.data.job_id
        if (!jobId) { setBusy(false); setResult(r.data || r); return }
        const timer = setInterval(async () => {
            const j = await api(`/weakpass/jobs/${jobId}`)
            const job = j.data
            if (!job) return
            if (job.status === 'completed') { clearInterval(timer); setResult(job.result); setBusy(false) }
            else if (job.status === 'failed') { clearInterval(timer); setBusy(false); setResult({ error: job.error }) }
        }, 1500)
    }
    return (
        <div className="card">
            <h3>弱口令检测</h3>
            <div className="row">
                <input placeholder="目标主机" value={host} onChange={e => setHost(e.target.value)} />
                <input placeholder="端口" value={port} onChange={e => setPort(e.target.value)} />
                <select value={protocol} onChange={e => setProtocol(e.target.value)}>
                    <option value="http">http</option><option value="https">https</option>
                    <option value="ftp">ftp</option><option value="ssh">ssh</option>
                </select>
                <button onClick={run} disabled={busy}>{busy ? '检测中...' : '检测'}</button>
            </div>
            {result && <pre>{JSON.stringify(result, null, 2)}</pre>}
        </div>
    )
}

const WF_STATES = ['OPEN', 'CONFIRMED', 'IN_PROGRESS', 'FIXED', 'VERIFIED', 'CLOSED', 'REOPENED', 'FALSE_POSITIVE', 'DUPLICATE']

// ===== 漏洞处置 =====
function Workflow() {
    const [items, setItems] = useState([])
    const [ref, setRef] = useState('')
    const [title, setTitle] = useState('')
    useEffect(() => { load() }, [])
    async function load() { api('/workflow/dispositions').then(r => setItems(r.data || [])) }
    async function create() {
        await api('/workflow/dispositions', { method: 'POST', body: JSON.stringify({ vuln_ref: ref, vuln_title: title, severity: 'HIGH' }) })
        setRef(''); setTitle(''); load()
    }
    async function transition(id, status) {
        await api(`/workflow/dispositions/${id}/transition`, { method: 'POST', body: JSON.stringify({ to_status: status }) })
        load()
    }
    return (
        <div className="card">
            <h3>漏洞处置工作流</h3>
            <div className="row">
                <input placeholder="漏洞引用 (CVE/资产)" value={ref} onChange={e => setRef(e.target.value)} />
                <input placeholder="标题" value={title} onChange={e => setTitle(e.target.value)} />
                <button onClick={create}>新建处置</button>
            </div>
            <table><thead><tr><th>引用</th><th>标题</th><th>状态</th><th>指派</th><th>操作</th></tr></thead>
                <tbody>{items.map(d => (
                    <tr key={d.id}>
                        <td>{d.vuln_ref}</td><td>{d.vuln_title}</td>
                        <td><span className="badge INFO">{d.status}</span></td>
                        <td>{d.assignee || '-'}</td>
                        <td><select defaultValue="" onChange={e => { if (e.target.value) transition(d.id, e.target.value) }}>
                            <option value="">流转...</option>
                            {WF_STATES.map(s => <option key={s} value={s}>{s}</option>)}
                        </select></td>
                    </tr>
                ))}</tbody></table>
        </div>
    )
}

// ===== 用户管理 =====
function Users() {
    const [items, setItems] = useState([])
    const [username, setUsername] = useState('')
    const [password, setPassword] = useState('')
    const [role, setRole] = useState('viewer')
    useEffect(() => { load() }, [])
    async function load() { api('/users').then(r => setItems(r.data || [])) }
    async function create() {
        await api('/users', { method: 'POST', body: JSON.stringify({ username, password, role }) })
        setUsername(''); setPassword(''); load()
    }
    return (
        <div className="card">
            <h3>用户管理（RBAC）</h3>
            <div className="row">
                <input placeholder="用户名" value={username} onChange={e => setUsername(e.target.value)} />
                <input placeholder="密码" type="password" value={password} onChange={e => setPassword(e.target.value)} />
                <select value={role} onChange={e => setRole(e.target.value)}>
                    <option value="admin">admin</option><option value="analyst">analyst</option>
                    <option value="auditor">auditor</option><option value="viewer">viewer</option>
                </select>
                <button onClick={create}>创建用户</button>
            </div>
            <table><thead><tr><th>用户名</th><th>角色</th><th>姓名</th><th>状态</th></tr></thead>
                <tbody>{items.map(u => (
                    <tr key={u.id}><td>{u.username}</td><td>{u.role}</td>
                        <td>{u.full_name || '-'}</td><td>{u.active ? '启用' : '停用'}</td></tr>
                ))}</tbody></table>
        </div>
    )
}

// ===== 主应用 =====
export default function App() {
    const [user, setUser] = useState(() => JSON.parse(localStorage.getItem('user') || 'null'))
    const [page, setPage] = useState('dashboard')
    const [webScanUrl, setWebScanUrl] = useState('')
    if (!user) return <Login onLogin={setUser} />
    if (user.must_change_password) return <ChangePassword user={user} onDone={setUser} />
    const nav = [
        ['dashboard', '仪表盘'], ['assets', '资产'], ['scans', '扫描任务'],
        ['webscan', 'Web 扫描'], ['weakpass', '弱口令'], ['workflow', '漏洞处置'],
        ['users', '用户管理'],
    ]
    return (
        <div className="app">
            <div className="sidebar">
                <div className="brand">AI漏洞扫描系统 Pro<small>v2.1.0</small></div>
                <div className="nav">
                    {nav.map(([k, l]) => (
                        <button key={k} className={page === k ? 'active' : ''}
                            onClick={() => { if (k === 'webscan') setWebScanUrl(''); setPage(k) }}>{l}</button>
                    ))}
                </div>
            </div>
            <div className="main">
                <div className="topbar">
                    <span className="user">{user.full_name || user.username}（{user.role}）</span>
                    <button className="secondary" onClick={() => setPage('changepw')}>修改密码</button>
                    <button className="secondary" onClick={() => { localStorage.clear(); setUser(null) }}>退出</button>
                </div>
                {page === 'changepw' && <ChangePassword user={user} onDone={setUser} inline />}
                {page === 'dashboard' && <Dashboard />}
                {page === 'assets' && <Assets onWebScan={(u) => { setWebScanUrl(u); setPage('webscan') }} />}
                {page === 'scans' && <Scans />}
                {page === 'webscan' && <WebScan key={webScanUrl} initialUrl={webScanUrl} />}
                {page === 'weakpass' && <WeakPass />}
                {page === 'workflow' && <Workflow />}
                {page === 'users' && <Users />}
            </div>
        </div>
    )
}
