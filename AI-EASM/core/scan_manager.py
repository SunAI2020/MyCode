# -*- coding: utf-8 -*-
"""扫描管理"""
import threading, socket, ssl, re
from datetime import datetime

# ===== banner/服务识别（端口扫描增强） =====
_BANNER_FIRST_PORTS = {21, 22, 25, 110, 143, 3306, 5432, 6379, 2181, 27017, 5900, 1521, 1433, 3389}
_HTTP_PORTS = {80, 8000, 8080, 8081, 8088, 8880, 8888, 9000, 9080, 9090, 8082}
_TLS_PORTS = {443, 8443, 9443, 993, 995, 465, 636, 989, 990, 10443}

class ScanManager:
    def __init__(self, org_manager):
        self.org_mgr = org_manager
        self.current_scanner = None
        self.scan_thread = None
        self._stop_event = threading.Event()
        self._progress_cb = None
        self._result_cb = None
        self._log_cb = None

    def set_callbacks(self, progress_cb=None, result_cb=None, log_cb=None):
        self._progress_cb = progress_cb
        self._result_cb = result_cb
        self._log_cb = log_cb

    def _log(self, msg):
        if self._log_cb: self._log_cb(msg)

    def _progress(self, pct, status=""):
        if self._progress_cb: self._progress_cb(pct, status)

    def _result(self, host, port, service, version, vulns):
        if self._result_cb: self._result_cb(host, port, service, version, vulns)

    def scan_target(self, org_id, target, ports=None, scan_type="quick"):
        if self.scan_thread and self.scan_thread.is_alive():
            self._log("[WARN] scan already running")
            return None
        task_id = self.org_mgr.add_task(org_id,
            f"Scan {target}", scan_type, target, ports or "")
        self._stop_event.clear()
        self.scan_thread = threading.Thread(
            target=self._run_scan,
            args=(task_id, org_id, target, ports, scan_type), daemon=True)
        self.scan_thread.start()
        return task_id

    def _run_scan(self, task_id, org_id, target, ports, scan_type):
        try:
            self._log(f"[START] target: {target}")
            self._progress(0, "parsing...")
            found = self._basic_port_scan(target, ports)
            self.org_mgr.update_task(task_id, status="completed", progress_pct=100,
                hosts_found=1, services_found=found,
                end_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            self._progress(100, "done")
            self._log(f"[DONE] {found} open ports")
        except Exception as e:
            self._log(f"[FAIL] {e}")
            self.org_mgr.update_task(task_id, status="failed",
                end_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    def _basic_port_scan(self, target, ports_str):
        from utils.helpers import parse_port_string
        from config.settings import COMMON_PORTS
        ports = parse_port_string(ports_str) if ports_str else list(COMMON_PORTS.keys())[:20]
        try:
            ip = socket.gethostbyname(target)
        except:
            ip = target
        total = len(ports)
        found = 0
        for i, port in enumerate(ports):
            if self._stop_event.is_set(): break
            self._progress(int(80*(i+1)/total), f"port {port}")
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            try:
                if sock.connect_ex((ip, port)) == 0:
                    svc = COMMON_PORTS.get(port, f"unknown-{port}")
                    ver = ""
                    try:
                        s2, v2 = self._grab_banner(sock, ip, port)
                        if s2: svc = s2
                        if v2: ver = v2
                    except Exception:
                        pass
                    self._result(ip, port, svc, ver, [])
                    found += 1
            except Exception:
                pass
            finally:
                try: sock.close()
                except Exception: pass
        return found

    # ===== banner 抓取与服务识别 =====
    def _grab_banner(self, sock, ip, port):
        """在已连接的 socket 上识别服务，返回 (service, version)；失败返回空串。"""
        try:
            if port in _TLS_PORTS:
                return self._grab_tls(sock, ip, port)
            raw = b""
            if port in _HTTP_PORTS:
                raw = self._http_probe(sock, ip, port)
            else:
                raw = self._recv(sock, 0.6)          # 等服务端主动 banner
                if not raw:
                    raw = self._http_probe(sock, ip, port)
            return self._parse_banner(raw, port)
        except Exception:
            return ("", "")

    def _recv(self, sock, timeout):
        try:
            sock.settimeout(timeout)
            chunks, total = [], 0
            while total < 4096:
                c = sock.recv(1024)
                if not c: break
                chunks.append(c); total += len(c)
                if len(chunks) >= 4: break
            return b"".join(chunks)
        except Exception:
            return b""

    def _http_probe(self, sock, ip, port):
        try:
            req = (f"GET / HTTP/1.0\r\nHost: {ip}:{port}\r\n"
                   "User-Agent: Mozilla/5.0\r\nAccept: */*\r\n\r\n").encode("latin-1")
            sock.sendall(req)
            return self._recv(sock, 1.5)
        except Exception:
            return b""

    def _grab_tls(self, sock, ip, port):
        """TLS 握手读证书 CN，并尝试 HTTP over TLS 取 Server 头。

        CERT_NONE 为刻意：主动探测陌生资产的 443，目标证书多为自签名/过期/域名不匹配，
        严格校验会握手失败拿不到 CN。此处 CN 仅作 banner 展示（version 列），不落库、
        不作为可信子域名资产——子域名发现走 CertSpotter/crt.sh 等独立验证源。
        """
        cn = ""
        try:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            tls = ctx.wrap_socket(sock, server_hostname=ip)
            cert = tls.getpeercert()
            if cert:
                for rdn in cert.get("subject") or ():
                    for k, v in rdn:
                        if k == "commonName":
                            cn = str(v); break
            try:
                tls.sendall(f"GET / HTTP/1.0\r\nHost: {ip}\r\n\r\n".encode("latin-1"))
                svc, ver = self._parse_banner(self._recv(tls, 1.0), port)
                if svc:
                    return (svc, ver or (f"cn={cn}(未验证)" if cn else ""))
            except Exception:
                pass
            return ("HTTPS", f"cn={cn}(未验证)" if cn else "TLS")
        except Exception:
            return ("", "")

    def _parse_banner(self, raw, port):
        """从原始 banner 提取 (service, version)。"""
        text = raw.decode("utf-8", "ignore")
        if not text.strip():
            return ("", "")
        m = re.search(r'(?im)^Server:\s*([^\r\n]+)', text)
        if m:
            server = m.group(1).strip()
            return (server.split("/")[0].strip() or server, server)
        m = re.search(r'SSH-(\d+\.\d+)-(\S+)', text)
        if m:
            return ("SSH", m.group(2))
        m = re.search(r'^220[\s\-]*(.*)$', text, re.M)
        if m:
            line = m.group(1).strip()
            return ("SMTP", line) if ("ESMTP" in line or port == 25) else ("FTP", line)
        if text.startswith("+OK"):
            return ("POP3", text.split("\r\n")[0])
        if text.startswith("* OK"):
            return ("IMAP", text.split("\r\n")[0])
        m = re.search(r'redis_version:(\S+)', text)
        if m:
            return ("Redis", m.group(1))
        m = re.search(r'(PostgreSQL\s+[\d.]+)', text)
        if m:
            return ("PostgreSQL", m.group(1))
        m = re.search(r'RFB\s+(\d+\.\d+)', text)
        if m:
            return ("VNC", f"RFB {m.group(1)}")
        if port == 3306 and len(raw) > 5 and raw[4:5] == b"\x0a":
            try:
                payload = raw[5:]
                end = payload.index(b"\x00")
                return ("MySQL", payload[:end].decode("utf-8", "ignore"))
            except Exception:
                pass
        return ("", "")

    def stop_scan(self):
        self._stop_event.set()
        if self.current_scanner and hasattr(self.current_scanner, 'cancel'):
            self.current_scanner.cancel()
