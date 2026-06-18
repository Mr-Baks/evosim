from entity import * 
from world import World
from simulation import Simulation
import random
from commands import *
from event_bus import Event, EventBus
from systems import *


def make_creature(x, y, world: World):
    e = Entity().add_component(Movable()).add_component(Biochemistry()).add_component(Vision(3)).add_component(CommandQueue()).add_component(State()).add_component(Breedable(cooldown=0))
    world.place_entity(e, x, y)

def make_food(x, y, world: World, nutrition=20):
    e = Entity().add_component(Eatable(nutrition))
    world.place_entity(e, x, y)   

def make_plant(x, y, world: World):
    e = Entity().add_component(Plant(fructify_treshold=random.randint(70, 85)))
    world.place_entity(e, x, y)

s = Simulation(10, 10, (200, 30))

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

for x in range(s.world.width):
    for y in range(s.world.height):
        if x % 15 == 0 and y % 15 == 0:
            make_creature(x, y, s.world)
            make_creature(x - 1, y, s.world)

        if random.random() > 0.87 and not s.world.get_entity(x, y) and (x % 5 == 3 and y % 5 >= 3):
            make_plant(x, y, s.world)

s.run()