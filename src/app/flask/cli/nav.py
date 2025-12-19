# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Navigation CLI commands for debugging and inspection."""

from __future__ import annotations

import click
from flask.cli import with_appcontext
from flask_super.cli import group
from rich.console import Console
from rich.table import Table
from rich.tree import Tree

from app.flask.lib.nav import nav_tree


@group(short_help="Navigation debugging commands")
def nav() -> None:
    """Navigation tree inspection and debugging."""


@nav.command()
@with_appcontext
def tree() -> None:
    """Print the full navigation tree."""
    console = Console()

    # Build tree if not already built
    from flask import current_app

    nav_tree.build(current_app)

    # Create rich tree
    root = Tree("[bold]Navigation Tree[/bold]")

    # Print sections sorted by order
    sections = sorted(nav_tree._sections.values(), key=lambda n: n.order)

    for section in sections:
        section_node = root.add(
            f"[bold cyan]{section.name}[/bold cyan] - {section.label} "
            f"[dim]({section.url_rule})[/dim]"
        )

        # Get children
        children = nav_tree.children_of(section.name)
        for child in children:
            _add_node_to_tree(section_node, child)

    console.print(root)
    console.print()
    console.print(f"[dim]Total sections: {len(nav_tree._sections)}[/dim]")
    console.print(f"[dim]Total nodes: {len(nav_tree._nodes)}[/dim]")


def _add_node_to_tree(parent_tree: Tree, node) -> None:
    """Recursively add node and its children to tree."""
    label = f"[green]{node.name.split('.')[-1]}[/green] - {node.label}"
    label += f" [dim]({node.url_rule})[/dim]"

    if node.icon:
        label += f" [yellow]icon:{node.icon}[/yellow]"
    if not node.in_menu:
        label += " [red](hidden from menu)[/red]"
    if node.acl:
        label += " [magenta](ACL protected)[/magenta]"

    child_tree = parent_tree.add(label)

    # Recursively add grandchildren
    grandchildren = nav_tree.children_of(node.name)
    for grandchild in grandchildren:
        _add_node_to_tree(child_tree, grandchild)


@nav.command()
@with_appcontext
def check() -> None:
    """Check for navigation issues."""
    from flask import current_app

    nav_tree.build(current_app)

    console = Console()
    issues: list[tuple[str, str, str]] = []  # (severity, endpoint, message)

    for name, node in nav_tree._nodes.items():
        if node.is_section:
            continue

        # Check parent exists
        if node.parent and node.parent not in nav_tree._nodes:
            issues.append(("ERROR", name, f"Unknown parent '{node.parent}'"))

        # Check for missing/inferred labels
        func_name = name.split(".")[-1]
        inferred_label = func_name.replace("_", " ").title()
        if node.label == inferred_label:
            issues.append(("INFO", name, f"Using inferred label '{node.label}'"))

        # Check for duplicate labels in same section
        section = name.split(".")[0]
        siblings = [
            n
            for n in nav_tree._nodes.values()
            if n.parent == section and n.name != name and n.label == node.label
        ]
        if siblings:
            issues.append(
                ("WARNING", name, f"Duplicate label '{node.label}' in section")
            )

    if issues:
        table = Table(title="Navigation Issues")
        table.add_column("Severity", style="bold")
        table.add_column("Endpoint")
        table.add_column("Issue")

        for severity, endpoint, message in issues:
            severity_style = {
                "ERROR": "red",
                "WARNING": "yellow",
                "INFO": "dim",
            }.get(severity, "white")
            table.add_row(f"[{severity_style}]{severity}[/]", endpoint, message)

        console.print(table)
        console.print(f"\n[dim]Found {len(issues)} issue(s)[/dim]")
    else:
        console.print("[green]No issues found.[/green]")


@nav.command()
@with_appcontext
def sections() -> None:
    """List all navigation sections (blueprints with nav config)."""
    from flask import current_app

    nav_tree.build(current_app)

    console = Console()
    table = Table(title="Navigation Sections")
    table.add_column("Name", style="cyan")
    table.add_column("Label")
    table.add_column("URL")
    table.add_column("Icon")
    table.add_column("Order", justify="right")
    table.add_column("Pages", justify="right")

    sections = sorted(nav_tree._sections.values(), key=lambda n: n.order)

    for section in sections:
        page_count = len(nav_tree.children_of(section.name))
        table.add_row(
            section.name,
            section.label,
            section.url_rule,
            section.icon or "-",
            str(section.order),
            str(page_count),
        )

    console.print(table)


@nav.command()
@click.argument("endpoint")
@with_appcontext
def show(endpoint: str) -> None:
    """Show details for a specific endpoint."""
    from flask import current_app

    nav_tree.build(current_app)

    console = Console()
    node = nav_tree.get(endpoint)

    if not node:
        console.print(f"[red]Endpoint '{endpoint}' not found in nav tree[/red]")
        return

    console.print(f"[bold]Endpoint:[/bold] {node.name}")
    console.print(f"[bold]Label:[/bold] {node.label}")
    console.print(f"[bold]URL:[/bold] {node.url_rule}")
    console.print(f"[bold]Parent:[/bold] {node.parent or '(none)'}")
    console.print(f"[bold]Icon:[/bold] {node.icon or '(none)'}")
    console.print(f"[bold]Order:[/bold] {node.order}")
    console.print(f"[bold]In Menu:[/bold] {node.in_menu}")
    console.print(f"[bold]Is Section:[/bold] {node.is_section}")

    if node.acl:
        console.print(f"[bold]ACL:[/bold] {node.acl}")

    # Show children
    children = nav_tree.children_of(node.name)
    if children:
        console.print(f"\n[bold]Children ({len(children)}):[/bold]")
        for child in children:
            console.print(f"  - {child.name} ({child.label})")

    # Show breadcrumb trail
    console.print("\n[bold]Breadcrumb trail:[/bold]")
    crumbs = nav_tree.build_breadcrumbs(endpoint, {})
    for i, crumb in enumerate(crumbs):
        prefix = "  " * i + "→ " if i > 0 else ""
        current = " [current]" if crumb.current else ""
        console.print(f"{prefix}{crumb.label}{current}")
