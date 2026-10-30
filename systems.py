from commands import CommandQueue, CommandStatus
from config import BalanceConfig
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
        vision: Vision = e.get_component(Vision)
        vision.visibles = []
        vision.cache = {'creatures': [], 'partners': [], 'foods': [], 'plants': []}

        for ve in world.get_neighbours(e, radius=vision.radius, sort=False):
            vision.visibles.append(ve)
            components = ve.components
            if Movable in components:
                vision.cache['creatures'].append(ve)
            if Breedable in components:
                vision.cache['partners'].append(ve)
            if Eatable in components:
                vision.cache['foods'].append(ve)
            if Plant in components:
                vision.cache['plants'].append(ve)

def biochemistry_system(entities: set[Entity], world: World):
    for e in entities:
        bio: Biochemistry = e.get_component(Biochemistry)
        breedable: Breedable = e.get_component(Breedable)
        queue = e.get_component(CommandQueue)
        genome: Genome = e.get_component(Genome)
        vision: Vision = e.get_component(Vision)
        traits = traits_for(genome)

        if vision and vision.cache is not None and world.balance.crowd_radius <= vision.radius:
            r2 = world.balance.crowd_radius ** 2
            creatures_count = 0
            for ve in vision.cache['creatures']:
                if (ve.x - e.x) ** 2 + (ve.y - e.y) ** 2 <= r2:
                    creatures_count += 1
        else:
            creatures_count = world.count_components_near(e.x, e.y, (Movable,), radius=world.balance.crowd_radius, exclude=e)[0]

        if creatures_count >= world.balance.crowd_count_threshold:
            normalized = (creatures_count - world.balance.crowd_count_threshold) / (world.balance.max_crowd_count - world.balance.crowd_count_threshold)
            crowd_penalty = min(normalized, 1.0) * world.balance.max_crowd_penalty_factor
        else:
            crowd_penalty = 0

        bio.age += 1
        bio.vitality = traits.vitality(bio.age)
        bio.max_health = traits.max_health(bio.vitality)
        if breedable:
            breedable.fertility = traits.effective_fertility(bio.vitality) * (1 - crowd_penalty)

        decay = world.balance.health_decay

        if not queue.running or not isinstance(queue.running, SleepCommand):
            bio.energy = max(0, bio.energy - traits.energy_drain(bio.vitality))
            if bio.energy == 0:
                bio.health = max(bio.health - decay, 0)

        bio.hunger = max(bio.hunger - traits.hunger_drain(), 0)

        if breedable:
            breedable.cooldown = max(breedable.cooldown - 1, 0)

        if bio.hunger == 0:
            bio.health = max(bio.health - decay, 0)

        if (bio.energy > world.balance.regeneration_energy_min and bio.hunger > world.balance.regeneration_hunger_min and bio.health < traits.regeneration_threshold * bio.max_health):
            cost = traits.regeneration_cost()
            bio.health += traits.regeneration_gain(bio.vitality)
            bio.energy -= cost
            bio.hunger -= cost

        bio.health = min(bio.health, bio.max_health)
        if bio.health <= 0:
            push_command(e, world, DeathCommand(emergency=100, corpse_nutrition=world.balance.corpse_nutrition))

def plant_system(entities: set[Entity], world: World):
    for e in entities:
        plant: Plant = e.get_component(Plant)
        plant.energy = min(plant.energy + plant.energy_increase, world.balance.plant_energy_cap)
        if plant.energy > plant.fructify_threshold:
            free_cells = world.get_free_cells_near(e)
            if free_cells:
                fruit = Entity().add_component(Eatable(nutrition=plant.fruit_nutrition)).add_component(Render(symbol='f', color=(140, 100, 50)))
                plant.energy -= plant.fructify_threshold
                world.place_entity(fruit, *random.choice(free_cells))

def eat_utility(bio: Biochemistry, genome: Genome, food_count: int, balance: BalanceConfig) -> float:
    hunger_factor = 1 - (bio.hunger / balance.hunger_scale)

    food_factor = max(0.01, min(food_count / balance.food_saturation, 1))

    genetic_drive = traits_for(genome).hunger_drive

    return hunger_factor * food_factor * genetic_drive

def sleep_utility(bio: Biochemistry, genome: Genome, balance: BalanceConfig) -> float:
    energy_factor = 1 - (bio.energy / balance.energy_scale)
    genetic_drive = traits_for(genome).sleep_drive

    return energy_factor * genetic_drive

def mate_utility(bio: Biochemistry, genome: Genome, breedable: Breedable, partner_count: int, balance: BalanceConfig) -> float:
    if breedable is None:
        return -1

    traits = traits_for(genome)
    energy_threshold = traits.mating_energy_threshold
    hunger_threshold = traits.mating_hunger_threshold
    cooldown = breedable.cooldown

    if bio.energy < energy_threshold or bio.hunger < hunger_threshold or cooldown > 0:
        return -1

    biochemistry_factor = ((bio.hunger + bio.energy) / (balance.hunger_scale + balance.energy_scale))

    partner_factor = min(partner_count / balance.partner_saturation, 1)

    genetic_drive = traits.mating_drive

    fertility = breedable.fertility
    if fertility < balance.fertility_min: fertility = 0

    return biochemistry_factor * partner_factor * genetic_drive * fertility

def wander_utility(bio: Biochemistry, genome: Genome, creatures_count: int, plant_count: int, balance: BalanceConfig) -> float:
    traits = traits_for(genome)

    starvation = min(1.0, max(0.0, 1 - bio.hunger / balance.hunger_scale))
    crowd_density = min(1.0, creatures_count / balance.creature_saturation)
    plant_absence = 1 - min(1.0, plant_count / balance.plant_saturation)
    crowd_aversion = max(0.0, -traits.crowd_preference)
    crowd_affinity = max(0.0, traits.crowd_preference)
    plant_appetence = max(0.0, traits.plant_appetence)

    utility = (0.10 * traits.exploration_drive + 0.15 * crowd_density * (crowd_aversion - crowd_affinity) + 0.05 * starvation * plant_absence * plant_appetence)
    
    return max(0, utility)

def visible_counts(vision: Vision) -> tuple[int, int, int, int]:
    if vision.cache is not None:
        food = len(vision.cache['foods'])
        creatures = len(vision.cache['creatures'])
        partners = len(vision.cache['partners'])
        plants = len(vision.cache['plants'])

        return food, creatures, partners, plants

    food = creatures = partners = plants = 0
    for ve in vision.visibles:
        if ve.has_component(Eatable):
            food += 1
        if ve.has_component(Movable):
            creatures += 1
        if ve.has_component(Breedable):
            partners += 1
        if ve.has_component(Plant):
            plants += 1

    return food, creatures, partners, plants

def logging_system(entities: set[Entity], world: World):
    log = ''

    for i, e in enumerate(entities):
        state: State = e.get_component(State)
        vision: Vision = e.get_component(Vision)
        bio: Biochemistry = e.get_component(Biochemistry)
        genome: Genome = e.get_component(Genome)
        breedable: Breedable = e.get_component(Breedable)
        queue: CommandQueue = e.get_component(CommandQueue)

        food_count, creatures_count, partner_count, plant_count = visible_counts(vision)

        uts = {
            'eat': eat_utility(bio, genome, food_count, world.balance),
            'sleep': sleep_utility(bio, genome, world.balance),
            'mating': mate_utility(bio, genome, breedable, partner_count, world.balance),
            'idle': wander_utility(bio, genome, creatures_count, plant_count, world.balance),
        }

        log += f'Entity {i} at {e.x}, {e.y}:\n'
        log += f'   Running command: {queue.running.target_state if queue.running else None} | queue\'s len: {len(queue.queue)}\n'
        log += f'   Current state: {state.current} | states: {state.states}\n'
        log += f'   Energy: {bio.energy:.2f} | hunger: {bio.hunger:.2f} | health: {bio.health:.2f} | age: {bio.age:.2f} | vitality: {bio.vitality:.2f}\n'
        log += f'   Utilities: {uts}\n'

    with open('logs/last_tick.txt', 'w+') as l:
        l.write(log)

def decision_system(entities: set[Entity], world: World):
    for e in entities:
        state: State = e.get_component(State)
        vision: Vision = e.get_component(Vision)
        bio: Biochemistry = e.get_component(Biochemistry)
        genome: Genome = e.get_component(Genome)
        breedable: Breedable = e.get_component(Breedable)

        if not (bio and vision and genome):
            continue

        food_count, creatures_count, partner_count, plant_count = visible_counts(vision)

        utilities = {
            'eat': eat_utility(bio, genome, food_count, world.balance),
            'sleep': sleep_utility(bio, genome, world.balance),
            'mating': mate_utility(bio, genome, breedable, partner_count, world.balance),
            'idle': wander_utility(bio, genome, creatures_count, plant_count, world.balance),
        }

        action = max(utilities, key=utilities.get)
        if action in state.states: 
            continue
        elif action == 'eat':
            if vision.cache is not None:
                food_candidates = list(vision.cache['foods'])
            else:
                food_candidates = [ve for ve in vision.visibles if ve.has_component(Eatable)]
            if food_candidates:
                food_candidates.sort(key=lambda f: (abs(e.x - f.x) + abs(e.y - f.y), f.eid))
                for f in food_candidates:
                    free_cell = world.get_free_cell_near(f)
                    if free_cell and random.random() > world.balance.eat_reconsider_chance:
                        tx, ty = free_cell
                        push_command(e, world, 
                                     MoveToTargetCommand(x=tx, y=ty, emergency=15), 
                                     EatCommand(target_x=f.x, target_y=f.y, emergency=16, target_state=action),
                                     target_state=action
                                     )
                        break
                else:
                    push_command(e, world, WanderCommand(radius=world.balance.wander_fallback_radius, target_state=action))
        elif action == 'sleep':
            if bio.hunger == 0:
                ticks_to_sleep = 1
            else:
                ticks_to_sleep = round((world.balance.sleep_target_energy - bio.energy) / world.balance.sleep_energy_increase)
            push_command(e, world, SleepCommand(emergency=10, ticks_to_sleep=ticks_to_sleep, energy_increase=world.balance.sleep_energy_increase, target_state=action))
        elif action == 'mating': 
            if vision.cache is not None:
                partners = list(vision.cache['partners'])
            else:
                partners = [ve for ve in vision.visibles if ve.has_component(Breedable) and ve is not e]
            if partners:
                partners.sort(key=lambda p: (abs(e.x - p.x) + abs(e.y - p.y), p.eid))
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
            push_command(e, world, WanderCommand(radius=vision.radius, target_state=action))
