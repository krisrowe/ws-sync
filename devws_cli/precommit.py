import click
import os
import re
import subprocess
import yaml # Added for loading patterns from YAML
from pathlib import Path

from devws_cli.utils import _run_command, _load_global_config

# Path to the generic patterns file
UNSAFE_PATTERNS_FILE = Path(__file__).parent / "unsafe-patterns.yaml"

def load_generic_patterns():
    """Loads generic patterns from the unsafe-patterns.yaml file."""
    try:
        with open(UNSAFE_PATTERNS_FILE, 'r') as f:
            content = yaml.safe_load(f)
            return content.get('generic_patterns', [])
    except Exception as e:
        click.echo(f"❌ Error loading generic patterns from {UNSAFE_PATTERNS_FILE}: {e}", err=True)
        return []

def gather_sensitive_strings(config, extend_built_in_patterns, generic_patterns_from_file):
    """
    Gathers all sensitive strings to check for, based on the environment and config.
    """
    sensitive_patterns_dict = {}

    # Conditionally add generic patterns
    if extend_built_in_patterns:
        for i, pattern in enumerate(generic_patterns_from_file):
            sensitive_patterns_dict[f"Generic Pattern #{i+1}"] = pattern

    # 1. Dynamically discovered values
    try:
        username = Path.home().name
        if username:
            sensitive_patterns_dict[f"Username ('{username}')"] = re.escape(username)
    except Exception:
        pass

    try:
        git_name = _run_command(['git', 'config', 'user.name'], capture_output=True).stdout.strip()
        if git_name:
            sensitive_patterns_dict[f"Git Full Name ('{git_name}')"] = re.escape(git_name)
            for part in git_name.split():
                if len(part) > 2: # Only check for reasonably long parts (avoid 'A', 'I', 'Me')
                    sensitive_patterns_dict[f"Git Name Part ('{part}')"] = re.escape(part)
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass # Git not installed or user.name not set

    try:
        git_email = _run_command(['git', 'config', 'user.email'], capture_output=True).stdout.strip()
        if git_email:
            sensitive_patterns_dict[f"Git Email ('{git_email}')"] = re.escape(git_email)
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    # 2. Values from .env file (project specific)
    try:
        env_path = Path('.env')
        if env_path.is_file():
            with open(env_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        value = value.strip().strip('"').strip("'")
                        if value and len(value) > 8: # Only check for reasonably long values
                            sensitive_patterns_dict[f"Value from .env (key: {key})"] = re.escape(value)
    except Exception:
        pass # Ignore errors parsing .env

    # 3. Custom user-defined patterns from config
    precommit_config = config.get('precommit', {}) # Renamed from safecheck_config
    user_patterns = precommit_config.get('unsafe_patterns', []) # Renamed from patterns
    for i, pattern in enumerate(user_patterns):
        sensitive_patterns_dict[f"Custom Pattern #{i+1}"] = pattern

    return sensitive_patterns_dict

def get_files_to_scan():
    """
    Gets the list of all files to be scanned (tracked + untracked non-ignored).
    """
    files_to_scan = set()

    # 1. Get all tracked files
    try:
        tracked_files_raw = _run_command(['git', 'ls-files', '-z'], capture_output=True).stdout
        files_to_scan.update(tracked_files_raw.split('\0'))
    except (subprocess.CalledProcessError, FileNotFoundError):
        click.echo("⚠️  Could not run 'git ls-files'. Is git installed and are you in a git repository?", err=True)
        return []

    # 2. Get all untracked files (that are not ignored)
    try:
        untracked_files_raw = _run_command(['git', 'ls-files', '--others', '--exclude-standard', '-z'], capture_output=True).stdout
        files_to_scan.update(untracked_files_raw.split('\0'))
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass # This can fail if git is not installed, but we already warned above.
    
    files_to_scan.discard('') # Remove any empty strings
    
    return sorted(list(files_to_scan))

def run_precommit():
    """
    The main engine for the precommit command.
    """
    config, _ = _load_global_config(silent=True)
    
    click.echo("Gathering sensitive data patterns...")
    
    # Load generic patterns from the external file
    generic_patterns_from_file = load_generic_patterns()
    
    # Determine if built-in patterns should be extended or replaced by user config
    precommit_config = config.get('precommit', {}) # Renamed from safecheck_config
    extend_built_in_patterns = precommit_config.get('extend_built_in_patterns', True) # Default to true
    
    sensitive_patterns_from_dynamic_and_user = gather_sensitive_strings(
        config, 
        extend_built_in_patterns, 
        generic_patterns_from_file
    )
    
    all_patterns = sensitive_patterns_from_dynamic_and_user # All patterns now come from gather_sensitive_strings

    click.echo("Identifying files to scan...")
    files_to_scan = get_files_to_scan()
    if not files_to_scan:
        click.echo("No files found to scan.")
        return

    click.echo(f"Scanning {len(files_to_scan)} files...")
    
    findings = []
    
    # Track which file is the unsafe-patterns.yaml itself to filter out self-matches
    # Only filter if the unsafe-patterns.yaml file is actually in the current repository
    unsafe_patterns_file_path_str = None
    try:
        unsafe_patterns_file_path_str = str(UNSAFE_PATTERNS_FILE.relative_to(Path.cwd()))
    except ValueError:
        # The unsafe-patterns.yaml file is not in the current working directory tree
        # This is fine - it means we don't need to filter it out since it won't be scanned
        pass
    
    for file_path_str in files_to_scan:
        file_path = Path(file_path_str)
        if not file_path.is_file():
            continue

        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                for line_num, line in enumerate(f, 1):
                    stripped_line = line.strip()
                    if stripped_line.startswith('#'): # Skip comment lines
                        continue
                        
                    for name, pattern in all_patterns.items():
                        try:
                            # Filter out false positives where generic pattern definitions match themselves in their own file
                            # Only do this check if unsafe_patterns_file_path_str is set (i.e., the file is in the current repo)
                            if (unsafe_patterns_file_path_str is not None and 
                                file_path_str == unsafe_patterns_file_path_str and 
                                name.startswith("Generic Pattern")):
                                # This is a heuristic: check if the pattern string is directly in the line.
                                # Given our new encoded patterns, a simple 'pattern in line' check should suffice
                                if pattern in line: 
                                    continue # Skip this known false positive
                                    
                            if re.search(pattern, line):
                                findings.append({
                                    "file": file_path_str,
                                    "line_num": line_num,
                                    "line_content": line.strip(),
                                    "match_type": name,
                                    "pattern": pattern # Include pattern for debugging if needed
                                })
                        except re.error as e:
                            click.echo(f"⚠️  Skipping invalid regex pattern: {pattern} ({e})", err=True)
                            all_patterns.pop(name) # Remove bad pattern to avoid re-checking
                            break

        except Exception:
            pass # Ignore files we can't read

    # --- Reporting ---
    if not findings:
        click.echo("\n✅ No secrets found.")
        return

    click.echo(f"\n🚨 FOUND {len(findings)} POTENTIAL SECRETS! 🚨")
    for finding in findings:
        click.echo("\n" + "-"*40)
        click.echo(f"[!] SECRET FOUND: {finding['match_type']}")
        click.echo(f"  - File:    {finding['file']}")
        click.echo(f"  - Line:    {finding['line_num']}")
        click.echo(f"  - Content: {finding['line_content']}")
        # if debug:
        #     click.echo(f"  - Pattern: {finding['pattern']}") # Uncomment for debugging patterns
    click.echo("\n" + "="*40)
    click.echo("Please review the findings above and remove any sensitive data before committing.")
