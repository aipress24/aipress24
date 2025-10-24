# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

# from __future__ import annotations
# import json
# from collections import Counter
# from importlib import resources as rso

# from app.modules.kyc.ontologies import (
#     ONTOLOGY_MAP,
#     ontology_for_pays,
#     zip_code_city_list,
# )

# DATA_MODULE = "app.modules.kyc.data"


# def _read_content(ontology: str) -> list | dict:
#     filename = f"{ontology}.json"
#     return json.loads(rso.files(DATA_MODULE).joinpath(filename).read_text())


# def unicity_keys(content: list) -> bool:
#     test = {item[0] for item in content}
#     if len(test) == len(content):
#         return True
#     test_list = [item[0] for item in content]
#     counter = {item for item in Counter(test_list).items() if item[1] > 1}
#     print(counter)
#     return False


# def total_values(content: dict) -> int:
#     field1 = content["field1"]
#     field2 = content["field2"]
#     return sum(len(field2[item[0]]) for item in field1)


# def test_all_files_exist():
#     for ontology in ONTOLOGY_MAP.values():
#         filename = f"{ontology}.json"
#         assert rso.files(DATA_MODULE).joinpath(filename).is_file()


# def test_civilite():
#     content = _read_content("civilite")
#     assert isinstance(content, list)
#     assert len([item for item in content if not isinstance(item, list)]) == 0
#     assert len([item for item in content if not item]) == 0
#     assert content[0] == ["Monsieur", "Monsieur"]
#     assert content[-1] == ["Non renseigné", "Non renseigné"]
#     assert len(content) == 3
#     assert unicity_keys(content)


# def test_newsrooms_broken_title():
#     def _no_bad_newsroom_name(content: list) -> bool:
#         return all(not room[0].endswith("Type de média") for room in content)

#     assert _no_bad_newsroom_name(_read_content("newsrooms"))


# def test_newsrooms():
#     content = _read_content("newsrooms")
#     assert isinstance(content, list)
#     assert len([item for item in content if not isinstance(item, list)]) == 0
#     assert len([item for item in content if not item]) == 0
#     assert content[0] == ["01 Net;Presse", "01 Net (Presse)"]
#     assert content[-1] == ["Îl(e)s;Presse", "Îl(e)s (Presse)"]
#     assert len(content) == 1900
#     assert unicity_keys(content)


# def test_medias():
#     content = _read_content("medias")
#     assert isinstance(content, list)
#     assert len([item for item in content if not isinstance(item, list)]) == 0
#     assert len([item for item in content if not item]) == 0
#     assert content[0] == ["Agence de presse", "Agence de presse"]
#     assert content[-1] == ["Autres", "Autres"]
#     assert len(content) == 42
#     assert unicity_keys(content)


# def test_media_type():
#     content = _read_content("media_type")
#     assert isinstance(content, list)
#     assert len([item for item in content if not isinstance(item, list)]) == 0
#     assert len([item for item in content if not item]) == 0
#     assert content[0] == ["Presse culturelle", "Presse culturelle"]
#     assert content[-1] == ["Autres", "Autres"]
#     assert len(content) == 11
#     assert unicity_keys(content)


# def test_journalisme_fonction():
#     content = _read_content("journalisme_fonction")
#     assert isinstance(content, list)
#     assert len([item for item in content if not isinstance(item, list)]) == 0
#     assert len([item for item in content if not item]) == 0
#     assert content[0] == ["Caméraman", "Caméraman"]
#     assert content[-1] == ["Autres", "Autres"]
#     assert content[-2] == ["Webmaster", "Webmaster"]
#     assert len(content) == 84
#     assert unicity_keys(content)


# def test_agence_rp():
#     content = _read_content("agence_rp")
#     assert isinstance(content, list)
#     assert len([item for item in content if not isinstance(item, list)]) == 0
#     assert len([item for item in content if not item]) == 0
#     assert content[0] == ["01MARS (PARIS)", "01MARS (PARIS)"]
#     assert content[-1] == [
#         "zi-agency (LA CHAPELLE SUR ERDRE)",
#         "zi-agency (LA CHAPELLE SUR ERDRE)",
#     ]
#     assert len(content) == 6982
#     assert unicity_keys(content)


# def test_type_agence_rp():
#     content = _read_content("type_agence_rp")
#     assert isinstance(content, list)
#     assert len([item for item in content if not isinstance(item, list)]) == 0
#     assert len([item for item in content if not item]) == 0
#     assert content[0] == [
#         "Agence de relations presse artistique",
#         "Agence de relations presse artistique",
#     ]
#     assert content[-1] == ["Autres", "Autres"]
#     assert content[-2] == [
#         "Agence de relations presse sportive",
#         "Agence de relations presse sportive",
#     ]
#     assert len(content) == 18
#     assert unicity_keys(content)


# def test_organisation():
#     content = _read_content("organisation")
#     assert isinstance(content, dict)
#     assert len(content) == 2
#     field1 = content["field1"]
#     field2 = content["field2"]

#     assert isinstance(field1, list)
#     assert len([item for item in field1 if not isinstance(item, list)]) == 0
#     assert len([item for item in field1 if not item]) == 0

#     assert isinstance(field2, dict)
#     assert len([item for item in field2 if not isinstance(item, str)]) == 0
#     assert len([item for item in field2.values() if not isinstance(item, list)]) == 0

#     assert field1[0] == [
#         "ORGANISATIONS POLITIQUES & ADMINISTRATIVES",
#         "ORGANISATIONS POLITIQUES & ADMINISTRATIVES",
#     ]
#     assert field1[-1] == [
#         "ASSOCIATIONS, FÉDÉRATIONS & SYNDICATS",
#         "ASSOCIATIONS, FÉDÉRATIONS & SYNDICATS",
#     ]
#     assert len(field1) == 3
#     assert len(field2) == len(field1)

#     key = "ORGANISATIONS POLITIQUES & ADMINISTRATIVES"
#     assert field2[key][0] == [
#         "ORGANISATIONS POLITIQUES & ADMINISTRATIVES;Administration publique",
#         "ORGANISATIONS POLITIQUES & ADMINISTRATIVES / Administration publique",
#     ]
#     assert len(field2[key]) == 123

#     key = "ASSOCIATIONS, FÉDÉRATIONS & SYNDICATS"
#     assert field2[key][-1] == [
#         "ASSOCIATIONS, FÉDÉRATIONS & SYNDICATS;Autres",
#         "ASSOCIATIONS, FÉDÉRATIONS & SYNDICATS / Autres",
#     ]
#     assert len(field2[key]) == 47
#     assert total_values(content) == 340


# def test_taille_organisation():
#     content = _read_content("taille_organisation")
#     assert isinstance(content, list)
#     assert len([item for item in content if not isinstance(item, list)]) == 0
#     assert len([item for item in content if not item]) == 0
#     assert content[0] == ["1", "1"]
#     assert content[-1] == ["+", "+"]
#     assert content[-2] == ["1000000", "1000000"]
#     assert len(content) == 10
#     assert unicity_keys(content)


# def test_profession_fonction_public():
#     content = _read_content("profession_fonction_public")
#     assert isinstance(content, dict)
#     assert len(content) == 2
#     field1 = content["field1"]
#     field2 = content["field2"]

#     assert isinstance(field1, list)
#     assert len([item for item in field1 if not isinstance(item, list)]) == 0
#     assert len([item for item in field1 if not item]) == 0

#     assert isinstance(field2, dict)
#     assert len([item for item in field2 if not isinstance(item, str)]) == 0
#     assert len([item for item in field2.values() if not isinstance(item, list)]) == 0

#     assert field1[0] == ["PRÉSIDENCE DE LA RÉPUBLIQUE", "PRÉSIDENCE DE LA RÉPUBLIQUE"]
#     assert field1[-1] == ["SÉCURITÉ CIVILE", "SÉCURITÉ CIVILE"]
#     assert len(field1) == 13
#     assert len(field2) == len(field1)

#     key = "PRÉSIDENCE DE LA RÉPUBLIQUE"
#     assert field2[key][0] == [
#         "PRÉSIDENCE DE LA RÉPUBLIQUE;Président de la République",
#         "PRÉSIDENCE DE LA RÉPUBLIQUE / Président de la République",
#     ]
#     assert len(field2[key]) == 21

#     key = "SANTÉ PUBLIQUE"
#     assert field2[key][-1] == ["SANTÉ PUBLIQUE;Autres", "SANTÉ PUBLIQUE / Autres"]
#     assert len(field2[key]) == 41
#     assert total_values(content) == 410


# def test_profession_fonction_prive():
#     content = _read_content("profession_fonction_prive")
#     assert isinstance(content, dict)
#     assert len(content) == 2
#     field1 = content["field1"]
#     field2 = content["field2"]

#     assert isinstance(field1, list)
#     assert len([item for item in field1 if not isinstance(item, list)]) == 0
#     assert len([item for item in field1 if not item]) == 0

#     assert isinstance(field2, dict)
#     assert len([item for item in field2 if not isinstance(item, str)]) == 0
#     assert len([item for item in field2.values() if not isinstance(item, list)]) == 0

#     assert field1[0] == ["DIRECTION GÉNÉRALE", "DIRECTION GÉNÉRALE"]
#     assert field1[-1] == ["DIRECTION TRANSPORTS", "DIRECTION TRANSPORTS"]
#     assert len(field1) == 23
#     assert len(field2) == len(field1)

#     key = "DIRECTION GÉNÉRALE"
#     assert field2[key][0] == [
#         "DIRECTION GÉNÉRALE;Co-fondatreur.trice",
#         "DIRECTION GÉNÉRALE / Co-fondatreur.trice",
#     ]
#     assert len(field2[key]) == 15

#     key = "DIRECTION TRANSPORTS"
#     assert field2[key][-1] == [
#         "DIRECTION TRANSPORTS;Autres",
#         "DIRECTION TRANSPORTS / Autres",
#     ]
#     assert len(field2[key]) == 24
#     assert total_values(content) == 562


# def test_profession_fonction_asso():
#     content = _read_content("profession_fonction_asso")
#     assert isinstance(content, dict)
#     assert len(content) == 2
#     field1 = content["field1"]
#     field2 = content["field2"]

#     assert isinstance(field1, list)
#     assert len([item for item in field1 if not isinstance(item, list)]) == 0
#     assert len([item for item in field1 if not item]) == 0

#     assert isinstance(field2, dict)
#     assert len([item for item in field2 if not isinstance(item, str)]) == 0
#     assert len([item for item in field2.values() if not isinstance(item, list)]) == 0

#     assert field1[0] == ["Direction", "Direction"]
#     assert field1[-1] == ["Représentations", "Représentations"]
#     assert len(field1) == 4
#     assert len(field2) == len(field1)

#     key = "Direction"
#     assert field2[key][0] == [
#         "Direction;Coordinateur.trice",
#         "Direction / Coordinateur.trice",
#     ]
#     assert len(field2[key]) == 13

#     key = "Représentations"
#     assert field2[key][-1] == [
#         "Représentations;Représentant.e syndical.e européen.ne",
#         "Représentations / Représentant.e syndical.e européen.ne",
#     ]
#     assert len(field2[key]) == 5
#     assert total_values(content) == 44


# def test_pays():
#     content = _read_content("pays")
#     assert isinstance(content, list)
#     assert len([item for item in content if not isinstance(item, list)]) == 0
#     assert len([item for item in content if not item]) == 0
#     assert content[0] == ["FRA", "France"]
#     assert content[-1] == ["MHL", "Îles Marshall"]
#     assert content[-2] == ["MNP", "Îles Mariannes du Nord"]
#     assert len(content) == 81
#     assert unicity_keys(content)


# def test_secteur_detaille():
#     content = _read_content("secteur_detaille")
#     assert isinstance(content, dict)
#     assert len(content) == 2
#     field1 = content["field1"]
#     field2 = content["field2"]

#     assert isinstance(field1, list)
#     assert len([item for item in field1 if not isinstance(item, list)]) == 0
#     assert len([item for item in field1 if not item]) == 0

#     assert isinstance(field2, dict)
#     assert len([item for item in field2 if not isinstance(item, str)]) == 0
#     assert len([item for item in field2.values() if not isinstance(item, list)]) == 0

#     assert field1[0] == ["ADMINISTRATION PUBLIQUE", "ADMINISTRATION PUBLIQUE"]
#     assert field1[-1] == ["Autres", "Autres"]
#     assert len(field1) == 62
#     assert len(field2) == len(field1)

#     key = "ADMINISTRATION PUBLIQUE"
#     assert field2[key][0] == [
#         "ADMINISTRATION PUBLIQUE;Affaires maritimes",
#         "ADMINISTRATION PUBLIQUE / Affaires maritimes",
#     ]
#     assert len(field2[key]) == 45

#     key = "Autres"
#     assert not field2[key]
#     assert total_values(content) == 2566


# def test_interet_politique():
#     content = _read_content("interet_politique")
#     assert isinstance(content, dict)
#     assert len(content) == 2
#     field1 = content["field1"]
#     field2 = content["field2"]

#     assert isinstance(field1, list)
#     assert len([item for item in field1 if not isinstance(item, list)]) == 0
#     assert len([item for item in field1 if not item]) == 0

#     assert isinstance(field2, dict)
#     assert len([item for item in field2 if not isinstance(item, str)]) == 0
#     assert len([item for item in field2.values() if not isinstance(item, list)]) == 0

#     assert field1[0] == ["Présidence de la République", "Présidence de la République"]
#     assert field1[-1] == ["Santé publique", "Santé publique"]
#     assert len(field1) == 11
#     assert len(field2) == len(field1)

#     key = "Présidence de la République"
#     assert field2[key][0] == [
#         "Présidence de la République;Agenda politique",
#         "Présidence de la République / Agenda politique",
#     ]
#     assert len(field2[key]) == 38

#     key = "Santé publique"
#     assert field2[key][-1] == ["Santé publique;Autres", "Santé publique / Autres"]
#     assert len(field2[key]) == 21
#     assert total_values(content) == 330


# def test_interet_orga():
#     content = _read_content("interet_orga")
#     assert isinstance(content, dict)
#     assert len(content) == 2
#     field1 = content["field1"]
#     field2 = content["field2"]

#     assert isinstance(field1, list)
#     assert len([item for item in field1 if not isinstance(item, list)]) == 0
#     assert len([item for item in field1 if not item]) == 0

#     assert isinstance(field2, dict)
#     assert len([item for item in field2 if not isinstance(item, str)]) == 0
#     assert len([item for item in field2.values() if not isinstance(item, list)]) == 0

#     assert field1[0] == ["Direction générale", "Direction générale"]
#     assert field1[-1] == ["Direction Publicité", "Direction Publicité"]
#     assert len(field1) == 20
#     assert len(field2) == len(field1)

#     key = "Direction générale"
#     assert field2[key][0] == [
#         "Direction générale;Vision et stratégie",
#         "Direction générale / Vision et stratégie",
#     ]
#     assert len(field2[key]) == 25

#     key = "Direction Publicité"
#     assert field2[key][-1] == [
#         "Direction Publicité;Autres",
#         "Direction Publicité / Autres",
#     ]
#     assert len(field2[key]) == 20
#     assert total_values(content) == 494


# def test_interet_asso():
#     content = _read_content("interet_asso")
#     assert isinstance(content, dict)
#     assert len(content) == 2
#     field1 = content["field1"]
#     field2 = content["field2"]

#     assert isinstance(field1, list)
#     assert len([item for item in field1 if not isinstance(item, list)]) == 0
#     assert len([item for item in field1 if not item]) == 0

#     assert isinstance(field2, dict)
#     assert len([item for item in field2 if not isinstance(item, str)]) == 0
#     assert len([item for item in field2.values() if not isinstance(item, list)]) == 0

#     assert field1[0] == ["Associations", "Associations"]
#     assert field1[-1] == ["Syndicats professionnels", "Syndicats professionnels"]
#     assert len(field1) == 9
#     assert len(field2) == len(field1)

#     key = "Associations"
#     assert field2[key][0] == [
#         "Associations;Actions humanitaires",
#         "Associations / Actions humanitaires",
#     ]
#     assert len(field2[key]) == 21

#     key = "Syndicats professionnels"
#     assert field2[key][-1] == [
#         "Syndicats professionnels;Autres",
#         "Syndicats professionnels / Autres",
#     ]
#     assert len(field2[key]) == 21
#     assert total_values(content) == 193


# def test_transformation_majeure():
#     content = _read_content("transformation_majeure")
#     assert isinstance(content, dict)
#     assert len(content) == 2
#     field1 = content["field1"]
#     field2 = content["field2"]

#     assert isinstance(field1, list)
#     assert len([item for item in field1 if not isinstance(item, list)]) == 0
#     assert len([item for item in field1 if not item]) == 0

#     assert isinstance(field2, dict)
#     assert len([item for item in field2 if not isinstance(item, str)]) == 0
#     assert len([item for item in field2.values() if not isinstance(item, list)]) == 0

#     assert field1[0] == ["TRANSITION ARTISTIQUE", "TRANSITION ARTISTIQUE"]
#     assert field1[-1] == ["TRANSITION TECHNOLOGIQUE", "TRANSITION TECHNOLOGIQUE"]
#     assert len(field1) == 12
#     assert len(field2) == len(field1)

#     key = "TRANSITION ARTISTIQUE"
#     assert field2[key][0] == [
#         "TRANSITION ARTISTIQUE;Accessibilité",
#         "TRANSITION ARTISTIQUE / Accessibilité",
#     ]
#     assert len(field2[key]) == 21

#     key = "TRANSITION TECHNOLOGIQUE"
#     assert field2[key][-1] == [
#         "TRANSITION TECHNOLOGIQUE;Autres",
#         "TRANSITION TECHNOLOGIQUE / Autres",
#     ]
#     assert len(field2[key]) == 43
#     assert total_values(content) == 293


# def test_metier():
#     content = _read_content("metier")
#     assert isinstance(content, dict)
#     assert len(content) == 2
#     field1 = content["field1"]
#     field2 = content["field2"]

#     assert isinstance(field1, list)
#     assert len([item for item in field1 if not isinstance(item, list)]) == 0
#     assert len([item for item in field1 if not item]) == 0

#     assert isinstance(field2, dict)
#     assert len([item for item in field2 if not isinstance(item, str)]) == 0
#     assert len([item for item in field2.values() if not isinstance(item, list)]) == 0

#     assert field1[0] == ["ADMIN.PUBLIQUE", "ADMIN.PUBLIQUE"]
#     assert field1[-1] == ["Autres", "Autres"]
#     assert len(field1) == 49
#     # BUG for "metier" ontology, double declaration for "PRESSE & MÉDIAS"
#     assert len(field2) == len(field1)

#     key = "ADMIN.PUBLIQUE"
#     assert field2[key][0] == [
#         "ADMIN.PUBLIQUE;Agent.e de développement économique",
#         "ADMIN.PUBLIQUE / Agent.e de développement économique",
#     ]
#     assert len(field2[key]) == 49

#     key = "Autres"
#     assert not field2[key]
#     assert total_values(content) == 1870


# def test_journalisme_competence():
#     content = _read_content("journalisme_competence")
#     assert isinstance(content, list)
#     assert len([item for item in content if not isinstance(item, list)]) == 0
#     assert len([item for item in content if not item]) == 0
#     assert content[0] == [
#         "Concevoir et gérer la ligne éditoriale du média",
#         "Concevoir et gérer la ligne éditoriale du média",
#     ]
#     assert content[-1] == [
#         "Gestion de plateau audiovisuel",
#         "Gestion de plateau audiovisuel",
#     ]
#     assert len(content) == 18
#     assert unicity_keys(content)


# def test_competence():
#     content = _read_content("competence")
#     assert isinstance(content, list)
#     assert len([item for item in content if not isinstance(item, list)]) == 0
#     assert len([item for item in content if not item]) == 0
#     assert content[0] == ["Analyse de mon secteur", "Analyse de mon secteur"]
#     assert content[-1] == [
#         "Partage de bonnes pratiques (RSE, techniques, etc.)",
#         "Partage de bonnes pratiques (RSE, techniques, etc.)",
#     ]
#     assert len(content) == 15
#     assert unicity_keys(content)


# def test_langue():
#     content = _read_content("langue")
#     assert isinstance(content, list)
#     assert len([item for item in content if not isinstance(item, list)]) == 0
#     assert len([item for item in content if not item]) == 0
#     assert content[0] == ["Français", "Français"]
#     assert content[-1] == ["Zoulou", "Zoulou"]
#     assert len(content) == 180
#     assert unicity_keys(content)


# def test_pays_fra():
#     pays = ontology_for_pays()
#     items = [item for item in pays if item[1] == "France"]
#     assert len(items) == 1
#     assert items[0][0] == "FRA"


# def test_pays_deu():
#     pays = ontology_for_pays()
#     items = [item for item in pays if item[0] == "DEU"]
#     assert len(items) == 1
#     assert items[0][1] == "Allemagne"


# def test_zip_france_nb_city():
#     zip_cities = zip_code_city_list("FRA")
#     assert len(zip_cities) == 37262


# def test_zip_allemagne_nb_city():
#     zip_cities = zip_code_city_list("DEU")
#     assert len(zip_cities) == 16477


# def test_zip_italie_nb_city():
#     zip_cities = zip_code_city_list("ITA")
#     assert len(zip_cities) == 18415


# def test_zip_france_paris():
#     zip_cities = zip_code_city_list("FRA")
#     all_paris = [city for city in zip_cities if city["label"].endswith(" Paris")]
#     assert len(all_paris) == 22
#     for zip in ("FRA;75001 ", "FRA;75018 ", "FRA;75020 "):
#         arrond = [item for item in all_paris if item["value"].startswith(zip)]
#         assert len(arrond) == 1
