import argparse
import json
import tomllib
from dataclasses import asdict, dataclass, field, fields, replace
from pathlib import Path
from typing import Any, Mapping

from genome import GeneNames


@dataclass(frozen=True)
class WorldConfig:
    width: int = 100
    height: int = 40

    @property
    def size(self) -> tuple[int, int]:
        return (self.width, self.height)


FounderGene = tuple[str, float, float, float]

DEFAULT_FOUNDER_GENES: tuple[FounderGene] = (
    (GeneNames.SPEED, -0.6, -0.6, 0.5),
    (GeneNames.HUNGER_DRIVE, 0.5, 0.5, 1),
    (GeneNames.SLEEP_DRIVE, 0.5, 0.5, 1),
    (GeneNames.EXPLORATION_DRIVE, 0.5, 0.5, 1),
    (GeneNames.METABOLISM, -0.8, -0.7, 0.5),
    (GeneNames.MATING_DRIVE, 1.0, 1.0, 1),
    (GeneNames.MATING_ENERGY_THRESHOLD, -0.2, -0.2, 1),
    (GeneNames.MATING_HUNGER_THRESHOLD, -0.2, -0.2, 1),
    (GeneNames.FERTILITY, 0.5, 0.5, 0.5),
    (GeneNames.REGENERATION_INCREASE, 0.1, 0.1, 1),
    (GeneNames.REGENERATION_THRESHOLD, -0.2, 0.5, 0.5),
    (GeneNames.SENESCENCE_SHAPE, -0.5, -0.3, 0.5),
    (GeneNames.WEAR_RESISTANCE, 0.0, 0.0, 1),
    (GeneNames.CROWD_PREFERENCE, -0.5, -0.5, 1),
    (GeneNames.PLANT_APPETENCE, 0.5, 0.5, 1),
    (GeneNames.FOOD_APPETENCE, 0.8, 0.8, 1),
)


@dataclass(frozen=True)
class ScenarioConfig:
    name: str = "baseline"
    world: WorldConfig = field(default_factory=WorldConfig)
    initial_plants: int = 120
    initial_creatures: int = 40
    creature_color: tuple[int, int, int] = (80, 120, 200)
    founder_genes: tuple[FounderGene, ...] = DEFAULT_FOUNDER_GENES


@dataclass(frozen=True)
class BalanceConfig:
    """World "physics": parameters that shape population dynamics."""
    plant_energy_increase: int = 2
    plant_energy_cap: int = 150
    plant_fructify_min: int = 70
    plant_fructify_max: int = 90
    plant_fruit_nutrition: int = 20
    
    corpse_nutrition: int = 50
    
    health_decay: float = 1.0
    regeneration_energy_min: float = 60.0
    regeneration_hunger_min: float = 60.0
    
    mating_energy_cost: float = 110.0
    mating_hunger_cost: float = 110.0
    mating_cooldown_base: int = 100
    mating_cooldown_scaling: tuple[float, float] = (0.001, 300.0)
    fertility_min: float = 0.2
    
    sleep_energy_increase: int = 45
    sleep_target_energy: float = 200.0
    
    hunger_scale: float = 200.0
    energy_scale: float = 200.0
    food_saturation: int = 3
    partner_saturation: int = 3
    creature_saturation: int = 5
    plant_saturation: int = 5
    eat_reconsider_chance: float = 0.3
    wander_radius: int = 8
    wander_fallback_radius: int = 6
    wander_angles_count: int = 8

    max_crowd_count: int = 15
    max_crowd_penalty_factor: float = 0.65
    crowd_count_threshold: int = 3
    crowd_radius: int = 5


@dataclass(frozen=True)
class RunConfig:
    seed: int = 1
    ticks: int = 1200
    record_every: int = 10
    output_dir: str = "results"
    headless: bool = False
    tickspeed: int = 10
    fps: int = 10


@dataclass(frozen=True)
class SimConfig:
    run: RunConfig = field(default_factory=RunConfig)
    scenario: ScenarioConfig = field(default_factory=ScenarioConfig)
    balance: BalanceConfig = field(default_factory=BalanceConfig)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "SimConfig":
        """Build a config from a nested dict (e.g. parsed TOML/JSON)."""
        data = dict(data)
        run = RunConfig(**_section(RunConfig, data.pop("run", {})))

        scenario_data = dict(data.pop("scenario", {}))
        world = WorldConfig(**_section(WorldConfig, scenario_data.pop("world", {})))
        if "founder_genes" in scenario_data:
            scenario_data["founder_genes"] = tuple(tuple(g) for g in scenario_data["founder_genes"])
        if "creature_color" in scenario_data:
            scenario_data["creature_color"] = tuple(scenario_data["creature_color"])
        scenario = ScenarioConfig(world=world, **_section(ScenarioConfig, scenario_data))

        balance = BalanceConfig(**_section(BalanceConfig, data.pop("balance", {})))

        if data:
            raise ValueError(f"Unknown config sections: {sorted(data)}")
        return cls(run=run, scenario=scenario, balance=balance)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _section(cls: type, data: Mapping[str, Any]) -> dict[str, Any]:
    """Validate that ``data`` only contains keys declared by ``cls``."""
    data = dict(data)
    unknown = set(data) - {f.name for f in fields(cls)}
    if unknown:
        raise ValueError(f"Unknown {cls.__name__} keys: {sorted(unknown)}")
    return data


def _cli_overrides(argv: list[str] | None) -> dict[str, Any]:
    parser = argparse.ArgumentParser(description="EvoSim config overrides")
    parser.add_argument("--config", type=str, default=None, help="Path to a TOML config file")
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--ticks", type=int, default=None)
    parser.add_argument("--record-every", dest="record_every", type=int, default=None)
    parser.add_argument("--output-dir", dest="output_dir", type=str, default=None)
    parser.add_argument("--tickspeed", type=int, default=None)
    parser.add_argument("--fps", type=int, default=None)
    parser.add_argument("--headless", action=argparse.BooleanOptionalAction, default=None)
    return vars(parser.parse_args(argv))


def load_config(path: str | Path | None = None, argv: list[str] | None = None) -> SimConfig:
    """Load a ``SimConfig`` from defaults, an optional TOML file and CLI flags."""
    overrides = _cli_overrides(argv)
    if path is None:
        path = overrides.pop("config", None)

    data: Mapping[str, Any] = {}
    if path:
        with open(path, "rb") as f:
            data = tomllib.load(f)
    cfg = SimConfig.from_dict(data)

    run_overrides = {k: v for k, v in overrides.items() if v is not None}
    return replace(cfg, run=replace(cfg.run, **run_overrides))


def dump_config(cfg: SimConfig, path: str | Path) -> None:
    """Persist the effective config next to a run's results for reproducibility."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(cfg.to_dict(), f, indent=2, sort_keys=True)
