# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import string

BASE62_LIST = string.digits + string.ascii_letters


class BaseXX:
    def __init__(self, base: str):
        self.base = base
        self.reverse_base = {c: i for i, c in enumerate(base)}

    def encode(self, n: int) -> str:
        if n == 0:
            return self.base[0]

        length = len(self.base)
        ret = ""
        while n != 0:
            mod = divmod(n, length)[1]
            ret = self.base[mod] + ret
            n //= length

        # We add a 'x' to distinguish from an integer
        return "x" + ret

    def decode(self, s: str) -> int:
        s = s[1:]
        length = len(self.base)
        ret = 0
        for i, c in enumerate(s[::-1]):
            ret += (length**i) * self.reverse_base[c]

        return ret


class Base62(BaseXX):
    def __init__(self):
        super().__init__(BASE62_LIST)


base62 = Base62()
