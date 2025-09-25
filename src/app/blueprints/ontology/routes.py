"""Routes for ontology and taxonomy management."""
# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from flask import flash, redirect, render_template, request, send_file, url_for
from flask_wtf import FlaskForm
from sqlalchemy import select

from app.flask.extensions import db
from app.services.taxonomies import (
    TaxonomyEntry,
    check_taxonomy_exists,
    create_entry,
    export_taxonomy_to_ods,
    get_all_taxonomy_names,
    update_entry,
)

from . import ontology_bp
from .forms import CreateTaxonomyForm, TaxonomyEntryForm


@ontology_bp.route("/create-taxonomy", methods=["GET", "POST"])
def create_taxonomy():
    """
    Provides a form to create a new taxonomy namespace.
    """
    form = CreateTaxonomyForm()
    if form.validate_on_submit():
        new_taxonomy_name = form.name.data
        flash(
            f"Taxonomy '{new_taxonomy_name}' created successfully. You can now add entries.",
            "success",
        )
        return redirect(url_for(".list_entries", taxonomy_name=new_taxonomy_name))

    return render_template("ontology/create_taxonomy.html", form=form)


@ontology_bp.route("/")
def list_entries():
    """
    Displays a list of entries for a selected taxonomy and provides a form
    for delete actions.
    """
    taxonomy_name = request.args.get("taxonomy_name")
    entries = []

    # Create a simple form instance specifically for the delete buttons' CSRF tokens.
    delete_form = FlaskForm()
    all_taxonomies = get_all_taxonomy_names()

    if taxonomy_name:
        query = (
            select(TaxonomyEntry)
            .where(TaxonomyEntry.taxonomy_name == taxonomy_name)
            .order_by(TaxonomyEntry.seq, TaxonomyEntry.name)
        )
        entries = db.session.scalars(query).all()

    return render_template(
        "ontology/list.html",
        entries=entries,
        taxonomy_name=taxonomy_name,
        all_taxonomies=all_taxonomies,
        delete_form=delete_form,  # <-- Pass the dedicated delete form to the template
    )


@ontology_bp.route("/create", methods=["GET", "POST"])
def create():
    """
    Provides a form to create a new entry in a specified taxonomy.
    """
    taxonomy_name = request.args.get("taxonomy_name")
    if not taxonomy_name:
        flash("Cannot create an entry without a 'taxonomy_name'.", "danger")
        return redirect(url_for(".list_entries"))

    form = TaxonomyEntryForm()
    if form.validate_on_submit():
        create_entry(
            taxonomy_name=taxonomy_name,
            name=form.name.data,
            category=form.category.data,
            value=form.value.data,
            seq=form.seq.data,
        )
        db.session.commit()
        flash(f"Entry '{form.name.data}' created successfully.", "success")
        return redirect(url_for(".list_entries", taxonomy_name=taxonomy_name))

    return render_template(
        "ontology/create.html",
        form=form,
        taxonomy_name=taxonomy_name,
    )


@ontology_bp.route("/edit/<int:entry_id>", methods=["GET", "POST"])
def edit(entry_id: int):
    """
    Provides a form to edit an existing taxonomy entry, identified by its ID.
    """
    entry = db.session.get(TaxonomyEntry, entry_id)
    if not entry:
        flash("Taxonomy entry not found.", "danger")
        return redirect(url_for(".list_entries"))

    form = TaxonomyEntryForm(obj=entry)
    if form.validate_on_submit():
        update_entry(
            taxonomy_name=entry.taxonomy_name,
            name=form.name.data,
            category=form.category.data,
            value=form.value.data,
            seq=form.seq.data,
        )
        db.session.commit()
        flash(f"Entry '{form.name.data}' updated successfully.", "success")
        return redirect(url_for(".list_entries", taxonomy_name=entry.taxonomy_name))

    return render_template(
        "ontology/edit.html",
        form=form,
        taxonomy_name=entry.taxonomy_name,
        entry_id=entry_id,
    )


@ontology_bp.route("/delete/<int:entry_id>", methods=["POST"])
def delete(entry_id: int):
    """
    Deletes a taxonomy entry after validating the CSRF token.
    """
    # Create a form instance to validate the CSRF token from the request.
    form = FlaskForm()
    if not form.validate_on_submit():
        flash(
            "Invalid CSRF token. The delete operation was aborted for your security.",
            "danger",
        )
        # Try to redirect back to the page the user was on.
        entry = db.session.get(TaxonomyEntry, entry_id)
        taxonomy_name = entry.taxonomy_name if entry else None
        return redirect(url_for(".list_entries", taxonomy_name=taxonomy_name))

    entry = db.session.get(TaxonomyEntry, entry_id)
    if entry:
        taxonomy_name = entry.taxonomy_name
        db.session.delete(entry)
        db.session.commit()
        flash(f"Entry '{entry.name}' has been deleted.", "success")
        return redirect(url_for(".list_entries", taxonomy_name=taxonomy_name))

    flash("Entry not found.", "danger")
    return redirect(url_for(".list_entries"))


@ontology_bp.route("/export/<string:taxonomy_name>.ods")
def export_ods(taxonomy_name: str):
    """
    Exports the entries of a specific taxonomy to an ODS spreadsheet file.
    """
    if not check_taxonomy_exists(taxonomy_name):
        flash(f"Taxonomy '{taxonomy_name}' not found.", "danger")
        return redirect(url_for(".list_entries"))

    # Generate the ODS file in memory using the service function
    ods_data = export_taxonomy_to_ods(taxonomy_name)

    download_name = f"{taxonomy_name}_export.ods"

    return send_file(
        ods_data,
        mimetype="application/vnd.oasis.opendocument.spreadsheet",
        as_attachment=True,
        download_name=download_name,
    )
