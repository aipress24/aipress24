# Changes Week 51, 2025

## Avis d'Enquête — Expert Contacts

- New `store_contact_avis_enquete()` to persist expert contacts.
- Expert filtering excludes contacts already added to an investigation (no duplicates).
- Missing `avis_enquete_notification.j2` template added — enables email notifications for Avis updates.
- Expert selection workflow updated with improved filtering.

## User Profile Enhancements

- New properties : `User.metiers`, `KYCProfile.country / ville / departement`. Enables better geographic + professional filtering.
- Public-profile page settings : rendering and UI improvements for visibility options.

## Image Handling Fixes

- Blank profile image displayed when S3 link is broken ; same for missing article images. Graceful fallback instead of broken-image icons.
- Fixed JSON serialisation issue with `FileObject` on the profile page.

## Refactoring & Misc

- Admin code cleanup + typing fixes ; global service pattern removed.
- Fixed dependency conflict between click and advanced-alchemy.
- More tests for preferences and admin UI.
