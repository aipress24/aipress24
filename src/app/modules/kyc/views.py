# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import base64
import sys
import uuid
from pathlib import Path
from typing import Any
from uuid import uuid4

from arrow import now
from email_validator import validate_email
from flask import (
    current_app,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)
from flask_login import current_user
from flask_sqlalchemy.session import Session
from flask_wtf import FlaskForm
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import scoped_session
from svcs.flask import container
from werkzeug import Response
from wtforms import Field

from app.constants import (
    BW_TRIGGER_LABEL,
    LABEL_INSCRIPTION_NOUVELLE,
    LABEL_MODIFICATION_MAJEURE,
    LABEL_MODIFICATION_MINEURE,
    LOCAL_TZ,
)
from app.enums import CommunityEnum
from app.flask.extensions import db
from app.models.auth import (
    KYCProfile,
    Role,
    User,
    clone_user,
    merge_values_from_other_user,
)
from app.models.repositories import RoleRepository
from app.modules.admin.utils import gc_all_auto_organisations
from app.modules.kyc.lib.valid_password import ValidPassword
from app.modules.kyc.organisation_utils import retrieve_user_organisation
from app.modules.swork.pages.masked_fields import MaskFields
from app.services.roles import generate_roles_map
from app.services.sessions import SessionService

from . import blueprint
from .community_role import append_user_role_from_community
from .dynform import TAG_LABELS, generate_form
from .field_label import data_to_label
from .ontology_loader import zip_code_city_list
from .populate_profile import populate_form_data, populate_json_field
from .renderer import render_field
from .resized import resized
from .survey_dataclass import SurveyField
from .survey_model import get_survey_fields, get_survey_model, get_survey_profile
from .temporary_blob import delete_tmp_blob, pop_tmp_blob, read_tmp_blob, store_tmp_blob

# python 3.12
# type ListVal = list[dict[str, str]]

# if MASKED_DATA set to "", the field label does not appear on
# profile page
MASKED_DATA = "*****"


@blueprint.route("/", methods=("GET", "POST"))
def index():
    return render_template("home.html")


@blueprint.route("/towns/<country_code>", methods=["GET"])
def zip_towns(country_code: str):
    # country_code = request.args.get("country_code", "FRA")
    return jsonify(zip_code_city_list(country_code))


def _load_user_data_in_session() -> None:
    user = g.user
    profile = user.profile
    # warning: no need to clone so early
    # cloned_user = clone_user(user)
    kyc_data = _populate_kyc_data_from_user(user)
    session_service = container.get(SessionService)
    session_service.set("profile_id", profile.profile_id)
    session_service.set("form_raw_results", kyc_data)
    session_service.set("modify_form", True)


def _create_session_id() -> str:
    """Create a unique session_id."""
    session_id = str(uuid.uuid4())
    session["session_id"] = session_id
    return str(session_id)


def _ensure_session_id() -> str:
    """Return current or new session_id."""
    session_id = session.get("session_id", "")
    if not session_id:
        session_id = _create_session_id()
    return session_id


@blueprint.route("/profile", methods=("GET", "POST"))
def profile_page() -> str | Response:
    _ensure_session_id()
    session_service = container.get(SessionService)
    survey = get_survey_model()

    if current_user.is_authenticated:
        _load_user_data_in_session()
    profile_id = session_service.get("profile_id", "")
    # print(request.method, file=sys.stderr)
    if request.method == "GET":
        # todo: populate form
        return render_template(
            "profile.html", communities=survey["communities"], profile_id=profile_id
        )
    # post
    try:
        profile_id = request.form["profile"]
        profile = get_survey_profile(profile_id)
    except Exception:
        profile = None
        profile_id = session_service.get("profile_id", "")
    if profile is None:
        return render_template(
            "profile.html", communities=survey["communities"], profile_id=profile_id
        )
    return make_form(profile_id=profile.id)


def make_form(profile_id: str):
    # print(f"profile:{profile_id}", file=sys.stderr)
    try:
        profile = get_survey_profile(profile_id)
    except ValueError:
        return redirect(url_for(".profile_page"))
    return redirect(url_for(".wizard_page", profile_id=profile.id))


def _log_invalid_form(form) -> None:
    print("form did not validate:", file=sys.stderr)
    for field in form:
        if field.name in {"_next", "csrf_token"}:
            continue
        print(f"field {field.name!r}:  {field.data!r}", file=sys.stderr)
        if field.errors:
            print(f"Error: {field.errors}", file=sys.stderr)
        if hasattr(field, "double_select"):
            name2 = f"{field.name}_detail"
            if name2 in request.form:
                print(f"field {name2!r}: {request.form[name2]!r}", file=sys.stderr)
            else:
                print(f"field {name2!r}: not found", file=sys.stderr)


def _parse_request_form(key: str) -> list[str]:
    dict_list = request.form.to_dict(flat=False)
    return dict_list.get(key, [])


def _parse_result(
    form_results: dict[str, Any],
    form_raw_results: dict[str, Any],
    field: Field | None = None,
    key: str = "",
) -> None:
    if field:
        # direct access to main Field data
        key = field.name
        if isinstance(field, ValidPassword):
            data = field.data.strip()
        else:
            data = field.data
    else:
        # read secondary data from request results
        data = _parse_request_form(key)
    label = data_to_label(data, key)
    form_results[key] = label
    form_raw_results[key] = data


def _filter_out_label_tags(name: Any) -> str:
    for tag in TAG_LABELS:
        name = str(name).split(tag)[0].strip()
    return name


# def _display_all_possible_fields() -> None:
#     survey = get_survey_model()
#     for survey_fields in survey["survey_fields"].values():
#         print(survey_fields.id, survey_fields.name, survey_fields.type, file=sys.stderr)


def _store_tmp_blob_preload(key: str) -> tuple[str, int]:
    req_dict = request.form.to_dict(flat=False)
    b64_content = req_dict[key + "_preload_b64"][0]
    filename = req_dict[key + "_preload_name"][0]
    content = base64.standard_b64decode(b64_content.encode())
    # size = len(content)
    blob_id = store_tmp_blob(filename, content)
    # print(f"Store b64: {blob_id} {filename} {len(content)}", file=sys.stderr)
    return filename, blob_id


def _store_tmp_blob(key: str) -> tuple[str, int]:
    try:
        filename = str(request.files[key].filename)
        content = request.files[key].read()
        # size = len(content)
    except KeyError:
        filename = ""
        content = b""
        # size = 0
    if _allowed_image_suffix(filename):
        content = resized(content)
    blob_id = store_tmp_blob(filename, content)
    # print(f"Store: {blob_id} {filename} {len(content)}", file=sys.stderr)
    return filename, blob_id


def _parse_valid_form(form: FlaskForm, profile_id: str) -> None:
    # _display_all_possible_fields()
    # print("request form:", request.form, file=sys.stderr)
    # print("request files:", request.files, file=sys.stderr)
    form_raw_results: dict[str, Any] = {}
    form_results: dict[str, Any] = {}
    form_labels_results: dict[str, Any] = {}
    form_id_key: dict[str, Any] = {}
    for field in form:
        key = field.name
        if key in {"_next", "csrf_token"}:
            continue
        id_field = field.id
        form_id_key[id_field] = key
        if field.type == "ValidImageField":
            filename, blob_id = _store_tmp_blob(key)
            if not filename:
                filename, blob_id = _store_tmp_blob_preload(key)
            form_raw_results[key] = blob_id
            form_results[key] = f"fichier {filename!r}"
            form_labels_results[key] = _filter_out_label_tags(field.label.text)
        else:
            _parse_result(form_results, form_raw_results, field=field)
            form_labels_results[key] = _filter_out_label_tags(field.label.text)
            if hasattr(field, "double_select"):
                id_field_detail = f"{id_field}_detail"
                key_detail = f"{field.name}_detail"
                form_id_key[id_field_detail] = key_detail
                _parse_result(form_results, form_raw_results, key=key_detail)
                form_labels_results[key_detail] = _filter_out_label_tags(
                    f"{field.label2}"
                )
    # for k, v in form_raw_results.items():
    #     print("======", k, v, file=sys.stderr)

    session_service = container.get(SessionService)
    session_service.set("form_results", form_results)
    session_service.set("form_raw_results", form_raw_results)
    session_service.set("form_labels_results", form_labels_results)
    session_service.set("form_id_key", form_id_key)
    session_service.set("profile_id", profile_id)


@blueprint.route("/wizard/<profile_id>", methods=["GET", "POST"])
def wizard_page(profile_id: str):
    form_data = None
    session_service = container.get(SessionService)
    modify_form = session_service.get("modify_form", False)
    profile = get_survey_profile(profile_id)
    if modify_form and request.method == "GET":
        # print("modify_form", file=sys.stderr)
        form_data = session_service.get("form_raw_results")
        # print("////////////edit form_data", form_data, file=sys.stderr)
        form = generate_form(profile, form_data, mode_edition=modify_form)
    else:
        form = generate_form(profile, mode_edition=modify_form)

    # print(f"WIZARD request method {request.method}", file=sys.stderr)
    # print(f"WIZARD profile:{profile_id}  {modify_form=}", file=sys.stderr)

    if request.method == "GET":
        ctx = {"form": form, "render_field": render_field}
        return render_template("wizard.html", **ctx)
    # debug
    # print("POST request form:", request.form, file=sys.stderr)
    if not form.validate_on_submit():
        print(f"validation errors {form.errors}", file=sys.stderr)
        _log_invalid_form(form)
        ctx = {"form": form, "render_field": render_field}
        return render_template("wizard.html", **ctx)
    _parse_valid_form(form, profile_id)
    return redirect(url_for(".validation_page"))


def _allowed_image_suffix(name: str) -> bool:
    return any(
        name.endswith(suffix)
        for suffix in (".jpg", ".JPG", ".jpeg", ".JPEG", ".png", ".PNG")
    )


def _get_diabled_flag_msg(raw_results: dict) -> tuple[str, str]:
    if raw_results.get("validation_gcu"):
        return "", ""
    msg = (
        "Conditions Générales d&apos;Utilisation non validées, "
        "validation du profil impossible."
    )
    return (
        "disabled",
        f'<div class="mt-3 flex justify-end"><p class="text-red-600">{msg}</p></div>',
    )


def _write_tmp_data(data: bytes, uuid: str) -> None:
    if not uuid:
        return
    images_dir = Path(current_app.instance_path) / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    path = images_dir / uuid
    if not path.is_file():
        path.write_bytes(data)
    # print("/////////////", str(file_path), file=sys.stderr)


def _remove_tmp_data(uuid: str) -> None:
    if not uuid:
        return
    images_dir = Path(current_app.instance_path) / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    path = images_dir / uuid
    path.unlink(missing_ok=True)


@blueprint.route("/images/<path:filename>")
def images_page(filename):
    images_dir = Path(current_app.instance_path) / "images"
    return send_from_directory(images_dir, filename)


@blueprint.route("/validation")
def validation_page():
    session_service = container.get(SessionService)
    results = session_service.get("form_results", {"nothing": "nothing"})
    raw_results = session_service.get("form_raw_results", {"nothing": "nothing"})
    # for k, v in raw_results.items():
    #     print("!!!!!!======", k, v, file=sys.stderr)
    labels = session_service.get("form_labels_results", {"nothing": "nothing"})
    id_key = session_service.get("form_id_key", {"nothing": "nothing"})
    profile_id = session_service.get("profile_id", "")
    images = {}
    session_service.set("modify_form", False)
    profile = get_survey_profile(profile_id)
    groups = []
    for group in profile.groups:
        group_content: dict[str, Any] = {"label": group.label}
        ids = []
        for survey_field, code in group.survey_fields:
            if code in {"?", "N"}:
                continue
            ids.append(survey_field.id)
            # add possible sub field
            sub_id = f"{survey_field.id}_detail"
            if sub_id in id_key:
                ids.append(sub_id)
            collect_photo_blob(images, raw_results, survey_field)
        group_content["ids"] = ids
        groups.append(group_content)

    gcudisabled, gcudisabledmsg = _get_diabled_flag_msg(raw_results)

    return render_template(
        "synthesis.html",
        results=results,
        labels=labels,
        id_key=id_key,
        profile_description=profile.description,
        groups=groups,
        images=images,
        gcudisabled=gcudisabled,
        gcudisabledmsg=gcudisabledmsg,
    )


@blueprint.route("/done")
def done_page():
    session_service = container.get(SessionService)
    raw_results = session_service.get("form_raw_results", {"nothing": "nothing"})
    if not raw_results.get("validation_gcu", False):
        return redirect(url_for(".undone_page"))
    msg_error = export_kyc_data()
    if msg_error:
        return render_template("db_error.html", msg_error=msg_error)
    return render_template("thanks.html")


@blueprint.route("/undone")
def undone_page():
    # delete tmp content:
    session_service = container.get(SessionService)
    results = session_service.get("form_raw_results", {})
    uuid = delete_tmp_blob(results.get("photo", None))
    _remove_tmp_data(uuid)
    uuid = delete_tmp_blob(results.get("photo_carte_presse", None))
    _remove_tmp_data(uuid)
    return render_template("later.html")


@blueprint.route("/modify")
def modify_page():
    session_service = container.get(SessionService)
    session_service.set("modify_form", True)
    return redirect(url_for(".profile_page"))


def _role_from_name(name: str) -> Role:
    role_repo = container.get(RoleRepository)
    roles_map = {role.name: role for role in role_repo.list()}
    return roles_map.get(name, roles_map["GUEST"])


def _make_new_kyc_user_record() -> User:
    """Make a User record for newly created user.

    user is not valid at this stage: it will require a validation step.
    Source of data is the "form_raw_results" of the session.
    """
    session_service = container.get(SessionService)
    results = session_service.get("form_raw_results", {})
    photo_blob_id = results.get("photo", None)
    photo_filename, photo_uuid, photo = pop_tmp_blob(photo_blob_id)
    carte_presse_blob_id = results.get("photo_carte_presse", None)
    (
        photo_carte_presse_filename,
        photo_carte_presse_filename_uuid,
        photo_carte_presse,
    ) = pop_tmp_blob(carte_presse_blob_id)

    _remove_tmp_data(photo_uuid)
    _remove_tmp_data(photo_carte_presse_filename_uuid)

    fs_uniquifier = results.get("fs_uniquifier") or uuid.uuid4().hex

    profile_id = session_service.get("profile_id", "")
    survey_profile = get_survey_profile(profile_id)

    profile = KYCProfile(
        profile_id=survey_profile.id,
        profile_code=survey_profile.code.name,
        profile_label=survey_profile.label,
        profile_community=survey_profile.community.name,
        contact_type=survey_profile.contact_type.name,
        presentation=results.get("presentation", ""),
        # not in KYC, so default values (via populate):
        show_contact_details=populate_json_field("show_contact_details", {}),
        info_personnelle=populate_json_field("info_personnelle", results),
        info_professionnelle=populate_json_field("info_professionnelle", results),
        match_making=populate_json_field("match_making", results),
        business_wall=populate_json_field("business_wall", results),
    )

    user = User(
        last_name=results.get("last_name", ""),
        first_name=results.get("first_name", ""),
        photo=photo,
        photo_filename=photo_filename,
        photo_carte_presse=photo_carte_presse,
        photo_carte_presse_filename=photo_carte_presse_filename,
        gender=results.get("civilite", ""),
        email=results.get("email", ""),
        email_secours=results.get("email_secours", ""),
        tel_mobile=results.get("tel_mobile", ""),
        password=results.get("password", ""),  # to be hashed by bcrypt
        fs_uniquifier=fs_uniquifier,
        is_clone=False,
        # is_cloned=False,
        active=False,
        validation_status=LABEL_INSCRIPTION_NOUVELLE,
        gcu_acceptation=results.get("validation_gcu", False),
    )

    user.profile = profile

    append_user_role_from_community(
        generate_roles_map(), user, survey_profile.community
    )
    # debug: add some role
    # user.roles.append(_role_from_name("EXPERT"))

    return user


def _set_default_kyc_profile(user: User) -> None:
    """Add an empty KYCProfile to the user.

    Should never be needed on coherent DB.
    """
    profile_id = "P002"  # aka PRESS_MEDIA journaliste salarié
    survey_profile = get_survey_profile(profile_id)
    # fake user at the moment
    profile = KYCProfile(
        profile_id=survey_profile.id,
        profile_code=survey_profile.code.name,
        profile_label=survey_profile.label,
        profile_community=survey_profile.community.name,
        contact_type=survey_profile.contact_type.name,
        show_contact_details=populate_json_field("show_contact_details", {}),
        info_personnelle=populate_json_field("info_personnelle", {}),
        info_professionnelle=populate_json_field("info_professionnelle", {}),
        match_making=populate_json_field("match_making", {}),
        business_wall=populate_json_field("business_wall", {}),
    )
    user.profile = profile


def _update_from_current_user(orig_user: User) -> User:
    session_service = container.get(SessionService)
    results = session_service.get("form_raw_results", {})
    photo_blob_id = results.get("photo", None)
    photo_filename, photo_uuid, photo = pop_tmp_blob(photo_blob_id)
    carte_presse_blob_id = results.get("photo_carte_presse", None)
    (
        photo_carte_presse_filename,
        photo_carte_presse_filename_uuid,
        photo_carte_presse,
    ) = pop_tmp_blob(carte_presse_blob_id)

    _remove_tmp_data(photo_uuid)
    _remove_tmp_data(photo_carte_presse_filename_uuid)

    if not orig_user.profile:  # should never happen
        _set_default_kyc_profile(orig_user)

    # now clone the origin user
    cloned_user = clone_user(orig_user)
    # orig_user.is_cloned = True

    profile = cloned_user.profile
    profile_id = session_service.get("profile_id", "")
    survey_profile = get_survey_profile(profile_id)
    profile.profile_id = survey_profile.id
    profile.profile_code = survey_profile.code.name
    profile.profile_label = survey_profile.label
    profile.profile_community = survey_profile.community.name
    profile.contact_type = survey_profile.contact_type.name
    profile.presentation = results.get("presentation", "")
    # not in KYC -> no update
    # profile.show_contact_details=populate_json_field("show_contact_details", {}),
    profile.info_personnelle = populate_json_field("info_personnelle", results)
    profile.info_professionnelle = populate_json_field("info_professionnelle", results)
    profile.match_making = populate_json_field("match_making", results)
    profile.business_wall = populate_json_field("business_wall", results)

    cloned_user.last_name = results.get("last_name", "")
    cloned_user.first_name = results.get("first_name", "")
    cloned_user.photo = photo
    cloned_user.photo_filename = photo_filename

    # remove hard coded URL from faker:
    cloned_user.profile_image_url = ""

    cloned_user.photo_carte_presse = photo_carte_presse
    cloned_user.photo_carte_presse_filename = photo_carte_presse_filename
    cloned_user.gender = results.get("civilite", "")
    # email=results.get("email", ""),
    # email_secours=results.get("email_secours", "")
    cloned_user.tel_mobile = results.get("tel_mobile", "")
    # for k, v in results.items():
    #     print("/////////////", k, v, file=sys.stderr)
    cloned_user.gcu_acceptation = results.get("validation_gcu", False)
    # duplicated: from KYCProfile

    # cloned_user.community = survey_profile.community
    append_user_role_from_community(
        generate_roles_map(), cloned_user, survey_profile.community
    )

    return cloned_user


def export_kyc_data() -> str:
    if current_user.is_authenticated:
        return _update_current_user_data()
    return _store_new_user_data()


def _store_new_user_data() -> str:
    user = _make_new_kyc_user_record()
    db_session = db.session
    db_session.merge(user)
    # db_session.add(user)
    error = ""
    try:
        db_session.commit()
    except IntegrityError as e:
        db_session.rollback()
        error = str(e)
    return error


def _get_critical_modified_fields(orig_user: User, cloned_user: User) -> list[str]:
    """If the differences between both user are on critical fields, validation
    is required.
    """
    convert = {"civilite": "gender"}

    def _get_value(user: User, field_name: str) -> Any:
        if field_name.startswith("trigger"):
            profile = user.profile
            return profile.business_wall[field_name]
        key = convert.get(field_name, field_name)
        return getattr(user, key)

    critical = [field.name for field in get_survey_fields() if field.validate_changes]
    critical_modified_fields = []
    for key_name in critical:
        if _get_value(orig_user, key_name) != _get_value(cloned_user, key_name):
            critical_modified_fields.append(convert.get(key_name, key_name))
    return critical_modified_fields


def _modified_fields_as_label(attr_names: list[str]) -> str:
    convert = {"civilite": "gender"}
    names = [convert.get(x, x) for x in attr_names]
    names = [BW_TRIGGER_LABEL.get(x, x) for x in names]
    return " ,".join(names)


def _modification_validation_required(
    db_session: scoped_session[Session],
    cloned_user: User,
    critical_modified_fields: list[str],
) -> str:
    cloned_user.active = False
    modified_text = _modified_fields_as_label(critical_modified_fields)
    cloned_user.validation_status = f"{LABEL_MODIFICATION_MAJEURE} {modified_text}"
    cloned_user.modified_at = now(LOCAL_TZ)
    print(f"#### {cloned_user} validation required: {modified_text}", file=sys.stderr)
    db_session.merge(cloned_user)  # add the cloned user to DB
    # orig_user is unchanged from modifs, but will be saved with the is_cloned
    # informations
    error = ""
    try:
        db_session.commit()
    except IntegrityError as e:
        db_session.rollback()
        error = str(e)
    return error


def _minor_modification_validated(
    db_session: scoped_session[Session],
    orig_user: User,
    cloned_user: User,
    critical_modified_fields: list[str],
) -> str:
    # forget cloned_user
    cloned_user.validation_status = LABEL_MODIFICATION_MINEURE
    merge_values_from_other_user(orig_user, cloned_user)
    auto_or_inviting_organisation = retrieve_user_organisation(orig_user)
    if auto_or_inviting_organisation:
        orig_user.organisation_id = auto_or_inviting_organisation.id
    orig_user.active = True
    orig_user.modified_at = now(LOCAL_TZ)
    orig_user.validated_at = now(LOCAL_TZ)
    db_session.merge(orig_user)  # store the cloned user to DB
    cloned_user = None
    error = ""
    try:
        db_session.commit()
    except IntegrityError as e:
        db_session.rollback()
        error = str(e)
    # maybe some auto organisation is orphan:
    gc_all_auto_organisations()
    return error


def _update_current_user_data() -> str:
    db_session = db.session
    orig_user = User.query.get(current_user.id)
    print("//Updating// updating user:", orig_user, file=sys.stderr)
    cloned_user = _update_from_current_user(orig_user)
    critical_modified_fields = _get_critical_modified_fields(orig_user, cloned_user)
    if critical_modified_fields:
        return _modification_validation_required(
            db_session, cloned_user, critical_modified_fields
        )
    return _minor_modification_validated(
        db_session, orig_user, cloned_user, critical_modified_fields
    )


def _store_tmp_blob_from_user(content: bytes, filename: str) -> tuple[str, int]:
    blob_id = store_tmp_blob(filename, content)
    # print(f"Store: {blob_id} {filename} {len(content)}", file=sys.stderr)
    return filename, blob_id


def _populate_kyc_data_from_user(user: User) -> dict[str, Any]:
    profile = user.profile
    data: dict[str, Any] = {}
    # debug: photos to be extracted as blobs
    blob_id_photo = store_tmp_blob(user.photo_filename, user.photo)
    data["photo"] = blob_id_photo
    data["photo_filename"] = user.photo_filename

    blob_id_carte = store_tmp_blob(
        user.photo_carte_presse_filename, user.photo_carte_presse
    )
    data["photo_carte_presse"] = blob_id_carte
    data["photo_carte_presse_filename"] = user.photo_carte_presse_filename

    data["last_name"] = user.last_name
    data["first_name"] = user.first_name
    data["civilite"] = user.gender
    data["presentation"] = user.profile.presentation
    data["email"] = user.email_safe_copy or user.email
    data["email_secours"] = user.email_secours
    data["tel_mobile"] = user.tel_mobile
    data["password"] = ""
    data["fs_uniquifier"] = user.fs_uniquifier
    data["validation_gcu"] = user.gcu_acceptation

    # no show_contact_details here. (not in KYC)
    populate_form_data("info_personnelle", profile.info_personnelle, data)
    populate_form_data("info_professionnelle", profile.info_professionnelle, data)
    populate_form_data("match_making", profile.match_making, data)
    populate_form_data("business_wall", profile.business_wall, data)

    return data


@blueprint.route("/check_mail/<email>", methods=["GET"])
def check_mail(email: str) -> str:
    new_email = email.strip()
    if not new_email:
        return ""
    try:
        validate_email(new_email)
    except Exception:
        return ""
    if email_already_used(new_email):
        return ""
    return "ok"


def email_already_used(email: str) -> bool:
    email = email.lower()
    return bool(
        db.session.query(User)
        .filter(
            or_(
                func.lower(User.email) == email, func.lower(User.email_secours) == email
            )
        )
        .first()
    )


def format_kyc_data(kyc_data: dict[str, Any]) -> dict[str, Any]:
    # raw_results = session["form_raw_results"]
    return {key: data_to_label(value, key) for key, value in kyc_data.items()}


def collect_photo_blob(
    images: dict,
    kyc_data: dict[str, Any],
    survey_field: SurveyField,
) -> str:
    url = ""
    if survey_field.type == "photo":
        filename, uuid, data = read_tmp_blob(kyc_data.get(survey_field.name, ""))
        _write_tmp_data(data, uuid)
        if _allowed_image_suffix(filename):
            images[survey_field.name] = uuid
            images[survey_field.id] = uuid
            url = url_for("kyc.images_page", filename=uuid)
    return url


def profile_photo_local_url(user: User, field="photo") -> str:
    """Return local or distant photo url (if photo is in a blob or profile_url
    is defined).

    'field' could be "photo" or "photo_carte_presse".

    This need to be reworked.
    """
    if field == "photo" and user.profile_image_url:
        # no check if local copy available
        return user.profile_image_url  # mainly for fake users
    photo_bytes = getattr(user, field)
    uuid = uuid4().hex
    _write_tmp_data(photo_bytes, uuid)
    url = url_for("kyc.images_page", filename=uuid)
    # broke: we dont habe User but UserVM
    # if field == "photo":
    #     user.profile_image_url = url
    return url


def _update_profile_display_level(level: int) -> int:
    level = max(0, min(2, level))
    user = g.user
    profile = user.profile
    if profile.display_level != level:
        profile.display_level = level
        db_session = db.session
        db_session.merge(user)
        db_session.commit()
    return level


def public_info_context(user: User, mask_fields: MaskFields) -> dict[str, Any]:
    # def public_info_context(user: User, mask_fields: list[str]) -> dict[str, Any]:
    """Return group of fields visible (with level visibility of the user).

    The "mask_fields" contains list of field names that should not be displayed.
    """
    profile = user.profile
    kyc_data = _populate_kyc_data_from_user(user)
    return _public_group_info_profile(profile, kyc_data, mask_fields)


def admin_info_context(user: User) -> dict[str, Any]:
    # def public_info_context(user: User, mask_fields: list[str]) -> dict[str, Any]:
    """Return group of fields visible by Admin of app."""
    profile = user.profile
    kyc_data = _populate_kyc_data_from_user(user)
    return _admin_group_info_profile(profile, kyc_data)


def _public_group_info(level: int) -> dict[str, Any]:
    """Return group of fields visible with level visibility level.

    level can be 0, 1 or 2
    """
    if not current_user.is_authenticated:
        msg = "No currently authenticated user"
        raise ValueError(msg)

    # direct change of display_level value
    level = _update_profile_display_level(level)

    user = g.user
    profile = user.profile
    kyc_data = _populate_kyc_data_from_user(user)
    return _public_group_info_profile(profile, kyc_data)


def _public_group_info_profile(
    profile: KYCProfile,
    kyc_data,
    mask_fields: MaskFields | None = None,
) -> dict[str, Any]:
    def add_information_row(field_id: str, name: str, description: str) -> None:
        nonlocal ids, results, field_labels, id_results, images, kyc_data, urls

        value = results.get(name)
        if value is None or (isinstance(value, str) and not value.strip()):
            return
        ids.append(field_id)
        field_labels[field_id] = description.strip()
        id_results[field_id] = value

    level = profile.display_level
    survey_profile = get_survey_profile(profile.profile_id)
    results = format_kyc_data(kyc_data)
    if mask_fields:
        for key in mask_fields.masked:
            results[key] = MASKED_DATA
        masked_story = mask_fields.story
    else:
        masked_story = ""

    # Special case: never show country and zip code, but only country
    results["pays_zip_ville_detail"] = ""

    field_labels = {}
    images = {}
    urls = {}
    groups = []
    id_results = {}
    for group in survey_profile.groups:
        group_content: dict[str, Any] = {"label": group.label}
        ids = []
        for survey_field, code in group.survey_fields:
            if code in {"?", "N"}:
                continue
            if not survey_field.is_visible(level):
                continue

            # check possible sub field (dual fields of KYC)
            sub_name = f"{survey_field.name}_detail"
            if sub_name in results:
                label1, label2 = survey_field.description.split(";")
                add_information_row(survey_field.id, survey_field.name, label1)
                add_information_row(f"{survey_field.id}_detail", sub_name, label2)
            else:
                add_information_row(
                    survey_field.id, survey_field.name, survey_field.description
                )
            if url := collect_photo_blob(images, kyc_data, survey_field):
                urls[survey_field.id] = url
        if not ids:
            continue
        group_content["ids"] = ids
        groups.append(group_content)
    return {
        "results": id_results,
        "labels": field_labels,
        "profile_description": survey_profile.description,
        "kycgroups": groups,
        "urls": urls,
        "masked_story": masked_story,
    }


def _admin_group_info_profile(
    profile: KYCProfile,
    kyc_data,
) -> dict[str, Any]:
    def add_information_row(field_id: str, name: str, description: str) -> None:
        nonlocal ids, results, field_labels, id_results, images, kyc_data, urls

        value = results.get(name)
        if value is None or (isinstance(value, str) and not value.strip()):
            return
        ids.append(field_id)
        field_labels[field_id] = description.strip()
        id_results[field_id] = value

    survey_profile = get_survey_profile(profile.profile_id)
    results = format_kyc_data(kyc_data)

    field_labels = {}
    images = {}
    urls = {}
    groups = []
    id_results = {}
    for group in survey_profile.groups:
        group_content: dict[str, Any] = {"label": group.label}
        ids = []
        for survey_field, code in group.survey_fields:
            if code in {"?", "N"}:
                continue

            # check possible sub field (dual fields of KYC)
            sub_name = f"{survey_field.name}_detail"
            if sub_name in results:
                label1, label2 = survey_field.description.split(";")
                add_information_row(survey_field.id, survey_field.name, label1)
                add_information_row(f"{survey_field.id}_detail", sub_name, label2)
            else:
                add_information_row(
                    survey_field.id, survey_field.name, survey_field.description
                )
            if url := collect_photo_blob(images, kyc_data, survey_field):
                urls[survey_field.id] = url
        if not ids:
            continue
        group_content["ids"] = ids
        groups.append(group_content)
    return {
        "results": id_results,
        "labels": field_labels,
        "profile_description": survey_profile.description,
        "kycgroups": groups,
        "urls": urls,
    }


def profil_groups_initial_level() -> dict[str, Any]:
    if not current_user.is_authenticated:
        msg = "No currently authenticated user"
        raise ValueError(msg)
    user = g.user
    profile = user.profile
    return {
        "display_level": profile.display_level,
        "profile_community": str(CommunityEnum[profile.profile_community]),
        "profile_label": profile.profile_label,
    }


@blueprint.route("/profil_groups/<level>", methods=["GET"])
def profil_groups_page(level: str):
    try:
        level_int = int(level)
    except ValueError:
        level_int = 1
    level_init = max(0, min(level_int, 2))
    return jsonify(_public_group_info(level_init))
