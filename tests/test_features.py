from config import RunConfig, ScenarioConfig, SimConfig, WorldConfig
from entity import Entity, Lineage, Movable
from event_bus import BirthEvent
from features import (
    AGGREGATE_COLUMNS,
    GENE_NAMES,
    TRAIT_COLUMNS,
    birth_feature_header,
    feature_header,
    log_birth_features,
    log_features,
)
from genome import GeneNames
from tests.helpers import default_genes
from world import World
import main
import pytest


def test_feature_header_is_stable():
    header = feature_header()

    assert header[:2] == ['tick', 'n']
    assert header[2:2 + len(GENE_NAMES)] == [
        f'gene_{name}_phenotype' for name in GENE_NAMES
    ]
    assert header[2 + len(GENE_NAMES):2 + 2 * len(GENE_NAMES)] == [
        f'gene_{name}_allele' for name in GENE_NAMES
    ]
    trait_start = 2 + 2 * len(GENE_NAMES) + 2
    assert header[trait_start:trait_start + len(TRAIT_COLUMNS)] == list(TRAIT_COLUMNS)
    assert header[-len(AGGREGATE_COLUMNS):] == list(AGGREGATE_COLUMNS)


def test_feature_schema_includes_food_ranking_genes_and_traits():
    assert GeneNames.FOOD_DISTANCE_WEIGHT in GENE_NAMES
    assert GeneNames.FOOD_DAMAGE_WEIGHT in GENE_NAMES
    assert 'food_distance_weight' in TRAIT_COLUMNS
    assert 'food_damage_weight' in TRAIT_COLUMNS
    assert feature_header().count('food_distance_weight') == 1
    assert feature_header().count('food_damage_weight') == 1


def test_log_features_reports_food_ranking_traits():
    world = World(5, 5)
    genome = default_genes(**{
        GeneNames.FOOD_DISTANCE_WEIGHT: 0.0,
        GeneNames.FOOD_DAMAGE_WEIGHT: 1.0,
    })
    entity = Entity().add_component(Movable()).add_component(genome)
    world.place_entity(entity, 2, 2)

    row = dict(zip(feature_header(), log_features(world, 1)))

    assert row['gene_food_distance_weight_phenotype'] == pytest.approx(0.0)
    assert row['gene_food_distance_weight_allele'] == pytest.approx(0.0)
    assert row['food_distance_weight'] == pytest.approx(1.0)
    assert row['gene_food_damage_weight_phenotype'] == pytest.approx(1.0)
    assert row['gene_food_damage_weight_allele'] == pytest.approx(1.0)
    assert row['food_damage_weight'] == pytest.approx(2.0)


def test_feature_matrix_flattens_metabolism_pleiotropy():
    world = World(5, 5)
    entity = Entity().add_component(Movable()).add_component(default_genes())
    world.place_entity(entity, 2, 2)

    row = dict(zip(feature_header(), log_features(world, 1)))

    assert row['metabolism_metabolic'] == pytest.approx(0.5)
    assert row['metabolism_digestion'] == pytest.approx(1.0)
    assert row['metabolism_cooldown_modifier'] == pytest.approx(0.03)


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


def test_log_features_reports_spatial_and_preference_metrics():
    world = World(5, 5)
    first = Entity().add_component(Movable()).add_component(default_genes())
    second = Entity().add_component(Movable()).add_component(default_genes())
    world.place_entity(first, 1, 1)
    world.place_entity(second, 1, 2)

    row = dict(zip(feature_header(), log_features(world, 1)))

    assert row['mean_neighbours'] == pytest.approx(1.0)
    assert row['mean_nearest_distance'] == pytest.approx(1.0)
    assert row['crowd_preference_negative_fraction'] == pytest.approx(1.0)
    assert row['crowd_preference_positive_fraction'] == pytest.approx(0.0)


def test_birth_feature_row_contains_child_genome_and_generation():
    world = World(5, 5)
    parent1 = Entity()
    parent2 = Entity()
    child = Entity().add_component(default_genes()).add_component(Lineage(generation=3))

    row = dict(zip(
        birth_feature_header(),
        log_birth_features(BirthEvent(source=child, parent1=parent1, parent2=parent2), world, 7),
    ))

    assert row['tick'] == 7
    assert row['generation'] == 3
    assert row['gene_metabolism_phenotype'] == pytest.approx(0.0)
    assert row['metabolism_metabolic'] == pytest.approx(0.5)
    assert row['metabolism_digestion'] == pytest.approx(1.0)
