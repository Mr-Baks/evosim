import pytest

from config import BalanceConfig
from systems import *
from commands import *
from entity import *
from world import World
from event_bus import EventBus
from genome import Genome, GeneNames
from traits import traits_for
from tests.helpers import (
    default_genes,
    make_decision_random_deterministic,
)


def wander_utility_of(entity) -> float:
    """Call ``wander_utility`` with the counts its signature expects."""
    bio = entity.get_component(Biochemistry)
    genome = entity.get_component(Genome)
    _, creatures, _, plants = visible_counts(entity.get_component(Vision))
    return wander_utility(bio, genome, creatures, plants, BalanceConfig())


class TestCommandSystem:
    def test_command_system_runs_running_command(self):
        e = Entity().add_component(CommandQueue()).add_component(State()).add_component(Movable()).add_component(Biochemistry())
        w = World(10, 10)
        w.place_entity(e, 5, 5)
        
        cmd = MoveToTargetCommand(x=6, y=5)
        cmd.status = CommandStatus.RUNNING
        queue = e.get_component(CommandQueue)
        queue.running = cmd
        
        command_system({e}, w)
        
        assert e.x == 6

    def test_command_system_starts_next_command(self):
        e = Entity().add_component(CommandQueue()).add_component(State()).add_component(Movable()).add_component(Biochemistry())
        w = World(10, 10)
        w.place_entity(e, 5, 5)

        # Distant target so cmd1 keeps running across ticks (speed = 1 cell/tick)
        cmd1 = MoveToTargetCommand(x=8, y=5)
        cmd2 = MoveToTargetCommand(x=9, y=5)
        queue = e.get_component(CommandQueue)
        queue.queue = [cmd1, cmd2]

        command_system({e}, w)

        assert queue.running is cmd1
        assert cmd1.status == CommandStatus.RUNNING
        assert cmd2 in queue.queue

    def test_command_system_skips_not_ready(self):
        e = Entity().add_component(CommandQueue()).add_component(State()).add_component(Movable()).add_component(Biochemistry())
        w = World(10, 10)
        w.place_entity(e, 5, 5)

        cmd1 = EatCommand(target_x=9, target_y=9)
        # Distant target so cmd2 keeps running across ticks (speed = 1 cell/tick)
        cmd2 = MoveToTargetCommand(x=8, y=5)
        queue = e.get_component(CommandQueue)
        queue.queue = [cmd1, cmd2]

        command_system({e}, w)

        assert queue.running is cmd2
        assert cmd1 in queue.queue


class TestVisionSystem:
    def test_vision_system_populates_visibles(self):
        e = Entity().add_component(Vision(radius=2)).add_component(Movable())
        w = World(10, 10)
        w.place_entity(e, 5, 5)
        
        target = Entity().add_component(Movable())
        w.place_entity(target, 6, 6)
        
        vision_system({e}, w)
        
        vision = e.get_component(Vision)
        assert target in vision.visibles

    def test_vision_system_excludes_self(self):
        e = Entity().add_component(Vision(radius=2)).add_component(Movable())
        w = World(10, 10)
        w.place_entity(e, 5, 5)
        
        vision_system({e}, w)
        
        assert e not in e.get_component(Vision).visibles

    def test_vision_system_populates_category_cache_without_duplicates(self):
        e = Entity().add_component(Vision(radius=3)).add_component(Movable())
        w = World(10, 10)
        w.place_entity(e, 5, 5)

        creature = Entity().add_component(Movable()).add_component(Breedable())
        fruit = Entity().add_component(Eatable(nutrition=10))
        plant = Entity().add_component(Plant())
        w.place_entity(creature, 6, 5)
        w.place_entity(fruit, 5, 6)
        w.place_entity(plant, 4, 5)

        vision_system({e}, w)

        vision = e.get_component(Vision)
        assert len(vision.visibles) == 3
        assert set(vision.visibles) == {creature, fruit, plant}
        assert vision.cache['creatures'] == [creature]
        assert vision.cache['partners'] == [creature]
        assert vision.cache['foods'] == [fruit]
        assert vision.cache['plants'] == [plant]
        assert visible_counts(vision) == (1, 1, 1, 1)

    def test_vision_system_resets_previous_visibles(self):
        e = Entity().add_component(Vision(radius=2)).add_component(Movable())
        w = World(10, 10)
        w.place_entity(e, 5, 5)
        target = Entity().add_component(Movable())
        w.place_entity(target, 6, 5)

        vision_system({e}, w)
        vision_system({e}, w)

        assert e.get_component(Vision).visibles == [target]


class TestBiochemistrySystem:
    # Drains are gene-derived: metabolism * speed**2 scaled, then weighted by
    # (2 - vitality) for energy and (wear_resistance / 710) for hunger.
    # The assertions below check properties (who drains more), not a copy of
    # the formula, so they survive balance changes.

    def test_biochemistry_system_energy_drain_grows_as_vitality_falls(self):
        w = World(10, 10)
        young = Entity().add_component(Biochemistry(energy=100, age=0)).add_component(CommandQueue()).add_component(Movable()).add_component(default_genes())
        old = Entity().add_component(Biochemistry(energy=100, age=650)).add_component(CommandQueue()).add_component(Movable()).add_component(default_genes())
        w.place_entity(young, 4, 5)
        w.place_entity(old, 6, 5)

        biochemistry_system({young, old}, w)

        young_drain = 100 - young.get_component(Biochemistry).energy
        old_drain = 100 - old.get_component(Biochemistry).energy
        assert young_drain > 0
        assert old_drain > young_drain

    def test_biochemistry_system_energy_zero_health_decay(self):
        e = Entity().add_component(Biochemistry(energy=0, health=100)).add_component(CommandQueue()).add_component(Movable()).add_component(default_genes())
        w = World(10, 10)
        w.place_entity(e, 5, 5)

        biochemistry_system({e}, w)

        bio = e.get_component(Biochemistry)
        assert bio.health == 99

    def test_biochemistry_system_hunger_drain_scales_with_lifespan(self):
        w = World(10, 10)
        short = Entity().add_component(Biochemistry(hunger=100)).add_component(CommandQueue()).add_component(Movable()).add_component(default_genes(**{GeneNames.WEAR_RESISTANCE: -1.0}))
        long = Entity().add_component(Biochemistry(hunger=100)).add_component(CommandQueue()).add_component(Movable()).add_component(default_genes(**{GeneNames.WEAR_RESISTANCE: 1.0}))
        w.place_entity(short, 4, 5)
        w.place_entity(long, 6, 5)

        biochemistry_system({short, long}, w)

        short_drain = 100 - short.get_component(Biochemistry).hunger
        long_drain = 100 - long.get_component(Biochemistry).hunger
        assert short_drain > 0
        assert long_drain > short_drain

    def test_biochemistry_system_hunger_zero_health_decay(self):
        e = Entity().add_component(Biochemistry(hunger=0, health=100)).add_component(CommandQueue()).add_component(Movable()).add_component(default_genes())
        w = World(10, 10)
        w.place_entity(e, 5, 5)

        biochemistry_system({e}, w)

        bio = e.get_component(Biochemistry)
        assert bio.health == 99

    def test_biochemistry_system_health_zero_death_command(self):
        e = Entity().add_component(Biochemistry(health=0)).add_component(CommandQueue()).add_component(Movable()).add_component(default_genes())
        w = World(10, 10)
        w.place_entity(e, 5, 5)

        biochemistry_system({e}, w)

        queue = e.get_component(CommandQueue)
        assert len(queue.queue) == 1
        assert isinstance(queue.queue[0], DeathCommand)
        assert queue.queue[0].emergency == 100

    def test_biochemistry_system_breedable_cooldown(self):
        e = Entity().add_component(Biochemistry()).add_component(CommandQueue()).add_component(Breedable(cooldown=5)).add_component(Movable()).add_component(default_genes())
        w = World(10, 10)
        w.place_entity(e, 5, 5)

        biochemistry_system({e}, w)

        breedable = e.get_component(Breedable)
        assert breedable.cooldown == 4

    def test_biochemistry_system_sleeping_no_energy_decay(self):
        e = Entity().add_component(Biochemistry(energy=100)).add_component(CommandQueue()).add_component(Movable()).add_component(default_genes())
        w = World(10, 10)
        w.place_entity(e, 5, 5)
        
        # Register the entity in the cache
        w.index.register_system(frozenset([Biochemistry, CommandQueue]))
        
        cmd = SleepCommand()
        cmd.status = CommandStatus.RUNNING
        queue = e.get_component(CommandQueue)
        queue.running = cmd
        
        biochemistry_system({e}, w)
        
        bio = e.get_component(Biochemistry)
        assert bio.energy == 100

    def test_biochemistry_reuses_vision_cache_for_crowd_count(self, monkeypatch):
        e = (Entity()
             .add_component(Biochemistry())
             .add_component(CommandQueue())
             .add_component(Breedable())
             .add_component(Movable())
             .add_component(Vision(radius=10))
             .add_component(default_genes()))
        w = World(20, 20)
        w.place_entity(e, 10, 10)
        for x, y in [(12, 10), (13, 10), (14, 10), (11, 12)]:
            w.place_entity(Entity().add_component(Movable()), x, y)

        vision_system({e}, w)

        def unexpected(*args, **kwargs):
            raise AssertionError('crowd count should use Vision.cache')

        monkeypatch.setattr(w, 'count_components_near', unexpected)
        biochemistry_system({e}, w)

        bio = e.get_component(Biochemistry)
        balance = w.balance
        normalized = (4 - balance.crowd_count_threshold) / (balance.max_crowd_count - balance.crowd_count_threshold)
        crowd_penalty = min(normalized, 1.0) * balance.max_crowd_penalty_factor
        expected = traits_for(e.get_component(Genome)).effective_fertility(bio.vitality) * (1 - crowd_penalty)
        assert e.get_component(Breedable).fertility == pytest.approx(expected)

    def test_biochemistry_falls_back_when_crowd_radius_exceeds_vision(self):
        e = (Entity()
             .add_component(Biochemistry())
             .add_component(CommandQueue())
             .add_component(Breedable())
             .add_component(Movable())
             .add_component(Vision(radius=1))
             .add_component(default_genes()))
        w = World(20, 20)
        w.place_entity(e, 10, 10)
        for x, y in [(13, 10), (12, 12), (10, 14), (7, 10)]:
            w.place_entity(Entity().add_component(Movable()), x, y)

        vision_system({e}, w)
        assert e.get_component(Vision).cache['creatures'] == []

        biochemistry_system({e}, w)

        bio = e.get_component(Biochemistry)
        balance = w.balance
        normalized = (4 - balance.crowd_count_threshold) / (balance.max_crowd_count - balance.crowd_count_threshold)
        crowd_penalty = min(normalized, 1.0) * balance.max_crowd_penalty_factor
        expected = traits_for(e.get_component(Genome)).effective_fertility(bio.vitality) * (1 - crowd_penalty)
        assert e.get_component(Breedable).fertility == pytest.approx(expected)


class TestPlantSystem:
    def test_plant_system_energy_increase(self):
        e = Entity().add_component(Plant(energy=10, energy_increase=5))
        w = World(10, 10)
        w.place_entity(e, 5, 5)
        
        plant_system({e}, w)
        
        plant = e.get_component(Plant)
        assert plant.energy == 15

    def test_plant_system_energy_capped(self):
        e = Entity().add_component(Plant(energy=175, energy_increase=10))
        w = World(10, 10)
        w.place_entity(e, 5, 5)
        
        plant_system({e}, w)
        
        plant = e.get_component(Plant)
        # Energy increases to 185, capped to 150, then fructify subtracts 80 -> 70
        assert plant.energy == 70

    def test_plant_system_fructify(self):
        e = Entity().add_component(Plant(energy=90, energy_increase=0, fructify_threshold=80, fruit_nutrition=25))
        w = World(10, 10)
        w.place_entity(e, 5, 5)
        
        plant_system({e}, w)
        
        plant = e.get_component(Plant)
        assert plant.energy == 10
        
        fruits = w.index.get_with(Eatable)
        assert len(fruits) == 1
        fruit = list(fruits)[0]
        assert fruit.get_component(Eatable).nutrition == 25

    def test_plant_system_fructify_no_space(self):
        e = Entity().add_component(Plant(energy=90, energy_increase=0, fructify_threshold=80, fruit_nutrition=25))
        w = World(3, 3)
        w.place_entity(e, 1, 1)
        
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                if dx == 0 and dy == 0:
                    continue
                ent = Entity().add_component(Movable())
                w.place_entity(ent, 1+dx, 1+dy)
        
        plant_system({e}, w)
        
        plant = e.get_component(Plant)
        assert plant.energy == 90


class TestDecisionSystem:
    def _subscribe_handlers(self, w):
        w.event_bus.subscribe(EatEvent, on_eat)
        w.event_bus.subscribe(SleepEvent, on_sleep)
        w.event_bus.subscribe(MoveEvent, on_move)

    def test_decision_system_hungry_seeks_food(self, monkeypatch):
        # Strong hunger drive so 'eat' utility beats 'idle'
        e = Entity().add_component(Biochemistry(hunger=30, energy=100)).add_component(CommandQueue()).add_component(State()).add_component(Vision(radius=5)).add_component(Movable()).add_component(default_genes(hunger_drive=1.0, exploration_drive=0.0))
        w = World(10, 10)
        self._subscribe_handlers(w)
        w.place_entity(e, 5, 5)

        food = Entity().add_component(Eatable(nutrition=20)).add_component(Movable())
        w.place_entity(food, 6, 6)

        make_decision_random_deterministic(monkeypatch)

        # Interpretation cycle until the intended command completes
        for _ in range(15):
            vision_system({e}, w)
            decision_system({e}, w)
            command_system({e}, w)
            w.event_bus.dispatch()
            if w.get_entity(6, 6) is None:
                break

        bio = e.get_component(Biochemistry)
        # Food was eaten (gone from its cell) and hunger was restored
        assert w.get_entity(6, 6) is None
        assert bio.hunger > 30

    def test_decision_system_hungry_no_food_wanders(self):
        # No food in sight and nothing else to do: 'idle' must win so the
        # creature wanders instead of freezing. Sleep is switched off and
        # exploration drive maximised so the choice is unambiguous.
        e = Entity().add_component(Biochemistry(hunger=30, energy=100)).add_component(CommandQueue()).add_component(State()).add_component(Vision(radius=1)).add_component(Movable()).add_component(default_genes(exploration_drive=1.0, sleep_drive=-1.0))
        w = World(10, 10)
        self._subscribe_handlers(w)
        w.place_entity(e, 5, 5)

        vision_system({e}, w)
        decision_system({e}, w)
        command_system({e}, w)

        # The decided action is 'idle': WanderCommand executes a first move step
        assert (e.x, e.y) != (5, 5)

    def test_decision_system_low_energy_sleeps(self):
        # Strong sleep drive so 'sleep' utility beats 'idle'
        e = Entity().add_component(Biochemistry(hunger=100, energy=30)).add_component(CommandQueue()).add_component(State()).add_component(Vision(radius=5)).add_component(Movable()).add_component(default_genes(sleep_drive=0.5))
        w = World(10, 10)
        self._subscribe_handlers(w)
        w.place_entity(e, 5, 5)

        vision_system({e}, w)
        decision_system({e}, w)
        command_system({e}, w)

        queue = e.get_component(CommandQueue)
        assert queue.running is not None
        assert isinstance(queue.running, SleepCommand)

    def test_decision_system_ready_to_breed(self):
        # One partner is not enough to make 'mating' top the 'idle' utility,
        # so place a group of 3 partners within vision, and tune e1's genes
        # for a strong mating drive and weak exploration drive.
        e1 = Entity().add_component(Biochemistry(hunger=80, energy=80)).add_component(CommandQueue()).add_component(State()).add_component(Vision(radius=5)).add_component(Movable()).add_component(Breedable(cooldown=0)).add_component(Render()).add_component(default_genes(mating_drive=1.0, fertility=1.0, exploration_drive=0.0))
        e2 = Entity().add_component(Biochemistry(hunger=80, energy=80)).add_component(Breedable(cooldown=0)).add_component(Movable()).add_component(Render()).add_component(default_genes())
        e3 = Entity().add_component(Biochemistry()).add_component(Breedable(cooldown=0)).add_component(Movable()).add_component(Render()).add_component(default_genes())
        e4 = Entity().add_component(Biochemistry()).add_component(Breedable(cooldown=0)).add_component(Movable()).add_component(Render()).add_component(default_genes())
        w = World(10, 10)
        self._subscribe_handlers(w)
        w.place_entity(e1, 5, 5)
        w.place_entity(e2, 6, 5)
        w.place_entity(e3, 7, 5)
        w.place_entity(e4, 8, 5)

        assert len(w.index.get_with(Movable)) == 4

        # Cooldown is derived from the parent's wear_resistance gene.
        expected_cooldown = 100 + traits_for(e1.get_component(Genome)).wear_resistance.cooldown

        # Interpretation cycle until the mating command completes
        for _ in range(15):
            vision_system({e1}, w)
            decision_system({e1}, w)
            command_system({e1}, w)
            w.event_bus.dispatch()
            if e2.get_component(Breedable).cooldown > 0:
                break

        # Mating happened: both parents are cooled down and a child was born
        assert e1.get_component(Breedable).cooldown == pytest.approx(expected_cooldown)
        assert e2.get_component(Breedable).cooldown == pytest.approx(expected_cooldown)
        assert len(w.index.get_with(Movable)) == 5

    def test_decision_system_wanders_when_idle(self):
        # Idle exploration is the fallback: eat/mate are unattractive (no food,
        # no partner) and sleep is switched off.
        e = Entity().add_component(Biochemistry(hunger=100, energy=100)).add_component(CommandQueue()).add_component(State()).add_component(Vision(radius=5)).add_component(Movable()).add_component(default_genes(exploration_drive=1.0, sleep_drive=-1.0))
        w = World(10, 10)
        self._subscribe_handlers(w)
        w.place_entity(e, 5, 5)

        vision_system({e}, w)
        decision_system({e}, w)
        command_system({e}, w)

        # The decided action is 'idle': WanderCommand executes a first move step
        assert (e.x, e.y) != (5, 5)

    def test_wander_utility_grows_with_crowding(self):
        # Birth-rate control: a crowded creature should be keener to wander
        # (and thus disperse) than an isolated one.
        lonely = Entity().add_component(Biochemistry(hunger=50, energy=100)).add_component(Vision(radius=5)).add_component(Movable()).add_component(default_genes())
        crowded = Entity().add_component(Biochemistry(hunger=50, energy=100)).add_component(Vision(radius=5)).add_component(Movable()).add_component(default_genes())
        w = World(10, 10)
        w.place_entity(lonely, 9, 9)
        w.place_entity(crowded, 1, 1)
        for (x, y) in [(1, 2), (2, 1), (2, 2), (1, 0), (0, 1)]:
            w.place_entity(Entity().add_component(Movable()), x, y)

        vision_system({lonely, crowded}, w)

        assert wander_utility_of(crowded) > wander_utility_of(lonely)

    def test_wander_utility_drops_with_crowding_for_crowd_lover(self):
        # CROWD_PREFERENCE is signed: a positive value means affinity, so a
        # crowd lover is less eager to leave a crowd than an isolated one.
        lonely = Entity().add_component(Biochemistry(hunger=50, energy=100)).add_component(Vision(radius=5)).add_component(Movable()).add_component(default_genes(crowd_preference=1.0))
        crowded = Entity().add_component(Biochemistry(hunger=50, energy=100)).add_component(Vision(radius=5)).add_component(Movable()).add_component(default_genes(crowd_preference=1.0))
        w = World(10, 10)
        w.place_entity(lonely, 9, 9)
        w.place_entity(crowded, 1, 1)
        for (x, y) in [(1, 2), (2, 1), (2, 2), (1, 0), (0, 1)]:
            w.place_entity(Entity().add_component(Movable()), x, y)

        vision_system({lonely, crowded}, w)

        assert wander_utility_of(crowded) < wander_utility_of(lonely)

    def test_wander_utility_grows_when_starving(self):
        # hunger is satiety: 0 = starving, 200 = full. A starving creature
        # should be more eager to wander in search of food.
        fed = Entity().add_component(Biochemistry(hunger=190, energy=100)).add_component(Vision(radius=5)).add_component(Movable()).add_component(default_genes())
        starving = Entity().add_component(Biochemistry(hunger=0, energy=100)).add_component(Vision(radius=5)).add_component(Movable()).add_component(default_genes())

        assert wander_utility_of(starving) > wander_utility_of(fed)

    def test_wander_utility_drops_near_plants_when_hungry(self):
        # Plant cover should anchor a hungry creature instead of making it
        # wander away: plant_appetence rewards staying where plants are.
        no_plants = Entity().add_component(Biochemistry(hunger=0, energy=100)).add_component(Vision(radius=5)).add_component(Movable()).add_component(default_genes(plant_appetence=1.0))
        near_plants = Entity().add_component(Biochemistry(hunger=0, energy=100)).add_component(Vision(radius=5)).add_component(Movable()).add_component(default_genes(plant_appetence=1.0))
        w = World(10, 10)
        w.place_entity(no_plants, 9, 9)
        w.place_entity(near_plants, 1, 1)
        for (x, y) in [(1, 2), (2, 1), (2, 2), (1, 0), (0, 1)]:
            w.place_entity(Entity().add_component(Plant()), x, y)

        vision_system({no_plants, near_plants}, w)

        assert wander_utility_of(near_plants) < wander_utility_of(no_plants)

    def test_decision_system_skips_without_bio_or_vision(self):
        e = Entity().add_component(CommandQueue()).add_component(State()).add_component(Movable())
        w = World(10, 10)
        self._subscribe_handlers(w)
        w.place_entity(e, 5, 5)

        decision_system({e}, w)

        queue = e.get_component(CommandQueue)
        assert queue.running is None


class TestSystemsIntegration:
    def test_full_tick_cycle(self):
        e = Entity().add_component(Biochemistry(energy=100, hunger=100, health=100)).add_component(CommandQueue()).add_component(State()).add_component(Vision(radius=5)).add_component(Movable()).add_component(Breedable(cooldown=0)).add_component(default_genes(sleep_drive=-1.0))
        w = World(20, 20)
        w.place_entity(e, 10, 10)

        food = Entity().add_component(Eatable(nutrition=20)).add_component(Movable())
        w.place_entity(food, 11, 11)

        vision_system({e}, w)
        decision_system({e}, w)
        command_system({e}, w)
        biochemistry_system({e}, w)
        w.event_bus.dispatch()

        bio = e.get_component(Biochemistry)
        # Sleep is switched off (sleep_drive=-1) so the creature stays awake:
        # energy decays from metabolism/ageing and, if it moved this tick, from
        # MoveEvent; it never rises on an awake tick.
        assert 0 <= bio.energy < 100
        assert bio.age == 1
        assert bio.max_health == pytest.approx(bio.vitality * 100)
        assert bio.health <= bio.max_health + 1e-9
        assert len(e.get_component(CommandQueue).queue) >= 0

    def test_eat_then_energy_increase(self, monkeypatch):
        # Strong hunger drive so 'eat' utility beats 'idle'
        e = Entity().add_component(Biochemistry(energy=50, hunger=30)).add_component(CommandQueue()).add_component(State()).add_component(Vision(radius=5)).add_component(Movable()).add_component(default_genes(hunger_drive=1.0, exploration_drive=0.0))
        w = World(10, 10)
        w.event_bus.subscribe(EatEvent, on_eat)
        w.event_bus.subscribe(SleepEvent, on_sleep)
        w.event_bus.subscribe(MoveEvent, on_move)
        w.place_entity(e, 5, 5)

        food = Entity().add_component(Eatable(nutrition=25)).add_component(Movable())
        w.place_entity(food, 5, 6)

        make_decision_random_deterministic(monkeypatch)

        # Run full cycles until hunger is restored by eating
        for _ in range(15):
            vision_system({e}, w)
            decision_system({e}, w)
            command_system({e}, w)
            w.event_bus.dispatch()
            biochemistry_system({e}, w)
            if e.get_component(Biochemistry).hunger > 30:
                break

        bio = e.get_component(Biochemistry)
        assert bio.hunger > 30


class TestVisibleCounts:
    def test_creature_counts_as_creature_and_partner(self):
        # A creature has both Movable and Breedable, so it must be counted in
        # both categories (an elif chain would drop it from partner_count and
        # silently disable mating).
        creature = Entity().add_component(Movable()).add_component(Breedable())
        fruit = Entity().add_component(Eatable(nutrition=10))
        plant = Entity().add_component(Plant())

        vision = Vision()
        vision.visibles = [creature, fruit, plant]

        food, creatures, partners, plants = visible_counts(vision)
        assert (food, creatures, partners, plants) == (1, 1, 1, 1)


class TestBalanceWiring:
    def test_plant_system_uses_energy_cap(self):
        w = World(10, 10)
        w.balance = BalanceConfig(plant_energy_cap=10)
        plant = Entity().add_component(Plant(energy=9, energy_increase=5, fructify_threshold=80))
        w.place_entity(plant, 5, 5)

        plant_system({plant}, w)

        assert plant.get_component(Plant).energy == 10

    def test_eat_utility_uses_food_saturation(self):
        bio = Biochemistry(hunger=100)
        genome = default_genes()

        default = eat_utility(bio, genome, 1, BalanceConfig())
        saturated = eat_utility(bio, genome, 1, BalanceConfig(food_saturation=10))

        assert default > saturated