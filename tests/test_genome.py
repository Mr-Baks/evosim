"""Unit tests for Gene/Genome: phenotype, dominance, crossover, mutation,
phenotype scaling and recombination."""
import math
import random

import pytest

from genome import Gene, Genome


class TestGene:
    def test_defaults(self):
        g = Gene('speed', 0.2, -0.4)
        assert g.name == 'speed'
        assert g.allele1 == 0.2
        assert g.allele2 == -0.4
        assert g.dominant is True

    def test_phenotype_dominant_is_max(self):
        assert Gene('x', 0.2, 0.8).phenotype == pytest.approx(0.8)
        assert Gene('x', -0.9, -0.3).phenotype == pytest.approx(-0.3)

    def test_phenotype_recessive_is_mean(self):
        assert Gene('x', 0.2, 0.8, dominant=False).phenotype == pytest.approx(0.5)
        assert Gene('x', -1.0, 1.0, dominant=False).phenotype == pytest.approx(0.0)

    def test_crossover_takes_alleles_from_partner_when_roll_high(self, monkeypatch):
        g1 = Gene('x', 1.0, 1.0)
        g2 = Gene('x', -1.0, -1.0)
        # random.random is used for: a1 choice, a2 choice, mutation roll.
        # 0.9 >= 0.5 -> take partner allele; 0.9 >= mutation_rate -> no mutation.
        monkeypatch.setattr(random, 'random', lambda: 0.9)
        child = g1.crossover(g2, mutation_rate=0.05)
        assert child.allele1 == -1.0
        assert child.allele2 == -1.0
        assert child.name == 'x'

    def test_crossover_keeps_self_alleles_when_roll_low(self, monkeypatch):
        g1 = Gene('x', 1.0, 0.5)
        g2 = Gene('x', -1.0, -0.5)
        monkeypatch.setattr(random, 'random', lambda: 0.0)
        child = g1.crossover(g2, mutation_rate=0.0)
        assert child.allele1 == 1.0
        assert child.allele2 == 0.5

    def test_crossover_inherits_dominance(self):
        child = Gene('x', 0.1, 0.1, dominant=False).crossover(Gene('x', 0.2, 0.2))
        assert child.dominant is False

    def test_crossover_positive_mutation_is_clamped(self, monkeypatch):
        g = Gene('x', 1.0, 1.0)
        monkeypatch.setattr(random, 'random', lambda: 0.0)        # self allele + trigger mutation
        monkeypatch.setattr(random, 'uniform', lambda a, b: 5.0)  # push far out of range
        child = g.crossover(g, mutation_rate=1.0, strength=1.0)
        assert child.allele1 == 1.0
        assert child.allele2 == 1.0

    def test_crossover_negative_mutation_is_clamped(self, monkeypatch):
        g = Gene('x', -1.0, -1.0)
        monkeypatch.setattr(random, 'random', lambda: 0.0)
        monkeypatch.setattr(random, 'uniform', lambda a, b: -5.0)
        child = g.crossover(g, mutation_rate=1.0, strength=1.0)
        assert child.allele1 == -1.0
        assert child.allele2 == -1.0


class TestGenome:
    def test_init_indexes_genes_by_name(self):
        g = Genome([Gene('speed', 0.5, 0.5), Gene('size', 0.1, 0.1)])
        assert set(g.genes) == {'speed', 'size'}

    def test_empty_init(self):
        assert Genome().genes == {}

    def test_add_gene(self):
        g = Genome()
        gene = Gene('speed', 0.2, 0.2)
        g.add_gene(gene)
        assert g.genes['speed'] is gene

    def test_add_gene_replaces_existing(self):
        g = Genome([Gene('speed', 0.2, 0.2)])
        new = Gene('speed', 0.9, 0.9)
        g.add_gene(new)
        assert g.genes['speed'] is new

    def test_remove_gene(self):
        g = Genome([Gene('speed', 0.1, 0.1)])
        removed = g.remove_gene('speed')
        assert removed is not None
        assert 'speed' not in g.genes

    def test_remove_missing_gene_returns_none(self):
        assert Genome().remove_gene('nope') is None


class TestGetPhenotype:
    def test_missing_gene_returns_none_by_default(self):
        assert Genome().get_phenotype('nope') is None

    def test_missing_gene_returns_custom_default(self):
        assert Genome().get_phenotype('nope', default=0.7) == 0.7

    def test_raw_phenotype_without_scaling(self):
        g = Genome([Gene('x', 0.4, 0.4)])
        assert g.get_phenotype('x') == pytest.approx(0.4)

    @pytest.mark.parametrize('raw, lo, hi, expected', [
        (-1.0, 0, 1, 0.0),
        (1.0, 0, 1, 1.0),
        (0.0, 0, 1, 0.5),
        (-1.0, 0, 5, 0.0),
        (1.0, 0, 5, 5.0),
        (0.0, 0, 5, 2.5),
        (-1.0, 0, 200, 0.0),
        (1.0, 0, 200, 200.0),
        (0.0, 0, 200, 100.0),
        (0.0, 0, 256, 128.0),
    ])
    def test_scaling_maps_range(self, raw, lo, hi, expected):
        g = Genome([Gene('x', raw, raw)])
        assert g.get_phenotype('x', (lo, hi)) == pytest.approx(expected)

    @pytest.mark.parametrize('raw, lo, hi, expected', [
        (-1.0, 180, 700, 180.0),
        (1.0, 180, 700, 700.0),
        (0.0, 180, 700, math.sqrt(180 * 700)),
        (-1.0, 0.01, 2, 0.01),
        (1.0, 0.01, 2, 2.0),
        (0.0, 0.01, 2, math.sqrt(0.01 * 2)),
        (-1.0, 1, 5, 1.0),
        (1.0, 1, 5, 5.0),
        (0.0, 1, 5, math.sqrt(5)),
    ])
    def test_log_scaling_maps_geometrically(self, raw, lo, hi, expected):
        g = Genome([Gene('x', raw, raw)])
        assert g.get_phenotype('x', (lo, hi), log=True) == pytest.approx(expected)

    def test_log_scaling_endpoints(self):
        g = Genome([Gene('x', -1.0, -1.0)])
        assert g.get_phenotype('x', (250, 550), log=True) == pytest.approx(250.0)
        g = Genome([Gene('x', 1.0, 1.0)])
        assert g.get_phenotype('x', (250, 550), log=True) == pytest.approx(550.0)

    def test_log_scaling_missing_gene_uses_default(self):
        assert Genome().get_phenotype('x', (180, 700), default=33.0, log=True) == 33.0

    def test_scaling_with_missing_gene_uses_default(self):
        assert Genome().get_phenotype('x', (0, 1), default=0.25) == 0.25


class TestRecombine:
    def test_child_has_all_parental_genes(self):
        g1 = Genome([Gene('a', 0.0, 0.0), Gene('b', 1.0, 1.0)])
        g2 = Genome([Gene('a', 1.0, 1.0), Gene('b', 0.0, 0.0)])
        child = g1.recombine(g2)
        assert set(child.genes) == {'a', 'b'}

    def test_different_gene_sets_raise(self):
        g1 = Genome([Gene('a', 0.0, 0.0)])
        g2 = Genome([Gene('b', 0.0, 0.0)])
        with pytest.raises(ValueError):
            g1.recombine(g2)

    def test_empty_genomes_produce_empty_child(self):
        assert Genome().recombine(Genome()).genes == {}

    def test_without_mutation_alleles_come_from_parents(self):
        g1 = Genome([Gene('a', 0.2, 0.2)])
        g2 = Genome([Gene('a', 0.8, 0.8)])
        child = g1.recombine(g2, mutation_rate=0.0)
        gene = child.genes['a']
        assert gene.allele1 in (0.2, 0.8)
        assert gene.allele2 in (0.2, 0.8)
