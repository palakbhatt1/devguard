import os
import re
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class ParsedTracebackFrame:
    file_path: str
    line_number: int
    func_name: str
    code_line: str


@dataclass
class ParsedTraceback:
    exception_type: str
    exception_message: str
    frames: List[ParsedTracebackFrame] = field(default_factory=list)
    failing_file: Optional[str] = None
    failing_line: Optional[int] = None
    surrounding_code: Optional[str] = None


def read_surrounding_code(file_path: str, line_number: int, context_lines: int = 5) -> Optional[str]:
    """Read lines around the target line number from a local source file if present."""
    if not file_path or not os.path.exists(file_path):
        return None

    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()

        start_idx = max(0, line_number - 1 - context_lines)
        end_idx = min(len(lines), line_number + context_lines)

        output_lines = []
        for idx in range(start_idx, end_idx):
            curr_line_no = idx + 1
            marker = "->" if curr_line_no == line_number else "  "
            output_lines.append(f"{marker} {curr_line_no:4d} | {lines[idx].rstrip()}")

        return "\n".join(output_lines)
    except Exception:
        return None


def parse_python_traceback(
    traceback_text: str,
    provided_source_code: Optional[str] = None,
) -> ParsedTraceback:
    """Parse a Python traceback string to extract exception details, frames, and nearby source code."""
    lines = [l for l in traceback_text.strip().splitlines() if l.strip()]
    if not lines:
        return ParsedTraceback(
            exception_type="UnknownError",
            exception_message="Empty traceback provided.",
        )

    # 1. Extract Exception Type and Message from final line or scanning backwards
    exception_type = "RuntimeError"
    exception_message = lines[-1].strip()
    for line in reversed(lines):
        line_str = line.strip()
        exc_match = re.match(r"^([a-zA-Z_][a-zA-Z0-9_\.]*)\s*:\s*(.*)$", line_str)
        if exc_match and not line_str.startswith("File ") and not line_str.startswith("Traceback"):
            raw_type = exc_match.group(1)
            exception_type = raw_type.split(".")[-1]
            exception_message = exc_match.group(2)
            break
        elif re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*Error$", line_str) or re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*Exception$", line_str):
            exception_type = line_str.split(".")[-1]
            exception_message = ""
            break

    # 2. Extract Frames matching `File "path", line X, in func`
    frame_pattern = re.compile(
        r'File\s+["\'](?P<file>[^"\']+)["\'],\s+line\s+(?P<line>\d+)(?:,\s+in\s+(?P<func>.+))?'
    )

    frames: List[ParsedTracebackFrame] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        match = frame_pattern.search(line)
        if match:
            file_path = match.group("file")
            line_no = int(match.group("line"))
            func_name = match.group("func") or "<module>"

            # The following line in standard Python traceback is usually the code snippet
            code_line = ""
            if i + 1 < len(lines) and not frame_pattern.search(lines[i + 1]) and not re.match(r"^[a-zA-Z_][a-zA-Z0-9_\.]*\s*:\s*", lines[i + 1]):
                code_line = lines[i + 1].strip()

            frames.append(
                ParsedTracebackFrame(
                    file_path=file_path,
                    line_number=line_no,
                    func_name=func_name,
                    code_line=code_line,
                )
            )
        i += 1

    failing_file = frames[-1].file_path if frames else None
    failing_line = frames[-1].line_number if frames else None

    # 3. Read surrounding source code
    surrounding = provided_source_code
    if not surrounding and failing_file and failing_line:
        surrounding = read_surrounding_code(failing_file, failing_line)

    return ParsedTraceback(
        exception_type=exception_type,
        exception_message=exception_message,
        frames=frames,
        failing_file=failing_file,
        failing_line=failing_line,
        surrounding_code=surrounding or "No source code snippet available.",
    )
