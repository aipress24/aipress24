# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from app.services.emails.base import EmailTemplate

# language=jinja2
TEMPLATE = """
Bonjour

Je souhaiterais m’inscrire en tant que journaliste professionnel.le non titulaire d’une carte de presse sur la plateforme Aipress24 qui permet aux journalistes professionnels de compléter leurs revenus et de gagner en efficacité opérationnelle.

Or, pour finaliser mon inscription, j’ai besoin:
- soit d’être titulaire d’une carte de presse en cours de validité,
- soit me faire parrainer par un des rédacteurs.res en chef, chefs.fes de rubrique ou chefs.fes de département avec lesquels je travaille.

Pourrais-je bénéficier de ton appui ?

→ **Si tu es déjà inscrit.e et que tu es d’accord**, je te remercie de cliquer ici. Tu trouveras le formulaire de parrainage d’Aipress24. Au passage, tu gagneras des points dans ton indice de performance réputationnelle.

→ **Si tu n’es pas encore membre d’Aipress24** (je te rappelle que c’est gratuit pour tous les journalistes ainsi que pour ton titre), je t’invite à t’inscrire sur Aipress24 [Lien vers une page explicative et vers le formulaire d’inscription] car tu gagneras de nouvelles sources de revenus pour ta rédaction.

→ **Si tu ne souhaites pas t’inscrire sur Aipress24** mais si tu acceptes de me parrainer, clique ici [lien vers la page de parrainage].

Encore merci de ton aide.

Cordialement

{{ sender_name }}
"""


class DemandeParrainageMailTemplate(EmailTemplate):
    subject = (
        "Demande de parrainage pour m’inscrire en tant que journaliste professionnel.le"
        " non titulaire d’une carte de presse sur la plateforme Aipress24"
    )

    template_md = TEMPLATE
