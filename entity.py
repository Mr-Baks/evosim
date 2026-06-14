from abc import ABC
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Component(ABC): pass

@dataclass 
class Movable(Component):
    speed: float = 1
    movement_accumulator: float = 0

@dataclass
class Biochemistry(Component):
    energy: int = 100
    hunger: int = 100
    health: int = 100

@dataclass
class Eatable(Component):
    nutrition: int

@dataclass 
class Breedable(Component): pass

@dataclass
class Phenotype(Component):
    color: tuple[int, int, int]

@dataclass 
class Vision(Component):
    radius: int
    visibles: set[Entity] = field(default_factory=list)

class Entity:
    def __init__(self, x: int = 0, y: int = 0):
        self.x = x
        self.y = y
        self.components: set[Component] = set()
        self.components_dict: dict[type[Component], Component] = {}

    def has_component(self, component_type: type[Component]) -> bool:
        """Checks availability of component type"""
        return component_type in self.components_dict

    def get_component(self, component_type: type[Component]) -> Optional[Component]:
        """Returns components if entity has that type, else None"""
        return self.components_dict.get(component_type)

    def add_component(self, component: Component) -> Entity:
        """Adds a component to entity"""
        self.components_dict[type(component)] = component
        self.components.add(type(component))
        return self

    def remove_component(self, component_type: type[Component]) -> Optional[Component]:
        """Removes component from entity"""
        self.components_dict.pop(component_type)
        self.components.discard(component_type)