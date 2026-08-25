"""Everything this package raises, in one place.

One module so a caller can see the whole set at once, and so `except` has
somewhere to import from. It imports nothing from the rest of the package, which
is what keeps it from ever closing a cycle: everything here raises, so everything
here imports this, and an import running the other way would make the order
modules happen to load in decide whether the package works at all.

It imports nothing from the processor package this one consumes as a submodule
either. A refusal this package makes is this package's, and inheriting one from a
member it depends on would make a caller's `except` depend on which of the two
raised.
"""

from __future__ import annotations


class UnknownModelError(Exception):
    """No part goes by that name.

    The message names the parts that would have worked, because a refusal that
    does not costs the caller a search through the source.
    """


class NoFirmware(Exception):
    """The microcode this part runs was not supplied.

    Nintendo's program is not carried here and cannot be, so a part built
    without it can hold registers and answer nothing. Raised at the point the
    program would have been read rather than at construction, so a caller who
    only wants to ask what the catalogue holds is not stopped.
    """


class NeverReady(Exception):
    """The part was asked for an answer and never produced one.

    A run bounded rather than left open, because microcode that never lowers its
    busy line would otherwise hang the caller instead of telling them what
    happened. The message carries the number of steps that were spent, which is
    the figure a reader needs to tell a slow answer from no answer at all.
    """


class Unrecognised(Exception):
    """The image was read and matches nothing in the manifest.

    The furthest-from-actionable of the refusals, and the one whose message works
    hardest: it prints the digest that was computed so a reader can search for
    it, rather than only saying that it did not match.
    """


class Corrupt(Exception):
    """The image matches a dump the manifest records as bad.

    Distinct from `Unrecognised` because the answer is different. This one says
    the reader has a known-broken copy rather than an unknown one, which turns a
    search into a re-download.
    """


class WrongShape(Exception):
    """The image is not a whole number of words of the width the part reads.

    Raised before anything is loaded, because a program store filled from a
    truncated image would run and would run wrongly, which is worse than
    refusing.
    """
