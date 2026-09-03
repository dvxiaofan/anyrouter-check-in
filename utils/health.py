#!/usr/bin/env python3
"""
网站健康检查模块：签到前探测网站是否可达。

只有硬错误（DNS 解析失败 / TCP 连接拒绝 / TLS 握手失败 / 连接超时）
才判定为「不可达」。HTTP 4xx/5xx 视为网站活着（可能是 WAF 拦截或服务器错误）。
"""

import socket
import time

import httpx

# 硬错误：只包含明确的「网站挂了」类异常
# ConnectTimeout 已继承 ConnectError，无需额外列出
# ReadTimeout 不算——服务器已接受连接，可能是慢/盾
_HARD_ERRORS = (
    socket.gaierror,
    httpx.ConnectError,
    httpx.RemoteProtocolError,
)


def check_domain_health(
    domain: str,
    timeout: int = 10,
    retries: int = 1,
    retry_delay: int = 30,
) -> tuple[bool, str]:
    """
    检查一个域名是否可达。

    Args:
        domain: 域名（不含 scheme，如 'anyrouter.top'）
        timeout: 单次 HTTP 请求超时秒数
        retries: 重试次数（默认 1 次，总尝试 = retries + 1）
        retry_delay: 重试前等待秒数

    Returns:
        (is_healthy, message)
        - is_healthy=True:  网站可达，继续签到
        - is_healthy=False: 网站不可达，跳过签到
        - message: 检查结果说明
    """
    # ---- 阶段 1: DNS 解析 ----
    try:
        socket.getaddrinfo(domain, 443)
    except socket.gaierror as e:
        if retries > 0:
            time.sleep(retry_delay)
            return check_domain_health(domain, timeout, retries - 1, retry_delay)
        return False, f"DNS 解析失败: {domain} ({e})"
    except Exception as e:
        return False, f"DNS 解析异常: {domain} ({type(e).__name__})"

    # ---- 阶段 2: HTTPS 连接 ----
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            with httpx.Client(timeout=timeout, follow_redirects=False, verify=True) as client:
                resp = client.get(f"https://{domain}/")
            # 任何 HTTP 响应（包括 403/500）都说明网站活着
            return True, f"可达 (HTTP {resp.status_code})"
        except _HARD_ERRORS as e:
            last_error = e
            if attempt < retries:
                time.sleep(retry_delay)
        except Exception as e:
            # 非连接类异常（如 JSON 解析）→ 网站有响应，不算不可达
            return True, f"可达（非连接异常: {type(e).__name__}）"

    # 所有重试用完，分类错误信息
    assert last_error is not None
    err_str = str(last_error)

    if "SSL" in err_str or "CERTIFICATE" in err_str.upper() or "handshake" in err_str.lower():
        return False, f"TLS 握手失败: {domain}"
    if "refused" in err_str.lower():
        return False, f"连接被拒绝: {domain}:443"
    if "timeout" in err_str.lower():
        return False, f"连接超时: {domain}"
    return False, f"连接失败: {domain} ({err_str[:60]})"