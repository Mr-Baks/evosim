from dataclasses import dataclass
from genome import GeneNames, Genome

MAX_HEALTH = 100
HUNGER_COST_SCALE = 710

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
class Traits:
    metabolism: float
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
        """Energy spent per awake tick; frailer bodies burn more."""
        return self.metabolism * self.speed.metabolic ** 2 * (2 - vitality)

    def hunger_drain(self) -> float:
        """Hunger spent per tick; longer-lived bodies burn more."""
        return self.metabolism * self.speed.metabolic ** 2 * (self.wear_resistance.aging / HUNGER_COST_SCALE)

    def effective_fertility(self, vitality: float) -> float:
        """Fertility after the vitality gate and the senescence-shape penalty."""
        return self.fertility * min(1.0, vitality * 2) * (1 - self.senescence_shape / 3)

    def regeneration_gain(self, vitality: float) -> float:
        """Health regained per regeneration activation."""
        return self.regeneration_increase * self.metabolism * vitality

    def regeneration_cost(self) -> float:
        """Energy (and equally hunger) spent per regeneration activation."""
        return self.regeneration_increase ** 2 * self.metabolism / 2

def derive(genome: Genome) -> Traits:
    """Compute all phenotype effects from a genome."""
    gp = genome.get_phenotype
    return Traits(
        metabolism=gp(GeneNames.METABOLISM, (0.1, 2), log=True),
        speed=Speed(
            locomotion=gp(GeneNames.SPEED, (0, 5)),
            metabolic=gp(GeneNames.SPEED, (1, 3)),
        ),
        fertility=gp(GeneNames.FERTILITY, (0, 1)),
        senescence_shape=gp(GeneNames.SENESCENCE_SHAPE, (1, 3)),
        wear_resistance=WearResistance(
            aging=gp(GeneNames.WEAR_RESISTANCE, (180, 700), log=True),
            cooldown=gp(GeneNames.WEAR_RESISTANCE, (0.001, 300), log=True),
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
    )

def traits_for(genome: Genome) -> Traits:
    """Return the genome's derived traits, computing them only once."""
    cached = getattr(genome, '_traits', None)
    if cached is None:
        cached = derive(genome)
        genome._traits = cached
    return cached
