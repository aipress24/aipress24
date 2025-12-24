# ADR 003: Navigation ACL System and Magic Roles

## Status

**Implemented** (All phases complete - 2024-12)

## Context

The navigation system (ADR 002) supports ACL rules via the `@nav()` decorator:

```python
@blueprint.route("/newsroom")
@nav(icon="rocket-launch", acl=[("Allow", RoleEnum.PRESS_MEDIA, "view")])
def newsroom():
    """Newsroom"""
    ...
```

### Multi-Layer Access Control Architecture

The application uses a defense-in-depth approach with four access control layers:

| Layer | Mechanism | Purpose | Scope |
|-------|-----------|---------|-------|
| 1. Doorman | Path prefix rules (`/admin/`) | Block unauthorized access early | Global, path-based |
| 2. Blueprint hooks | `@blueprint.before_request` | Require authentication per module | Module-level |
| 3. Nav ACL | `@nav(acl=[...])` | Control menu visibility | Per-route |
| 4. View checks | `has_role()` in view handlers | Enforce fine-grained access | Per-request |

**Design principle**: Each layer serves a distinct purpose. Nav ACL controls what users *see* in menus; view checks control what users *can access*. For most routes, authentication at Layer 2 is sufficient. Role-based restrictions need both Layer 3 (hide from nav) and Layer 4 (deny at view).

### Current State (as of 2024-12)

**ACL-protected routes:**
- All 11 `/admin/*` routes - Allow ADMIN ✅
- `wip.newsroom` - Allow PRESS_MEDIA
- `wip.comroom` - Allow PRESS_RELATIONS
- `wip.dashboard` - Allow PRESS_MEDIA, Allow ACADEMIC

### Problems Addressed

1. ✅ **Admin routes unprotected** - All admin routes now have ACL (section-level inheritance)
2. ✅ **Personal routes exposed** - Routes like billing, performance, and preferences now use SELF ACL
3. ✅ **GUEST role unused** - Removed from RoleEnum; KYC now raises KeyError for invalid roles
4. ✅ **No ownership concept** - SELF magic role expresses "visible to authenticated users, ownership checked in view"
5. ✅ **Org routes unprotected** - org-profile protected with MANAGER/LEADER ACL + view check

### Current Role Definitions (as of 2024-12)

```python
class RoleEnum(StrEnum):
    ADMIN = "admin"
    LEADER = "leader"        # Org leadership role
    MANAGER = "manager"      # Org management role
    PRESS_MEDIA = "journalist"
    PRESS_RELATIONS = "press_relations"
    EXPERT = "expert"
    ACADEMIC = "academic"
    TRANSFORMER = "transformer"
    # Magic roles (evaluated at runtime, not stored in database)
    SELF = "self"            # Owner of the resource
```

## Decision

### 1. Remove GUEST Role

Remove `GUEST` from `RoleEnum`. It serves no purpose:
- No users are assigned this role
- Used only as a fallback in `_role_from_name()` which should raise an error instead
- Creates confusion about role semantics

### 2. Add Magic Roles

Introduce "magic roles" - pseudo-roles that represent contextual access patterns rather than static role membership:

```python
class RoleEnum(StrEnum):
    # Static roles (assigned to users)
    ADMIN = "admin"
    LEADER = "leader"
    MANAGER = "manager"
    PRESS_MEDIA = "journalist"
    PRESS_RELATIONS = "press_relations"
    EXPERT = "expert"
    ACADEMIC = "academic"
    TRANSFORMER = "transformer"

    # Magic roles (evaluated at runtime)
    SELF = "self"              # Owner of the resource (implemented)
    # ORG_MEMBER = "org_member"  # Future: Member of the same organisation
```

#### SELF Role

**Meaning**: The current user owns the resource being accessed.

**Nav visibility**: Always visible to authenticated users. The navigation system cannot determine ownership without request context, so SELF-protected routes appear in menus for all logged-in users.

**Access control**: Views must verify ownership:
```python
@blueprint.route("/billing")
@nav(icon="credit-card", acl=[("Allow", RoleEnum.SELF, "view")])
def billing():
    """Facturation"""
    # View implicitly checks g.user owns the billing data
    invoices = get_invoices_for_user(g.user)
    ...
```

**Use cases**:
- `/wip/billing` - User's invoices
- `/wip/performance` - User's performance metrics
- `/wip/mail` - User's messages
- `/preferences/*` - User's settings

#### ORG_MEMBER Role (Future - Not Yet Implemented)

**Note**: This magic role is designed but not yet implemented. Organization routes currently use explicit MANAGER/LEADER ACLs with view-level checks.

**Meaning**: The current user belongs to the same organization as the resource.

**Nav visibility**: Would be visible to authenticated users who have an organization.

**Current approach** (without ORG_MEMBER):
```python
@blueprint.route("/org-profile")
@nav(icon="building-library", acl=[
    ("Allow", RoleEnum.MANAGER, "view"),
    ("Allow", RoleEnum.LEADER, "view"),
])
def org_profile():
    """Page institutionnelle"""
    # Explicit role check in view
    if not (has_role(user, RoleEnum.MANAGER) or has_role(user, RoleEnum.LEADER)):
        raise Forbidden(...)
    org = g.user.organisation
    ...
```

**Future use cases** (when ORG_MEMBER is implemented):
- Organization-scoped content visible to all org members
- Simplify ACL for "any member of this organization"

### 3. ACL Coverage Plan

#### Admin Section

All admin routes require ADMIN role:

| Route | Label | ACL |
|-------|-------|-----|
| `admin.index` | Admin | Allow ADMIN |
| `admin.dashboard` | Tableau de bord | Allow ADMIN |
| `admin.users` | Utilisateurs | Allow ADMIN |
| `admin.new_users` | Inscriptions | Allow ADMIN |
| `admin.modif_users` | Modifications | Allow ADMIN |
| `admin.orgs` | Organisations | Allow ADMIN |
| `admin.groups` | Groupes | Allow ADMIN |
| `admin.contents` | Contenus | Allow ADMIN |
| `admin.exports` | Exports | Allow ADMIN |
| `admin.promotions` | Promotions | Allow ADMIN |
| `admin.system` | Système | Allow ADMIN |
| `admin.show_user` | Détail utilisateur | Allow ADMIN |
| `admin.show_org` | Détail organisation | Allow ADMIN |
| `admin.validation_user` | Validation inscription | Allow ADMIN |
| `admin.export_database` | Export DB | Allow ADMIN |
| `admin.export_route` | Export générique | Allow ADMIN |

#### WIP Section (Personal Routes)

| Route | Label | Current | Proposed ACL |
|-------|-------|---------|--------------|
| `wip.billing` | Facturation | none | Allow SELF |
| `wip.billing_get_pdf` | PDF facture | none | Allow SELF |
| `wip.billing_get_csv` | CSV facture | none | Allow SELF |
| `wip.performance` | Performance | none | Allow SELF |
| `wip.mail` | Messagerie | none | Allow SELF |
| `wip.delegate` | Délégations | none | Allow SELF |

#### WIP Section (Organization Routes)

| Route | Label | Current | Proposed ACL |
|-------|-------|---------|--------------|
| `wip.org-profile` | Business Wall | none | Allow MANAGER, Allow LEADER |
| `wip.org_profile_post` | (POST handler) | none | Allow MANAGER, Allow LEADER |

#### WIP Section (Role-Based - Keep Current)

| Route | Label | ACL |
|-------|-------|-----|
| `wip.newsroom` | Newsroom | Allow PRESS_MEDIA |
| `wip.comroom` | Com'room | Allow PRESS_RELATIONS |
| `wip.dashboard` | Tableau de bord | Allow PRESS_MEDIA, Allow ACADEMIC |

#### Preferences Section

All preferences routes are personal:

| Route | Label | Proposed ACL |
|-------|-------|--------------|
| `preferences.home` | Préférences | Allow SELF |
| `preferences.profile` | Profil public | Allow SELF |
| `preferences.interests` | Centres d'intérêts | Allow SELF |
| `preferences.banner` | Image de présentation | Allow SELF |
| `preferences.contact_options` | Options de contact | Allow SELF |
| `preferences.invitations` | Invitations | Allow SELF |

### 4. Implementation Changes

#### NavNode.is_visible_to()

Updated visibility check to handle SELF magic role:

```python
def is_visible_to(self, user) -> bool:
    acl = self.effective_acl  # Includes inherited ACL
    if not acl:
        return True

    for directive, role, action in acl:
        directive_lower = directive.lower()
        if directive_lower == "deny":
            return False
        if directive_lower == "allow":
            if role == RoleEnum.SELF:
                # SELF is always visible to authenticated users
                # Actual ownership check happens in the view
                if not getattr(user, "is_anonymous", True):
                    return True
            elif has_role(user, role):
                return True

    return False
```

**Note**: When ORG_MEMBER is implemented, add handling similar to SELF:
```python
elif role == RoleEnum.ORG_MEMBER:
    if hasattr(user, 'organisation') and user.organisation:
        return True
```

#### CLI Updates

The `flask nav` commands already support filtering by roles. Magic roles will:
- `--roles SELF` - Shows routes visible to any authenticated user (SELF routes)
- `--roles ADMIN` - Shows routes visible to admins only

## Consequences

### Positive

1. **Clearer semantics**: SELF and ORG_MEMBER express intent, not just role membership
2. **Protected admin**: Admin routes hidden from non-admins in navigation
3. **Consistent model**: All routes explicitly declare their access requirements
4. **Better debugging**: `flask nav acl` and `flask nav roles` show complete access map
5. **No GUEST confusion**: Removed unused role

### Negative

1. **Migration effort**: Need to update all admin and personal routes
2. **Two-layer check**: Magic roles require both nav visibility AND view-level verification
3. **Test updates**: Tests using GUEST role need updating

### Neutral

1. **Nav vs access**: SELF routes visible in menu but access checked in view (unavoidable without request context)
2. **Future permissions**: This design is compatible with a future permission system layered on top

## Implementation Plan

### Phase 1: Remove GUEST role ✅ (Complete - 2024-12)
- ✅ Removed `RoleEnum.GUEST` from `src/app/enums.py`
- ✅ Fixed `_role_from_name()` in KYC to raise `KeyError` instead of returning GUEST
- ✅ Updated test to use `EXPERT` instead of `GUEST`

### Phase 2: Add magic roles ✅ (Complete - 2024-12)
- ✅ Added `RoleEnum.SELF` to `src/app/enums.py`
- ✅ Updated `is_visible_to()` to handle SELF (visible to all authenticated users)
- ✅ Tests updated to handle SELF magic role correctly

### Phase 3: Protect admin routes ✅ (Complete - 2024-12)
- ✅ Added section-level ACL to admin blueprint (inherited by all child routes)
- ✅ Implemented ACL inheritance in NavTree
- ✅ Removed individual ACL declarations from admin views (now inherited)
- ✅ CLI commands show inherited ACLs with source

### Phase 4: Protect personal routes ✅ (Complete - 2024-12)
- ✅ Added SELF ACL to billing, performance, mail, delegate routes
- ✅ Added section-level SELF ACL to preferences blueprint (inherited by all preferences routes)
- ✅ Views implicitly verify ownership (show current user's data only)

### Phase 5: Protect org routes ✅ (Complete - 2024-12)
- ✅ Added MANAGER/LEADER ACL to org-profile
- ✅ Added view-level role check to enforce access control

### Phase 6: Add comprehensive anonymous access tests ✅ (Complete - 2024-12)
- ✅ Added `TestAnonymousAccessSurface::test_anonymous_access_surface` - verifies only expected public routes are accessible
- ✅ Added `TestAnonymousAccessSurface::test_blueprint_before_request_hooks` - verifies blueprint-level auth
- ✅ Tests document expected public endpoints and catch accidental exposure

## Testing Strategy

### Current Test Coverage

| Test | Purpose | Status |
|------|---------|--------|
| `test_doorman.py` | Path-based access control (unit) | ✅ Complete |
| `test_nav_access.py::test_visible_routes_are_accessible` | ACL-protected routes visible → accessible | ✅ Complete |
| `test_nav_access.py::test_hidden_routes_are_denied` | ACL-hidden routes → denied | ✅ Complete |
| `test_nav_access.py::test_protected_routes_require_auth` | Unauthenticated access to ACL routes | ✅ Complete |
| `test_nav_access.py::test_anonymous_access_surface` | Verify only expected routes are public | ✅ Complete |
| `test_nav_access.py::test_blueprint_before_request_hooks` | Verify blueprint-level auth works | ✅ Complete |
| `test_nav_tree.py` | Nav tree structure, ACL inheritance, schema validation | ✅ Complete |

### Decision: Should we test anonymous access to ALL routes?

**Question**: Do we need a test proving anonymous users can only access login/logout/public pages?

**Answer**: Yes, but with a pragmatic approach:

1. **Blueprint-level protection is already in place**: Most modules have `@blueprint.before_request` hooks that enforce authentication. This is tested implicitly by the existing e2e tests.

2. **A focused test is valuable**: A test that explicitly checks "these are the ONLY routes accessible without auth" provides:
   - Documentation of the public attack surface
   - Regression detection if someone removes a `before_request` hook
   - Confidence for security audits

3. **Implementation**: Phase 6 will add `TestAnonymousAccessSurface` that:
   - Gets all registered routes
   - Tests each without auth
   - Asserts only explicitly allowed routes (login, register, public pages, static) return 200/302-to-public

## Existing Access Control Integration

### Current Redundancies

Some routes have duplicate access checks:

| Route | Nav ACL | View Check | Doorman | Blueprint |
|-------|---------|------------|---------|-----------|
| `/admin/*` | ✅ ADMIN | - | ✅ ADMIN | ✅ ADMIN |
| `/wip/newsroom` | ✅ PRESS_MEDIA | ✅ PRESS_MEDIA | - | ✅ auth |
| `/wip/billing` | - | ✅ ownership | - | ✅ auth |

### Decision: Consolidate or Keep Multi-Layer?

**Keep multi-layer** for defense in depth:

1. **Doorman** catches unauthorized access before any view code runs
2. **Blueprint hooks** enforce module-level auth requirements
3. **Nav ACL** controls UI visibility (UX concern)
4. **View checks** handle ownership and context-specific access

**Simplification opportunity**: For admin routes, the triple protection (Doorman + Blueprint + Nav ACL) is redundant. Consider:
- Remove admin blueprint `before_request` since Doorman handles it
- Or remove Doorman admin rule since blueprint handles it
- Keep Nav ACL regardless (it's about UX, not security)

## Future Considerations

1. **ORG_MEMBER magic role**: Implement organization membership check for org-scoped content
2. **Permission system**: Magic roles could evolve into a full permission system with predicates
3. **Deny rules**: Currently only Allow is used; Deny could be added for exceptions
4. **Hierarchical roles**: ADMIN could inherit all role permissions
5. **Audit logging**: Track access attempts to protected routes
6. **Consolidate admin protection**: Consider removing redundant layers for admin routes

## References

- ADR 002: Navigation System Refactoring
- Flask-Security-Too: https://flask-security-too.readthedocs.io/
- RBAC patterns: https://en.wikipedia.org/wiki/Role-based_access_control
