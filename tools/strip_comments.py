import os
import io
import sys
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PYTHON_DIRS = [
    ROOT,  # project root
    ROOT / 'cogs',
]

EXCLUDE_FILES = {
    'tools/strip_comments.py',
}

# Directories to exclude anywhere in the path
EXCLUDE_DIR_NAMES = {
    '__pycache__',
    '.git',
    '.hg',
    '.svn',
    '.local',
    'site-packages',
    'dist-packages',
    '.venv',
    'venv',
    'env',
    'ENV',
    'build',
    'dist',
    '__pypackages__',
    '.mypy_cache',
    '.pytest_cache',
}

# Simple patterns:
# - Remove full-line comments starting with # (ignores shebang & encoding lines)
# - Remove inline comments starting with # that are not inside strings
# - Collapse multiple blank lines to a single blank line
# NOTE: This is conservative to avoid breaking code. It won't touch docstrings.

COMMENT_RE = re.compile(r"(^\s*#(?!!| -*-).*$)")
INLINE_COMMENT_RE = re.compile(r"(?P<code>[^'#]*?(?:'(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\")?)(?P<comment>#.*)$")


def process_text(text: str) -> str:
    lines = text.splitlines()
    out_lines = []
    blank_count = 0

    for line in lines:
        # Skip full-line comments (but keep shebang/encoding markers)
        if COMMENT_RE.match(line):
            continue

        # Remove trailing comments when safe (not inside strings)
        m = INLINE_COMMENT_RE.match(line)
        if m and m.group('code').strip():
            line = m.group('code').rstrip()

        # Track and collapse blank lines
        if line.strip() == '':
            blank_count += 1
            if blank_count > 1:
                continue
        else:
            blank_count = 0

        out_lines.append(line.rstrip())

    # Final join with newline at end of file
    result = '\n'.join(out_lines).rstrip() + '\n'
    return result


def process_file(path: Path):
    rel = path.relative_to(ROOT).as_posix()
    if rel in EXCLUDE_FILES:
        return
    try:
        original = path.read_text(encoding='utf-8')
    except Exception:
        return

    updated = process_text(original)
    if updated != original:
        path.write_text(updated, encoding='utf-8')
        print(f"Stripped: {rel}")


def main():
    py_files = []
    for base in PYTHON_DIRS:
        if not base.exists():
            continue
        for p in base.rglob('*.py'):
            # Skip excluded directories (including hidden dirs)
            if any((part in EXCLUDE_DIR_NAMES) or part.startswith('.') for part in p.parts):
                continue
            py_files.append(p)

    for p in py_files:
        process_file(p)

    print(f"Processed {len(py_files)} Python files.")


if __name__ == '__main__':
    main()
