import math
from dataclasses import dataclass
from genome import GeneNames, Genome
from entity import FoodTypes

MAX_HEALTH = 100
HUNGER_COST_SCALE = 710
MAX_ROTTED_FOOD_DAMAGE: float = 25
ROTTED_DAMAGING_THRESHOLD: float = 0.8
ROTTED_BASE_DAMAGE: float = 2
GENERALIST_COST: float = 0.5

@dataclass(frozen=True)
class Metabolism:
    metabolic: float
    digestion: float
    cooldown_modifier: float

@dataclass(frozen=True)
class Speed:
    locomotion: float
    metabolic: float

@dataclass(frozen=True)
class WearResistance:
    aging: float
    cooldown: float

@dataclass(frozen=True)
class Color:
    r: float
    g: float
    b: float

@dataclass(frozen=True)
class Vision:
    radius: float
    metabolic: float

@dataclass(frozen=True)
class Traits:
    metabolism: Metabolism
    speed: Speed
    fertility: float
    senescence_shape: float
    wear_resistance: WearResistance
    regeneration_threshold: float
    regeneration_increase: float
    hunger_drive: float
    sleep_drive: float
    mating_drive: float
    exploration_drive: float
    mating_energy_threshold: float
    mating_hunger_threshold: float
    color: Color
    crowd_preference: float
    plant_appetence: float
    food_appetence: float
    vision: Vision
    fruit_digestibility: float
    corpse_digestibility: float

    def wear(self, age: float) -> float:
        """Fraction of the lifespan used at age, capped at 1."""
        return min(1.0, age / self.wear_resistance.aging)

    def vitality(self, age: float) -> float:
        """Health multiplier from ageing: 1 at birth, 0 at the end of life."""
        return max(0.0, 1.0 - self.wear(age) ** self.senescence_shape)

    def max_health(self, vitality: float) -> float:
        """Health cap at a given vitality."""
        return vitality * MAX_HEALTH

    def energy_drain(self, vitality: float) -> float:
        """Energy spent per awake tick; high metabolism costs more."""
        return ((self.metabolism.metabolic) ** 2) * (0.5 + 0.5 * self.metabolism.digestion) * self.speed.metabolic * (2 - vitality) * self.vision.metabolic

    def hunger_drain(self) -> float:
        """Hunger spent per tick; fast, long-lived bodies need more fuel."""
        return (self.wear_resistance.aging / HUNGER_COST_SCALE) * (self.metabolism.metabolic / 0.5) * self.speed.metabolic * 0.5 * self.vision.metabolic

    def _digestibility_efficiencies(self) -> dict[FoodTypes, float]:
        """Digestive efficiency of every known food type."""
        affinities = {
            FoodTypes.FRUIT: self.fruit_digestibility,
            FoodTypes.CORPSE: self.corpse_digestibility,
        }
        total = sum(affinities.values())

        weights = [value / total for value in affinities.values() if value > 0]
        entropy = -sum(weight * math.log(weight) for weight in weights)
        max_entropy = math.log(len(affinities)) if len(affinities) > 1 else 0.0
        normalized_entropy = entropy / max_entropy if max_entropy > 0 else 0.0
        penalty = GENERALIST_COST * normalized_entropy

        return {food_type: value * (1.0 - penalty) for food_type, value in affinities.items()}

    def hunger_gain(self, nutrition: int, decay: float, food_type: FoodTypes) -> float:
        """Satiety restored by food, scaled by digestive efficiency."""
        if food_type is None:
            digestibility = 1.0
        else:
            digestibility = self._digestibility_efficiencies().get(food_type, 0.0)

        return self.metabolism.digestion * nutrition * digestibility * (1 - decay)

    def food_damage(self, decay: float, food_type: FoodTypes) -> float:
        "Damage after eating a food."
        if decay < ROTTED_DAMAGING_THRESHOLD:
            return 0

        decay = (decay - ROTTED_DAMAGING_THRESHOLD) / (1 - ROTTED_DAMAGING_THRESHOLD)
        efficiency = self._digestibility_efficiencies().get(food_type)
        if efficiency is None:
            return 0

        damage_factor = ROTTED_BASE_DAMAGE + (1 - efficiency) * (MAX_ROTTED_FOOD_DAMAGE - ROTTED_BASE_DAMAGE)
        return decay * damage_factor

    def effective_fertility(self, vitality: float) -> float:
        """Fertility after the vitality gate and the senescence-shape penalty."""
        return self.fertility * min(1.0, vitality * 2) * (1 - self.senescence_shape / 3)

    def additional_cooldown(self) -> int:
        """Extra mating cooldown after the global base."""
        return round(self.wear_resistance.cooldown * (1 - 0.5 * self.metabolism.cooldown_modifier))

    def regeneration_gain(self, vitality: float) -> float:
        """Health regained per regeneration activation."""
        return self.regeneration_increase * self.metabolism.metabolic * vitality

    def regeneration_cost(self) -> float:
        """Energy (and equally hunger) spent per regeneration activation."""
        return self.regeneration_increase ** 2 * self.metabolism.metabolic / 2

def derive(genome: Genome) -> Traits:
    """Compute all phenotype effects from a genome."""
    gp = genome.get_phenotype

    return Traits(
        metabolism=Metabolism(
            metabolic=gp(GeneNames.METABOLISM, (0.1, 2.5), default=0.5, log=True),
            digestion=gp(GeneNames.METABOLISM, (0.5, 1.5), default=1.0),
            cooldown_modifier=gp(GeneNames.METABOLISM, (0.001, 0.9), default=0.0, log=True),
        ),
        speed=Speed(
            locomotion=gp(GeneNames.SPEED, (0, 5), default=2.5),
            metabolic=gp(GeneNames.SPEED, (1, 3), default=2.0),
        ),
        fertility=gp(GeneNames.FERTILITY, (0, 1)),
        senescence_shape=gp(GeneNames.SENESCENCE_SHAPE, (1, 3)),
        wear_resistance=WearResistance(
            aging=gp(GeneNames.WEAR_RESISTANCE, (180, 700), default=355.0, log=True),
            cooldown=gp(GeneNames.WEAR_RESISTANCE, (0.001, 300), default=100.0, log=True),
        ),
        regeneration_threshold=gp(GeneNames.REGENERATION_THRESHOLD, (0, 1)),
        regeneration_increase=gp(GeneNames.REGENERATION_INCREASE, (1, 5)),
        hunger_drive=gp(GeneNames.HUNGER_DRIVE, (0, 1)),
        sleep_drive=gp(GeneNames.SLEEP_DRIVE, (0, 1)),
        mating_drive=gp(GeneNames.MATING_DRIVE, (0, 1)),
        exploration_drive=gp(GeneNames.EXPLORATION_DRIVE, (0, 1)),
        mating_energy_threshold=gp(GeneNames.MATING_ENERGY_THRESHOLD, (0, 200)),
        mating_hunger_threshold=gp(GeneNames.MATING_HUNGER_THRESHOLD, (0, 200)),
        color=Color(
            r=gp(GeneNames.COLOR_R, (0, 256)),
            g=gp(GeneNames.COLOR_G, (0, 256)),
            b=gp(GeneNames.COLOR_B, (0, 256)),
        ),
        crowd_preference=gp(GeneNames.CROWD_PREFERENCE, default=0.0),
        plant_appetence=gp(GeneNames.PLANT_APPETENCE, default=0.0),
        food_appetence=gp(GeneNames.FOOD_APPETENCE, default=0.0),
        vision=Vision(
            radius=gp(GeneNames.VISION_RADIUS, (1, 10), default=7.5, log=True),
            metabolic=gp(GeneNames.VISION_RADIUS, (1, 1.25), default=1.2, log=True),
        ),
        fruit_digestibility=gp(GeneNames.FRUIT_DISGESTIBILITY, (0, 1), default=0.5),
        corpse_digestibility=gp(GeneNames.CORPSE_DISGESTIBILITY, (0, 1), default=0.5),
    )

def traits_for(genome: Genome) -> Traits:
    """Return the genome's derived traits, computing them only once."""
    cached = getattr(genome, '_traits', None)
    if cached is None:
        cached = derive(genome)
        genome._traits = cached
    return cached
