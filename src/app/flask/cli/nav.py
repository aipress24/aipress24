# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Navigation CLI commands for debugging and inspection."""

from __future__ import annotations

from typing import TYPE_CHECKING

import click
from flask.cli import with_appcontext
from flask_super.cli import group
from rich.console import Console
from rich.table import Table
from rich.tree import Tree

from app.flask.lib.nav import nav_tree

if TYPE_CHECKING:
    from app.models.auth import User


@group(short_help="Navigation debugging commands")
def nav() -> None:
    """Navigation tree inspection and debugging."""


def _get_user_by_email(email: str) -> User | None:
    """Look up a user by email address."""
    from sqlalchemy import select

    from app.flask.extensions import db
    from app.models.auth import User

    stmt = select(User).where(User.email == email)
    return db.session.scalar(stmt)


def _create_mock_user_with_roles(role_names: list[str]) -> object:
    """Create a mock user object with specified roles for ACL checking."""
    from app.enums import RoleEnum
    from app.models.auth import Role

    # Parse role names to RoleEnum values
    roles = []
    for role_name in role_names:
        normalized_name = role_name.strip().upper()
        try:
            role_enum = RoleEnum[normalized_name]
            # Create a mock Role object
            role = Role(name=role_enum.name, description=role_enum.value)
            roles.append(role)
        except KeyError:
            valid_roles = ", ".join(r.name for r in RoleEnum)
            msg = f"Unknown role: {normalized_name}. Valid roles: {valid_roles}"
            raise click.ClickException(msg) from None

    # Create a mock user-like object
    class MockUser:
        is_anonymous = False  # Mock users are always authenticated

        def __init__(self, roles):
            self.roles = roles

        def has_role(self, role):
            """Check if mock user has a role."""
            from app.enums import RoleEnum

            if isinstance(role, RoleEnum):
                return any(r.name == role.name for r in self.roles)
            if isinstance(role, str):
                return any(r.name == role for r in self.roles)
            return False

    return MockUser(roles)


@nav.command()
@click.option("-v", "--verbose", is_flag=True, help="Show detailed info for each route")
@click.option(
    "--email", "email", help="Filter by user email (shows only visible routes)"
)
@click.option(
    "--roles",
    "roles",
    help="Filter by roles (comma-separated, e.g., PRESS_MEDIA,ACADEMIC)",
)
@with_appcontext
def tree(verbose: bool, email: str | None, roles: str | None) -> None:
    """Print the full navigation tree.

    Use --email or --roles to filter the tree to only show routes
    visible to a specific user or role combination.

    Examples:
        flask nav tree --email user@example.com
        flask nav tree --roles PRESS_MEDIA
        flask nav tree --roles PRESS_MEDIA,ACADEMIC
    """
    console = Console()

    # Build tree if not already built
    from flask import current_app

    nav_tree.build(current_app)

    # Determine user for filtering
    filter_user = None
    filter_description = None

    if email and roles:
        msg = "Cannot use both --email and --roles. Choose one."
        raise click.ClickException(msg)

    if email:
        filter_user = _get_user_by_email(email)
        if not filter_user:
            msg = f"User with email '{email}' not found"
            raise click.ClickException(msg)
        role_names = [r.name for r in filter_user.roles]
        filter_description = (
            f"user '{email}' with roles: {', '.join(role_names) or '(none)'}"
        )

    if roles:
        role_list = [r.strip() for r in roles.split(",") if r.strip()]
        filter_user = _create_mock_user_with_roles(role_list)
        filter_description = f"roles: {', '.join(role_list)}"

    # Create rich tree
    if filter_user:
        root = Tree(
            f"[bold]Navigation Tree[/bold] [dim](filtered for {filter_description})[/dim]"
        )
    else:
        root = Tree("[bold]Navigation Tree[/bold]")

    # Track stats
    total_visible = 0
    total_hidden = 0

    # Print sections sorted by order
    sections = sorted(nav_tree._sections.values(), key=lambda n: n.order)

    for section in sections:
        # Check if section is visible to user
        if filter_user and not section.is_visible_to(filter_user):
            total_hidden += 1
            continue

        section_label = (
            f"[bold cyan]{section.name}[/bold cyan] - {section.label} "
            f"[dim]({section.url_rule})[/dim]"
        )
        if verbose:
            section_label += f" [yellow]icon:{section.icon or 'none'}[/yellow]"
            section_label += f" [dim]order:{section.order}[/dim]"
        section_node = root.add(section_label)
        total_visible += 1

        # Get children (filtered if user specified)
        children = nav_tree.children_of(section.name)
        for child in children:
            visible, hidden = _add_node_to_tree(
                section_node, child, verbose, filter_user
            )
            total_visible += visible
            total_hidden += hidden

    console.print(root)
    console.print()

    if filter_user:
        console.print(f"[dim]Visible nodes: {total_visible}[/dim]")
        console.print(f"[dim]Hidden nodes (no access): {total_hidden}[/dim]")
    else:
        console.print(f"[dim]Total sections: {len(nav_tree._sections)}[/dim]")
        console.print(f"[dim]Total nodes: {len(nav_tree._nodes)}[/dim]")


def _add_node_to_tree(
    parent_tree: Tree, node, verbose: bool = False, filter_user=None
) -> tuple[int, int]:
    """Recursively add node and its children to tree.

    Returns:
        Tuple of (visible_count, hidden_count) for statistics.
    """
    # Check visibility if filtering by user
    if filter_user and not node.is_visible_to(filter_user):
        return (0, 1)

    if verbose:
        # Verbose mode: show all details
        label = f"[green]{node.name}[/green]"
        label += f"\n  [bold]label:[/bold] {node.label}"
        label += f"\n  [bold]url:[/bold] {node.url_rule}"
        label += f"\n  [bold]parent:[/bold] {node.parent or '(section root)'}"
        label += f"\n  [bold]icon:[/bold] {node.icon or '(none)'}"
        label += f"\n  [bold]order:[/bold] {node.order}"
        label += f"\n  [bold]in_menu:[/bold] {node.in_menu}"
        if node.acl:
            acl_str = ", ".join(f"{d} {r}" for d, r, _ in node.acl)
            label += f"\n  [bold]acl:[/bold] [magenta]{acl_str}[/magenta]"
    else:
        # Compact mode: one line summary
        label = f"[green]{node.name.split('.')[-1]}[/green] - {node.label}"
        label += f" [dim]({node.url_rule})[/dim]"

        if node.icon:
            label += f" [yellow]icon:{node.icon}[/yellow]"
        if not node.in_menu:
            label += " [red](hidden from menu)[/red]"
        if node.acl:
            label += " [magenta](ACL protected)[/magenta]"

    child_tree = parent_tree.add(label)

    visible_count = 1
    hidden_count = 0

    # Recursively add grandchildren
    grandchildren = nav_tree.children_of(node.name)
    for grandchild in grandchildren:
        visible, hidden = _add_node_to_tree(
            child_tree, grandchild, verbose, filter_user
        )
        visible_count += visible
        hidden_count += hidden

    return (visible_count, hidden_count)


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
        console.print("[bold]ACL:[/bold]")
        for directive, role, action in node.acl:
            console.print(f"  {directive} [magenta]{role.name}[/magenta] ({action})")

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


@nav.command()
@click.option("--by-role", is_flag=True, help="Group routes by required role")
@with_appcontext
def acl(by_role: bool) -> None:
    """List all ACL-protected routes.

    Shows which routes require specific roles to access.
    Use --by-role to group routes by the role that can access them.
    """
    from collections import defaultdict

    from flask import current_app

    nav_tree.build(current_app)

    console = Console()

    # Collect all nodes with ACL
    protected_nodes = [
        (name, node) for name, node in nav_tree._nodes.items() if node.acl
    ]

    if not protected_nodes:
        console.print("[yellow]No ACL-protected routes found.[/yellow]")
        return

    if by_role:
        # Group by role
        role_to_nodes: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
        for name, node in protected_nodes:
            for _directive, role, _action in node.acl:
                role_to_nodes[role.name].append((name, node.label, node.url_rule))

        # Sort roles alphabetically
        for role_name in sorted(role_to_nodes.keys()):
            nodes = role_to_nodes[role_name]
            console.print(
                f"\n[bold magenta]{role_name}[/bold magenta] ({len(nodes)} routes)"
            )
            for name, label, url in sorted(nodes, key=lambda x: x[0]):
                console.print(f"  [green]{name}[/green] - {label} [dim]({url})[/dim]")
    else:
        # Show as table
        table = Table(title="ACL-Protected Routes")
        table.add_column("Endpoint", style="green")
        table.add_column("Label")
        table.add_column("URL", style="dim")
        table.add_column("Access Rules", style="magenta")

        for name, node in sorted(protected_nodes, key=lambda x: x[0]):
            acl_str = ", ".join(f"{d} {r.name}" for d, r, _ in node.acl)
            table.add_row(name, node.label, node.url_rule, acl_str)

        console.print(table)

    console.print(f"\n[dim]Total ACL-protected routes: {len(protected_nodes)}[/dim]")


@nav.command()
@with_appcontext
def roles() -> None:
    """List all roles and which routes they can access."""
    from collections import defaultdict

    from flask import current_app

    from app.enums import RoleEnum

    nav_tree.build(current_app)

    console = Console()

    # Count routes accessible per role
    role_access: dict[str, int] = defaultdict(int)
    total_nodes = len(nav_tree._nodes)

    for node in nav_tree._nodes.values():
        if not node.acl:
            # No ACL means everyone can access
            for role in RoleEnum:
                role_access[role.name] += 1
        else:
            # Check which roles have access
            for directive, role, _ in node.acl:
                if directive == "Allow":
                    role_access[role.name] += 1

    table = Table(title="Role Access Summary")
    table.add_column("Role", style="cyan")
    table.add_column("Accessible Routes", justify="right")
    table.add_column("Restricted", justify="right", style="red")
    table.add_column("Description")

    # Get role descriptions from enum values
    for role in RoleEnum:
        accessible = role_access[role.name]
        restricted = total_nodes - accessible
        table.add_row(
            role.name,
            str(accessible),
            str(restricted) if restricted > 0 else "-",
            role.value,
        )

    console.print(table)
    console.print(f"\n[dim]Total navigation nodes: {total_nodes}[/dim]")
