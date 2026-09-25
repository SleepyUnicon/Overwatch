"""The retry after a failed update -- see Bridge.retry_offer_if_failed.

Written after the first attempt at this hung the retry off the quiet-minute
guard inside offer_if_newer, where it could never fire: that window closes
after 60 s and the retry waits longer, so the bypass was dead code. The real
reason a failure was final is that nothing CALLED offer_if_newer afterwards.
"""
from pc.bridge import Bridge, RETRY_AFTER_S

MANIFEST = {"version": "9.9.9", "size": 1, "sha256": "x"}


def _bridge(now):
    b = Bridge(write_msg=lambda m: None,
               fetch_usage=lambda: None,
               fetch_manifest=lambda: MANIFEST,
               now=now)
    b._board_fw = "1.0.0"
    return b


def test_nothing_happens_without_a_failure():
    t = [1000.0]
    b = _bridge(lambda: t[0])
    seen = []
    b._on_ota_query = lambda cur: seen.append(cur)
    t[0] += RETRY_AFTER_S * 10
    b.retry_offer_if_failed()
    assert seen == [], "a board that never failed must not be re-offered"


def test_the_offer_comes_back_after_a_failure():
    t = [1000.0]
    b = _bridge(lambda: t[0])
    seen = []
    b._on_ota_query = lambda cur: seen.append(cur)

    b._ota_reset()                          # the update fails
    b.retry_offer_if_failed()
    assert seen == [], "not immediately"

    t[0] += RETRY_AFTER_S - 1
    b.retry_offer_if_failed()
    assert seen == [], "not before the cooldown"

    t[0] += 2
    b.retry_offer_if_failed()
    assert seen == ["1.0.0"], "the offer must come back"


def test_it_retries_once_per_failure():
    """Otherwise every poll re-offers for the rest of the daemon's life."""
    t = [1000.0]
    b = _bridge(lambda: t[0])
    seen = []
    b._on_ota_query = lambda cur: seen.append(cur)
    b._ota_reset()
    t[0] += RETRY_AFTER_S + 1
    b.retry_offer_if_failed()
    b.retry_offer_if_failed()
    t[0] += RETRY_AFTER_S * 5
    b.retry_offer_if_failed()
    assert len(seen) == 1


def test_a_board_that_never_said_its_version_is_left_alone():
    """_on_ota_query falls back to a fabricated version without one."""
    t = [1000.0]
    b = _bridge(lambda: t[0])
    b._board_fw = None
    seen = []
    b._on_ota_query = lambda cur: seen.append(cur)
    b._ota_reset()
    t[0] += RETRY_AFTER_S + 1
    b.retry_offer_if_failed()
    assert seen == []
