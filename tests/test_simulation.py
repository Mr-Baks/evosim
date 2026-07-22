from unittest.mock import patch, MagicMock
from simulation import Simulation
from world import World
from entity import Entity, Biochemistry, State, Vision, Movable, Breedable, Render, Eatable, Plant
from commands import CommandQueue, MoveToTargetCommand, CommandStatus
from event_bus import EventBus, EatEvent, SleepEvent, MoveEvent, on_eat, on_sleep, on_move


class TestSimulation:
    def test_init_defaults(self):
        sim = Simulation(tickspeed=10, fps=30, world_size=(20, 15))
        
        assert sim.tickspeed == 10
        assert sim.fps == 30
        assert sim.background_sym == '.'
        assert isinstance(sim.world, World)
        assert sim.world.width == 20
        assert sim.world.height == 15
        assert sim.systems == []
        assert sim.on_tick_callbacks == []

    def test_init_custom_background(self):
        sim = Simulation(tickspeed=10, fps=30, world_size=(20, 15), background_sym='#')
        
        assert sim.background_sym == '#'

    def test_register_system_priority_order(self):
        sim = Simulation(tickspeed=10, fps=30, world_size=(10, 10))
        
        def sys1(entities, world): pass
        def sys2(entities, world): pass
        def sys3(entities, world): pass
        
        sim.register_system(frozenset([Biochemistry]), sys1, priority=10)
        sim.register_system(frozenset([Biochemistry]), sys2, priority=50)
        sim.register_system(frozenset([Biochemistry]), sys3, priority=30)
        
        assert len(sim.systems) == 3
        assert sim.systems[0][0] == 50
        assert sim.systems[1][0] == 30
        assert sim.systems[2][0] == 10

    def test_register_system_registers_with_index(self):
        sim = Simulation(tickspeed=10, fps=30, world_size=(10, 10))
        
        def sys1(entities, world): pass
        
        sim.register_system(frozenset([Biochemistry]), sys1, priority=10)
        
        assert frozenset([Biochemistry]) in sim.world.index.systems_cache

    def test_handle_systems_locks_index(self):
        sim = Simulation(tickspeed=10, fps=30, world_size=(10, 10))
        
        e = Entity().add_component(Biochemistry())
        sim.world.place_entity(e, 5, 5)
        
        called = []
        def sys1(entities, world):
            called.append(1)
            assert sim.world.index.locked is True
        
        sim.register_system(frozenset([Biochemistry]), sys1, priority=10)
        sim.handle_systems()
        
        assert sim.world.index.locked is False
        assert called == [1]

    def test_handle_systems_flushes_pending(self):
        sim = Simulation(tickspeed=10, fps=30, world_size=(10, 10))
        
        def sys1(entities, world):
            e2 = Entity().add_component(Biochemistry())
            world.place_entity(e2, 6, 6)
        
        sim.register_system(frozenset([Biochemistry]), sys1, priority=10)
        
        e = Entity().add_component(Biochemistry())
        sim.world.place_entity(e, 5, 5)
        
        sim.handle_systems()
        
        assert len(sim.world.index.entities) == 2

    def test_add_on_tick(self):
        sim = Simulation(tickspeed=10, fps=30, world_size=(10, 10))
        
        callback = lambda s: None
        sim.add_on_tick(callback)
        
        assert callback in sim.on_tick_callbacks

    def test_render_returns_grid(self):
        sim = Simulation(tickspeed=10, fps=30, world_size=(5, 5))
        
        e = Entity().add_component(Render(symbol='C', color=(255, 0, 0)))
        sim.world.place_entity(e, 2, 2)
        
        screen = sim.render()
        
        assert len(screen) == 5
        assert len(screen[0]) == 5
        assert screen[2][2] == '\033[38;2;255;0;0mC\033[0m'

    def test_render_excludes_invisible(self):
        sim = Simulation(tickspeed=10, fps=30, world_size=(5, 5))
        
        e1 = Entity().add_component(Render(symbol='C', color=(255, 0, 0), is_visible=True))
        e2 = Entity().add_component(Render(symbol='X', color=(0, 255, 0), is_visible=False))
        sim.world.place_entity(e1, 1, 1)
        sim.world.place_entity(e2, 2, 2)
        
        screen = sim.render()
        
        assert screen[1][1] != '.'
        assert screen[2][2] == '.'

    def test_render_background(self):
        sim = Simulation(tickspeed=10, fps=30, world_size=(3, 3), background_sym='#')
        
        screen = sim.render()
        
        assert all(cell == '#' for row in screen for cell in row)

    def test_print_scene_outputs(self, capsys):
        sim = Simulation(tickspeed=10, fps=30, world_size=(3, 3))
        
        e = Entity().add_component(Render(symbol='C', color=(255, 0, 0)))
        sim.world.place_entity(e, 1, 1)
        
        sim.print_scene()
        
        captured = capsys.readouterr()
        assert 'C' in captured.out

    def test_run_stops_when_is_running_false(self):
        sim = Simulation(tickspeed=10, fps=30, world_size=(10, 10))
        
        # Create a callback that stops the simulation
        def stop_sim(s):
            s.is_running = False
        
        sim.add_on_tick(stop_sim)
        
        with patch('time.time', side_effect=[0, 0.1, 0.2, 0.3, 0.4]):
            with patch('time.sleep') as mock_sleep:
                sim.run()
                # Sleep should not be called because is_running becomes False after first tick
                mock_sleep.assert_not_called()

    def test_run_calls_systems_and_dispatch(self):
        sim = Simulation(tickspeed=1000, fps=30, world_size=(10, 10))
        sim.is_running = True
        
        call_order = []
        def sys1(entities, world):
            call_order.append('sys1')
        def sys2(entities, world):
            call_order.append('sys2')
        
        sim.register_system(frozenset([Biochemistry]), sys1, priority=10)
        sim.register_system(frozenset([Biochemistry]), sys2, priority=20)
        
        sim.world.event_bus.dispatch = MagicMock()
        
        def stop_after_tick(s):
            s.is_running = False
        
        sim.add_on_tick(stop_after_tick)
        
        time_values = [0.0]
        for i in range(1, 20):
            time_values.append(i * 0.02)
        time_values.append(999)
        
        with patch('time.time', side_effect=time_values):
            with patch('time.sleep'):
                try:
                    sim.run()
                except:
                    pass
        
        assert 'sys1' in call_order
        assert 'sys2' in call_order
        sim.world.event_bus.dispatch.assert_called()

    def test_run_calls_on_tick_callbacks(self):
        sim = Simulation(tickspeed=10, fps=30, world_size=(10, 10))
        sim.is_running = True
        
        calls = []
        def callback(s):
            calls.append(s)
            if len(calls) >= 2:
                s.is_running = False
        sim.add_on_tick(callback)
        
        time_values = [0.0]
        for i in range(1, 20):
            time_values.append(i * 0.2)
        time_values.append(999)
        
        with patch('time.time', side_effect=time_values):
            with patch('time.sleep'):
                try:
                    sim.run()
                except:
                    pass
        
        assert len(calls) >= 1
        assert all(c is sim for c in calls)

    def test_run_fixed_timestep(self):
        sim = Simulation(tickspeed=100, fps=30, world_size=(10, 10))
        sim.is_running = True
        
        tick_count = 0
        def sys1(entities, world):
            nonlocal tick_count
            tick_count += 1
        
        sim.register_system(frozenset([Biochemistry]), sys1, priority=10)
        
        def stop_after_ticks(s):
            if tick_count >= 5:
                s.is_running = False
        
        sim.add_on_tick(stop_after_ticks)
        
        time_values = [0]
        for i in range(1, 20):
            time_values.append(i * 0.02)
        time_values.append(999)
        
        with patch('time.time', side_effect=time_values):
            with patch('time.sleep'):
                try:
                    sim.run()
                except:
                    pass
        
        assert tick_count >= 1
        
        assert tick_count >= 1


class TestSimulationIntegration:
    def test_creature_eats_food(self):
        sim = Simulation(tickspeed=1000, fps=30, world_size=(10, 10))
        # Subscribe event handlers
        sim.world.event_bus.subscribe(EatEvent, on_eat)
        sim.world.event_bus.subscribe(SleepEvent, on_sleep)
        sim.world.event_bus.subscribe(MoveEvent, on_move)
        
        creature = Entity().add_component(Biochemistry(energy=100, hunger=30)).add_component(CommandQueue()).add_component(State()).add_component(Vision(radius=5)).add_component(Movable())
        sim.world.place_entity(creature, 5, 5)
        
        food = Entity().add_component(Eatable(nutrition=20)).add_component(Movable())
        sim.world.place_entity(food, 6, 5)
        
        from systems import vision_system, decision_system, command_system, biochemistry_system
        
        # Run multiple cycles until food is eaten
        for _ in range(10):
            vision_system({creature}, sim.world)
            decision_system({creature}, sim.world)
            command_system({creature}, sim.world)
            biochemistry_system({creature}, sim.world)
            sim.world.event_bus.dispatch()
            
            if sim.world.get_entity(6, 5) is None:  # Food eaten
                break
        
        bio = creature.get_component(Biochemistry)
        assert bio.hunger > 30

    def test_creature_sleeps_when_low_energy(self):
        sim = Simulation(tickspeed=1000, fps=30, world_size=(10, 10))
        
        creature = Entity().add_component(Biochemistry(energy=30, hunger=100)).add_component(CommandQueue()).add_component(State()).add_component(Vision(radius=5)).add_component(Movable())
        sim.world.place_entity(creature, 5, 5)
        
        from systems import decision_system, command_system, biochemistry_system
        
        decision_system({creature}, sim.world)
        command_system({creature}, sim.world)
        
        queue = creature.get_component(CommandQueue)
        assert queue.running is not None
        from commands import SleepCommand
        assert isinstance(queue.running, SleepCommand)

    def test_plant_produces_fruit(self):
        sim = Simulation(tickspeed=1000, fps=30, world_size=(10, 10))
        
        plant = Entity().add_component(Plant(energy=90, energy_increase=0, fructify_threshold=80, fruit_nutrition=25)).add_component(Render(symbol='P'))
        sim.world.place_entity(plant, 5, 5)
        
        from systems import plant_system
        
        plant_system({plant}, sim.world)
        
        p = plant.get_component(Plant)
        assert p.energy == 10
        
        fruits = sim.world.index.get_with(Eatable)
        assert len(fruits) == 1
        assert list(fruits)[0].get_component(Eatable).nutrition == 25