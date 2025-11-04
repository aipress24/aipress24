# Business Wall - Production Implementation Roadmap

**Date:** 2025-11-04
**POC Status:** 100% spec-compliant, ready for production implementation
**Architecture:** Multi-Page Application (MPA) with server-rendered templates

---

## Overview

This roadmap outlines the implementation path from the current POC to a production-ready Business Wall system. The implementation follows an **MPA architecture** using server-rendered templates and form posts, with minimal API endpoints.

### Key Architectural Decisions

- **Server-rendered templates** (Jinja2) for all user interfaces
- **Form posts** with WTForms for data validation and processing
- **Progressive enhancement** with HTMX and Alpine.js
- **Minimal API endpoints** - only where truly needed (file uploads, real-time features)
- **Background jobs** (Dramatiq) for emails and notifications
- **Traditional MVC pattern** with Flask blueprints

---

## PHASE 1: Database & Data Models

**Dependencies:** None

### Objectives
Create the database schema and models to persist all Business Wall data and workflows.

### Key Deliverables

#### 1.1 Business Wall Models
- `BusinessWall` model with all 8 type configurations
- Fields: type, status (draft/active/suspended), activation_date, owner_id, payer_id
- Relationships: organization, owner, payer, subscriptions

#### 1.2 Contact & Role Models
- Extend `User` model or create `Contact` model for Owner/Payer
- Store: fonction/titre, service, billing address
- Link to Organization and BusinessWall

#### 1.3 Subscription & Billing Models
- `Subscription` model for paid BW types
- Fields: bw_type, client_count/employee_count, pricing_tier, stripe_subscription_id
- Track subscription lifecycle (trial, active, past_due, canceled)

#### 1.4 Role Assignment Models (RBAC)
- `RoleAssignment` table: (user_id, role_id, organization_id, context)
- Roles: BW_OWNER, BWMi, BWPRi, BWMe, BWPRe
- Support for invitation workflows (pending, accepted, rejected)

#### 1.5 Permission Models
- `RolePermission` table for granular permissions (Stage 6 missions)
- Permissions: press_release:create, event:manage, etc.
- Contextual to organization

#### 1.6 Partnership Models
- `Partnership` table for PR Agency relationships (Stage 5)
- Fields: client_org_id, agency_org_id, status, billing_impact
- Workflow states: invited, accepted, rejected, active, revoked

#### 1.7 Content Configuration Models
- `BWContent` model for Stage 7 data
- Store: logo, banner, gallery images (file references)
- Administrative data: SIREN, TVA, nature, audiences
- Ontology selections: centres d'intérêt (stored as JSON or many-to-many)

### Technical Considerations
- Use SQLAlchemy 2.0+ patterns (as per codebase standards)
- Implement proper indexes for performance
- Add constraints for data integrity
- Create migration scripts (Alembic)

---

## PHASE 2: Server-Side Forms & Business Logic

**Dependencies:** Phase 1

### Objectives
Implement server-side form handling, validation, and business logic for all 7 stages using traditional MVC pattern.

### Key Deliverables

#### 2.1 WTForms Form Classes

**Activation Workflow Forms (Stages 1-3)**
- `ConfirmSubscriptionForm` - BW type selection and confirmation
- `NominateContactsForm` - Owner and Payer information
- `ActivationCGVForm` - Free activation with CGV acceptance
- `ActivationPaidForm` - Paid activation with pricing info
- Nested forms for complex structures (Owner/Payer sections)

**Role Management Forms (Stage 4)**
- `InviteManagerForm` - Invite BWMi/BWPRi
- Multi-email input fields with validation

**Partnership Management Forms (Stage 5)**
- `InviteAgencyForm` - Select and invite PR Agency
- `AcceptPartnershipForm` - Agency acceptance interface

**Permission Management Forms (Stage 6)**
- `AssignMissionsForm` - Toggle permissions (7 mission types)
- Boolean fields for each permission

**Content Configuration Forms (Stage 7)**
- `BWContentForm` - Dynamic form adapting to BW type
- `GraphicsUploadForm` - Logo, banner, gallery uploads
- Type-specific field sets (Media, PR, Academics, etc.)
- Multi-select fields for ontology (centres d'intérêt)

#### 2.2 Route Handlers & Controllers

**Blueprint structure:**
```text
# src/app/modules/business_wall/pages/
├── activation.py      # Stages 1-3 routes
├── management.py      # Dashboard and overview
├── roles.py          # Stage 4 routes
├── partnerships.py   # Stage 5 routes
├── permissions.py    # Stage 6 routes
└── content.py        # Stage 7 routes
```

**Form processing pattern:**
```python
@bp.route("/stage", methods=["GET", "POST"])
def handle_stage():
    form = StageForm()
    if form.validate_on_submit():
        # Process form data
        # Update database
        # Flash success message
        return redirect(next_stage)
    return render_template("stage.html", form=form)
```

#### 2.3 Service Layer

- `BWActivationService` - Orchestrates activation workflow
- `RoleInvitationService` - Handles invitation lifecycle
- `PartnershipService` - Manages agency relationships
- `PermissionService` - RBAC permission checks
- `BillingService` - Stripe integration logic
- `ContentService` - Handles content configuration

#### 2.4 Minimal API Endpoints (where needed)

**File uploads only:**
- `POST /bw/{id}/upload-logo` - AJAX logo upload
- `POST /bw/{id}/upload-banner` - AJAX banner upload
- `POST /bw/{id}/upload-gallery` - AJAX gallery upload
- Returns JSON with file URLs

**Real-time features (if needed):**
- `GET /bw/{id}/invitation-status` - Check pending invitations
- WebSocket endpoints for live notifications (optional)

### Technical Considerations
- Use SVCS dependency injection (as per codebase)
- Implement service layer pattern
- WTForms validation with custom validators
- Use background jobs (Dramatiq) for emails/notifications
- Transaction management for multi-step workflows
- Flash messages for user feedback
- Server-side session management

---

## PHASE 3: Integrations & External Services

**Dependencies:** Phase 2

### Objectives
Integrate with external services for payments, notifications, and file storage.

### Key Deliverables

#### 3.1 Stripe Integration
- Create Stripe customers on BW activation
- Create Stripe subscriptions for paid BW types
- Handle webhooks: payment success, payment failed, subscription canceled
- Implement dynamic pricing based on client_count/employee_count
- Handle proration when client count changes (Stage 5 impact)
- **Server-side only** - no client-side API calls

#### 3.2 Email Notification System
- Email templates (Jinja2) for all workflows:
  - Invitation to become BWMi/BWPRi (with accept/reject links)
  - Partnership invitation to PR Agencies
  - Role acceptance confirmation
  - Role revocation notice
  - Payment confirmations
  - Subscription reminders
- Queue emails via Dramatiq for reliability
- Generate secure tokens for invitation links

#### 3.3 File Storage
- Implement file upload service (logo, banner, gallery)
- Use cloud storage (AWS S3 or similar)
- Generate thumbnails for images
- Validate file types and sizes
- Serve files via CDN
- AJAX upload with progress indicators

#### 3.4 Notification System
- In-app notifications for:
  - New invitations (WORK/BUSINESS WALL/INVITATION/...)
  - Partnership requests
  - Role changes
- Notification persistence in database
- Server-rendered notification display

### Technical Considerations
- Use Stripe Python SDK (server-side)
- Implement webhook verification
- Handle idempotency for payments
- Use boto3 for S3 integration (if AWS)
- Implement file validation and virus scanning
- Secure token generation for invitation links

---

## PHASE 4: RBAC Enforcement & Security

**Dependencies:** Phase 2

### Objectives
Implement the complete Role-Based Access Control system and security measures.

### Key Deliverables

#### 4.1 RBAC System Implementation
- Permission decorators for route handlers
- Context-aware permission checks (organization-specific)
- Dynamic role assignment based on workflow state
- Permission inheritance (Owner → Manager → PR Manager)

#### 4.2 Access Control Rules
- `@require_permission('bw:manage')` - Can manage Business Wall
- `@require_permission('bw:invite_managers')` - Can invite managers
- `@require_permission('press_release:create')` - Can create press releases
- Context-aware: check user role FOR specific organization

#### 4.3 Security Measures
- CSRF protection for all forms (WTForms built-in)
- Rate limiting on form submissions
- Input validation and sanitization (WTForms)
- SQL injection prevention (use ORM properly)
- XSS prevention in templates (Jinja2 auto-escaping)
- Secure file upload validation

#### 4.4 Audit Logging
- Log all role changes (invited, accepted, revoked)
- Log permission changes
- Log partnership changes
- Log payment events
- Implement audit trail for compliance

### Technical Considerations
- Use Flask-Security-Too (already in codebase)
- Implement custom permission system on top
- Use decorators for permission checks
- Store audit logs in separate table
- Consider GDPR compliance for data handling

---

## PHASE 5: Frontend Templates & UI Enhancement

**Dependencies:** Phase 2, 3

### Objectives
Convert POC templates to production-ready server-rendered templates with enhanced UX.

### Key Deliverables

#### 5.1 Production Template Conversion
- Convert POC templates to production structure
- Integrate with WTForms rendering
- Add CSRF tokens to all forms
- Implement proper error display
- Flash message styling and positioning

#### 5.2 Form Enhancement
- Client-side validation (before submit, matching backend)
- Loading states during form submission
- Disable submit button on submit (prevent double-submit)
- Progressive enhancement with HTMX for partial updates

#### 5.3 File Upload UI
- Drag-and-drop file upload (with fallback)
- Progress indicators
- Image preview before upload
- Client-side validation (file type, size)
- AJAX upload with server-side processing

#### 5.4 Dynamic Content Loading
- Load existing BW data for editing (server-rendered)
- Show current managers/PR managers in lists
- Display pending invitations
- Real-time permission toggle sync (HTMX partial update)

#### 5.5 Dashboard Templates
- Show BW activation status
- Display subscription info (next billing date, amount)
- Show analytics: number of managers, active permissions
- Quick actions: invite manager, add agency
- Server-rendered with optional HTMX for live updates

#### 5.6 Invitation Acceptance Pages
- Landing page for invitation links (with token)
- Accept/Reject interface (form post)
- Show organization details
- Confirm role assignment
- Server-rendered confirmation pages

### Technical Considerations
- Use existing tech stack (HTMX, Alpine.js, Vite)
- Server-side rendering for all initial page loads
- HTMX for partial updates (optional enhancement)
- Alpine.js for client-side interactivity only
- Maintain progressive enhancement
- Add accessibility (ARIA labels, keyboard navigation)
- Mobile-responsive design (Tailwind CSS)

---

## PHASE 6: Testing & Quality Assurance

**Dependencies:** Phase 2-5

### Objectives
Ensure system reliability, security, and performance through comprehensive testing.

### Key Deliverables

#### 6.1 Unit Tests
- Test all service layer methods
- Test RBAC permission checks
- Test workflow state transitions
- Test billing calculations
- Test WTForms validation logic
- Target: >80% code coverage

#### 6.2 Integration Tests
- Test complete activation workflow (Stages 1-3)
- Test invitation/acceptance workflow (Stage 4)
- Test partnership workflow (Stage 5)
- Test permission management (Stage 6)
- Test content configuration (Stage 7)
- Test form submissions with valid/invalid data

#### 6.3 Form Testing
- Test all WTForms validation rules
- Test CSRF protection
- Test file upload validation
- Test error handling and display
- Use pytest with Flask test client

#### 6.4 E2E Tests
- Test complete user journeys with Playwright
- Test all 8 BW types activation
- Test role invitation flows
- Test agency partnership flows
- Test form submissions and navigation

#### 6.5 Security Testing
- OWASP Top 10 vulnerabilities check
- Test CSRF protection on all forms
- Test file upload security
- Test payment flow security
- Test authorization checks

#### 6.6 Performance Testing
- Load testing for page loads
- Database query optimization
- Test with realistic data volumes
- Identify and fix bottlenecks
- Test file upload performance

### Technical Considerations
- Use pytest (as per codebase)
- Use factory pattern for test data
- Mock external services (Stripe, S3)
- Use VCR for recording HTTP interactions
- Set up CI/CD pipeline for automated testing
- Test with both SQLite and PostgreSQL

---

## Timeline Summary

| Phase | Duration | Dependencies | Key Milestone |
|-------|----------|--------------|---------------|
| Phase 1: Database | 2-3 weeks | - | Schema complete, migrations ready |
| Phase 2: Forms & Logic | 3-4 weeks | Phase 1 | All forms functional, validation complete |
| Phase 3: Integrations | 2-3 weeks | Phase 2 | Stripe, email, file storage working |
| Phase 4: RBAC | 2 weeks | Phase 2 | Permission system enforced |
| Phase 5: Frontend | 3-4 weeks | Phase 2, 3 | Production templates with enhanced UX |
| Phase 6: Testing | 2-3 weeks | Phase 2-5 | >80% coverage, all tests passing |


---

## External Dependencies

- **Stripe** account and API keys
- **Email service** (SMTP or transactional email provider)
- **BLOB storage** (AWS S3, Azure Blob, or similar)
- **CDN** for serving static files and uploads

---

## Risk Management

### Technical Risks

1. **Stripe integration complexity**
   - Mitigation: Use well-documented SDK, test with Stripe test mode extensively
   - Use webhook testing tools

2. **RBAC complexity**
   - Mitigation: Start with simple permissions, iterate based on requirements
   - Document permission hierarchy clearly

3. **File upload security**
   - Mitigation: Implement virus scanning, file type validation, size limits
   - Use secure file naming and storage

4. **Performance at scale**
   - Mitigation: Load testing early, optimize queries, implement caching
   - Use database indexes effectively

5. **Form complexity**
   - Mitigation: Use WTForms field sets and nested forms
   - Test validation thoroughly

### Business Risks

1. **User adoption**
   - Mitigation: Beta testing, training materials, responsive support
   - Clear UX and error messages

2. **Payment failures**
   - Mitigation: Clear error messages, retry logic, webhook monitoring
   - Comprehensive testing with Stripe test mode

3. **Data migration issues**
   - Mitigation: Thorough testing, rollback plan, gradual rollout
   - Backup strategy

---

## Success Metrics

### Technical Metrics
- >80% test coverage
- <200ms average page load time
- Zero critical security vulnerabilities
- 99.9% uptime for payment processing

### Business Metrics
- Successful activation rate >95%
- User satisfaction score >4.5/5
- Average activation time <15 minutes
- Support ticket volume <5% of activations

---

## Notes

This roadmap assumes:
- Development team is familiar with Flask, SQLAlchemy, WTForms
- Existing codebase patterns are followed (SVCS, blueprints, etc.)
- Infrastructure is already provisioned (servers, databases, etc.)
- CI/CD pipeline is in place or will be set up in parallel

The MPA architecture provides:
- **Simpler development** - no API contract to maintain
- **Better SEO** - server-rendered content
- **Progressive enhancement** - works without JavaScript
- **Easier debugging** - traditional request/response flow
- **Lower complexity** - fewer moving parts than SPA + API architecture
