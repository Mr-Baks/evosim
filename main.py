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

s = Simulation(10, 10, (50, 20))

s.world.event_bus.subscribe(EatEvent, on_eat)
s.world.event_bus.subscribe(SleepEvent, on_sleep)
s.world.event_bus.subscribe(MoveEvent, on_move)

s.register_system(frozenset([CommandQueue]), command_system, priority=50)
s.register_system(frozenset([Vision]), vision_system, priority=80)
s.register_system(frozenset([CommandQueue, Biochemistry]), biochemistry_system, priority=70)
s.register_system(frozenset([CommandQueue, State]), decision_system, priority=100)

make_creature(1, 1, s.world)
make_creature(1, 10, s.world)

for i in range(10):
    make_food(i * 2, i, s.world)

s.run()