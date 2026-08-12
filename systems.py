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
        if not command:
            for c in queue.queue:
                if c.is_ready(e, world):
                    queue.running = command = c
                    c.status = CommandStatus.RUNNING
                    if c.target_state and state: 
                        state.states.add(c.target_state)
                    queue.queue.remove(c)
                    break
        if command: 
            command.execute(e, world)
        if len(queue.queue) > 25: print('LEAK')

def vision_system(entities: set[Entity], world: World):
    for e in entities:
        vision = e.get_component(Vision)
        vision.visibles = world.get_neighbours(e, radius=vision.radius)

def biochemistry_system(entities: set[Entity], world: World):
    for e in entities:
        bio: Biochemistry = e.get_component(Biochemistry)
        breedable = e.get_component(Breedable)
        queue = e.get_component(CommandQueue)
        genome: Genome = e.get_component(Genome)
        
        metabolism = genome.get_phenotype(GeneNames.METABOLISM)
        speed = genome.get_phenotype(GeneNames.SPEED)
        
        if not queue.running or not isinstance(queue.running, SleepCommand):
            bio.energy = max(bio.energy - (1 + metabolism) * (2 + speed) ** 2, 0)
            if bio.energy == 0:
                bio.health = max(bio.health - 1, 0)
        
        bio.hunger = max(bio.hunger - (2 + speed) ** 2 / 2, 0)

        if breedable:
            breedable.cooldown = max(breedable.cooldown - 1, 0)

        if bio.hunger == 0:
            bio.health = max(bio.health - 1, 0)

        if bio.health == 0:
            push_command(e, world, DeathCommand(emergency=100, corpse_nutrition=50))

        if bio.energy > 60 and bio.hunger > 60 and bio.health < 80:
            bio.health += 5 * (1 + metabolism)
            bio.energy -= 5
            bio.hunger -= 5

def plant_system(entities: set[Entity], world: World):
    for e in entities:
        plant: Plant = e.get_component(Plant)
        plant.energy = min(plant.energy + plant.energy_increase, 180)
        if plant.energy > plant.fructify_threshold:
            free_cells = world.get_free_cells_near(e)
            if free_cells:
                fruit = Entity().add_component(Eatable(nutrition=plant.fruit_nutrition)).add_component(Render(symbol='f', color=(140, 100, 50)))
                plant.energy -= plant.fructify_threshold
                world.place_entity(fruit, *random.choice(free_cells))

def eat_utility(entity: Entity, world: World) -> float:
    vision: Vision = entity.get_component(Vision)
    bio: Biochemistry = entity.get_component(Biochemistry)
    genome: Genome = entity.get_component(Genome)
    
    hunger_factor = 1 - (bio.hunger / 200)
    
    food_count = sum(1 for ve in vision.visibles if ve.has_component(Eatable))
    food_factor = max(0.6, min(food_count / 3, 1))
    
    genetic_drive = (genome.get_phenotype(GeneNames.HUNGER_DRIVE) + 1) / 2
    
    return hunger_factor * food_factor * genetic_drive

def sleep_utility(entity: Entity, world: World) -> float:
    bio: Biochemistry = entity.get_component(Biochemistry)
    genome: Genome = entity.get_component(Genome)
    
    energy_factor = 1 - (bio.energy / 200)
    genetic_drive = (genome.get_phenotype(GeneNames.SLEEP_DRIVE) + 1) / 2
    
    return energy_factor * genetic_drive

def mate_utility(entity: Entity, world: World) -> float:
    vision: Vision = entity.get_component(Vision)
    bio: Biochemistry = entity.get_component(Biochemistry)
    genome: Genome = entity.get_component(Genome)
    breedable: Breedable = entity.get_component(Breedable)

    energy_threshold = genome.get_phenotype(GeneNames.MATING_ENERGY_THRESHOLD)
    hunger_threshold = genome.get_phenotype(GeneNames.MATING_HUNGER_THRESHOLD)
    cooldown = breedable.cooldown

    if bio.energy < energy_threshold or bio.hunger < hunger_threshold or cooldown > 0:
        return -1
    
    biochemistry_factor = 1 - ((bio.hunger + bio.energy) / 400)
    
    partner_count = sum(1 for ve in vision.visibles if ve.has_component(Breedable))
    partner_factor = min(partner_count / 3, 1)
    
    genetic_drive = (genome.get_phenotype(GeneNames.MATING_DRIVE) + 1) / 2

    fertility = (genome.get_phenotype(GeneNames.FERTILITY) + 1) / 2
    if fertility < 0.2: fertility = 0
    
    return biochemistry_factor * partner_factor * genetic_drive * fertility

def wander_utility(entity: Entity, world: World) -> float:
    vision: Vision = entity.get_component(Vision)
    bio: Biochemistry = entity.get_component(Biochemistry)
    genome: Genome = entity.get_component(Genome)
    
    biochemistry_factor = 1 - ((bio.hunger + bio.energy) / 400)
    
    creatures_count = sum(1 for ve in vision.visibles if ve.has_component(Movable))
    creatures_factor = 1 - min(creatures_count / 5, 1)

    plant_count = sum(1 for ve in vision.visibles if ve.has_component(Plant))
    plant_factor = 1 - min(plant_count / 5, 1)
    
    genetic_drive = (genome.get_phenotype(GeneNames.EXPLORATION_DRIVE) + 1) / 2
    
    return biochemistry_factor * plant_factor * genetic_drive

def logging_system(entities: set[Entity], world: World):
    log = ''

    for i, e in enumerate(entities):
        queue: CommandQueue = e.get_component(CommandQueue)
        state: State = e.get_component(State)
        bio: Biochemistry = e.get_component(Biochemistry)

        uts = {
                    'eat': eat_utility(e, world),
                    'sleep': sleep_utility(e, world),
                    'mating': mate_utility(e, world),
                    'idle': wander_utility(e, world),
                }

        log += f'Entity {i} at {e.x}, {e.y}:\n'
        log += f'   Running command: {queue.running.target_state if queue.running else None} | queue\'s len: {len(queue.queue)}\n'
        log += f'   Current state: {state.current} | states: {state.states}\n'
        log += f'   Energy: {bio.energy} | hunger: {bio.hunger} | helth: {bio.health}\n'
        log += f'   Utilities: {uts}\n'

    with open('logs/last_tick.txt', 'w+') as l:
        l.write(log)

def decision_system(entities: set[Entity], world: World):
    for e in entities:
        state: State = e.get_component(State)
        vision: Vision = e.get_component(Vision)
        bio: Biochemistry = e.get_component(Biochemistry)

        utilities = {
            'eat': eat_utility(e, world),
            'sleep': sleep_utility(e, world),
            'mating': mate_utility(e, world),
            'idle': wander_utility(e, world),
        }

        action = max(utilities, key=utilities.get)
        if action in state.states: 
            continue
        elif action == 'eat':
            food_candidates = [ve for ve in vision.visibles if ve.has_component(Eatable)]
            if food_candidates:
                food_candidates.sort(key=lambda f: abs(e.x - f.x) + abs(e.y - f.y))
                for f in food_candidates:
                    free_cells = world.get_free_cells_near(f)
                    if free_cells and random.random() > 0.3:
                        tx, ty = free_cells[0]
                        push_command(e, world, 
                                     MoveToTargetCommand(x=tx, y=ty, emergency=15), 
                                     EatCommand(target_x=f.x, target_y=f.y, emergency=16, target_state=action),
                                     target_state=action
                                     )
                        break
                else:
                    push_command(e, world, WanderCommand(radius=6, target_state=action))
        elif action == 'sleep':
            if bio.hunger == 0:
                ticks_to_sleep = 1
            else:
                ticks_to_sleep = round((200 - bio.energy) / SleepCommand.energy_increase)
            push_command(e, world, SleepCommand(emergency=10, ticks_to_sleep=ticks_to_sleep, target_state=action))
        elif action == 'mating': 
            partners = [ve for ve in vision.visibles if ve.has_component(Breedable) and ve is not e]
            if partners:
                partners.sort(key=lambda p: abs(e.x - p.x) + abs(e.y - p.y))
                for p in partners:
                    free_cells = world.get_free_cells_near(p)
                    if free_cells:
                        tx, ty = free_cells[0]
                        push_command(e, world, 
                                     MoveToTargetCommand(x=tx, y=ty, emergency=1),
                                     MateCommand(partner=p, emergency=2),
                                     target_state=action
                                     )
                        break
        elif 'idle' not in state.states:
            push_command(e, world, WanderCommand(radius=8, target_state=action))

