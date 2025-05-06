# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from flask import render_template_string
from markdown import markdown


class EmailTemplate:
    subject: str = ""
    template_md: str = ""
    template_html: str = ""

    def __init__(self, sender, recipient, **kwargs) -> None:
        self.sender = sender
        self.recipient = recipient
        self.kwargs = kwargs

    # FINISH
    def render(self):
        if self.template_md:
            # Should we do: markdown -> jinja ?
            # Or jinja -> markdown ?
            body_md = markdown(self.template_md)
            return render_template_string(body_md, **self.kwargs)
        if self.template_html:
            return render_template_string(self.template_html, **self.kwargs)
        msg = "No template"
        raise ValueError(msg)

    def send(self) -> None:
        ...
        # mail.send(self.sender, self.recipient, self.subject, self.render())
