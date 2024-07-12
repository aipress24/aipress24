# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import base64
import sys
import uuid
from importlib import resources as rso
from pathlib import Path
from typing import Any

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
from flask_wtf import FlaskForm
from sqlalchemy.exc import IntegrityError
from svcs.flask import container
from werkzeug import Response
from wtforms import Field

from app.flask.extensions import db
from app.models.auth import KYCProfile, Role, User
from app.models.repositories import RoleRepository

from . import blueprint, kyc_models
from .dynform import TAG_LABELS, generate_form
from .field_label import requires_value, values_to_label
from .ontologies import zip_code_city_list
from .populate_profile import populate_form_data, populate_json_field
from .renderer import render_field
from .resized import resized
from .survey_dataclass import Profile
from .temporary_blob import delete_tmp_blob, pop_tmp_blob, read_tmp_blob, store_tmp_blob
from .xls_parser import XLSParser

# python 3.12
# type ListVal = list[dict[str, str]]

DEBUG_USE_DB = True
MODEL_FILENAME = "MVP-2-KYC-Commons-22_dev.xlsx"


@blueprint.route("/", methods=("GET", "POST"))
def index():
    return render_template("home.html")


@blueprint.route("/towns/<country_code>", methods=["GET"])
def zip_towns(country_code: str):
    # country_code = request.args.get("country_code", "FRA")
    return jsonify(zip_code_city_list(country_code))


def _load_user_data_in_form() -> None:
    user = g.user
    profile = user.profile
    print("////////////edit user:", user, file=sys.stderr)
    if not profile:
        # fake user at the moment
        print("//////////// generate empty profile", file=sys.stderr)
        profile = KYCProfile(
            profile_id="P002",
            info_professionnelle=populate_json_field("info_professionnelle", {}),
            match_making=populate_json_field("match_making", {}),
            hobbies=populate_json_field("hobbies", {}),
            business_wall=populate_json_field("business_wall", {}),
        )
        user.profile = profile

    session["profile_id"] = profile.profile_id
    session["form_raw_results"] = _populate_from_logged_user()
    session["modify_form"] = True


@blueprint.route("/profile", methods=("GET", "POST"))
def profile_page() -> str | Response:
    if current_user.is_authenticated:
        _load_user_data_in_form()
    profile_id = session.get("profile_id", "")
    # print(request.method, file=sys.stderr)
    if request.method == "GET":
        # todo: populate form
        return render_template(
            "profile.html", communities=survey["communities"], profile_id=profile_id
        )
    # post
    try:
        profile_id = request.form["profile"]
        profile = _get_profile(profile_id)
    except Exception:
        profile = None
        profile_id = session.get("profile_id", "")
    if profile is None:
        return render_template(
            "profile.html", communities=survey["communities"], profile_id=profile_id
        )
    return make_form(profile_id=profile.id)


def _get_profile(profile_id: str) -> Profile:
    for profile in survey["profiles"]:
        if profile.id == profile_id:
            return profile
    raise ValueError(f"unknown profile: {profile_id}")


def make_form(profile_id: str):
    # print(f"profile:{profile_id}", file=sys.stderr)
    profile = _get_profile(profile_id)
    if profile is None:
        return redirect(url_for(".profile_page"))
    return redirect(url_for(".wizard_page", profile_id=profile.id))


def _log_invalid_form(form):
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


def _oui_non(flag: bool) -> str:
    if flag:
        return "Oui"
    return "Non"


def _format_list_results(data: list | str | bool, key: str) -> str:
    if isinstance(data, list):
        value = ", ".join(data)
    elif isinstance(data, bool):
        value = _oui_non(data)
    else:  # str
        value = data
    if key == "password":
        # Minimal security
        try:
            value = "*" * len(value)
        except TypeError:
            value = ""
    return value


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
        data = field.data
    else:
        # read secondary data from request results
        data = _parse_request_form(key)

    if requires_value(key):
        label = values_to_label(data, key)
    else:
        label = _format_list_results(data, key)
    form_results[key] = label
    form_raw_results[key] = data


def _filter_out_label_tags(name: Any) -> str:
    for tag in TAG_LABELS:
        name = str(name).split(tag)[0].strip()
    return name


def _display_all_possible_fields() -> None:
    for field in survey["fields"].values():
        print(field.id, field.name, field.type, file=sys.stderr)


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
    print(f"Store: {blob_id} {filename} {len(content)}", file=sys.stderr)
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

    session["form_results"] = form_results
    session["form_raw_results"] = form_raw_results
    session["form_labels_results"] = form_labels_results
    session["form_id_key"] = form_id_key
    session["profile_id"] = profile_id


@blueprint.route("/wizard/<profile_id>", methods=["GET", "POST"])
def wizard_page(profile_id: str):
    form_data = None
    modify_form = bool(session.get("modify_form"))

    # form = generate_form(_get_profile(profile_id))
    if modify_form and request.method == "GET":
        # print("modify_form", file=sys.stderr)
        form_data = session["form_raw_results"]
        print("////////////edit form_data", form_data, file=sys.stderr)
        form = generate_form(
            _get_profile(profile_id), form_data, mode_edition=modify_form
        )
    else:
        form = generate_form(_get_profile(profile_id), mode_edition=modify_form)

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


def _get_diabled_flag_msg(raw_results) -> tuple[str, str]:
    if raw_results.get("validation_gcu", False):
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
    results = session.get("form_results", {"nothing": "nothing"})
    raw_results = session.get("form_raw_results", {"nothing": "nothing"})
    labels = session.get("form_labels_results", {"nothing": "nothing"})
    id_key = session.get("form_id_key", {"nothing": "nothing"})
    images = {}
    session["modify_form"] = False
    profile = _get_profile(session["profile_id"])
    groups = []
    for group in profile.groups:
        group_content: dict[str, Any] = {"label": group.label}
        ids = []
        for field, code in group.fields:
            if code in {"?", "N"}:
                continue
            ids.append(field.id)
            # add possible sub field
            sub_id = f"{field.id}_detail"
            if sub_id in id_key:
                ids.append(sub_id)
            if field.type == "photo":
                filename, uuid, data = read_tmp_blob(raw_results.get(field.name, ""))
                _write_tmp_data(data, uuid)
                if _allowed_image_suffix(filename):
                    # images[field.name] = (
                    #     "data:image/jpeg;base64,"
                    #     + base64.standard_b64encode(data).decode()
                    # )
                    images[field.name] = uuid
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
    raw_results = session.get("form_raw_results", {"nothing": "nothing"})
    if not raw_results.get("validation_gcu", False):
        return redirect(url_for(".undone_page"))
    msg_error: str = ""
    if DEBUG_USE_DB:
        msg_error = export_kyc_data()
    if msg_error:
        return render_template("db_error.html", msg_error=msg_error)
    else:
        return render_template("thanks.html")


@blueprint.route("/undone")
def undone_page():
    # delete tmp content:
    results = session.get("form_raw_results", {})
    uuid = delete_tmp_blob(results.get("photo", None))
    _remove_tmp_data(uuid)
    uuid = delete_tmp_blob(results.get("photo_carte_presse", None))
    _remove_tmp_data(uuid)
    return render_template("later.html")


@blueprint.route("/modify")
def modify_page():
    session["modify_form"] = True
    return redirect(url_for(".profile_page"))


def _civilite_to_gender(civilite: str) -> str:
    match civilite:
        case "Monsieur":
            gender = "M"
        case "Madame":
            gender = "F"
        case _:
            gender = "?"
    return gender


def _gender_to_civilite(gender: str) -> str:
    match gender:
        case "M":
            gender = "Monsieur"
        case "F":
            gender = "Madame"
        case _:
            gender = "Non renseigné"
    return gender


def _guess_organisation_name(results: dict) -> str:
    for field in ("nom_media", "nom_media_insti", "nom_agence_rp", "nom_orga"):
        value = results.get(field, "")
        # fixme: nom_media is a list of string, not a string
        if isinstance(value, list) and value:
            value = value[0]
        value = str(value).strip()
        if value:
            return value
    return ""


def _role_from_name(name: str) -> Role:
    role_repo = container.get(RoleRepository)
    roles_map = {role.name: role for role in role_repo.list()}
    return roles_map.get(name, roles_map["GUEST"])


def make_kyc_user_record() -> User:
    """Make a User record NON valid at this stage: it will require a validation step."""
    results = session.get("form_raw_results", {})
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

    profile = KYCProfile(
        profile_id=session.get("profile_id", ""),
        info_professionnelle=populate_json_field("info_professionnelle", results),
        match_making=populate_json_field("match_making", results),
        hobbies=populate_json_field("hobbies", results),
        business_wall=populate_json_field("business_wall", results),
    )

    user = User(
        last_name=results.get("last_name", ""),
        first_name=results.get("first_name", ""),
        photo=photo,
        photo_filename=photo_filename,
        photo_carte_presse=photo_carte_presse,
        photo_carte_presse_filename=photo_carte_presse_filename,
        pseudo=results.get("pseudo", ""),
        gender=_civilite_to_gender(results.get("civilite", "")),
        email=results.get("email", ""),
        email_secours=results.get("email_secours", ""),
        tel_mobile=results.get("tel_mobile", ""),
        password=results.get("password", ""),  # to be hashed by bcrypt
        fs_uniquifier=fs_uniquifier,
        user_valid=False,
        user_valid_comment="Utilisateur à valider",
        # duplicated: from KYCProfile
        hobbies=results.get("hobbies", ""),
        organisation_name=_guess_organisation_name(results),
    )

    user.profile = profile

    # debug: add some role
    user.roles.append(_role_from_name("EXPERT"))
    user.active = True

    return user


def _update_current_user(user: User) -> None:
    results = session.get("form_raw_results", {})
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

    profile = user.profile
    if not profile:
        # fake user at the moment
        print("//////////// generate empty profile", file=sys.stderr)
        profile = KYCProfile(
            profile_id="P002",
            info_professionnelle=populate_json_field("info_professionnelle", {}),
            match_making=populate_json_field("match_making", {}),
            hobbies=populate_json_field("hobbies", {}),
            business_wall=populate_json_field("business_wall", {}),
        )
        user.profile = profile

    profile.profile_id = session.get("profile_id", "")
    profile.info_professionnelle = populate_json_field("info_professionnelle", results)
    profile.match_making = populate_json_field("match_making", results)
    profile.hobbies = populate_json_field("hobbies", results)
    profile.business_wall = populate_json_field("business_wall", results)

    user.last_name = results.get("last_name", "")
    user.first_name = results.get("first_name", "")
    user.photo = photo
    user.photo_filename = photo_filename
    user.photo_carte_presse = photo_carte_presse
    user.photo_carte_presse_filename = photo_carte_presse_filename
    user.pseudo = results.get("pseudo", "")
    user.gender = _civilite_to_gender(results.get("civilite", ""))
    # email=results.get("email", ""),
    # email_secours=results.get("email_secours", "")
    user.tel_mobile = results.get("tel_mobile", "")
    # password=results.get("password", ""),  # to be hashed by bcrypt
    user.user_valid = False
    user.user_valid_comment = "Utilisateur à valider"
    # duplicated: from KYCProfile
    user.hobbies = results.get("hobbies", "")
    user.organisation_name = _guess_organisation_name(results)

    user.active = True


def export_kyc_data() -> str:
    if current_user.is_authenticated:
        return _update_current_user_data()
    else:
        return _store_user_data()


def _store_user_data() -> str:
    user = make_kyc_user_record()
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


def _update_current_user_data() -> str:
    db_session = db.session
    user = User.query.get(current_user.id)
    _update_current_user(user)
    error = ""
    try:
        db_session.commit()
    except IntegrityError as e:
        db_session.rollback()
        error = str(e)
    return error


def _store_tmp_blob_from_user(content: bytes, filename: str) -> tuple[str, int]:
    blob_id = store_tmp_blob(filename, content)
    print(f"Store: {blob_id} {filename} {len(content)}", file=sys.stderr)
    return filename, blob_id


def _populate_from_logged_user() -> dict[str, Any]:
    user = g.user
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
    data["pseudo"] = user.pseudo
    data["civilite"] = _gender_to_civilite(user.gender)
    data["email"] = user.email
    data["email_secours"] = user.email_secours
    data["tel_mobile"] = user.tel_mobile
    data["password"] = ""
    data["fs_uniquifier"] = user.fs_uniquifier
    data["hobbies"] = profile.hobbies["hobbies"]

    populate_form_data("info_professionnelle", profile.info_professionnelle, data)
    populate_form_data("match_making", profile.match_making, data)
    populate_form_data("hobbies", profile.hobbies, data)
    populate_form_data("business_wall", profile.business_wall, data)

    return data


def load_model() -> dict[str, Any]:
    parser = XLSParser()
    xls_file = rso.files(kyc_models) / MODEL_FILENAME
    parser.parse(xls_file)
    return parser.model


@blueprint.route("/test_mail/<email>", methods=["GET"])
def test_mail(email: str):
    new_email = email.strip()
    if not new_email:
        return ""
    if email_already_used(new_email):
        return ""
    return "ok"


def email_already_used(email: str) -> bool:
    exists_main = db.session.query(User).filter(User.email == email).first()
    exists_secours = db.session.query(User).filter(User.email_secours == email).first()
    return bool(exists_main) or bool(exists_secours)


survey = load_model()
