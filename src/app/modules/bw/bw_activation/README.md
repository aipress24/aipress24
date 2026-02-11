# Business Wall Activation Full - Package Structure

This package implements the complete Business Wall activation workflow with a clean, modular architecture.

## Architecture Overview

The blueprint uses a package structure with routes organized by numbered stages for clarity and maintainability.

```
bw_activation/
├── __init__.py          # Blueprint creation and routes import
├── config.py            # Business Wall types configuration
├── utils.py             # Helper functions and session management
├── README.md            # This file
└── routes/              # Route handlers organized by workflow stage
    ├── __init__.py      # Imports all route modules
    ├── stage1.py        # Stage 1: Subscription confirmation
    ├── stage2.py        # Stage 2: Contact nomination
    ├── stage3.py        # Stage 3: Activation (free/paid)
    ├── stage4.py        # Stage 4: Internal roles
    ├── stage5.py        # Stage 5: External partners
    ├── stage6.py        # Stage 6: Missions/permissions
    ├── stage7.py        # Stage 7: Content configuration
    └── dashboard.py     # Dashboard and reset utilities
```

## Module Responsibilities

### `config.py`
Contains the `BW_TYPES` dictionary with configuration for all 8 Business Wall types:
- 5 free types: Media, Micro, Corporate Media, Union, Academics
- 3 paid types: PR, Leaders & Experts, Transformers

Each type includes:
- Name and description
- Pricing information (for paid types)
- Onboarding messages
- Manager role type
- Activation text

### `utils.py`
Utility functions used across the workflow:
- `init_session()` - Initialize session variables
- `get_mock_owner_data()` - Provide mock user data for forms
- `init_missions_state()` - Initialize permissions state

### `routes/` Package

Each route module focuses on a specific workflow stage and imports the blueprint directly:

```python
from .. import bp

@bp.route("/endpoint")
def handler():
    # Route logic
    pass
```

This pattern:
- Avoids circular imports
- Uses Flask blueprint design properly
- Registers routes via import side effects
- Keeps route definitions at top level

#### `stage1.py` - Subscription Confirmation
- Index redirect
- Subscription type confirmation
- BW type selection
- Handles suggested vs alternative types

**Routes:**
- `GET /` - Redirect to confirmation
- `GET /confirm-subscription` - Show subscription options
- `POST /select-subscription/<bw_type>` - Select BW type
- `GET /activation-choice` - Visual validation page

#### `stage2.py` - Contact Nomination
- Owner designation
- Paying party designation
- Form pre-filling and submission

**Routes:**
- `GET /nominate-contacts` - Show contact form
- `POST /submit-contacts` - Process contacts

#### `stage3.py` - Activation
- Free activation (CGV acceptance)
- Paid activation (pricing and payment)
- Confirmation pages for both flows

**Routes:**
- `GET /activate-free/<bw_type>` - Free activation page
- `POST /activate_free/<bw_type>` - Process free activation
- `GET /confirmation/free` - Free activation confirmation
- `GET /pricing/<bw_type>` - Pricing page
- `POST /set_pricing/<bw_type>` - Set pricing
- `GET /payment/<bw_type>` - Payment page
- `POST /simulate_payment/<bw_type>` - Simulate payment
- `GET /confirmation/paid` - Paid activation confirmation

#### `stage4.py` - Internal Roles
- Internal Business Wall Managers (BWMi)
- Internal PR Managers (BWPRi)
- Invitation workflow simulation

**Routes:**
- `GET /manage-internal-roles` - Manage internal roles

#### `stage5.py` - External Partners
- External PR Agency management
- Partnership invitation and validation
- Not available for "BW for PR" type

**Routes:**
- `GET /manage-external-partners` - Manage external partners

#### `stage6.py` - Missions/Permissions
- Permission assignment (7 mission types)
- RBAC toggles
- Mission state management

**Routes:**
- `GET /assign-missions` - Assign permissions

#### `stage7.py` - Content Configuration
- Content configuration
- Type-specific forms
- Graphics, contacts, and ontology fields

**Routes:**
- `GET /configure-content` - Configure BW content

#### `dashboard.py` - Management Hub
- Post-activation dashboard
- Session reset utility

**Routes:**
- `GET /dashboard` - Management dashboard
- `POST /reset` - Reset session

## Blueprint Pattern

The package uses the standard Flask blueprint pattern:

1. **Blueprint creation** (`__init__.py`):
   ```python
   from flask import Blueprint
   bp = Blueprint("bw_activation", __name__, template_folder="../../templates")
   ```

2. **Route registration** (each route module):
   ```python
   from .. import bp

   @bp.route("/endpoint")
   def handler():
       pass
   ```

3. **Automatic registration** (`routes/__init__.py`):
   ```python
   # Importing modules registers routes via side effects
   from . import stage1, stage2, stage3, stage4, stage5, stage6, stage7, dashboard
   ```

4. **Package import** (main `__init__.py`):
   ```python
   from . import routes  # Registers all routes
   ```

This pattern:
- ✅ Avoids circular imports
- ✅ No wrapper functions needed
- ✅ Routes are top-level functions
- ✅ Clean separation of concerns
- ✅ Standard Flask blueprint usage

## Workflow Stages

1. **Subscription Confirmation** → User confirms or changes suggested BW type
2. **Contact Nomination** → Designate Owner and Paying Party
3. **Activation** → Free (CGV) or Paid (pricing + payment)
4. **Internal Roles** → Invite BWMi and BWPRi
5. **External Partners** → Invite PR Agencies (not for BW for PR)
6. **Missions** → Assign permissions (7 types)
7. **Content Configuration** → Fill BW profile (type-specific)

## Session Management

The workflow uses Flask session to maintain state:
- `bw_type` - Selected Business Wall type
- `bw_type_confirmed` - Whether type selection is confirmed
- `suggested_bw_type` - KYC-based suggestion
- `contacts_confirmed` - Whether contacts are nominated
- `bw_activated` - Whether BW is activated
- `pricing_value` - For paid types (client_count or employee_count)
- `missions` - Dictionary of permission toggles
- Owner and payer contact information

## Adding New Features

### To add a new route to an existing stage:
1. Open the appropriate `stageN.py` module
2. Import `bp` from parent package: `from .. import bp`
3. Add route using `@bp.route()` decorator
4. Routes auto-register when module is imported

### To add a new workflow stage:
1. Create `routes/stage8.py`
2. Import blueprint: `from .. import bp`
3. Add routes with `@bp.route()` decorators
4. Import module in `routes/__init__.py`
5. Add corresponding template in `templates/bw_activation/`

### To add a new BW type:
1. Add configuration to `BW_TYPES` in `config.py`
2. Update type-specific logic in route handlers
3. Add type-specific fields to templates

## Testing

The blueprint auto-registers routes when imported:

```python
from poc.blueprints.bw_activation import bp
from poc.app import create_app

app = create_app()
routes = [r for r in app.url_map.iter_rules() if 'bw_activation' in r.endpoint]

# Should show 20 routes registered
print(f"Routes: {len(routes)}")
```

## Migration Notes

This package structure was refactored from the original monolithic `bw_activation.py` file (backed up as `bw_activation.py.old`).

**Key improvements:**
- Route modules renamed to `stageN.py` for clarity
- Routes are top-level functions (no wrapper pattern)
- Blueprint imported directly in each module
- Proper use of Flask blueprint design
- 100% functional compatibility maintained
