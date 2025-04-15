import re

def is_valid_domain(domain: str) -> bool:
    """
    Простейшая валидация доменного имени.
    """
    pattern = re.compile(r"^(?!-)[A-Za-z0-9-]{1,63}(?<!-)\.[A-Za-z]{2,6}$")
    return bool(pattern.match(domain.strip().lower()))