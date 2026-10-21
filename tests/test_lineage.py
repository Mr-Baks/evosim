import random

import main
from config import RunConfig, ScenarioConfig, SimConfig
from entity import Lineage, Movable


def _run(seed=1, ticks=500):
    cfg = SimConfig(
        run=RunConfig(seed=seed, ticks=ticks, headless=True),
        scenario=ScenarioConfig(),
    )
    random.seed(cfg.run.seed)
    sim = main.build_simulation(cfg)
    main.run_headless(sim, cfg.run.ticks)
    return sim


def test_founders_start_at_generation_zero():
    cfg = SimConfig(scenario=ScenarioConfig())
    random.seed(cfg.run.seed)
    sim = main.build_simulation(cfg)

    lineages = [e.get_component(Lineage) for e in sim.world.index.get_with(Movable)]
    assert lineages
    assert all(lineage.generation == 0 for lineage in lineages)
    assert all(lineage.parents_eid is None for lineage in lineages)


def test_children_have_a_higher_generation_than_their_parents():
    sim = _run(ticks=500)
    lineages = [e.get_component(Lineage) for e in sim.world.index.get_with(Movable)]

    assert lineages
    assert max(lineage.generation for lineage in lineages) >= 1
    for lineage in lineages:
        if lineage.parents_eid is not None:
            assert lineage.generation >= 1
            assert len(lineage.parents_eid) == 2
            assert all(isinstance(eid, int) for eid in lineage.parents_eid)


def test_lineage_is_deterministic():
    def snapshot():
        sim = _run(seed=3, ticks=300)
        return sorted(
            (e.eid, e.get_component(Lineage).generation, e.get_component(Lineage).parents_eid)
            for e in sim.world.index.get_with(Movable)
        )

    assert snapshot() == snapshot()
