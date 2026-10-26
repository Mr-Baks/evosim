from typing import Any, Callable, Sequence, TextIO
from world import World
from event_bus import Event, EventBus
import csv
import os


class RunLogger:
    def __init__(self, world: World, event_bus: EventBus, logs_path: str = 'logs/', flush_every: int = 100):
        self.tick = 0
        self.closed = False

        self.world = world
        self.event_bus = event_bus

        self.logs_path = logs_path if logs_path[-1] == '/' else logs_path + '/'
        os.makedirs(self.logs_path, exist_ok=True)
        self.flush_every = flush_every

        self.queries: dict[str, list[Sequence[object]]] = {}
        self.callbacks: dict[str, Callable[[World, int], Sequence[object]]] = {}
        self.log_files: dict[str, TextIO] = {}
        self.writers: dict[str, Any] = {}
        self.call_every: dict[int, list[str]] = {}
        self.subscriptions: list[tuple[type[Event], Callable[[Event], None]]] = []

    def add_query(self, name: str, callback: Callable[[World, int], Sequence[object]], header: Sequence[str] | str, every: int = 50) -> None:
        self.queries[name] = []
        self.callbacks[name] = callback
        self._open_file(name, header)

        if not self.call_every.get(every):
            self.call_every[every] = []
        self.call_every[every].append(name)

    def add_event_query(self, name: str, event_type: type[Event], callback: Callable[[Event, World, int], Sequence[object]], header: Sequence[str] | str) -> None:
        self.queries[name] = []
        self._open_file(name, header)

        def handler(event: Event):
            self.queries[name].append(callback(event, self.world, self.tick))

        self.event_bus.subscribe(event_type, handler)
        self.subscriptions.append((event_type, handler))

    def _open_file(self, name: str, header: Sequence[str] | str) -> None:
        file = open(self.logs_path + name + '.csv', 'w', newline='')
        writer = csv.writer(file)
        writer.writerow(header.split(',') if isinstance(header, str) else header)

        self.log_files[name] = file
        self.writers[name] = writer

    def on_tick(self, tick: int) -> None:
        self.tick = tick

        for period, names in self.call_every.items():
            if self.tick % period == 0:
                for name in names:
                    self.queries[name].append(self.callbacks[name](self.world, self.tick))

        if self.tick % self.flush_every == 0:
            self.flush()

    def flush(self) -> None:
        for name, rows in self.queries.items():
            for row in rows:
                self.writers[name].writerow(row)

            self.log_files[name].flush()
            rows.clear()

    def close(self) -> None:
        if self.closed:
            return

        self.closed = True
        try:
            self.flush()
        finally:
            for event_type, handler in self.subscriptions:
                self.event_bus.unsubscribe(event_type, handler)

            for file in self.log_files.values():
                file.close()
