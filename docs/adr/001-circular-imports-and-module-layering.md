# ADR 001: Resolving Circular Imports Through Improved Module Layering

## Status

Superseded by ADR 002

The immediate circular import issues were resolved by implementing the navigation refactoring
described in ADR 002. The architectural recommendations in this ADR remain valid for future
consideration.

## Context

The aipress24 application uses a modular architecture organized by bounded contexts (swork, wire, events, biz, etc.). Each module contains its own models, views, services, and templates. This is essentially a vertical slice architecture.

However, the implementation has developed circular import issues between modules, particularly:

```
social_graph -> activity_stream -> swork.models -> swork (imports views)
    -> swork.views.organisation -> wire.models -> wire (imports views)
    -> wire.views.item -> social_graph
```

The immediate cause was eager view imports in module `__init__.py` files (`from . import views`), which triggered the full import chain at module load time.

### Current Architecture Analysis

The current structure follows this pattern:

```
src/app/
├── modules/                    # Bounded contexts (vertical slices)
│   ├── swork/                  # Social workspace
│   │   ├── __init__.py         # Blueprint + eager view import
│   │   ├── models/             # Domain models
│   │   ├── views/              # Flask views
│   │   └── templates/          # Jinja templates
│   ├── wire/                   # News/articles
│   ├── events/                 # Events management
│   └── ...
├── services/                   # Cross-cutting services
│   ├── social_graph/           # Follow/follower relationships
│   ├── activity_stream/        # Activity feed
│   └── ...
└── models/                     # Shared domain models (User, Organisation)
```

**Strengths:**
- Clear separation by business domain
- Each module is relatively self-contained
- Follows bounded context principles from DDD

**Weaknesses:**
- No clear layering within modules
- Cross-module dependencies create import cycles
- Services depend on models from multiple modules
- Views directly use models and services without abstraction

### Quick Fix Applied

A quick fix was implemented:
1. **Fix D**: Made `activity_stream` service use string-based type checking instead of importing `Group` model
2. **Fix E**: Deferred view imports in module `__init__.py` via `register_views()` function

This resolved the immediate circular import issue but doesn't address the underlying architectural tension.

## Decision

We need to choose an architectural approach for long-term maintainability. Below are the options considered:

### Option A: Strict Horizontal Layering

Organize the codebase into horizontal layers that enforce a strict dependency direction:

```
src/app/
├── domain/                     # Core business logic (no framework deps)
│   ├── models/                 # All domain models
│   ├── services/               # Domain services (pure functions)
│   └── events.py               # Domain events definitions
├── infrastructure/             # Framework integrations
│   ├── persistence/            # SQLAlchemy implementations
│   ├── messaging/              # Activity stream, notifications
│   └── external/               # External APIs
├── application/                # Use cases / orchestration
│   ├── swork/                  # Social workspace use cases
│   ├── wire/                   # News use cases
│   └── ...
└── presentation/               # Flask views, templates
    ├── swork/
    ├── wire/
    └── ...
```

**Pros:**
- Clear dependency direction (presentation -> application -> domain <- infrastructure)
- Easy to enforce with import linting
- Well-understood pattern

**Cons:**
- Major refactoring effort
- Loses the vertical slice cohesion
- Related code spread across directories
- May feel unnatural for Flask applications

### Option B: Event-Driven Decoupling with Signals

Keep the vertical slice structure but decouple modules using events/signals:

```python
# In app/events.py (shared)
from blinker import signal

user_followed = signal("user-followed")
group_joined = signal("group-joined")
article_published = signal("article-published")

# In swork/views/member.py
from app.events import user_followed

def follow_user(target):
    # ... perform follow ...
    user_followed.send(actor=g.user, target=target)

# In services/activity_stream/_service.py
from app.events import user_followed

@user_followed.connect
def on_user_followed(sender, actor, target):
    post_activity(ActivityType.Follow, actor, target)
```

**Pros:**
- Minimal structural changes
- Decouples modules via event contracts
- Modules don't need to know about each other's internals
- Easy to add new reactions without modifying source

**Cons:**
- Implicit control flow (harder to trace)
- Signal handlers can have ordering issues
- Testing requires careful setup of signal handlers
- Can lead to "spooky action at a distance"

### Option C: Clean Architecture Within Bounded Contexts

Maintain vertical slices but introduce clean architecture layers within each module:

```
src/app/
├── modules/
│   ├── swork/
│   │   ├── domain/             # Pure business logic
│   │   │   ├── models.py       # Domain models (may extend shared)
│   │   │   └── services.py     # Domain services
│   │   ├── application/        # Use cases
│   │   │   └── use_cases.py
│   │   ├── infrastructure/     # Ports & adapters
│   │   │   └── repositories.py
│   │   └── presentation/       # Views
│   │       └── views.py
│   └── wire/
│       └── ...
├── shared/                     # Shared kernel
│   ├── domain/                 # Shared domain concepts
│   │   ├── models.py           # User, Organisation
│   │   └── ports.py            # Interfaces (protocols)
│   └── infrastructure/         # Shared infrastructure
└── services/                   # Cross-cutting concerns
    └── ...
```

**Pros:**
- Preserves vertical slice cohesion
- Clear layering within each bounded context
- Explicit shared kernel for cross-module concepts
- Protocols define contracts between layers

**Cons:**
- More complex directory structure
- Requires discipline to maintain layer boundaries
- May feel over-engineered for smaller modules
- Need clear rules for what goes in shared kernel

### Option D: Minimal Fix with Import Discipline

Keep current structure with enhanced import rules:

1. **Models layer first**: Models can only import from `app.models` (shared) and their own module
2. **Services in between**: Services can import models but not views
3. **Views last**: Views can import anything

Enforce with import linting rules in `pyproject.toml`:
```toml
[tool.ruff.lint.isort]
known-first-party = ["app"]

# Add custom import linting rules
```

**Pros:**
- Minimal changes to current structure
- Quick to implement
- Easy to understand rules

**Cons:**
- Doesn't solve fundamental coupling issues
- Rules may be hard to enforce consistently
- Still allows tight coupling between modules

## Comparison Matrix

| Criterion                  | A: Horizontal | B: Events | C: Vertical+Layers | D: Discipline |
|---------------------------|---------------|-----------|-------------------|---------------|
| Refactoring effort        | High          | Low       | Medium            | Low           |
| Import cycle prevention   | Excellent     | Good      | Good              | Moderate      |
| Code cohesion             | Low           | High      | High              | High          |
| Testability               | Excellent     | Good      | Excellent         | Moderate      |
| Learning curve            | Medium        | Low       | Medium            | Low           |
| Flexibility               | Low           | High      | Medium            | High          |
| Maintainability           | Good          | Moderate  | Good              | Moderate      |

## Recommendation

We recommend **Option C (Clean Architecture Within Bounded Contexts)** with elements of Option B for specific cross-module communication needs.

**Rationale:**
1. Preserves the existing vertical slice structure that maps well to the business domains
2. Introduces clear boundaries within each module without major restructuring
3. Uses protocols/interfaces for cross-module dependencies
4. Events can be used selectively for truly decoupled operations (activity logging, notifications)

**Implementation Phases:**
1. Define shared kernel with User, Organisation, and common protocols
2. Refactor one module (e.g., swork) as a pilot
3. Extract services that cross module boundaries into shared services
4. Gradually apply pattern to other modules

## Consequences

**Positive:**
- Clearer dependency direction within and between modules
- Easier to test individual layers
- Better separation of concerns
- Prevents circular import issues by design

**Negative:**
- More files and directories
- Need to maintain protocol definitions
- Some duplication of model references
- Learning curve for team members

## References

- [Clean Architecture by Robert C. Martin](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html)
- [Vertical Slice Architecture by Jimmy Bogard](https://www.jimmybogard.com/vertical-slice-architecture/)
- [Domain-Driven Design by Eric Evans](https://www.domainlanguage.com/ddd/)
- [Cosmic Python - Architecture Patterns with Python](https://www.cosmicpython.com/)
