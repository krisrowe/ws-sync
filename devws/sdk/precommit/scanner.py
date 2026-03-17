"""SDK for precommit scanning - regex patterns + entropy detection."""
import os
import re
import subprocess
import yaml
from pathlib import Path
from typing import Dict, List, Any, Optional, Set

from devws.sdk.precommit.entropy import check_secret
from devws.sdk.utils import _run_command, _load_global_config

# Path to the regex patterns file
UNSAFE_PATTERNS_FILE = Path(__file__).parent.parent.parent / "unsafe-patterns.yaml"

# Token extraction pattern: word chars + dash + dot + slash + equals + plus
TOKEN_PATTERN = re.compile(r'[\w\-\.\/\=\+]{8,}')


def load_regex_patterns() -> List[str]:
    """Load regex patterns from the unsafe-patterns.yaml file."""
    try:
        with open(UNSAFE_PATTERNS_FILE, 'r') as f:
            content = yaml.safe_load(f)
            return content.get('generic_patterns', [])
    except Exception:
        return []


def gather_dynamic_patterns(config: dict) -> Dict[str, str]:
    """
    Gather sensitive patterns from environment and config.
    Returns dict of {description: regex_pattern}
    """
    patterns = {}

    # Username
    try:
        username = Path.home().name
        if username:
            patterns[f"Username ('{username}')"] = re.escape(username)
    except Exception:
        pass

    # Git user name
    try:
        git_name = _run_command(['git', 'config', 'user.name'], capture_output=True).stdout.strip()
        if git_name:
            patterns[f"Git Full Name ('{git_name}')"] = re.escape(git_name)
            for part in git_name.split():
                if len(part) > 2:
                    patterns[f"Git Name Part ('{part}')"] = re.escape(part)
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    # Git email
    try:
        git_email = _run_command(['git', 'config', 'user.email'], capture_output=True).stdout.strip()
        if git_email:
            patterns[f"Git Email ('{git_email}')"] = re.escape(git_email)
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    # Values from .env file
    try:
        env_path = Path('.env')
        if env_path.is_file():
            with open(env_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        value = value.strip().strip('"').strip("'")
                        if value and len(value) > 8:
                            patterns[f"Value from .env (key: {key})"] = re.escape(value)
    except Exception:
        pass

    # Custom user patterns from config
    precommit_config = config.get('precommit', {})
    user_patterns = precommit_config.get('unsafe_patterns', [])
    for i, pattern in enumerate(user_patterns):
        patterns[f"Custom Pattern #{i+1}"] = pattern

    return patterns


def get_files_to_scan(include_untracked: bool = False) -> List[str]:
    """Get list of files to scan.

    By default only tracked files are scanned — that's what a precommit
    check cares about.  Untracked files are not staged and won't be in
    the commit; scanning them is purely cautionary and must be opted into
    with ``include_untracked=True``.
    """
    files = set()

    # Tracked files
    try:
        tracked = _run_command(['git', 'ls-files', '-z'], capture_output=True).stdout
        files.update(tracked.strip('\0').split('\0'))
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []

    # Untracked files (not ignored) — opt-in only
    if include_untracked:
        try:
            untracked = _run_command(['git', 'ls-files', '--others', '--exclude-standard', '-z'], capture_output=True).stdout
            files.update(untracked.strip('\0').split('\0'))
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass

    files.discard('')
    return sorted(files)


def is_known_false_positive(finding: dict) -> bool:
    """Check if a finding is a known false positive."""
    file_lower = finding['file'].lower()
    match_type = finding['match_type']
    line_content_lower = finding.get('line_content', '').lower()

    # Author name in LICENSE file on copyright line
    if ('license' in file_lower and
        match_type.startswith(('Git Full Name', 'Git Name Part')) and
        'copyright' in line_content_lower):
        return True

    return False


def extract_tokens(line: str) -> List[str]:
    """Extract potential secret tokens from a line."""
    return TOKEN_PATTERN.findall(line)


def run_scan(
    verbose: bool = False,
    entropy_enabled: bool = True,
    entropy_threshold: float = 4.2,
    entropy_min_len: int = 20,
    allow_path_exception: bool = True,
    include_untracked: bool = False
) -> Dict[str, Any]:
    """
    Run precommit scan combining regex patterns and entropy detection.

    Returns dict with:
      - findings: list of findings
      - ignored: list of known false positives
      - summary: counts and stats
      - files_scanned: number of files checked
    """
    config, _ = _load_global_config(silent=True)

    # Load patterns
    regex_patterns = load_regex_patterns()
    precommit_config = config.get('precommit', {})
    extend_built_in = precommit_config.get('extend_built_in_patterns', True)

    all_patterns = {}
    if extend_built_in:
        for i, pattern in enumerate(regex_patterns):
            all_patterns[f"Generic Pattern #{i+1}"] = pattern

    dynamic_patterns = gather_dynamic_patterns(config)
    all_patterns.update(dynamic_patterns)

    # Get files
    files = get_files_to_scan(include_untracked=include_untracked)
    if not files:
        return {
            "findings": [],
            "ignored": [],
            "summary": {"total": 0, "regex_matches": 0, "entropy_matches": 0},
            "files_scanned": 0
        }

    findings = []
    regex_matched_tokens: Set[str] = set()  # Track what regex already caught

    # Determine unsafe-patterns.yaml path for self-match filtering
    unsafe_patterns_rel = None
    try:
        unsafe_patterns_rel = str(UNSAFE_PATTERNS_FILE.relative_to(Path.cwd()))
    except ValueError:
        pass

    for file_path in files:
        path = Path(file_path)
        if not path.is_file():
            continue

        try:
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                for line_num, line in enumerate(f, 1):
                    stripped = line.strip()
                    if not stripped or stripped.startswith('#'):
                        continue

                    # === REGEX PASS ===
                    for name, pattern in all_patterns.items():
                        try:
                            # Skip self-matches in unsafe-patterns.yaml
                            if (unsafe_patterns_rel and
                                file_path == unsafe_patterns_rel and
                                name.startswith("Generic Pattern") and
                                pattern in line):
                                continue

                            match = re.search(pattern, line)
                            if match:
                                matched_text = match.group(0)
                                regex_matched_tokens.add(matched_text)
                                findings.append({
                                    "file": file_path,
                                    "line_num": line_num,
                                    "line_content": stripped,
                                    "match_type": name,
                                    "matched_text": matched_text,
                                    "detection": "regex"
                                })
                        except re.error:
                            pass

                    # === ENTROPY PASS ===
                    if entropy_enabled:
                        tokens = extract_tokens(line)
                        for token in tokens:
                            # Skip if regex already caught this exact token
                            if token in regex_matched_tokens:
                                continue

                            result = check_secret(
                                token,
                                min_len=entropy_min_len,
                                entropy_threshold=entropy_threshold,
                                allow_path_exception=allow_path_exception
                            )

                            if result["flagged"]:
                                findings.append({
                                    "file": file_path,
                                    "line_num": line_num,
                                    "line_content": stripped,
                                    "match_type": "High Entropy String",
                                    "matched_text": token,
                                    "detection": "entropy",
                                    "entropy": result["entropy"]
                                })
        except Exception:
            pass

    # Separate real findings from false positives
    real_findings = []
    ignored_findings = []

    for finding in findings:
        if is_known_false_positive(finding):
            ignored_findings.append(finding)
        else:
            real_findings.append(finding)

    # Summary
    regex_count = sum(1 for f in real_findings if f.get("detection") == "regex")
    entropy_count = sum(1 for f in real_findings if f.get("detection") == "entropy")

    return {
        "findings": real_findings,
        "ignored": ignored_findings,
        "summary": {
            "total": len(real_findings),
            "regex_matches": regex_count,
            "entropy_matches": entropy_count
        },
        "files_scanned": len(files)
    }
