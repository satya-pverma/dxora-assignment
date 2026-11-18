"""Thread-safe rolling limits for a single application process."""

from collections import OrderedDict, deque
from math import ceil
from threading import Lock
from time import monotonic
from typing import Callable


class AnalysisRateLimitError(Exception):
    def __init__(self, retry_after: int):
        self.retry_after = retry_after


class AnalysisRateLimiter:
    def __init__(self, clock: Callable[[], float] = monotonic, max_clients: int = 10_000):
        self.clock = clock
        self.max_clients = max_clients
        self._clients: OrderedDict[str, deque[float]] = OrderedDict()
        self._lock = Lock()

    def consume(self, client: str) -> None:
        with self._lock:
            now = self.clock()
            cutoff = now - 60
            # Ordered by most recent admitted request; inactive clients can be reclaimed.
            while self._clients:
                oldest = next(iter(self._clients))
                if self._clients[oldest][-1] > cutoff:
                    break
                self._clients.popitem(last=False)
            timestamps = self._clients.get(client)
            if timestamps is None:
                if len(self._clients) >= self.max_clients:
                    # Do not evict active clients, which would reset their limits.
                    raise AnalysisRateLimitError(60)
                timestamps = deque()
                self._clients[client] = timestamps
            while timestamps and timestamps[0] <= cutoff:
                timestamps.popleft()
            if len(timestamps) >= 2:
                raise AnalysisRateLimitError(max(1, ceil(timestamps[0] + 60 - now)))
            timestamps.append(now)
            self._clients.move_to_end(client)

    def clear(self) -> None:
        with self._lock:
            self._clients.clear()
