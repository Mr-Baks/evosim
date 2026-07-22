import pytest
from entity import *


class TestComponent:
    def test_component_base(self):
        c = Component()
        assert isinstance(c, Component)

    def test_state_defaults(self):
        s = State()
        assert s.current == 'idle'
        assert s.states == set()

    def test_state_custom(self):
        s = State(current='eating', states={'eating', 'hungry'})
        assert s.current == 'eating'
        assert s.states == {'eating', 'hungry'}

    def test_render_defaults(self):
        r = Render()
        assert r.symbol == '?'
        assert r.color == (255, 255, 255)
        assert r.is_visible is True

    def test_render_custom(self):
        r = Render(symbol='C', color=(100, 200, 50), is_visible=False)
        assert r.symbol == 'C'
        assert r.color == (100, 200, 50)
        assert r.is_visible is False

    def test_movable_defaults(self):
        m = Movable()
        assert m.speed == 1
        assert m.movement_accumulator == 0

    def test_biochemistry_defaults(self):
        b = Biochemistry()
        assert b.energy == 100
        assert b.hunger == 100
        assert b.health == 100

    def test_biochemistry_custom(self):
        b = Biochemistry(energy=50, hunger=30, health=80)
        assert b.energy == 50
        assert b.hunger == 30
        assert b.health == 80

    def test_eatable(self):
        e = Eatable(nutrition=25)
        assert e.nutrition == 25

    def test_breedable_defaults(self):
        b = Breedable()
        assert b.fertility == 100
        assert b.cooldown == 30

    def test_breedable_custom(self):
        b = Breedable(fertility=80, cooldown=10)
        assert b.fertility == 80
        assert b.cooldown == 10

    def test_vision_defaults(self):
        v = Vision()
        assert v.radius == 4
        assert v.visibles == set()

    def test_vision_custom(self):
        v = Vision(radius=5)
        assert v.radius == 5

    def test_plant_defaults(self):
        plant = Plant()
        assert plant.energy == 0
        assert plant.energy_increase == 2
        assert plant.fructify_threshold == 80
        assert plant.fruit_nutrition == 25

    def test_plant_custom(self):
        plant = Plant(energy=50, energy_increase=5, fructify_threshold=90, fruit_nutrition=30)
        assert plant.energy == 50
        assert plant.energy_increase == 5
        assert plant.fructify_threshold == 90
        assert plant.fruit_nutrition == 30


class TestEntity:
    def test_entity_init(self):
        e = Entity(10, 20)
        assert e.x == 10
        assert e.y == 20
        assert e.components == set()
        assert e.components_dict == {}

    def test_add_component(self):
        e = Entity()
        bio = Biochemistry()
        result = e.add_component(bio)
        assert result is e
        assert Biochemistry in e.components
        assert e.components_dict[Biochemistry] is bio

    def test_add_multiple_components(self):
        e = Entity()
        e.add_component(Biochemistry())
        e.add_component(Movable())
        e.add_component(Vision())
        assert len(e.components) == 3
        assert Biochemistry in e.components
        assert Movable in e.components
        assert Vision in e.components

    def test_has_component(self):
        e = Entity()
        e.add_component(Biochemistry())
        assert e.has_component(Biochemistry) is True
        assert e.has_component(Movable) is False

    def test_get_component(self):
        e = Entity()
        bio = Biochemistry(energy=50)
        e.add_component(bio)
        result = e.get_component(Biochemistry)
        assert result is bio
        assert result.energy == 50

    def test_get_component_missing(self):
        e = Entity()
        result = e.get_component(Biochemistry)
        assert result is None

    def test_remove_component(self):
        e = Entity()
        bio = Biochemistry()
        e.add_component(bio)
        removed = e.remove_component(Biochemistry)
        assert removed is None
        assert Biochemistry not in e.components
        assert Biochemistry not in e.components_dict

    def test_remove_component_missing(self):
        e = Entity()
        with pytest.raises(KeyError):
            e.remove_component(Biochemistry)

    def test_chained_add_components(self):
        e = Entity().add_component(Biochemistry()).add_component(Movable())
        assert e.has_component(Biochemistry)
        assert e.has_component(Movable)