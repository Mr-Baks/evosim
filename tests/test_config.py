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
from entity import Lineage, Movable, Plant
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
        cfg = SimConfig(scenario=ScenarioConfig(world=WorldConfig(10, 10)))
        w = World(10, 10)
        main.make_creature(5, 5, w, cfg)
        genome = w.get_entity(5, 5).get_component(Genome)

        for name, a1, a2, dominance in DEFAULT_FOUNDER_GENES:
            gene = genome.genes[name]
            assert (gene.allele1, gene.allele2, gene.dominance) == (a1, a2, dominance)

        # Color genes derive from scenario.creature_color.
        assert genome.genes[GeneNames.COLOR_R].allele1 == (80 - 128) / 128
        assert genome.genes[GeneNames.COLOR_R].allele2 == (80 - 128) / 128

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
        # _scatter skips occupied cells, so exact counts are not guaranteed;
        # the point is that the tiny scenario counts (not 120/40) are used.
        assert 0 < len(sim.world.index.get_with(Movable)) <= 3
        assert 0 < len(sim.world.index.get_with(Plant)) <= 5

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
