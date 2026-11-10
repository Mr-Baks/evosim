"""Tests for the heritable food-ranking genes.

``FOOD_DISTANCE_WEIGHT`` and ``FOOD_DAMAGE_WEIGHT`` scale linearly onto
``(0, 2)`` and feed ``systems.rate_food``.  These tests pin the scaling, the
missing-gene defaults and the two independent penalties used to rank visible
food.
"""
import pytest

from entity import Eatable, Entity, FoodTypes
from genome import GeneNames, Genome
from systems import rate_food
from tests.helpers import default_genes
from traits import derive


def _traits(**overrides):
    return derive(default_genes(**overrides))


def _food(x, y, nutrition=20, decay=0.0):
    food = Entity().add_component(
        Eatable(nutrition=nutrition, food_type=FoodTypes.FRUIT, decay=decay)
    )
    food.x = x
    food.y = y
    return food


@pytest.mark.parametrize(('raw', 'expected'), [
    (-1.0, 0.0),
    (0.0, 1.0),
    (1.0, 2.0),
])
def test_food_weights_scale_linearly_from_zero_to_two(raw, expected):
    traits = _traits(**{
        GeneNames.FOOD_DISTANCE_WEIGHT: raw,
        GeneNames.FOOD_DAMAGE_WEIGHT: raw,
    })

    assert traits.food_distance_weight == pytest.approx(expected)
    assert traits.food_damage_weight == pytest.approx(expected)


def test_missing_food_weights_use_defaults():
    traits = derive(Genome())

    assert traits.food_distance_weight == pytest.approx(0.4)
    assert traits.food_damage_weight == pytest.approx(1.5)


def test_rate_food_subtracts_distance_penalty():
    traits = _traits(**{
        GeneNames.FOOD_DISTANCE_WEIGHT: 0.5,
        GeneNames.FOOD_DAMAGE_WEIGHT: -1.0,
    })

    near = rate_food(0, 0, _food(1, 0), traits)
    far = rate_food(0, 0, _food(3, 0), traits)

    assert near - far == pytest.approx(traits.food_distance_weight * 2)


def test_zero_distance_weight_makes_distance_irrelevant():
    traits = _traits(**{
        GeneNames.FOOD_DISTANCE_WEIGHT: -1.0,
        GeneNames.FOOD_DAMAGE_WEIGHT: -1.0,
    })

    assert rate_food(0, 0, _food(1, 0), traits) == pytest.approx(
        rate_food(0, 0, _food(5, 0), traits)
    )


def test_rate_food_subtracts_damage_penalty_only_for_rotting_food():
    no_penalty = _traits(**{
        GeneNames.FOOD_DISTANCE_WEIGHT: -1.0,
        GeneNames.FOOD_DAMAGE_WEIGHT: -1.0,
    })
    full_penalty = _traits(**{
        GeneNames.FOOD_DISTANCE_WEIGHT: -1.0,
        GeneNames.FOOD_DAMAGE_WEIGHT: 1.0,
    })
    fresh = _food(1, 0, decay=0.0)
    rotten = _food(1, 0, decay=1.0)

    # Fresh food is unaffected by the damage weight.
    assert rate_food(0, 0, fresh, no_penalty) == pytest.approx(
        rate_food(0, 0, fresh, full_penalty)
    )

    # Rotten food loses exactly weight * damage from its utility.
    difference = (
        rate_food(0, 0, rotten, no_penalty)
        - rate_food(0, 0, rotten, full_penalty)
    )
    assert difference == pytest.approx(
        full_penalty.food_damage_weight
        * full_penalty.food_damage(1.0, FoodTypes.FRUIT)
    )
    assert rate_food(0, 0, rotten, full_penalty) < rate_food(
        0, 0, rotten, no_penalty
    )


def test_food_weights_rank_candidates_independently():
    near_rotten = _food(1, 0, nutrition=20, decay=0.85)
    far_fresh = _food(8, 0, nutrition=20, decay=0.0)

    rot_tolerant = _traits(**{
        GeneNames.FOOD_DISTANCE_WEIGHT: 0.0,
        GeneNames.FOOD_DAMAGE_WEIGHT: -1.0,
    })
    rot_averse = _traits(**{
        GeneNames.FOOD_DISTANCE_WEIGHT: 0.0,
        GeneNames.FOOD_DAMAGE_WEIGHT: 1.0,
    })

    def preferred(traits):
        return min(
            (near_rotten, far_fresh),
            key=lambda food: -rate_food(0, 0, food, traits),
        )

    # A zero damage weight makes the nearby, partly rotten fruit win.
    assert preferred(rot_tolerant) is near_rotten
    # Charging for damage reverses the choice: walk farther for fresh food.
    assert preferred(rot_averse) is far_fresh
