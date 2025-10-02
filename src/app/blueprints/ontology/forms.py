"""Forms for ontology and taxonomy management."""
# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from flask_wtf import FlaskForm
from wtforms import IntegerField, StringField, SubmitField
from wtforms.validators import DataRequired, Optional, ValidationError

from app.services.taxonomies import check_taxonomy_exists


class TaxonomyEntryForm(FlaskForm):
    """
    Form for creating and editing a TaxonomyEntry.
    It includes fields for name, category, value, and sequence number.
    """

    name = StringField("Name", validators=[DataRequired()])
    category = StringField("Category")
    value = StringField("Value", validators=[DataRequired()])
    seq = IntegerField("Sequence", default=0, validators=[Optional()])
    submit = SubmitField("Save")


class CreateTaxonomyForm(FlaskForm):
    """Form for creating a new taxonomy."""

    name = StringField(
        "Taxonomy Name",
        validators=[DataRequired()],
        description="A unique, machine-friendly name (e.g., 'project_status', 'document_type').",
    )
    submit = SubmitField("Create Taxonomy")

    def validate_name(self, field) -> None:
        """Ensure the taxonomy name does not already exist."""
        if check_taxonomy_exists(field.data):
            msg = f"A taxonomy named '{field.data}' already exists."
            raise ValidationError(msg)
