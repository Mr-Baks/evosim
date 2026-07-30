from entity import * 
from world import World
from simulation import Simulation
import random
from commands import *
from event_bus import Event, EventBus
from systems import *
from genome import Gene, GeneNames, Genome


def make_creature(x, y, world: World, color=(80, 120, 200)):
    genes = []
    genes.append(Gene(GeneNames.SPEED, 0.3, 0.3, dominant=False))
    genes.append(Gene(GeneNames.ENERGY_THRESHOLD, -0.3, -0.3))
    genes.append(Gene(GeneNames.HUNGER_THRESHOLD, -0.3, -0.3))
    genes.append(Gene(GeneNames.COLOR_R, (color[0] - 128) / 128, -1))
    genes.append(Gene(GeneNames.COLOR_G, (color[1] - 128) / 128, -1))
    genes.append(Gene(GeneNames.COLOR_B, (color[2] - 128) / 128, -1))
    genes.append(Gene(GeneNames.METABOLISM, 0.1, 0.2, dominant=False))
    e = Entity().add_component(Movable()).add_component(Biochemistry()).add_component(Vision(8)).add_component(CommandQueue()).add_component(State()).add_component(Breedable()).add_component(Render(symbol='C', color=color)).add_component(Genome(genes))
    world.place_entity(e, x, y)

def make_food(x, y, world: World, nutrition=20):
    e = Entity().add_component(Eatable(nutrition))
    world.place_entity(e, x, y)   

def make_plant(x, y, world: World):
    e = Entity().add_component(Plant(fructify_threshold=random.randint(70, 90))).add_component(Render(symbol='P', color=(0, 200, 10)))
    world.place_entity(e, x, y)

s = Simulation(10, 10, (190, 40), background_sym='.')

s.world.event_bus.subscribe(EatEvent, on_eat)
s.world.event_bus.subscribe(SleepEvent, on_sleep)
s.world.event_bus.subscribe(MoveEvent, on_move)

s.register_system(frozenset([CommandQueue]), command_system, priority=50)
s.register_system(frozenset([Vision]), vision_system, priority=80)
s.register_system(frozenset([CommandQueue, Biochemistry]), biochemistry_system, priority=70)
s.register_system(frozenset([Plant]), plant_system, priority=75)
s.register_system(frozenset([CommandQueue, State]), decision_system, priority=100)

def tick_stats(sim: Simulation):
    food_amount = len(sim.world.index.get_with(Eatable))
    creatures_amount = len(sim.world.index.get_with(Movable))

    print(f'creatures: {creatures_amount} | food: {food_amount}')

s.add_on_tick(tick_stats)

for _ in range(85):
    x = random.randint(0, s.world.width - 1)
    y = random.randint(0, s.world.height - 1)
    if not s.world.get_entity(x, y):
        make_plant(x, y, s.world)

for _ in range(50):
    x = random.randint(0, s.world.width // 5)
    y = random.randint(0, s.world.height // 5)
    if not s.world.get_entity(x, y):
        make_creature(x, y, s.world)

s.run()