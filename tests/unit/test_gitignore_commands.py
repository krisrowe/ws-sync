import os
import subprocess
import pytest
import hashlib
import shutil
from pathlib import Path
from click.testing import CliRunner
from devws.cli.main import devws

# --- MACHINE SAFETY HARNESS ---

# Capture the environment's state BEFORE any pytest fixtures or patching starts.
# This is our immutable reference to the 'real' user environment.
REAL_HOME = Path.home().resolve()

def get_md5(path):
    if not path.exists(): return None
    return hashlib.md5(path.read_bytes()).hexdigest()

@pytest.fixture(scope="module", autouse=True)
def machine_safety_harness():
    """
    Protects real global configuration files from accidental modification.
    Crashes the test session if any real file is touched.
    """
    assert REAL_HOME.is_dir(), f"Safety: Identified home {REAL_HOME} is not a directory!"

    backup_dir = Path("/tmp/devws_test_safe_backup")
    if backup_dir.exists():
        shutil.rmtree(backup_dir)
    backup_dir.mkdir(parents=True)

    # 1. Identify files to protect (using the REAL home path)
    to_protect = []
    to_protect.append(("default", REAL_HOME / ".config" / "git" / "ignore"))
    
    try:
        # Explicitly use the real home to find the real .gitconfig settings
        custom_path_str = subprocess.check_output(
            ['git', 'config', '--global', '--get', 'core.excludesfile'], 
            text=True,
            env={**os.environ, "HOME": str(REAL_HOME)}
        ).strip()
        if custom_path_str:
            to_protect.append(("custom", Path(os.path.expanduser(custom_path_str))))
    except subprocess.CalledProcessError:
        pass

    # 2. Backup and Store MD5s
    initial_states = {}
    for label, path in to_protect:
        initial_states[path] = get_md5(path)
        if path.exists():
            shutil.copy2(path, backup_dir / f"{label}_backup")

    # Final pre-test verification: Ensure Path hasn't been patched yet
    assert Path.home().resolve() == REAL_HOME, "Safety: Path.home() already patched before harness!"

    yield

    # 3. Teardown: Verify Integrity
    corrupted = []
    for path, initial_md5 in initial_states.items():
        current_md5 = get_md5(path)
        if current_md5 != initial_md5:
            corrupted.append(path)

    if corrupted:
        alarm_msg = "\n" + "!" * 80 + "\n"
        alarm_msg += "CRITICAL ERROR: REAL MACHINE CONFIGURATION CORRUPTED DURING TESTS!\n"
        alarm_msg += "Affected files:\n"
        for p in corrupted:
            alarm_msg += f"  - {p}\n"
        alarm_msg += f"Backups are available at: {backup_dir}\n"
        alarm_msg += "!" * 80 + "\n"
        print(alarm_msg)
        pytest.exit("Machine config corruption detected. Aborting.", returncode=1)

# --- ISOLATION FIXTURE ---

@pytest.fixture
def home_sandbox(tmp_path, monkeypatch):
    """
    Strictly redirects HOME and XDG_CONFIG_HOME to a temporary directory.
    Demands proof of isolation for Python, Shell, and Git before proceeding.
    """
    sandbox_dir = (tmp_path / "home").resolve()
    sandbox_dir.mkdir()
    
    # 1. Verification BEFORE patching
    assert Path.home().resolve() != sandbox_dir
    
    # 2. Apply Patch
    monkeypatch.setenv("HOME", str(sandbox_dir))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(sandbox_dir / ".config"))
    
    # 3. Verification AFTER patching (Python)
    assert Path.home().resolve() == sandbox_dir
    
    # 4. Verification AFTER patching (Subprocess)
    sub_home = subprocess.check_output(['sh', '-c', 'echo $HOME'], text=True).strip()
    assert Path(sub_home).resolve() == sandbox_dir

    # 5. Verification AFTER patching (Git-Specific)
    (sandbox_dir / ".gitconfig").write_text("[user]\n  name = Sandbox User")
    git_origin = subprocess.check_output(
        ['git', 'config', '--global', '--list', '--show-origin'], 
        text=True
    )
    assert str(sandbox_dir) in git_origin, "Sandbox: Git is NOT reading from the sandbox home!"
    
    return sandbox_dir

# --- BEHAVIORAL UNIT TESTS ---

def test_gitignore_apply_create_default_path(home_sandbox):
    """
    Fresh state: Should create the default git standard file.
    """
    runner = CliRunner()
    result = runner.invoke(devws, ["gitignore", "global", "apply", "--overwrite=force"])
    
    assert result.exit_code == 0
    target = home_sandbox / ".config" / "git" / "ignore"
    assert target.exists()
    assert "venv/" in target.read_text()

def test_gitignore_apply_create_alt_path(home_sandbox):
    """
    Custom path set but file missing: Should create the custom file.
    """
    alt_path = (home_sandbox / ".my_git_ignore").resolve()
    subprocess.check_call(['git', 'config', '--global', 'core.excludesfile', str(alt_path)])
    
    runner = CliRunner()
    result = runner.invoke(devws, ["gitignore", "global", "apply", "--overwrite=force"])
    
    assert result.exit_code == 0
    assert alt_path.exists()
    assert not (home_sandbox / ".config" / "git" / "ignore").exists()

def test_gitignore_apply_matches_default_path(home_sandbox):
    """
    Idempotency: No changes if content matches.
    """
    target = home_sandbox / ".config" / "git" / "ignore"
    target.parent.mkdir(parents=True)
    
    # Load real template content from the project resources
    template_path = Path("devws/resources/global_gitignore")
    content = template_path.read_text()
    target.write_text(content)
    
    runner = CliRunner()
    result = runner.invoke(devws, ["gitignore", "global", "apply"])

def test_gitignore_apply_diff_fail_default_path(home_sandbox):
    """
    Default behavior: Fail (exit 1) if diff exists on target file.
    """
    target = home_sandbox / ".config" / "git" / "ignore"
    target.parent.mkdir(parents=True)
    target.write_text("unmanaged content")
    
    runner = CliRunner()
    result = runner.invoke(devws, ["gitignore", "global", "apply"]) # Defaults to --overwrite=fail
    
    assert result.exit_code == 1
    assert "has differences" in result.output
    assert target.read_text() == "unmanaged content"

def test_gitignore_apply_diff_force_overwrite(home_sandbox):
    """
    Force mode: Overwrite existing file without asking.
    """
    target = home_sandbox / ".config" / "git" / "ignore"
    target.parent.mkdir(parents=True)
    target.write_text("old version")
    
    runner = CliRunner()
    result = runner.invoke(devws, ["gitignore", "global", "apply", "--overwrite=force"])
    
    assert result.exit_code == 0
    assert "Updated standard gitignore" in result.output
    assert "venv/" in target.read_text()

def test_gitignore_apply_prompt_decline(home_sandbox):
    """
    Prompt mode: Decline overwrite should exit with failure (1).
    """
    target = home_sandbox / ".config" / "git" / "ignore"
    target.parent.mkdir(parents=True)
    target.write_text("pre-existing")
    
    runner = CliRunner()
    result = runner.invoke(devws, ["gitignore", "global", "apply", "--overwrite=prompt"], input="n\n")
    
    assert result.exit_code == 1
    assert "Aborted" in result.output
    assert target.read_text() == "pre-existing"

def test_gitignore_apply_effectiveness_default_path(home_sandbox, tmp_path):
    """
    Functional verification: Rules in standard location successfully affect git status.
    """
    repo_dir = tmp_path / "repo_default"
    repo_dir.mkdir()
    subprocess.check_call(['git', 'init'], cwd=repo_dir)
    (repo_dir / ".venv").mkdir()
    (repo_dir / ".venv" / "file").write_text("data")
    
    status_pre = subprocess.check_output(['git', 'status', '--porcelain'], cwd=repo_dir, text=True)
    assert ".venv/" in status_pre
    
    runner = CliRunner()
    runner.invoke(devws, ["gitignore", "global", "apply", "--overwrite=force"])
    
    status = subprocess.check_output(['git', 'status', '--porcelain'], cwd=repo_dir, text=True)
    assert status.strip() == ""
    
    ignored = subprocess.check_output(['git', 'status', '--ignored', '--porcelain'], cwd=repo_dir, text=True)
    assert "!! .venv/" in ignored

def test_gitignore_apply_effectiveness_alt_path(home_sandbox, tmp_path):
    """
    Functional verification: Rules in custom location successfully affect git status.
    """
    repo_dir = tmp_path / "repo_alt"
    repo_dir.mkdir()
    subprocess.check_call(['git', 'init'], cwd=repo_dir)
    (repo_dir / ".venv").mkdir()
    (repo_dir / ".venv" / "file").write_text("data")
    
    # Configure custom path
    alt_path = (home_sandbox / ".custom_ignore").resolve()
    subprocess.check_call(['git', 'config', '--global', 'core.excludesfile', str(alt_path)])
    
    runner = CliRunner()
    runner.invoke(devws, ["gitignore", "global", "apply", "--overwrite=force"])
    
    status = subprocess.check_output(['git', 'status', '--porcelain'], cwd=repo_dir, text=True)
    assert status.strip() == ""
    
    ignored = subprocess.check_output(['git', 'status', '--ignored', '--porcelain'], cwd=repo_dir, text=True)
    assert "!! .venv/" in ignored