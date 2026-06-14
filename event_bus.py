from abc import ABC
from dataclasses import dataclass
from typing import Optional
from entity import *

@dataclass
class Event(ABC):
    priority: int = 0
    source: Optional[type] = None

class EventBus:
    def __init__(self):
        self.subscribers: dict[type[Event], list[callable]] = {}
        self.event_queue: list[Event] = []

    def subscribe(self, event_type: type[Event], handler: callable) -> None:
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        self.subscribers[event_type].append(handler)

    def unsubscribe(self, event_type: type[Event], handler: callable) -> None:
        if event_type in self.subscribers:
            self.subscribers[event_type].remove(handler)

    def emit(self, event: Event) -> None:
        self.event_queue.append(event)

    def dispatch(self) -> None:
        self.event_queue.sort(key=lambda e: -e.priority)
        for event in self.event_queue:
            event_type = type(event)
            if event_type in self.subscribers:
                for handler in self.subscribers[event_type]:
                    handler(event)
        self.event_queue.clear()

@dataclass
class MoveEvent(Event):
    pass

def on_move(event: MoveEvent):
    bio = event.source.get_component(Biochemistry)
    if bio: bio.energy = max(0, bio.energy - 2)

@dataclass
class SleepEvent(Event):
    energy_increase: int = 15

def on_sleep(event: SleepEvent):
    bio = event.source.get_component(Biochemistry)
    if bio: bio.energy = max(bio.energy + event.energy_increase, 100)

@dataclass
class EatEvent(Event):
    nutrition: int = 20

def on_eat(event: EatEvent):
    bio = event.source.get_component(Biochemistry)
    if bio:
        bio.hunger = max(event.nutrition + bio.hunger, 100)