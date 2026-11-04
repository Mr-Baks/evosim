"""Aggregate experiment runs across seeds.

Usage:
    python experiments/aggregate.py baseline_40k
    python experiments/aggregate.py baseline_40k --root results/experiments
    python experiments/aggregate.py baseline_40k --generation-bin 50

The aggregator reads the run plan from ``matrix.json`` and the per-run CSV
files from ``<root>/<experiment>/<condition>/seed=<seed>/``. It writes
``aggregate.csv`` for per-tick metrics and ``cohort_aggregate.csv`` for
birth cohorts grouped by generation.
"""
import argparse
import csv
import json
import math
import statistics
import sys
from pathlib import Path

if __package__ is None or __package__ == '':
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


AGGREGATE_COLUMNS = [
    'experiment',
    'condition',
    'dataset',
    'metric',
    'tick',
    'mean',
    'sd',
    'ci_low',
    'ci_high',
    'runs',
]

COHORT_COLUMNS = [
    'experiment',
    'condition',
    'generation_bin',
    'metric',
    'mean',
    'sd',
    'ci_low',
    'ci_high',
    'runs',
    'births',
]

T_CRITICAL_95 = {
    1: 12.706,
    2: 4.303,
    3: 3.182,
    4: 2.776,
    5: 2.571,
    6: 2.447,
    7: 2.365,
    8: 2.306,
    9: 2.262,
    10: 2.228,
    11: 2.201,
    12: 2.179,
    13: 2.160,
    14: 2.145,
    15: 2.131,
    16: 2.120,
    17: 2.110,
    18: 2.101,
    19: 2.093,
    20: 2.086,
    21: 2.080,
    22: 2.074,
    23: 2.069,
    24: 2.064,
    25: 2.060,
    26: 2.056,
    27: 2.052,
    28: 2.048,
    29: 2.045,
    30: 2.042,
}


def _read_csv(path: Path) -> list[dict[str, str]]:
    """Reads a CSV file, returning an empty list when it is absent."""
    if not path.exists():
        return []
    with open(path, newline='') as file:
        return list(csv.DictReader(file))


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    """Writes rows with a fixed column order."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _to_float(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _numeric_metrics(row: dict[str, str], excluded: set[str]) -> dict[str, float]:
    """Extracts numeric metric columns from one CSV row."""
    metrics = {}
    for key, value in row.items():
        if key in excluded:
            continue
        number = _to_float(value)
        if number is not None and math.isfinite(number):
            metrics[key] = number
    return metrics


def _metric_order(rows: list[dict[str, str]], excluded: set[str]) -> list[str]:
    """Returns the first row's numeric column order."""
    if not rows:
        return []
    return list(_numeric_metrics(rows[0], excluded))


def _stats(values: list[float]) -> dict[str, float] | None:
    """Returns mean, sample SD and a 95% CI for a seed-level sample."""
    n = len(values)
    if n == 0:
        return None
    mean = statistics.fmean(values)
    if n == 1:
        return {
            'mean': mean,
            'sd': 0.0,
            'ci_low': mean,
            'ci_high': mean,
            'runs': 1,
        }
    sd = statistics.stdev(values)
    half_width = T_CRITICAL_95.get(n - 1, 1.96) * sd / math.sqrt(n)
    return {
        'mean': mean,
        'sd': sd,
        'ci_low': mean - half_width,
        'ci_high': mean + half_width,
        'runs': n,
    }


def _load_matrix(experiment_dir: Path) -> dict:
    """Loads matrix.json or returns an empty plan."""
    path = experiment_dir / 'matrix.json'
    if not path.exists():
        return {}
    with open(path) as file:
        return json.load(file)


def _conditions_and_seeds(experiment_dir: Path, matrix: dict) -> tuple[list[str], list[int]]:
    """Reads the condition/seed plan, falling back to directory names."""
    conditions = list(matrix.get('conditions', []))
    seeds = list(matrix.get('seeds', []))

    if not conditions:
        conditions = sorted(
            path.name for path in experiment_dir.iterdir()
            if path.is_dir() and any(path.glob('seed=*'))
        )
    if not seeds:
        seeds = sorted({
            int(path.name.removeprefix('seed='))
            for condition in conditions
            for path in (experiment_dir / condition).glob('seed=*')
            if path.name.removeprefix('seed=').isdigit()
        })
    return conditions, seeds


def _run_dir(experiment_dir: Path, condition: str, seed: int) -> Path:
    return experiment_dir / condition / f'seed={seed}'


def _rows_by_seed(
    experiment_dir: Path,
    condition: str,
    seeds: list[int],
    filename: str,
) -> list[list[dict[str, str]]]:
    """Loads one CSV from every available seed of a condition."""
    return [
        rows
        for seed in seeds
        if (rows := _read_csv(_run_dir(experiment_dir, condition, seed) / filename))
    ]


def _aggregate_tick_dataset(
    experiment: str,
    condition: str,
    dataset: str,
    rows_by_seed: list[list[dict[str, str]]],
    excluded: set[str],
) -> list[dict]:
    """Aggregates a CSV sampled by tick across seeds."""
    metrics = _metric_order(rows_by_seed[0], excluded) if rows_by_seed else []
    by_seed = []
    for rows in rows_by_seed:
        by_tick = {}
        for row in rows:
            tick = _to_float(row.get('tick'))
            if tick is not None:
                by_tick[int(tick)] = _numeric_metrics(row, excluded)
        by_seed.append(by_tick)

    ticks = sorted({tick for by_tick in by_seed for tick in by_tick})
    result = []
    for tick in ticks:
        for metric in metrics:
            values = [
                by_tick[tick][metric]
                for by_tick in by_seed
                if tick in by_tick and metric in by_tick[tick]
            ]
            stats = _stats(values)
            if stats is None:
                continue
            result.append({
                'experiment': experiment,
                'condition': condition,
                'dataset': dataset,
                'metric': metric,
                'tick': tick,
                **stats,
            })
    return result


def _aggregate_summary(
    experiment: str,
    condition: str,
    rows: list[dict[str, str]],
    tick: int,
) -> list[dict]:
    """Aggregates the batch summary values across seeds."""
    excluded = {'experiment', 'condition', 'seed', 'ticks'}
    metrics = _metric_order(rows, excluded) if rows else []
    result = []
    for metric in metrics:
        values = [
            number
            for row in rows
            if (number := _to_float(row.get(metric))) is not None
        ]
        stats = _stats(values)
        if stats is None:
            continue
        result.append({
            'experiment': experiment,
            'condition': condition,
            'dataset': 'summary',
            'metric': metric,
            'tick': tick,
            **stats,
        })
    return result


def _aggregate_cohorts(
    experiment: str,
    condition: str,
    rows_by_seed: list[list[dict[str, str]]],
    generation_bin: int,
) -> list[dict]:
    """Aggregates birth features into generation bins."""
    excluded = {'tick', 'child_eid', 'parent1_eid', 'parent2_eid', 'generation'}
    metrics = _metric_order(rows_by_seed[0], excluded) if rows_by_seed else []
    per_run = []
    for rows in rows_by_seed:
        bins: dict[int, list[dict[str, str]]] = {}
        for row in rows:
            generation = _to_float(row.get('generation'))
            if generation is None:
                continue
            start = int(generation) // generation_bin * generation_bin
            bins.setdefault(start, []).append(row)
        per_run.append(bins)

    starts = sorted({start for bins in per_run for start in bins})
    result = []
    for start in starts:
        for metric in metrics:
            run_means = []
            births = 0
            for bins in per_run:
                rows = bins.get(start, [])
                if not rows:
                    continue
                values = [
                    number
                    for row in rows
                    if (number := _to_float(row.get(metric))) is not None
                ]
                if not values:
                    continue
                run_means.append(statistics.fmean(values))
                births += len(rows)
            stats = _stats(run_means)
            if stats is None:
                continue
            result.append({
                'experiment': experiment,
                'condition': condition,
                'generation_bin': start,
                'metric': metric,
                **stats,
                'births': births,
            })
    return result


def parse_args(argv=None):
    """Parses aggregator command-line options."""
    parser = argparse.ArgumentParser(description='Aggregate EvoSim runs across seeds')
    parser.add_argument('experiment', help='experiment directory name, e.g. baseline_40k')
    parser.add_argument('--root', default='results/experiments')
    parser.add_argument('--generation-bin', type=int, default=25)
    parser.add_argument('--out', default=None, help='default: <experiment>/aggregate.csv')
    parser.add_argument('--cohort-out', default=None, help='default: <experiment>/cohort_aggregate.csv')
    return parser.parse_args(argv)


def main_cli(argv=None) -> int:
    """Aggregates all available runs and writes both aggregate CSVs."""
    args = parse_args(argv)
    if args.generation_bin < 1:
        raise SystemExit('--generation-bin must be at least 1')

    experiment_dir = Path(args.root) / args.experiment
    matrix = _load_matrix(experiment_dir)
    conditions, seeds = _conditions_and_seeds(experiment_dir, matrix)
    tick = int(matrix.get('ticks', 0))

    aggregate_rows = []
    cohort_rows = []
    summary_rows = _read_csv(experiment_dir / 'summary.csv')
    for condition in conditions:
        population = _rows_by_seed(experiment_dir, condition, seeds, 'population.csv')
        features = _rows_by_seed(experiment_dir, condition, seeds, 'features.csv')
        births = _rows_by_seed(experiment_dir, condition, seeds, 'birth_features.csv')
        summary = [
            row for row in summary_rows
            if row.get('condition') == condition
        ]

        aggregate_rows.extend(_aggregate_tick_dataset(
            args.experiment, condition, 'population', population, {'tick'},
        ))
        aggregate_rows.extend(_aggregate_tick_dataset(
            args.experiment, condition, 'features', features, {'tick'},
        ))
        aggregate_rows.extend(_aggregate_summary(
            args.experiment, condition, summary, tick,
        ))
        cohort_rows.extend(_aggregate_cohorts(
            args.experiment, condition, births, args.generation_bin,
        ))

    out = Path(args.out) if args.out else experiment_dir / 'aggregate.csv'
    cohort_out = (
        Path(args.cohort_out)
        if args.cohort_out
        else experiment_dir / 'cohort_aggregate.csv'
    )
    _write_csv(out, AGGREGATE_COLUMNS, aggregate_rows)
    _write_csv(cohort_out, COHORT_COLUMNS, cohort_rows)

    print(f'wrote {len(aggregate_rows)} aggregate row(s) to {out}')
    print(f'wrote {len(cohort_rows)} cohort row(s) to {cohort_out}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main_cli())
