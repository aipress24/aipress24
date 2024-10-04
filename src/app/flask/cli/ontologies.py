# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only


from __future__ import annotations

import json
from copy import deepcopy
from operator import itemgetter
from pathlib import Path
from typing import Any

from flask.cli import with_appcontext
from flask_super.cli import group
from odsparsator import odsparsator
from slugify import slugify

from app.enums import OrganisationFamilyEnum
from app.flask.extensions import db
from app.models.organisation_light import LightOrganisation
from app.services.countries import (
    check_countries_exist,
    create_country_entry,
    update_country_entry,
)
from app.services.taxonomies import (
    check_taxonomy_exist,
    create_entry,
    get_taxonomy,
    update_entry,
)
from app.services.zip_code import (
    check_zip_code_exist,
    create_zip_code_entry,
    get_full_zip_code_country,
    update_zip_code_entry,
)

# format for HTML selects
VALUE_LABEL_MODE = False

# required: use a.ods document
ONTOLOGY_SRC = Path("data/Ontologies-41.ods")
COUNTRY_SRC = Path("country_zip_code/pays.json")
ZIP_CODE_SRC = Path("country_zip_code/towns")


# Secteurs → `sectors`
# Rubriques → `sections`
# Genres → `genres`
# Type d'info → `topics`
TAXO_NAME_ONTOLOGIE_SLUG = [
    ("news_sectors", "news-secteurs"),
    ("sections", "news-rubriques"),
    ("topics", "news-types-dinfo"),
    ("genres", "news-genres"),
    # Not used yet
    ("genres-com", "news-com-genres"),
    ("technologies", "technologies"),  # probably not completed
    ("mode_remuneration", "modes-de-remuneration"),  # probably not completed
    (
        "type_contenu",
        "types-des-contenus-editoriaux",
    ),  # probably not completed
    ("taille_contenu", "tailles-des-contenus-editoriaux"),  # probably not completed
    # used in html select
    ("media_type", "types-de-presse-medias"),
    ("type_organisation_detail", "types-dorganisation"),
    ("journalisme_fonction", "fonctions-du-journalisme"),
    ("agence_rp", "agencesrp"),
    ("civilite", "civilite"),
    ("competence_expert", "competencesexperts"),  # FIXME rename see KYC
    ("interet_asso", "centres-d-interet-associations"),
    ("interet_orga", "centres-d-interet-organisations"),
    ("interet_politique", "centres-d-interet-politiques-ad"),
    ("journalisme_competence", "competences-en-journalisme"),
    ("langue", "langues"),
    ("type_entreprises_medias", "types-dentreprises-de-presse-medias"),
    ("metier", "metiers"),
    ("orga_newsrooms", "newsrooms"),
    ("profession_fonction_asso", "fonctions-associations-syndicat"),
    ("profession_fonction_prive", "fonctions-organisations-privees"),
    ("profession_fonction_public", "fonctions-politiques-administra"),
    ("secteur_detaille", "secteurs-detailles"),
    ("taille_organisation", "tailles-des-organisations"),
    ("transformation_majeure", "transformations-majeures"),
    ("type_agence_rp", "types-agences-rp"),
    ("groupes_cotes", "groupes-cotes"),
    ("etablissements_sup", "etabenseignsup"),
    ("competences_generales", "competencesgenerales"),
    ("tetieres_secteurs", "listestetieressecteurs"),
    ("niveaux_etudes", "niveaux-d-etude"),
    ("matieres_etudiees", "matieresetudiees"),
]

TAXO_NOT_FROM_FILE = {"geolocalisation", "feuille31", "civilite"}

# Special case, this ontology is not from the .ods file and behave
# differently (because we expect to keep the 'M' or 'F' gender
# compatibility with fake data)
CIVILITE_ONTOLOGY = [
    ("M", "Monsieur"),
    ("F", "Madame"),
    ("?", "Non renseigné"),
]


@group(short_help="Manage ontologies/taxonomies/vocabularies")
def ontologies() -> None:
    pass


def parse_source_ontologies() -> dict[str, Any]:
    """step1 : convert the ods source -> python dictionary."""
    if not ONTOLOGY_SRC.is_file():
        raise FileNotFoundError(f"Please add the missing {ONTOLOGY_SRC} file.")
    content = odsparsator.ods_to_python(
        input_path=ONTOLOGY_SRC,
        export_minimal=True,
    )
    result: dict[str, Any] = {}
    for sheet in content["body"]:
        name = sheet["name"]
        slug = slugify(name)
        table_list = sheet["table"]
        while table_list and not table_list[0]:
            table_list = table_list[1:]
        result[slug] = {"name": name, "slug": slug, "table": table_list}
    return result


def _check_tables_found(raw_ontologies: dict[str, Any]) -> None:
    print("Ontologies in file / known:")
    known = {t[1] for t in TAXO_NAME_ONTOLOGIE_SLUG}
    all_known = known | TAXO_NOT_FROM_FILE
    seen = set()
    for slug in raw_ontologies:
        if slug in all_known:
            print("  ok: ", slug)
            seen.add(slug)
        else:
            print(" new: ", slug)
    missing = known - seen - TAXO_NOT_FROM_FILE
    if missing:
        print("MISSING ontology:", missing)


def print_ontologies() -> None:
    raw_ontologies = parse_source_ontologies()
    for taxonomy_name, slug in TAXO_NAME_ONTOLOGIE_SLUG:
        print(taxonomy_name, slug)
        converter_class = get_converter(slug)
        converter = converter_class(raw_ontologies)
        converter.run()
        values = converter.export()
        print(values)


@ontologies.command(name="import", short_help="Import ontologies")
@with_appcontext
def import_ontologies() -> None:
    import_ontologies_content()


def import_ontologies_content() -> None:
    import_taxonomies()
    import_countries()
    import_zip_codes()
    merge_organisations()

    db.session.commit()


def merge_organisations():
    _merge_newsrooms_organisations()
    _merge_pr_agency_organisations()
    _merge_other_organisations()


def _merge_other_organisations():
    """Merge into organisations /family 'autre' the content of the
    "groupes_cotes" taxonomy
    """
    count = 0
    companies = get_taxonomy("groupes_cotes")
    print(f"Merging OrganisationLight: {len(companies)} groupes_cotes")
    for name in companies:
        if (
            db.session.query(LightOrganisation)
            .where(LightOrganisation.name == name)
            .first()
        ):
            continue
        family = OrganisationFamilyEnum.AUTRE
        db.session.add(LightOrganisation(name=name, family=family.name))
        count += 1
    print(f"Merging OrganisationLight: {count} added")


def _merge_newsrooms_organisations():
    """Merge into organisations /family 'media' the content of the
    "orga_newsrooms" taxonomy
    """
    count = 0
    medias = get_taxonomy("orga_newsrooms")
    print(f"Merging OrganisationLight: {len(medias)} orga_newsrooms")
    for name in medias:
        if (
            db.session.query(LightOrganisation)
            .where(LightOrganisation.name == name)
            .first()
        ):
            continue
        # sub families AG_PRESSE and SYNDIC not detected here:
        family = OrganisationFamilyEnum.MEDIA
        db.session.add(LightOrganisation(name=name, family=family.name))
        count += 1
    print(f"Merging OrganisationLight: {count} added")


def _merge_pr_agency_organisations():
    """Merge into organisations /family 'PR' (press relations) the content
    of the "agence_rp" taxonomy
    """
    count = 0
    agencies = get_taxonomy("agence_rp")
    print(f"Merging OrganisationLight: {len(agencies)} agence_rp")
    for name in agencies:
        if (
            db.session.query(LightOrganisation)
            .where(LightOrganisation.name == name)
            .first()
        ):
            continue
        family = OrganisationFamilyEnum.RP
        db.session.add(LightOrganisation(name=name, family=family.name))
        count += 1
    print(f"Merging OrganisationLight: {count} added")


def import_taxonomies() -> None:
    raw_ontologies = parse_source_ontologies()
    _check_tables_found(raw_ontologies)
    for taxonomy_name, slug in TAXO_NAME_ONTOLOGIE_SLUG:
        try:
            print(f"{taxonomy_name=}  {slug=}")
            converter_class = get_converter(slug)
            converter = converter_class(raw_ontologies)
            converter.run()
            values = converter.export()
            _update_or_create_taxonomy(taxonomy_name, values)
        except KeyError as e:
            print("************** Probable missing ontology for", taxonomy_name)
            print(e)


def _category_from_value(value: str) -> str:
    if ";" in value:
        return value.split(";")[0].strip()
    return ""


def _update_or_create_taxonomy(taxonomy_name, values) -> None:
    # Check that the taxonomy_name is present in DB
    if check_taxonomy_exist(taxonomy_name):
        updated = _update_taxonomy_entries(taxonomy_name, values)
        print(f"    - updated values: {updated}")
    else:
        print("    - create taxonomy")
        _create_taxonomy_entries(taxonomy_name, values)


def _update_taxonomy_entries(taxonomy_name, values) -> int:
    seq: int = 0
    updated: int = 0
    for value, name in values:
        seq += 10
        if update_entry(
            taxonomy_name=taxonomy_name,
            name=name,
            category=_category_from_value(value),
            value=value,
            seq=seq,
        ):
            updated += 1
    return updated


def _create_taxonomy_entries(taxonomy_name, values) -> None:
    seq: int = 0
    for value, name in values:
        seq += 10
        create_entry(
            taxonomy_name=taxonomy_name,
            name=name,
            category=_category_from_value(value),
            value=value,
            seq=seq,
        )
        # print(taxonomy_name, "|", category, "|", value, "|", name)


def import_countries() -> None:
    put_top_of_list = ["FRA"]
    data = json.loads(COUNTRY_SRC.read_text())
    # filter agains actual countries having zip codes
    country_list = [
        (item["iso3"], item["name"])
        for item in data
        if ZIP_CODE_SRC.joinpath(f"{item['iso3']}.json").is_file()
    ]
    print(f"importing {len(country_list)} country names")
    # fix order, put FRA first
    for iso3 in put_top_of_list:
        copy = [x for x in country_list if x[0] == iso3]
        country_list = [x for x in country_list if x[0] != iso3]
        country_list = copy + country_list
    _update_or_create_countries(country_list)


def _update_or_create_countries(country_list: list) -> None:
    # Check that the countries table is present in DB
    if check_countries_exist():
        updated = _update_countries_entries(country_list)
        print(f"    - updated values: {updated}")
    else:
        print("    - create countries")
        _create_country_entries(country_list)


def _update_countries_entries(country_list: list) -> int:
    seq: int = 0
    updated: int = 0
    for iso3, name in country_list:
        seq += 10
        if update_country_entry(
            iso3=iso3,
            name=name,
            seq=seq,
        ):
            updated += 1
    return updated


def _create_country_entries(country_list: list[str]) -> None:
    seq: int = 0
    for iso3, name in country_list:
        seq += 10
        create_country_entry(
            iso3=iso3,
            name=name,
            seq=seq,
        )


def import_zip_codes() -> None:
    print("importing zip codes")
    for path in ZIP_CODE_SRC.glob("*.json"):
        iso3 = path.stem
        zip_code_list = []
        for item in json.loads(path.read_text()):
            zip_code = item["zip_code"]
            name = item["name"]
            value = f"{iso3};{zip_code} {name}"
            label = f"{zip_code} {name}"
            zip_code_list.append((zip_code, name, value, label))
        zip_code_list.sort()
        _update_or_create_zip_code(iso3, zip_code_list)


def _update_or_create_zip_code(iso3: str, zip_code_list: list) -> None:
    # Check that the zip_code table is present in DB
    if check_zip_code_exist(iso3):
        current_zip_codes = get_full_zip_code_country(iso3)
        if current_zip_codes == zip_code_list:
            updated = "none"
        else:
            print("pb ", iso3)
            print(current_zip_codes)
            for a, b in zip(current_zip_codes, zip_code_list):
                if a != b:
                    print(a, b, "\n")
            updated = _update_zip_code_entries(iso3, zip_code_list)
        print(f"    - {iso3} updated values: {updated}")
    else:
        print(f"    - create {iso3} zip codes")
        _create_zip_code_entries(iso3, zip_code_list)


def _update_zip_code_entries(iso3: str, zip_code_list: list) -> int:
    updated: int = 0
    for zip_code, name, value, label in zip_code_list:
        if update_zip_code_entry(
            iso3=iso3,
            zip_code=zip_code,
            name=name,
            value=value,
            label=label,
        ):
            updated += 1
    return updated


def _create_zip_code_entries(iso3: str, zip_code_list: list) -> None:
    for zip_code, name, value, label in zip_code_list:
        create_zip_code_entry(
            iso3=iso3,
            zip_code=zip_code,
            name=name,
            value=value,
            label=label,
        )


def get_converter(ontology_slug: str) -> Any:  # noqa:PLR0915
    match ontology_slug:
        case "civilite":
            converter_class = CiviliteConverter
        case "newsrooms":
            converter_class = OrgaNewsroomsConverter
        case "types-dentreprises-de-presse-medias":
            converter_class = TypeEntrepriseMediasConverter
        case "types-de-presse-medias":
            converter_class = MediaTypeConverter
        case "fonctions-du-journalisme":
            converter_class = JournalismeFonctionConverter
        case "agencesrp":
            converter_class = AgenceRPFonctionConverter
        case "types-agences-rp":
            converter_class = TypeAgenceRPFonctionConverter
        case "types-dorganisation":
            converter_class = TypesOrganisationConverter
        case "tailles-des-organisations":
            converter_class = TailleOrganisationConverter
        case "fonctions-politiques-administra":
            converter_class = FonctionPublicConverter
        case "fonctions-organisations-privees":
            converter_class = FonctionPriveConverter
        case "fonctions-associations-syndicat":
            converter_class = FonctionAssoConverter
        case "secteurs-detailles":
            converter_class = SecteurDetailleConverter
        case "centres-d-interet-politiques-ad":
            converter_class = InteretPolitiqueConverter
        case "centres-d-interet-organisations":
            converter_class = InteretOrgaConverter
        case "centres-d-interet-associations":
            converter_class = InteretAssoConverter
        case "metiers":
            converter_class = MetierConverter
        case "competences-en-journalisme":
            converter_class = JournalismeCompetenceConverter
        case "competencesexperts":
            converter_class = CompetenceExpertConverter
        case "langues":
            converter_class = LangueConverter
        case "transformations-majeures":
            converter_class = TransformationsMajeuresConverter
        # taxonomies
        case "news-secteurs":
            converter_class = NewsSecteursConverter
        case "news-rubriques":
            converter_class = NewsRubriquesConverter
        case "news-types-dinfo":
            converter_class = NewsTypeInfoConverter
        case "news-genres":
            converter_class = NewsGenresConverter
        # Not used yet
        case "news-com-genres":
            converter_class = NewsComGenresConverter
        case "technologies":
            converter_class = TechnologiesConverter
        case "modes-de-remuneration":
            converter_class = ModeRemunerationConverter
        # case "types-et-taille-des-contenus-ed":
        #     converter_class = TypeContenuConverter
        case "types-des-contenus-editoriaux":
            converter_class = TypeContenuConverter
        case "tailles-des-contenus-editoriaux":
            converter_class = TailleContenuConverter
        case "groupes-cotes":
            converter_class = GroupesCotesConverter
        case "etabenseignsup":
            converter_class = EtablissementsSuperieurs
        case "competencesgenerales":
            converter_class = CompetencesGenerales
        case "listestetieressecteurs":
            converter_class = TetieresSecteurs
        case "niveaux-d-etude":
            converter_class = NiveauxEtudes
        case "matieresetudiees":
            converter_class = MatieresEtudiees
        case _:
            converter_class = None
    if not converter_class:
        raise ValueError(f"No converter found for {ontology_slug}")
    return converter_class


class BaseConvert:
    ontology_slug: str = "ontology_slug"
    onto_source_dir: Path = Path("./ontology_json")
    extra_source_dir: Path = Path("./extra_json")
    towns_source_dir: Path = Path("./extra_json/towns")
    dest_dir: Path = Path("./data")

    def __init__(self, raw_ontologies: dict) -> None:
        """Note: _buffer is dict type for the dual special case."""
        self._buffer: list | dict = []
        self.raw_ontologies = raw_ontologies

    def run(self) -> None:
        print(f"{self.ontology_slug} generation")
        self.read_dict()
        self.strip_content()
        self.generate()
        self.sort()

    def sort_per_label(self) -> None:
        if VALUE_LABEL_MODE:
            self._buffer = sorted(self._buffer, key=itemgetter("label"))
        else:
            self._buffer = sorted(self._buffer, key=itemgetter(1))

    def no_sort(self) -> None:
        pass

    sort = no_sort

    def read_dict(self) -> None:
        content = self.raw_ontologies[self.ontology_slug]
        if isinstance(content, dict):
            self._buffer = content["table"]
        elif isinstance(content, list):
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

        type organisation
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

        type organisation
        """
        if VALUE_LABEL_MODE:
            result = []
            for _group, data in self._buffer:
                extended = [
                    {"optgroup": _group, "value": f"{_group};{label}", "label": label}
                    for label in data
                ]
                result.extend(extended)
        else:
            result = {}
            for _group, data in self._buffer:
                extended = [(f"{_group};{label}", label) for label in data]
                result[_group] = extended

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
            for _group, data in self._buffer:
                extended = [
                    {
                        "optgroup": _group,
                        "value": f"{_group};{label}",
                        "label": f"{_group} / {label}",
                    }
                    for label in data
                ]
                field2.extend(extended)

        else:
            field1 = [(_group, _group) for _group, _ in self._buffer]
            field2 = {}
            for _group, data in self._buffer:
                extended = [
                    (f"{_group};{label}", f"{_group} / {label}") for label in data
                ]
                field2[_group] = extended
        self._buffer = {"field1": field1, "field2": field2}

    def save(self) -> None:
        filename = f"{self.ontology_slug}.json"
        destination = self.dest_dir / filename
        self.dest_dir.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps(self._buffer, ensure_ascii=False, indent=4),
            encoding="utf8",
        )
        print(f"  saved to {filename}  ({len(self._buffer)} lines)")

    def export_optgroup(self):
        """
        For optgroup kind of ontologies, returned formats:

        [
            ('ARTS, CULTURE, MEDIAS;Architecture', 'ARTS, CULTURE, MEDIAS / Architecture'), ('ARTS, CULTURE, MEDIAS;Artisanat d’art', 'ARTS, CULTURE, MEDIAS / Artisanat d’art'), ('ARTS, CULTURE, MEDIAS;Art vidéo', 'ARTS, CULTURE, MEDIAS / Art vidéo'),
            ('ARTS, CULTURE, MEDIAS;Arts textiles, Haute-couture', 'ARTS, CULTURE, MEDIAS / Arts textiles, Haute-couture')
            ...
        ]
        """
        all_values = []
        for items in self._buffer["field2"].values():
            all_values.extend(items)
        return all_values

    def export_list(self):
        """
        For list kind of ontologies, returned formats:

        [
            ('Economie & Finance', 'Economie & Finance'),
            ('Emploi, chômage, retraite', 'Emploi, chômage, retraite'),
            ...
        ]
        """
        return self._buffer

    export = export_optgroup


class CiviliteConverter(BaseConvert):
    ontology_slug: str = "civilite"
    export = BaseConvert.export_list

    def run(self) -> None:
        self._buffer = deepcopy(CIVILITE_ONTOLOGY)


class OrgaNewsroomsConverter(BaseConvert):
    ontology_slug: str = "newsrooms"
    strip_content = BaseConvert.strip_content_no_first_newsrooms
    generate = BaseConvert.generate_value_label_newsrooms
    sort = BaseConvert.sort_per_label
    export = BaseConvert.export_list


class TypeEntrepriseMediasConverter(BaseConvert):
    ontology_slug: str = "types-dentreprises-de-presse-medias"
    strip_content = BaseConvert.strip_content_second
    export = BaseConvert.export_list


class MediaTypeConverter(BaseConvert):
    ontology_slug: str = "types-de-presse-medias"
    export = BaseConvert.export_list


class JournalismeFonctionConverter(BaseConvert):
    ontology_slug: str = "fonctions-du-journalisme"
    export = BaseConvert.export_list


class AgenceRPFonctionConverter(BaseConvert):
    ontology_slug: str = "agencesrp"
    strip_content = BaseConvert.strip_content_agence
    sort = BaseConvert.sort_per_label
    export = BaseConvert.export_list


class TypeAgenceRPFonctionConverter(BaseConvert):
    ontology_slug: str = "types-agences-rp"
    export = BaseConvert.export_list


class TypesOrganisationConverter(BaseConvert):
    """Dual field."""

    ontology_slug: str = "types-dorganisation"
    strip_content = BaseConvert.strip_content_optgroup
    # generate = BaseConvert.generate_optgroup_value_label
    generate = BaseConvert.generate_dual_value_label


class TailleOrganisationConverter(BaseConvert):
    ontology_slug: str = "tailles-des-organisations"
    strip_content = BaseConvert.strip_content_second
    export = BaseConvert.export_list


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

    ontology_slug: str = "fonctions-politiques-administra"
    strip_content = BaseConvert.strip_content_optgroup
    generate = BaseConvert.generate_dual_value_label


class FonctionPriveConverter(FonctionPublicConverter):
    ontology_slug: str = "fonctions-organisations-privees"


class FonctionAssoConverter(FonctionPublicConverter):
    ontology_slug: str = "fonctions-associations-syndicat"


class SecteurDetailleConverter(FonctionPublicConverter):
    ontology_slug: str = "secteurs-detailles"


class InteretPolitiqueConverter(FonctionPublicConverter):
    ontology_slug: str = "centres-d-interet-politiques-ad"


class InteretOrgaConverter(FonctionPublicConverter):
    ontology_slug: str = "centres-d-interet-organisations"


class InteretAssoConverter(FonctionPublicConverter):
    ontology_slug: str = "centres-d-interet-associations"


class TransformationsMajeuresConverter(FonctionPublicConverter):
    ontology_slug: str = "transformations-majeures"


class MetierConverter(FonctionPublicConverter):
    ontology_slug: str = "metiers"


class JournalismeCompetenceConverter(BaseConvert):
    ontology_slug: str = "competences-en-journalisme"
    export = BaseConvert.export_list


class CompetenceExpertConverter(BaseConvert):
    ontology_slug: str = "competencesexperts"
    export = BaseConvert.export_list


class NewsSecteursConverter(FonctionPublicConverter):
    ontology_slug: str = "news-secteurs"


class NewsRubriquesConverter(BaseConvert):
    ontology_slug: str = "news-rubriques"
    export = BaseConvert.export_list


class NewsTypeInfoConverter(FonctionPublicConverter):
    ontology_slug: str = "news-types-dinfo"


class NewsGenresConverter(BaseConvert):
    ontology_slug: str = "news-genres"
    strip_content = BaseConvert.strip_content_second
    export = BaseConvert.export_list


class NewsComGenresConverter(BaseConvert):
    ontology_slug: str = "news-com-genres"
    export = BaseConvert.export_list


class TechnologiesConverter(FonctionPublicConverter):
    ontology_slug: str = "technologies"


class ModeRemunerationConverter(BaseConvert):
    ontology_slug: str = "modes-de-remuneration"
    strip_content = BaseConvert.strip_content_second
    export = BaseConvert.export_list


class TypeContenuConverter(BaseConvert):
    ontology_slug: str = "types-des-contenus-editoriaux"
    strip_content = BaseConvert.strip_content_second
    export = BaseConvert.export_list


class TailleContenuConverter(BaseConvert):
    ontology_slug: str = "tailles-des-contenus-editoriaux"
    strip_content = BaseConvert.strip_content_second
    export = BaseConvert.export_list


class GroupesCotesConverter(BaseConvert):
    ontology_slug: str = "groupes-cotes"
    strip_content = BaseConvert.strip_content_no_first
    export = BaseConvert.export_list


class EtablissementsSuperieurs(FonctionPublicConverter):
    ontology_slug: str = "etabenseignsup"


class CompetencesGenerales(FonctionPublicConverter):
    ontology_slug: str = "competencesgenerales"


class TetieresSecteurs(BaseConvert):
    ontology_slug: str = "listestetieressecteurs"
    export = BaseConvert.export_list


class NiveauxEtudes(BaseConvert):
    ontology_slug: str = "niveaux-d-etude"
    export = BaseConvert.export_list


class MatieresEtudiees(BaseConvert):
    ontology_slug: str = "matieresetudiees"
    export = BaseConvert.export_list


class LangueConverter(BaseConvert):
    ontology_slug: str = "langues"
    strip_content = BaseConvert.strip_content_second
    export = BaseConvert.export_list

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


# def convert_cities_to_select():
#     towns_source_dir = Path("./extra_json/towns")
#     dest_dir = Path("./data/towns")
#     dest_dir.mkdir(parents=True, exist_ok=True)
#     for path in towns_source_dir.glob("*.json"):
#         content = json.loads(path.read_text())
#         country_code = path.stem
#         result = [
#             {
#                 "value": f"{country_code};{city['zip_code']} {city['name']}",
#                 "label": f"{city['zip_code']} {city['name']}",
#             }
#             for city in content
#         ]
#         result = sorted(result, key=itemgetter("label"))
#         destination = dest_dir / path.name
#         destination.write_text(
#             json.dumps(result, ensure_ascii=False, indent=4),
#             encoding="utf8",
#         )
#         print(f"  saved to {path.name}  ({len(result)} lines)")


if __name__ == "__main__":
    print_ontologies()
