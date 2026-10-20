from entity import *


def test_vision_visibles_not_shared():
    # default_factory must give each Vision its own list, not a shared one.
    a = Vision()
    b = Vision()
    a.visibles.append('x')
    assert b.visibles == []


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
        assert removed is bio
        assert Biochemistry not in e.components
        assert Biochemistry not in e.components_dict

    def test_remove_component_missing(self):
        e = Entity()
        assert e.remove_component(Biochemistry) is None

    def test_chained_add_components(self):
        e = Entity().add_component(Biochemistry()).add_component(Movable())
        assert e.has_component(Biochemistry)
        assert e.has_component(Movable)
