from config import RunConfig, ScenarioConfig, SimConfig, WorldConfig
from features import GENE_NAMES, TRAIT_COLUMNS, feature_header, log_features
from world import World
import main


def test_feature_header_is_stable():
    header = feature_header()

    assert header[:2] == ['tick', 'n']
    assert header[2:2 + len(GENE_NAMES)] == [
        f'gene_{name}_phenotype' for name in GENE_NAMES
    ]
    assert header[2 + len(GENE_NAMES):2 + 2 * len(GENE_NAMES)] == [
        f'gene_{name}_allele' for name in GENE_NAMES
    ]
    assert header[-len(TRAIT_COLUMNS):] == list(TRAIT_COLUMNS)


def test_log_features_empty_world_keeps_matrix_shape():
    row = log_features(World(5, 5), 0)

    assert len(row) == len(feature_header())
    assert row[0] == 0
    assert row[1] == 0
    assert all(value == 0.0 for value in row[2:])


def test_log_features_reports_living_population(tmp_path):
    cfg = SimConfig(
        run=RunConfig(
            seed=1,
            headless=True,
            output_dir=str(tmp_path),
            record_every=5,
        ),
        scenario=ScenarioConfig(
            world=WorldConfig(10, 10),
            initial_creatures=3,
            initial_plants=0,
        ),
    )
    sim = main.build_simulation(cfg)

    row = log_features(sim.world, 7)

    assert row[0] == 7
    assert row[1] == 3
    assert len(row) == len(feature_header())
