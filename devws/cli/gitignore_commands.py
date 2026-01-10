import click
import os
import sys
import subprocess
import difflib
from pathlib import Path

@click.group()
def gitignore():
    """Manage gitignore configurations."""
    pass

@gitignore.group('global')
def global_group():
    """Manage global gitignore."""
    pass

@global_group.command('status')
@click.pass_context
def status(ctx):
    """Show current global gitignore status and configuration."""
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    
    # 1. Load Template
    # Move up one level from cli/ to devws/
    template_path = Path(__file__).parent.parent / 'resources' / 'global_gitignore'
    if not template_path.exists():
         console.print(f"[bold red]Error:[/bold red] Template not found at {template_path}")
         sys.exit(1)
    template_content = template_path.read_text()

    # 2. Location Discovery
    try:
        current_config = subprocess.check_output(['git', 'config', '--global', '--get', 'core.excludesfile'], text=True).strip()
    except subprocess.CalledProcessError:
        current_config = None

    if current_config:
        target_path = Path(os.path.expanduser(current_config))
        source = "Git Config (core.excludesfile)"
    else:
        # Official Git standard fallback
        xdg_config = os.environ.get('XDG_CONFIG_HOME')
        if xdg_config:
            target_path = Path(xdg_config) / "git" / "ignore"
        else:
            target_path = Path.home() / ".config" / "git" / "ignore"
        source = "Git Standard Default"

    # 3. Status Display
    table = Table(show_header=False, box=None)
    table.add_row("[bold blue]Authoritative Path:[/bold blue]", str(target_path))
    table.add_row("[bold blue]Source:[/bold blue]", source)
    
    status_text = "[bold red]Missing[/bold red]"
    if target_path.exists():
        status_text = "[bold green]Exists[/bold green]"
    table.add_row("[bold blue]Status:[/bold blue]", status_text)
    
    console.print(Panel(table, title="[bold] Global Gitignore Configuration [/bold]", border_style="blue", expand=False))

    if not target_path.exists():
        console.print("\n[yellow]File is missing. Run 'apply' to create it.[/yellow]")
        return

    current_content = target_path.read_text()
    
    if current_content.strip() == template_content.strip():
        console.print("\n[bold green]✅  Content matches the standard template.[/bold green]")
    else:
        console.print("\n[bold yellow]⚠️  Content differs from standard template:[/bold yellow]")
        
        diff = difflib.unified_diff(
            current_content.splitlines(),
            template_content.splitlines(),
            fromfile="Current File",
            tofile="Standard Template",
            lineterm=""
        )
        
        for line in diff:
            if line.startswith('---') or line.startswith('+++'):
                console.print(line, style="bold")
            elif line.startswith('@@'):
                console.print(line, style="cyan")
            elif line.startswith('+'):
                console.print(line, style="green")
            elif line.startswith('-'):
                console.print(line, style="red")
            else:
                console.print(line)

@global_group.command('show')
@click.pass_context
def show(ctx):
    """Alias for status."""
    ctx.invoke(status)

@global_group.command('apply')
@click.option('--overwrite', type=click.Choice(['force', 'prompt', 'fail']), default='fail',
              help="Overwrite policy for existing files with differences.")
def apply(overwrite):
    """Apply standard global gitignore configuration."""
    
    # 1. Load Template
    template_path = Path(__file__).parent.parent / 'resources' / 'global_gitignore'
    if not template_path.exists():
         click.echo(f"Error: Template not found at {template_path}", err=True)
         sys.exit(1)
    template_content = template_path.read_text()

    # 2. Location Discovery
    try:
        current_config = subprocess.check_output(['git', 'config', '--global', '--get', 'core.excludesfile'], text=True).strip()
    except subprocess.CalledProcessError:
        current_config = None

    if current_config:
        target_path = Path(os.path.expanduser(current_config))
    else:
        # Official Git standard fallback
        xdg_config = os.environ.get('XDG_CONFIG_HOME')
        if xdg_config:
            target_path = Path(xdg_config) / "git" / "ignore"
        else:
            target_path = Path.home() / ".config" / "git" / "ignore"

    # 3. Behavioral Routine
    if not target_path.exists():
        # Create missing
        try:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(template_content)
            click.echo(f"Created standard gitignore at {target_path}")
            sys.exit(0)
        except Exception as e:
            click.echo(f"Error creating file: {e}", err=True)
            sys.exit(1)

    # File exists, check content
    current_content = target_path.read_text()
    if current_content.strip() == template_content.strip():
        click.echo(f"Global gitignore at {target_path} is already up to date.")
        sys.exit(0)

    # Content differs, apply policy
    diff = list(difflib.unified_diff(
        current_content.splitlines(),
        template_content.splitlines(),
        fromfile=str(target_path),
        tofile="standard_template",
        lineterm=""
    ))

    if overwrite == 'fail':
        click.echo(f"Error: Global gitignore at {target_path} has differences.", err=True)
        for line in diff:
            if line.startswith('+') and not line.startswith('+++'): click.secho(line, fg='green', err=True)
            elif line.startswith('-') and not line.startswith('---'): click.secho(line, fg='red', err=True)
            else: click.echo(line, err=True)
        sys.exit(1)

    if overwrite == 'prompt':
        click.echo(f"Differences found in {target_path}:")
        for line in diff:
            if line.startswith('+') and not line.startswith('+++'): click.secho(line, fg='green')
            elif line.startswith('-') and not line.startswith('---'): click.secho(line, fg='red')
            else: click.echo(line)
        if not click.confirm("\nOverwrite with standard template?"):
            click.echo("Aborted.")
            sys.exit(1)

    # Force or Prompt-Accepted
    try:
        target_path.write_text(template_content)
        click.echo(f"Updated standard gitignore at {target_path}")
    except Exception as e:
        click.echo(f"Error updating file: {e}", err=True)
        sys.exit(1)