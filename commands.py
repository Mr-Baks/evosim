from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from enum import Enum
from entity import *
from world import World
from event_bus import *
import math
import random
from typing import Optional


class CommandStatus(Enum):
    PENDING = 0
    RUNNING = 1
    COMPLETED = 2
    FAILED = 3
    CANCELLED = 4
    INTERRUPTED = 5

@dataclass
class Command(ABC):
    priority: int = 0
    status: CommandStatus = CommandStatus.PENDING
    emergency: int = 0
    target_state: Optional[str] = None

    @abstractmethod
    def execute(self, entity: Entity, world: World) -> CommandStatus:
        """Execute command's step"""
        pass

    def is_ready(self, entity: Entity, world: World) -> bool:
        """Returns ready-state of command"""
        return True

    def on_interruption(self, entity: Entity) -> None:
        """Interruption handler"""
        pass

    def complete(self, entity: Entity, status=CommandStatus.COMPLETED) -> None:
        queue = entity.get_component(CommandQueue)
        state = entity.get_component(State)
        if queue and queue.running == self:
            queue.running = None
            self.status = status
            if state:
                state.current = 'idle'
                state.states.discard(self.target_state)

@dataclass
class CommandQueue(Component):
    queue: list[Command] = field(default_factory=list)
    running: Optional[Command] = None

def push_command(entity: Entity, world: World, command: Command) -> None:
    queue = entity.get_component(CommandQueue)
    state = entity.get_component(State)
    if not queue or queue.running is command: return

    if state and command.target_state:
        state.states.add(command.target_state)

    running_cmd = queue.running
    if running_cmd and command.emergency > running_cmd.emergency and command.is_ready(entity, world):
        running_cmd.complete(entity, status=CommandStatus.INTERRUPTED)
        running_cmd.on_interruption(entity)
        queue.running = command
        command.status = CommandStatus.RUNNING
        if command.target_state and state: 
            state.current = command.target_state
        return

    for i, cmd in enumerate(queue.queue):
        if (command.emergency > cmd.emergency) or (command.emergency == cmd.emergency and command.priority > cmd.priority):
            queue.queue.insert(i, command)
            break
    else:
        queue.queue.append(command)

@dataclass
class EatCommand(Command):
    target_x: int = 0
    target_y: int = 0

    def is_ready(self, entity: Entity, world: World):
        return abs(self.target_x - entity.x) < 2 and abs(self.target_y - entity.y) < 2
    
    def execute(self, entity: Entity, world: World):
        food = world.get_entity(self.target_x, self.target_y)
        if not food: 
            self.complete(entity, status=CommandStatus.FAILED)
            return

        eatable = food.get_component(Eatable)
        if eatable:
            world.remove_entity(food)
            world.event_bus.emit(EatEvent(source=entity, nutrition=eatable.nutrition))
            self.complete(entity)
        else:
            self.complete(entity, status=CommandStatus.FAILED)

@dataclass
class DeathCommand(Command):
    corpse_nutrition: int = 0

    def execute(self, entity: Entity, world: World):
        world.remove_entity(entity)
        if self.corpse_nutrition != 0:
            corpse = Entity().add_component(Eatable(self.corpse_nutrition))
            world.place_entity(corpse, entity.x, entity.y)

@dataclass
class SleepCommand(Command):
    ticks_to_sleep: int = 5
    energy_increase: int = 15

    def execute(self, entity: Entity, world: World):
        self.ticks_to_sleep -= 1
        world.event_bus.emit(SleepEvent(source=entity, energy_increase=self.energy_increase))

        if self.ticks_to_sleep == 0:
            self.complete(entity)

@dataclass
class MoveToTargetCommand(Command):
    x: int = 0
    y: int = 0

    def execute(self, entity: Entity, world: World):
        possibles = world.get_free_cells_near(entity)

        if not possibles:
            self.complete(entity, status=CommandStatus.FAILED)
            return
        
        if (self.x, self.y) in world.get_cells_near(entity):
            if world.get_entity(self.x, self.y):
                self.complete(entity, status=CommandStatus.FAILED)
                return
        
        best_move = possibles[0]
        min_dist = float('inf')
        for (px, py) in possibles:
            dist = abs(px - self.x) + abs(py - self.y)
            if dist < min_dist:
                min_dist = dist
                best_move = (px, py)

        if world.make_move(entity, *best_move):
            world.event_bus.emit(MoveEvent(source=entity))
        else:
            self.complete(entity, status=CommandStatus.FAILED)
            return

        if self.x == entity.x and self.y == entity.y:
            self.complete(entity)

@dataclass
class WanderCommand(Command):
    radius: int = 4
    
    def execute(self, entity: Entity, world: World):
        angle = random.uniform(0, 2 * math.pi)
        dx = round(math.cos(angle) * self.radius)
        dy = round(math.sin(angle) * self.radius)

        tx, ty = entity.x + dx, entity.y + dy
        if not (0 <= tx < world.width and 0 <= ty < world.height):
            dx, dy = -dx, -dy
            tx, ty = entity.x + dx, entity.y + dy
            if not (0 <= tx < world.width and 0 <= ty < world.height):
                tx = max(0, min(world.width - 1, entity.x + dx))
                ty = max(0, min(world.height - 1, entity.y + dy))

        self.complete(entity)
        command = MoveToTargetCommand(x=tx, y=ty, priority=self.priority, emergency=self.emergency, target_state=self.target_state)
        push_command(entity, world, command)
        command.execute(entity, world)

def create_child(parent1: Entity, parent2: Entity, world: World): # TODO GENETICS!!!
    child = Entity()
    
    components = set(parent1.components_dict.keys()) | set(parent2.components_dict.keys())
    for c in components:
        child.add_component(c())
    
    render = child.get_component(Render)
    render.symbol = 'C'

    r1, g1, b1 = parent1.get_component(Render).color
    r2, g2, b2 = parent2.get_component(Render).color
    r = max(0, min(255, int((r1 + r2) / 2 + random.randint(-10, 10))))
    g = max(0, min(255, int((g1 + g2) / 2 + random.randint(-10, 10))))
    b = max(0, min(255, int((b1 + b2) / 2 + random.randint(-10, 10))))

    render.color = (r, g, b)

    return child

@dataclass
class MateCommand(Command): 
    partner: Entity = None

    def is_ready(self, entity, world):
        if abs(entity.x - self.partner.x) + abs(entity.y - self.partner.y) > 1 or self.partner.get_component(Breedable).cooldown > 0:
            return False
        return True

    def execute(self, entity, world):
        child = create_child(entity, self.partner, world)
        free_cells = world.get_free_cells_near(entity)
        if free_cells and child:
            x, y = free_cells[0]
            world.place_entity(child, x, y)
        entity.get_component(Breedable).cooldown = 40
        self.partner.get_component(Breedable).cooldown = 40
        self.complete(entity)