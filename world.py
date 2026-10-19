from typing import Optional
from entity import *
from event_bus import EventBus
import random


class QueryIndex:
    def __init__(self):
        self.entities = []
        self.component_index: dict[type[Component], list[Entity]] = {}
        self.systems_cache: dict[frozenset[type[Component]], list[Entity]] = {}
        self.component_index_dirty = True
        self.systems_cache_dirty = True

        self.locked = False
        self.pending_addition: list[Entity] = []
        self.pending_removal: list[Entity] = []
    
    def add_entity(self, entity: Entity) -> None:
        if self.locked:
            self.pending_addition.append(entity)
            return
        
        index = self.component_index
        self.entities.append(entity)
        entity.locked_direct_operation = True

        for c in entity.components:
            if c not in index: index[c] = []
            index[c].append(entity)

        for key, cache_set in self.systems_cache.items():
            if key.issubset(set(entity.components)):
                cache_set.append(entity)

        self.component_index_dirty = True
        self.systems_cache_dirty = True

    def remove_entity(self, entity: Entity) -> None:
        if self.locked:
            if entity in self.pending_addition:
                self.pending_addition.remove(entity)
            else:
                self.pending_removal.append(entity)
            return

        if entity in self.entities:
            self.entities.remove(entity)
        entity.locked_direct_operation = False
        for c in entity.components:
            self.component_index[c].remove(entity)
        
        for key in self.systems_cache:
            if entity in self.systems_cache[key]:
                self.systems_cache[key].remove(entity)

    def sort_cache(self):
        if self.component_index_dirty:
            for lst in self.component_index.values():
                lst.sort(key=lambda e: e.eid)
            self.component_index_dirty = False

        if self.systems_cache_dirty:
            for lst in self.systems_cache.values():
                lst.sort(key=lambda e: e.eid)
            self.systems_cache_dirty = False

    def flush_pending(self):
        if self.locked: return

        for e in self.pending_removal:
            self.remove_entity(e)

        for e in self.pending_addition:
            self.add_entity(e)

        self.pending_addition.clear()
        self.pending_removal.clear()
        
    def register_system(self, components: frozenset[type[Component]]) -> None:
        self.systems_cache[components] = list(self.get_with(*components))
        self.systems_cache_dirty = True

    def get_with(self, *component_types: type[Component]) -> list[Entity]:
        if not component_types:
            return list(self.entities)

        lists = []
        for t in component_types:
            if t not in self.component_index:
                return []
            lists.append(self.component_index[t])

        lists.sort(key=len)

        others = [set(lst) for lst in lists[1:]]
        return [e for e in lists[0] if all(e in other for other in others)]
        
class World:
    def __init__(self, width: int = 60, height: int = 15):
        self.cells: list[list[Optional[Entity]]] = [[None for _ in range(width)] for _ in range(height)]
        self.index = QueryIndex()
        self.event_bus = EventBus()
        self.pending_component_addition: dict[Entity, list[Component]] = {}
        self.pending_component_removal: dict[Entity, list[Component]] = {}
        self.width = width
        self.height = height
        self._offset_cache = {}

        self._offset_cache[1] = []
        for dx in range(-1, 2):
            for dy in range(-1, 2):
                self._offset_cache[1].append((dx, dy))
        self._offset_cache[1].remove((0, 0))

        self._eid_counter = 0
    
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
        entity.eid = self._eid_counter
        self._eid_counter += 1

        return True

    def remove_entity(self, entity: Entity) -> Optional[Entity]:
        if self.get_entity(entity.x, entity.y) is entity:
            self.index.remove_entity(entity)
            self.cells[entity.y][entity.x] = None
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

    def get_neighbours(self, entity: Entity, radius=1) -> list[Entity]:
        neighbours = []
        x, y = entity.x, entity.y

        for dx, dy in self._get_offsets(radius):
            nx, ny = x + dx, y + dy
            if 0 <= nx < self.width and 0 <= ny < self.height:
                entity = self.cells[ny][nx]
                if entity:
                    neighbours.append(entity)

        return sorted(neighbours, key=lambda e: e.eid)

    def get_free_cells_near(self, entity: Entity, radius: int = 1) -> list[tuple[int, int]]:
        free_cells = []
        offsets = self._get_offsets(radius=radius)

        for (dx, dy) in offsets:
            nx, ny = entity.x + dx, entity.y + dy
            if self._check_cell(nx, ny):
                free_cells.append((nx, ny))

        return free_cells

    def get_free_cell_near(self, entity: Entity, radius: int = 1) -> tuple[int, int] | None:
        free_cells = self.get_free_cells_near(entity, radius)
        return random.choice(free_cells) if free_cells else None
    
    def get_cells_near(self, entity: Entity, radius: int = 1) -> list[tuple[int, int]]:
        cells = []
        offsets = self._get_offsets(radius=radius)

        for (dx, dy) in offsets:
            cells.append((entity.x + dx, entity.y + dy))

        return cells

    def add_component(self, entity, component):
        if self.index.locked:
            self.pending_component_addition.setdefault(entity, []).append(component)
            return

        ctype = type(component)
        if entity.has_component(ctype):
            return

        entity.add_component(component, direct=False)
        self.index.component_index.setdefault(ctype, []).append(entity)
        self.index.component_index_dirty = True

        if entity in self.index.entities:
            for key, cache in self.index.systems_cache.items():
                if key.issubset(entity.components):
                    cache.append(entity)
                    self.index.systems_cache_dirty = True

    def remove_component(self, entity, component_type):
        if self.index.locked:
            self.pending_component_removal.setdefault(entity, []).append(component_type)
            return

        if not entity.has_component(component_type):
            return

        removed = entity.remove_component(component_type, direct=False)
        component_list = self.index.component_index.get(component_type)
        if component_list is not None and entity in component_list:
            component_list.remove(entity)

        for key, cache in self.index.systems_cache.items():
            if not key.issubset(entity.components):
                if entity in cache:
                    cache.remove(entity)

        return removed

    def flush_pending(self):
        if self.index.locked: return
        self.index.flush_pending()

        for entity, comps in self.pending_component_removal.items():
            for comp in comps:
                self.remove_component(entity, comp)

        for entity, comps in self.pending_component_addition.items():
            for comp in comps:
                self.add_component(entity, comp)

        self.pending_component_addition.clear()
        self.pending_component_removal.clear()

