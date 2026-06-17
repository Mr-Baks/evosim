from typing import Optional
from entity import *
from event_bus import EventBus


class QueryIndex:
    def __init__(self):
        self.entities = set()
        self.component_index: dict[type[Component], set[Entity]] = {}
        self.systems_cache: dict[frozenset[type[Component]], set[Entity]] = {}

        self.locked = False
        self.pending_addition: list[Entity] = []
        self.pending_removal: list[Entity] = []
    
    def add_entity(self, entity: Entity) -> None:
        if self.locked:
            self.pending_addition.append(entity)
            return
        
        index = self.component_index
        self.entities.add(entity)

        for c in entity.components:
            if c not in index: index[c] = set()
            index[c].add(entity)

        for key, cache_set in self.systems_cache.items():
            if key.issubset(set(entity.components)):
                cache_set.add(entity)

    def remove_entity(self, entity: Entity) -> None:
        if self.locked:
            self.pending_removal.append(entity)
            return
        
        self.entities.discard(entity)
        for c in entity.components:
            self.component_index[c].discard(entity)
        
        for key in self.systems_cache:
            self.systems_cache[key].discard(entity)

    def flush_pending(self):
        if self.locked: return

        for e in self.pending_removal:
            if e in self.pending_addition:
                self.pending_addition.remove(e)
            self.remove_entity(e)

        for e in self.pending_addition:
            self.add_entity(e)
        
    def register_system(self, components: frozenset[type[Component]]) -> None:
        self.systems_cache[components] = self.get_with(*components)

    def get_with(self, *component_types: type[Component]) -> set[Entity]:
        if not component_types:
            return self.entities

        sets = []
        for t in component_types:
            if t not in self.component_index:
                return set()
            sets.append(self.component_index[t])

        sets.sort(key=len)

        result = sets[0].copy()
        for s in sets[1:]:
            result &= s

        return result
        
class World:
    def __init__(self, width: int = 60, height: int = 15):
        self.cells: list[list[Optional[Entity]]] = [[None for _ in range(width)] for _ in range(height)]
        self.index = QueryIndex()
        self.event_bus = EventBus()
        self.width = width
        self.height = height
        self._offset_cache = {}

        self._offset_cache[1] = []
        for dx in range(-1, 2):
            for dy in range(-1, 2):
                self._offset_cache[1].append((dx, dy))
        self._offset_cache[1].remove((0, 0))
    
    def _check_cell(self, x: int, y: int) -> bool:
        if x < 0 or x >= self.width or y < 0 or y >= self.height: return False
        if self.cells[y][x]: return False
        return True

    def make_move(self, entity: Entity, x: int, y: int) -> bool:
        if not entity.has_component(Movable): return False
        if not self._check_cell(x, y): return False

        ex, ey = entity.x, entity.y
        if self.cells[ey][ex] is not entity: return False
        entity.x, entity.y = x, y

        self.cells[y][x] = entity
        self.cells[ey][ex] = None

        return True
    
    def get_entity(self, x: int, y: int) -> Optional[Entity]:
        if 0 <= x < self.width and 0 <= y < self.height:
            return self.cells[y][x]

    def place_entity(self, entity: Entity, x: int, y: int) -> bool:
        if not self._check_cell(x, y): return False
        
        self.cells[y][x] = entity
        entity.x, entity.y = x, y
        self.index.add_entity(entity)

        return True

    def remove_entity(self, entity: Entity) -> Optional[Entity]:
        if entity in self.index.entities:
            self.index.remove_entity(entity)
            ex, ey = entity.x, entity.y
            self.cells[ey][ex] = None
            return entity

    def _get_offsets(self, radius: int) -> list[tuple[int, int]]:
        if radius in self._offset_cache:
            return self._offset_cache[radius]
        offsets = []
        r_sq = radius ** 2
        for dx in range(-radius, radius+1):
            for dy in range(-radius, radius+1):
                if dx ** 2 + dy ** 2 <= r_sq:
                    offsets.append((dx, dy))
        offsets.remove((0, 0))
        self._offset_cache[radius] = offsets
        return offsets

    def get_neighbours(self, entity: Entity, radius=1) -> set[Entity]:
        neighbours = set()
        x, y = entity.x, entity.y

        for dx, dy in self._get_offsets(radius):
            entity = self.get_entity(x + dx, y + dy)
            if entity:
                neighbours.add(entity)
        return neighbours

    def get_free_cells_near(self, entity: Entity, radius: int = 1) -> list[tuple[int, int]]:
        free_cells = []
        offsets = self._get_offsets(radius=radius)

        for (dx, dy) in offsets:
            nx, ny = entity.x + dx, entity.y + dy
            if self.get_entity(nx, ny) is None:
                free_cells.append((nx, ny))

        return free_cells
    
    def get_cells_near(self, entity: Entity, radius: int = 1) -> list[tuple[int, int]]:
        cells = []
        offsets = self._get_offsets(radius=radius)

        for (dx, dy) in offsets:
            cells.append((entity.x + dx, entity.y + dy))

        return cells
