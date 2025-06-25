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
import httpx
import ssl
import socket
from datetime import datetime
from typing import Dict, Any
import asyncio


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
            if code.isdigit() and int(code) < 600:
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

# def check_domain_expiry(domain: str) -> Dict[str, Any]:
#     """
#     Checks the domain registration expiration date via WHOIS.
#
#     Args:
#         domain (str): The domain name.
#
#     Returns:
#         dict: Expiry info or error:
#               {
#                   "valid": True,
#                   "expires_at": "2025-08-19",
#                   "days_left": 103
#               }
#               or
#               {
#                   "valid": False,
#                   "error": "..."
#               }
#     """
#     try:
#         w = whois.whois(domain)
#         expires_at = w.expiration_date
#
#         if isinstance(expires_at, list):
#             expires_at = next((d for d in expires_at if isinstance(d, datetime)), None)
#
#         if not isinstance(expires_at, datetime):
#             raise ValueError("Could not determine expiration date.")
#
#         days_left = (expires_at - datetime.utcnow()).days
#
#         return {
#             "valid": True,
#             "expires_at": expires_at.strftime("%Y-%m-%d"),
#             "days_left": days_left
#         }
#
#     except Exception as e:
#         return {
#             "valid": False,
#             "error": str(e)
#         }


def _check_domain_expiry_sync(domain: str) -> Dict[str, Any]:
    """
    Checks domain expiry using the system `whois` command for better TLD support.
    """
    try:
        result = subprocess.run(["whois", domain], capture_output=True, text=True, timeout=10)

        if result.returncode != 0:
            raise RuntimeError("WHOIS command failed")

        output = result.stdout

        # Try multiple patterns for expiration date
        patterns = [
            r"Expiry Date:\s?(.+)",
            r"Expiration Date:\s?(.+)",
            r"Registry Expiry Date:\s?(.+)",
            r"paid-till:\s?(.+)"
        ]

        for pattern in patterns:
            match = re.search(pattern, output)
            if match:
                date_str = match.group(1).strip()

                # Try parsing multiple formats
                for fmt in ("%Y-%m-%d", "%d-%b-%Y", "%Y.%m.%d", "%Y-%m-%dT%H:%M:%SZ"):
                    try:
                        expires_at = datetime.strptime(date_str, fmt)
                        days_left = (expires_at - datetime.utcnow()).days
                        return {
                            "valid": True,
                            "expires_at": expires_at.strftime("%Y-%m-%d"),
                            "days_left": days_left
                        }
                    except ValueError:
                        continue

        raise ValueError("Could not parse expiration date.")

    except Exception as e:
        return {
            "valid": False,
            "error": f"WHOIS error: {str(e)}"
        }


async def check_domain_expiry(domain: str) -> Dict[str, Any]:
    return await asyncio.to_thread(_check_domain_expiry_sync, domain)