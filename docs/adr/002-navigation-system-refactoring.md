# ADR 002: Navigation System Refactoring - From Page Classes to Flask Views

## Status

Accepted (Implemented)

## Context

The application originally used a custom "Page" system for defining routes and navigation. This system consisted of:

1. **Page classes** decorated with `@page` that combined route definition, view logic, and navigation metadata
2. **PageRegistry** to discover and register page classes
3. **Custom routing** via `Route` wrapper classes

Example of old pattern:
```python
@page
class MembersPage(BaseSworkPage):
    name = "members"
    label = "Membres"
    path = "/members/"
    icon = "users"
    template = "pages/members.j2"
    parent = SworkHomePage

    def context(self):
        return {"members": get_members()}
```

### Problems with the Page System

1. **Circular imports**: Page classes imported from each other (parent references) causing import cycles
2. **Mixed concerns**: Combined routing, view logic, navigation metadata, and template rendering
3. **Non-standard**: Deviated from Flask conventions, requiring custom infrastructure
4. **Complex**: Required PageRegistry, Route wrappers, and decorator magic
5. **Hard to test**: Page classes had implicit dependencies on Flask context

## Decision

Replace the Page system with standard Flask views and a convention-driven navigation system:

1. **Flask views** with `@blueprint.route()` for routing
2. **`@nav()` decorator** for navigation metadata
3. **NavTree** for automatic menu/breadcrumb generation from routes
4. **Module-specific menu configs** for custom secondary menus

### New Architecture

#### Standard Flask Views

```python
@blueprint.route("/members/")
@nav(parent="swork", icon="users")
def members():
    """Membres"""  # Label from docstring
    return render_template("pages/members.j2", members=get_members())
```

#### Navigation Decorator

The `@nav()` decorator attaches metadata to view functions:
- `parent`: Parent endpoint for breadcrumbs
- `icon`: Icon name for menu display
- `label`: Optional label override (defaults to docstring)
- `menu`: Whether to show in navigation (default True)
- `hidden`: Hide from nav tree entirely
- `acl`: Access control rules

#### NavTree System

The `NavTree` class (`app.flask.lib.nav.tree`):
- Builds at app startup from Flask routes
- Generates breadcrumbs from endpoint to root
- Builds section menus from child routes
- Respects ACL rules for visibility

#### Module Menu Configs

Modules with custom menus use constants:

```python
# wip/constants.py
MENU = [
    MenuEntry(name="dashboard", label="Tableau de bord", icon="chart-bar", ...),
    MenuEntry(name="newsroom", label="Newsroom", icon="rocket-launch", ...),
]
```

Injected via context processors:
```python
@blueprint.context_processor
def inject_menu():
    return {"menus": {"secondary": make_menu(current_name)}}
```

## Implementation

### Files Removed

- `app/flask/lib/pages/` (entire module)
- `app/flask/cli/pages.py`
- `app/modules/search/pages/`
- Various `pages/` directories in modules (migrated to views)

### Files Added/Modified

- `app/flask/lib/nav/` - New navigation system
  - `decorator.py` - `@nav()` decorator
  - `tree.py` - NavTree class
  - `context.py` - Context processors
- Module `views/` directories - Flask view functions
- Module `constants.py` - Menu configurations (wip, preferences)

### Migration Pattern

For each module:
1. Create `views/` directory with Flask view functions
2. Move template context logic to view functions
3. Add `@nav()` decorator for navigation metadata
4. Update `__init__.py` to use `register_views()` for deferred imports
5. Configure custom menus via constants and context processors

## Consequences

### Positive

1. **Standard Flask patterns**: Uses idiomatic Flask routing and blueprints
2. **No circular imports**: Views are loaded lazily via `register_views()`
3. **Simpler testing**: Standard Flask test patterns work
4. **Clear separation**: Routing, view logic, and navigation metadata are distinct
5. **Less code**: Removed ~500 lines of Page infrastructure

### Negative

1. **Migration effort**: All modules needed updating
2. **Test updates**: Some tests for Page classes were removed
3. **Menu configs**: Custom menus require explicit configuration

### Metrics

- Tests: 1971 passing (after ACL and access control work in ADR 003)
- Lines of code: Reduced infrastructure complexity
- Import cycles: Resolved

## Future Considerations

1. **Clean up remaining Page classes**: `preferences/pages/` still has metadata classes for backwards compatibility with some tests
2. ~~**View-based tests**~~: ✅ Comprehensive navigation access tests added in ADR 003
3. ~~**Navigation enhancements**~~: ✅ Route-based permission checks implemented in ADR 003

## References

- ADR 001: Circular Imports and Module Layering
- Flask documentation: https://flask.palletsprojects.com/
- Flask Blueprints: https://flask.palletsprojects.com/en/latest/blueprints/
