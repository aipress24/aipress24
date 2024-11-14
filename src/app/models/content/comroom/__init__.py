# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""
'-----------------------------------------------------------------
'Communication content
'-----------------------------------------------------------------

class CommunicationContent {
    +sender: string
}
CommunicationContent -up-|> BaseContent

class PressRelease {
    +title: string
    +subheader: string
    +categories: list[string]
    +release_date: DateTime
    +embargo_date: DateTime

    +about: string

    +attachments: list[Attachment]
}
PressRelease -up-|> CommunicationContent

class PressKit {
}
PressKit -up-|> CommunicationContent

' class PressKit {
' }
' PressKit -up-|> CommunicationContent

' class Backgrounder {
' }
' Backgrounder -up-|> CommunicationContent

' class Study {
' }
' Study -up-|> CommunicationContent

' class FinancialReport {
' }
' FinancialReport -up-|> CommunicationContent

' class ExpertOpinion {
' }
' ExpertOpinion -up-|> CommunicationContent


Metadata:

From: "Publier un communiqué de presse sur AIpress24"
1- [ ] la localisation du communiqué [TODO]
2- [x] la date de publication du communiqué
3- [x] le genre (nouveau produit, avis d’expert...)
4- [x] les thématiques (Liste IPTC)
5- [x] les secteurs d’activité concernés
6- [x] les technologies (le cas échéant)
7- [x] la langue (en français par défaut)
8- [x] Tapez vos mots-clés (tags)
TODO: champs multi-valués
"""

from __future__ import annotations

from app.models.content.comroom.press_release import PressRelease

__all__ = ["PressRelease"]
