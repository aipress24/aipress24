# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Pin the public contract of the `AvisEnquete` / `ContactAvisEnquete` models.

WHY these tests exist
=====================
`AvisEnquete` and its companion `ContactAvisEnquete` carry a non-trivial
business workflow (Avis -> RDV negotiation -> Confirmation) that drives
the journalist <-> expert UX. The model encodes:

- A column shape (table, FKs, defaults) consumed by repositories,
  templates, faker, and several modules under ``app.modules.wip``.
- Four StrEnums (``TypeAvis``, ``StatutAvis``, ``RDVType``, ``RDVStatus``)
  whose lowercase string values are persisted in the database and
  referenced in templates — renaming a member would silently break
  every row already stored.
- Pure state-machine helpers (``can_propose_rdv``, ``can_accept_rdv``,
  ``can_confirm_rdv``, ``can_cancel_rdv``, ``is_*`` properties) and the
  slot-validation rules (future / business-hours / weekday).

We exercise the **pure** parts only — no database session required —
to lock the contract without pulling the full ORM stack into a unit test.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.models.lifecycle import PublicationStatus
from app.modules.wip.models.newsroom.avis_enquete import (
    AvisEnquete,
    ContactAvisEnquete,
    RDVStatus,
    RDVType,
    StatutAvis,
    TypeAvis,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _next_weekday_at(hour: int, days_ahead: int = 1) -> datetime:
    """Return an aware UTC datetime ``days_ahead`` days from now at ``hour``.

    Skips weekends so callers can request a guaranteed valid business slot.
    """
    candidate = datetime.now(UTC) + timedelta(days=days_ahead)
    while candidate.weekday() >= 5:  # Saturday=5, Sunday=6
        candidate += timedelta(days=1)
    return candidate.replace(hour=hour, minute=0, second=0, microsecond=0)


def _make_contact(**overrides) -> ContactAvisEnquete:
    """Build an un-persisted ContactAvisEnquete with sensible defaults.

    Uses the regular constructor (no session attach) so SQLAlchemy's
    instrumented attributes work, then sets defaults explicitly to
    avoid relying on column-level defaults (which only fire on flush).
    """
    contact = ContactAvisEnquete()
    contact.status = StatutAvis.EN_ATTENTE
    contact.rdv_status = RDVStatus.NO_RDV
    contact.rdv_type = None
    contact.proposed_slots = []
    contact.date_rdv = None
    contact.rdv_phone = ""
    contact.rdv_video_link = ""
    contact.rdv_address = ""
    contact.rdv_notes_journaliste = ""
    contact.rdv_notes_expert = ""
    for key, value in overrides.items():
        setattr(contact, key, value)
    return contact


# ---------------------------------------------------------------------------
# Enum contract
# ---------------------------------------------------------------------------


class TestEnumValues:
    """Pin the persisted string values of every StrEnum on this model.

    These values land in the database (``sa.Enum(...)`` columns) and are
    referenced from templates/views. Reordering or renaming a member is
    a breaking change.
    """

    @pytest.mark.parametrize(
        ("member", "expected"),
        [
            (TypeAvis.AVIS_D_ENQUETE, "avis_d_enquete"),
            (TypeAvis.APPEL_A_TEMOIN, "appel_a_temoin"),
            (TypeAvis.APPEL_A_EXPERT, "appel_a_expert"),
        ],
    )
    def test_type_avis_values(self, member: TypeAvis, expected: str) -> None:
        assert member.value == expected

    @pytest.mark.parametrize(
        ("member", "expected"),
        [
            (StatutAvis.EN_ATTENTE, "en_attente"),
            (StatutAvis.ACCEPTE, "accepte"),
            (StatutAvis.ACCEPTE_RELATION_PRESSE, "accepte_relation_presse"),
            (StatutAvis.REFUSE, "refuse"),
            (StatutAvis.REFUSE_SUGGESTION, "refuse_suggestion"),
        ],
    )
    def test_statut_avis_values(self, member: StatutAvis, expected: str) -> None:
        assert member.value == expected

    @pytest.mark.parametrize(
        ("member", "expected_value", "expected_label"),
        [
            (RDVType.PHONE, "phone", "Téléphone"),
            (RDVType.VIDEO, "video", "Visioconférence"),
            (RDVType.F2F, "f2f", "Face-à-face"),
        ],
    )
    def test_rdv_type_values_and_labels(
        self, member: RDVType, expected_value: str, expected_label: str
    ) -> None:
        assert member.value == expected_value
        assert member.label == expected_label

    @pytest.mark.parametrize(
        ("member", "expected_value", "expected_label"),
        [
            (RDVStatus.NO_RDV, "no_rdv", "Pas de RDV"),
            (RDVStatus.PROPOSED, "proposed", "Proposé"),
            (RDVStatus.ACCEPTED, "accepted", "Accepté"),
            (RDVStatus.CONFIRMED, "confirmed", "Confirmé"),
        ],
    )
    def test_rdv_status_values_and_labels(
        self, member: RDVStatus, expected_value: str, expected_label: str
    ) -> None:
        assert member.value == expected_value
        assert member.label == expected_label


# ---------------------------------------------------------------------------
# Table shape
# ---------------------------------------------------------------------------


class TestAvisEnqueteTableShape:
    """Pin the SQLAlchemy table shape of ``AvisEnquete``.

    Renaming a column or changing a default breaks every migration,
    repository query, and template that already references the model.
    """

    def test_tablename(self) -> None:
        assert AvisEnquete.__tablename__ == "nrm_avis_enquete"

    def test_required_columns_present(self) -> None:
        columns = {col.name for col in AvisEnquete.__table__.columns}
        # Local columns
        for name in (
            "date_debut_enquete",
            "date_fin_enquete",
            "date_bouclage",
            "date_parution_prevue",
            "type_avis",
            "status",
            "pays_zip_ville",
            "pays_zip_ville_detail",
            "justificatif_notifications_count",
        ):
            assert name in columns, f"missing column: {name}"
        # Inherited from NewsroomCommonMixin
        for name in ("titre", "brief", "contenu", "media_id", "commanditaire_id"):
            assert name in columns, f"missing inherited column: {name}"
        # Inherited from NewsMetadataMixin
        for name in ("genre", "section", "topic", "sector", "language"):
            assert name in columns, f"missing metadata column: {name}"
        # Inherited from CiblageMixin
        assert "ciblage_secteur_detailles" in columns

    def test_status_default_is_draft(self) -> None:
        col = AvisEnquete.__table__.columns["status"]
        assert col.default.arg is PublicationStatus.DRAFT

    def test_type_avis_default_is_avis_d_enquete(self) -> None:
        col = AvisEnquete.__table__.columns["type_avis"]
        assert col.default.arg is TypeAvis.AVIS_D_ENQUETE

    def test_justificatif_count_defaults_to_zero(self) -> None:
        col = AvisEnquete.__table__.columns["justificatif_notifications_count"]
        assert col.default.arg == 0


class TestContactAvisEnqueteTableShape:
    """Pin the ``ContactAvisEnquete`` table shape and key FKs."""

    def test_tablename(self) -> None:
        assert ContactAvisEnquete.__tablename__ == "nrm_contact_avis_enquete"

    def test_required_columns_present(self) -> None:
        columns = {col.name for col in ContactAvisEnquete.__table__.columns}
        for name in (
            "avis_enquete_id",
            "journaliste_id",
            "expert_id",
            "suggested_by_user_id",
            "status",
            "date_reponse",
            "date_rdv",
            "rdv_type",
            "rdv_status",
            "proposed_slots",
            "rdv_phone",
            "rdv_video_link",
            "rdv_address",
            "rdv_notes_journaliste",
            "rdv_notes_expert",
            "email_relation_presse",
        ):
            assert name in columns, f"missing column: {name}"

    def test_avis_enquete_fk_is_not_nullable(self) -> None:
        assert ContactAvisEnquete.__table__.columns["avis_enquete_id"].nullable is False
        assert ContactAvisEnquete.__table__.columns["journaliste_id"].nullable is False
        assert ContactAvisEnquete.__table__.columns["expert_id"].nullable is False

    def test_suggested_by_user_id_is_nullable(self) -> None:
        # The suggestion chain is optional.
        assert (
            ContactAvisEnquete.__table__.columns["suggested_by_user_id"].nullable
            is True
        )

    def test_status_default_is_en_attente(self) -> None:
        col = ContactAvisEnquete.__table__.columns["status"]
        assert col.default.arg is StatutAvis.EN_ATTENTE

    def test_rdv_status_default_is_no_rdv(self) -> None:
        col = ContactAvisEnquete.__table__.columns["rdv_status"]
        assert col.default.arg is RDVStatus.NO_RDV


# ---------------------------------------------------------------------------
# proposed_slots_dt property
# ---------------------------------------------------------------------------


class TestProposedSlotsDt:
    """``proposed_slots`` is persisted as ISO strings (JSON-safe); the
    ``_dt`` accessor must convert them back to aware datetimes."""

    def test_returns_empty_list_when_no_slots(self) -> None:
        contact = _make_contact(proposed_slots=[])
        assert contact.proposed_slots_dt == []

    def test_parses_iso_strings_back_to_datetimes(self) -> None:
        slot = _next_weekday_at(10, days_ahead=2)
        contact = _make_contact(proposed_slots=[slot.isoformat()])
        result = contact.proposed_slots_dt
        assert len(result) == 1
        assert result[0] == slot


# ---------------------------------------------------------------------------
# can_* state-machine predicates
# ---------------------------------------------------------------------------


class TestCanProposeRdv:
    """Only an *accepted* Avis with no existing RDV can receive a proposal."""

    @pytest.mark.parametrize(
        "status",
        [StatutAvis.ACCEPTE, StatutAvis.ACCEPTE_RELATION_PRESSE],
    )
    def test_can_propose_when_accepted_and_no_rdv(self, status: StatutAvis) -> None:
        contact = _make_contact(status=status, rdv_status=RDVStatus.NO_RDV)
        assert contact.can_propose_rdv() is True

    @pytest.mark.parametrize(
        "status",
        [
            StatutAvis.EN_ATTENTE,
            StatutAvis.REFUSE,
            StatutAvis.REFUSE_SUGGESTION,
        ],
    )
    def test_cannot_propose_when_not_accepted(self, status: StatutAvis) -> None:
        contact = _make_contact(status=status, rdv_status=RDVStatus.NO_RDV)
        assert contact.can_propose_rdv() is False

    @pytest.mark.parametrize(
        "rdv_status",
        [RDVStatus.PROPOSED, RDVStatus.ACCEPTED, RDVStatus.CONFIRMED],
    )
    def test_cannot_propose_when_rdv_already_exists(
        self, rdv_status: RDVStatus
    ) -> None:
        contact = _make_contact(status=StatutAvis.ACCEPTE, rdv_status=rdv_status)
        assert contact.can_propose_rdv() is False


class TestCanAcceptRdv:
    """The expert can only accept when a RDV has been proposed."""

    def test_can_accept_when_proposed(self) -> None:
        contact = _make_contact(rdv_status=RDVStatus.PROPOSED)
        assert contact.can_accept_rdv() is True

    @pytest.mark.parametrize(
        "rdv_status",
        [RDVStatus.NO_RDV, RDVStatus.ACCEPTED, RDVStatus.CONFIRMED],
    )
    def test_cannot_accept_otherwise(self, rdv_status: RDVStatus) -> None:
        contact = _make_contact(rdv_status=rdv_status)
        assert contact.can_accept_rdv() is False


class TestCanConfirmRdv:
    """Confirmation is the optional step after the expert accepts."""

    def test_can_confirm_after_accepted(self) -> None:
        contact = _make_contact(rdv_status=RDVStatus.ACCEPTED)
        assert contact.can_confirm_rdv() is True

    @pytest.mark.parametrize(
        "rdv_status",
        [RDVStatus.NO_RDV, RDVStatus.PROPOSED, RDVStatus.CONFIRMED],
    )
    def test_cannot_confirm_otherwise(self, rdv_status: RDVStatus) -> None:
        contact = _make_contact(rdv_status=rdv_status)
        assert contact.can_confirm_rdv() is False


# ---------------------------------------------------------------------------
# is_* properties
# ---------------------------------------------------------------------------


class TestStatusFlags:
    """Read-only ``is_*`` flags consumed by templates and views.

    Keeping them in lockstep with the underlying enum values prevents
    UI regressions where badges or filters silently flip.
    """

    def test_is_new_opportunity_only_when_en_attente(self) -> None:
        assert _make_contact(status=StatutAvis.EN_ATTENTE).is_new_opportunity is True
        assert _make_contact(status=StatutAvis.ACCEPTE).is_new_opportunity is False

    @pytest.mark.parametrize(
        "status",
        [StatutAvis.REFUSE, StatutAvis.REFUSE_SUGGESTION],
    )
    def test_is_declined_for_both_refusal_variants(self, status: StatutAvis) -> None:
        assert _make_contact(status=status).is_declined_opportunity is True

    @pytest.mark.parametrize(
        "status",
        [StatutAvis.EN_ATTENTE, StatutAvis.ACCEPTE],
    )
    def test_is_not_declined_when_not_refused(self, status: StatutAvis) -> None:
        assert _make_contact(status=status).is_declined_opportunity is False

    def test_is_rdv_requested_when_accepted_without_rdv(self) -> None:
        contact = _make_contact(status=StatutAvis.ACCEPTE, rdv_status=RDVStatus.NO_RDV)
        assert contact.is_rdv_requested is True

    def test_is_rdv_requested_false_after_proposal(self) -> None:
        contact = _make_contact(
            status=StatutAvis.ACCEPTE, rdv_status=RDVStatus.PROPOSED
        )
        assert contact.is_rdv_requested is False

    def test_has_rdv_false_when_no_rdv(self) -> None:
        assert _make_contact(rdv_status=RDVStatus.NO_RDV).has_rdv is False

    @pytest.mark.parametrize(
        "rdv_status",
        [RDVStatus.PROPOSED, RDVStatus.ACCEPTED, RDVStatus.CONFIRMED],
    )
    def test_has_rdv_true_otherwise(self, rdv_status: RDVStatus) -> None:
        assert _make_contact(rdv_status=rdv_status).has_rdv is True

    def test_is_rdv_confirmed_flag(self) -> None:
        assert _make_contact(rdv_status=RDVStatus.CONFIRMED).is_rdv_confirmed is True
        assert _make_contact(rdv_status=RDVStatus.ACCEPTED).is_rdv_confirmed is False

    def test_is_rdv_accepted_flag(self) -> None:
        assert _make_contact(rdv_status=RDVStatus.ACCEPTED).is_rdv_accepted is True
        assert _make_contact(rdv_status=RDVStatus.PROPOSED).is_rdv_accepted is False

    def test_is_waiting_expert_response_flag(self) -> None:
        contact = _make_contact(rdv_status=RDVStatus.PROPOSED)
        assert contact.is_waiting_expert_response is True
        assert (
            _make_contact(rdv_status=RDVStatus.ACCEPTED).is_waiting_expert_response
            is False
        )


# ---------------------------------------------------------------------------
# _validate_slot_time
# ---------------------------------------------------------------------------


class TestValidateSlotTime:
    """Defensive rules for proposed RDV slots: future + business hours + weekday."""

    def test_accepts_valid_business_hour_slot(self) -> None:
        contact = _make_contact()
        slot = _next_weekday_at(10, days_ahead=2)
        validated = contact._validate_slot_time(slot)
        assert validated == slot

    def test_naive_datetime_is_assumed_utc(self) -> None:
        contact = _make_contact()
        naive = _next_weekday_at(10, days_ahead=2).replace(tzinfo=None)
        validated = contact._validate_slot_time(naive)
        assert validated.tzinfo is UTC

    def test_rejects_past_slot(self) -> None:
        contact = _make_contact()
        past = datetime.now(UTC) - timedelta(days=1)
        with pytest.raises(ValueError, match="must be in the future"):
            contact._validate_slot_time(past)

    @pytest.mark.parametrize("bad_hour", [0, 5, 8, 18, 22])
    def test_rejects_slot_outside_business_hours(self, bad_hour: int) -> None:
        contact = _make_contact()
        slot = _next_weekday_at(bad_hour, days_ahead=2)
        with pytest.raises(ValueError, match="business hours"):
            contact._validate_slot_time(slot)

    def test_rejects_weekend_slot(self) -> None:
        contact = _make_contact()
        # Walk to the next Saturday at a business hour.
        candidate = datetime.now(UTC) + timedelta(days=1)
        while candidate.weekday() != 5:
            candidate += timedelta(days=1)
        saturday = candidate.replace(hour=10, minute=0, second=0, microsecond=0)
        with pytest.raises(ValueError, match="weekend"):
            contact._validate_slot_time(saturday)


# ---------------------------------------------------------------------------
# propose_rdv business method
# ---------------------------------------------------------------------------


class TestProposeRdv:
    """Pin the happy path and every defensive branch of ``propose_rdv``."""

    def _accepted_contact(self) -> ContactAvisEnquete:
        return _make_contact(status=StatutAvis.ACCEPTE, rdv_status=RDVStatus.NO_RDV)

    def test_proposes_phone_rdv_successfully(self) -> None:
        contact = self._accepted_contact()
        slot = _next_weekday_at(10, days_ahead=2)
        contact.propose_rdv(
            rdv_type=RDVType.PHONE,
            proposed_slots=[slot],
            rdv_phone="+33123456789",
            rdv_notes="hi",
        )
        assert contact.rdv_type == RDVType.PHONE
        assert contact.rdv_status == RDVStatus.PROPOSED
        assert contact.proposed_slots == [slot.isoformat()]
        assert contact.rdv_phone == "+33123456789"
        assert contact.rdv_notes_journaliste == "hi"

    def test_rejects_when_status_not_accepted(self) -> None:
        contact = _make_contact(status=StatutAvis.EN_ATTENTE)
        with pytest.raises(ValueError, match="Cannot propose RDV"):
            contact.propose_rdv(
                rdv_type=RDVType.PHONE,
                proposed_slots=[_next_weekday_at(10, days_ahead=2)],
                rdv_phone="123",
            )

    def test_rejects_empty_slot_list(self) -> None:
        contact = self._accepted_contact()
        with pytest.raises(ValueError, match="At least one time slot"):
            contact.propose_rdv(
                rdv_type=RDVType.PHONE, proposed_slots=[], rdv_phone="123"
            )

    def test_rejects_more_than_five_slots(self) -> None:
        contact = self._accepted_contact()
        slots = [_next_weekday_at(10, days_ahead=i + 1) for i in range(6)]
        with pytest.raises(ValueError, match="Maximum 5"):
            contact.propose_rdv(
                rdv_type=RDVType.PHONE, proposed_slots=slots, rdv_phone="123"
            )

    def test_rejects_phone_type_without_phone(self) -> None:
        contact = self._accepted_contact()
        with pytest.raises(ValueError, match="Phone number required"):
            contact.propose_rdv(
                rdv_type=RDVType.PHONE,
                proposed_slots=[_next_weekday_at(10, days_ahead=2)],
            )

    def test_rejects_video_type_without_link(self) -> None:
        contact = self._accepted_contact()
        with pytest.raises(ValueError, match="Video link required"):
            contact.propose_rdv(
                rdv_type=RDVType.VIDEO,
                proposed_slots=[_next_weekday_at(10, days_ahead=2)],
            )

    def test_rejects_f2f_type_without_address(self) -> None:
        contact = self._accepted_contact()
        with pytest.raises(ValueError, match="Address required"):
            contact.propose_rdv(
                rdv_type=RDVType.F2F,
                proposed_slots=[_next_weekday_at(10, days_ahead=2)],
            )


# ---------------------------------------------------------------------------
# accept / refuse / confirm / cancel RDV
# ---------------------------------------------------------------------------


class TestAcceptRdv:
    """Expert accepts one of the proposed slots; selected slot becomes ``date_rdv``."""

    def test_accept_valid_slot(self) -> None:
        slot = _next_weekday_at(10, days_ahead=2)
        contact = _make_contact(
            rdv_status=RDVStatus.PROPOSED, proposed_slots=[slot.isoformat()]
        )
        contact.accept_rdv(slot, expert_notes="ok")
        assert contact.rdv_status == RDVStatus.ACCEPTED
        assert contact.date_rdv == slot
        assert contact.rdv_notes_expert == "ok"

    def test_naive_slot_assumed_utc(self) -> None:
        aware = _next_weekday_at(10, days_ahead=2)
        contact = _make_contact(
            rdv_status=RDVStatus.PROPOSED, proposed_slots=[aware.isoformat()]
        )
        # Caller passes a naive copy; method must normalise to UTC.
        contact.accept_rdv(aware.replace(tzinfo=None))
        assert contact.rdv_status == RDVStatus.ACCEPTED

    def test_rejects_when_no_rdv_proposed(self) -> None:
        contact = _make_contact(rdv_status=RDVStatus.NO_RDV)
        with pytest.raises(ValueError, match="no RDV has been proposed"):
            contact.accept_rdv(_next_weekday_at(10, days_ahead=2))

    def test_rejects_unknown_slot(self) -> None:
        proposed = _next_weekday_at(10, days_ahead=2)
        other = _next_weekday_at(11, days_ahead=2)
        contact = _make_contact(
            rdv_status=RDVStatus.PROPOSED, proposed_slots=[proposed.isoformat()]
        )
        with pytest.raises(ValueError, match="must be one of the proposed"):
            contact.accept_rdv(other)


class TestRefuseRdv:
    """Expert refuses; full reset to initial state."""

    def test_refuse_resets_state(self) -> None:
        contact = _make_contact(
            rdv_status=RDVStatus.PROPOSED,
            rdv_type=RDVType.PHONE,
            proposed_slots=["x"],
            date_rdv=_next_weekday_at(10, days_ahead=2),
            rdv_phone="123",
            rdv_notes_journaliste="n",
        )
        contact.refuse_rdv()
        assert contact.rdv_status == RDVStatus.NO_RDV
        assert contact.rdv_type is None
        assert contact.proposed_slots == []
        assert contact.date_rdv is None
        assert contact.rdv_phone == ""
        assert contact.rdv_notes_journaliste == ""

    def test_rejects_when_no_rdv_proposed(self) -> None:
        contact = _make_contact(rdv_status=RDVStatus.NO_RDV)
        with pytest.raises(ValueError, match="no RDV has been proposed"):
            contact.refuse_rdv()


class TestConfirmRdv:
    """Confirmation is the optional final transition ACCEPTED -> CONFIRMED."""

    def test_confirm_from_accepted(self) -> None:
        contact = _make_contact(rdv_status=RDVStatus.ACCEPTED)
        contact.confirm_rdv()
        assert contact.rdv_status == RDVStatus.CONFIRMED

    @pytest.mark.parametrize(
        "rdv_status",
        [RDVStatus.NO_RDV, RDVStatus.PROPOSED, RDVStatus.CONFIRMED],
    )
    def test_rejects_other_states(self, rdv_status: RDVStatus) -> None:
        contact = _make_contact(rdv_status=rdv_status)
        with pytest.raises(ValueError, match="not been accepted"):
            contact.confirm_rdv()


class TestCancelRdv:
    """Cancellation is allowed from any active RDV state, but not after it
    has already happened in the past."""

    @pytest.mark.parametrize(
        "rdv_status",
        [RDVStatus.PROPOSED, RDVStatus.ACCEPTED, RDVStatus.CONFIRMED],
    )
    def test_can_cancel_future_rdv(self, rdv_status: RDVStatus) -> None:
        contact = _make_contact(
            rdv_status=rdv_status, date_rdv=_next_weekday_at(10, days_ahead=2)
        )
        assert contact.can_cancel_rdv() is True

    def test_cannot_cancel_when_no_rdv(self) -> None:
        contact = _make_contact(rdv_status=RDVStatus.NO_RDV)
        assert contact.can_cancel_rdv() is False

    def test_cannot_cancel_when_rdv_past(self) -> None:
        # is_rdv_past short-circuits the predicate.
        past = datetime.now(UTC) - timedelta(days=1)
        contact = _make_contact(rdv_status=RDVStatus.CONFIRMED, date_rdv=past)
        assert contact.can_cancel_rdv() is False

    def test_cancel_resets_state(self) -> None:
        contact = _make_contact(
            rdv_status=RDVStatus.ACCEPTED,
            rdv_type=RDVType.VIDEO,
            date_rdv=_next_weekday_at(10, days_ahead=2),
            proposed_slots=["x"],
            rdv_video_link="https://example.test",
            rdv_notes_journaliste="n",
            rdv_notes_expert="e",
        )
        contact.cancel_rdv()
        assert contact.rdv_status == RDVStatus.NO_RDV
        assert contact.rdv_type is None
        assert contact.date_rdv is None
        assert contact.proposed_slots == []
        assert contact.rdv_video_link == ""
        assert contact.rdv_notes_journaliste == ""
        assert contact.rdv_notes_expert == ""

    def test_cancel_rejects_when_nothing_to_cancel(self) -> None:
        contact = _make_contact(rdv_status=RDVStatus.NO_RDV)
        with pytest.raises(ValueError, match="No RDV to cancel"):
            contact.cancel_rdv()


# ---------------------------------------------------------------------------
# Temporal calculations
# ---------------------------------------------------------------------------


class TestTimeUntilRdv:
    """``time_until_rdv`` underpins ``is_rdv_soon`` and ``is_rdv_past``."""

    def test_returns_none_when_no_date(self) -> None:
        contact = _make_contact(date_rdv=None)
        assert contact.time_until_rdv() is None

    def test_returns_positive_delta_for_future(self) -> None:
        contact = _make_contact(date_rdv=_next_weekday_at(10, days_ahead=3))
        delta = contact.time_until_rdv()
        assert delta is not None
        assert delta > timedelta(0)

    def test_returns_negative_delta_for_past(self) -> None:
        past = datetime.now(UTC) - timedelta(days=1)
        contact = _make_contact(date_rdv=past)
        delta = contact.time_until_rdv()
        assert delta is not None
        assert delta < timedelta(0)

    def test_naive_date_is_normalised_to_utc(self) -> None:
        # The method mutates ``self.date_rdv`` to attach UTC when naive.
        naive_future = (datetime.now(UTC) + timedelta(hours=2)).replace(tzinfo=None)
        contact = _make_contact(date_rdv=naive_future)
        delta = contact.time_until_rdv()
        assert delta is not None
        assert contact.date_rdv.tzinfo is UTC


class TestIsRdvSoonAndPast:
    """``is_rdv_soon`` flips inside the 24h window; ``is_rdv_past`` after the date."""

    def test_is_rdv_soon_true_within_24h(self) -> None:
        soon = datetime.now(UTC) + timedelta(hours=3)
        contact = _make_contact(date_rdv=soon)
        assert contact.is_rdv_soon is True

    def test_is_rdv_soon_false_when_far(self) -> None:
        far = datetime.now(UTC) + timedelta(days=5)
        contact = _make_contact(date_rdv=far)
        assert contact.is_rdv_soon is False

    def test_is_rdv_soon_false_when_no_date(self) -> None:
        assert _make_contact(date_rdv=None).is_rdv_soon is False

    def test_is_rdv_past_true_for_past_date(self) -> None:
        past = datetime.now(UTC) - timedelta(hours=1)
        contact = _make_contact(date_rdv=past)
        assert contact.is_rdv_past is True

    def test_is_rdv_past_false_for_future_date(self) -> None:
        future = datetime.now(UTC) + timedelta(hours=1)
        contact = _make_contact(date_rdv=future)
        assert contact.is_rdv_past is False

    def test_is_rdv_past_false_when_no_date(self) -> None:
        assert _make_contact(date_rdv=None).is_rdv_past is False


# ---------------------------------------------------------------------------
# get_rdv_summary — human-readable string used in templates
# ---------------------------------------------------------------------------


class TestGetRdvSummary:
    """The summary is rendered in templates; pin every branch."""

    def test_returns_no_rdv_text_when_absent(self) -> None:
        contact = _make_contact(rdv_status=RDVStatus.NO_RDV)
        assert contact.get_rdv_summary() == "Pas de rendez-vous"

    def test_proposed_shows_slot_count(self) -> None:
        slots = ["a", "b", "c"]
        contact = _make_contact(rdv_status=RDVStatus.PROPOSED, proposed_slots=slots)
        assert contact.get_rdv_summary() == "RDV proposé (3 créneaux)"

    @pytest.mark.parametrize(
        ("rdv_type", "expected_label"),
        [
            (RDVType.PHONE, "Téléphone"),
            (RDVType.VIDEO, "Visio"),
            (RDVType.F2F, "Face-à-face"),
        ],
    )
    def test_confirmed_includes_type_and_date(
        self, rdv_type: RDVType, expected_label: str
    ) -> None:
        # Use a SimpleNamespace as a stand-in for the real datetime: only
        # ``strftime`` is needed, so we keep the assertion deterministic.
        date_ns = SimpleNamespace(strftime=lambda _fmt: "01/01/2030 à 10:00")
        contact = _make_contact(
            rdv_status=RDVStatus.CONFIRMED, date_rdv=date_ns, rdv_type=rdv_type
        )
        summary = contact.get_rdv_summary()
        assert "RDV confirmé" in summary
        assert expected_label in summary
        assert "01/01/2030 à 10:00" in summary

    def test_accepted_branch_renders_without_confirmed_prefix(self) -> None:
        date_ns = SimpleNamespace(strftime=lambda _fmt: "02/02/2030 à 11:00")
        contact = _make_contact(
            rdv_status=RDVStatus.ACCEPTED, date_rdv=date_ns, rdv_type=RDVType.PHONE
        )
        summary = contact.get_rdv_summary()
        assert summary.startswith("RDV ")
        assert "confirmé" not in summary
        assert "Téléphone" in summary

    def test_proposed_without_date_falls_through(self) -> None:
        # Status ACCEPTED but date missing — defensive fallback.
        contact = _make_contact(
            rdv_status=RDVStatus.ACCEPTED, date_rdv=None, rdv_type=None
        )
        assert contact.get_rdv_summary() == "RDV en cours"
