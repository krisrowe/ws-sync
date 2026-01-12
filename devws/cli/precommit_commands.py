"""Precommit CLI - thin wrapper around SDK with rich formatting."""
import json
import click
from devws.cli.precommit import run_precommit


@click.group(invoke_without_command=True)
@click.option('--verbose', '-v', is_flag=True, help='Show ignored false positives.')
@click.pass_context
def precommit(ctx, verbose):
    """
    Scan for sensitive information in the repository.

    Run without subcommand to scan. Use 'patterns' for testing.
    """
    ctx.ensure_object(dict)
    ctx.obj['verbose'] = verbose
    if ctx.invoked_subcommand is None:
        run_precommit(verbose=verbose)


@precommit.group()
def patterns():
    """Test pattern detection (regex + entropy)."""
    pass


@patterns.command('list')
@click.option('--format', 'fmt', type=click.Choice(['table', 'json']), default='table')
def patterns_list(fmt):
    """List all test patterns."""
    from devws.sdk.precommit import list_test_patterns

    data = list_test_patterns()

    if fmt == 'json':
        click.echo(json.dumps(data, indent=2))
        return

    # Rich table output
    from rich.console import Console
    from rich.table import Table

    console = Console()
    table = Table(title="Test Patterns", show_header=True, header_style="bold")
    table.add_column("ID", style="cyan")
    table.add_column("Type")
    table.add_column("Expect", justify="center")
    table.add_column("Description")

    for p in data["patterns"]:
        expect_style = "green" if p.get("expect") == "pass" else "red"
        table.add_row(
            p.get("id", ""),
            p.get("type", ""),
            f"[{expect_style}]{p.get('expect', 'pass')}[/]",
            p.get("description", "")
        )

    console.print(table)


@patterns.command('test')
@click.option('--format', 'fmt', type=click.Choice(['table', 'json']), default='table')
@click.option('--test', '-t', 'test_values', multiple=True, help='Test additional string values')
def patterns_test(fmt, test_values):
    """Run patterns through full detection (regex + entropy)."""
    from devws.sdk.precommit import run_full_pattern_test, check_secret
    from devws.sdk.precommit.scanner import load_regex_patterns
    import re

    data = run_full_pattern_test()
    results = data["results"]

    # Add user-provided test values
    if test_values:
        regex_patterns = load_regex_patterns()
        for val in test_values:
            regex_match = any(re.search(pat, val) for pat in regex_patterns if pat)
            entropy_result = check_secret(val)
            results.append({
                "id": val[:24] if len(val) <= 24 else val[:21] + "...",
                "expect": None,  # Unknown - user provided
                "regex_match": regex_match,
                "entropy_flag": entropy_result["flagged"],
                "entropy_val": entropy_result["entropy"],
                "exception": entropy_result.get("exception"),
                "final_flag": regex_match or entropy_result["flagged"],
                "correct": None,  # Can't know - user must verify
                "user_provided": True
            })

    if fmt == 'json':
        click.echo(json.dumps(data, indent=2))
        return

    from rich.console import Console
    from rich.table import Table

    console = Console()

    # Group results
    user_provided = [r for r in results if r.get("user_provided")]
    flagged_secrets = [r for r in results if not r.get("user_provided") and r["expect"] == "flag" and r["final_flag"]]
    passed_clean = [r for r in results if not r.get("user_provided") and r["expect"] == "pass" and not r["final_flag"] and not r.get("exception")]
    passed_exception = [r for r in results if not r.get("user_provided") and r["expect"] == "pass" and not r["final_flag"] and r.get("exception")]
    failures = [r for r in results if not r.get("user_provided") and not r["correct"]]

    # Sort each group by entropy (highest first)
    for group in [user_provided, flagged_secrets, passed_clean, passed_exception, failures]:
        group.sort(key=lambda x: -x["entropy_val"])

    def make_table(title, rows, show_exception=False):
        table = Table(title=title, show_header=True, header_style="bold", title_style="bold")
        table.add_column("", justify="right", width=5)  # Status: [alert/eyes] [✓/✗]
        table.add_column("ID", style="cyan", width=24)
        table.add_column("Regex", justify="center", width=5)  # ✓ if regex caught it
        table.add_column("Ent", justify="center", width=4)    # ✓ if entropy caught it
        table.add_column("Value", justify="right", width=5)   # actual entropy value
        if show_exception:
            table.add_column("Exception", width=20)

        for r in rows:
            # Regex: checkmark if matched, dot if not
            regex = "[yellow]✓[/]" if r["regex_match"] else "·"

            # Entropy: checkmark if flagged, dot if not
            ent_flag = "[yellow]✓[/]" if r["entropy_flag"] else "·"
            ent_val = f"{r['entropy_val']:.2f}"

            # Status icon logic: [optional alert/eyes] [✓/✗]
            # ✓ = clean/passed, ✗ = flagged as secret
            if r.get("user_provided"):
                # User provided - eyes + indicator (user must verify)
                indicator = "[red]✗[/]" if r["final_flag"] else "[green]✓[/]"
                status = f"👀 {indicator}"
            elif r["correct"]:
                # Result matches expectation
                status = "   [green]✓[/]"
            else:
                # Result does NOT match expectation - alarm!
                status = "[red]🚨 ✗[/]"

            row_data = [
                status,
                r["id"],
                regex,
                ent_flag,
                ent_val,
            ]
            if show_exception:
                row_data.append(r.get("exception") or "")

            table.add_row(*row_data)

        return table

    # Print groups
    if user_provided:
        console.print(make_table("👀 User-Provided Values (verify manually)", user_provided))
        console.print()

    if failures:
        console.print(make_table("🚨 Unexpected Results", failures))
        console.print()

    if flagged_secrets:
        console.print(make_table("Secrets Flagged (expect: flag → FLAG)", flagged_secrets))
        console.print()

    if passed_exception:
        console.print(make_table("Passed via Exception (expect: pass → pass)", passed_exception, show_exception=True))
        console.print()

    if passed_clean:
        console.print(make_table("Clean Non-Secrets (expect: pass → pass)", passed_clean))
        console.print()

    # Summary
    s = data["summary"]
    console.print(f"[bold]ACCURACY:[/] {s['correct']}/{s['total']} ({s['accuracy']*100:.0f}%)")
    console.print()
    console.print(f"  [green]✓[/] True Positives:  {s['true_positives']:2d}   (secrets correctly flagged)")
    console.print(f"  [green]✓[/] True Negatives:  {s['true_negatives']:2d}   (non-secrets correctly passed)")
    console.print(f"  [red]✗[/] False Positives: {s['false_positives']:2d}   (non-secrets incorrectly flagged)")
    console.print(f"  [red]✗[/] False Negatives: {s['false_negatives']:2d}   (secrets incorrectly passed)")
