from entity import Lineage, Movable
from genome import GeneNames, Genome
from traits import Traits, traits_for
from world import World

GENE_NAMES = (
    GeneNames.SPEED,
    GeneNames.METABOLISM,
    GeneNames.COLOR_R,
    GeneNames.COLOR_G,
    GeneNames.COLOR_B,
    GeneNames.HUNGER_DRIVE,
    GeneNames.SLEEP_DRIVE,
    GeneNames.MATING_DRIVE,
    GeneNames.EXPLORATION_DRIVE,
    GeneNames.MATING_HUNGER_THRESHOLD,
    GeneNames.MATING_ENERGY_THRESHOLD,
    GeneNames.FERTILITY,
    GeneNames.SENESCENCE_SHAPE,
    GeneNames.WEAR_RESISTANCE,
    GeneNames.REGENERATION_THRESHOLD,
    GeneNames.REGENERATION_INCREASE,
    GeneNames.CROWD_PREFERENCE,
    GeneNames.PLANT_APPETENCE,
    GeneNames.FOOD_APPETENCE,
    GeneNames.VISION_RADIUS,
)

TRAIT_COLUMNS = (
    'speed_locomotion',
    'speed_metabolic',
    'metabolism',
    'fertility',
    'senescence_shape',
    'wear_aging',
    'wear_cooldown',
    'regeneration_threshold',
    'regeneration_increase',
    'hunger_drive',
    'sleep_drive',
    'mating_drive',
    'exploration_drive',
    'mating_energy_threshold',
    'mating_hunger_threshold',
    'color_r',
    'color_g',
    'color_b',
    'crowd_preference',
    'plant_appetence',
    'food_appetence',
    'vision_radius',
    'vision_metabolic',
)


def feature_header() -> list[str]:
    """Return the fixed column order of the per-tick feature matrix."""
    header = ['tick', 'n']
    for name in GENE_NAMES:
        header.append(f'gene_{name}_phenotype')
    for name in GENE_NAMES:
        header.append(f'gene_{name}_allele')
    header.extend(['mean_generation', 'max_generation'])
    header.extend(TRAIT_COLUMNS)
    return header


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _trait_values(traits: Traits) -> list[float]:
    return [
        traits.speed.locomotion,
        traits.speed.metabolic,
        traits.metabolism,
        traits.fertility,
        traits.senescence_shape,
        traits.wear_resistance.aging,
        traits.wear_resistance.cooldown,
        traits.regeneration_threshold,
        traits.regeneration_increase,
        traits.hunger_drive,
        traits.sleep_drive,
        traits.mating_drive,
        traits.exploration_drive,
        traits.mating_energy_threshold,
        traits.mating_hunger_threshold,
        traits.color.r,
        traits.color.g,
        traits.color.b,
        traits.crowd_preference,
        traits.plant_appetence,
        traits.food_appetence,
        traits.vision.radius,
        traits.vision.metabolic,
    ]


def log_features(world: World, tick: int) -> list[float]:
    """Summarise the living population into the fixed feature matrix row."""
    creatures = [
        entity
        for entity in world.index.get_with(Movable)
        if entity.has_component(Genome)
    ]

    phenotype_sums = [0.0] * len(GENE_NAMES)
    allele_sums = [0.0] * len(GENE_NAMES)
    trait_sums = [0.0] * len(TRAIT_COLUMNS)
    generations = []

    for entity in creatures:
        genome = entity.get_component(Genome)
        for i, name in enumerate(GENE_NAMES):
            gene = genome.genes.get(name)
            if gene is None:
                continue
            phenotype_sums[i] += gene.phenotype
            allele_sums[i] += (gene.allele1 + gene.allele2) / 2

        for i, value in enumerate(_trait_values(traits_for(genome))):
            trait_sums[i] += value

        lineage = entity.get_component(Lineage)
        generations.append(lineage.generation if lineage else 0)

    n = len(creatures)
    if n == 0:
        return [tick, 0] + [0.0] * (len(GENE_NAMES) * 2 + 2 + len(TRAIT_COLUMNS))

    row = [tick, n]
    row.extend(value / n for value in phenotype_sums)
    row.extend(value / n for value in allele_sums)
    row.extend([_mean(generations), max(generations)])
    row.extend(value / n for value in trait_sums)
    return row
