# Business Wall Activation Module Overview

This document describes the `bw_activation` module, which implements the complete Business Wall activation and management workflow for AiPRESS24.

## Purpose

A **Business Wall** is an organization's "storefront" on the AiPRESS24 platform. It enables organizations to:
- Establish their official presence on the platform
- Manage internal team members and roles
- Declare external PR partnerships
- Configure content and permissions for press activities

## Business Wall Types

The system supports **8 types** of Business Walls, divided into two categories:

### Free Types (5)

| Type | Target Audience | Description |
|------|-----------------|-------------|
| **Media** | Recognized press organizations | For accredited media outlets |
| **Micro** | Micro-press enterprises | Freelancers and small press entities working for recognized outlets |
| **Corporate Media** | Institutional/corporate media | For company and institutional media |
| **Union** | Press unions and associations | For press federations, journalist clubs, and associations |
| **Academics** | Research and higher education | For universities and research institutions |

### Paid Types (3)

| Type | Target Audience | Pricing Model |
|------|-----------------|---------------|
| **PR** | PR agencies and consultants | Based on number of represented clients |
| **Leaders & Experts** | Enterprises, associations, experts | Based on number of employees |
| **Transformers** | Innovation and digital transformation actors | Based on number of employees |

## User Roles (RBAC)

The system implements role-based access control with 5 role types:

| Role | Code | Scope | Description |
|------|------|-------|-------------|
| **BW Owner** | `BW_OWNER` | Internal | Creator/owner of the Business Wall |
| **BW Manager (internal)** | `BWMi` | Internal | Manages BW operations internally |
| **PR Manager (internal)** | `BWPRi` | Internal | Handles press relations internally |
| **BW Manager (external)** | `BWMe` | External | External management representative |
| **PR Manager (external)** | `BWPRe` | External | External PR representative |

## Activation Workflow

The activation workflow consists of **3 initial stages** followed by **6 management stages**.

### Initial Activation (Stages 1-3)

```
[Stage 1: Confirm Subscription]
         │
         ▼
[Stage 2: Nominate Contacts]
         │
         ▼
[Stage 3: Activation]
    ┌────┴────┐
    │         │
  FREE      PAID
    │         │
    ▼         ▼
CGV Accept  Pricing
    │         │
    │       Payment
    │         │
    └────┬────┘
         │
         ▼
   [Confirmation]
         │
         ▼
    [Dashboard]
```

#### Stage 1: Subscription Confirmation
- User's profile determines suggested BW type automatically
- User confirms or selects a different BW type
- Session tracks the selected type

#### Stage 2: Contact Nomination
- Define the **BW Owner** (typically the current user)
- Define the **Payer** (can be same as owner or different)
- Collect contact information (name, email, phone)

#### Stage 3: Activation
- **Free types**: Accept CGV (General Terms of Sale) and activate
- **Paid types**:
  1. Specify pricing parameters (client count or employee count)
  2. Accept CGV
  3. Process payment (Stripe integration placeholder)
  4. Activation confirmation

### Post-Activation Management (Stages B1-B6)

After activation, the BW Owner accesses a dashboard with 6 management areas:

#### Stage B1: Invite Organisation Members
- Send invitations to join the BW's organisation
- Manage pending invitations
- Email-based invitation workflow

#### Stage B2: Manage Organisation Members
- View current members
- Add/remove members (cannot remove owner)
- Members are associated via email

#### Stage B3: Manage Internal Roles
- Assign **BWMi** (BW Manager Internal) roles
- Assign **BWPRi** (PR Manager Internal) roles
- Track invitation status (pending/accepted/rejected/expired)

#### Stage B4: Manage External Partners
- Declare and validate external PR agencies
- Manage partnerships with PR consultants
- Partnership status workflow (invited → accepted/rejected → active/revoked)

#### Stage B5: Assign Missions
- Configure permissions for PR Managers:
  - Press release publication
  - Event management
  - Mission assignments
  - Profile management
  - Media contacts
  - Statistics/KPIs
  - Messaging

#### Stage B6: Configure Content
- Visual identity (logo, banner, gallery)
- Organization information (official name, type, description)
- Administrative data (SIREN, TVA, CPPAP)
- Contact information (website, email, phone, address)
- Social media links
- Ontology selections (topics, geographic zones, sectors)
- Member/client lists

## Data Model

### Core Entities

```
┌─────────────────┐       ┌──────────────────┐
│  BusinessWall   │───────│   Organisation   │
│  (bw_business_  │       │  (crp_organis-   │
│   wall)         │       │   ation)         │
├─────────────────┤       └──────────────────┘
│ id (UUID)       │              │
│ bw_type         │              │
│ status          │              ▼
│ is_free         │       ┌──────────────────┐
│ owner_id ───────┼───────│      User        │
│ payer_id ───────┼───────│   (aut_user)     │
│ organisation_id │       └──────────────────┘
│ activated_at    │
│ payer_*         │
└────────┬────────┘
         │
         │ 1
         │
    ┌────┴────┬──────────┬─────────────┐
    │ 1       │ *        │ *           │ 1
    ▼         ▼          ▼             ▼
┌─────────┐ ┌──────────┐ ┌───────────┐ ┌──────────┐
│ BWCon-  │ │ RoleAs-  │ │ Partner-  │ │ Subscrip-│
│ tent    │ │ signment │ │ ship      │ │ tion     │
└─────────┘ └────┬─────┘ └───────────┘ └──────────┘
                 │
                 │ *
                 ▼
            ┌──────────┐
            │ RolePer- │
            │ mission  │
            └──────────┘
```

### Entity Details

#### BusinessWall
- Central entity representing an organization's presence
- Links to owner/payer (User) and organisation
- Tracks activation status and type

#### Subscription
- Tracks pricing tier and payment status
- Stores Stripe integration data (customer_id, subscription_id)
- Billing information and subscription period

#### RoleAssignment
- Maps users to BW roles
- Invitation workflow with status tracking
- Links to granular permissions

#### RolePermission
- Fine-grained permission control for PR Managers
- Permission types: press_release, events, missions, profiles, etc.

#### Partnership
- Represents BW ↔ PR Agency relationships
- Full invitation/acceptance workflow
- Contract period tracking

#### BWContent
- Visual content (logo, banner, gallery via S3 storage)
- Organization metadata
- Contact and social media information
- Ontology selections (topics, zones, sectors)

## Status Enumerations

### BusinessWall Status
- `DRAFT`: Initial state before activation
- `ACTIVE`: Successfully activated
- `SUSPENDED`: Temporarily suspended
- `CANCELLED`: Permanently cancelled

### Subscription Status
- `PENDING`: Awaiting payment
- `ACTIVE`: Active subscription
- `PAST_DUE`: Payment overdue
- `CANCELLED`: Subscription cancelled
- `EXPIRED`: Subscription expired

### Invitation Status
- `PENDING`: Invitation sent, awaiting response
- `ACCEPTED`: Invitation accepted
- `REJECTED`: Invitation declined
- `EXPIRED`: Invitation expired

### Partnership Status
- `INVITED`: Partnership invitation sent
- `ACCEPTED`: Partner accepted invitation
- `REJECTED`: Partner declined
- `ACTIVE`: Active partnership
- `REVOKED`: Partnership revoked
- `EXPIRED`: Partnership expired

## Use Case Scenarios

### Scenario 1: Media Organization Activation (Free)
1. Director of a recognized media outlet logs in
2. System suggests "Business Wall for Media" based on profile
3. Director confirms subscription type
4. Nominates themselves as owner and payer
5. Accepts CGV (distribution agreement + terms)
6. Business Wall is activated immediately
7. Director can now invite journalists and manage newsroom features

### Scenario 2: PR Agency Activation (Paid)
1. PR agency director logs in
2. System suggests "Business Wall for PR"
3. Director confirms and specifies number of represented clients (e.g., 1)
4. Enters payer information (may be different person)
5. Accepts CGV
6. Completes payment via Stripe
7. Business Wall activated
8. Can later represent clients after mutual validation

### Scenario 3: Post-Activation Management
1. BW Owner accesses dashboard
2. Invites team members to join organisation (Stage B1)
3. Validates accepted members (Stage B2)
4. Assigns internal roles - promotes a member to BWMi (Stage B3)
5. Declares external PR agency partnership (Stage B4)
6. Configures permissions for PR managers (Stage B5)
7. Uploads logo, fills organization details (Stage B6)

### Scenario 4: Role Invitation Flow
1. BW Owner navigates to internal roles management
2. Enters email of member to invite as BWMi
3. System creates RoleAssignment with `PENDING` status
4. Invited user sees pending invitation
5. User accepts → status changes to `ACCEPTED`
6. User now has management rights on the Business Wall

## Technical Architecture

### Module Structure
```
src/app/modules/bw/bw_activation/
├── __init__.py          # Blueprint definition, login requirement
├── config.py            # BW types configuration (properties, pricing, messages)
├── utils.py             # Session management, permission checks
├── user_utils.py        # User context utilities, BW type guessing
├── bw_creation.py       # BW record creation logic
├── bw_invitation.py     # Role invitation management
├── models/
│   ├── __init__.py      # Exports all models
│   ├── business_wall.py # Core BusinessWall entity
│   ├── subscription.py  # Subscription entity
│   ├── role.py          # RoleAssignment & RolePermission
│   ├── partnership.py   # Partnership entity
│   ├── content.py       # BWContent entity
│   ├── repositories.py  # Data access layer
│   └── services.py      # Service layer (via flask-super)
├── routes/
│   ├── __init__.py      # Route registration
│   ├── stage1.py        # Subscription confirmation
│   ├── stage2.py        # Contact nomination
│   ├── stage3.py        # Activation (free/paid)
│   ├── stage_b1.py      # Invite members
│   ├── stage_b2.py      # Manage members
│   ├── stage_b3.py      # Internal roles
│   ├── stage_b4.py      # External partners
│   ├── stage_b5.py      # Mission permissions
│   ├── stage_b6.py      # Content configuration
│   ├── dashboard.py     # Management hub
│   └── not_authorized.py
└── templates/
    └── bw_activation/   # Jinja2 templates
```

### Key Patterns
- **Repository Pattern**: Data access via Advanced-Alchemy repositories
- **Service Layer**: Business logic via SVCS-injected services
- **Session-based Workflow**: Multi-step activation state in Flask session
- **HTMX Integration**: Dynamic UI updates without full page reloads
- **Profile-based Suggestions**: BW type auto-suggested from user's profile code

## Integration Points

### External Systems
- **Stripe**: Payment processing for paid BW types (placeholder)
- **S3**: File storage for logos, banners, galleries

### Internal Systems
- **Organisation**: BW linked to user's organisation
- **User/Auth**: Role assignments reference users
- **Profile System**: Determines suggested BW type
- **Invitation System**: Email-based member invitations

## Access Control

Access to BW management is restricted to:
1. **BW Owner** (always has access)
2. **Users with accepted role assignments** (BWMi, BWPRi)

Non-managers are redirected to "not authorized" page.
