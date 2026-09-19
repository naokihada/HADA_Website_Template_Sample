"""Block-aware built-in i18n helpers for master Markdown documents."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

MASTER_SUFFIX = "_master.md"
LOCALE_SUFFIX = re.compile(r"_(?P<locale>[A-Za-z][A-Za-z0-9-]*)\.md$")
DIRECTIVE_RE = re.compile(r"^<!--\s*i18n:\s*(?P<name>no-translate|end)\s*-->\s*$")
FENCE_RE = re.compile(r"^(?P<indent>\s*)(?P<fence>`{3,}|~{3,})(?P<info>.*)$")


@dataclass(frozen=True)
class Block:
    kind: str
    text: str
    translatable: bool = True
    comments_only: bool = False


def source_hash(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.replace("\r\n", "\n").encode("utf-8")).hexdigest()


def parse_blocks(body: str) -> list[Block]:
    """Split Markdown into safe translation units without translating code by default."""
    lines = body.splitlines(keepends=True)
    blocks: list[Block] = []
    buffer: list[str] = []
    protected = False
    code = False
    comments_only = False
    fence = ""

    def flush(kind: str = "prose", translatable: bool = True, comments: bool = False) -> None:
        if buffer:
            blocks.append(Block(kind, "".join(buffer), translatable, comments))
            buffer.clear()

    for line in lines:
        directive = DIRECTIVE_RE.match(line.strip())
        if directive:
            if directive.group("name") == "no-translate":
                flush()
                protected = True
            else:
                flush("protected", False)
                protected = False
            continue

        match = FENCE_RE.match(line)
        if match and not code:
            flush()
            code = True
            fence = match.group("fence")
            comments_only = "i18n-comments" in match.group("info").split()
            buffer.append(line)
            continue
        if code:
            buffer.append(line)
            if line.lstrip().startswith(fence):
                flush("code", comments_only, comments_only)
                code = False
                comments_only = False
            continue

        if protected:
            buffer.append(line)
        elif not line.strip():
            flush()
        else:
            buffer.append(line)

    flush("protected" if protected else "prose", not protected)
    return blocks


def protect_nontranslatable(text: str) -> tuple[str, dict[str, str]]:
    """Protect inline code, URLs, and HTML tags before provider translation."""
    values: dict[str, str] = {}
    patterns = [r"`[^`]+`", r"https?://[^\s)]+", r"<[^>]+>"]
    protected = text
    for pattern in patterns:
        for match in reversed(list(re.finditer(pattern, protected))):
            key = f"__I18N_KEEP_{len(values)}__"
            values[key] = match.group(0)
            protected = protected[: match.start()] + key + protected[match.end() :]
    return protected, values


def restore_nontranslatable(text: str, values: dict[str, str]) -> str:
    for key, value in values.items():
        text = text.replace(key, value)
    return text


def translate_comments_only(text: str, translator) -> str:
    lines = text.splitlines(keepends=True)
    result = []
    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith(("#", "//", "/*", "*", "<!--")):
            prefix = line[: len(line) - len(stripped)]
            result.append(prefix + translator(stripped.rstrip("\r\n")) + line[len(line.rstrip("\r\n")) :])
        else:
            result.append(line)
    return "".join(result)


def translate_blocks(blocks: Iterable[Block], translator) -> str:
    output: list[str] = []
    for block in blocks:
        if not block.translatable:
            output.append(block.text)
            continue
        if block.comments_only:
            output.append(translate_comments_only(block.text, translator))
            continue
        protected, values = protect_nontranslatable(block.text)
        output.append(restore_nontranslatable(translator(protected), values))
    return "".join(output)


def master_files(root: Path) -> list[Path]:
    return sorted((root / "content" / "pages").glob(f"*{MASTER_SUFFIX}"))


def snapshot_path(master: Path, locale: str) -> Path:
    stem = master.name[: -len(MASTER_SUFFIX)]
    return master.with_name(f"{stem}_{locale.upper()}.md")
