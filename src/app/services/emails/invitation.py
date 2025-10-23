# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from flask_mailman import Mail

# language=jinja2
TEMPLATE = """
<p>
Bonjour {{ recipient_name }}
</p>

<p>
Je vous invite à rejoindre mon groupe sur AiPRESS24, le workspace des médias.
Adhérer à AiPRESS24 sera, pour vous, l’occasion de développer votre notoriété et d’entrer au cœur des rédactions.
</p>

<p>
Pour vous inscrire gratuitement sur AiPRESS24, cliquez sur ce lien.
</p>

<p>
À très bientôt.
</p>

<p>
{{ sender_name }}
</p>
"""


class InvitationMail(Mail):
    subject = "Invitation to join AiPRESS24"

    template = TEMPLATE
