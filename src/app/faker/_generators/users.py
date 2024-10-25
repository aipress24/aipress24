# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import functools
import random
import urllib.request

from flask_security import hash_password
from mimesis import Internet, Person
from mimesis.enums import Gender
from sqlalchemy.sql import func

from app.constants import LABEL_INSCRIPTION_NOUVELLE, LABEL_INSCRIPTION_VALIDEE
from app.enums import ContactTypeEnum, OrganisationTypeEnum
from app.faker._constants import COVER_IMAGES
from app.faker._geo import fake_geoloc
from app.flask.extensions import security
from app.models.auth import KYCProfile, User
from app.modules.kyc.community_role import append_user_role_from_community
from app.modules.kyc.ontology_loader import zip_code_city_list
from app.modules.kyc.organisation_utils import (
    get_organisation_family,
    store_auto_organisation,
)
from app.modules.kyc.populate_profile import populate_json_field
from app.modules.kyc.survey_model import get_survey_profile, get_survey_profile_ids
from app.services.roles import Role, generate_roles_map
from app.services.taxonomies import get_full_taxonomy, get_full_taxonomy_category_value
from app.settings.vocabularies.user import USER_STATUS

from .base import BaseGenerator

GENDERS = {
    "M": Gender.MALE,
    "F": Gender.FEMALE,
}

GLOBAL_COUNTER = {"no_carte_presse": 0}
COMMON_PWD = "AAAABBBB-1"
PERCENT_USERS_WITH_AUTO_ORGANISATION = 50
AUTO_ORGANISATIONS_NAMES = set()


@functools.cache
def _role_map() -> dict[str, Role]:
    return generate_roles_map()


@functools.cache
def _get_full_taxo(taxonomy: str) -> list[tuple[str, str]]:
    return get_full_taxonomy(taxonomy)


@functools.cache
def _get_full_taxo_category_value(taxonomy: str) -> list[tuple[str, str]]:
    return get_full_taxonomy_category_value(taxonomy)


@functools.cache
def _get_full_organisation_family(family: OrganisationTypeEnum) -> list[str]:
    return get_organisation_family(family)


def random_profile_id() -> str:
    return random.choice(get_survey_profile_ids())


def _use_known_organisation_name() -> str | None:
    if not AUTO_ORGANISATIONS_NAMES:
        return None
    if random.randint(1, 100) <= 50:
        return None
    return random.choice(list(AUTO_ORGANISATIONS_NAMES))


class UserGenerator(BaseGenerator):
    users: list[User] = []

    def __post_init__(self) -> None:
        super().__post_init__()
        self.person_faker = Person(self.locale)

    def _random_pseudo(self, _user: User, profile: KYCProfile) -> None:
        profile.info_personnelle["pseudo"] = self.generate_words(1)

    def _random_macaron_hebergement(self, _user: User, profile: KYCProfile) -> None:
        profile.info_personnelle["macaron_hebergement"] = bool(random.randint(0, 1))

    def _random_macaron_repas(self, _user: User, profile: KYCProfile) -> None:
        profile.info_personnelle["macaron_repas"] = bool(random.randint(0, 1))

    def _random_macaron_verre(self, _user: User, profile: KYCProfile) -> None:
        profile.info_personnelle["macaron_verre"] = bool(random.randint(0, 1))

    def _random_trigger_academics(self, _user: User, profile: KYCProfile) -> None:
        profile.business_wall["trigger_academics"] = bool(random.randint(0, 1))

    def _random_trigger_academics_entrepreneur(
        self, _user: User, profile: KYCProfile
    ) -> None:
        profile.business_wall["trigger_academics_entrepreneur"] = bool(
            random.randint(0, 1)
        )

    def _random_trigger_media_agence_de_presse(
        self, _user: User, profile: KYCProfile
    ) -> None:
        profile.business_wall["trigger_media_agence_de_presse"] = bool(
            random.randint(0, 1)
        )

    def _random_trigger_media_media(self, _user: User, profile: KYCProfile) -> None:
        profile.business_wall["trigger_media_media"] = bool(random.randint(0, 1))

    def _random_trigger_organization(self, _user: User, profile: KYCProfile) -> None:
        profile.business_wall["trigger_organization"] = bool(random.randint(0, 1))

    def _random_trigger_pr(self, _user: User, profile: KYCProfile) -> None:
        profile.business_wall["trigger_pr"] = bool(random.randint(0, 1))

    def _random_trigger_pr_independant(self, _user: User, profile: KYCProfile) -> None:
        profile.business_wall["trigger_pr_independant"] = bool(random.randint(0, 1))

    def _random_trigger_transformers(self, _user: User, profile: KYCProfile) -> None:
        profile.business_wall["trigger_transformers"] = bool(random.randint(0, 1))

    def _random_taille_orga(self, _user: User, profile: KYCProfile) -> None:
        profile.info_professionnelle["taille_orga"] = random.choice(
            _get_full_taxo("taille_organisation")
        )[0]

    def _random_tel_mobile(self, user: User, _profile: KYCProfile) -> None:
        user.tel_mobile = self.person_faker.telephone()

    def _random_tel_standard(self, _user: User, profile: KYCProfile) -> None:
        profile.info_professionnelle["tel_standard"] = self.person_faker.telephone()

    def _random_ligne_directe(self, _user: User, profile: KYCProfile) -> None:
        profile.info_professionnelle["ligne_directe"] = self.person_faker.telephone()

    def _random_no_carte_presse(self, _user: User, profile: KYCProfile) -> None:
        GLOBAL_COUNTER["no_carte_presse"] += 1
        profile.info_personnelle["no_carte_presse"] = str(
            GLOBAL_COUNTER["no_carte_presse"]
        )

    def _random_photo_carte_presse(self, user: User, _profile: KYCProfile) -> None:
        lego = self.get_lego_image()
        try:
            user.photo_carte_presse = urllib.request.urlopen(lego).read()  # noqa: S310
            user.photo_carte_presse_filename = lego
            # user.profile_image_url = ""  # for compat with KYC, to be modified
        except Exception as e:
            print(e)

    def _random_nom_groupe_presse(self, _user: User, profile: KYCProfile) -> None:
        word = self.generate_words(1)
        profile.info_professionnelle["nom_groupe_presse"] = (
            f"{word.capitalize()} Press Group"
        )

    def _random_nom_adm(self, _user: User, profile: KYCProfile) -> None:
        word = self.generate_words(1)
        profile.info_professionnelle["nom_adm"] = f"{word.capitalize()} Administration"

    def _random_type_entreprise_media(self, _user: User, profile: KYCProfile) -> None:
        profile.info_professionnelle["type_entreprise_media"] = list({
            random.choice(_get_full_taxo("type_entreprises_medias"))[0]
            for _ in range(random.randint(1, 3))
        })

    def _random_type_presse_et_media(self, _user: User, profile: KYCProfile) -> None:
        profile.info_professionnelle["type_presse_et_media"] = list({
            random.choice(_get_full_taxo("media_type"))[0]
            for _ in range(random.randint(1, 3))
        })

    def _random_fonctions_journalisme(self, _user: User, profile: KYCProfile) -> None:
        profile.info_professionnelle["fonctions_journalisme"] = list({
            random.choice(_get_full_taxo("journalisme_fonction"))[0]
            for _ in range(random.randint(1, 5))
        })

    def _random_nom_orga(self, _user: User, profile: KYCProfile) -> None:
        organisations = _get_full_organisation_family(OrganisationTypeEnum.OTHER)
        if not organisations or random.randint(1, 4) == 1:
            name = _use_known_organisation_name()
            if not name:
                name = self.generate_words(1)
                name = f"{name.capitalize()} Organisation"
        else:
            name = random.choice(organisations)
        AUTO_ORGANISATIONS_NAMES.add(name)
        profile.info_professionnelle["nom_orga"] = name

    def _random_nom_media(self, _user: User, profile: KYCProfile) -> None:
        # special case: several possible free or from list but first one taken
        # as organisation_name
        def _nom_media() -> str:
            medias = _get_full_organisation_family(OrganisationTypeEnum.MEDIA)
            if not medias or random.randint(1, 4) == 1:
                name = _use_known_organisation_name()
                if not name:
                    name = self.generate_words(1)
                    name = f"{name.capitalize()} Média"
            else:
                name = random.choice(medias)
            AUTO_ORGANISATIONS_NAMES.add(name)
            return name

        profile.info_professionnelle["nom_media"] = list({
            _nom_media() for _ in range(random.randint(1, 3))
        })

    def _random_nom_media_instit(self, _user: User, profile: KYCProfile) -> None:
        name = _use_known_organisation_name()
        if not name:
            word = self.generate_words(1)
            name = f"{word.capitalize()} Média Inst"
        AUTO_ORGANISATIONS_NAMES.add(name)
        profile.info_professionnelle["nom_media_instit"] = name

    def _random_nom_agence_rp(self, _user: User, profile: KYCProfile) -> None:
        agencies = _get_full_organisation_family(OrganisationTypeEnum.COM)
        if not agencies or random.randint(1, 4) == 1:
            name = _use_known_organisation_name()
            if not name:
                name = self.generate_words(1)
                name = f"{name.capitalize()} PR Agency"
        else:
            name = random.choice(agencies)
        AUTO_ORGANISATIONS_NAMES.add(name)
        profile.info_professionnelle["nom_agence_rp"] = name

    def _random_nom_group_com(self, _user: User, profile: KYCProfile) -> None:
        word = self.generate_words(1)
        profile.info_professionnelle["nom_group_com"] = f"{word.capitalize()} PR Group"

    def _random_langues(self, _user: User, profile: KYCProfile) -> None:
        profile.match_making["langues"] = [
            "Français",
            random.choice(_get_full_taxo("langue"))[0],
        ]

    def _random_hobbies(self, _user: User, profile: KYCProfile) -> None:
        profile.match_making["hobbies"] = self.generate_text(1500)

    def _random_formations(self, _user: User, profile: KYCProfile) -> None:
        # education is now "formations"
        profile.match_making["formations"] = self.generate_text(1500)

    def _random_experiences(self, _user: User, profile: KYCProfile) -> None:
        # bio is now "experiences"
        profile.match_making["experiences"] = self.generate_text(1500)

    def _random_validation_gcu(self, user: User, _profile: KYCProfile) -> None:
        user.gcu_acceptation = True
        user.gcu_acceptation_date = func.now()

    def _random_competences_journalisme(self, _user: User, profile: KYCProfile) -> None:
        profile.match_making["competences_journalisme"] = list({
            random.choice(_get_full_taxo("journalisme_competence"))[0]
            for _ in range(random.randint(1, 8))
        })

    def _random_competences(self, _user: User, profile: KYCProfile) -> None:
        profile.match_making["competences"] = list({
            random.choice(_get_full_taxo("competence_expert"))[0]
            for _ in range(random.randint(1, 5))
        })

    def _random_type_orga(self, _user: User, profile: KYCProfile) -> None:
        taxo = _get_full_taxo_category_value("type_organisation_detail")
        categ_values = list({random.choice(taxo) for _ in range(random.randint(1, 5))})
        categories = list({cv[0] for cv in categ_values})
        values = list({cv[1] for cv in categ_values})
        profile.info_professionnelle["type_orga"] = categories
        profile.info_professionnelle["type_orga_detail"] = values

    def _random_type_agence_rp(self, _user: User, profile: KYCProfile) -> None:
        profile.info_professionnelle["type_agence_rp"] = list({
            random.choice(_get_full_taxo("type_agence_rp"))[0]
            for _ in range(random.randint(1, 3))
        })

    def _random_metier(self, _user: User, profile: KYCProfile) -> None:
        taxo = _get_full_taxo_category_value("metier")
        categ_values = list({random.choice(taxo) for _ in range(random.randint(1, 5))})
        categories = list({cv[0] for cv in categ_values})
        values = list({cv[1] for cv in categ_values})
        profile.match_making["metier"] = categories
        profile.match_making["metier_detail"] = values

    def _random_transformation_majeure(self, _user: User, profile: KYCProfile) -> None:
        taxo = _get_full_taxo_category_value("transformation_majeure")
        categ_values = list({random.choice(taxo) for _ in range(random.randint(1, 5))})
        categories = list({cv[0] for cv in categ_values})
        values = list({cv[1] for cv in categ_values})
        profile.match_making["transformation_majeure"] = categories
        profile.match_making["transformation_majeure_detail"] = values

    def _random_interet_ass_syn(self, _user: User, profile: KYCProfile) -> None:
        taxo = _get_full_taxo_category_value("interet_asso")
        categ_values = list({random.choice(taxo) for _ in range(random.randint(1, 5))})
        categories = list({cv[0] for cv in categ_values})
        values = list({cv[1] for cv in categ_values})
        profile.match_making["interet_ass_syn"] = categories
        profile.match_making["interet_ass_syn_detail"] = values

    def _random_interet_org_priv(self, _user: User, profile: KYCProfile) -> None:
        taxo = _get_full_taxo_category_value("interet_orga")
        categ_values = list({random.choice(taxo) for _ in range(random.randint(1, 3))})
        categories = list({cv[0] for cv in categ_values})
        values = list({cv[1] for cv in categ_values})
        profile.match_making["interet_org_priv"] = categories
        profile.match_making["interet_org_priv_detail"] = values

    def _random_interet_pol_adm(self, _user: User, profile: KYCProfile) -> None:
        taxo = _get_full_taxo_category_value("interet_politique")
        categ_values = list({random.choice(taxo) for _ in range(random.randint(1, 3))})
        categories = list({cv[0] for cv in categ_values})
        values = list({cv[1] for cv in categ_values})
        profile.match_making["interet_pol_adm"] = categories
        profile.match_making["interet_pol_adm_detail"] = values

    def _random_secteurs_activite_detailles(
        self, _user: User, profile: KYCProfile
    ) -> None:
        taxo = _get_full_taxo_category_value("secteur_detaille")
        categ_values = list({random.choice(taxo) for _ in range(random.randint(1, 3))})
        categories = list({cv[0] for cv in categ_values})
        values = list({cv[1] for cv in categ_values})
        profile.match_making["secteurs_activite_detailles"] = categories
        profile.match_making["secteurs_activite_detailles_detail"] = values

    def _random_secteurs_activite_rp(self, _user: User, profile: KYCProfile) -> None:
        taxo = _get_full_taxo_category_value("secteur_detaille")
        categ_values = list({random.choice(taxo) for _ in range(random.randint(1, 3))})
        categories = list({cv[0] for cv in categ_values})
        values = list({cv[1] for cv in categ_values})
        profile.match_making["secteurs_activite_rp"] = categories
        profile.match_making["secteurs_activite_rp_detail"] = values

    def _random_secteurs_activite_medias(
        self, _user: User, profile: KYCProfile
    ) -> None:
        taxo = _get_full_taxo_category_value("secteur_detaille")
        categ_values = list({random.choice(taxo) for _ in range(random.randint(1, 3))})
        categories = list({cv[0] for cv in categ_values})
        values = list({cv[1] for cv in categ_values})
        profile.match_making["secteurs_activite_medias"] = categories
        profile.match_making["secteurs_activite_medias_detail"] = values

    def _random_fonctions_pol_adm(self, _user: User, profile: KYCProfile) -> None:
        taxo = _get_full_taxo_category_value("profession_fonction_public")
        categ_values = list({random.choice(taxo) for _ in range(random.randint(1, 3))})
        categories = list({cv[0] for cv in categ_values})
        values = list({cv[1] for cv in categ_values})
        profile.info_professionnelle["fonctions_pol_adm"] = categories
        profile.info_professionnelle["fonctions_pol_adm_detail"] = values

    def _random_fonctions_org_priv(self, _user: User, profile: KYCProfile) -> None:
        taxo = _get_full_taxo_category_value("profession_fonction_prive")
        categ_values = list({random.choice(taxo) for _ in range(random.randint(1, 3))})
        categories = list({cv[0] for cv in categ_values})
        values = list({cv[1] for cv in categ_values})
        profile.info_professionnelle["fonctions_org_priv"] = categories
        profile.info_professionnelle["fonctions_org_priv_detail"] = values

    def _random_fonctions_ass_syn(self, _user: User, profile: KYCProfile) -> None:
        taxo = _get_full_taxo_category_value("profession_fonction_asso")
        categ_values = list({random.choice(taxo) for _ in range(random.randint(1, 3))})
        categories = list({cv[0] for cv in categ_values})
        values = list({cv[1] for cv in categ_values})
        profile.info_professionnelle["fonctions_ass_syn"] = categories
        profile.info_professionnelle["fonctions_ass_syn_detail"] = values

    def _random_url_site_web(self, _user: User, profile: KYCProfile) -> None:
        profile.info_professionnelle["url_site_web"] = Internet().url()

    def _random_pays_zip_ville(self, _user: User, profile: KYCProfile) -> None:
        country = "FRA"
        row = random.choice(zip_code_city_list(country))
        zip_city = row["value"]
        profile.info_professionnelle["pays_zip_ville"] = country
        profile.info_professionnelle["pays_zip_ville_detail"] = zip_city

    def _random_adresse_pro(self, _user: User, profile: KYCProfile) -> None:
        word = self.generate_words(1)
        adr = f"{random.randint(1, 200)} rue {word.capitalize()}"
        profile.info_professionnelle["adresse_pro"] = adr

    def _random_compl_adresse_pro(self, _user: User, profile: KYCProfile) -> None:
        bat = f"Bat {random.choice(('A', 'B', 'C'))}"
        profile.info_professionnelle["compl_adresse_pro"] = bat

    def _random_password(self, user: User, _profile: KYCProfile) -> None:
        user.password = hash_password(COMMON_PWD)

    def _make_random_contact_details(self, _user: User, profile: KYCProfile) -> None:
        # advanced feature for faker would be default depending on user's community
        data = {}
        for contact_type in ContactTypeEnum:
            data[f"email_{contact_type.name}"] = bool(random.randint(0, 1))
            data[f"mobile_{contact_type.name}"] = bool(random.randint(0, 1))
        profile.show_contact_details = data

    def _make_random_validation(
        self,
        user: User,
        _profile: KYCProfile,
        counter: int,
    ) -> None:
        # advanced feature for faker would be default depending on user's community
        if counter > 50 and (random.randint(1, 5)) == 1:
            user.active = False
            user.user_valid_comment = LABEL_INSCRIPTION_NOUVELLE
        else:
            user.active = True
            user.user_valid_comment = LABEL_INSCRIPTION_VALIDEE

    @staticmethod
    def _load_photo_profil(user: User) -> None:
        try:
            user.photo = urllib.request.urlopen(  # noqa: S310
                user.profile_image_url
            ).read()
            user.photo_filename = user.profile_image_url
            user.profile_image_url = ""  # for compat with KYC, to be modified
        except Exception as e:
            print(e)

    def _make_non_official_orga(self, user: User, profile: KYCProfile) -> None:
        """Generate random non official organisation from user infos."""
        orga_field_name = profile.organisation_field_name_origin
        current_value = profile.get_value(orga_field_name)
        if isinstance(current_value, list):
            if current_value:
                organisation_name = current_value[0]
            else:
                organisation_name = ""
        else:
            organisation_name = current_value
        if not organisation_name:  # user without organisation
            return
        # family = profile.organisation_family
        # store AUTO organisation
        # allow organisation of same name
        auto_organisation = store_auto_organisation(organisation_name)
        if auto_organisation:
            user.organisation_id = auto_organisation.id
        # store organisation name in user profile
        profile.deduce_organisation_name()

    def make_obj(self) -> User:
        datastore = security.datastore
        user: User = datastore.create_user()  # type:ignore

        self.counter += 1

        user.gender = random.choice(["M", "F"])
        gender = GENDERS[user.gender]
        user.first_name = self.person_faker.first_name(gender)
        user.last_name = self.person_faker.last_name(gender)
        user.email = f"u{self.counter}@aipress24.com"
        # user.email = self.person_faker.email(unique=True)
        user.email_secours = self.person_faker.email(unique=True)

        survey_profile = get_survey_profile(random_profile_id())

        profile = KYCProfile(
            profile_id=survey_profile.id,
            profile_label=survey_profile.label,
            profile_community=survey_profile.community.name,
            contact_type=survey_profile.contact_type.name,
            presentation=self.generate_text(300),
            show_contact_details=populate_json_field("show_contact_details", {}),
            info_personnelle=populate_json_field("info_personnelle", {}),
            info_professionnelle=populate_json_field("info_professionnelle", {}),
            match_making=populate_json_field("match_making", {}),
            business_wall=populate_json_field("business_wall", {}),
        )

        field_done = {
            "first_name",
            "last_name",
            "civilite",
            "email",
            "email_secours",
            # "telephone",
            "photo",
            "presentation",
        }

        field_related_to_organisation = {
            "nom_media",  # organisation name
            "nom_media_instit",  # organisation name
            "nom_agence_rp",  # organisation name
            "nom_orga",  # organisation name
            "nom_groupe_presse",
            "type_entreprise_media",
            "type_presse_et_media",
            "nom_group_com",
            "type_agence_rp",
            "nom_adm",
            "type_orga",
            "taille_orga",
            "pays_zip_ville",
            "adresse_pro",
            "compl_adresse_pro",
            "tel_standard",
            "ligne_directe",
            "url_site_web",
        }

        user_with_auto_org = (
            random.randint(1, 100) <= PERCENT_USERS_WITH_AUTO_ORGANISATION
        )

        for field in survey_profile.fields(only_mandatory=False):
            name = field.name
            if not user_with_auto_org and name in field_related_to_organisation:
                continue
            if name not in field_done:
                method = getattr(self, f"_random_{name}", None)
                if method:
                    method(user, profile)
                else:
                    print("-- not found:", name)

        self._make_random_contact_details(user, profile)
        self._make_random_validation(user, profile, self.counter)

        # non official organisation:
        if user_with_auto_org:
            self._make_non_official_orga(user, profile)

        user.profile = profile

        # job_titles = ROLES + ROLES + ROLES + [faker.job() for i in range(1, 100)]
        # user.job_title = random.choice(job_titles)
        # user.job_title = survey_profile.label

        # user.job_description = self.generate_html(1, 4)
        # user.job_description = ""  ~ replaced by user.presentation

        user.profile_image_url = self.get_profile_image(user)
        self._load_photo_profil(user)
        user.cover_image_url = random.choice(COVER_IMAGES)

        user.status = random.choice(USER_STATUS)
        user.karma = random.randint(0, 100)
        user.mojo = random.randint(0, 1000)

        fake_geoloc(user)

        # user.community = survey_profile.community
        append_user_role_from_community(_role_map(), user, survey_profile.community)

        self.users += [user]
        return user
