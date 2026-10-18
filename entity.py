from abc import ABC
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Component(ABC): pass

@dataclass
class State(Component):
    current: str = 'idle'
    states: set = field(default_factory=set)

@dataclass
class Render(Component):
    symbol: str = '?'
    color: tuple[int, int, int] = (255, 255, 255)
    is_visible: bool = True
    
@dataclass 
class Movable(Component):
    speed: float = 1
    movement_accumulator: float = 0

@dataclass
class Biochemistry(Component):
    energy: float = 100
    hunger: float = 100
    health: float = 100
    max_health: float = 100
    vitality: float = 1
    age: float = 0

@dataclass
class Eatable(Component):
    nutrition: int

@dataclass
class Breedable(Component):
    fertility: float = 1
    cooldown: int = 30

@dataclass 
class Vision(Component):
    radius: int = 4
    visibles: list[Entity] = field(default_factory=list)

@dataclass 
class Plant(Component):
    energy: int = 0
    energy_increase: int = 2
    fructify_threshold: int = 80
    fruit_nutrition: int = 25

class Entity:
    def __init__(self, x: int = 0, y: int = 0):
        self.x = x
        self.y = y
        self.eid = None
        self.components: set[Component] = set()
        self.components_dict: dict[type[Component], Component] = {}
        self.locked_direct_operation = False

    def has_component(self, component_type: type[Component]) -> bool:
        """Checks availability of component type"""
        return component_type in self.components_dict

    def get_component(self, component_type: type[Component]) -> Optional[Component]:
        """Returns components if entity has that type, else None"""
        return self.components_dict.get(component_type)

    def add_component(self, component: Component, direct: bool = True) -> Entity:
        """Adds a component to entity"""
        if self.locked_direct_operation and direct:
            raise RuntimeError("Operation add_component was called directly passing World's proxy after addition to QueryIndex. Please use World.add_component() instead this")
        
        self.components_dict[type(component)] = component
        self.components.add(type(component))
        return self

    def remove_component(self, component_type: type[Component], direct: bool = True) -> Optional[Component]:
        """Removes a component from entity"""
        if self.locked_direct_operation and direct:
            raise RuntimeError("Operation remove_component was called directly passing World's proxy after addition to QueryIndex. Please use World.remove_component() instead this")
                
        self.components.discard(component_type)
        component = self.components_dict.pop(component_type, None)

        return component
