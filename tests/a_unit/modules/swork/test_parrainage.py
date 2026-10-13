# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for swork parrainage."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import arrow

from app.models.parrainage_email_log import ParrainageEmailLog
from app.modules.swork.settings import SWORK_MENU
from app.modules.swork.views.parrainage import (
    parse_and_validate_emails,
    send_parrainage_emails,
)


class TestParrainageEmailParsing:
    """Test parse_and_validate_emails()."""

    def test_parse_comma_separated(self):
        raw = "alice@example.com, bob@example.com, charlie@example.org"
        valid, invalid = parse_and_validate_emails(raw)
        assert valid == ["alice@example.com", "bob@example.com", "charlie@example.org"]
        assert invalid == []

    def test_parse_semicolon_and_newlines(self):
        raw = "alice@example.com;\nbob@example.com\r\ncharlie@example.org"
        valid, invalid = parse_and_validate_emails(raw)
        assert valid == ["alice@example.com", "bob@example.com", "charlie@example.org"]
        assert invalid == []

    def test_parse_mixed_separators(self):
        raw = "alice@example.com, bob@example.com; charlie@example.org  david@example.com\n"
        valid, invalid = parse_and_validate_emails(raw)
        assert valid == [
            "alice@example.com",
            "bob@example.com",
            "charlie@example.org",
            "david@example.com",
        ]
        assert invalid == []

    def test_parse_deduplication_case_insensitive(self):
        raw = "alice@example.com, ALICE@EXAMPLE.COM, Bob@Example.Com, bob@example.com"
        valid, invalid = parse_and_validate_emails(raw)
        assert valid == ["alice@example.com", "bob@example.com"]
        assert invalid == []

    def test_parse_invalid_emails(self):
        raw = "valid@example.com, invalid-email, also_invalid@, good@domain.fr"
        valid, invalid = parse_and_validate_emails(raw)
        assert valid == ["valid@example.com", "good@domain.fr"]
        assert invalid == ["invalid-email", "also_invalid@"]

    def test_parse_empty_string(self):
        valid, invalid = parse_and_validate_emails("")
        assert valid == []
        assert invalid == []

    def test_parse_whitespace_only(self):
        valid, invalid = parse_and_validate_emails("   \n\t  \r\n ")
        assert valid == []
        assert invalid == []


class TestParrainageEmailLogModel:
    """Test ParrainageEmailLog model schema and attributes."""

    def test_model_table_name(self):
        assert ParrainageEmailLog.__tablename__ == "parrainage_email_log"

    def test_model_instantiation(self):
        now = arrow.utcnow()
        log = ParrainageEmailLog(
            user_id=123,
            recipient_email="friend@example.com",
            sent_at=now,
        )
        assert log.user_id == 123
        assert log.recipient_email == "friend@example.com"
        assert log.sent_at == now
        assert "123" in repr(log)
        assert "friend@example.com" in repr(log)


class TestSworkMenuConfiguration:
    """Test swork menu endpoints."""

    def test_parrainage_positioned_above_members(self):
        endpoints = [item["endpoint"] for item in SWORK_MENU]
        assert "swork.parrainage" in endpoints
        assert "swork.members" in endpoints

        parrainage_idx = endpoints.index("swork.parrainage")
        members_idx = endpoints.index("swork.members")
        assert parrainage_idx == members_idx - 1

        parrainage_item = SWORK_MENU[parrainage_idx]
        assert parrainage_item["label"] == "Parrainage"
        assert parrainage_item["icon"] == "heart"


class TestSendParrainageEmails:
    """Test send_parrainage_emails()."""

    def test_send_parrainage_emails(self):
        user = MagicMock()
        user.email = "sender@example.com"
        user.full_name = "Sender Name"

        with patch(
            "app.modules.swork.views.parrainage.ParrainageMail"
        ) as mock_mail_cls:
            mock_instance = mock_mail_cls.return_value
            mock_instance.send.return_value = True

            send_parrainage_emails(user, ["friend1@example.com", "friend2@example.com"])

            assert mock_mail_cls.call_count == 2
            assert mock_instance.send.call_count == 2
            first_call_kwargs = mock_mail_cls.call_args_list[0].kwargs
            assert first_call_kwargs["recipient"] == "friend1@example.com"
            assert first_call_kwargs["sender_mail"] == "sender@example.com"
            assert first_call_kwargs["sender_full_name"] == "Sender Name"
            assert first_call_kwargs["sender"] == "contact@aipress24.com"
