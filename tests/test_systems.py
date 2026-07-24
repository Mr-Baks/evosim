from systems import *
from commands import *
from entity import *
from world import World
from event_bus import EventBus


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
        
        cmd1 = MoveToTargetCommand(x=6, y=5)
        cmd2 = MoveToTargetCommand(x=7, y=5)
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
        cmd2 = MoveToTargetCommand(x=6, y=5)
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
    def test_biochemistry_system_energy_decay(self):
        e = Entity().add_component(Biochemistry(energy=100)).add_component(CommandQueue()).add_component(Movable())
        w = World(10, 10)
        w.place_entity(e, 5, 5)
        
        biochemistry_system({e}, w)
        
        bio = e.get_component(Biochemistry)
        assert bio.energy == 99.5

    def test_biochemistry_system_energy_zero_health_decay(self):
        e = Entity().add_component(Biochemistry(energy=0, health=100)).add_component(CommandQueue()).add_component(Movable())
        w = World(10, 10)
        w.place_entity(e, 5, 5)
        
        biochemistry_system({e}, w)
        
        bio = e.get_component(Biochemistry)
        assert bio.health == 99

    def test_biochemistry_system_hunger_decay(self):
        e = Entity().add_component(Biochemistry(hunger=100)).add_component(CommandQueue()).add_component(Movable())
        w = World(10, 10)
        w.place_entity(e, 5, 5)
        
        biochemistry_system({e}, w)
        
        bio = e.get_component(Biochemistry)
        assert bio.hunger == 99.5

    def test_biochemistry_system_hunger_zero_health_decay(self):
        e = Entity().add_component(Biochemistry(hunger=0, health=100)).add_component(CommandQueue()).add_component(Movable())
        w = World(10, 10)
        w.place_entity(e, 5, 5)
        
        biochemistry_system({e}, w)
        
        bio = e.get_component(Biochemistry)
        assert bio.health == 99

    def test_biochemistry_system_health_zero_death_command(self):
        e = Entity().add_component(Biochemistry(health=0)).add_component(CommandQueue()).add_component(Movable())
        w = World(10, 10)
        w.place_entity(e, 5, 5)
        
        biochemistry_system({e}, w)
        
        queue = e.get_component(CommandQueue)
        assert len(queue.queue) == 1
        assert isinstance(queue.queue[0], DeathCommand)
        assert queue.queue[0].emergency == 100

    def test_biochemistry_system_breedable_cooldown(self):
        e = Entity().add_component(Biochemistry()).add_component(CommandQueue()).add_component(Breedable(cooldown=5)).add_component(Movable())
        w = World(10, 10)
        w.place_entity(e, 5, 5)
        
        biochemistry_system({e}, w)
        
        breedable = e.get_component(Breedable)
        assert breedable.cooldown == 4

    def test_biochemistry_system_sleeping_no_energy_decay(self):
        e = Entity().add_component(Biochemistry(energy=100)).add_component(CommandQueue()).add_component(Movable())
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

    def test_decision_system_hungry_seeks_food(self):
        e = Entity().add_component(Biochemistry(hunger=30, energy=100)).add_component(CommandQueue()).add_component(State()).add_component(Vision(radius=5)).add_component(Movable())
        w = World(10, 10)
        self._subscribe_handlers(w)
        w.place_entity(e, 5, 5)
        
        food = Entity().add_component(Eatable(nutrition=20)).add_component(Movable())
        w.place_entity(food, 6, 6)
        
        vision_system({e}, w)
        decision_system({e}, w)
        command_system({e}, w)
        
        queue = e.get_component(CommandQueue)
        assert queue.running is not None
        # EatCommand has higher emergency (81) than MoveToTargetCommand (80), so it runs first
        assert isinstance(queue.running, EatCommand)

    def test_decision_system_hungry_no_food_wanders(self):
        e = Entity().add_component(Biochemistry(hunger=30, energy=100)).add_component(CommandQueue()).add_component(State()).add_component(Vision(radius=1)).add_component(Movable())
        w = World(10, 10)
        self._subscribe_handlers(w)
        w.place_entity(e, 5, 5)
        
        vision_system({e}, w)
        decision_system({e}, w)
        command_system({e}, w)
        
        queue = e.get_component(CommandQueue)
        assert queue.running is not None
        assert isinstance(queue.running, WanderCommand)

    def test_decision_system_low_energy_sleeps(self):
        e = Entity().add_component(Biochemistry(hunger=100, energy=30)).add_component(CommandQueue()).add_component(State()).add_component(Vision(radius=5)).add_component(Movable())
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
        e1 = Entity().add_component(Biochemistry(hunger=80, energy=80)).add_component(CommandQueue()).add_component(State()).add_component(Vision(radius=5)).add_component(Movable()).add_component(Breedable(cooldown=0))
        e2 = Entity().add_component(Biochemistry(hunger=80, energy=80)).add_component(Breedable(cooldown=0)).add_component(Movable())
        w = World(10, 10)
        self._subscribe_handlers(w)
        w.place_entity(e1, 5, 5)
        w.place_entity(e2, 6, 5)
        
        vision_system({e1}, w)
        decision_system({e1}, w)
        command_system({e1}, w)
        
        queue = e1.get_component(CommandQueue)
        assert queue.running is not None
        # MateCommand has higher emergency (16) than MoveToTargetCommand (15), so it runs first
        assert isinstance(queue.running, MateCommand)

    def test_decision_system_wanders_when_idle(self):
        e = Entity().add_component(Biochemistry(hunger=100, energy=100)).add_component(CommandQueue()).add_component(State()).add_component(Vision(radius=5)).add_component(Movable())
        w = World(10, 10)
        self._subscribe_handlers(w)
        w.place_entity(e, 5, 5)
        
        vision_system({e}, w)
        decision_system({e}, w)
        command_system({e}, w)
        
        queue = e.get_component(CommandQueue)
        assert queue.running is not None
        assert isinstance(queue.running, WanderCommand)

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
        e = Entity().add_component(Biochemistry(energy=100, hunger=100, health=100)).add_component(CommandQueue()).add_component(State()).add_component(Vision(radius=5)).add_component(Movable()).add_component(Breedable(cooldown=0))
        w = World(20, 20)
        w.place_entity(e, 10, 10)
        
        food = Entity().add_component(Eatable(nutrition=20)).add_component(Movable())
        w.place_entity(food, 11, 11)
        
        vision_system({e}, w)
        decision_system({e}, w)
        command_system({e}, w)
        biochemistry_system({e}, w)
        w.event_bus.dispatch()
        
        # Energy decays by 0.5 when not sleeping
        assert e.get_component(Biochemistry).energy == 99.5
        assert len(e.get_component(CommandQueue).queue) >= 0

    def test_eat_then_energy_increase(self):
        e = Entity().add_component(Biochemistry(energy=50, hunger=30)).add_component(CommandQueue()).add_component(State()).add_component(Vision(radius=5)).add_component(Movable())
        w = World(10, 10)
        w.event_bus.subscribe(EatEvent, on_eat)
        w.event_bus.subscribe(SleepEvent, on_sleep)
        w.event_bus.subscribe(MoveEvent, on_move)
        w.place_entity(e, 5, 5)
        
        food = Entity().add_component(Eatable(nutrition=25)).add_component(Movable())
        w.place_entity(food, 5, 6)
        
        vision_system({e}, w)
        decision_system({e}, w)
        
        # Run multiple command cycles until food is eaten
        for _ in range(15):
            command_system({e}, w)
            w.event_bus.dispatch()
            biochemistry_system({e}, w)
            if e.get_component(Biochemistry).hunger > 30:
                break
        
        bio = e.get_component(Biochemistry)
        assert bio.hunger > 30