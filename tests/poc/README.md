# POC Models Tests

This directory contains tests for the POC blueprint models.

## Test Structure

```
tests/poc/
├── __init__.py
├── conftest.py            # Test fixtures
├── README.md             # This file
└── models/
    ├── __init__.py
    ├── test_business_wall.py
    ├── test_subscription.py
    ├── test_role.py
    ├── test_partnership.py
    └── test_content.py
```

## Models Tested

- **BusinessWall**: Core Business Wall entity with 8 types and lifecycle management
- **Subscription**: Pricing and payment tracking for paid Business Walls
- **RoleAssignment & RolePermission**: RBAC system with 5 roles and 7 permission types
- **Partnership**: PR Agency relationship management
- **BWContent**: Content configuration with File Object Storage for images

## Testing Approach

### Unit Tests

All model tests are designed as unit tests focusing on:
- Model creation and validation
- Enum value handling
- Relationship integrity
- Repository CRUD operations
- JSON field handling (topics, member_ids, etc.)
- File Object Storage integration

### Test Coverage

- **BusinessWall**: 11 tests covering creation, types, status transitions, relationships
- **Subscription**: 10 tests covering pricing tiers, lifecycle, Stripe integration
- **RoleAssignment/Permission**: 15 tests covering RBAC, invitations, permissions
- **Partnership**: 9 tests covering workflow, contract terms, relationships
- **BWContent**: 13 tests covering all fields, File Object Storage, ontology

Total: **58 comprehensive model tests**

## Known Limitations

### Cross-Metadata Foreign Key Constraints

**Issue**: The POC models use Advanced-Alchemy's `UUIDAuditBase` which has its own SQLAlchemy metadata, separate from the main app's `Base` metadata. This causes SQLAlchemy to be unable to resolve foreign key references to tables in the main app (like `aut_user` and `crp_organisation`) during table creation.

**Error**:
```
sqlalchemy.exc.NoReferencedTableError: Foreign key associated with column
'poc_business_wall.owner_id' could not find table 'aut_user' with which to
generate a foreign key to target column 'id'
```

**Solutions Attempted**:
1. ✗ `use_alter=True` on ForeignKey - still tries to resolve during CREATE TABLE
2. ✗ Creating POC tables after main app tables - metadata is separate
3. ✗ `checkfirst=True` - doesn't help with foreign key resolution

**Recommended Solutions** (for future implementation):

1. **Remove FK Constraints for Testing** (Quick fix):
   - Remove ForeignKey() declarations, keep integer columns
   - Relationships will still work through integer IDs
   - Foreign key integrity enforced at application level

2. **Merge Metadata** (Proper fix):
   - Have POC models inherit from main app's Base instead of UUIDAuditBase
   - Use mixins from Advanced-Alchemy without separate metadata
   - Allows SQLAlchemy to see all tables in one metadata

3. **Integration Testing Approach** (Alternative):
   - Skip FK constraint validation in unit tests
   - Focus on integration tests with full database
   - Test relationships through actual database operations

## Running Tests (When Fixed)

```bash
# Run all POC model tests
uv run pytest tests/poc/models/ -v

# Run specific model tests
uv run pytest tests/poc/models/test_business_wall.py -v

# Run with coverage
uv run pytest tests/poc/models/ --cov=poc.blueprints.bw_activation_full.models
```

## Test Fixtures

### Session-Level Fixtures

- `app`: Flask application with test configuration
- `db`: Database with all tables created
- `_create_poc_tables`: Creates POC model tables (autouse)

### Function-Level Fixtures

- `db_session`: Transactional session with automatic rollback
- `user`: Test user (owner)
- `payer`: Test payer user
- `business_wall`: Free BusinessWall instance
- `paid_business_wall`: Paid BusinessWall instance

## Example Test

```python
def test_create_business_wall(db_session: Session, user: User):
    """Test creating a BusinessWall."""
    bw = BusinessWall(
        bw_type=BWType.MEDIA.value,
        status=BWStatus.DRAFT.value,
        is_free=True,
        owner_id=user.id,
        payer_id=user.id,
    )
    db_session.add(bw)
    db_session.commit()

    assert bw.id is not None
    assert bw.bw_type == "media"
    assert bw.owner_id == user.id
```

## Future Improvements

1. **Fix Foreign Key Constraints**: Implement one of the recommended solutions
2. **Add Factory Classes**: Use factory_boy for test data generation
3. **Property-Based Testing**: Add Hypothesis tests for edge cases
4. **Performance Tests**: Test repository queries with large datasets
5. **File Storage Tests**: Add integration tests with actual file operations
6. **Service Layer Tests**: Test business logic in service classes

## Contributing

When adding new models or modifying existing ones:

1. Add corresponding tests in `tests/poc/models/`
2. Follow existing test patterns
3. Test all enum values
4. Test relationships in both directions
5. Test repository CRUD operations
6. Include docstrings for test methods

## References

- Main app tests: `tests/a_unit/models/`
- Advanced-Alchemy docs: `notes/3rd-party/advanced-alchemy.md`
- Model documentation: `src/poc/blueprints/bw_activation_full/models/README.md`
