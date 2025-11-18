# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from .base import EmailTemplate


class BWInvitationMail(EmailTemplate):
    """Expected args:

    sender
    recipient
    sender_name
    bw_name
    """

    subject = "Invitation to join AiPRESS24"
    template_html = "bw_invitation.j2"
