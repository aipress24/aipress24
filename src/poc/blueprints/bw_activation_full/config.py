# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Business Wall types configuration.

This module defines all available Business Wall types with their properties,
pricing, and onboarding messages.
"""

from __future__ import annotations

# Business Wall Types configuration
BW_TYPES = {
    # Free BW types (5 types)
    "media": {
        "name": "Business Wall for Media",
        "description": "Pour les organes de presse reconnus.",
        "free": True,
        "activation_text": "Approuver l'accord de diffusion sur AiPRESS24 + Business Wall CGV",
        "manager_role": "PR Manager",  # For confirmation messages
        "onboarding_messages": [
            "Votre abonnement gratuit à Business Wall for Media sera la vitrine sur AiPRESS24 de l'organe de presse reconnu que vous dirigez.",
            "Vous devez créer un seul Business Wall for Media par organe de presse.",
            "Pour bénéficier de votre Business Wall for Media, de l'accès aux fonctionnalités de NEWSROOM (propositions et commandes de sujets, Avis d'enquête digital, etc.) et pour commercialiser vos contenus journalistiques (consultations sur NEWS, Consultations Offertes, justificatifs de publication, revente de ©, fonds mutualisé des Avis d'enquêtes), vous devrez approuver notre contrat de diffusion sur AiPRESS24.",
            "Vous devrez aussi approuver nos Conditions générales de vente sur AiPRESS24.",
            "Vous devez également déclarer et valider individuellement chaque PR Agency ou chaque PR Consultant qui vous représentent sur AiPRESS24 et peuvent agir en tant que contact presse, publier vos communiqués de presse et vos événements.",
            "Les informations que vous allez saisir seront vérifiées par les équipes d'AiPRESS24.",
        ],
    },
    "micro": {
        "name": "Business Wall for Micro",
        "description": "Pour les micro-entreprises de presse travaillant pour des organes de presse reconnus.",
        "free": True,
        "activation_text": "Approuver l'accord de diffusion sur AiPRESS24 + Business Wall CGV",
        "manager_role": "PR Manager",
        "onboarding_messages": [
            "Votre abonnement gratuit à Business Wall for Micro sera la vitrine sur AiPRESS24 de votre micro-entreprise de presse travaillant pour des organes de presse reconnus.",
            "Pour bénéficier de Business Wall for Micro, de l'accès aux fonctionnalités de NEWSROOM (propositions et commandes de sujets, Avis d'enquête digital, etc.) et pour commercialiser vos contenus journalistiques (consultations sur NEWS, Consultations Offertes, justificatifs de publication, revente de ©, fonds mutualisé des Avis d'enquêtes), vous devrez approuver notre contrat de diffusion sur AiPRESS24.",
            "Vous devrez aussi approuver nos Conditions générales de vente sur AiPRESS24.",
            "Les informations que vous allez saisir seront vérifiées par les équipes d'AiPRESS24.",
        ],
    },
    "corporate_media": {
        "name": "Business Wall for Corporate Media",
        "description": "Pour les médias d'entreprise et institutionnels.",
        "free": True,
        "activation_text": "Approuver les CGV de Business Wall sur AiPRESS24",
        "manager_role": "PR Manager",
        "onboarding_messages": [
            "Votre abonnement gratuit à Business Wall for Corporate Media sera la vitrine sur AiPRESS24 de votre organe de presse institutionnel",
            "Pour bénéficier de Business Wall for Corporate Media et de l'accès aux fonctionnalités de NEWSROOM (propositions et commandes de sujets, Avis d'enquête digital), vous devrez approuver nos Conditions générales de vente.",
            "Les informations que vous allez saisir seront vérifiées par les équipes d'AiPRESS24.",
        ],
    },
    "union": {
        "name": "Business Wall for Union",
        "description": "Pour les syndicats ou fédérations de la presse ou des médias, clubs de la presse ou associations de journalistes.",
        "free": True,
        "activation_text": "Approuver les CGV de Business Wall sur AiPRESS24",
        "manager_role": "Press Manager",  # Different from other types
        "onboarding_messages": [
            "Votre abonnement gratuit à Business Wall for Union sera la vitrine sur AiPRESS24 de votre syndicat ou fédération de la presse ou des médias, de votre club de la presse ou association de journalistes",
            "Pour bénéficier de Business Wall for Union, vous devrez approuver nos Conditions générales de vente.",
            "Les informations que vous allez saisir seront vérifiées par les équipes d'AiPRESS24.",
            "Vous devez déclarer également déclarer et valider individuellement chaque PR Agency ou chaque PR Consultant qui vous représentent sur AiPRESS24 et peuvent agir en tant que contact presse, publier vos communiqués de presse et vos événements.",
        ],
    },
    "academics": {
        "name": "Business Wall for Academics",
        "description": "Pour les établissements de recherche ou d'enseignement supérieur.",
        "free": True,
        "activation_text": "Approuver les CGV de Business Wall sur AiPRESS24",
        "manager_role": "PR Manager",
        "onboarding_messages": [
            "Votre abonnement gratuit à Business Wall for Academics sera la vitrine sur AiPRESS24 de votre établissement de recherche ou d'enseignement supérieur",
            "Pour bénéficier de Business Wall for Academics, vous devrez approuver nos Conditions générales de vente.",
            "Vous devez déclarer et valider individuellement chaque PR Agency ou chaque PR Consultant qui vous représentent sur AiPRESS24 et peuvent agir en tant que contact presse, publier vos communiqués de presse et vos événements.",
            "Les informations que vous allez saisir seront vérifiées par les équipes d'AiPRESS24.",
        ],
    },
    # Paid BW types (3 types)
    "pr": {
        "name": "Business Wall for PR",
        "description": "Pour les agences de relations presse et les consultants indépendants.",
        "free": False,
        "manager_role": "PR Manager",
        "pricing_field": "client_count",
        "pricing_label": "Nombre de clients représentés",
        "pricing_placeholder": "Ex: 5",
        "onboarding_messages": [
            "Votre abonnement payant à Business Wall for PR sera la vitrine sur AiPRESS24 de votre PR Agency ou de votre activité de PR Consultant indépendant.e",
            "Pour bénéficier de Business Wall for PR, vous devez déclarer le nombre de vos clients que vous représentez sur AiPRESS24 car le tarif de votre abonnement en dépend.",
            "Vous devrez aussi approuver nos Conditions générales de vente.",
            "Vous pourrez représenter vos clients sur AiPRESS24, agir en tant que contact presse, publier leurs communiqués de presse et leurs événements après que chacun de vos clients aura déclaré et validé votre organisation sur AiPRESS24.",
            "Les informations que vous allez saisir seront vérifiées par les équipes d'AiPRESS24.",
        ],
    },
    "leaders_experts": {
        "name": "Business Wall for Leaders & Experts",
        "description": "Pour les entreprises, associations, experts et leaders d'opinion.",
        "free": False,
        "manager_role": "PR Manager",
        "pricing_field": "employee_count",
        "pricing_label": "Nombre de salariés",
        "pricing_placeholder": "Ex: 50",
        "onboarding_messages": [
            "Votre abonnement payant à Business Wall for Leaders & Experts (BW4L&E) sera la vitrine de votre groupe, entreprise privée, administration, ministère ou association sur AiPRESS24",
            "Pour bénéficier du BW4L&E, vous devez déclarer le nombre de vos salariés car le tarif de votre abonnement en dépend.",
            "Vous devrez aussi approuver nos Conditions générales de vente.",
            "Vous devez déclarer et valider individuellement chaque PR Agency ou chaque PR Consultant qui vous représentent sur AiPRESS24 et peuvent agir en tant que contact presse, publier vos communiqués de presse et vos événements.",
            "Les informations que vous allez saisir seront vérifiées par les équipes d'AiPRESS24.",
        ],
    },
    "transformers": {
        "name": "Business Wall for Transformers",
        "description": "Pour les acteurs de l'innovation et de la transformation numérique.",
        "free": False,
        "manager_role": "PR Manager",
        "pricing_field": "employee_count",
        "pricing_label": "Nombre de salariés",
        "pricing_placeholder": "Ex: 20",
        "onboarding_messages": [
            "Votre abonnement payant à Business Wall for Transformers (BW4T) sera la vitrine de votre groupe, entreprise privée, administration, ministère ou association sur AiPRESS24",
            "Pour bénéficier du BW4T, vous devez déclarer le nombre de vos salariés car le tarif de votre abonnement en dépend.",
            "Vous devrez aussi approuver nos Conditions générales de vente.",
            "Vous devez déclarer et valider individuellement chaque PR Agency ou chaque PR Consultant qui vous représentent sur AiPRESS24 et peuvent agir en tant que contact presse, publier vos communiqués de presse et vos événements.",
            "Les informations que vous allez saisir seront vérifiées par les équipes d'AiPRESS24.",
        ],
    },
}
