# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from io import StringIO

from app.flask.components.forms import Form

# language=toml
FORM_SPEC = """
[field.subheader]
title = "subheader"
type = "text"
group = "header"

[field.image_url]
title = "image_url"
type = "text"
group = "header"

# [field.owner]
# title = "owner"
# type = "relation"

# [field.view_count]
# title = "view_count"
# type = "int"
# read_only = true
#
# [field.like_count]
# title = "like_count"
# type = "int"
# read_only = true
#
# [field.comment_count]
# title = "comment_count"
# type = "int"
# read_only = true
#
# [field.published_at]
# title = "published_at"
# type = "datetime"

[field.expired_at]
title = "expired_at"
type = "datetime"

[field.created_at]
title = "created_at"
type = "datetime"

[field.modified_at]
title = "modified_at"
type = "datetime"

[field.deleted_at]
title = "deleted_at"
type = "datetime"

# [field.type]
# title = "type"
# type = "int"

[field.status]
title = "status"
type = "text"

[field.title]
title = "title"
type = "text"

[field.content]
title = "content"
type = "text"

[field.summary]
title = "summary"
type = "text"

[field.url]
title = "url"
type = "text"

[field.info_source]
title = "info_source"
type = "text"

[field.genre]
title = "genre"
type = "text"
group = "metadata"

[field.topic]
title = "topic"
type = "text"
group = "metadata"

[field.section]
title = "section"
type = "text"
group = "metadata"

[field.language]
title = "language"
type = "text"
group = "metadata"

[field.sector]
title = "sector"
type = "text"
group = "metadata"

[field.job]
title = "job"
type = "text"
group = "metadata"

[field.competency]
title = "competency"
type = "text"
group = "metadata"

[field.copyright_holder]
title = "copyright_holder"
type = "text"
group = "copyright"

[field.copyright_notice]
title = "copyright_notice"
type = "text"
group = "copyright"
"""


def test_form_spec():
    form = Form.from_file(StringIO(FORM_SPEC))
    assert len(form.fields) > 0
    assert form.fields["title"].type() == "text"
