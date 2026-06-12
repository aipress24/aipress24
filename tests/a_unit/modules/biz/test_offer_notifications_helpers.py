# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for the pure helpers in
`app.modules.biz.services.offer_notifications`.

Three pure helpers route every accept/reject email and in-app cloche
to the right offer-detail URL :

- `_dashboard_for(offer)` → the (endpoint, fallback URL) pair for
  the emitter's « Candidatures reçues » dashboard
- `_detail_for(offer)`    → same pair for the public detail page
- `_absolutize(path)`     → glues scheme + host onto a relative path

These functions read `offer.type` (a polymorphic SQLAlchemy
discriminator : `"mission_offer"`, `"project_offer"`, `"job_offer"`)
and dispatch by `match` statement. A wrong dispatch routes a
notification to the wrong section of the site — silent in tests, very
visible to the user. Pinning the table catches typos at PR time.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.modules.biz.services.offer_notifications import (
    _absolute_applications_url,
    _absolute_offer_url,
    _absolute_profile_url,
    _absolutize,
    _dashboard_for,
    _detail_for,
    _pick_emitter_email,
)

if TYPE_CHECKING:
    from flask import Flask


class _OfferLike:
    """Stand-in for the polymorphic offer ORM rows. Only carries the
    `type` discriminator + `id` (and optional `contact_email` for the
    `_pick_emitter_email` tests)."""

    def __init__(
        self,
        *,
        type_: str = "mission_offer",
        id_: int = 42,
        contact_email: str = "",
        owner_id: int = 1,
    ) -> None:
        self.type = type_
        self.id = id_
        self.contact_email = contact_email
        self.owner_id = owner_id


class TestDashboardFor:
    """Dashboard URL routing : the (endpoint, fallback) pair for the
    emitter's « Candidatures reçues » page."""

    def test_mission_offer_dispatches_to_missions(self):
        endpoint, fallback = _dashboard_for(_OfferLike(type_="mission_offer", id_=42))
        assert endpoint == "biz.missions_applications"
        assert fallback == "/biz/missions/42/applications"

    def test_project_offer_dispatches_to_projects(self):
        endpoint, fallback = _dashboard_for(_OfferLike(type_="project_offer", id_=42))
        assert endpoint == "biz.projects_applications"
        assert fallback == "/biz/projects/42/applications"

    def test_job_offer_dispatches_to_jobs(self):
        endpoint, fallback = _dashboard_for(_OfferLike(type_="job_offer", id_=42))
        assert endpoint == "biz.jobs_applications"
        assert fallback == "/biz/jobs/42/applications"

    def test_unknown_type_falls_back_to_missions(self):
        """`match _:` is the default arm — unknown types route to
        missions. Pin so a future fourth offer-type added without
        updating this dispatch silently routes wrong instead of
        crashing."""
        endpoint, _fallback = _dashboard_for(_OfferLike(type_="bogus_type"))
        assert endpoint == "biz.missions_applications"

    def test_missing_type_attr_falls_back_to_mission_offer(self):
        """`getattr(offer, "type", "mission_offer")` — a row whose
        `type` column wasn't populated (legacy data, fixture
        oversight) still routes to missions. Pin so the safety net
        doesn't get accidentally removed."""

        class _NoType:
            id = 99

        endpoint, _ = _dashboard_for(_NoType())
        assert endpoint == "biz.missions_applications"

    def test_fallback_url_uses_offer_id(self):
        """If the URL builder fails (e.g. blueprint not loaded), the
        fallback URL still gets the correct offer id baked in."""
        _, fallback = _dashboard_for(_OfferLike(type_="project_offer", id_=12345))
        assert "12345" in fallback


class TestDetailFor:
    """Public detail-page URL routing — same pattern as dashboard
    but for the offer detail page the candidate sees."""

    def test_mission_offer_dispatches(self):
        endpoint, fallback = _detail_for(_OfferLike(type_="mission_offer", id_=42))
        assert endpoint == "biz.missions_detail"
        assert fallback == "/biz/missions/42"

    def test_project_offer_dispatches(self):
        endpoint, fallback = _detail_for(_OfferLike(type_="project_offer", id_=42))
        assert endpoint == "biz.projects_detail"
        assert fallback == "/biz/projects/42"

    def test_job_offer_dispatches(self):
        endpoint, fallback = _detail_for(_OfferLike(type_="job_offer", id_=42))
        assert endpoint == "biz.jobs_detail"
        assert fallback == "/biz/jobs/42"

    def test_unknown_type_falls_back_to_missions(self):
        endpoint, _ = _detail_for(_OfferLike(type_="strange"))
        assert endpoint == "biz.missions_detail"

    def test_fallback_url_no_trailing_slash(self):
        """The fallback URL is the canonical detail-page path — no
        trailing slash. Pin so a future stripper / appender doesn't
        silently change the URL shape (and break HTMX swaps)."""
        _, fallback = _detail_for(_OfferLike(type_="mission_offer", id_=1))
        assert fallback == "/biz/missions/1"
        assert not fallback.endswith("/")


class TestAbsolutize:
    """Glue scheme + host onto a relative path. The host comes from
    `current_app.config["SERVER_NAME"]` ; protocol is `https` for
    real hosts, `http` for loopback (127.* dev addresses)."""

    def test_real_hostname_uses_https(self, app: Flask):
        with app.test_request_context():
            app.config["SERVER_NAME"] = "aipress24.com"
            result = _absolutize("/wire/article/42")
        assert result == "https://aipress24.com/wire/article/42"

    def test_loopback_uses_http(self, app: Flask):
        """The dev server runs at 127.0.0.1:5000 ; using https would
        break the local browser (no certificate). Pin the heuristic
        so an accidental fixed-https regression doesn't break local
        notification testing."""
        with app.test_request_context():
            app.config["SERVER_NAME"] = "127.0.0.1:5000"
            result = _absolutize("/wire/article/42")
        assert result.startswith("http://")
        assert "127.0.0.1:5000" in result

    def test_missing_server_name_defaults_to_aipress24_com(self, app: Flask):
        """Production fallback : when `SERVER_NAME` isn't set (some
        worker contexts), default to the canonical hostname so the
        email link still points at the right place."""
        with app.test_request_context():
            app.config["SERVER_NAME"] = None
            result = _absolutize("/wire/x")
        assert "aipress24.com" in result
        assert result.startswith("https://")

    def test_empty_string_server_name_defaults(self, app: Flask):
        with app.test_request_context():
            app.config["SERVER_NAME"] = ""
            result = _absolutize("/wire/x")
        assert "aipress24.com" in result

    def test_path_passed_through_unchanged(self, app: Flask):
        """The path is appended verbatim — no normalisation, no
        url-encoding, no trailing-slash stripping. Pin so a future
        « clean-up » doesn't silently change link shapes."""
        with app.test_request_context():
            app.config["SERVER_NAME"] = "aipress24.com"
            result = _absolutize("/swork/members/12?tab=press-book")
        assert result.endswith("/swork/members/12?tab=press-book")


class TestPickEmitterEmail:
    """Pure prefix of `_pick_emitter_email` — the early-return when
    `offer.contact_email` is set, before the DB lookup. Pin so a
    future refactor that always queries the DB doesn't silently slow
    down every notification."""

    def test_contact_email_takes_priority(self):
        offer = _OfferLike(contact_email="contact@example.com", owner_id=999)
        # No DB session needed when contact_email is set — short-circuits.
        assert _pick_emitter_email(offer) == "contact@example.com"

    def test_empty_contact_email_falls_through_to_db(self, app: Flask):
        """When `contact_email` is empty, the function falls through
        to a DB lookup. In a unit context we can verify the
        short-circuit DOESN'T fire, even though we can't easily test
        the DB branch without a fixture. With no User row matching
        `owner_id`, returns empty string."""
        with app.app_context():
            offer = _OfferLike(contact_email="", owner_id=999_999_999)
            # owner_id 999M won't match any seed user, so falls through
            # to the empty default.
            assert _pick_emitter_email(offer) == ""

    def test_missing_contact_email_attr_treated_as_empty(self, app: Flask):
        """`getattr(offer, "contact_email", "")` — a row schema that
        doesn't have a contact_email column (legacy) still falls
        through to the owner-email path."""

        class _NoContact:
            owner_id = 999_999_999

        with app.app_context():
            assert _pick_emitter_email(_NoContact()) == ""


class _StubUser:
    def __init__(self, *, id_: int = 1) -> None:
        self.id = id_


class TestAbsoluteProfileUrl:
    """`_absolute_profile_url` calls `url_for("swork.member", id=user.id)`
    inside a try/except — when the resolver fails (no request context,
    blueprint missing, etc.), it falls back to a hand-coded
    `/swork/members/<id>` path. The fallback is the unit-testable
    branch ; the happy path needs a routed app and lives in
    b_integration."""

    def test_fallback_path_when_no_app_context(self, app: Flask):
        """Outside any request/app context, `url_for` raises a
        RuntimeError — the helper must catch it and fall back to the
        hand-coded path."""
        # `_absolutize` reads `current_app.config` — give it just enough
        # context to do that, but no request context so `url_for` fails.
        with app.app_context():
            app.config["SERVER_NAME"] = "aipress24.com"
            result = _absolute_profile_url(_StubUser(id_=42))
        assert result.endswith("/swork/members/42")
        assert result.startswith("https://aipress24.com")


class TestAbsoluteApplicationsUrl:
    """Same shape as `_absolute_profile_url` — dispatch by offer type
    and absolutize the result."""

    def test_fallback_for_mission_offer(self, app: Flask):
        with app.app_context():
            app.config["SERVER_NAME"] = "aipress24.com"
            result = _absolute_applications_url(
                _OfferLike(type_="mission_offer", id_=7)
            )
        assert result.endswith("/biz/missions/7/applications")
        assert result.startswith("https://aipress24.com")

    def test_fallback_for_project_offer(self, app: Flask):
        with app.app_context():
            app.config["SERVER_NAME"] = "aipress24.com"
            result = _absolute_applications_url(
                _OfferLike(type_="project_offer", id_=8)
            )
        assert result.endswith("/biz/projects/8/applications")

    def test_fallback_for_job_offer(self, app: Flask):
        with app.app_context():
            app.config["SERVER_NAME"] = "aipress24.com"
            result = _absolute_applications_url(_OfferLike(type_="job_offer", id_=9))
        assert result.endswith("/biz/jobs/9/applications")


class TestAbsoluteOfferUrl:
    """Detail-page absolutiser — pairs with `_detail_for` to produce
    a public URL the candidate sees in the rejection/selection email."""

    def test_fallback_for_mission_offer(self, app: Flask):
        with app.app_context():
            app.config["SERVER_NAME"] = "aipress24.com"
            result = _absolute_offer_url(_OfferLike(type_="mission_offer", id_=42))
        assert result.endswith("/biz/missions/42")

    def test_fallback_for_project_offer(self, app: Flask):
        with app.app_context():
            app.config["SERVER_NAME"] = "aipress24.com"
            result = _absolute_offer_url(_OfferLike(type_="project_offer", id_=42))
        assert result.endswith("/biz/projects/42")

    def test_fallback_for_job_offer(self, app: Flask):
        with app.app_context():
            app.config["SERVER_NAME"] = "aipress24.com"
            result = _absolute_offer_url(_OfferLike(type_="job_offer", id_=42))
        assert result.endswith("/biz/jobs/42")

    def test_loopback_dev_host_uses_http(self, app: Flask):
        """End-to-end check that the absolutiser's loopback-detection
        feeds through to the per-kind helpers — dev runs over http."""
        with app.app_context():
            app.config["SERVER_NAME"] = "127.0.0.1:5000"
            result = _absolute_offer_url(_OfferLike(type_="mission_offer", id_=1))
        assert result.startswith("http://127.0.0.1:5000")
