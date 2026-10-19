from dataclasses import dataclass
from genome import GeneNames, Genome


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

def derive(genome: Genome) -> Traits:
    """Compute all phenotype effects from a genome."""
    gp = genome.get_phenotype
    return Traits(
        metabolism=gp(GeneNames.METABOLISM, (0.01, 2), log=True),
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
    )

def traits_for(genome: Genome) -> Traits:
    """Return the cached genome's derived traits."""
    cached = getattr(genome, '_traits', None)
    if cached is None:
        cached = derive(genome)
        genome._traits = cached
    return cached
