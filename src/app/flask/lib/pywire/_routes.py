# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from flask import jsonify, request
from flask.app import Flask

from app.lib.names import to_snake_case

from ._components import component_registry


def register_pywire(app: Flask) -> None:
    app.route("/livewire/message/<component>", methods=["POST"])(livewire_message)


def livewire_message(component):
    assert request.json

    fingerprint: dict = request.json["fingerprint"]
    component_id = fingerprint["id"]
    component_class = component_registry[component]
    component_instance = component_class(id=component_id)
    component_instance._restore(request.json["serverMemo"]["data"])

    for update in request.json["updates"]:
        payload = update["payload"]

        update_type = to_snake_case(update["type"])

        func_name = f"livewire_{update_type}"
        func = globals().get(func_name)
        if not func:
            raise ValueError(f"Unknown update type: {update['type']}")

        func(component_instance, payload)

    assert callable(component_instance.render)

    response = {
        "effects": {
            "html": component_instance.render(),
            "dirty": component_instance._dirty,
        },
        "serverMemo": {
            "data": component_instance._state(),
            "htmlHash": "c3b2ae73",
            "checksum": (
                "390ac5acd01d5ec09d67dac95ff69d26734956559e9a59249b4c552c0451f2da"
            ),
        },
    }
    return jsonify(response)


def livewire_call_methos(component_instance, payload) -> None:
    method_name = payload["method"]
    method_params = payload["params"]
    method = getattr(component_instance, method_name)
    method(*method_params)
    # component_instance._call_method(method_name, method_params)


def livewire_sync_input(component_instance, payload) -> None:
    attr_name = payload["name"]
    attr_value = payload["value"]
    segments = attr_name.split(".")

    if len(segments) == 1:
        setattr(component_instance, attr_name, attr_value)
        return

    obj = getattr(component_instance, segments[0])
    for segment in segments[1:-1]:
        obj = obj[segment]
    obj[segments[-1]] = attr_value

    # setattr(obj, segments[-1], attr_value)
    # component_instance._sync_input(att_name, attr_value)


def livewire_fire_event(component_instance, payload) -> None:
    # debug(payload)
    event_name = payload["event"]
    event_params = payload["params"]
    method_name = f"on_{event_name.replace('-', '_')}"
    method = getattr(component_instance, method_name)
    method(*event_params)
