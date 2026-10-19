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
]


def genome_at(value: float) -> Genome:
    """All genes share one raw allele value; dominant -> phenotype == value."""
    return Genome([Gene(name, value, value) for name in ALL_GENES])


class TestDeriveBounds:
    def test_minus_one_gives_lower_bounds(self):
        t = derive(genome_at(-1.0))
        assert t.metabolism == pytest.approx(0.01)
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
        assert t.metabolism == pytest.approx((0.01 * 2) ** 0.5)
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

    def test_matches_direct_lookup(self):
        genome = genome_at(0.37)
        t = traits_for(genome)
        gp = genome.get_phenotype
        assert t.metabolism == gp(GeneNames.METABOLISM, (0.01, 2), log=True)
        assert t.speed.locomotion == gp(GeneNames.SPEED, (0, 5))
        assert t.speed.metabolic == gp(GeneNames.SPEED, (1, 3))
        assert t.wear_resistance.aging == gp(GeneNames.WEAR_RESISTANCE, (180, 700), log=True)
        assert t.wear_resistance.cooldown == gp(GeneNames.WEAR_RESISTANCE, (0.001, 300), log=True)
        assert t.color.r == gp(GeneNames.COLOR_R, (0, 256))
