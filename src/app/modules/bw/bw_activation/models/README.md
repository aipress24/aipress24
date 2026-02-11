# Business Wall Models

SQLAlchemy ORM models for the Business Wall activation system, using Advanced-Alchemy for UUID-based IDs, audit trails, and repository pattern.

## Overview

This package contains all data models for the 7-stage Business Wall activation workflow:

1. **Stage 1-2**: Subscription confirmation and contact nomination
2. **Stage 3**: Activation (free or paid)
3. **Stage 4**: Internal roles management
4. **Stage 5**: External PR agency partnerships
5. **Stage 6**: Permission/mission assignments
6. **Stage 7**: Content configuration

## Models

### BusinessWall

Core entity representing a Business Wall instance.

**Key fields:**
- `bw_type`: One of 8 types (media, micro, corporate_media, union, academics, pr, leaders_experts, transformers)
- `status`: draft, active, suspended, cancelled
- `is_free`: Boolean indicating free vs paid tier
- `owner_id`, `payer_id`: References to User model
- `activated_at`: Timestamp of activation

**Relationships:**
- `subscription`: One-to-one with Subscription (for paid BWs)
- `content`: One-to-one with BWContent
- `role_assignments`: One-to-many with RoleAssignment
- `partnerships`: One-to-many with Partnership

### Subscription

Payment and subscription tracking for paid Business Walls.

**Key fields:**
- `pricing_field`: "client_count" or "employee_count"
- `pricing_tier`: "1-10", "11-50", "51-200", "201+"
- `monthly_price`, `annual_price`: Decimal pricing
- `billing_cycle`: "monthly" or "annual"
- `stripe_*`: Stripe integration fields
- `billing_*`: Billing address fields

**Status values:**
- pending, active, past_due, cancelled, expired

### RoleAssignment

RBAC system for Business Wall access control.

**Role types:**
- `BW_OWNER`: Business Wall Owner
- `BWMi`: Business Wall Manager (internal)
- `BWPRi`: PR Manager (internal)
- `BWMe`: Business Wall Manager (external)
- `BWPRe`: PR Manager (external)

**Invitation workflow:**
- `invitation_status`: pending, accepted, rejected, expired
- `invited_at`, `accepted_at`, `rejected_at`: Timestamps

**Relationships:**
- `permissions`: One-to-many with RolePermission

### RolePermission

Granular permissions for PR Manager roles (Stage 6 missions).

**Permission types:**
- `press_release`: Manage press releases
- `events`: Manage events
- `missions`: Manage missions
- `profiles`: Manage profiles
- `media_contacts`: Manage media contacts
- `stats_kpi`: View statistics and KPIs
- `messages`: Manage messages

**Key fields:**
- `permission_type`: One of the above types
- `is_granted`: Boolean grant status

### Partnership

PR Agency partnership relationships (Stage 5).

**Key fields:**
- `partner_org_id`: Reference to Organisation
- `status`: invited, accepted, rejected, active, revoked, expired
- `invited_by_user_id`: User who sent invitation
- `invitation_message`: Custom message
- `contract_start_date`, `contract_end_date`: Optional contract terms

### BWContent

Content and configuration for Business Wall (Stage 7).

**Visual content** (using Advanced-Alchemy File Object Storage):
- `logo`: FileObject for logo image
- `banner`: FileObject for banner image
- `gallery`: FileObjectList for image gallery
- `description`, `baseline`: Text content

**Administrative data:**
- `official_name`, `organization_type`
- `siren`, `tva_number`, `cppap`: French business identifiers

**Contact information:**
- `website`, `email`, `phone`
- `address`, `city`, `zip_code`, `country`
- `twitter_url`, `linkedin_url`, `facebook_url`

**Ontology selections** (JSON arrays):
- `topics`: Selected centres d'intérêt
- `geographic_zones`: Geographic coverage
- `sectors`: Industry sectors

**Member and client lists** (JSON arrays):
- `member_ids`: User IDs for member lists
- `client_list`: Client names or IDs (for PR type)

## Architecture

### Base Classes

All models inherit from `UUIDAuditBase` which provides:
- `id`: UUID primary key (using Advanced-Alchemy's GUID type)
- `created_at`: Creation timestamp (DateTimeUTC)
- `updated_at`: Last update timestamp (DateTimeUTC)

### Repository Pattern

Each model has a corresponding repository class extending `SQLAlchemySyncRepository`:

```python
from poc.blueprints.bw_activation.models import (
    BusinessWall,
    BusinessWallRepository,
)

# Usage (in Flask context with db session)
repo = BusinessWallRepository(session=db.session)

# CRUD operations
bw = repo.get(id=some_uuid)
bw = repo.add(BusinessWall(bw_type="media", ...))
bw = repo.update(bw, data={"status": "active"})
repo.delete(bw)

# Query operations
bws = repo.list()
bws = repo.list(status="active")
```

### Service Layer

Service classes extend `SQLAlchemySyncRepositoryService` with `FlaskServiceMixin`:

```python
from poc.blueprints.bw_activation.models import BusinessWallService

# Usage (services auto-wire with Flask app)
service = BusinessWallService()

# High-level operations
bw = service.create({"bw_type": "media", "owner_id": user.id, ...})
bw = service.get(id=some_uuid)
bws = service.list()
service.update(bw, {"status": "active"})
service.delete(bw.id)
```

## Usage Examples

### Creating a Business Wall

```python
from poc.blueprints.bw_activation.models import (
    BusinessWall,
    BusinessWallService,
)

service = BusinessWallService()

# Create free BW
bw = service.create({
    "bw_type": "media",
    "status": "draft",
    "is_free": True,
    "owner_id": user.id,
    "payer_id": user.id,
})

# Create paid BW with subscription
bw = service.create({
    "bw_type": "pr",
    "status": "draft",
    "is_free": False,
    "owner_id": owner.id,
    "payer_id": payer.id,
})

# Add subscription
from poc.blueprints.bw_activation.models import SubscriptionService

sub_service = SubscriptionService()
subscription = sub_service.create({
    "business_wall_id": bw.id,
    "pricing_field": "client_count",
    "pricing_tier": "11-50",
    "monthly_price": 299.00,
    "annual_price": 2990.00,
    "billing_cycle": "monthly",
})
```

### Assigning Roles and Permissions

```python
from poc.blueprints.bw_activation.models import (
    RoleAssignmentService,
    RolePermissionService,
)

# Assign PR Manager role
role_service = RoleAssignmentService()
role = role_service.create({
    "business_wall_id": bw.id,
    "user_id": manager.id,
    "role_type": "BWPRi",
    "invitation_status": "accepted",
})

# Grant specific permissions
perm_service = RolePermissionService()
for perm_type in ["press_release", "events", "missions"]:
    perm_service.create({
        "role_assignment_id": role.id,
        "permission_type": perm_type,
        "is_granted": True,
    })
```

### Managing PR Agency Partnerships

```python
from poc.blueprints.bw_activation.models import PartnershipService

partnership_service = PartnershipService()

# Invite PR agency
partnership = partnership_service.create({
    "business_wall_id": bw.id,
    "partner_org_id": agency.id,
    "invited_by_user_id": current_user.id,
    "invitation_message": "We'd like to work with you...",
    "status": "invited",
})

# Accept partnership
partnership_service.update(partnership, {
    "status": "accepted",
    "accepted_at": datetime.utcnow(),
})
```

### Configuring Content

```python
from poc.blueprints.bw_activation.models import BWContentService
from advanced_alchemy.types.file_object import FileObject

content_service = BWContentService()

# Create logo and banner FileObjects
logo = FileObject(
    backend="local",
    filename="logo.png",
    content=logo_bytes,
    metadata={"alt": "Company Logo"},
)

banner = FileObject(
    backend="local",
    filename="banner.jpg",
    content=banner_bytes,
    metadata={"alt": "Company Banner"},
)

# Create gallery images
gallery = [
    FileObject(backend="local", filename=f"gallery_{i}.jpg", content=img_bytes)
    for i, img_bytes in enumerate(gallery_images)
]

content = content_service.create({
    "business_wall_id": bw.id,
    "official_name": "My Organization",
    "organization_type": "Entreprise",
    "logo": logo,
    "banner": banner,
    "gallery": gallery,
    "description": "We are a leading media company...",
    "website": "https://example.com",
    "email": "contact@example.com",
    "topics": ["technology", "business", "innovation"],
    "geographic_zones": ["france", "europe"],
})
```

## Enums

All enum types are defined as `str` enums for easy JSON serialization:

```python
from poc.blueprints.bw_activation.models.business_wall import BWType, BWStatus
from poc.blueprints.bw_activation.models.role import BWRoleType, PermissionType

# Usage
bw_type = BWType.MEDIA.value  # "media"
status = BWStatus.ACTIVE.value  # "active"
role = BWRoleType.BWPRI.value  # "BWPRi"
perm = PermissionType.PRESS_RELEASE.value  # "press_release"
```

## Database Integration

### Creating Tables

These models are NOT automatically integrated with the main app's database. They are designed for the POC blueprint.

To create tables in a POC database:

```python
from advanced_alchemy.base import UUIDAuditBase
from sqlalchemy import create_engine

engine = create_engine("postgresql://localhost/poc_db")
UUIDAuditBase.metadata.create_all(engine)
```

### Migration Notes

When ready to integrate with the main application:

1. Add models to main app's models directory
2. Create Alembic migrations
3. Update foreign key references
4. Register services with Flask app's dependency injection (SVCS)

## Advanced-Alchemy Features Used

- **UUIDAuditBase**: UUID primary keys with audit timestamps
- **GUID Type**: PostgreSQL-optimized UUID storage
- **JsonB Type**: Efficient JSON storage for lists and dicts
- **Repository Pattern**: CRUD operations with query builders
- **Service Layer**: Business logic with Flask integration
- **FlaskServiceMixin**: Auto-wiring with Flask app context

## Type Safety

All models use SQLAlchemy 2.0 `Mapped` type hints for type safety:

```python
from sqlalchemy.orm import Mapped, mapped_column

class BusinessWall(UUIDAuditBase):
    bw_type: Mapped[str] = mapped_column(String(50), nullable=False)
    is_free: Mapped[bool] = mapped_column(default=False)
    owner_id: Mapped[int] = mapped_column(ForeignKey("aut_user.id"))
    activated_at: Mapped[datetime | None] = mapped_column(nullable=True)
```

This enables IDE autocomplete and type checking with Pyright/MyPy.

## Testing

Models are designed to be testable with factories:

```python
import pytest
from poc.blueprints.bw_activation.models import BusinessWall

@pytest.fixture
def business_wall(db_session):
    bw = BusinessWall(
        bw_type="media",
        status="active",
        is_free=True,
        owner_id=1,
        payer_id=1,
    )
    db_session.add(bw)
    db_session.commit()
    return bw

def test_business_wall_creation(business_wall):
    assert business_wall.bw_type == "media"
    assert business_wall.is_free is True
```

## File Object Storage

The BWContent model uses Advanced-Alchemy's File Object Storage for managing uploaded files (logos, banners, gallery images).

### Features

**Automatic File Management:**
- Files are automatically saved when model is committed
- Old files are automatically deleted when updated
- All files are deleted when model is deleted

**Multiple Storage Backends:**
- Local filesystem (default: "local")
- S3-compatible storage
- Any fsspec-supported backend

**File Metadata:**
- Each FileObject can store custom metadata
- Useful for alt text, tags, categories, etc.

**Signed URLs:**
- Generate temporary signed URLs for secure file access
- Configure expiration time

### Usage Example

```python
from advanced_alchemy.types.file_object import FileObject

# Create a BWContent with files
logo = FileObject(
    backend="local",
    filename="logo.png",
    content=logo_bytes,
    metadata={"alt": "Company Logo", "width": 200, "height": 100},
)

content.logo = logo
session.commit()  # File is automatically saved

# Get file content
logo_content = await content.logo.get_content_async()

# Get signed URL (if backend supports it)
url = await content.logo.sign_async(expires_in=3600)  # 1 hour

# Update file (old file is automatically deleted)
content.logo = FileObject(
    backend="local",
    filename="new_logo.png",
    content=new_logo_bytes,
)
session.commit()

# Remove file (file is automatically deleted from storage)
content.logo = None
session.commit()
```

### Storage Backend Configuration

For production, configure storage backends in your Flask app initialization:

```python
from advanced_alchemy.types.file_object import storages
from advanced_alchemy.types.file_object.backends.fsspec import FSSpecBackend
import fsspec

# Local storage for development
storages.register_backend(
    FSSpecBackend(fs=fsspec.filesystem("file"), key="local")
)

# S3 storage for production
s3_fs = fsspec.S3FileSystem(
    key="your-access-key",
    secret="your-secret-key",
    endpoint_url="https://s3.amazonaws.com",
)
storages.register_backend(
    FSSpecBackend(fs=s3_fs, key="s3", prefix="your-bucket/uploads")
)
```

## Future Enhancements

Potential improvements:

1. **Validation**: Add Pydantic schemas for input validation
2. **Events**: Add SQLAlchemy event listeners for lifecycle hooks
3. **Versioning**: Add version tracking for content changes
4. **Soft Deletes**: Track deleted entities
5. **Full-text Search**: Integrate with Typesense for content search
6. **Caching**: Add Redis caching layer via repositories
7. **Async Support**: Add async repository/service variants
8. **Image Processing**: Add automatic thumbnail generation and image optimization
9. **CDN Integration**: Integrate with CDN for file delivery

## References

- [Advanced-Alchemy Documentation](https://docs.advanced-alchemy.litestar.dev/)
- [SQLAlchemy 2.0 Documentation](https://docs.sqlalchemy.org/en/20/)
- Main app models: `src/app/models/`
- Advanced-Alchemy notes: `notes/3rd-party/advanced-alchemy.md`
