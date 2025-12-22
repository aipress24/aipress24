# Changes Week 51, 2025

## Avis d'Enquête (Investigation Notice) Improvements

Several enhancements to the Avis d'Enquête feature for journalist investigations.

### Key Changes

**1. Expert Contact Management**
- New `store_contact_avis_enquete()` function for storing expert contacts
- Expert filtering to exclude contacts already added to an investigation
- Prevents duplicate contacts in the expert list

**2. Notification System**
- Added missing `avis_enquete_notification.j2` template
- Enables email notifications for Avis d'Enquête updates

**3. Expert Selection**
- Updated expert selection workflow
- Improved filtering and management of potential expert contacts

## User Profile Enhancements

### Key Changes

**1. New User Properties**
- Added `User.metiers` property for user professions/trades
- Added `User.profile.country`, `.ville`, `.departement` properties
- Enables better geographic and professional filtering

**2. Public Profile Settings**
- Improved rendering of public-profile page settings
- Better UI for managing profile visibility options

## Image Handling Fixes

Fixes for S3-based image storage and display.

### Key Changes

**1. Broken Image Detection**
- Display blank profile image when S3 link is broken
- Detect missing images for articles
- Graceful fallback instead of broken image icons

**2. FileObject Handling**
- Fixed JSON serialization issue with FileObject for profile page
- Prevents errors when rendering profile data

## Refactoring

**1. Admin Code Cleanup**
- Cleanup and fix typing issues in admin code
- Removed global service pattern

**2. Dependency Fixes**
- Fixed dependency conflict between click and advanced-alchemy

## Testing

- Added more tests for preferences module
- Added more tests for admin UI
