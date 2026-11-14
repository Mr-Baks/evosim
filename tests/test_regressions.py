import pytest

from commands import CommandQueue, CommandStatus, MateCommand
from entity import Biochemistry, Breedable, Entity, State
from genome import Genome
from simulation import Simulation
from tests.helpers import default_genes
from world import QueryIndex, World


def make_breeder(genes: Genome) -> Entity:
    return (Entity()
            .add_component(genes)
            .add_component(Biochemistry())
            .add_component(Breedable()))


class TestSimulationUnlock:
    def test_index_unlocked_when_system_raises(self):
        sim = Simulation(tickspeed=10, fps=10, world_size=(10, 10))

        def broken_system(entities, world):
            raise RuntimeError('boom')

        sim.register_system(frozenset(), broken_system)
        with pytest.raises(RuntimeError):
            sim.handle_systems()

        assert sim.world.index.locked is False


class TestMateCommandSafety:
    def test_dead_partner_is_not_ready(self):
        world = World(10, 10)
        entity = make_breeder(default_genes())
        partner = make_breeder(default_genes())
        world.place_entity(entity, 5, 5)
        world.place_entity(partner, 6, 5)
        world.remove_entity(partner)

        command = MateCommand(partner=partner)
        assert command.is_ready(entity, world) is False

    def test_execute_with_dead_partner_fails_safely(self):
        world = World(10, 10)
        entity = (make_breeder(default_genes())
                  .add_component(CommandQueue())
                  .add_component(State()))
        partner = make_breeder(default_genes())
        world.place_entity(entity, 5, 5)
        world.place_entity(partner, 6, 5)
        world.remove_entity(partner)

        command = MateCommand(partner=partner)
        queue = entity.get_component(CommandQueue)
        queue.running = command

        command.execute(entity, world)

        assert command.status == CommandStatus.FAILED
        assert queue.running is None


class TestWorldIndexConsistency:
    def test_remove_entity_clears_index_when_position_is_stale(self):
        world = World(10, 10)
        entity = Entity().add_component(Biochemistry())
        world.place_entity(entity, 5, 5)
        entity.x, entity.y = 7, 7

        assert world.remove_entity(entity) is entity
        assert entity not in world.index.entities
        assert entity not in world.index.get_with(Biochemistry)

    def test_query_index_remove_entity_is_idempotent(self):
        index = QueryIndex()
        entity = Entity().add_component(Biochemistry())
        index.add_entity(entity)

        index.remove_entity(entity)
        index.remove_entity(entity)

        assert entity not in index.entities
        assert index.get_with(Biochemistry) == []

    def test_place_entity_assigns_eid_before_indexing(self):
        world = World(10, 10)
        entity = Entity()

        world.place_entity(entity, 1, 1)

        assert entity.eid is not None
        assert entity in world.index.entities

    def test_get_cells_near_stays_in_bounds(self):
        world = World(10, 10)
        entity = Entity()
        world.place_entity(entity, 0, 0)

        cells = world.get_cells_near(entity, radius=2)

        assert all(0 <= x < world.width and 0 <= y < world.height for x, y in cells)
        assert (0, 0) not in cells
