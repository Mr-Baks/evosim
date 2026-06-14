from commands import CommandQueue, CommandStatus
from entity import *
from world import World
from commands import *


def command_system(entities: set[Entity], world: World):
    for e in entities:
        queue = e.get_component(CommandQueue)
        command = queue.running
        if command:
            command.execute(e, world)
        else: 
            for c in queue.queue:
                if c.is_ready(e, world):
                    queue.running = c
                    c.status = CommandStatus.RUNNING
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
        queue = e.get_component(CommandQueue)
        
        if not queue.running or isinstance(queue.running, SleepCommand):
            bio.energy = max(bio.energy - 1, 0)
            if bio.energy == 0:
                bio.health = max(bio.health - 1, 0)
        
        bio.hunger = max(bio.hunger - 1, 0)

        if bio.hunger == 0:
            bio.health = max(bio.health - 1, 0)

        if bio.health == 0:
            push_command(e, world, DeathCommand(emergency=100))

def decision_system(entities: set[Entity], world: World):
    for e in entities:
        queue: CommandQueue = e.get_component(CommandQueue)
        vision: Vision = e.get_component(Vision)
        bio: Biochemistry = e.get_component(Biochemistry)

        if bio and vision:
            if bio.hunger < 40:
                food = []

                for ve in vision.visibles:
                    if ve.has_component(Eatable):
                        food.append(ve)

                if food:
                    food.sort(key=lambda f: abs(e.x - f.x) + abs(e.y - f.y))
                    for f in food:
                        free_cells = world.get_free_cells_near(f)
                        if free_cells: 
                            tx, ty = free_cells[0]
                            fx, fy = f.x, f.y
                            break
                    else: return # fallback if all food is unreachable
                    push_command(e, world, MoveToTargetCommand(x=tx, y=ty, emergency=80))
                    push_command(e, world, EatCommand(target_x=fx, target_y=fy, emergency=81))
                else: 
                    push_command(e, world, WanderCommand(emergency=79))
            elif bio.energy < 55: 
                push_command(e, world, SleepCommand(ticks_to_sleep=2, emergency=20))
        if not queue.running:
            push_command(e, world, WanderCommand(priority=-1))