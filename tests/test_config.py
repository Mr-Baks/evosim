import json

import pytest

import main
from config import (
    DEFAULT_FOUNDER_GENES,
    BalanceConfig,
    RunConfig,
    ScenarioConfig,
    SimConfig,
    WorldConfig,
    dump_config,
    load_config,
)
from entity import Breedable, Lineage, Movable, Plant, Vision
from genome import GeneNames, Genome
from traits import traits_for
from world import World


class TestDefaults:
    def test_default_layers(self):
        cfg = SimConfig()
        assert cfg.run == RunConfig(seed=1, ticks=1200, headless=False)
        assert cfg.scenario.world == WorldConfig(width=100, height=40)
        assert cfg.scenario.initial_plants == 120
        assert cfg.scenario.initial_creatures == 40
        assert cfg.scenario.founder_genes_jitter == 0.0
        assert isinstance(cfg.balance, BalanceConfig)

    def test_world_size_property(self):
        assert WorldConfig(30, 20).size == (30, 20)

    def test_default_balance_is_long_horizon_plateau(self):
        balance = SimConfig().balance
        assert balance.plant_energy_cap == 150
        assert balance.plant_fruit_nutrition == 20
        assert balance.mating_energy_cost == 110
        assert balance.mating_hunger_cost == 110
        assert balance.mating_cooldown_base == 100
        assert balance.sleep_energy_increase == 45

    def test_default_founder_has_low_metabolism(self):
        genes = {gene[0]: gene for gene in DEFAULT_FOUNDER_GENES}
        assert genes[GeneNames.METABOLISM] == (GeneNames.METABOLISM, -0.8, -0.7, 0.5)


class TestFromDict:
    def test_nested_overrides(self):
        cfg = SimConfig.from_dict({
            "run": {"seed": 7, "ticks": 50, "headless": True},
            "scenario": {
                "name": "sparse",
                "world": {"width": 30, "height": 20},
                "initial_plants": 10,
                "initial_creatures": 4,
                "creature_color": [1, 2, 3],
                "founder_genes": [["speed", -0.4, -0.4, 0.5]],
            },
            "balance": {"corpse_nutrition": 0},
        })
        assert cfg.run.seed == 7 and cfg.run.ticks == 50 and cfg.run.headless is True
        assert cfg.scenario.name == "sparse"
        assert cfg.scenario.world.size == (30, 20)
        assert cfg.scenario.creature_color == (1, 2, 3)
        assert cfg.scenario.founder_genes == (("speed", -0.4, -0.4, 0.5),)
        assert cfg.balance.corpse_nutrition == 0

    def test_partial_dict_keeps_defaults(self):
        cfg = SimConfig.from_dict({"run": {"seed": 3}})
        assert cfg.run.seed == 3
        assert cfg.run.ticks == RunConfig().ticks
        assert cfg.scenario == ScenarioConfig()

    def test_founder_jitter_roundtrips(self):
        cfg = SimConfig.from_dict({"scenario": {"founder_genes_jitter": 0.25}})
        assert cfg.scenario.founder_genes_jitter == 0.25
        assert cfg.to_dict()["scenario"]["founder_genes_jitter"] == 0.25

    def test_rejects_unknown_section(self):
        with pytest.raises(ValueError, match="Unknown config sections"):
            SimConfig.from_dict({"nope": {}})

    def test_rejects_unknown_key(self):
        with pytest.raises(ValueError, match="Unknown RunConfig keys"):
            SimConfig.from_dict({"run": {"nope": 1}})

    def test_rejects_unknown_balance_key(self):
        with pytest.raises(ValueError, match="Unknown BalanceConfig keys"):
            SimConfig.from_dict({"balance": {"nope": 1}})


class TestLoadConfig:
    def test_toml_file(self, tmp_path):
        path = tmp_path / "scenario.toml"
        path.write_text(
            "[run]\nseed = 42\nticks = 77\n\n"
            "[scenario]\ninitial_creatures = 5\n\n"
            "[scenario.world]\nwidth = 12\nheight = 8\n"
        )
        cfg = load_config(path, argv=[])
        assert cfg.run.seed == 42 and cfg.run.ticks == 77
        assert cfg.scenario.initial_creatures == 5
        assert cfg.scenario.world.size == (12, 8)

    def test_cli_overrides_toml(self, tmp_path):
        path = tmp_path / "scenario.toml"
        path.write_text("[run]\nseed = 42\n")
        cfg = load_config(path, argv=["--seed", "99", "--ticks", "10", "--headless"])
        assert cfg.run.seed == 99
        assert cfg.run.ticks == 10
        assert cfg.run.headless is True

    def test_cli_config_path(self, tmp_path):
        path = tmp_path / "scenario.toml"
        path.write_text("[run]\nseed = 5\n")
        cfg = load_config(None, argv=["--config", str(path)])
        assert cfg.run.seed == 5

    def test_dump_roundtrip(self, tmp_path):
        cfg = SimConfig(run=RunConfig(seed=11, ticks=20))
        out = tmp_path / "nested" / "config.json"
        dump_config(cfg, out)
        assert out.exists()
        roundtripped = SimConfig.from_dict(json.loads(out.read_text()))
        assert roundtripped.run.seed == 11 and roundtripped.run.ticks == 20


class TestMainWiring:
    def test_founder_genes_are_applied(self):
        cfg = SimConfig(
            scenario=ScenarioConfig(
                world=WorldConfig(10, 10),
                founder_genes_jitter=0.0,
            )
        )
        w = World(10, 10)
        main.make_creature(5, 5, w, cfg)
        genome = w.get_entity(5, 5).get_component(Genome)

        for name, a1, a2, dominance in DEFAULT_FOUNDER_GENES:
            gene = genome.genes[name]
            assert (gene.allele1, gene.allele2, gene.dominance) == (a1, a2, dominance)

        # Color genes derive from scenario.creature_color.
        assert genome.genes[GeneNames.COLOR_R].allele1 == (80 - 128) / 128
        assert genome.genes[GeneNames.COLOR_R].allele2 == (80 - 128) / 128

    def test_founder_components_are_derived_from_genome(self):
        custom = {
            GeneNames.SPEED: 0.2,
            GeneNames.FERTILITY: -1.0,
            GeneNames.VISION_RADIUS: -1.0,
        }
        founder_genes = tuple(
            (name, custom.get(name, a1), custom.get(name, a2), dominance)
            for name, a1, a2, dominance in DEFAULT_FOUNDER_GENES
        )
        cfg = SimConfig(
            scenario=ScenarioConfig(
                world=WorldConfig(10, 10),
                founder_genes=founder_genes,
            )
        )
        w = World(10, 10)
        main.make_creature(5, 5, w, cfg)

        entity = w.get_entity(5, 5)
        genome = entity.get_component(Genome)
        traits = traits_for(genome)

        assert entity.get_component(Movable).speed == pytest.approx(traits.speed.locomotion)
        assert entity.get_component(Breedable).fertility == pytest.approx(traits.fertility)
        assert entity.get_component(Vision).radius == round(traits.vision.radius)

        # None of these should be left at the component constructor defaults.
        assert entity.get_component(Movable).speed != Movable().speed
        assert entity.get_component(Breedable).fertility != Breedable().fertility
        assert entity.get_component(Vision).radius != Vision().radius

    def test_founder_color_matches_scenario(self):
        cfg = SimConfig(scenario=ScenarioConfig(world=WorldConfig(10, 10)))
        w = World(10, 10)
        main.make_creature(5, 5, w, cfg)
        genome = w.get_entity(5, 5).get_component(Genome)
        color = traits_for(genome).color
        assert (color.r, color.g, color.b) == pytest.approx(cfg.scenario.creature_color)

    def test_founder_lineage_starts_at_zero(self):
        cfg = SimConfig(scenario=ScenarioConfig(world=WorldConfig(10, 10)))
        w = World(10, 10)
        main.make_creature(5, 5, w, cfg)

        lineage = w.get_entity(5, 5).get_component(Lineage)
        assert lineage.generation == 0
        assert lineage.parents_eid is None

    def test_build_simulation_respects_counts(self):
        cfg = SimConfig(
            run=RunConfig(seed=123, headless=True),
            scenario=ScenarioConfig(
                world=WorldConfig(20, 20),
                initial_plants=5,
                initial_creatures=3,
            ),
        )
        sim = main.build_simulation(cfg)
        assert sim.tick == 0
        assert len(sim.world.index.get_with(Plant)) == 5
        assert len(sim.world.index.get_with(Movable)) == 3

    def test_scatter_raises_when_world_has_not_enough_space(self):
        cfg = SimConfig(
            run=RunConfig(seed=123, headless=True),
            scenario=ScenarioConfig(
                world=WorldConfig(2, 2),
                initial_plants=5,
                initial_creatures=0,
            ),
        )

        with pytest.raises(ValueError, match="only 4 free cells are available"):
            main.build_simulation(cfg)

    def test_scatter_places_overlapping_counts_on_distinct_cells(self):
        cfg = SimConfig(
            run=RunConfig(seed=123, headless=True),
            scenario=ScenarioConfig(
                world=WorldConfig(2, 2),
                initial_plants=2,
                initial_creatures=2,
            ),
        )
        sim = main.build_simulation(cfg)

        assert len(sim.world.index.get_with(Plant)) == 2
        assert len(sim.world.index.get_with(Movable)) == 2
        for y in range(2):
            for x in range(2):
                assert sim.world.get_entity(x, y) is not None

    def test_headless_run_advances_ticks(self):
        cfg = SimConfig(
            run=RunConfig(seed=1, ticks=25, headless=True),
            scenario=ScenarioConfig(world=WorldConfig(20, 20), initial_plants=5, initial_creatures=3),
        )
        sim = main.build_simulation(cfg)
        main.run_headless(sim, cfg.run.ticks)
        assert sim.tick == 25

    def test_importing_main_has_no_side_effects(self):
        # If main.py still ran the TUI loop on import, collecting tests would
        # block. Reaching this assertion means importing is safe.
        assert callable(main.main)
        assert callable(main.build_simulation)


class TestFounderJitter:
    def test_zero_jitter_keeps_genes_and_does_not_consume_rng(self, monkeypatch):
        genes = (
            (GeneNames.SPEED, -0.4, 0.2, 0.5),
            (GeneNames.MATING_DRIVE, 1.0, 0.4, 1.0),
        )

        def unexpected(*args):
            raise AssertionError("jitter=0 must not draw a random delta")

        monkeypatch.setattr(main.random, "uniform", unexpected)
        assert main.jitter_genes(genes, jitter=0.0) == genes

    @pytest.mark.parametrize("jitter", [-0.1, 1.1])
    def test_rejects_jitter_outside_unit_interval(self, jitter):
        with pytest.raises(ValueError, match="Founder gene jitter must be in"):
            main.jitter_genes(((GeneNames.SPEED, 0.0, 0.0, 0.5),), jitter=jitter)

    def test_same_delta_is_applied_to_both_alleles(self, monkeypatch):
        monkeypatch.setattr(main.random, "uniform", lambda low, high: 0.05)
        genes = ((GeneNames.SPEED, -0.4, 0.2, 0.5),)

        jittered = main.jitter_genes(genes, jitter=0.1)

        (name, a1, a2, dominance), = jittered
        assert name == GeneNames.SPEED
        assert a1 == pytest.approx(-0.35)
        assert a2 == pytest.approx(0.25)
        assert dominance == 0.5

    @pytest.mark.parametrize("allele", [-1.0, 1.0])
    def test_boundary_loci_are_left_unchanged(self, monkeypatch, allele):
        def unexpected(*args):
            raise AssertionError("a locus without headroom must not draw a delta")

        monkeypatch.setattr(main.random, "uniform", unexpected)
        genes = ((GeneNames.SPEED, allele, allele, 0.5),)

        assert main.jitter_genes(genes, jitter=0.25) == genes

    def test_jitter_range_shrinks_near_boundary(self, monkeypatch):
        calls = []
        def uniform(low, high):
            calls.append((low, high))
            return 0.04

        monkeypatch.setattr(main.random, "uniform", uniform)
        genes = ((GeneNames.SPEED, 0.95, 0.5, 0.5),)

        (_, a1, a2, _), = main.jitter_genes(genes, jitter=0.25)

        assert calls[0][0] == pytest.approx(-0.05)
        assert calls[0][1] == pytest.approx(0.05)
        assert a1 == pytest.approx(0.99)
        assert a2 == pytest.approx(0.54)

    def test_make_creature_applies_jitter_but_not_to_color_genes(self, monkeypatch):
        monkeypatch.setattr(main.random, "uniform", lambda low, high: 0.05)
        cfg = SimConfig(
            scenario=ScenarioConfig(
                world=WorldConfig(10, 10),
                founder_genes_jitter=0.1,
            )
        )
        world = World(10, 10)

        main.make_creature(5, 5, world, cfg)
        genome = world.get_entity(5, 5).get_component(Genome)

        speed = genome.genes[GeneNames.SPEED]
        assert speed.allele1 == pytest.approx(-0.55)
        assert speed.allele2 == pytest.approx(-0.55)

        # MATING_DRIVE starts at the upper bound, so it has no jitter headroom.
        mating = genome.genes[GeneNames.MATING_DRIVE]
        assert mating.allele1 == pytest.approx(1.0)
        assert mating.allele2 == pytest.approx(1.0)

        # Color genes are appended after jitter and must stay exact.
        color_r = genome.genes[GeneNames.COLOR_R]
        assert color_r.allele1 == pytest.approx((80 - 128) / 128)
        assert color_r.allele2 == pytest.approx((80 - 128) / 128)

    def test_each_founder_is_jittered_independently(self, monkeypatch):
        state = {"delta": 0.05}
        monkeypatch.setattr(main.random, "uniform", lambda low, high: state["delta"])
        cfg = SimConfig(
            scenario=ScenarioConfig(
                world=WorldConfig(10, 10),
                founder_genes_jitter=0.1,
            )
        )
        world = World(10, 10)

        main.make_creature(5, 5, world, cfg)
        state["delta"] = -0.05
        main.make_creature(6, 5, world, cfg)

        first = world.get_entity(5, 5).get_component(Genome).genes[GeneNames.SPEED]
        second = world.get_entity(6, 5).get_component(Genome).genes[GeneNames.SPEED]

        assert first.allele1 == pytest.approx(-0.55)
        assert second.allele1 == pytest.approx(-0.65)
        assert first.allele1 != second.allele1
