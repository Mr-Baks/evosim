from abc import ABC
from dataclasses import dataclass, field
from typing import Optional
from entity import Entity, Biochemistry, Eatable
from genome import Genome
from traits import traits_for

@dataclass
class Event(ABC):
    priority: int = 0
    source: Optional[type] = None

class EventBus:
    def __init__(self):
        self.subscribers: dict[type[Event], list[callable]] = {}
        self.event_queue: list[Event] = []

    def subscribe(self, event_type: type[Event], handler: callable) -> None:
        """Registers a handler for an event type"""
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        self.subscribers[event_type].append(handler)

    def unsubscribe(self, event_type: type[Event], handler: callable) -> None:
        """Removes a handler for an event type"""
        if event_type in self.subscribers:
            self.subscribers[event_type].remove(handler)

    def emit(self, event: Event) -> None:
        """Adds an event to the pending queue"""
        self.event_queue.append(event)

    def dispatch(self) -> None:
        """Delivers queued events to their subscribers"""
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
    """Spends energy when an entity moves"""
    bio = event.source.get_component(Biochemistry)
    if bio: bio.energy = max(0, bio.energy - 2)

@dataclass
class SleepEvent(Event):
    energy_increase: int = 30

def on_sleep(event: SleepEvent):
    """Restores energy when an entity sleeps"""
    bio = event.source.get_component(Biochemistry)
    if bio: bio.energy = min(bio.energy + event.energy_increase, 200)

@dataclass
class EatEvent(Event):
    eatable: Eatable = field(default_factory=Eatable)

def on_eat(event: EatEvent):
    """Restores hunger when an entity eats"""
    bio = event.source.get_component(Biochemistry)
    if bio:
        if event.source.has_component(Genome):
            gain = traits_for(event.source.get_component(Genome)).hunger_gain(event.eatable.nutrition, event.eatable.decay, event.eatable.food_type)
        else:
            gain = event.eatable.nutrition * (1 - event.eatable.decay)
        bio.hunger = min(gain + bio.hunger, 200)

@dataclass
class BirthEvent(Event):
    parent1: Entity = None
    parent2: Entity = None

@dataclass
class DeathEvent(Event):
    age: int = None

@dataclass
class DamageEvent(Event):
    target: Entity = None
    damage: float = 1

def on_damage(event: DamageEvent):
    biochemistry: Biochemistry = event.target.get_component(Biochemistry)
    if biochemistry:
        biochemistry.health = max(0, biochemistry.health - event.damage)