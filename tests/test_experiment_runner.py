import csv
import json

import pytest

from experiments import runner
from features import GENE_NAMES, TRAIT_COLUMNS, feature_header
from genome import GeneNames


def test_minimal_runner_writes_runs_and_summary(tmp_path):
    result = runner.main_cli([
        '--out', str(tmp_path),
        '--experiment', 'smoke',
        '--conditions', 'baseline', 'crowd_off',
        '--seeds', '1',
        '--ticks', '5',
        '--sample-every', '5',
        '--jobs', '2',
    ])

    assert result == 0
    base = tmp_path / 'smoke'

    with open(base / 'summary.csv', newline='') as file:
        rows = list(csv.DictReader(file))

    assert [row['condition'] for row in rows] == ['baseline', 'crowd_off']
    assert all(row['seed'] == '1' for row in rows)
    assert all(row['ticks'] == '5' for row in rows)
    assert all(row['population'] == '40' for row in rows)

    with open(base / 'matrix.json') as file:
        matrix = json.load(file)

    assert matrix['conditions'] == ['baseline', 'crowd_off']
    assert matrix['seeds'] == [1]
    assert matrix['ticks'] == 5
    assert matrix['jobs'] == 2
    assert matrix['features']['genes'] == list(GENE_NAMES)
    assert matrix['features']['traits'] == list(TRAIT_COLUMNS)
    assert matrix['features']['columns'] == feature_header()
    assert len(matrix['runs']) == 2

    with open(base / 'baseline' / 'seed=1' / 'features.csv', newline='') as file:
        feature_rows = list(csv.reader(file))

    assert feature_rows[0] == feature_header()
    assert [row[0] for row in feature_rows[1:]] == ['0', '5']
    assert feature_rows[1][1] == '40'
    assert all(len(row) == len(feature_header()) for row in feature_rows)

    baseline = json.loads((base / 'baseline' / 'seed=1' / 'config.json').read_text())
    assert baseline['run']['headless'] is True
    assert baseline['run']['seed'] == 1
    assert baseline['run']['ticks'] == 5
    assert baseline['run']['record_every'] == 5

    crowd_off = json.loads((base / 'crowd_off' / 'seed=1' / 'config.json').read_text())
    gene = next(
        item for item in crowd_off['scenario']['founder_genes']
        if item[0] == GeneNames.CROWD_PREFERENCE
    )
    assert gene[1:3] == [0.0, 0.0]


def test_runner_rejects_unknown_condition(tmp_path):
    with pytest.raises(SystemExit) as error:
        runner.main_cli(['--out', str(tmp_path), '--conditions', 'unknown'])
    assert error.value.code == 2


def test_parallel_runs_match_serial_results(tmp_path):
    common = [
        '--out', str(tmp_path),
        '--conditions', 'baseline',
        '--seeds', '1', '2',
        '--ticks', '5',
        '--sample-every', '5',
    ]
    runner.main_cli(common + ['--experiment', 'serial', '--jobs', '1'])
    runner.main_cli(common + ['--experiment', 'parallel', '--jobs', '2'])

    for seed in (1, 2):
        serial = (tmp_path / 'serial' / 'baseline' / f'seed={seed}' / 'features.csv').read_text()
        parallel = (tmp_path / 'parallel' / 'baseline' / f'seed={seed}' / 'features.csv').read_text()
        assert parallel == serial

    with open(tmp_path / 'serial' / 'summary.csv', newline='') as file:
        serial_rows = list(csv.DictReader(file))
    with open(tmp_path / 'parallel' / 'summary.csv', newline='') as file:
        parallel_rows = list(csv.DictReader(file))

    for row in serial_rows:
        row.pop('experiment')
    for row in parallel_rows:
        row.pop('experiment')

    assert parallel_rows == serial_rows
