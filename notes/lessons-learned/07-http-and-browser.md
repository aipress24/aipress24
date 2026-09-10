# HTTP & Browser

Part of [Lessons Learned](00-index.md).

### Idempotent GET on confirmation pages

**Rule**: any GET route that creates an object must guard on the **real state**, not a session flag.

`/BW/confirmation/free` created two BWs on one GET: Firefox prefetch re-fired the handler while `session["bw_activated"]` was still true. Check whether the entity exists in the DB.

### Werkzeug 3+ caps forms at 500 KB

**Rule**: set `MAX_FORM_MEMORY_SIZE` to ~3× your max image size when accepting base64 uploads.

A 1 MB image becomes a ~1.4 MB form field and is silently rejected with a 413.
