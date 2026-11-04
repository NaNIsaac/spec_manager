"""Names and mnemonics of the motors (#O / #o) or counters (#J / #j) of one SPEC session.

The command on a `#S` line names a motor as typed, usually by its mnemonic (`sx`), while `#P` and
`#L` use its name (`Sample_X`). The two header rows list them in the same order, which is the only
link between them. Files before about 2014 have no `#o` row; there only names resolve.
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass, field


def name_key(name: str) -> str:
    """Older files write Sample X where newer ones say Sample_X."""
    return re.sub(r"[\s_]", "", name).lower()


@dataclass
class Names:
    names: list[str] = field(default_factory=list)
    mnemonics: list[str] = field(default_factory=list)

    @property
    def paired(self) -> bool:
        """Whether every name has its mnemonic; a row count that differs makes the pairing unsafe."""
        return bool(self.mnemonics) and len(self.mnemonics) == len(self.names)

    def mnemonic(self, name: str) -> str | None:
        if not self.paired or (found := find(name, self.names)) is None:
            return None
        return self.mnemonics[self.names.index(found)]

    def resolve(self, key: str, among: Iterable[str] | None = None) -> str | None:
        """The name meant by a name or a mnemonic, if it is in `among` (default: every name)."""
        among = list(self.names if among is None else among)
        if (found := find(key, among)) is not None:
            return found
        if self.paired and key in self.mnemonics:
            name = self.names[self.mnemonics.index(key)]
            return find(name, among)
        return None


def find(name: str, names: Iterable[str]) -> str | None:
    """The entry of names meant by name: exact first, then ignoring case, spaces and underscores."""
    names = list(names)
    if name in names:
        return name
    return next((candidate for candidate in names if name_key(candidate) == name_key(name)), None)
