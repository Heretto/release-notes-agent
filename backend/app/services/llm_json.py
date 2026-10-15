"""Pulling a JSON document out of a model's reply.

Models asked for "JSON only" still wrap it in code fences or a sentence of preamble often
enough that every structured step needs the same tolerant parse.
"""

import json
import re
from typing import Any

_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


def extract_json(text: str) -> Any:
    """Parse the first JSON object or array in ``text``.

    Raises ``ValueError`` when nothing parses, with the start of the text in the message so
    the failure is diagnosable from a log line.
    """
    if text is None:
        raise ValueError("No content to parse")
    candidates = []
    fenced = _FENCE.search(text)
    if fenced:
        candidates.append(fenced.group(1))
    candidates.append(text)

    for candidate in candidates:
        stripped = candidate.strip()
        try:
            return json.loads(stripped)
        except (json.JSONDecodeError, ValueError):
            pass
        # Find the outermost object or array by bracket matching from the first opener.
        for opener, closer in (("{", "}"), ("[", "]")):
            start = stripped.find(opener)
            if start < 0:
                continue
            depth = 0
            in_string = False
            escape = False
            for index in range(start, len(stripped)):
                char = stripped[index]
                if in_string:
                    if escape:
                        escape = False
                    elif char == "\\":
                        escape = True
                    elif char == '"':
                        in_string = False
                    continue
                if char == '"':
                    in_string = True
                elif char == opener:
                    depth += 1
                elif char == closer:
                    depth -= 1
                    if depth == 0:
                        try:
                            return json.loads(stripped[start:index + 1])
                        except (json.JSONDecodeError, ValueError):
                            break
    preview = (text or "")[:200].replace("\n", " ")
    raise ValueError(f"The model did not return JSON: {preview!r}")
