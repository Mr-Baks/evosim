"""Tests for the senescence / accumulated-wear ageing model.

The ageing model lives in ``biochemistry_system``:

    age      += 1 each tick                        # chronological age in ticks
    wear      = min(1, age / wear_resistance)      # L = wear_resistance
    vitality  = max(0, 1 - wear ** senescence_shape)
    max_health = vitality * 100
    fertility  = fertility_gene * min(1, vitality * 2) * (1 - a / 3)

Death is *emergent*, not timer-driven: at the end of life vitality reaches 0,
so ``max_health`` is 0, ``health`` clamps to 0 and a ``DeathCommand`` is
pushed. ``wear_resistance`` is the scale (lifespan ``L``) and
``senescence_shape`` is the shape (Weibull exponent ``a``).
"""
import pytest

from commands import CommandQueue, DeathCommand
from entity import Biochemistry, Breedable, Entity, Movable
from genome import GeneNames, Genome
from systems import biochemistry_system
from traits import traits_for
from tests.helpers import default_genes
from world import World


def make_aging_entity(world, age=0, x=5, y=5, **gene_overrides):
    """A minimal creature that ``biochemistry_system`` accepts.

    Includes a ``Breedable`` because fertility is written every tick.
    """
    e = (
        Entity()
        .add_component(Biochemistry(age=age))
        .add_component(CommandQueue())
        .add_component(Breedable())
        .add_component(Movable())
        .add_component(default_genes(**gene_overrides))
    )
    world.place_entity(e, x, y)
    return e


SHORT_LIFE = {GeneNames.WEAR_RESISTANCE: -1.0}    # L = 180
LONG_LIFE = {GeneNames.WEAR_RESISTANCE: 1.0}      # L = 700
LINEAR = {GeneNames.SENESCENCE_SHAPE: -1.0}       # a = 1
QUADRATIC = {GeneNames.SENESCENCE_SHAPE: 0.0}     # a = 2
CUBIC = {GeneNames.SENESCENCE_SHAPE: 1.0}         # a = 3


class TestAgeAccumulation:
    def test_age_increments_each_tick(self):
        w = World(10, 10)
        e = make_aging_entity(w, age=0)
        biochemistry_system({e}, w)
        assert e.get_component(Biochemistry).age == 1

    def test_age_is_chronological_ticks(self):
        w = World(10, 10)
        e = make_aging_entity(w, age=41)
        biochemistry_system({e}, w)
        assert e.get_component(Biochemistry).age == 42

    def test_age_is_independent_of_genes(self):
        # Unlike wear, age must not be re-scaled by any gene.
        w1, w2 = World(10, 10), World(10, 10)
        a = make_aging_entity(w1, age=10, **SHORT_LIFE)
        b = make_aging_entity(w2, age=10, **LONG_LIFE)
        biochemistry_system({a}, w1)
        biochemistry_system({b}, w2)
        assert a.get_component(Biochemistry).age == b.get_component(Biochemistry).age == 11


class TestVitality:
    def test_young_creature_is_nearly_full_vitality(self):
        w = World(10, 10)
        e = make_aging_entity(w, age=0, **LONG_LIFE, **LINEAR)
        biochemistry_system({e}, w)
        bio = e.get_component(Biochemistry)
        assert bio.vitality == pytest.approx(1 - 1 / 700)
        assert bio.max_health == pytest.approx(bio.vitality * 100)

    def test_vitality_follows_wear_curve(self):
        # age 90, L 180, a = 1  ->  vitality = 1 - 0.5 = 0.5
        w = World(10, 10)
        e = make_aging_entity(w, age=89, **SHORT_LIFE, **LINEAR)
        biochemistry_system({e}, w)
        assert e.get_component(Biochemistry).vitality == pytest.approx(0.5)

    def test_vitality_is_monotonically_decreasing(self):
        vitality = []
        for start_age in (0, 44, 89, 134):
            w = World(10, 10)
            e = make_aging_entity(w, age=start_age, **SHORT_LIFE, **LINEAR)
            biochemistry_system({e}, w)
            vitality.append(e.get_component(Biochemistry).vitality)
        assert vitality == sorted(vitality, reverse=True)
        assert len(set(vitality)) == len(vitality)

    def test_vitality_never_goes_negative_past_lifespan(self):
        w = World(10, 10)
        e = make_aging_entity(w, age=400, **SHORT_LIFE, **LINEAR)
        biochemistry_system({e}, w)
        assert e.get_component(Biochemistry).vitality == 0.0

    def test_wear_is_capped_at_one(self):
        w = World(10, 10)
        e = make_aging_entity(w, age=400, **SHORT_LIFE, **LINEAR)
        biochemistry_system({e}, w)
        traits = traits_for(e.get_component(Genome))
        assert traits.wear(401) == 1.0


class TestHealthScaling:
    def test_max_health_equals_vitality_times_100(self):
        w = World(10, 10)
        e = make_aging_entity(w, age=89, **SHORT_LIFE, **LINEAR)
        biochemistry_system({e}, w)
        bio = e.get_component(Biochemistry)
        assert bio.vitality == pytest.approx(0.5)
        assert bio.max_health == pytest.approx(50.0)

    def test_health_is_clamped_to_max_health(self):
        # Full health (100) is capped by the aged max_health (50).
        w = World(10, 10)
        e = make_aging_entity(w, age=89, **SHORT_LIFE, **LINEAR)
        biochemistry_system({e}, w)
        assert e.get_component(Biochemistry).health == pytest.approx(50.0)


class TestEmergentDeath:
    def test_death_at_end_of_life(self):
        w = World(10, 10)
        e = make_aging_entity(w, age=179, **SHORT_LIFE, **LINEAR)
        biochemistry_system({e}, w)
        bio = e.get_component(Biochemistry)
        assert bio.age == 180
        assert bio.vitality == pytest.approx(0.0)
        assert bio.health == 0
        queue = e.get_component(CommandQueue)
        assert len(queue.queue) == 1
        assert isinstance(queue.queue[0], DeathCommand)

    def test_no_death_while_vitality_positive(self):
        w = World(10, 10)
        e = make_aging_entity(w, age=100, **SHORT_LIFE, **LINEAR)
        biochemistry_system({e}, w)
        queue = e.get_component(CommandQueue)
        assert not any(isinstance(c, DeathCommand) for c in queue.queue)

    def test_longer_lifespan_delays_death(self):
        w_short = World(10, 10)
        short = make_aging_entity(w_short, age=179, **SHORT_LIFE, **LINEAR)
        biochemistry_system({short}, w_short)
        assert short.get_component(Biochemistry).vitality == pytest.approx(0.0)

        w_long = World(10, 10)
        long = make_aging_entity(w_long, age=179, **LONG_LIFE, **LINEAR)
        biochemistry_system({long}, w_long)
        assert long.get_component(Biochemistry).vitality > 0.7


class TestSenescenceShape:
    def test_shape_changes_curve_not_scale(self):
        # At half a lifespan both share wear = 0.5, but a = 3 accumulates
        # less damage than a = 1, so vitality is higher.
        w_linear = World(10, 10)
        linear = make_aging_entity(w_linear, age=349, **LONG_LIFE, **LINEAR)
        biochemistry_system({linear}, w_linear)

        w_cubic = World(10, 10)
        cubic = make_aging_entity(w_cubic, age=349, **LONG_LIFE, **CUBIC)
        biochemistry_system({cubic}, w_cubic)

        v_linear = linear.get_component(Biochemistry).vitality
        v_cubic = cubic.get_component(Biochemistry).vitality
        assert v_linear == pytest.approx(0.5)
        assert v_cubic == pytest.approx(1 - 0.5 ** 3)
        assert v_cubic > v_linear

    def test_end_of_life_shared_by_all_shapes(self):
        # Whatever the shape, vitality reaches 0 exactly at age = L.
        for shape in (-1.0, 0.0, 1.0):
            w = World(10, 10)
            e = make_aging_entity(
                w, age=179, **SHORT_LIFE,
                **{GeneNames.SENESCENCE_SHAPE: shape},
            )
            biochemistry_system({e}, w)
            assert e.get_component(Biochemistry).vitality == pytest.approx(0.0)

    def test_quadratic_curve_between_linear_and_cubic(self):
        w = World(10, 10)
        e = make_aging_entity(w, age=349, **LONG_LIFE, **QUADRATIC)
        biochemistry_system({e}, w)
        # wear = 0.5, a = 2  ->  vitality = 1 - 0.25 = 0.75
        assert e.get_component(Biochemistry).vitality == pytest.approx(0.75)


class TestReproductiveSenescence:
    def test_fertility_scales_with_vitality(self):
        w = World(10, 10)
        e = make_aging_entity(w, age=0, **LONG_LIFE, **LINEAR,
                              **{GeneNames.FERTILITY: 1.0})
        biochemistry_system({e}, w)
        traits = traits_for(e.get_component(Genome))
        expected = traits.effective_fertility(traits.vitality(1))
        assert e.get_component(Breedable).fertility == pytest.approx(expected)
        assert e.get_component(Breedable).fertility == pytest.approx(2 / 3)

    def test_max_shape_sterilises(self):
        # (1 - a / 3) is 0 when a = 3, so the longest-lived gene is sterile.
        w = World(10, 10)
        e = make_aging_entity(w, age=0, **LONG_LIFE, **CUBIC,
                              **{GeneNames.FERTILITY: 1.0})
        biochemistry_system({e}, w)
        assert e.get_component(Breedable).fertility == pytest.approx(0.0)

    def test_fertility_uses_vitality_gate_below_half(self):
        # vitality = 0.25 -> min(1, 2 * 0.25) = 0.5, shape factor 2/3.
        w = World(10, 10)
        e = make_aging_entity(w, age=134, **SHORT_LIFE, **LINEAR,
                              **{GeneNames.FERTILITY: 1.0})
        biochemistry_system({e}, w)
        assert e.get_component(Biochemistry).vitality == pytest.approx(0.25)
        assert e.get_component(Breedable).fertility == pytest.approx(0.5 * 2 / 3)
