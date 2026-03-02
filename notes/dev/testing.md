# Testing Best Practices

This document captures testing best practices and antipatterns learned from the AiPress24 codebase.

## Core Principles

### 1. Prefer Stubs Over Mocks

**Do:** Verify tangible outcomes (state) rather than internal interactions (behavior).

```python
# Good: Verify the result
def test_toggle_like_adds_like(db_session, user, post):
    toggle_like(post)
    db_session.flush()
    assert post.like_count == 1

# Avoid: Verify internal calls
def test_toggle_like_calls_like_method(mock_user, post):
    toggle_like(post)
    mock_user.like.assert_called_once_with(post)  # Fragile, coupled to implementation
```

### 2. Test Pure Functions in Isolation

Extract testable logic into pure functions that don't depend on Flask context or database.

```python
# Good: Pure function, easy to test
def _get_logo_url(org) -> str:
    if not org:
        return "/static/img/transparent-square.png"
    if org.is_auto:
        return "/static/img/logo-page-non-officielle.png"
    return org.logo_image_signed_url()

# Test is simple
def test_returns_placeholder_for_auto_org():
    org = MagicMock(is_auto=True)
    assert _get_logo_url(org) == "/static/img/logo-page-non-officielle.png"
```

### 3. Test ViewModels Separately from Views

ViewModels contain presentation logic that can be tested without HTTP requests.

```python
def test_org_vm_extra_attrs(app, db_session, organisation):
    with app.test_request_context():
        vm = OrgVM(organisation)
        attrs = vm.extra_attrs()

        assert "members" in attrs
        assert "count_members" in attrs
        assert "logo_url" in attrs
```

---

## Database Testing Patterns

### Transaction Isolation

The test suite uses nested transactions with savepoints. Each test runs in a transaction that rolls back after completion.

**Critical Rule:** Helper methods should use `flush()`, not `commit()`.

```python
# BAD: Commits bypass test transaction wrapper
def toggle_like(obj: Post) -> str:
    user = adapt(g.user)
    if user.is_liking(obj):
        user.unlike(obj)
    else:
        user.like(obj)
    db.session.commit()  # ❌ Breaks test isolation
    return str(obj.like_count)

# GOOD: Flush makes changes visible without committing
def toggle_like(obj: Post) -> str:
    user = adapt(g.user)
    if user.is_liking(obj):
        user.unlike(obj)
    else:
        user.like(obj)
    db.session.flush()  # ✅ Changes visible, transaction intact
    obj.like_count = adapt(obj).num_likes()
    return str(obj.like_count)

# View layer commits
@blueprint.post("/likes/<cls>/<id>")
def likes(cls: str, id: int) -> str:
    obj = get_obj(id, Post)
    result = toggle_like(obj)
    db.session.commit()  # ✅ Commit at view layer
    return result
```

### Functional Core, Imperative Shell

This pattern keeps business logic pure and testable:

- **Functional Core:** Business logic uses `flush()` to make changes visible
- **Imperative Shell:** Views/controllers call `commit()` after all operations complete

Benefits:
1. Tests can verify state without worrying about transaction boundaries
2. Multiple operations can be composed before a single commit
3. Failures roll back cleanly

---

## Antipatterns to Avoid

### 1. Committing in Helper Methods

```python
# ❌ Antipattern: Commit in helper
def add_user_to_group(user, group):
    group.members.append(user)
    db.session.commit()  # Breaks test isolation

# ✅ Better: Flush in helper, commit in view
def add_user_to_group(user, group):
    group.members.append(user)
    db.session.flush()
```

### 2. Testing External Services Without Mocking

```python
# ❌ Antipattern: Direct external service call
def test_search_results(app):
    results = SearchResults(qs="test", filter="all")  # Calls Typesense
    assert len(results.result_sets) > 0

# ✅ Better: Test components that don't need external services
def test_hit_properties():
    hit = Hit({"document": {"title": "Test", "url": "/test"}})
    assert hit.title == "Test"
```

### 3. Inline Imports in Test Methods

```python
# ❌ Antipattern: Import inside method (fails PLC0415)
def test_something(self):
    from app.models import User
    user = User()

# ✅ Better: Import at top of file
from app.models import User

def test_something(self):
    user = User()
```

### 4. Over-Mocking

```python
# ❌ Antipattern: Mock everything
def test_user_creation(mock_db, mock_session, mock_user_class):
    mock_user_class.return_value = mock_user
    create_user("test@example.com")
    mock_session.add.assert_called_once()

# ✅ Better: Use real objects with test database
def test_user_creation(db_session):
    user = create_user("test@example.com")
    db_session.flush()
    assert db_session.get(User, user.id) is not None
```

### 5. Testing Implementation Details

```python
# ❌ Antipattern: Test internal structure
def test_filter_options_is_list():
    filter = MyFilter()
    assert isinstance(filter.options, list)
    assert filter._internal_cache == {}

# ✅ Better: Test observable behavior
def test_filter_returns_active_options():
    filter = MyFilter()
    filter.options = ["A", "B", "C"]
    state = {"0": True, "1": False, "2": True}
    assert filter.active_options(state) == ["A", "C"]
```

---

## Test Organization

### Directory Structure

```
tests/
├── a_unit/           # Unit tests (no database, fast)
│   └── modules/
│       ├── common/
│       ├── kyc/
│       └── wip/
├── b_integration/    # Integration tests (with database)
│   ├── admin/
│   └── modules/
├── c_e2e/           # End-to-end tests (full stack)
└── conftest.py      # Shared fixtures
```

### Naming Conventions

- Test files: `test_<module_name>.py`
- Test classes: `Test<ClassName>` or `Test<FunctionName>`
- Test methods: `test_<behavior_description>`

```python
class TestFilterByCity:
    def test_selector_returns_city(self):
        ...

    def test_apply_with_no_active_options(self):
        ...
```

---

## What to Test

### High Value Tests

1. **Business logic functions** - Core algorithms and calculations
2. **Data transformations** - ViewModels, adapters, serializers
3. **Validation logic** - Form validators, input sanitization
4. **State transitions** - Publish/unpublish, activate/deactivate
5. **Edge cases** - Empty inputs, missing data, boundary conditions

### Lower Value Tests (but still useful)

1. **Constants and configuration** - Catch typos, ensure consistency
2. **Class attributes** - Verify correct wiring (model_class, repo_class)
3. **Simple property accessors** - Document expected behavior

```python
# Simple but useful: ensures configuration is correct
def test_events_table_id():
    table = EventsTable()
    assert table.id == "events-table"

def test_view_has_model_class():
    assert EventsWipView.model_class == Event
```

---

## Fixtures

### Use Fixtures for Common Setup

```python
@pytest.fixture
def user_with_profile(db_session: Session) -> User:
    """Create a user with a complete profile."""
    user = User(email="test@example.com", first_name="Test", last_name="User")
    profile = KYCProfile(contact_type="PRESSE")
    user.profile = profile
    db_session.add(user)
    db_session.flush()
    return user
```

### Fixture Composition

Build complex fixtures from simple ones:

```python
@pytest.fixture
def organisation(db_session: Session) -> Organisation:
    org = Organisation(name="Test Org", type=OrganisationTypeEnum.MEDIA)
    db_session.add(org)
    db_session.flush()
    return org

@pytest.fixture
def user_with_org(db_session: Session, organisation: Organisation) -> User:
    user = User(email="member@example.com", organisation_id=organisation.id)
    db_session.add(user)
    db_session.flush()
    return user
```

---

## Testing Flask Views

### Use Request Context

```python
def test_view_model_in_context(app, db_session, test_data):
    with app.test_request_context():
        from flask import g
        g.user = test_user  # Set up request context

        vm = MyViewModel(test_data)
        assert vm.some_property == expected_value
```

### Test View Methods Directly (when possible)

```python
def test_view_get_method(app, db_session, test_org):
    with app.test_request_context():
        g.user = admin_user

        view = ShowOrgView()
        response = view.get(str(test_org.id))

        assert response is not None
```

---

## Running Tests

```bash
# Run all tests
make test

# Run specific test file
uv run pytest tests/a_unit/modules/common/test_post_card.py -v

# Run with coverage
uv run pytest --cov=app --cov-report=html

# Run only unit tests (fast)
uv run pytest tests/a_unit/ -v

# Run failing tests first
uv run pytest --failed-first
```

---

## Summary

1. **Keep commits at the view layer** - Use `flush()` in helpers
2. **Test state, not interactions** - Prefer stubs over mocks
3. **Extract pure functions** - Make logic testable in isolation
4. **Test ViewModels separately** - Don't need full HTTP request
5. **Use real database objects** - Test fixtures with actual models
6. **Imports at top-level** - Avoid inline imports in test methods
7. **Focus on behavior** - Test what code does, not how it does it
