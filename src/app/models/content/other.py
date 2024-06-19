# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""
'-----------------------------------------------------------------
'Corporate pages / info
'-----------------------------------------------------------------

abstract class OrganisationPage {
    +website_url URL
    +linkedin_url URL
    +siren_number SIREN
    +mission HTML
    +baseline string
    +logo Image
}
OrganisationPage -up-|> BaseContent

class MediaCompanyPage {
    +NoAgreement: string
    TODO contenu à définir
}
note bottom: Avec un numéro d agrément ou un numéro de Commission Paritaire

MediaCompanyPage -up-|> OrganisationPage

class CommunicationCompanyPage {
    TODO contenu à définir
}
CommunicationCompanyPage -up-|> OrganisationPage

class OtherOrganisationPage {
    TODO contenu à définir
}
OtherOrganisationPage -up-|> OrganisationPage

@enduml
"""
