# Email & Notifications

Part of [Lessons Learned](00-index.md).

### Send before mutating the state the email cites

**Rule**: if an email quotes state, send it before any mutation that invalidates it.

`cancel_rdv` reset `contact.date_rdv = None`; the cancellation email body cites that date and early-returns when it's `None`, so the original cancel-then-email order silently dropped the notification.

### Couple recipient creation to the notification trigger

**Rule**: a user-input path that must produce a notification later should create or reference the recipient entity *in the form*, not downstream.

A free-text email input wasn't stored as a Contact, so no notification could ever be sent. Replaced with a `<select>` of colleagues, which guarantees the Contact exists when the trigger fires.

### Name mail variables by type, not by role

**Rule**: `sender_mail` / `sender_full_name`, never `sender_name`.

Ambiguity between "person name" and "technical identifier" is a reliable source of the "I put the email in the name field" bug.

### Verify "familiar" imports before writing send-mail code

**Rule**: grep for the actual library first.

This project uses `flask_mailman` via `EmailService`, not `flask_mail.Message`. The familiar import would have crashed on the first cron run.
