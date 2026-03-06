# N+1 Query Detector

The N+1 query detector identifies potential N+1 query issues by tracking SQL queries during requests and detecting patterns where similar queries are executed multiple times.

**Location:** `src/app/flask/lib/n_plus_one_detector.py`

## Quick Start

The detector is already initialized in the application. It runs automatically in debug mode.

To check logs for N+1 warnings:
```bash
# Look for warnings in server output
make run 2>&1 | grep "N+1"
```

## How It Works

1. **Request Start**: Creates a `QueryTracker` for the request
2. **Query Execution**: Hooks into SQLAlchemy's `before_cursor_execute` event
3. **Normalization**: Replaces literal values with placeholders to group similar queries
4. **Request End**: Checks if any query pattern exceeds the threshold

### Query Normalization

The detector normalizes queries to identify patterns:

```python
# These queries are grouped together:
"SELECT * FROM users WHERE id = 1"
"SELECT * FROM users WHERE id = 2"
"SELECT * FROM users WHERE id = 3"

# Normalized to:
"SELECT * FROM users WHERE id = ?"
```

Normalization handles:
- Numeric literals → `?`
- String literals → `?`
- UUIDs → `?`
- IN clauses → `IN (...)`

## Configuration

Set in Flask config or environment:

```python
# Enable/disable explicitly (None = follow debug mode)
N_PLUS_ONE_ENABLED = True  # or False, or None

# Minimum repeated queries to trigger warning (default: 3)
N_PLUS_ONE_THRESHOLD = 3

# Log level for alerts (default: "WARNING")
N_PLUS_ONE_LOG_LEVEL = "WARNING"  # or "ERROR", "INFO", "DEBUG"

# Raise exception instead of logging (default: False)
N_PLUS_ONE_RAISE = False
```

### Enable in Production (for testing)

```python
# In config or .env
N_PLUS_ONE_ENABLED=true
N_PLUS_ONE_THRESHOLD=5  # Higher threshold for production
```

### Enable in Tests

```python
# In conftest.py or test file
@pytest.fixture
def app_with_n_plus_one(app):
    app.config["N_PLUS_ONE_ENABLED"] = True
    app.config["N_PLUS_ONE_RAISE"] = True  # Fail test on N+1
    return app
```

## Example Output

```
WARNING - Potential N+1 query detected! 2 pattern(s) found:

  [15x] SELECT user.id, user.name FROM user WHERE user.id = ?
       params: (1,)
       params: (2,)
       params: (3,)
  [10x] SELECT org.id, org.name FROM organisation WHERE organisation.id = ?
       params: (42,)
       params: (43,)

Total queries this request: 28
```

## Common N+1 Patterns and Fixes

### Pattern 1: Accessing Related Objects in Loop

**Problem:**
```python
users = db.session.scalars(select(User).limit(10))
for user in users:
    print(user.organisation.name)  # N+1: loads organisation for each user
```

**Solution: Use `selectinload`**
```python
from sqlalchemy.orm import selectinload

users = db.session.scalars(
    select(User)
    .options(selectinload(User.organisation))
    .limit(10)
)
for user in users:
    print(user.organisation.name)  # Already loaded
```

### Pattern 2: Accessing Collection in Loop

**Problem:**
```python
orgs = db.session.scalars(select(Organisation))
for org in orgs:
    print(len(org.members))  # N+1: loads members for each org
```

**Solution: Use `selectinload` or `subqueryload`**
```python
orgs = db.session.scalars(
    select(Organisation)
    .options(selectinload(Organisation.members))
)
```

### Pattern 3: Nested Relationships

**Problem:**
```python
posts = db.session.scalars(select(Post))
for post in posts:
    print(post.author.organisation.name)  # Double N+1
```

**Solution: Chain eager loading**
```python
posts = db.session.scalars(
    select(Post)
    .options(
        selectinload(Post.author)
        .selectinload(User.organisation)
    )
)
```

### Pattern 4: ViewModel/Template Access

**Problem:**
```jinja
{% for user in users %}
  {{ user.organisation.name }}  {# N+1 if not eager loaded #}
{% endfor %}
```

**Solution: Eager load in view/component**
```python
def get_users():
    return db.session.scalars(
        select(User)
        .options(selectinload(User.organisation))
    )
```

## Choosing Eager Loading Strategy

| Strategy | Use When | SQL Pattern |
|----------|----------|-------------|
| `selectinload` | Loading collections, many related objects | SELECT ... WHERE id IN (...) |
| `joinedload` | Loading single related object, small result sets | LEFT JOIN |
| `subqueryload` | Large collections, complex queries | Subquery |

**Default recommendation:** Use `selectinload` for most cases.

## Utility Functions

### Get Query Count in Request

```python
from app.flask.lib.n_plus_one_detector import get_query_count

@app.after_request
def log_query_count(response):
    count = get_query_count()
    if count > 20:
        logger.info(f"High query count: {count}")
    return response
```

### Get Query Statistics

```python
from app.flask.lib.n_plus_one_detector import get_query_stats

stats = get_query_stats()
# Returns:
# {
#     "total": 15,
#     "patterns": 8,
#     "potential_n_plus_one": [("SELECT * FROM users WHERE id = ?", 5)]
# }
```

## Integration in Tests

### Command-Line Options

Run tests with N+1 detection enabled:

```bash
# Log warnings when N+1 patterns detected
pytest --n-plus-one

# Fail tests that trigger N+1 patterns
pytest --n-plus-one-strict

# Combine with other options
pytest tests/b_integration/ --n-plus-one-strict -x
```

### Using the `assert_no_n_plus_one` Fixture

The `assert_no_n_plus_one` fixture is available for testing specific endpoints:

```python
def test_list_users_no_n_plus_one(client, assert_no_n_plus_one):
    # Create test data
    # ...

    response = client.get("/users")
    assert response.status_code == 200

    # Assert no N+1 patterns were detected
    assert_no_n_plus_one()
```

### Manual N+1 Checking in Tests

```python
from app.flask.lib.n_plus_one_detector import get_query_stats

def test_list_users_query_efficiency(client, db_session):
    # Create test data
    for i in range(10):
        user = User(email=f"user{i}@test.com")
        db_session.add(user)
    db_session.flush()

    response = client.get("/users")

    stats = get_query_stats()
    n_plus_one = stats["potential_n_plus_one"]
    assert len(n_plus_one) == 0, f"N+1 detected: {n_plus_one}"
```

### CI Integration

Add to your CI workflow to catch N+1 regressions:

```yaml
# In .github/workflows/tests.yml
- name: Run integration tests with N+1 detection
  run: pytest tests/b_integration/ --n-plus-one
```

For strict enforcement on specific test suites:

```yaml
- name: Run performance-critical tests
  run: pytest tests/b_integration/test_api.py --n-plus-one-strict
```

## Excluded Queries

The detector automatically skips:
- `PRAGMA` statements (SQLite)
- `SAVEPOINT` / `RELEASE` / `ROLLBACK TO` (transaction management)

## Troubleshooting

### Detector not reporting anything

1. Check if debug mode is enabled: `app.debug == True`
2. Or explicitly enable: `N_PLUS_ONE_ENABLED=true`
3. Check threshold: default is 3 repeated queries

### False positives

Some patterns are intentional (e.g., batch processing). Options:
- Increase `N_PLUS_ONE_THRESHOLD`
- Disable for specific endpoints
- Review if the pattern is actually a problem

### Performance impact

The detector adds minimal overhead:
- Only active in debug mode by default
- Uses efficient pattern matching
- No query modification

Disable in production unless actively debugging:
```python
N_PLUS_ONE_ENABLED = False  # Explicit disable
```
