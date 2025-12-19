# Navigation System Refactor: Breadcrumbs & Menus

## Executive Summary

Replace the current `Page` class abstraction with a **convention-driven navigation system** that derives the navigation tree from routes automatically, requiring minimal configuration.

**Key principle:** Routes are the source of truth. Navigation structure is inferred, not duplicated.

---

## Current State Analysis

### The Problem

The current `Page` abstraction conflates multiple concerns:
- View/controller logic
- Route registration
- Breadcrumb hierarchy
- Menu configuration
- ACL definitions

This creates a leaky abstraction where Flask concepts bleed through, and navigation structure is scattered across:
1. **Routes** - URL patterns (`/swork/members/<id>`)
2. **Page classes** - parent references, labels, ACL
3. **Menu specs** - in settings files (MAIN_MENU, SWORK_MENU, etc.)
4. **Base classes** - module-specific secondary menus

### Current Pain Points

**Breadcrumbs:**
- Parent defined as class reference (`parent = MembersPage`) - tight coupling
- Dynamic labels need instance data but parent is a class
- URL generation requires tracking `args` dict manually

**Menus:**
- `MenuService` is request-scoped, modified by each page
- Active state detection via URL prefix matching (fragile)
- Role filtering requires instantiating Page classes to call `__acl__()`
- Secondary menus set per-module via inheritance

**General:**
- Adding a page requires updating multiple places
- Easy to forget nav tree update, causing runtime issues

---

## Proposed Solution: Convention-Driven Navigation

### Core Principles

1. **Blueprint = Section**: Each blueprint defines a navigation section
2. **Route = Page**: Each route is a navigation page
3. **Hierarchy from URL**: Parent-child relationships inferred from URL patterns
4. **Labels inferred**: From docstring or function name
5. **`g.nav` for request state**: Explicit, no magic proxies
6. **Override when needed**: `@nav()` decorator for edge cases only

### Inference Rules

#### Parent Inference (from URL)

```
/swork/                  → parent: (section root, no parent)
/swork/members/          → parent: swork
/swork/members/<id>      → parent: swork.members
/swork/groups/           → parent: swork
/swork/groups/<id>       → parent: swork.groups
/swork/groups/<id>/edit  → parent: swork.group (may need override)
```

Rules:
- `/foo/bar/` is child of `/foo/`
- `/foo/<param>` is child of `/foo/`
- `/foo/<param>/bar` is child of `/foo/<param>` (often needs `@nav(parent=...)`)

#### Label Inference

1. First line of docstring (if present)
2. Otherwise: function name, titleized and spaces added

```python
def members():
    """Membres"""  # ← label = "Membres"
    ...

def user_groups():  # ← label = "User Groups"
    ...
```

---

## Usage Examples

### Most Pages: Zero Configuration

```python
@blueprint.route("/members/")
def members():
    """Membres"""
    return render_template("pages/members.j2")
```

The system infers:
- Endpoint: `swork.members`
- Label: "Membres" (from docstring)
- Parent: `swork` (from URL)
- URL: `/swork/members/`

### Dynamic Breadcrumb Label

```python
@blueprint.route("/members/<id>")
def member(id: str):
    user = get_obj(id, User)
    g.nav.label = user.full_name  # dynamic label
    return render_template("pages/member.j2", user=user)
```

### Override Parent (Non-Hierarchical URL)

```python
@blueprint.route("/profile/")
@nav(parent="members")  # logically under members, not at /members/profile/
def my_profile():
    return redirect(url_for("swork.member", id=g.user.id))
```

### ACL-Protected Page

```python
@blueprint.route("/newsroom/")
@nav(acl=allow(RoleEnum.PRESS_MEDIA))
def newsroom():
    """Newsroom"""
    return render_template("pages/newsroom.j2")
```

### Page with Icon

```python
@blueprint.route("/reports/")
@nav(icon="chart-bar")
def reports():
    """Rapports"""
    return render_template("pages/reports.j2")
```

### Not in Menu (But Has Breadcrumbs)

```python
@blueprint.route("/members/<id>/edit")
@nav(menu=False)
def member_edit(id: str):
    """Modifier"""
    user = get_obj(id, User)
    g.nav.label = f"Modifier {user.full_name}"
    return render_template("pages/member_edit.j2", user=user)
```

### Completely Hidden (API, Redirects)

```python
@blueprint.route("/api/search")
@nav(hidden=True)
def api_search():
    return jsonify(...)
```

### Multiple Routes, Same Page

```python
@blueprint.route("/")
@blueprint.route("/tab/<tab>")
def wire(tab: str = ""):
    """Fil d'actualités"""
    return render_template("pages/wire.j2", tab=tab)
```

Both routes map to endpoint `wire.wire`, single nav entry.

---

## Blueprint Configuration

### Section Metadata

```python
# src/app/modules/swork/__init__.py
from flask import Blueprint

blueprint = Blueprint("swork", __name__, url_prefix="/swork", template_folder="templates")

blueprint.nav = {
    "label": "Social",
    "icon": "users",
    "order": 2,  # position in main menu
    "menu": ["members", "groups", "parrainages"],  # submenu order
}
```

### ACL at Section Level

```python
# src/app/modules/admin/__init__.py
blueprint = Blueprint("admin", __name__, url_prefix="/admin")

blueprint.nav = {
    "label": "Administration",
    "icon": "cog",
    "acl": allow("admin"),  # whole section restricted
}
```

---

## Template Usage

### Context Processor Injects Navigation

```python
@app.context_processor
def inject_navigation():
    if hasattr(g, 'nav'):
        return {
            "breadcrumbs": g.nav.breadcrumbs(),
            "main_menu": g.nav.menu("main"),
            "secondary_menu": g.nav.menu(),  # current section
        }
    return {}
```

### Breadcrumbs Template

```jinja2
<nav aria-label="Breadcrumb" class="breadcrumbs">
  {% for crumb in breadcrumbs %}
    {% if loop.last %}
      <span class="current">{{ crumb.label }}</span>
    {% else %}
      <a href="{{ crumb.url }}">{{ crumb.label }}</a>
      <span class="separator">/</span>
    {% endif %}
  {% endfor %}
</nav>
```

### Secondary Menu Template

```jinja2
<nav class="secondary-menu">
  {% for item in secondary_menu %}
    <a href="{{ item.url }}"
       class="{{ 'active' if item.active else '' }}"
       {% if item.icon %}data-icon="{{ item.icon }}"{% endif %}>
      {{ item.label }}
    </a>
  {% endfor %}
</nav>
```

---

## Static Menus (User, Create)

Some menus are curated action lists, not navigation structure. Keep these as static config:

```python
# src/app/settings/menus.py

USER_MENU = [
    {"label": "Mon profil", "endpoint": "swork.my_profile", "icon": "user"},
    {"label": "Préférences", "endpoint": "preferences.home", "icon": "cog"},
    {"label": "Déconnexion", "endpoint": "security.logout", "icon": "logout"},
]

CREATE_MENU = [
    {"label": "Nouvel article", "endpoint": "wire.new_article", "icon": "document"},
    {"label": "Nouvel événement", "endpoint": "events.new_event", "icon": "calendar"},
]
```

Access via:
```python
g.nav.menu("user")    # returns USER_MENU, filtered by permissions
g.nav.menu("create")  # returns CREATE_MENU, filtered by permissions
```

---

## Implementation

### The `@nav()` Decorator

```python
# src/app/flask/lib/nav/decorator.py

def nav(
    *,
    parent: str | None = None,
    label: str | None = None,
    icon: str | None = None,
    order: int | None = None,
    acl: list | None = None,
    menu: bool = True,
    hidden: bool = False,
):
    """Decorator to override navigation defaults.

    Args:
        parent: Override inferred parent (e.g., "members" for swork.members)
        label: Static label (instead of docstring/function name)
        icon: Icon identifier for menus
        order: Position in menu (lower = earlier)
        acl: Access control list for visibility
        menu: If False, page has breadcrumbs but not in menus
        hidden: If True, page excluded from nav entirely
    """
    def decorator(f):
        f._nav_meta = {
            "parent": parent,
            "label": label,
            "icon": icon,
            "order": order,
            "acl": acl or [],
            "menu": menu,
            "hidden": hidden,
        }
        return f
    return decorator
```

### NavRequest (Request-Scoped State)

```python
# src/app/flask/lib/nav/request.py

from flask import g, request
from app.flask.lib.nav.tree import nav_tree

class NavRequest:
    """Request-scoped navigation state. Attached to g.nav."""

    def __init__(self, endpoint: str, view_args: dict):
        self._endpoint = endpoint
        self._view_args = view_args
        self._label_override: str | None = None
        self._parent_override: str | None = None

    @property
    def label(self) -> str | None:
        return self._label_override

    @label.setter
    def label(self, value: str):
        """Set dynamic breadcrumb label for current page."""
        self._label_override = value

    @property
    def parent(self) -> str | None:
        return self._parent_override

    @parent.setter
    def parent(self, value: str):
        """Override inferred parent (rare)."""
        self._parent_override = value

    @property
    def current_section(self) -> str:
        """Get the section (blueprint) for current endpoint."""
        return self._endpoint.split(".")[0] if "." in self._endpoint else self._endpoint

    def breadcrumbs(self) -> list[BreadCrumb]:
        """Build breadcrumb trail from current endpoint to root."""
        return nav_tree.build_breadcrumbs(
            endpoint=self._endpoint,
            view_args=self._view_args,
            label_override=self._label_override,
            parent_override=self._parent_override,
        )

    def menu(self, section: str | None = None) -> list[MenuItem]:
        """Get menu for a section.

        Args:
            section: Section name, or None for current section.
                     Special values: "main", "user", "create"
        """
        if section is None:
            section = self.current_section

        return nav_tree.build_menu(
            section=section,
            current_endpoint=self._endpoint,
            user=g.user,
        )
```

### NavTree (App-Level, Built at Startup)

```python
# src/app/flask/lib/nav/tree.py

from __future__ import annotations
from dataclasses import dataclass, field
from flask import Flask, url_for

@dataclass
class NavNode:
    """A node in the navigation tree."""
    name: str                           # endpoint name (e.g., "swork.members")
    label: str                          # display label
    url_rule: str                       # URL pattern (e.g., "/members/<id>")
    parent: str | None = None           # parent endpoint name
    icon: str = ""
    order: int = 99
    acl: list = field(default_factory=list)
    in_menu: bool = True
    is_section: bool = False            # True for blueprint roots

    def url_for(self, **kwargs) -> str:
        """Generate URL for this node."""
        try:
            return url_for(self.name, **kwargs)
        except Exception:
            return "#"

    def is_visible_to(self, user) -> bool:
        """Check if user can see this node based on ACL."""
        if not self.acl:
            return True
        return evaluate_acl(self.acl, user)


class NavTree:
    """Navigation tree, built at app startup from routes."""

    def __init__(self):
        self._nodes: dict[str, NavNode] = {}
        self._sections: dict[str, NavNode] = {}

    def build(self, app: Flask) -> None:
        """Scan blueprints and routes, build navigation tree."""
        self._build_sections(app)
        self._build_pages(app)
        self._validate()

    def _build_sections(self, app: Flask) -> None:
        """Build section nodes from blueprints."""
        for name, bp in app.blueprints.items():
            nav_config = getattr(bp, "nav", None)
            if nav_config is None:
                continue

            node = NavNode(
                name=name,
                label=nav_config.get("label", name.title()),
                url_rule=bp.url_prefix or "/",
                icon=nav_config.get("icon", ""),
                order=nav_config.get("order", 99),
                acl=nav_config.get("acl", []),
                is_section=True,
            )
            self._nodes[name] = node
            self._sections[name] = node

    def _build_pages(self, app: Flask) -> None:
        """Build page nodes from routes."""
        for rule in app.url_map.iter_rules():
            endpoint = rule.endpoint
            if "." not in endpoint or endpoint.startswith("static"):
                continue

            section = endpoint.split(".")[0]
            if section not in self._sections:
                continue

            view_func = app.view_functions.get(endpoint)
            if view_func is None:
                continue

            meta = getattr(view_func, "_nav_meta", {})

            if meta.get("hidden"):
                continue

            # Skip if already registered (multiple routes same endpoint)
            if endpoint in self._nodes:
                continue

            parent = self._infer_parent(rule.rule, section, meta.get("parent"))
            label = self._infer_label(view_func, meta.get("label"))

            node = NavNode(
                name=endpoint,
                label=label,
                url_rule=rule.rule,
                parent=parent,
                icon=meta.get("icon", ""),
                order=meta.get("order", 99),
                acl=meta.get("acl", []),
                in_menu=meta.get("menu", True),
            )
            self._nodes[endpoint] = node

    def _infer_parent(self, url_rule: str, section: str, override: str | None) -> str | None:
        """Infer parent from URL pattern."""
        if override:
            return f"{section}.{override}" if "." not in override else override

        # Remove trailing slash and parameters
        parts = url_rule.rstrip("/").split("/")

        # Find the parent URL by removing last segment
        # /swork/members/<id> → /swork/members/ → swork.members
        # /swork/members/ → /swork/ → swork

        if len(parts) <= 2:  # Just /section/ or /section
            return section  # Parent is section root

        # Try to find a matching parent route
        # This is simplified; real implementation would look up routes
        parent_path = "/".join(parts[:-1]) + "/"

        # Search for a route matching parent_path
        for name, node in self._nodes.items():
            if node.url_rule.rstrip("/") + "/" == parent_path:
                return name

        return section  # Fallback to section root

    def _infer_label(self, view_func, override: str | None) -> str:
        """Infer label from docstring or function name."""
        if override:
            return override

        # Try docstring first line
        if view_func.__doc__:
            first_line = view_func.__doc__.strip().split("\n")[0]
            if first_line:
                return first_line

        # Fallback to function name, titleized
        name = view_func.__name__
        return name.replace("_", " ").title()

    def _validate(self) -> None:
        """Warn about potential issues."""
        import warnings

        for name, node in self._nodes.items():
            if node.is_section:
                continue

            if node.parent and node.parent not in self._nodes:
                warnings.warn(
                    f"Nav: {name} has parent '{node.parent}' which doesn't exist"
                )

            if not node.label:
                warnings.warn(f"Nav: {name} has no label")

    def get(self, endpoint: str) -> NavNode | None:
        """Get a node by endpoint name."""
        return self._nodes.get(endpoint)

    def children_of(self, parent: str) -> list[NavNode]:
        """Get direct children of a node."""
        children = [
            node for node in self._nodes.values()
            if node.parent == parent and node.in_menu
        ]
        return sorted(children, key=lambda n: (n.order, n.label))

    def build_breadcrumbs(
        self,
        endpoint: str,
        view_args: dict,
        label_override: str | None,
        parent_override: str | None,
    ) -> list[BreadCrumb]:
        """Build breadcrumb trail from endpoint to root."""
        crumbs = []

        node = self.get(endpoint)
        if not node:
            return crumbs

        # Current page
        label = label_override or node.label
        url = node.url_for(**view_args)
        crumbs.append(BreadCrumb(label=label, url=url, current=True))

        # Walk up parent chain
        parent_name = parent_override or node.parent
        visited = {endpoint}  # Prevent infinite loops

        while parent_name and parent_name not in visited:
            visited.add(parent_name)
            parent_node = self.get(parent_name)
            if not parent_node:
                break

            # Filter view_args to only include params in parent's URL
            parent_args = {
                k: v for k, v in view_args.items()
                if f"<{k}>" in parent_node.url_rule
            }

            crumbs.append(BreadCrumb(
                label=parent_node.label,
                url=parent_node.url_for(**parent_args),
                current=False,
            ))

            parent_name = parent_node.parent

        return list(reversed(crumbs))

    def build_menu(
        self,
        section: str,
        current_endpoint: str,
        user,
    ) -> list[MenuItem]:
        """Build menu for a section."""
        # Handle special menus
        if section == "main":
            return self._build_main_menu(current_endpoint, user)
        if section in ("user", "create"):
            return self._build_static_menu(section, user)

        # Section submenu
        children = self.children_of(section)
        items = []

        for node in children:
            if not node.is_visible_to(user):
                continue

            items.append(MenuItem(
                label=node.label,
                url=node.url_for(),
                icon=node.icon,
                active=self._is_active(node.name, current_endpoint),
            ))

        return items

    def _build_main_menu(self, current_endpoint: str, user) -> list[MenuItem]:
        """Build main navigation from sections."""
        sections = sorted(self._sections.values(), key=lambda n: n.order)
        items = []

        for node in sections:
            if not node.is_visible_to(user):
                continue

            items.append(MenuItem(
                label=node.label,
                url=node.url_for(),
                icon=node.icon,
                active=current_endpoint.startswith(node.name + ".") or current_endpoint == node.name,
            ))

        return items

    def _build_static_menu(self, menu_name: str, user) -> list[MenuItem]:
        """Build menu from static configuration."""
        from app.settings.menus import USER_MENU, CREATE_MENU

        config = {"user": USER_MENU, "create": CREATE_MENU}.get(menu_name, [])
        items = []

        for entry in config:
            # TODO: ACL check
            items.append(MenuItem(
                label=entry["label"],
                url=url_for(entry["endpoint"]),
                icon=entry.get("icon", ""),
                active=False,
            ))

        return items

    def _is_active(self, node_endpoint: str, current_endpoint: str) -> bool:
        """Check if node is in current breadcrumb trail."""
        if node_endpoint == current_endpoint:
            return True

        # Check if current is a descendant
        node = self.get(current_endpoint)
        while node and node.parent:
            if node.parent == node_endpoint:
                return True
            node = self.get(node.parent)

        return False


# Global instance, built at app startup
nav_tree = NavTree()


@dataclass(frozen=True)
class BreadCrumb:
    label: str
    url: str
    current: bool = False


@dataclass
class MenuItem:
    label: str
    url: str
    icon: str = ""
    active: bool = False
```

### Registration Hooks

```python
# src/app/flask/lib/nav/__init__.py

from flask import Flask, g, request
from .tree import nav_tree
from .request import NavRequest
from .decorator import nav

__all__ = ["nav", "register_nav", "nav_tree"]


def register_nav(app: Flask) -> None:
    """Register navigation system with Flask app."""

    # Build nav tree after all blueprints registered
    @app.before_first_request
    def build_nav():
        nav_tree.build(app)

    # Create request-scoped nav state
    @app.before_request
    def setup_nav():
        endpoint = request.endpoint
        if endpoint:
            g.nav = NavRequest(endpoint, request.view_args or {})

    # Inject into templates
    @app.context_processor
    def inject_nav():
        if hasattr(g, "nav"):
            return {
                "breadcrumbs": g.nav.breadcrumbs(),
                "main_menu": g.nav.menu("main"),
                "secondary_menu": g.nav.menu(),
            }
        return {}
```

---

## CLI Debugging Tools

```python
# src/app/flask/cli/nav.py

import click
from flask.cli import with_appcontext
from app.flask.lib.nav import nav_tree

@click.group()
def nav():
    """Navigation debugging commands."""
    pass

@nav.command()
@with_appcontext
def tree():
    """Print the full navigation tree."""
    def print_node(node, indent=0):
        prefix = "  " * indent
        marker = "[S]" if node.is_section else "[P]"
        click.echo(f"{prefix}{marker} {node.name}")
        click.echo(f"{prefix}    label: {node.label}")
        click.echo(f"{prefix}    url: {node.url_rule}")
        if node.parent:
            click.echo(f"{prefix}    parent: {node.parent}")
        if node.acl:
            click.echo(f"{prefix}    acl: {node.acl}")
        if not node.in_menu:
            click.echo(f"{prefix}    (not in menu)")

    # Print sections first
    for section in sorted(nav_tree._sections.values(), key=lambda n: n.order):
        print_node(section)

        # Print children
        for child in nav_tree.children_of(section.name):
            print_node(child, indent=1)
            for grandchild in nav_tree.children_of(child.name):
                print_node(grandchild, indent=2)

        click.echo()

@nav.command()
@with_appcontext
def check():
    """Check for navigation issues."""
    issues = []

    for name, node in nav_tree._nodes.items():
        if node.is_section:
            continue

        # Check parent exists
        if node.parent and node.parent not in nav_tree._nodes:
            issues.append(f"WARNING: {name} has unknown parent '{node.parent}'")

        # Check for missing labels
        if not node.label or node.label == name.split(".")[-1].title():
            issues.append(f"INFO: {name} using inferred label '{node.label}'")

    if issues:
        for issue in issues:
            click.echo(issue)
    else:
        click.echo("No issues found.")
```

---

## Migration Path

### Phase 1: Implement New System Alongside Old

1. Create `src/app/flask/lib/nav/` module
2. Add `register_nav(app)` call in `main.py`
3. New views can use new system immediately

### Phase 2: Migrate Modules (Simplest First)

Order:
1. `search` - Very simple, 2 pages
2. `events` - Simple, few pages
3. `preferences` - Medium complexity
4. `biz` - Small module
5. `swork` - Complex, good test case
6. `wire` - Has multi-route pages
7. `wip` - Most complex, has ACL
8. `admin` - Large, save for last

### Phase 3: Remove Old System

1. Delete `src/app/flask/lib/pages/`
2. Remove `Page`, `@page`, `@expose` imports
3. Update `MenuService` to use new nav system
4. Clean up `Context` service

### Per-Module Migration

Before:
```python
# pages/member.py
@page
class MemberPage(BaseSworkPage):
    name = "member"
    path = "/members/<id>"
    parent = MembersPage
    template = "pages/member.j2"

    def __init__(self, id: str):
        self.args = {"id": id}
        self.user = get_obj(id, User)

    @property
    def label(self):
        return self.user.full_name

    def context(self):
        return {"user": self.user}
```

After:
```python
# views/member.py
@blueprint.route("/members/<id>")
def member(id: str):
    user = get_obj(id, User)
    g.nav.label = user.full_name
    return render_template("pages/member.j2", user=user)
```

---

## Feature Comparison

| Feature | Old (Page class) | New (Convention-driven) |
|---------|------------------|------------------------|
| Breadcrumbs | `parent = PageClass` | Inferred from URL |
| Dynamic labels | `@property def label` | `g.nav.label = ...` |
| Menus | `MenuService` + base classes | `g.nav.menu()` |
| ACL | `__acl__()` method | `@nav(acl=...)` or blueprint |
| Route registration | `@page` + registry | Standard Flask routes |
| Auto-discovery | Magic registry scan | Route scanning at startup |
| Multiple routes | `routes: ClassVar` | Multiple `@blueprint.route` |
| Config location | Scattered | Blueprint `.nav` + route docstrings |
| Debugging | Hard (implicit) | `flask nav tree/check` |

---

## Design Decisions

1. **Blueprint ordering**: Use `order` attribute on each blueprint's `.nav` config.

2. **Deep nesting**: URL hierarchy can go arbitrarily deep. Flask endpoint names are limited to 2 levels (`blueprint.function`), but URL patterns have no limit. The nav system infers parent from URL structure, not endpoint naming:

   ```
   URL                                    Endpoint              Inferred Parent
   ─────────────────────────────────────────────────────────────────────────────
   /swork/                                swork.home            (section root)
   /swork/groups/                         swork.groups          swork
   /swork/groups/<id>                     swork.group           swork.groups
   /swork/groups/<id>/members/            swork.group_members   swork.group
   /swork/groups/<id>/members/<uid>       swork.group_member    swork.group_members
   /swork/groups/<id>/members/<uid>/edit  swork.group_member_edit  swork.group_member
   ```

   Parent inference works by finding registered routes whose URL pattern matches the parent path.

3. **Internationalization**: No i18n needed currently. For localized labels, use lazy strings:
   ```python
   from flask_babel import lazy_gettext as _

   @nav(label=_("Membres"))
   def members(): ...
   ```

4. **Testing**: Navigation is tested via integration or e2e tests. No mocking of `nav_tree`.

---

## Lessons Learned: Events Module Migration

The events module was the first to be migrated. Key lessons:

### 1. Context Service Integration

**Problem:** The `HeaderBreadcrumbs` component reads breadcrumbs from the `Context` service, not from template variables.

**Solution:** The nav registration hook injects breadcrumbs into the Context service in the legacy format:

```python
def _inject_breadcrumbs_to_context() -> None:
    context = container.get(Context)
    breadcrumbs = [
        {"name": crumb.label, "href": crumb.url, "current": crumb.current}
        for crumb in g.nav.breadcrumbs()
    ]
    context.update(breadcrumbs=breadcrumbs)
```

Note the key mapping: nav uses `label`/`url`, legacy uses `name`/`href`.

### 2. HTMX Detection

**Problem:** Initial code used `request.headers.get("HX-Request")` directly, causing incorrect behavior.

**Solution:** Use the Flask-HTMX extension properly:
- `htmx.boosted` = boosted link click → render full page
- `htmx` (truthy, not boosted) = partial HTMX request → may return fragment
- Neither = regular request → render full page

```python
@blueprint.route("/")
def events():
    if htmx.boosted:
        return _render_full_page()
    if htmx:
        return _handle_htmx_partial()
    return _render_full_page()
```

### 3. GET vs POST Handlers

**Problem:** HTMX GET handler was calling `filter_bar.update_state()` which expects form data.

**Solution:** Separate concerns clearly:
- GET handler: reads query params, session state
- POST handler: processes form data, updates session state

### 4. File Organization

Split views into separate modules for clarity:

```
views/
├── __init__.py        # Imports all to register routes
├── _common.py         # Shared: ViewModels, DateFilter, Calendar, TABS
├── events_list.py     # List view + POST
├── event_detail.py    # Detail view + POST (like/unlike)
└── calendar.py        # Calendar view
```

### 5. Import Style

Use absolute imports from parent packages to satisfy linter (TID252):

```python
# Good
from app.modules.events import blueprint
from app.modules.events.views._common import EventListVM

# Avoid
from .. import blueprint
from ._common import EventListVM
```

### 6. Test Assertions

Session-based authentication may not work fully in test environments. Accept both success and redirect:

```python
def test_page_accessible(self, authenticated_client):
    response = authenticated_client.get("/events/")
    assert response.status_code in (200, 302)
```

### 7. Navigation Decorator Usage

- Most views need no decorator - labels from docstrings, parents from URLs
- `@nav(parent="events")` - override inferred parent
- `@nav(hidden=True)` - exclude from nav (POST handlers, API endpoints)

### 8. Template Title Variable

**Problem:** Templates expect a `title` variable for the page title (in `<title>` tag).

**Solution:** Include `title` in the context for every view that renders a template:

```python
@blueprint.route("/profile")
def profile():
    """Visibilité du profil public"""
    ctx = get_profile_data()
    ctx["title"] = "Visibilité du profil public"  # Required for templates
    return render_template("pages/profile.j2", **ctx)
```

The title typically matches the docstring/nav label, but can differ if needed.

### 9. Endpoint Naming: Underscores vs Hyphens

**Problem:** Old Page classes used `name = "biz-item"` with hyphens, but Flask view function names use underscores (`biz_item`). The endpoint name comes from the function name.

**Solution:** Update any routing functions that reference the old hyphenated endpoint names:

```python
# Old (Page class name)
name = f"{_ns}.biz-item"

# New (function name)
name = f"{_ns}.biz_item"
```

Check for `url_for` calls in routing modules that may need updating when migrating.

### 10. Coexisting with Old Page Classes

**Problem:** During migration, old Page classes may still be used by tests or menu systems that call `url_for(f".{page_class.name}")`. If the Page class name differs from the view function name, this fails.

**Solution:** Add a `url_string` attribute to old Page classes that maps to the new view endpoint:

```python
#@page  # Disabled - using views instead
class PrefPasswordPage(BasePreferencesPage):
    name = "Mot de passe"  # Old French name
    url_string = ".password"  # Maps to new view endpoint
    label = "Mot de passe"
    ...
```

The menu system checks for `url_string` first:
```python
def make_menu(name: str):
    for page_class in MENU:
        if hasattr(page_class, "url_string"):
            href = url_for(page_class.url_string)
        else:
            href = url_for(f".{page_class.name}")
```

### 11. Circular Import Issues with Views

**Problem:** Importing views at module level can cause circular imports when:
- Module `__init__.py` imports views
- Views import from services (e.g., `social_graph`, `activity_stream`)
- Services import from models in the same module

This creates chains like: `swork.__init__` → `swork.views` → `social_graph` → `activity_stream` → `swork.models` → (back to `swork.__init__`)

**Solution:** Use lazy imports inside functions that need the problematic modules:

```python
# Instead of top-level import:
# from app.services.social_graph import adapt  # Causes circular import

# Use lazy import inside functions:
def swork():
    from app.services.social_graph import adapt  # Imported when function runs
    followees = adapt(g.user).get_followees()
    ...
```

This applies to:
- `app.services.social_graph` (adapt, SocialUser)
- `app.services.activity_stream` (get_timeline, post_activity)
- Any other services that import from modules with views

### 12. Page Context Objects for Template Compatibility

**Problem:** Old Page classes provide `self` as `page` in template context, used for attributes like `page.top_news()`, `page.label`, etc. New views don't have this object.

**Solution:** Create a simple context class to provide expected attributes:

```python
@define
class WirePageContext:
    """Page-like object for template context."""
    label: str = "News"

    def top_news(self) -> list:
        """Return top news items (placeholder)."""
        return []

def _render_wire(tab, filter_bar, tabs):
    page = WirePageContext()
    return render_template("pages/wire.j2", page=page, ...)
```

### 13. Preserving Hyphenated Endpoint Names

**Problem:** Some old Page classes have hyphenated names (e.g., `org-profile`, `alt-content`). Flask function names can't use hyphens. Menu systems may look up endpoints by these old names.

**Solution:** Use the `endpoint` parameter in route decorator to set a custom endpoint name:

```python
@blueprint.route("/org-profile", endpoint="org-profile")
def org_profile():
    """Business Wall - endpoint preserves old hyphenated name."""
    ...
```

This allows `url_for("wip.org-profile")` to work even though the function is named `org_profile`.

### 14. Multi-Route Views

**Problem:** Some pages respond to multiple URLs (e.g., `/` redirects to `/tab/<tab>`). The Page class handled this with `paths` attribute.

**Solution:** Use multiple route decorators on a single function, or create separate functions:

```python
@blueprint.route("/")
@blueprint.route("/wip")  # Backward compatibility
def wip():
    """Responds to both /wip/ and /wip/wip"""
    return redirect(url_for(".dashboard"))
```

### 15. ACL Checks in Views

**Problem:** Old Page classes used `__acl__()` method for role-based access control. New views need equivalent protection.

**Solution:** Check roles at the start of view functions:

```python
@blueprint.route("/newsroom")
def newsroom():
    from app.services.roles import has_role

    user = g.user
    if not has_role(user, [RoleEnum.PRESS_MEDIA]):
        msg = "Access denied to newsroom"
        raise Forbidden(msg)

    # Rest of view logic...
```

For modules with many protected views, consider a decorator or before_request handler.

### 16. Secondary Menus

**Problem:** Old Page classes generated secondary menus via `menus()` method. Views need to provide this context.

**Solution:** Create a helper function and pass menu data to templates:

```python
# In _common.py
def get_secondary_menu(current_name: str):
    from ..menu import make_menu
    return make_menu(current_name)

# In view
return render_template(
    "template.j2",
    menus={"secondary": get_secondary_menu("dashboard")},
    ...
)
```

### 17. Incremental Migration Strategy

**Problem:** Large modules (like admin with 434 tests) are risky to migrate all at once.

**Solution:** Add nav config first, then migrate views incrementally:

1. Add `blueprint.nav = {...}` config
2. Keep existing Page classes working
3. Migrate views one at a time, testing after each
4. Disable @page decorators only after view is working
5. Update menu systems to work with both old and new endpoints

For complex modules, it's acceptable to add nav config and leave Page classes in place if they work correctly.

---

## Migration Status

| Module | Status | Notes |
|--------|--------|-------|
| events | ✅ Done | First migration, validated approach |
| search | ✅ Done | Very simple, 1 page |
| preferences | ✅ Done | 8 views (profile, interests, contact, banner, invitations + redirects) |
| biz | ✅ Done | 3 views (home, purchases, item) |
| swork | ✅ Done | 9 views (home, members, member, groups, group, new_group, organisations, org, parrainages) |
| wire | ✅ Done | 2 pages (wire with tabs, item detail) with page context object |
| wip | ✅ Done | 11 views with ACL checks, hyphenated endpoint names preserved |
| admin | ✅ Done | Nav config added, keeping existing Page classes (complex module with 434 tests) |

---

## Remaining Tasks

### Overview

| Item                        | Status         | Notes                                            |
|-----------------------------|----------------|--------------------------------------------------|
| Admin module migration      | Deferred       | Uses Page classes (434 tests, complex)           |
| Static menus (user/create)  | Not integrated | USER_MENU/CREATE_MENU used directly by templates |
| MenuService update          | Not done       | Still uses MAIN_MENU from settings               |
| Template variable migration | Not done       | Templates could use nav_* variables              |
| Phase 3: Remove Old System  | Not started    | Optional cleanup; old and new systems coexist    |

### Priority 1: Admin Module Migration

The admin module is the last major module using the old Page class system. While nav config was added, the Page classes remain in place due to complexity (434 tests, many views).

**Why it matters:**
- Admin uses different patterns than other modules (CRUD, forms, tables)
- Keeps the old `src/app/flask/lib/pages/` system alive
- Creates inconsistency in how navigation is configured

**Migration approach:**
1. Audit all admin Page classes and their dependencies
2. Create `views/` package structure mirroring other modules
3. Migrate views in groups (dashboard, users, organisations, content, etc.)
4. Update tests incrementally
5. Remove Page class decorators once views are validated

**Files involved:**
- `src/app/modules/admin/pages/` - 30+ Page classes
- `src/app/modules/admin/templates/` - Complex templates with left-menu
- `tests/b_integration/admin/` - 434 tests

### Priority 2: Unified Menu and Breadcrumb System

**The original motivation:** A single source of truth for navigation, with consistent APIs across the application.

**Current state:** Navigation is fragmented:
- `nav_tree` builds breadcrumbs and section menus ✅
- `MenuService` still builds main menu from `MAIN_MENU` config ❌
- Secondary menus use module-specific `get_menus()` helpers ❌
- Static menus (user/create) used directly in templates ❌
- Templates access breadcrumbs via `Context` service, not nav ❌

**Target architecture:**

```
┌─────────────────────────────────────────────────────────────────────┐
│                           NavTree                                   │
│                    (Single Source of Truth)                         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Sections (from blueprint.nav)                                      │
│    └── Pages (from routes + @nav decorator)                         │
│                                                                     │
│  Static Menus (from settings: USER_MENU, CREATE_MENU)               │
│                                                                     │
├─────────────────────────────────────────────────────────────────────┤
│                           g.nav                                     │
│                    (Request-Scoped API)                             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  g.nav.breadcrumbs()      → Breadcrumb trail for current page       │
│  g.nav.menu("main")       → Main navigation sections                │
│  g.nav.menu()             → Current section's secondary menu        │
│  g.nav.menu("user")       → User dropdown menu                      │
│  g.nav.menu("create")     → Create action menu                      │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    Context Processor                                │
│              (Injects into all templates)                           │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  nav_breadcrumbs     = g.nav.breadcrumbs()                          │
│  nav_main_menu       = g.nav.menu("main")                           │
│  nav_secondary_menu  = g.nav.menu()                                 │
│  nav_user_menu       = g.nav.menu("user")                           │
│  nav_create_menu     = g.nav.menu("create")                         │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

**Tasks to achieve this:**

1. **Implement `_build_static_menu()`** in `NavTree`
   - Load USER_MENU and CREATE_MENU from settings
   - Apply ACL filtering based on current user
   - Return consistent `MenuItem` objects

2. **Update `_build_main_menu()`** to use sections from `nav_tree`
   - Currently returns sections but MenuService still used in templates
   - Templates should use `nav_main_menu` from context processor

3. **Remove module-specific `get_menus()` helpers**
   - `preferences/views/_common.py:get_menus()`
   - `swork/views/_common.py:get_menus()`
   - `wip/views/_common.py:get_secondary_menu()`
   - Replace with `menus={"secondary": g.nav.menu()}`

4. **Update context processor** to inject all nav variables:
   ```python
   @app.context_processor
   def inject_nav():
       if hasattr(g, "nav"):
           return {
               "nav_breadcrumbs": g.nav.breadcrumbs(),
               "nav_main_menu": g.nav.menu("main"),
               "nav_secondary_menu": g.nav.menu(),
               "nav_user_menu": g.nav.menu("user"),
               "nav_create_menu": g.nav.menu("create"),
               # Legacy compatibility
               "breadcrumbs": g.nav.breadcrumbs(),
           }
       return {}
   ```

5. **Update templates** to use nav_* variables:
   - `layout/private.j2` - main menu
   - `layout/components/header.j2` - user menu
   - Module left-menu templates - secondary menu
   - Breadcrumb components - nav_breadcrumbs

6. **Deprecate and remove MenuService**
   - Once all templates use nav_* variables
   - Remove `src/app/services/menus.py`

### Design Principles

1. **Single source of truth**: All navigation config flows through `NavTree`
2. **Consistent API**: `g.nav.menu(name)` for all menu types
3. **Explicit over magic**: Templates declare what menu they need
4. **Convention with escape hatches**: Most cases work automatically, `@nav()` for overrides
5. **Testable**: `flask nav check` validates the navigation tree

### CLI Commands (Implemented)

The `flask nav` command group provides debugging tools:

```bash
flask nav tree       # Print full navigation tree
flask nav sections   # List sections with page counts
flask nav check      # Check for issues (missing parents, inferred labels)
flask nav show <ep>  # Show details for specific endpoint
```

---

## References

- Current Page implementation: `src/app/flask/lib/pages/`
- Current menu system: `src/app/services/menus.py`
- Flask-Super scanner: Used for component auto-discovery
- Pyramid ACL: Inspiration for `__acl__` pattern
- New nav system: `src/app/flask/lib/nav/`
- Nav CLI commands: `src/app/flask/cli/nav.py`
