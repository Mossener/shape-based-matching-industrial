"""Parse fixed GCC dependency rules, preserving every ordered alias occurrence.

Adapted from the repository's hash-prototype dependency parser. This module
records local compiler inputs, not every linker, operating-system or loader read.
"""
from pathlib import Path

TARGETS = ("v11_reference.o", "v18_reference.o", "direct_core.o", "matcher_contract.o")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def parse_depfile(data, target, working_directory):
    require(isinstance(data, bytes) and b"\0" not in data, "Invalid dependency bytes")
    try:
        text = data.decode("utf-8")
    except UnicodeError as error:
        raise ValueError("Dependency file must be UTF-8") from error
    require(target in TARGETS, "Fixed four-TU dependency target required")
    text = text.replace("\\\r\n", "").replace("\\\n", "").strip()
    require(text.startswith(target + ":"), "Dependency target differs")
    text = text[len(target) + 1:]
    require("\r" not in text and "\n" not in text, "Multiple dependency rules rejected")
    tokens, token, position = [], [], 0
    while position < len(text):
        char = text[position]
        if char in " \t":
            if token:
                tokens.append("".join(token))
                token = []
        elif char == "\\":
            require(position + 1 < len(text), "Truncated dependency escape")
            following = text[position + 1]
            if following in " \t#:$\\":
                token.append(following)
                position += 1
            else:
                token.append(char)
        elif char == "$":
            require(position + 1 < len(text) and text[position + 1] == "$",
                    "Unescaped Make dependency dollar")
            token.append("$")
            position += 1
        else:
            require(char != "#", "Unescaped Make dependency comment")
            token.append(char)
        position += 1
    if token:
        tokens.append("".join(token))
    require(tokens, "Empty dependency list")
    cwd = Path(working_directory).resolve(strict=True)
    # Real GCC can emit several lexical aliases for one resolved file. Keep
    # every occurrence, in order; pre-M and actual-MD must agree on that list.
    return [(Path(value) if Path(value).is_absolute() else cwd / value).resolve()
            for value in tokens]
