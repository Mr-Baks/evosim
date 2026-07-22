from commands import *
from entity import *
from world import World
from event_bus import EventBus


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
        e1 = Entity(x=5, y=5).add_component(Breedable(cooldown=0)).add_component(Render(symbol='C', color=(100, 100, 100))).add_component(Biochemistry()).add_component(Movable()).add_component(Vision()).add_component(CommandQueue()).add_component(State())
        e2 = Entity(x=6, y=5).add_component(Breedable(cooldown=0)).add_component(Render(symbol='C', color=(200, 200, 200))).add_component(Biochemistry()).add_component(Movable()).add_component(Vision()).add_component(CommandQueue()).add_component(State())
        w = World(10, 10)
        w.place_entity(e1, 5, 5)
        w.place_entity(e2, 6, 5)
        
        free_cells_before = w.get_free_cells_near(e1)
        expected_child_pos = free_cells_before[0]
        
        cmd = MateCommand(partner=e2)
        queue = e1.get_component(CommandQueue)
        queue.running = cmd
        cmd.execute(e1, w)
        
        assert cmd.status == CommandStatus.COMPLETED
        assert e1.get_component(Breedable).cooldown == 40
        assert e2.get_component(Breedable).cooldown == 40
        
        # Child should be placed at the first free cell near e1 before execution
        child = w.get_entity(*expected_child_pos)
        assert child is not None
        assert child.has_component(Biochemistry)
        assert child.has_component(Movable)


class TestCreateChild:
    def test_create_child_combines_components(self):
        e1 = Entity().add_component(Biochemistry()).add_component(Movable()).add_component(Render(symbol='C', color=(100, 100, 100)))
        e2 = Entity().add_component(Biochemistry()).add_component(Vision()).add_component(Render(symbol='C', color=(200, 200, 200)))
        w = World()
        
        child = create_child(e1, e2, w)
        
        assert child.has_component(Biochemistry)
        assert child.has_component(Movable)
        assert child.has_component(Vision)
        assert child.has_component(Render)
        assert child.get_component(Render).symbol == 'C'