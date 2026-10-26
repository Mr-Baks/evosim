import csv

import main
from commands import create_child
from config import RunConfig, ScenarioConfig, SimConfig, WorldConfig
from entity import Biochemistry, Lineage, Movable, Plant
from event_bus import BirthEvent, DeathEvent


def _cfg(tmp_path, initial_creatures=0, initial_plants=0):
    return SimConfig(
        run=RunConfig(
            seed=1,
            headless=True,
            output_dir=str(tmp_path / 'out'),
            record_every=5,
        ),
        scenario=ScenarioConfig(
            world=WorldConfig(20, 20),
            initial_creatures=initial_creatures,
            initial_plants=initial_plants,
        ),
    )


def _read(path):
    with open(path, newline='') as file:
        return list(csv.reader(file))


def test_build_logger_writes_initial_population(tmp_path):
    cfg = _cfg(tmp_path, initial_creatures=3, initial_plants=5)
    sim = main.build_simulation(cfg)

    logger = main.build_logger(sim, cfg)
    logger.close()

    rows = _read(tmp_path / 'out' / 'population.csv')
    assert rows[0] == [
        'tick', 'creatures', 'plants', 'food',
        'mean_energy', 'mean_hunger', 'mean_age', 'mean_speed',
    ]
    assert len(rows) == 2
    assert int(rows[1][0]) == 0
    assert int(rows[1][1]) == len(sim.world.index.get_with(Movable))
    assert int(rows[1][2]) == len(sim.world.index.get_with(Plant))


def test_build_logger_records_births(tmp_path):
    cfg = _cfg(tmp_path)
    sim = main.build_simulation(cfg)
    logger = main.build_logger(sim, cfg)

    main.make_creature(1, 1, sim.world, cfg)
    main.make_creature(2, 2, sim.world, cfg)
    parent1 = sim.world.get_entity(1, 1)
    parent2 = sim.world.get_entity(2, 2)

    child = create_child(parent1, parent2, sim.world)
    lineage = child.get_component(Lineage)
    lineage.generation = 1
    lineage.parents_eid = (parent1.eid, parent2.eid)
    sim.world.place_entity(child, 3, 3)

    sim.world.event_bus.emit(BirthEvent(source=child, parent1=parent1, parent2=parent2))
    sim.world.event_bus.dispatch()
    logger.close()

    rows = _read(tmp_path / 'out' / 'births.csv')
    assert rows[0] == ['tick', 'child_eid', 'parent1_eid', 'parent2_eid', 'generation']
    assert rows[1] == ['0', str(child.eid), str(parent1.eid), str(parent2.eid), '1']


def test_build_logger_records_deaths(tmp_path):
    cfg = _cfg(tmp_path)
    sim = main.build_simulation(cfg)
    logger = main.build_logger(sim, cfg)

    main.make_creature(4, 4, sim.world, cfg)
    entity = sim.world.get_entity(4, 4)
    bio = entity.get_component(Biochemistry)
    bio.age = 42
    bio.energy = 0
    bio.hunger = 3
    bio.health = 0
    bio.max_health = 20

    sim.world.remove_entity(entity)
    sim.world.event_bus.emit(DeathEvent(source=entity, age=bio.age))
    sim.world.event_bus.dispatch()
    logger.close()

    rows = _read(tmp_path / 'out' / 'deaths.csv')
    assert rows[0] == [
        'tick', 'eid', 'age', 'generation',
        'energy', 'hunger', 'health', 'max_health',
    ]
    assert rows[1][0] == '0'
    assert int(rows[1][1]) == entity.eid
    assert float(rows[1][2]) == 42
    assert rows[1][3] == '0'
    assert float(rows[1][4]) == 0
    assert float(rows[1][5]) == 3
    assert float(rows[1][6]) == 0
    assert float(rows[1][7]) == 20


def test_logger_close_is_idempotent(tmp_path):
    cfg = _cfg(tmp_path)
    sim = main.build_simulation(cfg)
    logger = main.build_logger(sim, cfg)

    logger.close()
    logger.close()
