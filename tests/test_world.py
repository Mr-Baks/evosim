import pytest
from entity import Entity, Biochemistry, Movable, Render, Eatable, Plant, Vision, Breedable, State, Component
from world import World, QueryIndex


class TestWorldInit:
    def test_init_defaults(self):
        world = World()
        assert world.width == 60
        assert world.height == 15
        assert len(world.cells) == 15
        assert len(world.cells[0]) == 60

    def test_init_custom_size(self):
        world = World(width=20, height=10)
        assert world.width == 20
        assert world.height == 10
        assert len(world.cells) == 10
        assert len(world.cells[0]) == 20

    def test_init_offset_cache(self):
        world = World()
        assert 1 in world._offset_cache
        offsets = world._offset_cache[1]
        assert len(offsets) == 8
        assert (0, 0) not in offsets


class TestWorldCheckCell:
    def test_check_cell_valid_empty(self):
        world = World(10, 10)
        assert world._check_cell(5, 5) is True

    def test_check_cell_out_of_bounds(self):
        world = World(10, 10)
        assert world._check_cell(-1, 5) is False
        assert world._check_cell(10, 5) is False
        assert world._check_cell(5, -1) is False
        assert world._check_cell(5, 10) is False

    def test_check_cell_occupied(self):
        world = World(10, 10)
        e = Entity().add_component(Movable())
        world.place_entity(e, 5, 5)
        assert world._check_cell(5, 5) is False


class TestWorldMakeMove:
    def test_make_move_success(self):
        world = World(10, 10)
        e = Entity(x=5, y=5).add_component(Movable())
        world.place_entity(e, 5, 5)
        
        result = world.make_move(e, 6, 5)
        
        assert result is True
        assert e.x == 6
        assert e.y == 5
        assert world.get_entity(6, 5) is e
        assert world.get_entity(5, 5) is None

    def test_make_move_no_movable_component(self):
        world = World(10, 10)
        e = Entity(x=5, y=5)
        world.place_entity(e, 5, 5)
        
        result = world.make_move(e, 6, 5)
        
        assert result is False
        assert e.x == 5
        assert e.y == 5

    def test_make_move_invalid_target(self):
        world = World(10, 10)
        e = Entity(x=5, y=5).add_component(Movable())
        world.place_entity(e, 5, 5)
        
        result = world.make_move(e, -1, 5)
        
        assert result is False

    def test_make_move_target_occupied(self):
        world = World(10, 10)
        e1 = Entity(x=5, y=5).add_component(Movable())
        e2 = Entity(x=6, y=5).add_component(Movable())
        world.place_entity(e1, 5, 5)
        world.place_entity(e2, 6, 5)
        
        result = world.make_move(e1, 6, 5)
        
        assert result is False

    def test_make_move_entity_not_at_source(self):
        world = World(10, 10)
        e = Entity(x=5, y=5).add_component(Movable())
        world.place_entity(e, 5, 5)
        
        world.cells[5][5] = None
        world.cells[6][5] = e
        e.x, e.y = 6, 5
        
        result = world.make_move(e, 7, 5)
        
        assert result is False


class TestWorldGetEntity:
    def test_get_entity_valid(self):
        world = World(10, 10)
        e = Entity().add_component(Movable())
        world.place_entity(e, 5, 5)
        
        result = world.get_entity(5, 5)
        
        assert result is e

    def test_get_entity_empty(self):
        world = World(10, 10)
        
        result = world.get_entity(5, 5)
        
        assert result is None

    def test_get_entity_out_of_bounds(self):
        world = World(10, 10)
        
        assert world.get_entity(-1, 5) is None
        assert world.get_entity(10, 5) is None
        assert world.get_entity(5, -1) is None
        assert world.get_entity(5, 10) is None


class TestWorldPlaceEntity:
    def test_place_entity_success(self):
        world = World(10, 10)
        e = Entity().add_component(Movable())
        
        result = world.place_entity(e, 5, 5)
        
        assert result is True
        assert world.get_entity(5, 5) is e
        assert e.x == 5
        assert e.y == 5
        assert e in world.index.entities

    def test_place_entity_occupied(self):
        world = World(10, 10)
        e1 = Entity().add_component(Movable())
        e2 = Entity().add_component(Movable())
        world.place_entity(e1, 5, 5)
        
        result = world.place_entity(e2, 5, 5)
        
        assert result is False
        assert world.get_entity(5, 5) is e1

    def test_place_entity_out_of_bounds(self):
        world = World(10, 10)
        e = Entity().add_component(Movable())
        
        result = world.place_entity(e, -1, 5)
        
        assert result is False


class TestWorldRemoveEntity:
    def test_remove_entity_success(self):
        world = World(10, 10)
        e = Entity().add_component(Movable())
        world.place_entity(e, 5, 5)
        
        result = world.remove_entity(e)
        
        assert result is e
        assert world.get_entity(5, 5) is None
        assert e not in world.index.entities

    def test_remove_entity_not_in_world(self):
        world = World(10, 10)
        e = Entity().add_component(Movable())
        
        result = world.remove_entity(e)
        
        assert result is None


class TestWorldGetOffsets:
    def test_get_offsets_cached(self):
        world = World()
        offsets1 = world._get_offsets(1)
        offsets2 = world._get_offsets(1)
        assert offsets1 is offsets2

    def test_get_offsets_radius_1(self):
        world = World()
        offsets = world._get_offsets(1)
        assert len(offsets) == 8
        assert (0, 0) not in offsets
        assert (1, 0) in offsets
        assert (0, 1) in offsets
        assert (-1, -1) in offsets

    def test_get_offsets_radius_2(self):
        world = World()
        offsets = world._get_offsets(2)
        assert len(offsets) == 12
        assert (0, 0) not in offsets
        assert (2, 0) in offsets
        assert (1, 1) in offsets
        assert (2, 2) not in offsets


class TestWorldGetNeighbours:
    def test_get_neighbours_radius_1(self):
        world = World(10, 10)
        center = Entity().add_component(Movable())
        world.place_entity(center, 5, 5)
        
        neighbours = []
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                if dx == 0 and dy == 0:
                    continue
                e = Entity().add_component(Movable())
                world.place_entity(e, 5+dx, 5+dy)
                neighbours.append(e)
        
        result = world.get_neighbours(center, radius=1)
        
        assert len(result) == 8
        for e in neighbours:
            assert e in result

    def test_get_neighbours_excludes_center(self):
        world = World(10, 10)
        center = Entity().add_component(Movable())
        world.place_entity(center, 5, 5)
        
        result = world.get_neighbours(center, radius=1)
        
        assert center not in result

    def test_get_neighbours_radius_2(self):
        world = World(10, 10)
        center = Entity().add_component(Movable())
        world.place_entity(center, 5, 5)
        
        e = Entity().add_component(Movable())
        world.place_entity(e, 7, 5)
        
        result = world.get_neighbours(center, radius=2)
        
        assert e in result


class TestWorldGetFreeCellsNear:
    def test_get_free_cells_near(self):
        world = World(10, 10)
        center = Entity().add_component(Movable())
        world.place_entity(center, 5, 5)
        
        e = Entity().add_component(Movable())
        world.place_entity(e, 4, 5)
        
        free = world.get_free_cells_near(center, radius=1)
        
        assert len(free) == 7
        assert (4, 5) not in free
        assert (5, 5) not in free
        assert (6, 5) in free

    def test_get_free_cells_near_all_occupied(self):
        world = World(10, 10)
        center = Entity().add_component(Movable())
        world.place_entity(center, 5, 5)
        
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                if dx == 0 and dy == 0:
                    continue
                e = Entity().add_component(Movable())
                world.place_entity(e, 5+dx, 5+dy)
        
        free = world.get_free_cells_near(center, radius=1)
        
        assert len(free) == 0


class TestWorldGetCellsNear:
    def test_get_cells_near(self):
        world = World(10, 10)
        center = Entity().add_component(Movable())
        world.place_entity(center, 5, 5)
        
        cells = world.get_cells_near(center, radius=1)
        
        assert len(cells) == 8
        assert (4, 4) in cells
        assert (5, 4) in cells
        assert (6, 6) in cells
        assert (5, 5) not in cells


class TestWorldIntegration:
    def test_full_cycle_place_move_remove(self):
        world = World(20, 20)
        
        e = Entity().add_component(Movable()).add_component(Biochemistry())
        assert world.place_entity(e, 10, 10)
        
        assert world.make_move(e, 11, 10)
        assert e.x == 11
        assert e.y == 10
        
        assert world.remove_entity(e) is e
        assert world.get_entity(11, 10) is None

    def test_plant_fruit_generation_area(self):
        world = World(20, 20)
        plant = Entity().add_component(Plant(fructify_threshold=10, fruit_nutrition=25))
        plant.add_component(Render(symbol='P'))
        world.place_entity(plant, 10, 10)
        
        plant.get_component(Plant).energy = 15
        
        free = world.get_free_cells_near(plant, radius=1)
        assert len(free) > 0
        
        fruit = Entity().add_component(Eatable(nutrition=25)).add_component(Render(symbol='f'))
        world.place_entity(fruit, *free[0])
        
        assert world.get_entity(free[0][0], free[0][1]) is fruit