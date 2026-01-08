# Changes Weeks 1-2, 2026

## Avis d'Enquête - RDV (Appointment) System

Full implementation of the rendez-vous scheduling workflow for journalist-expert interactions.

### Key Changes

**1. RDV Workflow**
- Journalists can propose 1-5 time slots to experts
- Three RDV types: Phone, Video, Face-to-face
- Experts select a slot and optionally add notes
- Full state machine: NO_RDV → PROPOSED → ACCEPTED → CONFIRMED

**2. RDV Views**
- New RDV table displaying all contacts with RDV status
- RDV details view with full appointment information
- RDV management interface for responses
- Link from opportunities view to RDV details

**3. Validation Rules**
- Slots must be in business hours (9h-18h)
- Slots must be on weekdays (Mon-Fri)
- All slots must be in the future
- Contact details required per RDV type (phone/video link/address)

## Service Layer Architecture

Major refactoring to separate concerns and improve testability.

### Key Changes

**1. AvisEnqueteService**
- Orchestrates RDV workflow (propose, accept, confirm, cancel)
- Handles expert notifications and emails
- Manages contact storage and filtering

**2. ExpertFilterService**
- Multi-criteria expert filtering (8 selectors)
- Session state management for filter persistence
- HTMX request parsing for dynamic updates

**3. Architecture Benefits**
- CRUD view reduced from 877 to 390 lines (55% reduction)
- Business logic extracted to services
- Domain validation in models
- Testable components with dependency injection

## Type Checking & Code Quality

Comprehensive type checking improvements across the codebase.

### Key Changes

**1. Runtime Type Checking**
- Added `typeguard` for runtime type verification during tests
- Removed `beartype` in favor of typeguard
- Fixed 68+ type errors across codebase

**2. Navigation Registry Pattern**
- Replaced monkey-patching `blueprint.nav = {...}` with clean registry
- New `configure_nav()` function with TypedDict configuration
- Type-safe with IDE autocomplete support
- Migrated 8 modules (admin, biz, events, preferences, search, swork, wip, wire)

## Navigation ACL System (ADR 003)

Completed implementation of role-based access control for navigation.

### Key Changes

**1. ACL Inheritance**
- Section-level ACL automatically inherited by child routes
- Admin routes inherit from admin section
- Preferences routes inherit SELF ACL

**2. Magic Roles**
- Removed GUEST role from RoleEnum
- Added SELF magic role (visible to all authenticated users)
- Protected personal routes (billing, performance, mail, delegate)
- Protected org routes with MANAGER/LEADER ACL

**3. Four-Layer Security**
- Doorman (path-based) → Blueprint hooks → Nav ACL → View checks
- Defense in depth with intentional redundancy

## Legacy Code Cleanup

Removal of deprecated code patterns.

### Key Changes

**1. Page Classes Removed**
- Deleted `preferences/pages/` directory (10 legacy files)
- Removed 28 legacy Page class tests, kept 9 useful tests
- Replaced with modern Flask-Classful views

**2. Module Refactoring**
- Cleaned up admin module
- Refactored test fixtures for e2e tests
- Fixed circular imports

## Documentation

New specification documentation for publication workflow.

### Key Changes

**1. Publication Cycle Specification**
- Created `notes/specs/cycle-de-publication.md`
- Documented full workflow: Sujet → Commande → Avis d'Enquête → Article → Justificatif
- Integrated client feedback (v1.1)
- Defined entity states, transitions, and business rules

## Testing

- Added anonymous access surface tests
- Navigation e2e tests
- 1960+ tests passing
