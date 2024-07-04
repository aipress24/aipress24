# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import json
from operator import itemgetter
from pathlib import Path
from typing import Any

ONTOLOGY_FILENAME = {
    "agence_rp": "agencesrp.json",
    "civilite": "civilite.json",
    "competence": "competencesexperts.json",
    "interet_asso": "centres-d-interet-associations.json",
    "interet_orga": "centres-d-interet-organisations.json",
    "interet_politique": "centres-d-interet-politiques-ad.json",
    "journalisme_competence": "competences-en-journalisme.json",
    "journalisme_fonction": "fonctions-du-journalisme.json",
    "langue": "langues.json",
    "media_type": "types-de-presse-medias.json",
    "medias": "types-dentreprises-de-presse.json",
    "metier": "metiers.json",
    "newsrooms": "newsrooms.json",
    "organisation": "types-dorganisation.json",
    "pays": "pays.json",
    "profession_fonction_asso": "fonctions-associations-syndicat.json",
    "profession_fonction_prive": "fonctions-organisations-privees.json",
    "profession_fonction_public": "fonctions-politiques-administra.json",
    "secteur_detaille": "secteurs-detailles.json",
    "taille_organisation": "tailles-dorganisation.json",
    "transformation_majeure": "trasnitions-majeures.json",
    "type_agence_rp": "types-agences-rp.json",
}

VALUE_LABEL_MODE = False


def convert_ontologies_to_select() -> None:  # noqa: PLR0915
    for ontology in ONTOLOGY_FILENAME:
        match ontology:
            case "civilite":
                converter = CiviliteConverter()

            case "newsrooms":
                converter = NewsroomsConverter()

            case "medias":
                converter = MediasConverter()

            case "media_type":
                converter = MediaTypeConverter()

            case "journalisme_fonction":
                converter = JournalismeFonctionConverter()

            case "agence_rp":
                converter = AgenceRPFonctionConverter()

            case "type_agence_rp":
                converter = TypeAgenceRPFonctionConverter()

            case "organisation":
                converter = OrganisationConverter()

            case "taille_organisation":
                converter = TailleOrganisationConverter()

            case "profession_fonction_public":
                converter = FonctionPublicConverter()

            case "profession_fonction_prive":
                converter = FonctionPriveConverter()

            case "profession_fonction_asso":
                converter = FonctionAssoConverter()

            case "secteur_detaille":
                converter = SecteurDetailleConverter()

            case "interet_politique":
                converter = InteretPolitiqueConverter()

            case "interet_orga":
                converter = InteretOrgaConverter()

            case "interet_asso":
                converter = InteretAssoConverter()

            case "metier":
                converter = MetierConverter()

            case "journalisme_competence":
                converter = JournalismeCompetenceConverter()

            case "competence":
                converter = CompetenceConverter()

            case "langue":
                converter = LangueConverter()

            case "pays":
                converter = PaysConverter()

            case "transformation_majeure":
                converter = TransitionMajeureConverter()

            case _:
                converter = None
        if converter:
            converter.run()
        else:
            print(f"Warning: no converter for {ontology}")


class BaseConvert:
    ontology: str = "ontology_name"
    onto_source_dir: Path = Path("./ontology_json")
    extra_source_dir: Path = Path("./extra_json")
    towns_source_dir: Path = Path("./extra_json/towns")
    dest_dir: Path = Path("./data")

    def __init__(self) -> None:
        """Note: _buffer is dict type for the dual special case."""
        self._buffer: list | dict = []

    def run(self) -> None:
        print(f"{self.ontology} generation")
        self.read_json()
        self.strip_content()
        self.generate()
        self.sort()
        self.save()

    def sort_per_label(self) -> None:
        if VALUE_LABEL_MODE:
            self._buffer = sorted(self._buffer, key=itemgetter("label"))
        else:
            self._buffer = sorted(self._buffer, key=itemgetter(1))

    def no_sort(self) -> None:
        pass

    sort = no_sort

    def _read_json_base_content(self) -> dict | list:
        src_file = ONTOLOGY_FILENAME[self.ontology]
        src = self.extra_source_dir / src_file
        # first try geoloc and extra files
        if not src.is_file():
            src = self.onto_source_dir / src_file
        if not src.is_file():
            raise FileNotFoundError(src)
        return json.loads(src.read_text())

    def read_json_content(self) -> None:
        content = self._read_json_base_content()
        if isinstance(content, dict):
            self._buffer = content["table"]
        else:
            raise TypeError
        print(f"  read {len(self._buffer)} lines")

    read_json = read_json_content

    def read_json_list_content(self) -> None:
        content = self._read_json_base_content()
        if isinstance(content, list):
            self._buffer = content
        else:
            raise TypeError
        print(f"  read {len(self._buffer)} lines")

    @staticmethod
    def strip(item: Any) -> str:
        if not item:
            return ""
        return str(item).strip()

    def strip_content_all(self) -> None:
        """Simple list
        - take first item of line as the name
        - some line can be empty

        civilite journalisme_fonction media_type
        """
        self._buffer = [self.strip(line[0]) for line in self._buffer if line]
        self._buffer = [item for item in self._buffer if item]

    strip_content = strip_content_all

    def strip_content_no_first(self) -> None:
        """Simple list no first line
        - remove First line (headers)
        - take first item of line as the name
        - some line can be empty
        """
        self._buffer = [self.strip(line[0]) for line in self._buffer[1:] if line]
        self._buffer = [item for item in self._buffer if item]

    def strip_content_no_first_newsrooms(self) -> None:
        """Simple list no first line
        - remove First line (headers)
        - take first item of line as the name
        - some line can be empty
        - keep the 2 first fields to insure unicity of keys
        """
        self._buffer = [
            (self.strip(line[0]), self.strip(line[1])) for line in self._buffer if line
        ]
        self._buffer = [item for item in self._buffer if item]
        self._buffer = [
            item
            for item in self._buffer
            if not item[1].strip().lower().startswith("Type de")
        ]

    def strip_content_second(self) -> None:
        """Second item in list
        - take 2nd item of line if exist
        - some line could be empty
        - some value may be null

        medias taille_organisation
        """
        self._buffer = [self.strip(line[1]) for line in self._buffer if len(line) > 1]
        self._buffer = [item for item in self._buffer if item]

    def strip_content_agence(self) -> None:
        """For agence_rp list
        - format: "name (ville)"
        - drop first line (header"denomination" "ville" )
        - take first item of line if exist as name
        - take second item of line if exist as town
        - some line could be empty
        - dont use missing name line

        agence_rp
        """
        result = []
        for line in self._buffer[1:]:
            if not line:
                continue
            name = ""
            if len(line) > 0:
                name = self.strip(line[0])
            if not name:
                continue
            town = ""
            if len(line) > 1:
                town = self.strip(line[1])
            if town:
                result.append(f"{name} ({town})")
            else:
                result.append(f"{name}")
        self._buffer = result

    def strip_content_optgroup(self) -> None:
        """For optgroup lists
        - use optgroup
        - take second item of line if exist
        - item can be null
        - some line could be empty

        return format list of list:
            [
              [optgroup,[label, label2, label3...]]
              ...
            ]

        organisation
        """
        current_optgroup: str = ""
        group_list: list[str] = []
        result = []
        for line in self._buffer:
            if not line:
                continue
            group = ""
            if len(line) > 0:
                group = self.strip(line[0])
            if group:
                # close previous group
                if current_optgroup:
                    result.append([current_optgroup, group_list])
                # clean list
                group_list = []
                # store new group
                current_optgroup = group
                continue
            # expect a value on 2nd column
            if len(line) > 1:
                value = self.strip(line[1])
                if value:
                    group_list.append(value)

        if current_optgroup:
            result.append([current_optgroup, group_list])

        self._buffer = result

    def strip_filter_country(self) -> None:
        """Filter list of country to keep only countries with existing
        zip code list.
        """
        filtered = []
        if not self.towns_source_dir.is_dir():
            raise FileNotFoundError(self.towns_source_dir)
        for item in self._buffer:
            cc = item["iso3"]
            if (self.towns_source_dir / f"{cc}.json").is_file():
                filtered.append(item)
        self._buffer = filtered

    def generate_value_label(self) -> None:
        if VALUE_LABEL_MODE:
            self._buffer = [{"value": item, "label": item} for item in self._buffer]
        else:
            self._buffer = [(item, item) for item in self._buffer]

    generate = generate_value_label

    def generate_value_label_newsrooms(self) -> None:
        self._buffer = [
            {"value": f"{item[0]};{item[1]}", "label": f"{item[0]} ({item[1]})"}
            for item in self._buffer
        ]
        if not VALUE_LABEL_MODE:
            self._buffer = [(item["value"], item["label"]) for item in self._buffer]

    def generate_optgroup_value_label(self) -> None:
        """Base optgroup format:
        [{"optgroup": group, "value": value, "label": label}, ... ]

        organisation
        """
        if VALUE_LABEL_MODE:
            result = []
            for group, data in self._buffer:
                extended = [
                    {"optgroup": group, "value": f"{group};{label}", "label": label}
                    for label in data
                ]
                result.extend(extended)
        else:
            result = {}
            for group, data in self._buffer:
                extended = [(f"{group};{label}", label) for label in data]
                result[group] = extended

        self._buffer = result

    def generate_dual_value_label(self) -> None:
        """Dual format:
        {
            "field1": [ {"value": 'Associations', "label": 'Associations'} ...
            "field2": [ {"optgroup": "Associations",
                            "value": 'Associations;Actions humanitaires',
                            "label": 'Associations / Actions humanitaires'
                        }, ...
        }

        profession_fonction_public
        profession_fonction_prive
        profession_fonction_asso
        secteur_detaille
        """
        if VALUE_LABEL_MODE:
            field1 = [{"value": group, "label": group} for group, _ in self._buffer]
            field2 = []
            for group, data in self._buffer:
                extended = [
                    {
                        "optgroup": group,
                        "value": f"{group};{label}",
                        "label": f"{group} / {label}",
                    }
                    for label in data
                ]
                field2.extend(extended)

        else:
            field1 = [(group, group) for group, _ in self._buffer]
            field2 = {}
            for group, data in self._buffer:
                extended = [
                    (f"{group};{label}", f"{group} / {label}") for label in data
                ]
                field2[group] = extended
        self._buffer = {"field1": field1, "field2": field2}

    def generate_country(self) -> None:
        if VALUE_LABEL_MODE:
            self._buffer = [
                {"value": item["iso3"], "label": item["name"]} for item in self._buffer
            ]
            # fix order
            for iso3 in ["FRA"]:
                copy = [x for x in self._buffer if x["value"] == iso3]
                self._buffer = [x for x in self._buffer if x["value"] != iso3]
                self._buffer = copy + self._buffer
        else:
            self._buffer = [(item["iso3"], item["name"]) for item in self._buffer]
            # fix order
            for iso3 in ["FRA"]:
                copy = [x for x in self._buffer if x[0] == iso3]
                self._buffer = [x for x in self._buffer if x[0] != iso3]
                self._buffer = copy + self._buffer

    def save(self) -> None:
        filename = f"{self.ontology}.json"
        destination = self.dest_dir / filename
        self.dest_dir.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps(self._buffer, ensure_ascii=False, indent=4),
            encoding="utf8",
        )
        (self.dest_dir / "__init__.py").touch()
        print(f"  saved to {filename}  ({len(self._buffer)} lines)")


class CiviliteConverter(BaseConvert):
    ontology: str = "civilite"


class NewsroomsConverter(BaseConvert):
    ontology: str = "newsrooms"
    strip_content = BaseConvert.strip_content_no_first_newsrooms
    generate = BaseConvert.generate_value_label_newsrooms
    sort = BaseConvert.sort_per_label


class MediasConverter(BaseConvert):
    ontology: str = "medias"
    strip_content = BaseConvert.strip_content_second


class MediaTypeConverter(BaseConvert):
    ontology: str = "media_type"


class JournalismeFonctionConverter(BaseConvert):
    ontology: str = "journalisme_fonction"


class AgenceRPFonctionConverter(BaseConvert):
    ontology: str = "agence_rp"
    strip_content = BaseConvert.strip_content_agence
    sort = BaseConvert.sort_per_label


class TypeAgenceRPFonctionConverter(BaseConvert):
    ontology: str = "type_agence_rp"


class OrganisationConverter(BaseConvert):
    """Dual field."""

    ontology: str = "organisation"
    strip_content = BaseConvert.strip_content_optgroup
    # generate = BaseConvert.generate_optgroup_value_label
    generate = BaseConvert.generate_dual_value_label


class TailleOrganisationConverter(BaseConvert):
    ontology: str = "taille_organisation"
    strip_content = BaseConvert.strip_content_second


class FonctionPublicConverter(BaseConvert):
    """Dual field.

    For this class, output is different from "optgroup" type, we use 2
    field1 and field2 primary keys to permit two actual select fields.
    Output:
        {
            "field1": [ {"value": 'Associations', "label": 'Associations'} ...
            "field2": [ {"optgroup": "Associations",
                         "value": 'Associations;Actions humanitaires',
                         "label": 'Associations / Actions humanitaires'
                        }, ...
        }
    """

    ontology: str = "profession_fonction_public"
    strip_content = BaseConvert.strip_content_optgroup
    generate = BaseConvert.generate_dual_value_label


class FonctionPriveConverter(FonctionPublicConverter):
    ontology: str = "profession_fonction_prive"


class FonctionAssoConverter(FonctionPublicConverter):
    ontology: str = "profession_fonction_asso"


class SecteurDetailleConverter(FonctionPublicConverter):
    ontology: str = "secteur_detaille"


class InteretPolitiqueConverter(FonctionPublicConverter):
    ontology: str = "interet_politique"


class InteretOrgaConverter(FonctionPublicConverter):
    ontology: str = "interet_orga"


class InteretAssoConverter(FonctionPublicConverter):
    ontology: str = "interet_asso"


class TransitionMajeureConverter(FonctionPublicConverter):
    ontology: str = "transformation_majeure"


class MetierConverter(FonctionPublicConverter):
    ontology: str = "metier"


class JournalismeCompetenceConverter(BaseConvert):
    ontology: str = "journalisme_competence"


class CompetenceConverter(BaseConvert):
    ontology: str = "competence"


class LangueConverter(BaseConvert):
    ontology: str = "langue"
    strip_content = BaseConvert.strip_content_second

    def sort(self) -> None:
        put_first = ["Français"]
        if VALUE_LABEL_MODE:
            for key in put_first:
                copy = [x for x in self._buffer if x["value"] == key]
                self._buffer = [x for x in self._buffer if x["value"] != key]
                self._buffer = copy + self._buffer
        else:
            for key in put_first:
                copy = [x for x in self._buffer if x[0] == key]
                self._buffer = [x for x in self._buffer if x[0] != key]
                self._buffer = copy + self._buffer


class PaysConverter(BaseConvert):
    ontology: str = "pays"
    read_json = BaseConvert.read_json_list_content
    strip_content = BaseConvert.strip_filter_country
    generate = BaseConvert.generate_country


def convert_cities_to_select():
    towns_source_dir = Path("./extra_json/towns")
    dest_dir = Path("./data/towns")
    dest_dir.mkdir(parents=True, exist_ok=True)
    (dest_dir / "__init__.py").touch()
    for path in towns_source_dir.glob("*.json"):
        content = json.loads(path.read_text())
        country_code = path.stem
        result = [
            {
                "value": f"{country_code};{city['zip_code']} {city['name']}",
                "label": f"{city['zip_code']} {city['name']}",
            }
            for city in content
        ]
        result = sorted(result, key=itemgetter("label"))
        destination = dest_dir / path.name
        destination.write_text(
            json.dumps(result, ensure_ascii=False, indent=4),
            encoding="utf8",
        )
        print(f"  saved to {path.name}  ({len(result)} lines)")


if __name__ == "__main__":
    convert_ontologies_to_select()
    convert_cities_to_select()
