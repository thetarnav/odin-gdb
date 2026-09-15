#!/usr/bin/env python3
"""
Test script for GDB Odin pretty-printers.

This script:
1. Builds the Odin program using build.sh
2. Starts a single GDB batch session
3. Parses main.odin for expected test cases
4. Validates pretty-printer output with wildcard comparison
"""

import re
import subprocess
import sys
import shutil
from typing import List, Optional

class ANSI:
    RED       = '\033[91m'
    GREEN     = '\033[92m'
    YELLOW    = '\033[93m'
    BLUE      = '\033[94m'
    MAGENTA   = '\033[95m'
    CYAN      = '\033[96m'
    WHITE     = '\033[97m'
    BOLD      = '\033[1m'
    UNDERLINE = '\033[4m'
    END       = '\033[0m'

def colored   (text: str, color: str) -> str: return f"{color}{text}{ANSI.END}"

def success   (text: str) -> str: return colored(text, ANSI.GREEN)
def error     (text: str) -> str: return colored(text, ANSI.RED)
def warning   (text: str) -> str: return colored(text, ANSI.YELLOW)
def info      (text: str) -> str: return colored(text, ANSI.BLUE)
def highlight (text: str) -> str: return colored(text, ANSI.BOLD)


class TestCase:
    def __init__(self, command: str, expected: str):
        self.command  = command
        self.expected = expected

def print_line(msg: str, color: str = ANSI.CYAN) -> None:
    width = shutil.get_terminal_size().columns
    print(colored(msg.center(width, '-'), color))

def run_build_script() -> bool:
    print(info("Building Odin program..."))
    print_line("build.sh")
    try:
        # Run without capturing output so it shows in real-time
        subprocess.run(['bash', 'build.sh'],
                       text=True,
                       check=True)
        print_line("success", color=ANSI.GREEN)
        return True
    except subprocess.CalledProcessError as e:
        print_line(f"failed: {e.returncode}", color=ANSI.RED)
        return False


def parse_test_cases(filename: str) -> List[TestCase]:
    print(info(f"Parsing test cases from {filename}..."))

    test_cases: List[TestCase] = []

    with open(filename, 'r') as f:
        content = f.read()

    # Pattern to match:
    # // (gdb) command
    # // expected_output

    test_cases: List[TestCase] = []
    lines = content.split('\n')
    line_i = 0

    while line_i < len(lines):
        line = lines[line_i].strip()

        # Look for "// (gdb) command" lines
        if line.startswith('//'):
            gdb_pos = line.find('(gdb)')
            if gdb_pos != -1:
                command = line[gdb_pos + 5:].strip()

                expected_lines = []
                line_i += 1

                while line_i < len(lines):
                    next_line = lines[line_i].strip()

                    # not a comment
                    if not next_line.startswith('//'):
                        break

                    # next command
                    if '(gdb)' in next_line:
                        line_i -= 1  # step back to reprocess this line
                        break

                    expected_lines.append(next_line[2:].strip())
                    line_i += 1

                if expected_lines:
                    expected = '\n'.join(expected_lines)
                    test_cases.append(TestCase(command, expected))

        line_i += 1

    print(success(f"Found {len(test_cases)} test cases"))
    return test_cases

def compare_outputs(expected: str, actual: str) -> bool:

    ei, ai = 0, 0

    while ei < len(expected) and ai < len(actual):
        # expect any int
        if expected[ei:ei+5] == "%INT%":
            ei += 5
            while ai < len(actual) and actual[ai].isdigit(): ai += 1
        # expect any ptr (0x123123d123)
        elif expected[ei:ei+5] == "%PTR%":
            ei += 5
            if actual[ai]   != '0': return False
            if actual[ai+1] != 'x': return False
            ai += 2
            while ai < len(actual) and (actual[ai].isdigit() or actual[ai] in 'abcdef'): ai += 1
        # compare chars
        elif expected[ei] != actual[ai]:
            return False
        ei += 1
        ai += 1

    if ei < len(expected) or ai < len(actual):
        return False

    return True

def case_marker(i: int) -> str:
    return f"__ODIN_CASE_{i}__"

def run_gdb(test_cases: List[TestCase]) -> str:

    cmd = ["gdb", "--batch", "-nx",
           "-ex", "set confirm off",
           "-ex", "set pagination off",
           "-ex", "source odin.py",
           "-ex", "file ./main.bin",
           "-ex", "break breakpoint",
           "-ex", "run",
           "-ex", "up"]

    for i, test_case in enumerate(test_cases):
        cmd.append("-ex")
        cmd.append(f"python print('{case_marker(i)}')")
        cmd.append("-ex")
        cmd.append(test_case.command)

    print(info("Running GDB session:\n"), " ".join(cmd))
    print_line("gdb")

    timeout = 120

    try:
        result = subprocess.run(cmd,
                                capture_output=True,
                                text=True,
                                timeout=timeout)

        print(result.stdout, end='')
        if result.stderr:
            print(warning("GDB stderr:"))
            print(result.stderr, end='')

        if result.returncode != 0:
            print(error(f"GDB exited with code {result.returncode}"))

        return result.stdout

    except subprocess.TimeoutExpired:
        print(error(f"\nGDB session timed out after {timeout} seconds"))
        print(warning("This might be due to DWARF symbol indexing taking too long."))
        return ""
    except FileNotFoundError:
        print(error("Error: GDB not found. Please install GDB."))
        print(info("On Ubuntu: sudo apt-get install gdb"))
        return ""


def parse_gdb_output(output: str, test_cases: List[TestCase]) -> dict[str, str | None]:

    results: dict[str, str | None] = {}

    for i, test_case in enumerate(test_cases):
        start_marker = case_marker(i) + "\n"
        end_marker = case_marker(i + 1) + "\n" if i + 1 < len(test_cases) else None

        start_idx = output.find(start_marker)
        if start_idx == -1:
            results[test_case.command] = None
            continue
        start_idx += len(start_marker)

        if end_marker is not None:
            end_idx = output.find(end_marker, start_idx)
            chunk = output[start_idx:end_idx].strip() if end_idx != -1 else output[start_idx:].strip()
        else:
            chunk = output[start_idx:].strip()

        # Strip the `$N = ` prefix GDB prepends to `print` output.
        # (`odin-children` lines have no prefix; the regex only strips
        # a leading `$<digits> = ` on the first line.)
        chunk = re.sub(r'^\$\d+ = ', '', chunk, count=1)

        results[test_case.command] = chunk

    return results


def run_test_case(test_case: TestCase, actual_output: Optional[str]) -> bool:
    """Validate a single test case result."""
    if actual_output is None:
        print(error(f"  FAIL: {test_case.command} - No output captured"))
        return False

    if compare_outputs(test_case.expected, actual_output):
        print(success(f"  PASS: {test_case.command}"))
        return True
    else:
        print(error(f"  FAIL: {test_case.command}"))
        print(f"    {success('Expected:')} {highlight(test_case.expected)}")
        print(f"    {error('Actual:')}   {highlight(actual_output)}")
        return False


def check_dependencies() -> bool:
    required_checks = [
        (["odin", "version"],   "Odin compiler not found. Please install Odin."),
        (["gdb", "--version"], "GDB debugger not found. Please install GDB.\nOn Ubuntu: sudo apt-get install gdb"),
        (["bash", "--version"], "Bash shell not found.")
    ]

    for cmd, error_msg in required_checks:
        try:
            subprocess.run(cmd,
                           capture_output=True,
                           check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            print(error(f"Error: {error_msg}"))
            return False

    return True


def run_tests() -> bool:
    print(highlight("Starting GDB Odin tests..."))

    # Check dependencies first
    if not check_dependencies():
        print(error("Dependency check failed, aborting tests"))
        return False

    if not run_build_script():
        print(error("Build failed, aborting tests"))
        return False

    test_cases = parse_test_cases("main.odin")
    if not test_cases:
        print(warning("No test cases found"))
        return False

    gdb_output = run_gdb(test_cases)

    print_line("end")

    results = parse_gdb_output(gdb_output, test_cases)

    failed = 0

    for test_case in test_cases:
        actual_output = results.get(test_case.command)
        if not run_test_case(test_case, actual_output):
            failed += 1

    if failed == 0:
        print(success("All tests passed! 🎉"))
        return True
    else:
        print(error(f"  Failed: {len(test_cases)-failed}/{len(test_cases)}"))
        return False


if __name__ == "__main__":
    test_success = run_tests()
    sys.exit(0 if test_success else 1)
