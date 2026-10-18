"""Determinism tests for the ``eid`` (entity-id) ordering in ``QueryIndex``.

The simulation must not depend on Python's identity-hash ``set`` iteration
order. Every entity gets a monotonic ``eid`` at placement time, and each
collection the systems iterate (``component_index``, ``systems_cache`` and
``World.get_neighbours``) is kept sorted by ``eid`` before systems run.

These tests pin that contract: they build entities, deliberately scramble the
index structures, and assert that eid order is restored / preserved.
"""
import random

import main
from config import RunConfig, ScenarioConfig, SimConfig, WorldConfig
from entity import Biochemistry, Entity, Movable, Plant
from simulation import Simulation
from world import World


def _entity_with(*components):
    entity = Entity()
    for component in components:
        entity.add_component(component)
    return entity


def _snapshot(sim):
    rows = []
    for e in sim.world.index.get_with(Movable):
        bio = e.get_component(Biochemistry)
        rows.append((
            e.eid, e.x, e.y,
            round(bio.energy, 6), round(bio.hunger, 6),
            round(bio.health, 6), round(bio.age, 6),
        ))
    rows.sort()
    return rows


class TestEidAssignment:
    def test_place_entity_assigns_monotonic_eids(self):
        world = World(10, 10)
        eids = []
        for x in range(5):
            e = _entity_with(Biochemistry())
            world.place_entity(e, x, 0)
            eids.append(e.eid)
        assert eids == [0, 1, 2, 3, 4]

    def test_eids_are_unique(self):
        world = World(5, 5)
        seen = set()
        for x in range(5):
            for y in range(5):
                e = _entity_with(Biochemistry())
                world.place_entity(e, x, y)
                seen.add(e.eid)
        assert len(seen) == 25

    def test_entity_starts_without_eid(self):
        assert Entity().eid is None


class TestIndexEidOrdering:
    def test_component_index_sorted_by_eid_after_sort_cache(self):
        world = World(10, 10)
        for x in range(4):
            world.place_entity(_entity_with(Biochemistry()), x, 0)

        # Scramble on purpose: sort_cache must repair structural churn.
        world.index.component_index[Biochemistry].reverse()
        world.index.component_index_dirty = True
        world.index.sort_cache()

        eids = [e.eid for e in world.index.component_index[Biochemistry]]
        assert eids == [0, 1, 2, 3]

    def test_systems_cache_sorted_by_eid_after_sort_cache(self):
        world = World(10, 10)
        world.index.register_system(frozenset([Biochemistry]))
        cache = world.index.systems_cache[frozenset([Biochemistry])]
        for x in range(4):
            world.place_entity(_entity_with(Biochemistry()), x, 0)

        cache.reverse()
        world.index.systems_cache_dirty = True
        world.index.sort_cache()

        assert [e.eid for e in cache] == [0, 1, 2, 3]

    def test_get_with_returns_entities_in_eid_order(self):
        world = World(10, 10)
        for x in range(4):
            world.place_entity(_entity_with(Biochemistry()), x, 0)
        world.index.sort_cache()

        assert [e.eid for e in world.index.get_with(Biochemistry)] == [0, 1, 2, 3]

    def test_direct_index_insertion_order_is_repaired_by_eid(self):
        # Mirrors the failure mode the eid migration targets: an arbitrary
        # (hash-like) order must be re-sorted back into creation order.
        world = World(10, 10)
        a = _entity_with(Biochemistry()); world.place_entity(a, 0, 0)
        b = _entity_with(Biochemistry()); world.place_entity(b, 1, 0)
        c = _entity_with(Biochemistry()); world.place_entity(c, 2, 0)

        world.index.component_index[Biochemistry][:] = [c, a, b]
        world.index.component_index_dirty = True
        world.index.sort_cache()

        assert world.index.component_index[Biochemistry] == [a, b, c]

    def test_flush_pending_preserves_eid_order(self):
        world = World(10, 10)
        world.index.register_system(frozenset([Biochemistry]))
        world.index.locked = True
        for x in range(3):
            world.place_entity(_entity_with(Biochemistry()), x, 0)
        world.index.locked = False
        world.flush_pending()

        cache = world.index.systems_cache[frozenset([Biochemistry])]
        assert [e.eid for e in cache] == [0, 1, 2]

    def test_get_neighbours_sorted_by_eid(self):
        world = World(10, 10)
        center = _entity_with(Biochemistry())
        world.place_entity(center, 5, 5)
        # Placed out of geometric order; eid still dictates the result order.
        n_right = _entity_with(Biochemistry()); world.place_entity(n_right, 6, 5)
        n_left = _entity_with(Biochemistry()); world.place_entity(n_left, 4, 5)
        n_below = _entity_with(Biochemistry()); world.place_entity(n_below, 5, 6)

        neighbours = world.get_neighbours(center, radius=1)

        assert neighbours == [n_right, n_left, n_below]
        assert [e.eid for e in neighbours] == [1, 2, 3]


class TestSystemsEidOrdering:
    def _sim_recording(self, seen):
        sim = Simulation(tickspeed=10, fps=30, world_size=(10, 10))
        sim.register_system(
            frozenset([Biochemistry]),
            lambda entities, world: seen.append([e.eid for e in entities]),
            priority=1,
        )
        return sim

    def test_systems_receive_entities_in_eid_order(self):
        seen = []
        sim = self._sim_recording(seen)
        for x in range(4):
            sim.world.place_entity(_entity_with(Biochemistry()), x, 0)

        sim.handle_systems()

        assert seen == [[0, 1, 2, 3]]

    def test_handle_systems_sorts_before_running_even_when_scrambled(self):
        seen = []
        sim = self._sim_recording(seen)
        for x in range(4):
            sim.world.place_entity(_entity_with(Biochemistry()), x, 0)

        # Recreate the churn a set-based cache would hand to the systems.
        cache = sim.world.index.systems_cache[frozenset([Biochemistry])]
        cache.reverse()
        sim.world.index.systems_cache_dirty = True

        sim.handle_systems()

        assert seen == [[0, 1, 2, 3]]


class TestEndToEndDeterminism:
    def _build_and_run(self, ticks):
        cfg = SimConfig(
            run=RunConfig(seed=2024, ticks=ticks, headless=True),
            scenario=ScenarioConfig(
                world=WorldConfig(30, 30),
                initial_plants=30,
                initial_creatures=12,
            ),
        )
        random.seed(cfg.run.seed)
        sim = main.build_simulation(cfg)
        main.run_headless(sim, ticks)
        return sim

    def test_same_seed_produces_identical_final_state(self):
        # Two fully independent runs (same process, same seed) with births and
        # deaths must end in the exact same state: eid ordering, not identity
        # hashing, drives every system.
        ticks = 150
        first = self._build_and_run(ticks)
        second = self._build_and_run(ticks)

        assert _snapshot(first) == _snapshot(second)
        assert len(first.world.index.get_with(Plant)) == len(second.world.index.get_with(Plant))

    def test_restarting_seed_reproduces_state(self):
        # Re-seeding inside the same process must reproduce the run exactly.
        ticks = 80
        first = self._build_and_run(ticks)
        again = self._build_and_run(ticks)

        assert _snapshot(first) == _snapshot(again)
