# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

# from app.modules.kyc.wizards.base import WizardStep
# from app.modules.kyc.wizards.first import Step0
#
#
# class StepJournaliste(WizardStep):
#     title = "Je suis journaliste professionnel"
#
#     previous = Step0
#
#
# TEXT_JOURNALISTE_PROFESSIONNEL_AVEC_CARTE_DE_PRESSE = """
# → Après vérification par l’équipe d’Aipress24, mon profil sera qualifié de **Journaliste** dans Aipress24.
#
# Selon mon profil, je pourrai:
#
# - vendre mes sujets à des rédacteurs en chef qui l’acceptent;
# - recevoir des propositions de sujets à couvrir;
# - accéder à la centralisation des invitations de presse et autres événements;
# - commander des sujets aux journalistes de ma rédaction ou à des pigistes;
# - commander des piges aux journalistes qui s’inscrivent à des événements auxquels ma rédaction ne peut participer;
# - lancer des avis d’enquête pour accélérer mes prises de contact et mes rendez-vous d’interview;
# - publier mes articles rémunérés à la consultation et au partage groupé;
# - publier mes justificatifs de publication rémunérés;
# - vendre mes droits d’auteur;
# - vendre mes formations au journalisme;
# - centraliser la vision de toutes mes ventes;
# - centraliser la vision de toutes les ventes de ma rédaction;
# - inscrire collectivement tous les journalistes de ma rédaction;
# - parrainer des inscriptions sur Aipress24 et gagner des points d’indice de performance réputationnelle;
# - parrainer la vente d’abonnements à BW et toucher des commissions régulières;
# - passer ou répondre à des annonces de missions ponctuelles (piges) à des journalistes;
# - passer ou répondre à des appels à projets auprès d’agence de presse pour des collaborations à moyen ou long termes;
# - passer ou répondre à des appels à projets pour la création de médias;
# - passer ou répondre à des appels à projets d’innovation.
# """
#
#
# class StepJournalisteProfessionnelAvecCarteDePresse(WizardStep):
#     title = "Je suis journaliste professionnel titulaire d’une carte de presse à jour"
#     test = TEXT_JOURNALISTE_PROFESSIONNEL_AVEC_CARTE_DE_PRESSE
#
#     previous = StepJournaliste
#
#     questions = [
#         "Quel est votre numéro de carte de presse ?",
#         "Téléversez la photo JPEG de votre carte de presse",
#     ]
#
#
# TEXT_JOURNALISTE_HONORAIRE_AVEC_CARTE_DE_PRESSE = """
# → Après vérification, mon profil sera qualifié de **Journaliste** dans Aipress24. Je pourrai alors:
#
# - vendre mes sujets à des rédacteurs en chef qui l’acceptent;
# - recevoir des propositions de sujets à couvrir;
# - accéder à la centralisation des invitations de presse et autres événements;
# - lancer des avis d’enquête pour accélérer mes prises de contact et mes rendez-vous d’interview;
# - publier mes articles rémunérés à la consultation et au partage groupé;
# - publier mes justificatifs de publication rémunérés;
# - vendre mes droits d’auteur;
# - vendre mes formations au journalisme;
# - centraliser la vision de toutes mes ventes sur Aipress24;
# - centraliser la vision de toutes les ventes de la rédaction sur Aipress24;
# - parrainer des inscriptions sur Aipress24 et gagner des points d’indice de performance réputationnelle;
# - parrainer la vente d’abonnements à BW et toucher des commissions régulières;
# - passer ou répondre à des appels à projets auprès d’agence de presse pour des collaborations à moyen ou long termes;
# - passer ou répondre à des appels à projets pour la création de médias;
# - passer ou répondre à des appels à projets d’innovation.
# """
#
#
# class StepJournalisteHonoraireAvecCarteDePresse(WizardStep):
#     title = "Je suis journaliste honoraire titulaire d’une carte de presse"
#     postscript_md = TEXT_JOURNALISTE_HONORAIRE_AVEC_CARTE_DE_PRESSE
#
#     previous = StepJournaliste
#
#     questions = [
#         "Quel est votre numéro de carte de presse ?",
#         "Téléversez la photo JPEG de votre carte de presse",
#     ]
#
#
# class StepJournalisteSansCarteDePresse(WizardStep):
#     title = "Je suis journaliste professionnel non titulaire d’une carte de presse"
#
#     previous = StepJournaliste
#
#     questions = [
#         "Indiquez les médias:",
#     ]
#
#
# TEXT_JOURNALISTE_SANS_CARTE_DE_PRESSE = """
# → Après vérification, mon profil sera qualifié de **Journaliste** dans Aipress24. Je pourrai alors :
#
# - demander aux rédacteurs en chef pour lesquels je travaille de parrainer mon inscription sur Aipress24;
# - vendre mes sujets à des rédacteurs en chef qui l’acceptent;
# - recevoir des propositions de sujets à couvrir;
# - accéder à la centralisation des invitations de presse et autres événements;
# - lancer des avis d’enquête pour accélérer mes prises de contact et mes rendez-vous d’interview;
# - publier mes articles rémunérés à la consultation et au partage groupé;
# - publier mes justificatifs de publication rémunérés;
# - vendre mes droits d’auteur;
# - vendre mes formations au journalisme;
# - centraliser la vision de toutes mes ventes sur Aipress24;
# - parrainer des inscriptions sur Aipress24 et gagner des points d’indice de performance réputationnelle;
# - parrainer la vente d’abonnements à BW et toucher des commissions régulières.
# """
#
#
# class StepVraiJournalisteSansCarteDePresse(WizardStep):
#     title = "Je gagne ma vie principalement en publiant des articles, photos, vidéos, podcasts dans un ou plusieurs médias certifiés par la CPPAP ou l'Arcom"
#     postscript_md = TEXT_JOURNALISTE_SANS_CARTE_DE_PRESSE
#
#     previous = StepJournalisteSansCarteDePresse
#
#     questions = [
#         "Indiquez les médias:",
#     ]
#
#
# TEXT_JOURNALISTE_INSTITUTIONNEL = """
# → Mon profil sera qualifié de **Communicant** dans Aipress24. Je pourrai alors:
#
# - vendre mes sujets à des rédacteurs en chef qui l’acceptent;
# - recevoir des propositions de sujets à couvrir;
# - solliciter des accréditations pour assister à des conférences de presse et autres événements, selon l’appréciation de l’organisateur;
# - lancer des avis d’enquête pour accélérer mes prises de contact et mes rendez-vous d’interview;
# - parrainer des inscriptions sur Aipress24 et gagner des points d’indice de performance réputationnelle;
# - parrainer la vente d’abonnements à BW et toucher des commissions régulières.
# """
#
#
# class StepJournalisteInstitutionnel(WizardStep):
#     title = "Je suis journaliste d’entreprise pour des médias institutionnels (non certifiés par la CPPAP ou l’Arcom)"
#
#     postscript_md = TEXT_JOURNALISTE_INSTITUTIONNEL
#
#     previous = StepJournalisteSansCarteDePresse
#
#     questions = [
#         "Indiquez les médias:",
#     ]
#
#
# TEXT_EXPERT = """
# → Mon profil sera qualifié d’**Expert** dans Aipress24. Je pourrai alors:
#
# - vendre mes sujets à des rédacteurs en chef qui l’acceptent;
# - recevoir des propositions de sujets à couvrir;
# - solliciter des accréditations pour assister à des conférences de presse et autres événements, selon l’appréciation de l’organisateur;
# - lancer des avis d’enquête pour accélérer mes prises de contact et mes rendez-vous d’interview;
# - parrainer des inscriptions sur Aipress24 et gagner des points d’indice de performance réputationnelle;
# - parrainer la vente d’abonnements à BW et toucher des commissions régulières.
# """
#
#
# class StepExpert(WizardStep):
#     title = "Je suis expert dans un domaine précis et j’interviens occasionnellement dans des rédactions"
#     postscript_md = TEXT_EXPERT
#
#     previous = StepJournalisteSansCarteDePresse
#
#     questions = [
#         "Indiquez votre domaine d’expertise:",
#         "Indiquez les médias:",
#     ]
