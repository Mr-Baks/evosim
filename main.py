"""Interactive entry point: build the default world from SimConfig and run it.

Running this module directly starts the TUI simulation. Importing it has no
side effects, so experiment runners and tests can reuse build_simulation.
"""
import random
from commands import *
from config import SimConfig, load_config, FounderGene
from entity import *
from event_bus import BirthEvent, DeathEvent, EatEvent, Event, EventBus, MoveEvent, SleepEvent, on_eat, on_move, on_sleep
from genome import Gene, GeneNames, Genome
from logger import RunLogger
from simulation import Simulation
from systems import *
from world import World


def jitter_genes(genes: tuple[FounderGene], jitter: float = 0.1) -> tuple[FounderGene]:
    jittered = []
    for gene in genes:
        delta = random.uniform(-jitter, jitter)
        name, a1, a2, dominance = gene

        if abs(a1 + delta) > 1:
            a1 -= delta
        else:
            a1 += delta

        if abs(a2 + delta) > 1:
            a2 -= delta
        else:
            a2 += delta

        jittered.append((name, a1, a2, dominance))
    return tuple(jittered)

def make_creature(x, y, world: World, cfg: SimConfig, color=None):
    color = color or cfg.scenario.creature_color
    founder_genes = jitter_genes(cfg.scenario.founder_genes, jitter=cfg.scenario.founder_genes_jitter)
    genes = [Gene(name, a1, a2, dominance=dom) for name, a1, a2, dom in founder_genes]
    genes.append(Gene(GeneNames.COLOR_R, (color[0] - 128) / 128, (color[0] - 128) / 128, dominance=0.5))
    genes.append(Gene(GeneNames.COLOR_G, (color[1] - 128) / 128, (color[1] - 128) / 128, dominance=0.5))
    genes.append(Gene(GeneNames.COLOR_B, (color[2] - 128) / 128, (color[2] - 128) / 128, dominance=0.5))

    e = create_entity_from_genome(Genome(genes))

    world.place_entity(e, x, y)

def make_food(x, y, world: World, nutrition=20):
    e = Entity().add_component(Eatable(nutrition))
    world.place_entity(e, x, y)

def make_plant(x, y, world: World, cfg: SimConfig):
    threshold = random.randint(cfg.balance.plant_fructify_min, cfg.balance.plant_fructify_max)
    e = (Entity()
         .add_component(Plant(energy_increase=cfg.balance.plant_energy_increase,
                              fructify_threshold=threshold,
                              fruit_nutrition=cfg.balance.plant_fruit_nutrition))
         .add_component(Render(symbol='P', color=(0, 200, 10))))
    world.place_entity(e, x, y)

def tick_stats(sim: Simulation):
    food_amount = len(sim.world.index.get_with(Eatable))
    creatures_amount = len(sim.world.index.get_with(Movable))

    speeds = [e.get_component(Movable).speed for e in sim.world.index.get_with(Movable)]
    avg_speed = sum(speeds) / len(speeds) if len(speeds) > 0 else 0

    print(f'creatures: {creatures_amount} | food: {food_amount} | avg speed: {avg_speed}')

def _scatter(sim: Simulation, count: int, make):
    world = sim.world
    for _ in range(count):
        x = random.randint(0, world.width - 1)
        y = random.randint(0, world.height - 1)
        if not world.get_entity(x, y):
            make(x, y)

def _mean(values):
    return sum(values) / len(values) if values else 0.0

def log_population(world: World, tick: int):
    creatures = [e for e in world.index.get_with(Movable) if e.get_component(Biochemistry)]
    biochemistry = [e.get_component(Biochemistry) for e in creatures]
    return [
        tick,
        len(creatures),
        len(world.index.get_with(Plant)),
        len(world.index.get_with(Eatable)),
        _mean([bio.energy for bio in biochemistry]),
        _mean([bio.hunger for bio in biochemistry]),
        _mean([bio.age for bio in biochemistry]),
        _mean([e.get_component(Movable).speed for e in creatures]),
    ]

def log_birth(event: BirthEvent, world: World, tick: int):
    child = event.source
    lineage = child.get_component(Lineage)
    return [
        tick,
        child.eid,
        event.parent1.eid if event.parent1 else None,
        event.parent2.eid if event.parent2 else None,
        lineage.generation if lineage else 0,
    ]

def log_death(event: DeathEvent, world: World, tick: int):
    entity = event.source
    bio = entity.get_component(Biochemistry)
    lineage = entity.get_component(Lineage)
    return [
        tick,
        entity.eid,
        event.age,
        lineage.generation if lineage else 0,
        bio.energy if bio else None,
        bio.hunger if bio else None,
        bio.health if bio else None,
        bio.max_health if bio else None,
    ]

def build_logger(sim: Simulation, cfg: SimConfig) -> RunLogger:
    logger = RunLogger(sim.world, sim.world.event_bus, cfg.run.output_dir)
    period = max(1, cfg.run.record_every)
    logger.add_query(
        'population', log_population,
        ['tick', 'creatures', 'plants', 'food', 'mean_energy', 'mean_hunger', 'mean_age', 'mean_speed'],
        every=period,
    )
    logger.add_event_query(
        'births', BirthEvent, log_birth,
        ['tick', 'child_eid', 'parent1_eid', 'parent2_eid', 'generation'],
    )
    logger.add_event_query(
        'deaths', DeathEvent, log_death,
        ['tick', 'eid', 'age', 'generation', 'energy', 'hunger', 'health', 'max_health'],
    )
    sim.add_on_tick(lambda s: logger.on_tick(s.tick))
    logger.on_tick(sim.tick)
    return logger

def build_simulation(cfg: SimConfig) -> Simulation:
    """Assemble the default world described by ``cfg`` (no stepping)."""
    sim = Simulation(cfg.run.tickspeed, cfg.run.fps, cfg.scenario.world.size, background_sym='.')
    sim.world.balance = cfg.balance

    sim.world.event_bus.subscribe(EatEvent, on_eat)
    sim.world.event_bus.subscribe(SleepEvent, on_sleep)
    sim.world.event_bus.subscribe(MoveEvent, on_move)

    if not cfg.run.headless:
        sim.register_system(frozenset([CommandQueue, State, Biochemistry, Vision, Genome]), logging_system, priority=0)
        sim.add_on_tick(tick_stats)
        
    sim.register_system(frozenset([CommandQueue]), command_system, priority=50)
    sim.register_system(frozenset([Vision]), vision_system, priority=200)
    sim.register_system(frozenset([CommandQueue, Biochemistry]), biochemistry_system, priority=70)
    sim.register_system(frozenset([Plant]), plant_system, priority=75)
    sim.register_system(frozenset([CommandQueue, State, Biochemistry, Vision, Genome]), decision_system, priority=100)

    _scatter(sim, cfg.scenario.initial_plants, lambda x, y: make_plant(x, y, sim.world, cfg))
    _scatter(sim, cfg.scenario.initial_creatures, lambda x, y: make_creature(x, y, sim.world, cfg))

    return sim

def run_headless(sim: Simulation, ticks: int) -> None:
    """Step the simulation without wall-clock pacing or rendering."""
    for _ in range(ticks):
        sim.step()

def main(cfg: SimConfig | None = None) -> None:
    if cfg is None:
        cfg = load_config()

    random.seed(cfg.run.seed)
    sim = build_simulation(cfg)
    logger = build_logger(sim, cfg)

    try:
        if cfg.run.headless:
            run_headless(sim, cfg.run.ticks)
        else:
            sim.run(target_tick=cfg.run.ticks)
    finally:
        logger.close()

if __name__ == '__main__':
    main()
