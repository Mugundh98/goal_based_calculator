"""At most SIMULATION_CONCURRENCY Monte Carlo runs at a time, across all requests.

One 10,000-path run of the longest retirement plan the API accepts needs about 180 MB on top of
the ~200 MB the API itself uses: on the free hosting plan (512 MB) two at once would get the
process killed. Further requests wait for a free slot - a second or two - instead.
"""

import threading
from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

from app.core.config import get_settings


@lru_cache
def _slots() -> threading.BoundedSemaphore:
    return threading.BoundedSemaphore(get_settings().simulation_concurrency)


@contextmanager
def simulation_slot() -> Iterator[None]:
    with _slots():
        yield
