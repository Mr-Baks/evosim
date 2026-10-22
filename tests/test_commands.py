import math

import pytest

from commands import *
from entity import *
from world import World
from event_bus import EventBus
from genome import Gene, GeneNames, Genome
from traits import traits_for
from systems import command_system
from tests.helpers import default_genes


class TestCommandStatus:
    def test_status_values(self):
        assert CommandStatus.PENDING.value == 0
        assert CommandStatus.RUNNING.value == 1
        assert CommandStatus.COMPLETED.value == 2
        assert CommandStatus.FAILED.value == 3
        assert CommandStatus.CANCELLED.value == 4
        assert CommandStatus.INTERRUPTED.value == 5


class TestCommand:
    def test_command_defaults(self):
        cmd = MoveToTargetCommand()
        assert cmd.priority == 0
        assert cmd.status == CommandStatus.PENDING
        assert cmd.emergency == 0
        assert cmd.target_state is None

    def test_command_custom(self):
        cmd = MoveToTargetCommand(priority=10, emergency=5, target_state='eating')
        assert cmd.priority == 10
        assert cmd.emergency == 5
        assert cmd.target_state == 'eating'

    def test_is_ready_default(self):
        cmd = MoveToTargetCommand()
        e = Entity()
        w = World()
        assert cmd.is_ready(e, w) is True

    def test_on_interruption_default(self):
        cmd = MoveToTargetCommand()
        e = Entity()
        cmd.on_interruption(e)

    def test_complete(self):
        e = Entity().add_component(CommandQueue()).add_component(State())
        cmd = MoveToTargetCommand()
        queue = e.get_component(CommandQueue)
        queue.running = cmd
        cmd.complete(e)
        assert cmd.status == CommandStatus.COMPLETED


class TestCommandQueue:
    def test_command_queue_defaults(self):
        q = CommandQueue()
        assert q.queue == []
        assert q.running is None

    def test_command_queue_with_commands(self):
        cmd1 = MoveToTargetCommand(x=1, y=1)
        cmd2 = MoveToTargetCommand(x=2, y=2)
        q = CommandQueue(queue=[cmd1, cmd2], running=cmd1)
        assert q.queue == [cmd1, cmd2]
        assert q.running is cmd1


class TestPushCommand:
    def test_push_command_empty_queue(self):
        e = Entity().add_component(CommandQueue()).add_component(State()).add_component(Movable()).add_component(Biochemistry())
        w = World(10, 10)
        w.place_entity(e, 5, 5)
        cmd = MoveToTargetCommand(priority=5)
        push_command(e, w, cmd)
        queue = e.get_component(CommandQueue)
        assert queue.queue == [cmd]
        assert queue.running is None

    def test_push_command_higher_priority(self):
        e = Entity().add_component(CommandQueue()).add_component(State()).add_component(Movable()).add_component(Biochemistry())
        w = World(10, 10)
        w.place_entity(e, 5, 5)
        cmd1 = MoveToTargetCommand(x=6, y=5, priority=5)
        cmd2 = MoveToTargetCommand(x=7, y=5, priority=10)
        push_command(e, w, cmd1)
        push_command(e, w, cmd2)
        queue = e.get_component(CommandQueue)
        assert queue.queue[0] is cmd2
        assert queue.queue[1] is cmd1

    def test_push_command_same_priority_higher_emergency(self):
        e = Entity().add_component(CommandQueue()).add_component(State()).add_component(Movable()).add_component(Biochemistry())
        w = World(10, 10)
        w.place_entity(e, 5, 5)
        cmd1 = MoveToTargetCommand(x=6, y=5, priority=5, emergency=1)
        cmd2 = MoveToTargetCommand(x=7, y=5, priority=5, emergency=2)
        push_command(e, w, cmd1)
        push_command(e, w, cmd2)
        queue = e.get_component(CommandQueue)
        assert queue.queue[0] is cmd2
        assert queue.queue[1] is cmd1

    def test_push_command_emergency_interrupts_running(self):
        e = Entity().add_component(CommandQueue()).add_component(State()).add_component(Movable()).add_component(Biochemistry())
        w = World(10, 10)
        w.place_entity(e, 5, 5)
        running_cmd = MoveToTargetCommand(x=6, y=5, emergency=5)
        running_cmd.status = CommandStatus.RUNNING
        queue = e.get_component(CommandQueue)
        queue.running = running_cmd
        
        new_cmd = MoveToTargetCommand(x=7, y=5, emergency=10)
        push_command(e, w, new_cmd)
        
        assert queue.running is new_cmd
        assert new_cmd.status == CommandStatus.RUNNING
        assert running_cmd.status == CommandStatus.INTERRUPTED

    def test_push_command_emergency_not_ready(self):
        e = Entity().add_component(CommandQueue()).add_component(State()).add_component(Movable()).add_component(Biochemistry())
        w = World(10, 10)
        w.place_entity(e, 5, 5)
        running_cmd = MoveToTargetCommand(x=6, y=5, emergency=5)
        running_cmd.status = CommandStatus.RUNNING
        queue = e.get_component(CommandQueue)
        queue.running = running_cmd
        
        class NotReadyCommand(MoveToTargetCommand):
            def is_ready(self, entity, world):
                return False
        
        new_cmd = NotReadyCommand(x=7, y=5, emergency=10)
        push_command(e, w, new_cmd)
        
        assert queue.running is running_cmd
        assert new_cmd in queue.queue

    def test_push_command_state_tracking(self):
        e = Entity().add_component(CommandQueue()).add_component(State()).add_component(Movable()).add_component(Biochemistry())
        w = World(10, 10)
        w.place_entity(e, 5, 5)
        
        cmd = MoveToTargetCommand(x=6, y=5, target_state='moving')
        push_command(e, w, cmd)
        
        state = e.get_component(State)
        assert 'moving' in state.states


class TestEatCommand:
    def test_is_ready_adjacent(self):
        e = Entity(x=5, y=5).add_component(Biochemistry())
        w = World(10, 10)
        cmd = EatCommand(target_x=5, target_y=6)
        assert cmd.is_ready(e, w) is True

    def test_is_ready_not_adjacent(self):
        e = Entity(x=5, y=5).add_component(Biochemistry())
        w = World(10, 10)
        cmd = EatCommand(target_x=7, target_y=7)
        assert cmd.is_ready(e, w) is False

    def test_execute_eats_food(self):
        e = Entity(x=5, y=5).add_component(Biochemistry()).add_component(CommandQueue()).add_component(State())
        w = World(10, 10)
        w.place_entity(e, 5, 5)
        
        food = Entity().add_component(Eatable(nutrition=20))
        w.place_entity(food, 5, 6)
        
        cmd = EatCommand(target_x=5, target_y=6)
        queue = e.get_component(CommandQueue)
        queue.running = cmd
        cmd.execute(e, w)
        
        assert cmd.status == CommandStatus.COMPLETED
        assert w.get_entity(5, 6) is None

    def test_execute_no_food(self):
        e = Entity(x=5, y=5).add_component(Biochemistry()).add_component(CommandQueue()).add_component(State())
        w = World(10, 10)
        w.place_entity(e, 5, 5)
        
        cmd = EatCommand(target_x=5, target_y=6)
        queue = e.get_component(CommandQueue)
        queue.running = cmd
        cmd.execute(e, w)
        
        assert cmd.status == CommandStatus.FAILED

    def test_execute_not_eatable(self):
        e = Entity(x=5, y=5).add_component(Biochemistry()).add_component(CommandQueue()).add_component(State())
        w = World(10, 10)
        w.place_entity(e, 5, 5)
        
        rock = Entity().add_component(Movable())
        w.place_entity(rock, 5, 6)
        
        cmd = EatCommand(target_x=5, target_y=6)
        queue = e.get_component(CommandQueue)
        queue.running = cmd
        cmd.execute(e, w)
        
        assert cmd.status == CommandStatus.FAILED
        assert w.get_entity(5, 6) is rock


class TestDeathCommand:
    def test_execute_removes_entity(self):
        e = Entity(x=5, y=5).add_component(Biochemistry())
        w = World(10, 10)
        w.place_entity(e, 5, 5)
        
        cmd = DeathCommand()
        cmd.execute(e, w)
        
        assert w.get_entity(5, 5) is None
        assert e not in w.index.entities

    def test_execute_creates_corpse(self):
        e = Entity(x=5, y=5).add_component(Biochemistry())
        w = World(10, 10)
        w.place_entity(e, 5, 5)
        
        cmd = DeathCommand(corpse_nutrition=50)
        cmd.execute(e, w)
        
        corpse = w.get_entity(5, 5)
        assert corpse is not None
        assert corpse.has_component(Eatable)
        assert corpse.get_component(Eatable).nutrition == 50


class TestSleepCommand:
    def test_execute_decrements_ticks(self):
        e = Entity().add_component(Biochemistry()).add_component(CommandQueue()).add_component(State())
        w = World()
        cmd = SleepCommand(ticks_to_sleep=3)
        queue = e.get_component(CommandQueue)
        queue.running = cmd
        cmd.execute(e, w)
        assert cmd.ticks_to_sleep == 2
        assert cmd.status == CommandStatus.PENDING

    def test_execute_completes_when_zero(self):
        e = Entity().add_component(Biochemistry()).add_component(CommandQueue()).add_component(State())
        w = World()
        cmd = SleepCommand(ticks_to_sleep=1)
        queue = e.get_component(CommandQueue)
        queue.running = cmd
        cmd.execute(e, w)
        assert cmd.ticks_to_sleep == 0
        assert cmd.status == CommandStatus.COMPLETED

    def test_execute_completes_when_rounded_to_zero(self):
        e = Entity().add_component(Biochemistry()).add_component(CommandQueue()).add_component(State())
        w = World()
        cmd = SleepCommand(ticks_to_sleep=0)
        queue = e.get_component(CommandQueue)
        queue.running = cmd
        cmd.execute(e, w)
        assert cmd.status == CommandStatus.COMPLETED
        assert queue.running is None


class TestMoveToTargetCommand:
    def test_execute_moves_towards_target(self):
        e = Entity(x=5, y=5).add_component(Movable()).add_component(CommandQueue()).add_component(State())
        w = World(10, 10)
        w.place_entity(e, 5, 5)
        
        cmd = MoveToTargetCommand(x=7, y=5)
        queue = e.get_component(CommandQueue)
        queue.running = cmd
        cmd.execute(e, w)
        
        assert e.x == 6
        assert e.y == 5

    def test_execute_completes_at_target(self):
        e = Entity(x=5, y=5).add_component(Movable()).add_component(CommandQueue()).add_component(State())
        w = World(10, 10)
        w.place_entity(e, 5, 5)
        
        # Target is adjacent - after one move entity will be at target
        cmd = MoveToTargetCommand(x=6, y=5)
        queue = e.get_component(CommandQueue)
        queue.running = cmd
        cmd.execute(e, w)
        
        # After one move, entity is at (6, 5)
        assert e.x == 6
        assert e.y == 5
        assert cmd.status == CommandStatus.COMPLETED

    def test_execute_fails_no_free_cells(self):
        e = Entity(x=5, y=5).add_component(Movable()).add_component(CommandQueue()).add_component(State())
        w = World(10, 10)
        w.place_entity(e, 5, 5)
        
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                if dx == 0 and dy == 0:
                    continue
                ent = Entity().add_component(Biochemistry())
                w.place_entity(ent, 5+dx, 5+dy)
        
        cmd = MoveToTargetCommand(x=7, y=5)
        queue = e.get_component(CommandQueue)
        queue.running = cmd
        cmd.execute(e, w)
        
        assert cmd.status == CommandStatus.FAILED

    def test_execute_fails_target_occupied(self):
        e = Entity(x=5, y=5).add_component(Movable()).add_component(CommandQueue()).add_component(State())
        w = World(10, 10)
        w.place_entity(e, 5, 5)
        
        target = Entity().add_component(Biochemistry())
        w.place_entity(target, 6, 5)
        
        cmd = MoveToTargetCommand(x=6, y=5)
        queue = e.get_component(CommandQueue)
        queue.running = cmd
        
        # The destination is occupied: the entity does not idle - it slips to a
        # free neighbour - and after repeated failures the command gives up.
        cmd.execute(e, w)
        assert cmd.status != CommandStatus.FAILED
        assert (e.x, e.y) != (5, 5)
        
        for _ in range(10):
            cmd.execute(e, w)
        
        assert cmd.status == CommandStatus.FAILED


class TestWanderCommand:
    def test_execute_creates_move_command(self):
        e = Entity(x=5, y=5).add_component(Movable()).add_component(CommandQueue())
        w = World(10, 10)
        w.place_entity(e, 5, 5)
        
        cmd = WanderCommand(radius=2)
        cmd.execute(e, w)
        
        queue = e.get_component(CommandQueue)
        assert len(queue.queue) == 1
        assert isinstance(queue.queue[0], MoveToTargetCommand)


class TestMateCommand:
    def test_is_ready_adjacent_and_cooldown_zero(self):
        e1 = Entity(x=5, y=5).add_component(Breedable(cooldown=0))
        e2 = Entity(x=6, y=5).add_component(Breedable(cooldown=0))
        w = World(10, 10)
        w.place_entity(e1, 5, 5)
        w.place_entity(e2, 6, 5)
        
        cmd = MateCommand(partner=e2)
        assert cmd.is_ready(e1, w) is True

    def test_is_ready_not_adjacent(self):
        e1 = Entity(x=5, y=5).add_component(Breedable(cooldown=0))
        e2 = Entity(x=8, y=5).add_component(Breedable(cooldown=0))
        w = World(10, 10)
        w.place_entity(e1, 5, 5)
        w.place_entity(e2, 8, 5)
        
        cmd = MateCommand(partner=e2)
        assert cmd.is_ready(e1, w) is False

    def test_is_ready_cooldown_active(self):
        e1 = Entity(x=5, y=5).add_component(Breedable(cooldown=0))
        e2 = Entity(x=6, y=5).add_component(Breedable(cooldown=10))
        w = World(10, 10)
        w.place_entity(e1, 5, 5)
        w.place_entity(e2, 6, 5)
        
        cmd = MateCommand(partner=e2)
        assert cmd.is_ready(e1, w) is False

    def test_execute_creates_child(self):
        e1 = Entity(x=5, y=5).add_component(Breedable(cooldown=0)).add_component(Render(symbol='C', color=(100, 100, 100))).add_component(Biochemistry()).add_component(Movable()).add_component(Vision()).add_component(CommandQueue()).add_component(State()).add_component(default_genes()).add_component(Lineage(generation=2))
        e2 = Entity(x=6, y=5).add_component(Breedable(cooldown=0)).add_component(Render(symbol='C', color=(200, 200, 200))).add_component(Biochemistry()).add_component(Movable()).add_component(Vision()).add_component(CommandQueue()).add_component(State()).add_component(default_genes()).add_component(Lineage(generation=5))
        w = World(10, 10)
        w.place_entity(e1, 5, 5)
        w.place_entity(e2, 6, 5)

        free_cells_before = w.get_free_cells_near(e1)

        cmd = MateCommand(partner=e2)
        queue = e1.get_component(CommandQueue)
        queue.running = cmd
        cmd.execute(e1, w)

        assert cmd.status == CommandStatus.COMPLETED
        # Cooldown is now derived from the parent's wear_resistance gene
        # (traits.WearResistance.cooldown): default_genes -> 100 + 300.
        expected_cooldown = 100 + traits_for(e1.get_component(Genome)).wear_resistance.cooldown
        assert e1.get_component(Breedable).cooldown == pytest.approx(expected_cooldown)
        assert e2.get_component(Breedable).cooldown == pytest.approx(expected_cooldown)

        # The child is placed on a *random* free cell near e1
        # (World.get_free_cell_near -> random.choice), so exactly one of the
        # cells that were free before execution must now hold the child.
        occupied = [w.get_entity(x, y) for (x, y) in free_cells_before]
        children = [c for c in occupied if c is not None]
        assert len(children) == 1
        child = children[0]
        assert child.has_component(Biochemistry)
        assert child.has_component(Movable)
        # Child inherits a recombined genome
        assert child.has_component(Genome)

        lineage = child.get_component(Lineage)
        assert lineage.generation == 6
        assert lineage.parents_eid == (e2.eid, e1.eid)

    def test_execute_treats_missing_parent_lineage_as_zero(self):
        e1 = Entity(x=5, y=5).add_component(Breedable(cooldown=0)).add_component(Render(symbol='C', color=(100, 100, 100))).add_component(Biochemistry()).add_component(Movable()).add_component(Vision()).add_component(CommandQueue()).add_component(State()).add_component(default_genes()).add_component(Lineage(generation=4))
        e2 = Entity(x=6, y=5).add_component(Breedable(cooldown=0)).add_component(Render(symbol='C', color=(200, 200, 200))).add_component(Biochemistry()).add_component(Movable()).add_component(Vision()).add_component(CommandQueue()).add_component(State()).add_component(default_genes())
        w = World(10, 10)
        w.place_entity(e1, 5, 5)
        w.place_entity(e2, 6, 5)

        cmd = MateCommand(partner=e2)
        e1.get_component(CommandQueue).running = cmd
        cmd.execute(e1, w)

        child = next(e for e in w.index.get_with(Movable) if e not in (e1, e2))
        assert child.get_component(Lineage).generation == 5


class TestCreateChild:
    def test_create_child_combines_components(self):
        genes1 = [Gene(GeneNames.SPEED, 0.2, 0.2),
                  Gene(GeneNames.COLOR_R, 0.5, 0.5),
                  Gene(GeneNames.COLOR_G, 0.1, 0.1),
                  Gene(GeneNames.COLOR_B, 0.1, 0.1),
                  Gene(GeneNames.FERTILITY, 0.5, 0.5)]
        genes2 = [Gene(GeneNames.SPEED, -0.4, -0.4),
                  Gene(GeneNames.COLOR_R, -0.5, -0.5),
                  Gene(GeneNames.COLOR_G, -0.2, -0.2),
                  Gene(GeneNames.COLOR_B, -0.2, -0.2),
                  Gene(GeneNames.FERTILITY, -0.5, -0.5)]
        e1 = Entity().add_component(Biochemistry()).add_component(Movable()).add_component(Breedable()).add_component(Render(symbol='C', color=(100, 100, 100))).add_component(Genome(genes1))
        e2 = Entity().add_component(Biochemistry()).add_component(Vision()).add_component(Breedable()).add_component(Render(symbol='C', color=(200, 200, 200))).add_component(Genome(genes2))
        w = World()

        child = create_child(e1, e2, w)

        assert child.has_component(Biochemistry)
        assert child.has_component(Movable)
        assert child.has_component(Vision)
        assert child.has_component(Render)
        assert child.has_component(Genome)
        assert child.has_component(Lineage)
        assert child.get_component(Lineage).generation == 0
        assert child.get_component(Render).symbol == 'C'

        # Speed and color are derived from the child's recombined genome
        genome = child.get_component(Genome)
        r = int(genome.get_phenotype(GeneNames.COLOR_R) * 128 + 128)
        g = int(genome.get_phenotype(GeneNames.COLOR_G) * 128 + 128)
        b = int(genome.get_phenotype(GeneNames.COLOR_B) * 128 + 128)
        assert math.isclose(
            child.get_component(Movable).speed,
            genome.get_phenotype(GeneNames.SPEED) * 2.5 + 2.5,
            rel_tol=1e-9,
        )
        assert child.get_component(Render).color == (r, g, b)


def _creature(world, x=5, y=5, speed=1):
    entity = (
        Entity()
        .add_component(Movable(speed=speed))
        .add_component(CommandQueue())
        .add_component(State())
    )
    world.place_entity(entity, x, y)
    return entity


class TestCommandGroup:
    def test_empty_subcommand_list_completes(self):
        world = World(10, 10)
        entity = _creature(world)
        group = CommandGroup([])
        queue = entity.get_component(CommandQueue)
        queue.running = group

        group.execute(entity, world)

        assert group.status == CommandStatus.COMPLETED
        assert queue.running is None

    def test_takes_max_priority_and_emergency_from_children(self):
        group = CommandGroup([
            MoveToTargetCommand(x=1, y=1, priority=1, emergency=2),
            MoveToTargetCommand(x=2, y=2, priority=5, emergency=3),
        ])
        assert group.priority == 5
        assert group.emergency == 3

    def test_skips_subcommand_that_is_not_ready(self):
        world = World(10, 10)
        entity = _creature(world, 5, 5)
        group = CommandGroup([
            EatCommand(target_x=9, target_y=9),   # out of reach -> not ready
            MoveToTargetCommand(x=6, y=5),        # ready
        ])
        entity.get_component(CommandQueue).running = group

        group.execute(entity, world)

        assert isinstance(group._queue.running, MoveToTargetCommand)

    def test_completes_when_no_subcommand_is_ready(self):
        world = World(10, 10)
        entity = _creature(world, 5, 5)
        state = entity.get_component(State)
        state.states.add('eat')
        state.current = 'eat'
        group = CommandGroup([EatCommand(target_x=9, target_y=9)], target_state='eat')
        queue = entity.get_component(CommandQueue)
        queue.running = group

        group.execute(entity, world)

        assert group.status == CommandStatus.COMPLETED
        assert queue.running is None
        assert state.current == 'idle'
        assert 'eat' not in state.states

    def test_propagates_own_target_state_to_subcommand(self):
        world = World(10, 10)
        entity = _creature(world, 5, 5)
        group = CommandGroup([MoveToTargetCommand(x=8, y=5)], target_state='wander')
        entity.get_component(CommandQueue).running = group

        group.execute(entity, world)

        assert group._queue.running.target_state == 'wander'

    def test_inherits_target_state_from_subcommand(self):
        world = World(10, 10)
        entity = _creature(world, 5, 5)
        group = CommandGroup([MoveToTargetCommand(x=8, y=5, target_state='wander')])
        entity.get_component(CommandQueue).running = group

        group.execute(entity, world)

        assert group.target_state == 'wander'

    def test_interruption_cancels_children(self):
        world = World(10, 10)
        entity = _creature(world, 5, 5)
        running_sub = MoveToTargetCommand(x=8, y=5)
        queued_sub = MoveToTargetCommand(x=9, y=5)
        group = CommandGroup([running_sub, queued_sub])
        group._queue.running = running_sub
        running_sub.target_status = CommandStatus.RUNNING
        entity.get_component(CommandQueue).running = group

        group.on_interruption(entity)

        assert queued_sub.target_status == CommandStatus.CANCELLED
        assert running_sub.target_status == CommandStatus.INTERRUPTED
        assert group.status == CommandStatus.INTERRUPTED

    def test_executes_move_then_eat_in_order(self):
        world = World(10, 10)
        entity = _creature(world, 1, 1)
        food = Entity().add_component(Eatable(nutrition=20))
        world.place_entity(food, 2, 2)

        push_command(
            entity, world,
            MoveToTargetCommand(x=1, y=2),
            EatCommand(target_x=2, target_y=2, target_state='eat'),
            target_state='eat',
        )
        queue = entity.get_component(CommandQueue)
        assert isinstance(queue.queue[0], CommandGroup)

        for _ in range(5):
            command_system({entity}, world)

        assert world.get_entity(2, 2) is None            # food was eaten
        assert queue.running is None                     # group finished
        assert entity.get_component(State).current == 'idle'


class TestPushCommand:
    def test_single_command_is_not_wrapped(self):
        world = World(10, 10)
        entity = _creature(world)
        push_command(entity, world, MoveToTargetCommand(x=6, y=5), target_state='move')
        queue = entity.get_component(CommandQueue)
        assert len(queue.queue) == 1
        assert isinstance(queue.queue[0], MoveToTargetCommand)
        assert queue.queue[0].target_state == 'move'

    def test_multiple_commands_are_wrapped_in_group(self):
        world = World(10, 10)
        entity = _creature(world)
        push_command(
            entity, world,
            MoveToTargetCommand(x=6, y=5),
            EatCommand(target_x=6, target_y=5, target_state='eat'),
            target_state='eat',
        )
        queue = entity.get_component(CommandQueue)
        assert len(queue.queue) == 1
        assert isinstance(queue.queue[0], CommandGroup)
        assert queue.queue[0].target_state == 'eat'

    def test_higher_emergency_command_interrupts_running(self):
        world = World(10, 10)
        entity = _creature(world, 5, 5)
        low = MoveToTargetCommand(x=8, y=5, emergency=0)
        queue = entity.get_component(CommandQueue)
        queue.running = low
        low.status = CommandStatus.RUNNING

        high = MoveToTargetCommand(x=2, y=5, emergency=5)
        push_command(entity, world, high)

        assert queue.running is high
        assert high.status == CommandStatus.RUNNING
        assert low.target_status == CommandStatus.INTERRUPTED


class TestMoveToTargetPathfinding:
    def test_start_equals_goal_returns_empty_path(self):
        world = World(5, 5)
        entity = _creature(world, 2, 2)
        command = MoveToTargetCommand(x=2, y=2)
        assert command._find_path(world, (2, 2), ignore_entity=entity) == []

    def test_path_avoids_other_entities(self):
        world = World(5, 5)
        entity = _creature(world, 1, 1)
        world.place_entity(Entity().add_component(Biochemistry()), 1, 2)
        command = MoveToTargetCommand(x=1, y=3)

        path = command._find_path(world, (1, 1), ignore_entity=entity)

        assert path
        assert path[-1] == (1, 3)
        assert (1, 2) not in path
        assert all(world.get_entity(*cell) is None for cell in path)

    def test_path_goes_around_a_wall(self):
        world = World(7, 7)
        entity = _creature(world, 0, 3)
        for y in range(1, 7):                    # wall at x=3 with a gap at (3, 0)
            world.place_entity(Entity().add_component(Biochemistry()), 3, y)
        command = MoveToTargetCommand(x=6, y=3)

        path = command._find_path(world, (0, 3), ignore_entity=entity)

        assert path
        assert path[-1] == (6, 3)
        assert all(world.get_entity(*cell) is None for cell in path)

    def test_fully_enclosed_goal_is_unreachable(self):
        world = World(5, 5)
        entity = _creature(world, 0, 0)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                world.place_entity(Entity().add_component(Biochemistry()), 2 + dx, 2 + dy)
        command = MoveToTargetCommand(x=2, y=2)

        assert command._find_path(world, (0, 0), ignore_entity=entity) == []

    def test_high_speed_takes_multiple_steps_per_tick(self):
        world = World(10, 10)
        entity = _creature(world, 0, 0, speed=2)
        command = MoveToTargetCommand(x=4, y=0)
        entity.get_component(CommandQueue).running = command

        command.execute(entity, world)
        assert entity.x == 2
        assert command.status == CommandStatus.PENDING

        command.execute(entity, world)
        assert entity.x == 4
        assert command.status == CommandStatus.COMPLETED

    def test_low_speed_accumulates_before_stepping(self):
        world = World(10, 10)
        entity = _creature(world, 0, 0, speed=0.5)
        command = MoveToTargetCommand(x=3, y=0)
        entity.get_component(CommandQueue).running = command

        command.execute(entity, world)
        assert entity.x == 0
        assert command.status == CommandStatus.PENDING

        command.execute(entity, world)
        assert entity.x == 1

    def test_sidesteps_when_next_cell_becomes_blocked(self):
        world = World(6, 6)
        entity = _creature(world, 0, 0)
        command = MoveToTargetCommand(x=3, y=0)
        entity.get_component(CommandQueue).running = command

        command.execute(entity, world)
        assert entity.x == 1

        world.place_entity(Entity().add_component(Biochemistry()), 2, 0)
        command.execute(entity, world)

        assert command.path == []
        assert command.path_retry_count == 1
        # It slips aside instead of idling on top of the obstacle.
        assert (entity.x, entity.y) != (1, 0)
        assert (entity.x, entity.y) != (2, 0)

    def test_octile_distance_matches_8way_walk_cost(self):
        # 3 right + 4 up = 3 diagonal steps + 1 straight step
        assert octile(0, 0, 3, 4) == pytest.approx(3 * 1.414 + 1.0)

    def test_route_prefers_straight_line_when_clear(self):
        world = World(6, 6)
        entity = _creature(world, 0, 0)
        command = MoveToTargetCommand(x=0, y=4)

        assert command._route(world, entity) == [(0, 1), (0, 2), (0, 3), (0, 4)]

    def test_route_falls_back_to_a_star_when_line_is_blocked(self):
        world = World(7, 7)
        entity = _creature(world, 0, 3)
        world.place_entity(Entity().add_component(Biochemistry()), 1, 3)
        command = MoveToTargetCommand(x=6, y=3)

        route = command._route(world, entity)

        assert route and route[-1] == (6, 3)
        assert (1, 3) not in route

    def test_sidesteps_when_goal_is_occupied(self):
        world = World(8, 8)
        entity = _creature(world, 3, 3)
        world.place_entity(Entity().add_component(Biochemistry()), 4, 3)
        command = MoveToTargetCommand(x=4, y=3)
        entity.get_component(CommandQueue).running = command

        command.execute(entity, world)

        # No idling: the creature moves to a free neighbour instead.
        assert (entity.x, entity.y) != (3, 3)
        assert command.path == []


class TestWanderCommand:
    def test_point_utility_prefers_food_when_starving(self):
        world = World(10, 10)
        entity = (Entity()
                  .add_component(Biochemistry(hunger=0, energy=100))
                  .add_component(Movable())
                  .add_component(default_genes(food_appetence=1.0, crowd_preference=0.0, plant_appetence=0.0)))
        world.place_entity(entity, 5, 5)
        world.place_entity(Entity().add_component(Eatable(nutrition=20)), 2, 5)

        command = WanderCommand()

        assert command.point_utility(3, 5, entity, world) > command.point_utility(8, 5, entity, world)

    def test_point_utility_prefers_food_over_plants_when_starving(self):
        # Plants themselves are not food. A starving creature should not stop
        # at plant cover when a visible fruit is available.
        world = World(10, 10)
        entity = (Entity()
                  .add_component(Biochemistry(hunger=0, energy=100))
                  .add_component(Movable())
                  .add_component(default_genes(food_appetence=1.0, plant_appetence=1.0, crowd_preference=0.0)))
        world.place_entity(entity, 5, 5)
        world.place_entity(Entity().add_component(Eatable(nutrition=20)), 2, 5)
        for x, y in ((7, 4), (7, 6), (6, 5)):
            world.place_entity(Entity().add_component(Plant()), x, y)

        command = WanderCommand()

        assert command.point_utility(3, 5, entity, world) > command.point_utility(7, 5, entity, world)

    def test_point_utility_avoids_crowds_for_crowd_averse_creature(self):
        world = World(10, 10)
        entity = (Entity()
                  .add_component(Biochemistry(hunger=0, energy=100))
                  .add_component(Movable())
                  .add_component(default_genes(crowd_preference=-1.0, food_appetence=0.0, plant_appetence=0.0)))
        world.place_entity(entity, 5, 5)
        world.place_entity(Entity().add_component(Movable()), 1, 6)

        command = WanderCommand()

        assert command.point_utility(1, 5, entity, world) < command.point_utility(9, 5, entity, world)

    def test_inverts_direction_when_target_out_of_bounds(self, monkeypatch):
        import commands
        monkeypatch.setattr(commands.random, 'uniform', lambda a, b: 0.0)  # angle 0 -> +x
        world = World(5, 5)
        entity = _creature(world, 4, 0)

        WanderCommand(radius=4).execute(entity, world)

        queued = entity.get_component(CommandQueue).queue[-1]
        assert isinstance(queued, MoveToTargetCommand)
        assert (queued.x, queued.y) == (0, 0)

    def test_clamps_target_when_both_directions_out_of_bounds(self, monkeypatch):
        import commands
        monkeypatch.setattr(commands.random, 'uniform', lambda a, b: 0.0)
        world = World(5, 5)
        entity = _creature(world, 0, 0)

        WanderCommand(radius=10).execute(entity, world)

        queued = entity.get_component(CommandQueue).queue[-1]
        assert 0 <= queued.x < world.width
        assert 0 <= queued.y < world.height
