# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Lire une liste d'adresses saisie à la main dans un formulaire.

Deux vues en avaient chacune leur version — le partage d'article et
l'achat d'une consultation offerte — et elles ne découpaient pas pareil :
l'une acceptait l'espace comme séparateur et validait la forme de
l'adresse, l'autre non. « a@b.com c@d.com » donnait donc deux
destinataires d'un côté et une chaîne invalide de l'autre, sur un
chemin facturé (audit du 2026-09-02).
"""

from __future__ import annotations


def parse_recipient_emails(raw_emails: str) -> list[str]:
    """Découper une saisie libre en adresses uniques et minuscules.

    Virgules, retours à la ligne et espaces séparent indifféremment :
    un membre qui colle une colonne d'un tableur, une liste séparée par
    des virgules ou une ligne d'adresses obtient le même résultat.

    Les entrées qui n'ont pas la forme d'une adresse sont écartées ici
    plutôt qu'en aval : c'est la frontière, et une adresse invalide n'a
    de sens ni pour un envoi ni pour une facturation.
    """
    if not raw_emails:
        return []

    addresses = {
        address
        for token in raw_emails.replace(",", " ").split()
        if _looks_like_an_email(address := token.strip().lower())
    }
    return sorted(addresses)


def _looks_like_an_email(address: str) -> bool:
    """Quelque chose, une arobase, puis un domaine pointé.

    Rien de plus : la validation sérieuse appartient au serveur de
    messagerie, pas à un formulaire. Mais la partie locale doit exister —
    l'ancien contrôle acceptait « @exemple.com », qui serait parti en
    destinataire facturé.
    """
    local, separator, domain = address.partition("@")
    return bool(separator and local and "." in domain)
