# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from flask import current_app, request

from . import blueprint

# language=html
_PAGE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Upload test</title>
  <style>
    body {{ font-family: system-ui, sans-serif; max-width: 720px;
            margin: 2em auto; padding: 0 1em; }}
    pre  {{ background: #f4f4f4; padding: 1em; border-radius: 4px;
            overflow-x: auto; font-size: 0.95em; }}
    .ok  {{ color: #0a7a2f; }}
    .ko  {{ color: #b00020; }}
    label {{ display: block; margin: 1em 0 0.25em; }}
    button {{ margin-top: 1em; padding: 0.5em 1em; }}
  </style>
</head>
<body>
  <h1>Upload test</h1>
  <p>Le formulaire ci-dessous poste sur la même URL
     (<code>/tests/upload</code>). Les octets reçus sont lus puis jetés ;
     seules les métadonnées sont renvoyées. Utile pour savoir si un
     échec d'upload vient d'nginx (la requête n'arrive jamais ici,
     réponse 413 sans log applicatif) ou de Flask
     (<code>MAX_CONTENT_LENGTH = {max_mb}</code>).</p>

  <form method="post" enctype="multipart/form-data"
        action="/tests/upload">
    <label for="file">Fichier :</label>
    <input type="file" id="file" name="file" required>
    <button type="submit">Envoyer</button>
  </form>

  {result}
</body>
</html>
"""


@blueprint.route("/upload", methods=["GET", "POST"])
def upload() -> str:
    max_bytes = current_app.config.get("MAX_CONTENT_LENGTH") or 0
    max_mb = f"{max_bytes / (1024 * 1024):.1f} MB" if max_bytes else "illimité"

    if request.method != "POST":
        return _PAGE.format(max_mb=max_mb, result="")

    content_length = request.content_length or 0
    f = request.files.get("file")
    if f is None:
        result = (
            "<h2 class='ko'>Aucun fichier reçu</h2>"
            "<p>Le champ <code>file</code> est absent de la requête.</p>"
        )
        return _PAGE.format(max_mb=max_mb, result=result)

    # Drain the stream in chunks to make sure the full body got through.
    received = 0
    while chunk := f.stream.read(1024 * 1024):
        received += len(chunk)

    result = (
        "<h2 class='ok'>Upload reçu</h2>"
        f"<pre>filename       : {f.filename}\n"
        f"mimetype       : {f.mimetype}\n"
        f"content-length : {content_length} octets "
        f"({content_length / 1024 / 1024:.2f} MB)\n"
        f"lu depuis file : {received} octets "
        f"({received / 1024 / 1024:.2f} MB)\n"
        f"flask limit    : {max_mb}</pre>"
        "<p>(<code>content-length</code> couvre tout le corps multipart, "
        "donc légèrement supérieur à la taille du fichier — les boundaries "
        "et en-têtes s'ajoutent.)</p>"
    )
    return _PAGE.format(max_mb=max_mb, result=result)
