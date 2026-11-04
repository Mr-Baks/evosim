import csv
import json
import math
from pathlib import Path

import pytest

from experiments import aggregate


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _make_run(root: Path, condition: str, seed: int) -> Path:
    run = root / condition / f'seed={seed}'
    _write_csv(
        run / 'population.csv',
        ['tick', 'creatures', 'mean_energy'],
        [
            {'tick': 0, 'creatures': 100, 'mean_energy': 100.0},
            {'tick': 10, 'creatures': 110 + seed * 10, 'mean_energy': 150.0 + seed * 10},
        ],
    )
    _write_csv(
        run / 'features.csv',
        ['tick', 'n', 'gene_speed_phenotype', 'mean_neighbours'],
        [
            {'tick': 0, 'n': 100, 'gene_speed_phenotype': -0.6, 'mean_neighbours': 1.0},
            {'tick': 10, 'n': 110 + seed * 10, 'gene_speed_phenotype': 0.2, 'mean_neighbours': 2.0},
        ],
    )
    return run


def test_aggregate_computes_seed_level_stats_and_cohorts(tmp_path):
    root = tmp_path / 'results'
    experiment_dir = root / 'demo'
    experiment_dir.mkdir(parents=True)
    matrix = {
        'experiment': 'demo',
        'conditions': ['baseline', 'rich'],
        'seeds': [1, 2],
        'ticks': 10,
        'sample_every': 10,
    }
    with open(experiment_dir / 'matrix.json', 'w') as file:
        json.dump(matrix, file)

    for seed in (1, 2):
        run = _make_run(experiment_dir, 'baseline', seed)
        _write_csv(
            run / 'birth_features.csv',
            ['tick', 'child_eid', 'parent1_eid', 'parent2_eid', 'generation',
             'gene_speed_phenotype', 'metabolism_metabolic'],
            [
                {'tick': 1, 'child_eid': seed, 'parent1_eid': 0, 'parent2_eid': 0,
                 'generation': 1, 'gene_speed_phenotype': -0.6, 'metabolism_metabolic': 0.5},
                {'tick': 2, 'child_eid': seed + 10, 'parent1_eid': 0, 'parent2_eid': 0,
                 'generation': 20, 'gene_speed_phenotype': 0.2, 'metabolism_metabolic': 0.4},
                {'tick': 3, 'child_eid': seed + 20, 'parent1_eid': 0, 'parent2_eid': 0,
                 'generation': 30, 'gene_speed_phenotype': 0.4, 'metabolism_metabolic': 0.3},
            ],
        )

    _write_csv(
        experiment_dir / 'summary.csv',
        ['experiment', 'condition', 'seed', 'ticks', 'population', 'births'],
        [
            {'experiment': 'demo', 'condition': 'baseline', 'seed': seed,
             'ticks': 10, 'population': 110 + seed * 10, 'births': 20 + seed}
            for seed in (1, 2)
        ],
    )

    out = tmp_path / 'aggregate.csv'
    cohort_out = tmp_path / 'cohort.csv'
    assert aggregate.main_cli([
        'demo',
        '--root', str(root),
        '--out', str(out),
        '--cohort-out', str(cohort_out),
        '--generation-bin', '25',
    ]) == 0

    with open(out, newline='') as file:
        rows = list(csv.DictReader(file))

    population = next(
        row for row in rows
        if row['condition'] == 'baseline'
        and row['dataset'] == 'population'
        and row['metric'] == 'creatures'
        and row['tick'] == '10'
    )
    assert float(population['mean']) == pytest.approx(125.0)
    assert float(population['sd']) == pytest.approx(math.sqrt(50))
    assert int(population['runs']) == 2

    feature = next(
        row for row in rows
        if row['condition'] == 'baseline'
        and row['dataset'] == 'features'
        and row['metric'] == 'gene_speed_phenotype'
        and row['tick'] == '10'
    )
    assert float(feature['mean']) == pytest.approx(0.2)

    summary = next(
        row for row in rows
        if row['condition'] == 'baseline'
        and row['dataset'] == 'summary'
        and row['metric'] == 'births'
    )
    assert float(summary['mean']) == pytest.approx(21.5)
    assert int(summary['runs']) == 2

    with open(cohort_out, newline='') as file:
        cohorts = list(csv.DictReader(file))

    bin_zero = next(
        row for row in cohorts
        if row['generation_bin'] == '0' and row['metric'] == 'gene_speed_phenotype'
    )
    assert float(bin_zero['mean']) == pytest.approx(-0.2)
    assert int(bin_zero['births']) == 4

    bin_twenty_five = next(
        row for row in cohorts
        if row['generation_bin'] == '25' and row['metric'] == 'metabolism_metabolic'
    )
    assert float(bin_twenty_five['mean']) == pytest.approx(0.3)
    assert int(bin_twenty_five['births']) == 2


def test_aggregate_handles_missing_files_and_matrix(tmp_path):
    root = tmp_path / 'results'
    run = root / 'demo' / 'baseline' / 'seed=1'
    _write_csv(
        run / 'population.csv',
        ['tick', 'creatures'],
        [{'tick': 0, 'creatures': 100}],
    )

    out = tmp_path / 'aggregate.csv'
    assert aggregate.main_cli([
        'demo',
        '--root', str(root),
        '--out', str(out),
        '--cohort-out', str(tmp_path / 'cohort.csv'),
    ]) == 0

    with open(out, newline='') as file:
        rows = list(csv.DictReader(file))

    assert len(rows) == 1
    assert rows[0]['condition'] == 'baseline'
    assert rows[0]['metric'] == 'creatures'
    assert int(rows[0]['runs']) == 1
