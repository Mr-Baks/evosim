"""Tests for traits.py: gene -> phenotype derivation and memoization."""
import pytest

from genome import Gene, GeneNames, Genome
from traits import derive, traits_for


ALL_GENES = [
    GeneNames.SPEED,
    GeneNames.METABOLISM,
    GeneNames.FERTILITY,
    GeneNames.SENESCENCE_SHAPE,
    GeneNames.WEAR_RESISTANCE,
    GeneNames.REGENERATION_THRESHOLD,
    GeneNames.REGENERATION_INCREASE,
    GeneNames.HUNGER_DRIVE,
    GeneNames.SLEEP_DRIVE,
    GeneNames.MATING_DRIVE,
    GeneNames.EXPLORATION_DRIVE,
    GeneNames.MATING_ENERGY_THRESHOLD,
    GeneNames.MATING_HUNGER_THRESHOLD,
    GeneNames.COLOR_R,
    GeneNames.COLOR_G,
    GeneNames.COLOR_B,
    GeneNames.VISION_RADIUS
]


def genome_at(value: float) -> Genome:
    """All genes share one raw allele value; dominant -> phenotype == value."""
    return Genome([Gene(name, value, value) for name in ALL_GENES])


class TestDeriveBounds:
    def test_minus_one_gives_lower_bounds(self):
        t = derive(genome_at(-1.0))
        assert t.metabolism == pytest.approx(0.1)
        assert t.speed.locomotion == pytest.approx(0.0)
        assert t.speed.metabolic == pytest.approx(1.0)
        assert t.fertility == pytest.approx(0.0)
        assert t.senescence_shape == pytest.approx(1.0)
        assert t.wear_resistance.aging == pytest.approx(180.0)
        assert t.wear_resistance.cooldown == pytest.approx(0.001)
        assert t.regeneration_threshold == pytest.approx(0.0)
        assert t.regeneration_increase == pytest.approx(1.0)
        assert t.hunger_drive == pytest.approx(0.0)
        assert t.sleep_drive == pytest.approx(0.0)
        assert t.mating_drive == pytest.approx(0.0)
        assert t.exploration_drive == pytest.approx(0.0)
        assert t.mating_energy_threshold == pytest.approx(0.0)
        assert t.mating_hunger_threshold == pytest.approx(0.0)
        assert (t.color.r, t.color.g, t.color.b) == pytest.approx((0.0, 0.0, 0.0))

    def test_zero_gives_midpoints(self):
        t = derive(genome_at(0.0))
        assert t.metabolism == pytest.approx((0.1 * 2) ** 0.5)
        assert t.speed.locomotion == pytest.approx(2.5)
        assert t.speed.metabolic == pytest.approx(2.0)
        assert t.fertility == pytest.approx(0.5)
        assert t.senescence_shape == pytest.approx(2.0)
        assert t.wear_resistance.aging == pytest.approx((180 * 700) ** 0.5)
        assert t.wear_resistance.cooldown == pytest.approx((0.001 * 300) ** 0.5)
        assert t.regeneration_threshold == pytest.approx(0.5)
        assert t.regeneration_increase == pytest.approx(3.0)
        assert t.hunger_drive == pytest.approx(0.5)
        assert t.sleep_drive == pytest.approx(0.5)
        assert t.mating_drive == pytest.approx(0.5)
        assert t.exploration_drive == pytest.approx(0.5)
        assert t.mating_energy_threshold == pytest.approx(100.0)
        assert t.mating_hunger_threshold == pytest.approx(100.0)
        assert (t.color.r, t.color.g, t.color.b) == pytest.approx((128.0, 128.0, 128.0))

    def test_plus_one_gives_upper_bounds(self):
        t = derive(genome_at(1.0))
        assert t.metabolism == pytest.approx(2.0)
        assert t.speed.locomotion == pytest.approx(5.0)
        assert t.speed.metabolic == pytest.approx(3.0)
        assert t.fertility == pytest.approx(1.0)
        assert t.senescence_shape == pytest.approx(3.0)
        assert t.wear_resistance.aging == pytest.approx(700.0)
        assert t.wear_resistance.cooldown == pytest.approx(300.0)
        assert t.regeneration_threshold == pytest.approx(1.0)
        assert t.regeneration_increase == pytest.approx(5.0)
        assert t.hunger_drive == pytest.approx(1.0)
        assert t.sleep_drive == pytest.approx(1.0)
        assert t.mating_drive == pytest.approx(1.0)
        assert t.exploration_drive == pytest.approx(1.0)
        assert t.mating_energy_threshold == pytest.approx(200.0)
        assert t.mating_hunger_threshold == pytest.approx(200.0)
        assert (t.color.r, t.color.g, t.color.b) == pytest.approx((256.0, 256.0, 256.0))

    def test_missing_vision_gene_uses_default(self):
        genes = [Gene(name, 0.75, 0.75) for name in ALL_GENES if name != GeneNames.VISION_RADIUS]
        t = derive(Genome(genes))

        assert t.vision.radius == pytest.approx(7.5)
        assert t.vision.metabolic == pytest.approx(1.2)


class TestPleiotropy:
    def test_one_gene_drives_two_speed_effects(self):
        t = derive(genome_at(0.5))
        assert t.speed.locomotion == pytest.approx(3.75)   # (0, 5)
        assert t.speed.metabolic == pytest.approx(2.5)     # (1, 3)

    def test_one_gene_drives_two_wear_effects(self):
        t = derive(genome_at(0.5))
        assert t.wear_resistance.aging == pytest.approx(180 * (700 / 180) ** 0.75)
        assert t.wear_resistance.cooldown == pytest.approx(0.001 * (300 / 0.001) ** 0.75)


class TestTraitsFor:
    def test_memoized_on_genome(self):
        genome = genome_at(0.2)
        assert traits_for(genome) is traits_for(genome)

    def test_computes_only_once(self):
        genome = genome_at(0.2)
        calls = {'n': 0}
        original = genome.get_phenotype

        def counting(*args, **kwargs):
            calls['n'] += 1
            return original(*args, **kwargs)

        genome.get_phenotype = counting

        traits_for(genome)
        first = calls['n']
        traits_for(genome)

        assert first > 0
        assert calls['n'] == first


class TestFormulas:
    """Physiological formulas now live on Traits and are used by systems/tests."""

    def setup_method(self):
        self.t = derive(genome_at(0.0))
        self.lifespan = self.t.wear_resistance.aging            # sqrt(180 * 700)
        self.base = self.t.metabolism * self.t.speed.metabolic ** 2 * self.t.vision.metabolic

    def test_wear_saturates_at_one(self):
        assert self.t.wear(0) == pytest.approx(0.0)
        assert self.t.wear(self.lifespan / 2) == pytest.approx(0.5)
        assert self.t.wear(self.lifespan) == pytest.approx(1.0)
        assert self.t.wear(self.lifespan * 2) == pytest.approx(1.0)

    def test_vitality_is_one_minus_wear_to_the_shape(self):
        # senescence_shape = 2 for this genome
        assert self.t.vitality(0) == pytest.approx(1.0)
        assert self.t.vitality(self.lifespan / 2) == pytest.approx(1 - 0.5 ** 2)
        assert self.t.vitality(self.lifespan) == pytest.approx(0.0)
        assert self.t.vitality(self.lifespan * 3) == pytest.approx(0.0)

    def test_max_health_scales_vitality_to_100(self):
        assert self.t.max_health(1.0) == pytest.approx(100.0)
        assert self.t.max_health(0.25) == pytest.approx(25.0)
        assert self.t.max_health(0.0) == pytest.approx(0.0)

    def test_energy_drain_is_heavier_when_frail(self):
        assert self.t.energy_drain(1.0) == pytest.approx(self.base * 1.0)
        assert self.t.energy_drain(0.0) == pytest.approx(self.base * 2.0)

    def test_hunger_drain_scales_with_lifespan(self):
        assert self.t.hunger_drain() == pytest.approx(self.base * self.lifespan / 710)

    def test_effective_fertility_applies_gate_and_shape(self):
        shape = 1 - self.t.senescence_shape / 3
        assert self.t.effective_fertility(1.0) == pytest.approx(self.t.fertility * shape)
        # vitality below 0.5 halves the gate
        assert self.t.effective_fertility(0.25) == pytest.approx(self.t.fertility * 0.5 * shape)
