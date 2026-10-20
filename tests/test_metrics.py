import csv
import random

from config import RunConfig, ScenarioConfig, SimConfig
from entity import Movable
from tools.experiments.metrics import COLUMNS, MetricsRecorder
from main import build_simulation


def _cfg(seed=1, ticks=20, sample_every=5):
    return SimConfig(
        run=RunConfig(seed=seed, ticks=ticks, headless=True, record_every=sample_every),
        scenario=ScenarioConfig(initial_plants=20, initial_creatures=8),
    )


def _advance(sim, recorder, ticks):
    for _ in range(ticks):
        sim.handle_systems()
        sim.world.event_bus.dispatch()
        recorder.record(sim)
        sim.tick += 1


def test_recorder_writes_header_and_sampled_rows(tmp_path):
    cfg = _cfg(ticks=20, sample_every=5)
    random.seed(cfg.run.seed)
    sim = build_simulation(cfg)

    recorder = MetricsRecorder(tmp_path / 'metrics.csv', sample_every=cfg.run.record_every)
    _advance(sim, recorder, cfg.run.ticks)
    recorder.close()

    with open(tmp_path / 'metrics.csv', newline='') as f:
        rows = list(csv.DictReader(f))

    assert list(rows[0].keys()) == COLUMNS
    # ticks 0, 5, 10, 15 are sampled out of 20
    assert len(rows) == 4
    assert recorder.births_total >= 0
    assert recorder.deaths_total >= 0


def test_recording_does_not_change_the_run(tmp_path):
    cfg = _cfg(seed=3, ticks=50)

    random.seed(cfg.run.seed)
    plain = build_simulation(cfg)
    for _ in range(cfg.run.ticks):
        plain.handle_systems()
        plain.world.event_bus.dispatch()
        plain.tick += 1

    random.seed(cfg.run.seed)
    recorded = build_simulation(cfg)
    recorder = MetricsRecorder(tmp_path / 'metrics.csv', sample_every=cfg.run.record_every)
    _advance(recorded, recorder, cfg.run.ticks)
    recorder.close()

    def state(sim):
        return sorted((e.eid, e.x, e.y) for e in sim.world.index.get_with(Movable))

    assert state(plain) == state(recorded)
