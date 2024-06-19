# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from ._types import Spec

REPUT_MEMBER_SPEC: Spec = [
    ("nb_foller_mbr", "Social Net", 0.1),
    ("nb_follg_mbr", "Social Net", 0.1),
    ("nb_follg_org", "Social Net", 0.1),
    ("nb_follg_gr", "Social Net", 0.2),
    ("nb_likes_art", "Social Net", 0.3),
    ("nb_ptage_art", "Social Net", 0.5),
]

REPUT_JOURNALIST_SPEC: Spec = [
    ("nb_suj_prop", "Métier", 4),
    ("nb_suj_com", "Métier", 5),
    ("nb_av_enq", "Métier", 5),
    ("nb_art_pub", "Métier", 5),
    ("nb_ption_eve", "Métier", 2),
    ("nb_anc_pro", "Métier", 2),
    ("nb_prage", "Engagement", 5),
    ("nb_art_pub_cc", "Engagement", 5),
    ("nb_wbnr_cc", "Engagement", 5),
    ("nb_form_cc", "Engagement", 5),
    ("nb_anc_aip24", "Engagement", 2),
    ("nb_med_tring", "Prestations", 3),
    ("nb_tab_rde", "Prestation", 3),
    ("nb_anim_conf", "Prestation", 3),
    ("nb_cons_art", "Ventes", 3),
    ("nb_justif_pub", "Ventes", 3),
    ("nb_cess_droit", "Ventes", 4),
    *REPUT_MEMBER_SPEC,
]

REPUT_EDITOR_SPEC: Spec = REPUT_MEMBER_SPEC

REPUT_GENERIC_USER_SPEC: Spec = REPUT_MEMBER_SPEC

REPUT_MEDIA_SPEC: Spec = []
REPUT_COM_SPEC: Spec = []
REPUT_GENERIC_ORG_SPEC: Spec = []
