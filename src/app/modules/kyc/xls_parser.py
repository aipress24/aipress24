# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-onlyfrom __future__ import annotations

from __future__ import annotations

from pathlib import Path
from typing import Any

from openpyxl.reader.excel import load_workbook

from .survey_dataclass import Communities, Group, ModelLoader, Profile, SurveyField

COLOR_CODES = {
    "FF32CD32": "M",  # Mandatory
    "FFFFA500": "O",  # Optional
    "FFC9211E": "N",  # No
}

ROW_FIELDS = 5
ROW_COMMUNITY = 1
ROW_PROFILE = 2
COL_LABEL = 0
COL_PUBLIC_ALLOW = 1
COL_PUBLIC_DEFAULT = 2
COL_MESSAGE = 3
COL_ID = 4
COL_TYPE = 5
COL_COMMENT = 6
COL_PROFILE = 7


class XLSParser(ModelLoader):
    def __init__(self) -> None:
        self.survey_fields: dict[str, SurveyField] = {}
        self.profiles: list[Profile] = []
        self.communities: Communities = Communities()

    def parse(self, source: Path | str) -> None:
        wb = load_workbook(source)
        ws = wb.active

        rows = list(ws.iter_rows())

        self.read_fields(rows)
        self.read_profiles(rows)
        self.parse_fields(rows)
        self.build_communities()

    @property
    def model(self) -> dict[str, Any]:
        return {
            "communities": self.communities,
            "survey_fields": self.survey_fields,
            "profiles": self.profiles,
        }

    def parse_fields(self, rows) -> None:
        field_i = 0
        for row in rows[ROW_FIELDS:]:
            field_description = row[COL_LABEL].value
            field_name = row[COL_ID].value
            field_type = row[COL_TYPE].value
            if field_type == "title":
                # it's a group title
                for i, _cell in enumerate(row[COL_PROFILE:]):
                    if i >= len(self.profiles):
                        break
                    profile = self.profiles[i]
                    profile.groups.append(Group(label=field_description))
                continue
            if not field_name:
                continue
            field_i += 1
            field_id = f"F{field_i:03}"
            for i, cell in enumerate(row[COL_PROFILE:]):
                if i >= len(self.profiles):
                    break
                profile = self.profiles[i]
                code = COLOR_CODES.get(cell.fill.fgColor.rgb, "?")
                if code == "N":
                    continue
                profile_current_group = profile.groups[-1]
                field = self.survey_fields[field_id]
                profile_current_group.survey_fields.append((field, code))

    def dump(self):
        print("# Modèle KYC")
        print()
        self.dump_fields()
        self.dump_profiles()

    def read_fields(self, rows) -> None:
        field_i = 0
        for row in rows[ROW_FIELDS:]:
            field_description = row[COL_LABEL].value
            field_public_allow = bool((row[COL_PUBLIC_ALLOW].value or "").strip())
            field_public_default = bool((row[COL_PUBLIC_DEFAULT].value or "").strip())
            field_message = row[COL_MESSAGE].value
            field_name = row[COL_ID].value
            field_type = row[COL_TYPE].value
            if not field_name or field_type == "title":
                continue
            field_i += 1
            field_id = f"F{field_i:03}"
            field = SurveyField(
                id=field_id,
                name=field_name,
                public_allow=field_public_allow,
                public_default=field_public_default,
                type=field_type,
                description=field_description,
                upper_message=field_message,
            )
            self.survey_fields[field_id] = field

    def read_profiles(self, rows) -> None:
        for i, cell in enumerate(rows[ROW_PROFILE][COL_PROFILE:]):
            description = cell.value
            if not description or not description.strip():
                break
            id = f"P{i + 1:03}"
            profile = Profile(id=id, description=description)
            self.profiles.append(profile)
        nb_profiles = len(self.profiles)
        community = ""
        for i, cell in enumerate(rows[ROW_COMMUNITY][COL_PROFILE:]):
            if i >= nb_profiles:
                break
            if cell.value:
                community = cell.value
            profile = self.profiles[i]
            profile.community = community

    def build_communities(self) -> None:
        self.communities = Communities()
        for profile in self.profiles:
            self.communities.add_profile(profile)

    def dump_fields(self):
        print()
        print("## Fields")
        print()
        for field in self.survey_fields.values():
            print(f"### {field.id}")
            print()
            print(field.description)
            print()

    def dump_profiles(self):
        print()
        print("## Profiles")
        print()
        for profile in self.profiles:
            print(f"### {profile.community} - {profile.id}")
            print()
            print(profile.description)
            print()
            for group in profile.groups:
                print(f"grouo: {group.label}")
                for field, code in group.survey_fields:
                    if code in {"?", "N"}:
                        continue
                    print(f"- {field.id}({code}): {field.description}")
            print()
