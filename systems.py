from commands import CommandQueue, CommandStatus
from entity import *
from world import World
from commands import *
import random


def command_system(entities: set[Entity], world: World):
    for e in entities:
        queue = e.get_component(CommandQueue)
        state = e.get_component(State)
        command = queue.running
        if command:
            command.execute(e, world)
        else: 
            for c in queue.queue:
                if c.is_ready(e, world):
                    queue.running = c
                    c.status = CommandStatus.RUNNING
                    if c.target_state and state: 
                        state.states.add(c.target_state)
                    queue.queue.remove(c)
                    break

def vision_system(entities: set[Entity], world: World):
    for e in entities:
        vision = e.get_component(Vision)
        vision.visibles = world.get_neighbours(e, radius=vision.radius)

def biochemistry_system(entities: set[Entity], world: World):
    entities = world.index.get_with(Biochemistry, CommandQueue)
    for e in entities:
        bio: Biochemistry = e.get_component(Biochemistry)
        breedable = e.get_component(Breedable)
        queue = e.get_component(CommandQueue)
        
        if not queue.running or isinstance(queue.running, SleepCommand):
            bio.energy = max(bio.energy - 1, 0)
            if bio.energy == 0:
                bio.health = max(bio.health - 1, 0)
        
        bio.hunger = max(bio.hunger - 1, 0)

        if breedable:
            breedable.cooldown = max(breedable.cooldown - 1, 0)

        if bio.hunger == 0:
            bio.health = max(bio.health - 1, 0)

        if bio.health == 0:
            push_command(e, world, DeathCommand(emergency=100))

def plant_system(entities: set[Entity], world: World):
    for e in entities:
        plant: Plant = e.get_component(Plant)
        plant.energy = min(plant.energy + plant.energy_increase, 180)
        if plant.energy > plant.fructify_treshold:
            free_cells = world.get_cells_near(e)
            if free_cells:
                fruit = Entity().add_component(Eatable(nutrition=plant.fruit_nutrition))
                plant.energy -= plant.fructify_treshold
                world.place_entity(fruit, *random.choice(free_cells))

def decision_system(entities: set[Entity], world: World):
    for e in entities:
        queue: CommandQueue = e.get_component(CommandQueue)
        state: State = e.get_component(State)
        vision: Vision = e.get_component(Vision)
        bio: Biochemistry = e.get_component(Biochemistry)

        if not (bio and vision):
            continue

        if bio.hunger < 40 and 'seeking_food' not in state.states and 'eating' not in state.states:
            food_candidates = [ve for ve in vision.visibles if ve.has_component(Eatable)]
            if food_candidates:
                food_candidates.sort(key=lambda f: abs(e.x - f.x) + abs(e.y - f.y))
                for f in food_candidates:
                    free_cells = world.get_free_cells_near(f)
                    if free_cells:
                        tx, ty = free_cells[0]
                        push_command(e, world, MoveToTargetCommand(x=tx, y=ty, emergency=80, target_state='seeking_food'))
                        push_command(e, world, EatCommand(target_x=f.x, target_y=f.y, emergency=81, target_state='eating'))
                        break
                else:
                    push_command(e, world, WanderCommand(emergency=79, target_state='seeking_food'))
            else:
                push_command(e, world, WanderCommand(emergency=79, target_state='seeking_food'))

        elif bio.energy < 55 and 'sleeping' not in state.states:
            push_command(e, world, SleepCommand(ticks_to_sleep=2, emergency=20, target_state='sleeping'))

        elif bio.energy > 70 and bio.hunger > 70 and (not queue.running or queue.running.emergency == 0) and 'seeking_partner' not in state.states and 'breeding' not in state.states:
            partners = [ve for ve in vision.visibles if ve.has_component(Breedable) and ve is not e]
            if partners:
                partners.sort(key=lambda p: abs(e.x - p.x) + abs(e.y - p.y))
                for p in partners:
                    free_cells = world.get_free_cells_near(p)
                    if free_cells:
                        tx, ty = free_cells[0]
                        push_command(e, world, MoveToTargetCommand(x=tx, y=ty, emergency=15, target_state='seeking_partner'))
                        push_command(e, world, MateCommand(partner=p, emergency=16, target_state='breeding'))
                        break

        if not queue.running and 'wandering' not in state.states:
            push_command(e, world, WanderCommand(priority=-1, target_state='wandering'))