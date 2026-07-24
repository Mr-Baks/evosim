from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from enum import Enum
from entity import *
from world import World
from event_bus import *
import math
import random
import heapq
from typing import Optional
from genome import Genome, GeneNames


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
            corpse = Entity().add_component(Eatable(self.corpse_nutrition)).add_component(Render(symbol='D', color=(255, 0, 0)))
            world.place_entity(corpse, entity.x, entity.y)

        with open('log.txt', 'a') as log:
            bio: Biochemistry = entity.get_component(Biochemistry)
            log.write(f'died at {entity.x}, {entity.y} | Hunger: {bio.hunger}, energy: {bio.energy} \n')

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
    path: list[tuple[int, int]] = field(default_factory=list)
    path_retry_count: int = 0
    
    def _find_path(self, world: World, start: tuple[int, int], ignore_entity: Entity = None) -> list[tuple[int, int]]:
        sx, sy = start
        gx, gy = self.x, self.y
        goal = (self.x, self.y)
        
        if start == goal:
            return []
        
        def heuristic(x, y):
            return abs(x - gx) + abs(y - gy)
        
        open_set = [(heuristic(sx, sy), 0, sx, sy)]
        came_from = {}
        g_score = {start: 0}
        closed_set = set()
        
        while open_set:
            _, g, x, y = heapq.heappop(open_set)
            current = (x, y)
            
            if current == goal:
                path = []
                while current in came_from:
                    path.append(current)
                    current = came_from[current]
                return path[::-1]
            
            if current in closed_set:
                continue
            closed_set.add(current)
            
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    if dx == 0 and dy == 0:
                        continue
                    nx, ny = x + dx, y + dy
                    
                    if not (0 <= nx < world.width and 0 <= ny < world.height):
                        continue
                    
                    neighbor = (nx, ny)
                    if neighbor in closed_set:
                        continue
                    
                    entity_at = world.get_entity(nx, ny)
                    if entity_at and entity_at is not ignore_entity and neighbor != goal:
                        continue
                    
                    move_cost = 1.414 if dx != 0 and dy != 0 else 1.0
                    tentative_g = g + move_cost
                    
                    if neighbor not in g_score or tentative_g < g_score[neighbor]:
                        came_from[neighbor] = current
                        g_score[neighbor] = tentative_g
                        f = tentative_g + heuristic(nx, ny)
                        heapq.heappush(open_set, (f, tentative_g, nx, ny))
        
        return []
    
    def execute(self, entity: Entity, world: World):
        if self.x == entity.x and self.y == entity.y:
            self.complete(entity)
            return

        target_entity = world.get_entity(self.x, self.y)
        if target_entity and target_entity is not entity:
            self.complete(entity, status=CommandStatus.FAILED)
            return

        if not self.path:
            self.path = self._find_path(world, (entity.x, entity.y), ignore_entity=entity)
            if not self.path:
                self.complete(entity, CommandStatus.FAILED)
                return

        movable: Movable = entity.get_component(Movable)
        movable.movement_accumulator += movable.speed
        steps = int(movable.movement_accumulator)
        movable.movement_accumulator -= steps

        for _ in range(steps):
            if not self.path: break
            
            next_pos = self.path[0]
            entity_at_next = world.get_entity(*next_pos)

            if entity_at_next and entity_at_next is not entity:
                self.path_retry_count += 1
                if self.path_retry_count > 3:
                    self.complete(entity, status=CommandStatus.FAILED)
                    return
                self.path = []
                return

            if world.make_move(entity, *next_pos):
                world.event_bus.emit(MoveEvent(source=entity))
                self.path.pop(0)
                self.path_retry_count = 0

                if self.x == entity.x and self.y == entity.y:
                    self.complete(entity)
            else:
                self.path = []
                self.path_retry_count = 0

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
        command.execute(entity, world)
        push_command(entity, world, command)

def create_child(parent1: Entity, parent2: Entity, world: World): # TODO GENETICS!!!
    child = Entity()
    
    components = set(parent1.components_dict.keys()) | set(parent2.components_dict.keys())
    for c in components:
        child.add_component(c())
    
    render = child.get_component(Render)
    render.symbol = 'C'

    genome1 = parent1.get_component(Genome)
    genome2 = parent2.get_component(Genome)
    genome = genome1.recombine(genome2)

    child.add_component(genome)

    r = int(genome.genes[GeneNames.COLOR_R].phenotype * 128 + 128)
    g = int(genome.genes[GeneNames.COLOR_G].phenotype * 128 + 128)
    b = int(genome.genes[GeneNames.COLOR_B].phenotype * 128 + 128)

    render.color = (r, g, b)

    movable = child.get_component(Movable)
    movable.speed = int(genome.genes[GeneNames.SPEED].phenotype * 2.5 + 2.5)

    with open('log.txt', 'a') as log:
        log.write(f'Mating at {parent2.x}, {parent2.y}. Parents id: {(parent1.x + parent2.x + 1) * (parent1.y + parent2.y + 1)} \n')

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