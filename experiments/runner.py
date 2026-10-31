"""Minimal experiment runner: conditions x seeds with a fixed feature matrix.

Usage:
    python experiments/runner.py --conditions baseline crowd_off --seeds 1 2 3 --ticks 20000
    python experiments/runner.py --config my.toml --conditions jitter_0.1 --seeds 1 --ticks 5000
    python experiments/runner.py --conditions baseline crowd_off --seeds 1 2 --jobs 4

Each run writes ``config.json``, ``population.csv``, ``features.csv``,
``births.csv`` and ``deaths.csv`` to
``<out>/<experiment>/<condition>/seed=<seed>/``. The fixed run plan and feature
schema are written to ``<out>/<experiment>/matrix.json`` before the simulations
start. Final counts for the whole batch go to ``<out>/<experiment>/summary.csv``.
"""
import argparse
import csv
import json
import random
import sys
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, replace
from pathlib import Path

if __package__ is None or __package__ == '':
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import main
from config import SimConfig, dump_config, load_config
from entity import Eatable, Lineage, Movable, Plant
from event_bus import BirthEvent, DeathEvent
from features import GENE_NAMES, TRAIT_COLUMNS, feature_header
from genome import GeneNames


@dataclass(frozen=True)
class RunSpec:
    experiment: str
    condition: str
    seed: int
    ticks: int
    sample_every: int
    config: SimConfig

def _with_gene(cfg: SimConfig, name: str, value: float) -> SimConfig:
    genes = tuple(
        (
            gene_name,
            value if gene_name == name else allele1,
            value if gene_name == name else allele2,
            dominance,
        )
        for gene_name, allele1, allele2, dominance in cfg.scenario.founder_genes
    )
    return replace(cfg, scenario=replace(cfg.scenario, founder_genes=genes))


CONDITIONS = {
    'baseline': lambda cfg: cfg,
    'jitter_0.1': lambda cfg: replace(
        cfg, scenario=replace(cfg.scenario, founder_genes_jitter=0.1)
    ),
    'crowd_off': lambda cfg: _with_gene(cfg, GeneNames.CROWD_PREFERENCE, 0.0),
    'exploration_off': lambda cfg: _with_gene(cfg, GeneNames.EXPLORATION_DRIVE, 0.0),
    'plant_off': lambda cfg: _with_gene(cfg, GeneNames.PLANT_APPETENCE, 0.0),
    'food_off': lambda cfg: _with_gene(cfg, GeneNames.FOOD_APPETENCE, 0.0),
}


def run(spec: RunSpec) -> dict:
    run_dir = Path(spec.config.run.output_dir)
    dump_config(spec.config, run_dir / 'config.json')

    births = 0
    deaths = 0

    def on_birth(event: BirthEvent) -> None:
        nonlocal births
        births += 1

    def on_death(event: DeathEvent) -> None:
        nonlocal deaths
        deaths += 1

    random.seed(spec.seed)
    sim = main.build_simulation(spec.config)
    sim.world.event_bus.subscribe(BirthEvent, on_birth)
    sim.world.event_bus.subscribe(DeathEvent, on_death)

    logger = main.build_logger(sim, spec.config)
    try:
        main.run_headless(sim, spec.ticks)
    finally:
        logger.close()

    creatures = list(sim.world.index.get_with(Movable))
    generations = [entity.get_component(Lineage).generation for entity in creatures if entity.has_component(Lineage)]

    return {
        'experiment': spec.experiment,
        'condition': spec.condition,
        'seed': spec.seed,
        'ticks': spec.ticks,
        'population': len(creatures),
        'plants': len(sim.world.index.get_with(Plant)),
        'food': len(sim.world.index.get_with(Eatable)),
        'births': births,
        'deaths': deaths,
        'max_generation': max(generations, default=0),
    }

def parse_args(argv=None):
    parser = argparse.ArgumentParser(description='Run a minimal EvoSim experiment')
    parser.add_argument('--experiment', default='main')
    parser.add_argument('--config', default=None)
    parser.add_argument('--conditions', nargs='+', choices=sorted(CONDITIONS), default=['baseline'])
    parser.add_argument('--seeds', nargs='+', type=int, default=None)
    parser.add_argument('--ticks', type=int, default=None)
    parser.add_argument('--sample-every', type=int, default=None)
    parser.add_argument('--out', default='results/experiments')
    parser.add_argument('--jobs', type=_positive_int, default=1)
    return parser.parse_args(argv)

def _positive_int(value: str) -> int:
    result = int(value)
    if result < 1:
        raise argparse.ArgumentTypeError('must be at least 1')
    return result

def _write_matrix(path: Path, experiment: str, conditions: list[str], seeds: list[int], ticks: int, sample_every: int, jobs: int, specs: list[RunSpec]) -> None:
    """Freeze the run plan and the feature schema before any simulation starts."""
    matrix = {
        'experiment': experiment,
        'conditions': conditions,
        'seeds': seeds,
        'ticks': ticks,
        'sample_every': sample_every,
        'jobs': jobs,
        'features': {
            'file': 'features.csv',
            'genes': list(GENE_NAMES),
            'traits': list(TRAIT_COLUMNS),
            'columns': feature_header(),
        },
        'runs': [
            {
                'condition': spec.condition,
                'seed': spec.seed,
                'output_dir': spec.config.run.output_dir,
            }
            for spec in specs
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w') as file:
        json.dump(matrix, file, indent=2)
        file.write('\n')

def _run_specs(specs: list[RunSpec], jobs: int) -> list[dict]:
    if jobs == 1:
        return [run(spec) for spec in specs]

    with ProcessPoolExecutor(max_workers=jobs) as executor:
        return list(executor.map(run, specs))

def main_cli(argv=None) -> int:
    args = parse_args(argv)
    base_cfg = load_config(args.config, argv=[])
    ticks = args.ticks if args.ticks is not None else base_cfg.run.ticks
    sample_every = args.sample_every if args.sample_every is not None else base_cfg.run.record_every
    seeds = args.seeds if args.seeds is not None else [base_cfg.run.seed]

    specs = []
    for condition in args.conditions:
        for seed in seeds:
            run_dir = Path(args.out) / args.experiment / condition / f'seed={seed}'
            cfg = CONDITIONS[condition](base_cfg)
            cfg = replace(
                cfg,
                run=replace(
                    cfg.run,
                    seed=seed,
                    ticks=ticks,
                    record_every=sample_every,
                    headless=True,
                    output_dir=str(run_dir),
                ),
            )
            specs.append(RunSpec(args.experiment, condition, seed, ticks, sample_every, cfg))

    _write_matrix(
        Path(args.out) / args.experiment / 'matrix.json',
        args.experiment, args.conditions, seeds, ticks, sample_every, args.jobs, specs,
    )

    rows = _run_specs(specs, args.jobs)
    for row in rows:
        print(
            f"{row['condition']} seed={row['seed']}: pop={row['population']} "
            f"plants={row['plants']} food={row['food']} "
            f"births={row['births']} deaths={row['deaths']}"
        )

    summary_path = Path(args.out) / args.experiment / 'summary.csv'
    with open(summary_path, 'w', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    print(f'wrote {len(rows)} run(s) to {summary_path.parent}')
    return 0

if __name__ == '__main__':
    raise SystemExit(main_cli())
