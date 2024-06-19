# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

# """
# Communicants
# """
# from .base import WizardStep
# from .first import Step0
#
# FREE_PITCH = """
# → Mon profil sera qualifié de **Communicant** dans Aipress24. Je pourrai alors :
#
# - publier gratuitement les communiqués de presse concernant mon organisation ;
# - publier gratuitement les événements presse que j’organise concernant mon organisation ;
# - voir quels journalistes s’inscrivent aux événements de presse que j’organise ;
# - parrainer des inscriptions sur Aipress24 et gagner des points d’indice de performance réputationnelle.
# """
#
# BW_PITCH = """
# → Si je m’abonne au service de **Business Wall** d’Aipress24, je pourrai en plus :
#
# - bénéficier d’un tarif spécial « Communicant » ;
# - vendre mes sujets à des rédacteurs en chef et journalistes qui l’acceptent ;
# - centraliser les sujets que les membres de mon équipe vendent à des rédacteurs en chef et journalistes qui l’acceptent ;
# - recevoir les avis d’enquête de la part des journalistes et accélérer l’organisation des rendez-vous d’interview des membres concernés dans mon organisation ;
# - centraliser les avis d’enquête que reçoivent les membres de mon équipe de la part des journalistes ;
# - voir qui a consulté ou liké les communiqués de presse publiés par mon équipe ;
# - afficher les communiqués de presse concernant mon organisation sur mon profil personnel ;
# - afficher les communiqués de presse sur le BW de mon organisation ;
# - afficher dans mon press-book personnel les justificatifs de publication concernant mon organisation que j’ai achetés ;
# - acheter des justificatifs de publication pour les afficher dans le press-book du BW de mon organisation ;
# - centraliser la vision de toutes mes dépenses sur Aipress24.
# """
#
# PITCH = f"""
# {FREE_PITCH}
#
# {BW_PITCH}
# """
#
#
# class StepCommunicant(WizardStep):
#     title = "Je suis professionnel.le de la communication et des relations presse"
#
#     previous = Step0
#
#
# class StepCommunicantIndependant(WizardStep):
#     title = "Je travaille en tant qu’indépendant.e"
#     postscript_md = PITCH
#
#     previous = StepCommunicant
#
#     questions = [
#         "Voici mes secteurs d’activité (voir la liste des secteurs d’activité):",
#         "Voici mes clients:",
#     ]
#
#
# class StepCommunicantEnAgence(WizardStep):
#     title = "Je travaille dans une agence de relations presse"
#
#     previous = StepCommunicant
#
#
# class StepCommunicantEnAgenceChargeDeCompte(WizardStep):
#     title = "Je suis chargé de comptes"
#     postscript_md = PITCH
#
#     previous = StepCommunicantEnAgence
#
#     questions = [
#         "Voici la société qui m’emploie:",
#         "Voici mes secteurs d’activité (voir la liste des secteurs d’activité):",
#         "Voici mes clients:",
#     ]
#
#
# class StepCommunicantEnAgenceManager(WizardStep):
#     title = "Je dirige une équipe de consultants en relations presse"
#     postscript_md = PITCH
#
#     previous = StepCommunicantEnAgence
#
#     questions = [
#         "Voici la société qui m’emploie:",
#         "Voici mes secteurs d’activité (voir la liste des secteurs d’activité):",
#         "Voici les personnes de mon équipe:",
#         "Voici mes clients:",
#     ]
#
#
# class StepCommunicantEnEntreprise(WizardStep):
#     title = "Je travaille chez un annonceur"
#     postscript_md = PITCH
#
#     previous = StepCommunicant
#
#     questions = [
#         "Voici la société qui m’emploie:",
#         "Voici les personnes de mon équipe:",
#         "Voici mes secteurs d’activité (voir la liste des secteurs d’activité):",
#     ]
#
#
# class StepCommunicantOccasionel(WizardStep):
#     title = "Je suis en charge des relations presse mais ce n’est pas mon activité principale"
#
#     previous = StepCommunicant
#
#
# class StepCommunicantOccasionelEnEntreprise(WizardStep):
#     title = "Je travaille au sein du département Marketing de mon organisation"
#     postscript_md = PITCH
#
#     previous = StepCommunicantOccasionel
#
#     questions = [
#         "Voici la société qui m’emploie:",
#         "Voici les personnes de mon équipe:",
#         "Voici mes secteurs d’activité (voir la liste des secteurs d’activité):",
#     ]
#
#
# class StepCommunicantBenevole(WizardStep):
#     title = "Je travaille bénévolement au sein d’une association"
#     postscript_md = PITCH
#
#     previous = StepCommunicantOccasionel
#
#     questions = [
#         "Voici l'association qui m’emploie:",
#         "Voici les personnes de mon équipe:",
#         "Voici mes secteurs d’activité (voir la liste des secteurs d’activité):",
#     ]
