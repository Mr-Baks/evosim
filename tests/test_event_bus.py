from event_bus import Event, EventBus, MoveEvent, SleepEvent, EatEvent, on_move, on_sleep, on_eat
from entity import Entity, Biochemistry


class TestEvent:
    def test_event_defaults(self):
        e = Event()
        assert e.priority == 0
        assert e.source is None

    def test_event_custom(self):
        ent = Entity()
        e = Event(priority=10, source=ent)
        assert e.priority == 10
        assert e.source is ent


class TestEventBus:
    def test_init(self):
        bus = EventBus()
        assert bus.subscribers == {}
        assert bus.event_queue == []

    def test_subscribe(self):
        bus = EventBus()
        handler = lambda e: None
        bus.subscribe(MoveEvent, handler)
        assert MoveEvent in bus.subscribers
        assert handler in bus.subscribers[MoveEvent]

    def test_subscribe_multiple_handlers(self):
        bus = EventBus()
        h1 = lambda e: None
        h2 = lambda e: None
        bus.subscribe(MoveEvent, h1)
        bus.subscribe(MoveEvent, h2)
        assert len(bus.subscribers[MoveEvent]) == 2

    def test_unsubscribe(self):
        bus = EventBus()
        handler = lambda e: None
        bus.subscribe(MoveEvent, handler)
        bus.unsubscribe(MoveEvent, handler)
        assert handler not in bus.subscribers[MoveEvent]

    def test_emit(self):
        bus = EventBus()
        event = MoveEvent()
        bus.emit(event)
        assert len(bus.event_queue) == 1
        assert bus.event_queue[0] is event

    def test_emit_multiple(self):
        bus = EventBus()
        bus.emit(MoveEvent())
        bus.emit(SleepEvent())
        bus.emit(EatEvent())
        assert len(bus.event_queue) == 3

    def test_dispatch_calls_handlers(self):
        bus = EventBus()
        calls = []
        def handler(e):
            calls.append(e)
        bus.subscribe(MoveEvent, handler)
        
        event = MoveEvent(source=Entity())
        bus.emit(event)
        bus.dispatch()
        
        assert len(calls) == 1
        assert calls[0] is event

    def test_dispatch_multiple_handlers(self):
        bus = EventBus()
        calls1 = []
        calls2 = []
        bus.subscribe(MoveEvent, lambda e: calls1.append(e))
        bus.subscribe(MoveEvent, lambda e: calls2.append(e))
        
        event = MoveEvent()
        bus.emit(event)
        bus.dispatch()
        
        assert len(calls1) == 1
        assert len(calls2) == 1

    def test_dispatch_priority_order(self):
        bus = EventBus()
        order = []
        bus.subscribe(MoveEvent, lambda e: order.append('low'))
        bus.subscribe(MoveEvent, lambda e: order.append('high'))
        
        bus.emit(MoveEvent(priority=0))
        bus.emit(MoveEvent(priority=10))
        bus.dispatch()
        
        # Events are sorted by priority (high first), handlers called in subscription order
        # high priority event -> low handler, high handler
        # low priority event -> low handler, high handler
        assert order == ['low', 'high', 'low', 'high']

    def test_dispatch_clears_queue(self):
        bus = EventBus()
        bus.emit(MoveEvent())
        bus.dispatch()
        assert len(bus.event_queue) == 0

    def test_dispatch_no_subscribers(self):
        bus = EventBus()
        bus.emit(MoveEvent())
        bus.dispatch()


class TestMoveEvent:
    def test_move_event(self):
        e = MoveEvent()
        assert isinstance(e, Event)


class TestSleepEvent:
    def test_sleep_event_defaults(self):
        e = SleepEvent()
        assert e.energy_increase == 30

    def test_sleep_event_custom(self):
        e = SleepEvent(energy_increase=50)
        assert e.energy_increase == 50


class TestEatEvent:
    def test_eat_event_defaults(self):
        e = EatEvent()
        assert e.nutrition == 35

    def test_eat_event_custom(self):
        e = EatEvent(nutrition=20)
        assert e.nutrition == 20


class TestEventHandlers:
    def test_on_move_decreases_energy(self):
        ent = Entity().add_component(Biochemistry(energy=100))
        event = MoveEvent(source=ent)
        on_move(event)
        assert ent.get_component(Biochemistry).energy == 98

    def test_on_move_energy_min_zero(self):
        ent = Entity().add_component(Biochemistry(energy=1))
        event = MoveEvent(source=ent)
        on_move(event)
        assert ent.get_component(Biochemistry).energy == 0

    def test_on_move_no_biochemistry(self):
        ent = Entity()
        event = MoveEvent(source=ent)
        on_move(event)

    def test_on_sleep_increases_energy(self):
        ent = Entity().add_component(Biochemistry(energy=50))
        event = SleepEvent(source=ent, energy_increase=30)
        on_sleep(event)
        assert ent.get_component(Biochemistry).energy == 80

    def test_on_sleep_energy_capped_at_200(self):
        ent = Entity().add_component(Biochemistry(energy=180))
        event = SleepEvent(source=ent, energy_increase=50)
        on_sleep(event)
        assert ent.get_component(Biochemistry).energy == 200

    def test_on_sleep_no_biochemistry(self):
        ent = Entity()
        event = SleepEvent(source=ent)
        on_sleep(event)

    def test_on_eat_increases_hunger(self):
        ent = Entity().add_component(Biochemistry(hunger=50))
        event = EatEvent(source=ent, nutrition=30)
        on_eat(event)
        assert ent.get_component(Biochemistry).hunger == 80

    def test_on_eat_hunger_capped_at_200(self):
        ent = Entity().add_component(Biochemistry(hunger=180))
        event = EatEvent(source=ent, nutrition=50)
        on_eat(event)
        assert ent.get_component(Biochemistry).hunger == 200

    def test_on_eat_no_biochemistry(self):
        ent = Entity()
        event = EatEvent(source=ent)
        on_eat(event)