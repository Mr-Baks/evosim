"""Interactive entry point: build the default world from ``SimConfig`` and run it.

Running this module directly starts the TUI simulation. Importing it has no
side effects, so experiment runners and tests can reuse ``build_simulation``.
"""
import random

from commands import *
from config import SimConfig, load_config
from entity import *
from event_bus import EatEvent, Event, EventBus, MoveEvent, SleepEvent, on_eat, on_move, on_sleep
from genome import Gene, GeneNames, Genome
from simulation import Simulation
from systems import *
from world import World


def make_creature(x, y, world: World, cfg: SimConfig, color=None):
    color = color or cfg.scenario.creature_color

    genes = [Gene(name, a1, a2, dominant=dom) for name, a1, a2, dom in cfg.scenario.founder_genes]
    genes.append(Gene(GeneNames.COLOR_R, (color[0] - 128) / 128, -1, dominant=False))
    genes.append(Gene(GeneNames.COLOR_G, (color[1] - 128) / 128, -1, dominant=False))
    genes.append(Gene(GeneNames.COLOR_B, (color[2] - 128) / 128, -1, dominant=False))

    e = (Entity().add_component(Movable()).add_component(Biochemistry())
         .add_component(Vision(8)).add_component(CommandQueue()).add_component(State())
         .add_component(Breedable()).add_component(Render(symbol='C', color=color))
         .add_component(Genome(genes)))
    world.place_entity(e, x, y)


def make_food(x, y, world: World, nutrition=20):
    e = Entity().add_component(Eatable(nutrition))
    world.place_entity(e, x, y)


def make_plant(x, y, world: World, cfg: SimConfig):
    threshold = random.randint(cfg.balance.plant_fructify_min, cfg.balance.plant_fructify_max)
    e = Entity().add_component(Plant(fructify_threshold=threshold)).add_component(Render(symbol='P', color=(0, 200, 10)))
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


def build_simulation(cfg: SimConfig) -> Simulation:
    """Assemble the default world described by ``cfg`` (no stepping)."""
    sim = Simulation(cfg.run.tickspeed, cfg.run.fps, cfg.scenario.world.size, background_sym='.')

    sim.world.event_bus.subscribe(EatEvent, on_eat)
    sim.world.event_bus.subscribe(SleepEvent, on_sleep)
    sim.world.event_bus.subscribe(MoveEvent, on_move)

    if not cfg.run.headless:
        sim.register_system(frozenset([CommandQueue, State, Biochemistry]), logging_system, priority=0)
        sim.add_on_tick(tick_stats)
        
    sim.register_system(frozenset([CommandQueue]), command_system, priority=50)
    sim.register_system(frozenset([Vision]), vision_system, priority=200)
    sim.register_system(frozenset([CommandQueue, Biochemistry]), biochemistry_system, priority=70)
    sim.register_system(frozenset([Plant]), plant_system, priority=75)
    sim.register_system(frozenset([CommandQueue, State]), decision_system, priority=100)

    _scatter(sim, cfg.scenario.initial_plants, lambda x, y: make_plant(x, y, sim.world, cfg))
    _scatter(sim, cfg.scenario.initial_creatures, lambda x, y: make_creature(x, y, sim.world, cfg))

    return sim


def run_headless(sim: Simulation, ticks: int) -> None:
    """Step the simulation without wall-clock pacing or rendering."""
    for _ in range(ticks):
        sim.handle_systems()
        sim.world.event_bus.dispatch()
        sim.tick += 1


def main(cfg: SimConfig | None = None) -> None:
    if cfg is None:
        cfg = load_config()

    random.seed(cfg.run.seed)
    sim = build_simulation(cfg)

    if cfg.run.headless:
        run_headless(sim, cfg.run.ticks)
    else:
        sim.run(target_tick=cfg.run.ticks)


if __name__ == '__main__':
    main()
