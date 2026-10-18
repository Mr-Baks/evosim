import pytest

from systems import *
from commands import *
from entity import *
from world import World
from event_bus import EventBus
from genome import Genome, GeneNames
from tests.helpers import (
    default_genes,
    make_decision_random_deterministic,
    biochem_traits,
    living_energy_cost,
    living_hunger_cost,
)


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


class TestBiochemistrySystem:
    # Drains are gene-derived: metabolism * speed**2 scaled, then weighted by
    # (2 - vitality) for energy and (wear_resistance / 710) for hunger.
    # Expected values are computed from the same scaling in tests.helpers.

    def test_biochemistry_system_energy_decay(self):
        e = Entity().add_component(Biochemistry(energy=100)).add_component(CommandQueue()).add_component(Movable()).add_component(default_genes())
        w = World(10, 10)
        w.place_entity(e, 5, 5)

        traits = biochem_traits(e.get_component(Genome))
        biochemistry_system({e}, w)

        bio = e.get_component(Biochemistry)
        assert bio.energy == pytest.approx(100 - living_energy_cost(traits, age=1))

    def test_biochemistry_system_energy_zero_health_decay(self):
        e = Entity().add_component(Biochemistry(energy=0, health=100)).add_component(CommandQueue()).add_component(Movable()).add_component(default_genes())
        w = World(10, 10)
        w.place_entity(e, 5, 5)

        biochemistry_system({e}, w)

        bio = e.get_component(Biochemistry)
        assert bio.health == 99

    def test_biochemistry_system_hunger_decay(self):
        e = Entity().add_component(Biochemistry(hunger=100)).add_component(CommandQueue()).add_component(Movable()).add_component(default_genes())
        w = World(10, 10)
        w.place_entity(e, 5, 5)

        traits = biochem_traits(e.get_component(Genome))
        biochemistry_system({e}, w)

        bio = e.get_component(Biochemistry)
        assert bio.hunger == pytest.approx(100 - living_hunger_cost(traits))

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
        # Energy increases to 185, capped to 180, then fructify subtracts 80 -> 100
        assert plant.energy == 100

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
        expected_cooldown = 100 + e1.get_component(Genome).get_phenotype(
            GeneNames.WEAR_RESISTANCE, (0.001, 300), log=True
        )

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

        assert wander_utility(crowded, w) > wander_utility(lonely, w)

    def test_wander_utility_drops_when_starving(self):
        # A starving creature should be less eager to wander aimlessly.
        fed = Entity().add_component(Biochemistry(hunger=0, energy=100)).add_component(Vision(radius=5)).add_component(Movable()).add_component(default_genes())
        starving = Entity().add_component(Biochemistry(hunger=190, energy=100)).add_component(Vision(radius=5)).add_component(Movable()).add_component(default_genes())

        assert wander_utility(fed, None) > wander_utility(starving, None)

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