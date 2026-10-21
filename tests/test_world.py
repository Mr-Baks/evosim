import pytest
from entity import Entity, Biochemistry, Movable, Render, Eatable, Plant, Vision, Breedable, State, Component
from world import World, QueryIndex


class TestQueryIndex:
    def test_init(self):
        index = QueryIndex()
        assert index.entities == []
        assert index.component_index == {}
        assert index.systems_cache == {}
        assert index.locked is False
        assert index.pending_addition == []
        assert index.pending_removal == []

    def test_add_entity(self):
        index = QueryIndex()
        e = Entity().add_component(Biochemistry()).add_component(Movable())
        index.add_entity(e)
        assert e in index.entities
        assert Biochemistry in index.component_index
        assert Movable in index.component_index
        assert e in index.component_index[Biochemistry]
        assert e in index.component_index[Movable]

    def test_add_entity_locked(self):
        index = QueryIndex()
        index.locked = True
        e = Entity().add_component(Biochemistry())
        index.add_entity(e)
        assert e in index.pending_addition
        assert e not in index.entities

    def test_remove_entity(self):
        index = QueryIndex()
        e = Entity().add_component(Biochemistry()).add_component(Movable())
        index.add_entity(e)
        index.remove_entity(e)
        assert e not in index.entities
        assert e not in index.component_index[Biochemistry]
        assert e not in index.component_index[Movable]

    def test_remove_entity_locked(self):
        index = QueryIndex()
        e = Entity().add_component(Biochemistry())

        # Adding and then removing while locked cancels the pending addition:
        # the entity never enters the index nor any pending list
        index.locked = True
        index.add_entity(e)
        index.remove_entity(e)
        assert e not in index.entities
        assert e not in index.pending_addition
        assert e not in index.pending_removal

        # Removing an already-indexed entity while locked defers removal
        index.locked = False
        index.add_entity(e)
        index.locked = True
        index.remove_entity(e)
        assert e in index.pending_removal

    def test_flush_pending(self):
        index = QueryIndex()
        index.locked = True
        e1 = Entity().add_component(Biochemistry())
        e2 = Entity().add_component(Movable())
        index.add_entity(e1)
        index.add_entity(e2)
        
        index.locked = False
        index.flush_pending()
        
        assert e1 in index.entities
        assert Biochemistry in index.component_index
        assert e1 in index.component_index[Biochemistry]
        assert e2 in index.entities
        assert Movable in index.component_index
        assert e2 in index.component_index[Movable]

    def test_flush_pending_while_locked(self):
        index = QueryIndex()
        index.locked = True
        e1 = Entity().add_component(Biochemistry())
        index.add_entity(e1)
        index.flush_pending()
        assert e1 not in index.entities

    def test_register_system(self):
        index = QueryIndex()
        e1 = Entity().add_component(Biochemistry()).add_component(Movable())
        e2 = Entity().add_component(Biochemistry())
        e3 = Entity().add_component(Movable())
        index.add_entity(e1)
        index.add_entity(e2)
        index.add_entity(e3)
        
        components = frozenset([Biochemistry, Movable])
        index.register_system(components)
        
        assert components in index.systems_cache
        assert index.systems_cache[components] == [e1]

    def test_get_with_single_component(self):
        index = QueryIndex()
        e1 = Entity().add_component(Biochemistry())
        e2 = Entity().add_component(Biochemistry())
        e3 = Entity().add_component(Movable())
        index.add_entity(e1)
        index.add_entity(e2)
        index.add_entity(e3)
        
        result = index.get_with(Biochemistry)
        assert result == [e1, e2]

    def test_get_with_multiple_components(self):
        index = QueryIndex()
        e1 = Entity().add_component(Biochemistry()).add_component(Movable())
        e2 = Entity().add_component(Biochemistry())
        e3 = Entity().add_component(Movable())
        e4 = Entity().add_component(Biochemistry()).add_component(Movable()).add_component(Render())
        index.add_entity(e1)
        index.add_entity(e2)
        index.add_entity(e3)
        index.add_entity(e4)
        
        result = index.get_with(Biochemistry, Movable)
        assert result == [e1, e4]

    def test_get_with_no_components(self):
        index = QueryIndex()
        e1 = Entity().add_component(Biochemistry())
        e2 = Entity().add_component(Movable())
        index.add_entity(e1)
        index.add_entity(e2)
        
        result = index.get_with()
        assert result == [e1, e2]

    def test_get_with_missing_component(self):
        index = QueryIndex()
        e1 = Entity().add_component(Biochemistry())
        index.add_entity(e1)
        
        result = index.get_with(Plant)
        assert result == []


class TestWorld:
    def test_init(self):
        world = World(width=20, height=15)
        assert world.width == 20
        assert world.height == 15
        assert len(world.cells) == 15
        assert len(world.cells[0]) == 20
        assert world.event_bus is not None
        assert world.index is not None

    def test_check_cell_valid(self):
        world = World(10, 10)
        assert world._check_cell(5, 5) is True

    def test_check_cell_out_of_bounds(self):
        world = World(10, 10)
        assert world._check_cell(-1, 0) is False
        assert world._check_cell(10, 0) is False
        assert world._check_cell(0, -1) is False
        assert world._check_cell(0, 10) is False

    def test_check_cell_occupied(self):
        world = World(10, 10)
        e = Entity()
        world.place_entity(e, 5, 5)
        assert world._check_cell(5, 5) is False

    def test_place_entity(self):
        world = World(10, 10)
        e = Entity().add_component(Biochemistry())
        result = world.place_entity(e, 3, 4)
        assert result is True
        assert e.x == 3
        assert e.y == 4
        assert world.cells[4][3] is e
        assert e in world.index.entities

    def test_place_entity_invalid_cell(self):
        world = World(10, 10)
        e1 = Entity().add_component(Biochemistry())
        world.place_entity(e1, 5, 5)
        e2 = Entity().add_component(Biochemistry())
        result = world.place_entity(e2, 5, 5)
        assert result is False

    def test_place_entity_out_of_bounds(self):
        world = World(10, 10)
        e = Entity().add_component(Biochemistry())
        result = world.place_entity(e, 15, 15)
        assert result is False

    def test_get_entity(self):
        world = World(10, 10)
        e = Entity().add_component(Biochemistry())
        world.place_entity(e, 2, 3)
        result = world.get_entity(2, 3)
        assert result is e

    def test_get_entity_empty(self):
        world = World(10, 10)
        result = world.get_entity(5, 5)
        assert result is None

    def test_get_entity_out_of_bounds(self):
        world = World(10, 10)
        result = world.get_entity(-1, 0)
        assert result is None
        result = world.get_entity(10, 10)
        assert result is None

    def test_remove_entity(self):
        world = World(10, 10)
        e = Entity().add_component(Biochemistry()).add_component(Movable())
        world.place_entity(e, 5, 5)
        removed = world.remove_entity(e)
        assert removed is e
        assert world.cells[5][5] is None
        assert e not in world.index.entities

    def test_remove_entity_not_in_index(self):
        world = World(10, 10)
        e = Entity().add_component(Biochemistry())
        removed = world.remove_entity(e)
        assert removed is None

    def test_make_move(self):
        world = World(10, 10)
        e = Entity().add_component(Movable())
        world.place_entity(e, 5, 5)
        result = world.make_move(e, 6, 5)
        assert result is True
        assert e.x == 6
        assert e.y == 5
        assert world.cells[5][6] is e
        assert world.cells[5][5] is None

    def test_make_move_not_movable(self):
        world = World(10, 10)
        e = Entity().add_component(Biochemistry())
        world.place_entity(e, 5, 5)
        result = world.make_move(e, 6, 5)
        assert result is False

    def test_make_move_invalid_cell(self):
        world = World(10, 10)
        e = Entity().add_component(Movable())
        world.place_entity(e, 5, 5)
        result = world.make_move(e, 15, 5)
        assert result is False

    def test_make_move_occupied_cell(self):
        world = World(10, 10)
        e1 = Entity().add_component(Movable())
        e2 = Entity().add_component(Movable())
        world.place_entity(e1, 5, 5)
        world.place_entity(e2, 6, 5)
        result = world.make_move(e1, 6, 5)
        assert result is False

    def test_make_move_wrong_entity_in_cell(self):
        world = World(10, 10)
        e1 = Entity().add_component(Movable())
        e2 = Entity().add_component(Movable())
        world.place_entity(e1, 5, 5)
        world.cells[5][5] = e2
        result = world.make_move(e1, 6, 5)
        assert result is False

    def test_get_offsets_cache(self):
        world = World()
        offsets1 = world._get_offsets(1)
        offsets2 = world._get_offsets(1)
        assert offsets1 is offsets2

    def test_get_offsets_radius_1(self):
        world = World()
        offsets = world._get_offsets(1)
        expected = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
        assert len(offsets) == 8
        assert set(offsets) == set(expected)

    def test_get_offsets_radius_2(self):
        world = World()
        offsets = world._get_offsets(2)
        assert len(offsets) == 12
        for dx, dy in offsets:
            assert dx**2 + dy**2 <= 4
            assert not (dx == 0 and dy == 0)

    def test_get_neighbours(self):
        world = World(10, 10)
        center = Entity().add_component(Biochemistry())
        world.place_entity(center, 5, 5)
        
        e1 = Entity().add_component(Biochemistry())
        e2 = Entity().add_component(Biochemistry())
        world.place_entity(e1, 4, 5)
        world.place_entity(e2, 5, 6)
        
        neighbours = world.get_neighbours(center, radius=1)
        assert e1 in neighbours
        assert e2 in neighbours
        assert center not in neighbours

    def test_get_neighbours_radius_2(self):
        world = World(10, 10)
        center = Entity().add_component(Biochemistry())
        world.place_entity(center, 5, 5)
        
        e1 = Entity().add_component(Biochemistry())
        world.place_entity(e1, 3, 5)
        
        neighbours = world.get_neighbours(center, radius=2)
        assert e1 in neighbours

    def test_count_near_respects_condition(self):
        world = World(10, 10)
        center = Entity().add_component(Movable())
        mover = Entity().add_component(Movable())
        plant = Entity().add_component(Plant())
        world.place_entity(center, 5, 5)
        world.place_entity(mover, 5, 6)
        world.place_entity(plant, 6, 5)

        assert world.count_near(5, 5, lambda e: e.has_component(Movable), radius=2) == 1
        assert world.count_near(5, 5, lambda e: e.has_component(Plant), radius=2) == 1
        assert world.count_near(5, 5, lambda e: True, radius=2) == 2

    def test_count_near_excludes_center_and_uses_euclidean_radius(self):
        world = World(10, 10)
        center = Entity()
        inside = Entity()
        diagonal = Entity()
        outside = Entity()
        world.place_entity(center, 5, 5)
        world.place_entity(inside, 7, 5)
        world.place_entity(diagonal, 7, 6)
        world.place_entity(outside, 8, 5)

        assert world.count_near(5, 5, lambda e: True, radius=2) == 1
        assert world.count_near(5, 5, lambda e: True, radius=3) == 3

    def test_get_free_cells_near(self):
        world = World(10, 10)
        center = Entity().add_component(Biochemistry())
        world.place_entity(center, 5, 5)
        
        e1 = Entity().add_component(Biochemistry())
        world.place_entity(e1, 4, 5)
        
        free = world.get_free_cells_near(center, radius=1)
        assert (4, 5) not in free
        assert (6, 5) in free
        assert (5, 4) in free
        assert (5, 6) in free

    def test_get_cells_near(self):
        world = World(10, 10)
        center = Entity().add_component(Biochemistry())
        world.place_entity(center, 5, 5)
        
        cells = world.get_cells_near(center, radius=1)
        assert len(cells) == 8
        assert (4, 4) in cells
        assert (5, 5) not in cells


class TestWorldComponentProxy:
    """World.add_component / remove_component must keep QueryIndex in sync.

    Structural changes are normally forbidden once an entity is indexed
    (Entity.locked_direct_operation); World is the sanctioned entry point and
    it also updates component_index and every affected systems_cache. While
    the index is locked, changes are queued and later applied by
    World.flush_pending.
    """

    def _world_with(self, *components):
        world = World(10, 10)
        entity = Entity()
        for component in components:
            entity.add_component(component)
        world.place_entity(entity, 5, 5)
        return world, entity

    def test_add_component_updates_entity_index_and_cache(self):
        world = World(10, 10)
        world.index.register_system(frozenset([Biochemistry, Movable]))
        cache = world.index.systems_cache[frozenset([Biochemistry, Movable])]
        entity = Entity().add_component(Biochemistry())
        world.place_entity(entity, 5, 5)
        assert entity not in cache

        world.add_component(entity, Movable())

        assert entity.has_component(Movable)
        assert entity in world.index.component_index[Movable]
        assert entity in cache

    def test_add_component_duplicate_is_ignored(self):
        world, entity = self._world_with(Biochemistry(energy=50))
        world.add_component(entity, Biochemistry(energy=10))
        assert entity.get_component(Biochemistry).energy == 50

    def test_remove_component_returns_component_and_updates_cache(self):
        world = World(10, 10)
        world.index.register_system(frozenset([Biochemistry, Movable]))
        cache = world.index.systems_cache[frozenset([Biochemistry, Movable])]
        entity = Entity().add_component(Biochemistry()).add_component(Movable())
        world.place_entity(entity, 5, 5)
        assert entity in cache

        removed = world.remove_component(entity, Movable)

        assert isinstance(removed, Movable)
        assert not entity.has_component(Movable)
        assert entity not in world.index.component_index[Movable]
        assert entity not in cache

    def test_remove_missing_component_returns_none(self):
        world, entity = self._world_with(Biochemistry())
        assert world.remove_component(entity, Movable) is None

    def test_direct_mutation_after_indexing_raises(self):
        world, entity = self._world_with(Biochemistry())
        with pytest.raises(RuntimeError):
            entity.add_component(Render())
        with pytest.raises(RuntimeError):
            entity.remove_component(Biochemistry)

    def test_direct_mutation_before_indexing_is_allowed(self):
        entity = Entity()
        entity.add_component(Biochemistry())
        assert entity.has_component(Biochemistry)

    def test_deferred_component_addition_is_applied_on_flush(self):
        world = World(10, 10)
        world.index.register_system(frozenset([Biochemistry, Movable]))
        cache = world.index.systems_cache[frozenset([Biochemistry, Movable])]
        entity = Entity().add_component(Biochemistry())
        world.place_entity(entity, 5, 5)

        world.index.locked = True
        world.add_component(entity, Movable())
        assert not entity.has_component(Movable)
        assert entity in world.pending_component_addition

        world.index.locked = False
        world.flush_pending()

        assert entity.has_component(Movable)
        assert entity in cache
        assert world.pending_component_addition == {}

    def test_deferred_component_removal_is_applied_on_flush(self):
        world = World(10, 10)
        world.index.register_system(frozenset([Biochemistry, Movable]))
        cache = world.index.systems_cache[frozenset([Biochemistry, Movable])]
        entity = Entity().add_component(Biochemistry()).add_component(Movable())
        world.place_entity(entity, 5, 5)

        world.index.locked = True
        world.remove_component(entity, Movable)
        assert entity.has_component(Movable)
        assert entity in world.pending_component_removal

        world.index.locked = False
        world.flush_pending()

        assert not entity.has_component(Movable)
        assert entity not in world.index.component_index[Movable]
        assert entity not in cache
        assert world.pending_component_removal == {}

    def test_flush_pending_while_locked_does_nothing(self):
        world = World(10, 10)
        entity = Entity().add_component(Biochemistry())
        world.place_entity(entity, 5, 5)
        world.index.locked = True
        world.add_component(entity, Movable())

        world.flush_pending()

        assert not entity.has_component(Movable)
        assert entity in world.pending_component_addition

    def test_flush_pending_is_idempotent(self):
        world = World(10, 10)
        world.index.register_system(frozenset([Biochemistry, Movable]))
        cache = world.index.systems_cache[frozenset([Biochemistry, Movable])]
        entity = Entity().add_component(Biochemistry())
        world.place_entity(entity, 5, 5)
        world.index.locked = True
        world.add_component(entity, Movable())
        world.index.locked = False

        world.flush_pending()
        world.flush_pending()

        assert entity.has_component(Movable)
        assert entity in cache