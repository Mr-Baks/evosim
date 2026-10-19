from commands import CommandQueue, CommandStatus
from entity import *
from world import World
from commands import *
from traits import traits_for
import random


def command_system(entities: set[Entity], world: World):
    for e in entities:
        queue: CommandQueue = e.get_component(CommandQueue)
        state: State = e.get_component(State)
        command = queue.running
        if not command:
            for c in queue.queue:
                if c.is_ready(e, world):
                    queue.running = command = c
                    c.status = CommandStatus.RUNNING
                    if c.target_state and state: 
                        state.states.add(c.target_state)
                        state.current = c.target_state
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
        breedable: Breedable = e.get_component(Breedable)
        queue = e.get_component(CommandQueue)
        genome: Genome = e.get_component(Genome)
        traits = traits_for(genome)

        metabolism = traits.metabolism
        speed = traits.speed.metabolic
        fertility = traits.fertility
        regeneration_threshold = traits.regeneration_threshold
        regeneration_increase = traits.regeneration_increase
        senescence_shape = traits.senescence_shape
        wear_resistance = traits.wear_resistance.aging

        bio.age += 1 
        wear = min(1, bio.age / wear_resistance)
        bio.vitality = max(0, 1 - wear ** (senescence_shape))
        bio.max_health = bio.vitality * 100
        if breedable:
            breedable.fertility = fertility * min(1, bio.vitality * 2) * (1 - senescence_shape / 3)
        
        if not queue.running or not isinstance(queue.running, SleepCommand):
            bio.energy = max(bio.energy - metabolism * speed ** 2 * (2 - bio.vitality), 0)
            if bio.energy == 0:
                bio.health = max(bio.health - 1, 0)
        
        bio.hunger = max(bio.hunger - metabolism * speed ** 2 * (wear_resistance / 710), 0)

        if breedable:
            breedable.cooldown = max(breedable.cooldown - 1, 0)

        if bio.hunger == 0:
            bio.health = max(bio.health - 1, 0)

        if bio.energy > 60 and bio.hunger > 60 and bio.health < regeneration_threshold * bio.max_health:
            bio.health += regeneration_increase * metabolism * bio.vitality
            bio.energy -= regeneration_increase ** 2 * metabolism / 2
            bio.hunger -= regeneration_increase ** 2 * metabolism / 2

        bio.health = min(bio.health, bio.max_health)
        if bio.health <= 0:
            push_command(e, world, DeathCommand(emergency=100, corpse_nutrition=50))

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
    food_factor = max(0.01, min(food_count / 3, 1))
    
    genetic_drive = traits_for(genome).hunger_drive
    
    return hunger_factor * food_factor * genetic_drive

def sleep_utility(entity: Entity, world: World) -> float:
    bio: Biochemistry = entity.get_component(Biochemistry)
    genome: Genome = entity.get_component(Genome)
    
    energy_factor = 1 - (bio.energy / 200)
    genetic_drive = traits_for(genome).sleep_drive
    
    return energy_factor * genetic_drive

def mate_utility(entity: Entity, world: World) -> float:
    vision: Vision = entity.get_component(Vision)
    bio: Biochemistry = entity.get_component(Biochemistry)
    genome: Genome = entity.get_component(Genome)
    breedable: Breedable = entity.get_component(Breedable)

    if breedable is None:
        return -1

    traits = traits_for(genome)
    energy_threshold = traits.mating_energy_threshold
    hunger_threshold = traits.mating_hunger_threshold
    cooldown = breedable.cooldown

    if bio.energy < energy_threshold or bio.hunger < hunger_threshold or cooldown > 0:
        return -1
    
    biochemistry_factor = ((bio.hunger + bio.energy) / 400)
    
    partner_count = sum(1 for ve in vision.visibles if ve.has_component(Breedable))
    partner_factor = min(partner_count / 3, 1)
    
    genetic_drive = traits.mating_drive

    fertility = breedable.fertility
    if fertility < 0.2: fertility = 0
    
    return biochemistry_factor * partner_factor * genetic_drive * fertility

def wander_utility(entity: Entity, world: World) -> float:
    vision: Vision = entity.get_component(Vision)
    bio: Biochemistry = entity.get_component(Biochemistry)
    genome: Genome = entity.get_component(Genome)
    
    biochemistry_factor = min(1, max(0.2, 2 * (1 - (bio.hunger / 200))))
    
    creatures_count = sum(1 for ve in vision.visibles if ve.has_component(Movable))
    creatures_factor = min(1, max(creatures_count / 5, 0.01))

    plant_count = sum(1 for ve in vision.visibles if ve.has_component(Plant))
    plant_factor = 1 - min(plant_count / 5, 1)
    
    genetic_drive = traits_for(genome).exploration_drive
    
    return biochemistry_factor * plant_factor * genetic_drive * creatures_factor

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
        log += f'   Energy: {bio.energy:.2f} | hunger: {bio.hunger:.2f} | helth: {bio.health:.2f} | age: {bio.age:.2f} | vitality: {bio.vitality:.2f}\n'
        log += f'   Utilities: {uts}\n'

    with open('logs/last_tick.txt', 'w+') as l:
        l.write(log)

def decision_system(entities: set[Entity], world: World):
    for e in entities:
        state: State = e.get_component(State)
        vision: Vision = e.get_component(Vision)
        bio: Biochemistry = e.get_component(Biochemistry)
        genome: Genome = e.get_component(Genome)

        if not (bio and vision and genome):
            continue

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
                    free_cell = world.get_free_cell_near(f)
                    if free_cell and random.random() > 0.3:
                        tx, ty = free_cell
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
                    free_cell = world.get_free_cell_near(p)
                    if free_cell:
                        tx, ty = free_cell
                        push_command(e, world, 
                                     MoveToTargetCommand(x=tx, y=ty, emergency=1),
                                     MateCommand(partner=p, emergency=2),
                                     target_state=action
                                     )
                        break
        elif 'idle' not in state.states:
            push_command(e, world, WanderCommand(radius=8, target_state=action))

