"""Precommit scanning - thin CLI wrapper around SDK."""
import sys

import click

from devws.sdk.precommit import run_scan


def run_precommit(verbose=False, include_untracked=False):
    """Run precommit scan and display results."""
    click.echo("Scanning for sensitive data...")

    result = run_scan(verbose=verbose, include_untracked=include_untracked)

    files_scanned = result["files_scanned"]
    findings = result["findings"]
    ignored = result["ignored"]
    summary = result["summary"]

    if not findings:
        click.echo(f"\n✅ No secrets found. ({files_scanned} files scanned)")
        if verbose and ignored:
            click.echo(f"\n📋 IGNORED ({len(ignored)} known false positives):")
            click.echo("-" * 50)
            for f in ignored:
                click.echo(f"  {f['file']}:{f['line_num']} - {f['match_type']}")
            click.echo("-" * 50)
        return

    click.echo(f"\n🚨 FOUND {len(findings)} POTENTIAL SECRETS! 🚨")
    click.echo(f"   (Regex: {summary['regex_matches']}, Entropy: {summary['entropy_matches']})")

    for f in findings:
        click.echo("\n" + "-" * 60)
        detection = f.get("detection", "unknown")
        if detection == "entropy":
            click.echo(f"[!] HIGH ENTROPY STRING (entropy={f.get('entropy', 0):.2f})")
        else:
            click.echo(f"[!] {f['match_type']}")

        click.echo(f"  - File:    {f['file']}")
        click.echo(f"  - Line:    {f['line_num']}")
        click.echo(f"  - Match:   {f.get('matched_text', '')[:60]}")
        click.echo(f"  - Content: {f.get('line_content', '')[:80]}")

    click.echo("\n" + "=" * 60)
    click.echo("Please review and remove sensitive data before committing.")

    if verbose and ignored:
        click.echo(f"\n📋 IGNORED ({len(ignored)} known false positives):")
        click.echo("-" * 50)
        for f in ignored:
            click.echo(f"  {f['file']}:{f['line_num']} - {f['match_type']}")
        click.echo("-" * 50)

    # Exit non-zero so CI/CD and wrapper tools detect failure
    sys.exit(1)
