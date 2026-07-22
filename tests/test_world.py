import pytest
from entity import Entity, Biochemistry, Movable, Render, Eatable, Plant, Vision, Breedable, State, Component
from world import World, QueryIndex


class TestQueryIndex:
    def test_init(self):
        index = QueryIndex()
        assert index.entities == set()
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
        index.locked = True
        e = Entity().add_component(Biochemistry())
        index.add_entity(e)
        index.remove_entity(e)
        assert e in index.pending_removal
        assert e in index.pending_addition  # When locked, add_entity puts in pending_addition

    def test_flush_pending(self):
        index = QueryIndex()
        index.locked = True
        e1 = Entity().add_component(Biochemistry())
        e2 = Entity().add_component(Movable())
        index.add_entity(e1)
        index.remove_entity(e2)
        
        index.locked = False
        index.flush_pending()
        
        assert e1 in index.entities
        assert Biochemistry in index.component_index
        assert e1 in index.component_index[Biochemistry]
        assert e2 not in index.entities

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
        assert index.systems_cache[components] == {e1}

    def test_get_with_single_component(self):
        index = QueryIndex()
        e1 = Entity().add_component(Biochemistry())
        e2 = Entity().add_component(Biochemistry())
        e3 = Entity().add_component(Movable())
        index.add_entity(e1)
        index.add_entity(e2)
        index.add_entity(e3)
        
        result = index.get_with(Biochemistry)
        assert result == {e1, e2}

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
        assert result == {e1, e4}

    def test_get_with_no_components(self):
        index = QueryIndex()
        e1 = Entity().add_component(Biochemistry())
        e2 = Entity().add_component(Movable())
        index.add_entity(e1)
        index.add_entity(e2)
        
        result = index.get_with()
        assert result == {e1, e2}

    def test_get_with_missing_component(self):
        index = QueryIndex()
        e1 = Entity().add_component(Biochemistry())
        index.add_entity(e1)
        
        result = index.get_with(Plant)
        assert result == set()


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