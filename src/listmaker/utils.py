import re

import arabic_reshaper
from bidi.algorithm import get_display


def format_terminal_text(text: str) -> str:
    """Shape and order mixed Arabic text for terminal display."""
    return get_display(arabic_reshaper.reshape(text))


def parse_selection(value: str, choice_count: int):
    """Parse ASCII or Arabic selection numbers."""
    normalized = value.strip().lower()
    if not normalized or normalized in ('s', 'skip'):
        return None

    match = re.search(r'\d+', normalized)
    if match:
        selection = int(match.group())
        if 1 <= selection <= choice_count:
            return selection - 1

    return -1
