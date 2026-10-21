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
from traits import traits_for


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
    target_status: CommandStatus = CommandStatus.PENDING
    emergency: int = 0
    target_state: Optional[str] = None

    @abstractmethod
    def execute(self, entity: Entity, world: World) -> None:
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

        if status == CommandStatus.FAILED:
                    with open('logs/error_log.txt', 'a') as log:
                        log.write(f'Command {type(self)} failed | current state: {state.current if state else 'no state'} \n')
        
        if queue and queue.running == self:
            queue.running = None
            self.status = status
            if state:
                state.current = 'idle'
                state.states.discard(self.target_state) 
        self.target_status = status    

@dataclass
class CommandQueue(Component):
    queue: list[Command] = field(default_factory=list)
    running: Optional[Command] = None

class CommandGroup(Command):
    def __init__(self, subcommands: list[Command], priority: int = 0, status: CommandStatus = CommandStatus.PENDING, emergency: int = 0, target_state: Optional[str] = None):
        super().__init__(priority=priority, status=status, emergency=emergency, target_state=target_state)
        self._queue = CommandQueue(queue=subcommands)
        self.target_state = target_state
        self.has_target_state = bool(target_state)

        for c in subcommands:
            self.emergency = max(self.emergency, c.emergency)
            self.priority = max(self.priority, c.priority)

    def on_interruption(self, entity: Entity):
        for c in self._queue.queue:
            c.complete(entity, status=CommandStatus.CANCELLED)

        if self._queue.running:
            self._queue.running.complete(entity, status=CommandStatus.INTERRUPTED)
            self._queue.running.on_interruption(entity)

        self.complete(entity, status=CommandStatus.INTERRUPTED)

    def execute(self, entity: Entity, world: World):
        if not self._queue.running or self._queue.running.target_status != CommandStatus.RUNNING:
            self._queue.queue = [cmd for cmd in self._queue.queue if cmd.target_status == CommandStatus.PENDING]
            for i, cmd in enumerate(self._queue.queue):
                if cmd.is_ready(entity, world):
                    self._queue.running = self._queue.queue.pop(i)
                    self._queue.running.target_status = CommandStatus.RUNNING
                    if self.has_target_state:
                        cmd.target_state = self.target_state
                    else:
                        self.target_state = cmd.target_state
                    break
            else:
                self.complete(entity)
                return

        self._queue.running.execute(entity, world)
        
def push_command(entity: Entity, world: World, *commands: Command, target_state: Optional[str] = None) -> None:
    if len(commands) > 1:
        command = CommandGroup(list(commands), target_state=target_state)
    else:
        command = commands[0]
        if target_state:
            command.target_state = target_state

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

        self.complete(entity, status=CommandStatus.COMPLETED)
        with open('logs/log.txt', 'a') as log:
            bio: Biochemistry = entity.get_component(Biochemistry)
            log.write(f'died at {entity.x}, {entity.y} | Hunger: {bio.hunger}, energy: {bio.energy} \n')

@dataclass
class SleepCommand(Command):
    ticks_to_sleep: int = 5
    energy_increase: int = 50

    def execute(self, entity: Entity, world: World):
        self.ticks_to_sleep -= 1
        world.event_bus.emit(SleepEvent(source=entity, energy_increase=self.energy_increase))

        if self.ticks_to_sleep <= 0:
            self.complete(entity)

_DIAGONAL = 1.414
_CARDINAL = 1.0
_MAX_EXPANSIONS = 400
_MAX_PATH_RETRIES = 7
_DIRECTIONS = ((-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1),  (1, 0),  (1, 1),)

def octile(x: int, y: int, gx: int, gy: int) -> float:
    """Octile distance - the exact cost of an unobstructed 8-way walk."""
    dx = abs(x - gx)
    dy = abs(y - gy)
    return (dx + dy) + (_DIAGONAL - 2.0) * min(dx, dy)

def _straight_steps(start: tuple[int, int], goal: tuple[int, int]) -> list[tuple[int, int]]:
    """Cells of the greedy 8-way line: start exclusive, goal inclusive."""
    x, y = start
    gx, gy = goal
    steps = []
    while (x, y) != goal:
        x += (gx > x) - (gx < x)
        y += (gy > y) - (gy < y)
        steps.append((x, y))
    return steps

def _line_of_sight(world: World, start: tuple[int, int], goal: tuple[int, int], ignore_entity: Entity = None) -> bool:
    """True if the greedy 8-way line from start to goal is free of entities."""
    x, y = start
    gx, gy = goal
    while (x, y) != goal:
        x += (gx > x) - (gx < x)
        y += (gy > y) - (gy < y)
        if (x, y) == goal:
            break
        occupant = world.get_entity(x, y)
        if occupant is not None and occupant is not ignore_entity:
            return False
    return True

@dataclass
class MoveToTargetCommand(Command):
    x: int = 0
    y: int = 0
    path: list[tuple[int, int]] = field(default_factory=list)
    path_retry_count: int = 0
    previous: Optional[tuple[int, int]] = None

    def _route(self, world: World, entity: Entity) -> list[tuple[int, int]]:
        """Cheapest route to the goal: straight line when clear, else A*."""
        start = (entity.x, entity.y)
        if start == (self.x, self.y):
            return []
        if _line_of_sight(world, start, (self.x, self.y), ignore_entity=entity):
            return _straight_steps(start, (self.x, self.y))
        return self._find_path(world, start, ignore_entity=entity)

    def _find_path(self, world: World, start: tuple[int, int], ignore_entity: Entity = None) -> list[tuple[int, int]]:
        sx, sy = start
        gx, gy = self.x, self.y
        goal = (self.x, self.y)

        if start == goal:
            return []

        counter = 0
        open_set = [(octile(sx, sy, gx, gy), counter, sx, sy)]
        came_from = {}
        g_score = {start: 0.0}
        closed_set = set()
        expansions = 0

        while open_set:
            _, _, x, y = heapq.heappop(open_set)
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

            expansions += 1
            if expansions > _MAX_EXPANSIONS:
                return []

            g = g_score[current]
            for dx, dy in _DIRECTIONS:
                nx, ny = x + dx, y + dy

                if not (0 <= nx < world.width and 0 <= ny < world.height):
                    continue

                neighbor = (nx, ny)
                if neighbor in closed_set:
                    continue

                entity_at = world.get_entity(nx, ny)
                if entity_at and entity_at is not ignore_entity and neighbor != goal:
                    continue

                move_cost = _DIAGONAL if dx != 0 and dy != 0 else _CARDINAL
                tentative_g = g + move_cost

                if neighbor not in g_score or tentative_g < g_score[neighbor]:
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative_g
                    counter += 1
                    heapq.heappush(open_set, (tentative_g + octile(nx, ny, gx, gy), counter, nx, ny))

        return []

    def _step_around(self, entity: Entity, world: World) -> bool:
        """Slip into the free neighbour that keeps the entity closing on its goal."""
        gx, gy = self.x, self.y
        current_dist = octile(entity.x, entity.y, gx, gy)

        best = None
        best_dist = None
        for dx, dy in _DIRECTIONS:
            nx, ny = entity.x + dx, entity.y + dy
            if (nx, ny) == self.previous:
                continue
            if not (0 <= nx < world.width and 0 <= ny < world.height):
                continue
            if world.get_entity(nx, ny) is not None:
                continue

            dist = octile(nx, ny, gx, gy)
            if dist > current_dist:
                continue
            if best_dist is None or dist < best_dist:
                best_dist = dist
                best = (nx, ny)

        if best is None:
            return False

        old = (entity.x, entity.y)
        if not world.make_move(entity, *best):
            return False
        self.previous = old
        world.event_bus.emit(MoveEvent(source=entity))
        return True

    def execute(self, entity: Entity, world: World):
        if self.x == entity.x and self.y == entity.y:
            self.complete(entity)
            return

        movable: Movable = entity.get_component(Movable)
        movable.movement_accumulator += movable.speed
        steps = int(movable.movement_accumulator)
        movable.movement_accumulator -= steps

        for _ in range(steps):
            if self.x == entity.x and self.y == entity.y:
                self.complete(entity)
                return

            if not self.path:
                self.path = self._route(world, entity)
                if not self.path:
                    self.complete(entity, CommandStatus.FAILED)
                    return

            next_pos = self.path[0]
            old = (entity.x, entity.y)

            if world.make_move(entity, *next_pos):
                self.previous = old
                world.event_bus.emit(MoveEvent(source=entity))
                self.path.pop(0)
                self.path_retry_count = 0
                continue

            self.path = []
            self._step_around(entity, world)
            self.path_retry_count += 1
            if self.path_retry_count > _MAX_PATH_RETRIES:
                self.complete(entity, CommandStatus.FAILED)
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
        command.execute(entity, world)
        push_command(entity, world, command)

def create_child(parent1: Entity, parent2: Entity, world: World):
    child = Entity()
    
    components = set(parent1.components_dict.keys()) | set(parent2.components_dict.keys())
    for c in components:
        child.add_component(c())
    if not child.has_component(Lineage):
        child.add_component(Lineage())
    
    render = child.get_component(Render)
    render.symbol = 'C'

    genome1 = parent1.get_component(Genome)
    genome2 = parent2.get_component(Genome)
    genome: Genome = genome1.recombine(genome2)

    child.add_component(genome)

    traits = traits_for(genome)
    render.color = (int(traits.color.r), int(traits.color.g), int(traits.color.b))

    movable = child.get_component(Movable)
    movable.speed = traits.speed.locomotion

    breeadable = child.get_component(Breedable)
    breeadable.fertility = traits.fertility

    with open('logs/log.txt', 'a') as log:
        log.write(f'Mating at {parent2.x}, {parent2.y}\n')

    return child

@dataclass
class MateCommand(Command): 
    partner: Entity = None

    def is_ready(self, entity, world):
        if abs(entity.x - self.partner.x) > 1 or abs(entity.y - self.partner.y) > 1 or self.partner.get_component(Breedable).cooldown > 0 or entity.get_component(Breedable).cooldown > 0:
            return False
        return True

    def execute(self, entity, world):
        genome1: Genome = entity.get_component(Genome)
        genome2: Genome = self.partner.get_component(Genome)
        bio1: Biochemistry = entity.get_component(Biochemistry)
        bio2: Biochemistry = self.partner.get_component(Biochemistry)
        lineage1: Lineage = entity.get_component(Lineage)
        lineage2: Lineage = self.partner.get_component(Lineage)
        
        child = create_child(entity, self.partner, world)
        free_cell = world.get_free_cell_near(entity)

        if free_cell and child:
            x, y = free_cell
            world.place_entity(child, x, y)

            entity.get_component(Breedable).cooldown = world.balance.mating_cooldown_base + traits_for(genome1).wear_resistance.cooldown
            self.partner.get_component(Breedable).cooldown = world.balance.mating_cooldown_base + traits_for(genome2).wear_resistance.cooldown

            bio1.energy -= world.balance.mating_energy_cost
            bio1.hunger -= world.balance.mating_hunger_cost
            bio2.energy -= world.balance.mating_energy_cost
            bio2.hunger -= world.balance.mating_hunger_cost

            lineage: Lineage = child.get_component(Lineage)
            lineage.generation = max(
                lineage1.generation if lineage1 else 0,
                lineage2.generation if lineage2 else 0,
            ) + 1
            lineage.parents_eid = (self.partner.eid, entity.eid)

            self.complete(entity)
        else:
            self.complete(entity, status=CommandStatus.FAILED)
