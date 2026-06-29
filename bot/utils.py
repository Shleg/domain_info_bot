"""
Utility functions for domain validation and monitoring.
Includes:
- Domain name format validation
- HTTP/HTTPS availability checks
- SSL certificate expiration checks
- Domain registration expiration checks
"""
import subprocess
import re
import time
import httpx
import ssl
import socket
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from datetime import datetime
from typing import Dict, Any, Optional, Tuple
import asyncio

WHOIS_CMD_TIMEOUT = 45
WHOIS_PYTHON_TIMEOUT = 45
WHOIS_REFERRAL_ATTEMPTS = 3
WHOIS_REFERRAL_RETRY_DELAY = 5


def is_valid_domain(domain: str) -> bool:
    """
    Validates the format of a domain name.

    Args:
        domain (str): The domain name to validate.

    Returns:
        bool: True if the domain format is valid, False otherwise.
    """
    pattern = re.compile(r"^(?!-)[A-Za-z0-9-]{1,63}(?<!-)\.[A-Za-z]{2,6}$")
    return bool(pattern.match(domain.strip().lower()))


async def check_http_https(domain: str) -> Dict[str, Dict[str, Any]]:
    """
    Checks domain availability over HTTP and HTTPS protocols in parallel, reusing a single AsyncClient.
    Makes up to 3 attempts with httpx, then tries curl if all fail. Only notifies if all fail.
    """
    results = {}
    protocols = ["http", "https"]
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Connection": "keep-alive"
    }

    async def fetch_with_retries(protocol: str, client: httpx.AsyncClient):
        url = f"{protocol}://{domain}"
        last_error = None
        for attempt in range(3):
            try:
                response = await client.get(url, headers=headers)
                return protocol, {"status": "ok", "code": response.status_code}
            except Exception as e:
                last_error = str(e)
                await asyncio.sleep(1)
        # If all httpx attempts failed, try curl
        curl_result = await run_curl_check(url)
        if curl_result["ok"]:
            return protocol, {"status": "ok", "code": curl_result["code"]}
        else:
            return protocol, {"status": "fail", "error": f"httpx: {last_error}; curl: {curl_result['error']}"}

    async def run_curl_check(url: str) -> dict:
        # Compose curl command with headers
        curl_cmd = [
            "curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
            "-A", headers["User-Agent"],
            "-H", f"Accept: {headers['Accept']}",
            "-H", f"Accept-Language: {headers['Accept-Language']}",
            "-H", f"Connection: {headers['Connection']}",
            "--max-time", "10",
            url
        ]
        try:
            proc = await asyncio.create_subprocess_exec(
                *curl_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            code = stdout.decode().strip()
            if code.isdigit() and 100 <= int(code) <= 599:
                return {"ok": True, "code": int(code)}
            else:
                return {"ok": False, "error": f"curl status: {code}, stderr: {stderr.decode().strip()}"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    async with httpx.AsyncClient(timeout=5.0, follow_redirects=True) as client:
        tasks = [fetch_with_retries(proto, client) for proto in protocols]
        results_list = await asyncio.gather(*tasks)
        for proto, result in results_list:
            results[proto] = result

    return results


def _check_ssl_sync(domain: str) -> Dict[str, Any]:
    """
    Checks the SSL certificate of a domain.

    Args:
        domain (str): The domain name.

    Returns:
        dict: Certificate information or error:
              {
                  "valid": True,
                  "expires_at": "2025-06-01",
                  "days_left": 47,
                  "issuer": "Let's Encrypt"
              }
              or
              {
                  "valid": False,
                  "error": "..."
              }
    """
    try:
        context = ssl.create_default_context()
        with socket.create_connection((domain, 443), timeout=5) as sock:
            with context.wrap_socket(sock, server_hostname=domain) as ssock:
                cert = ssock.getpeercert()

        expires_str = cert['notAfter']
        expires_at = datetime.strptime(expires_str, '%b %d %H:%M:%S %Y %Z')
        days_left = (expires_at - datetime.utcnow()).days

        issuer_parts = [x[0][1] for x in cert.get("issuer", [])]
        issuer = ", ".join(issuer_parts)

        return {
            "valid": True,
            "expires_at": expires_at.strftime("%Y-%m-%d"),
            "days_left": days_left,
            "issuer": issuer
        }

    except Exception as e:
        return {
            "valid": False,
            "error": str(e)
        }

async def check_ssl(domain: str) -> Dict[str, Any]:
    return await asyncio.to_thread(_check_ssl_sync, domain)


_WHOIS_DATE_PATTERNS = (
    r"Registry Expiry Date:\s*(.+)",
    r"Registrar Registration Expiration Date:\s*(.+)",
    r"paid-till:\s*(.+)",
    r"Expiry Date:\s*(.+)",
    r"Expiration Date:\s*(.+)",
)

_WHOIS_DATE_FORMATS = (
    "%Y-%m-%dT%H:%M:%S.%fZ",
    "%Y-%m-%dT%H:%M:%SZ",
    "%Y-%m-%d",
    "%d-%b-%Y",
    "%Y.%m.%d",
)


def _expiry_result(expires_at: datetime) -> Dict[str, Any]:
    if expires_at.tzinfo is not None:
        expires_at = expires_at.replace(tzinfo=None)
    days_left = (expires_at - datetime.utcnow()).days
    return {
        "valid": True,
        "expires_at": expires_at.strftime("%Y-%m-%d"),
        "days_left": days_left,
    }


def _parse_whois_text(output: str) -> Optional[Dict[str, Any]]:
    for pattern in _WHOIS_DATE_PATTERNS:
        match = re.search(pattern, output, re.IGNORECASE)
        if not match:
            continue
        date_str = match.group(1).strip()
        for fmt in _WHOIS_DATE_FORMATS:
            try:
                return _expiry_result(datetime.strptime(date_str, fmt))
            except ValueError:
                continue
    return None


def _run_whois(domain: str, server: Optional[str] = None) -> subprocess.CompletedProcess[str]:
    cmd = ["whois"]
    if server:
        cmd.extend(["-h", server])
    cmd.append(domain)
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=WHOIS_CMD_TIMEOUT,
    )


def _extract_whois_server(output: str) -> Optional[str]:
    for prefix in ("refer:", "whois:"):
        for line in output.splitlines():
            stripped = line.strip()
            if stripped.lower().startswith(prefix):
                return stripped.split(":", 1)[1].strip()
    return None


def _whois_via_command(domain: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    try:
        result = _run_whois(domain)
        if result.returncode != 0:
            return None, "WHOIS command failed"

        parsed = _parse_whois_text(result.stdout)
        if parsed is not None:
            return parsed, None

        server = _extract_whois_server(result.stdout)
        if server:
            last_error = "Could not parse expiration date"
            for attempt in range(WHOIS_REFERRAL_ATTEMPTS):
                if attempt:
                    time.sleep(WHOIS_REFERRAL_RETRY_DELAY)
                referral = _run_whois(domain, server)
                if referral.returncode != 0:
                    last_error = "referral WHOIS command failed"
                    continue
                if not referral.stdout.strip():
                    last_error = "referral returned empty response"
                    continue
                parsed = _parse_whois_text(referral.stdout)
                if parsed is not None:
                    return parsed, None
                last_error = "Could not parse expiration date from referral"
            return None, last_error

        return None, "Could not parse expiration date"
    except subprocess.TimeoutExpired:
        return None, f"timed out after {WHOIS_CMD_TIMEOUT} seconds"
    except Exception as e:
        return None, str(e)


def _expiration_from_python_record(record: Any) -> Optional[Dict[str, Any]]:
    expiration = (
        record.get("expiration_date")
        if isinstance(record, dict)
        else getattr(record, "expiration_date", None)
    )
    if expiration is not None:
        if isinstance(expiration, list):
            expiration = max(expiration)
        if isinstance(expiration, datetime):
            return _expiry_result(expiration)

    raw = record.get("raw") if isinstance(record, dict) else None
    if raw:
        if isinstance(raw, list):
            raw = "\n".join(str(part) for part in raw)
        return _parse_whois_text(str(raw))
    return None


def _whois_via_python(domain: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    import whois as python_whois

    strategies: tuple[tuple[str, dict[str, Any]], ...] = (
        ("builtin", {"timeout": WHOIS_PYTHON_TIMEOUT, "inc_raw": True}),
        ("command", {"timeout": WHOIS_PYTHON_TIMEOUT, "inc_raw": True, "command": True}),
    )
    errors: list[str] = []
    for label, kwargs in strategies:
        try:
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(python_whois.whois, domain, **kwargs)
                record = future.result(timeout=WHOIS_PYTHON_TIMEOUT + 5)
        except FuturesTimeoutError:
            errors.append(f"{label}: timed out after {WHOIS_PYTHON_TIMEOUT} seconds")
            continue
        except Exception as e:
            errors.append(f"{label}: {e}")
            continue

        parsed = _expiration_from_python_record(record)
        if parsed is not None:
            return parsed, None
        errors.append(f"{label}: no expiration date")

    return None, "; ".join(errors) if errors else "lookup failed"


def _check_domain_expiry_sync(domain: str) -> Dict[str, Any]:
    """
    Checks domain expiry via system ``whois`` and python-whois, returning the
    first successful parse (system whois is preferred when both succeed).
    """
    cmd_result, cmd_error = _whois_via_command(domain)
    if cmd_result is not None:
        return cmd_result

    py_result, py_error = _whois_via_python(domain)
    if py_result is not None:
        return py_result

    errors: list[str] = []
    if cmd_error:
        errors.append(f"whois: {cmd_error}")
    if py_error:
        errors.append(f"python-whois: {py_error}")
    return {
        "valid": False,
        "error": "; ".join(errors) or "all methods failed",
    }


async def check_domain_expiry(domain: str) -> Dict[str, Any]:
    return await asyncio.to_thread(_check_domain_expiry_sync, domain)