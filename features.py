from entity import Lineage, Movable
from event_bus import BirthEvent
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
    GeneNames.FRUIT_DISGESTIBILITY,
    GeneNames.CORPSE_DISGESTIBILITY,
    GeneNames.FOOD_DISTANCE_WEIGHT,
    GeneNames.FOOD_DAMAGE_WEIGHT,
)

TRAIT_COLUMNS = (
    'speed_locomotion',
    'speed_metabolic',
    'metabolism_metabolic',
    'metabolism_digestion',
    'metabolism_cooldown_modifier',
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
    'fruit_digestibility',
    'corpse_digestibility',
    'food_distance_weight',
    'food_damage_weight',
)

AGGREGATE_COLUMNS = (
    'mean_neighbours',
    'mean_nearest_distance',
    'crowd_preference_negative_fraction',
    'crowd_preference_positive_fraction',
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
    header.extend(AGGREGATE_COLUMNS)
    return header


def birth_feature_header() -> list[str]:
    """Return the fixed column order of the birth-cohort feature matrix."""
    header = ['tick', 'child_eid', 'parent1_eid', 'parent2_eid', 'generation']
    for name in GENE_NAMES:
        header.append(f'gene_{name}_phenotype')
    for name in GENE_NAMES:
        header.append(f'gene_{name}_allele')
    header.extend(TRAIT_COLUMNS)
    return header


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _trait_values(traits: Traits) -> list[float]:
    return [
        traits.speed.locomotion,
        traits.speed.metabolic,
        traits.metabolism.metabolic,
        traits.metabolism.digestion,
        traits.metabolism.cooldown_modifier,
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
        traits.fruit_digestibility,
        traits.corpse_digestibility,
        traits.food_distance_weight,
        traits.food_damage_weight,
    ]


def _gene_values(genome: Genome) -> tuple[list[float], list[float], list[float]]:
    phenotypes = []
    alleles = []
    for name in GENE_NAMES:
        gene = genome.genes.get(name)
        if gene is None:
            phenotypes.append(0.0)
            alleles.append(0.0)
        else:
            phenotypes.append(gene.phenotype)
            alleles.append((gene.allele1 + gene.allele2) / 2)
    return phenotypes, alleles, _trait_values(traits_for(genome))


def _spatial_values(world: World, creatures: list) -> list[float]:
    neighbour_counts = []
    nearest_distances = []
    negative = 0
    positive = 0

    for entity in creatures:
        neighbours = [
            other
            for other in world.get_neighbours(entity, radius=5, sort=False)
            if other is not entity and other.has_component(Movable)
        ]
        neighbour_counts.append(len(neighbours))

        if neighbours:
            nearest_distances.append(min(((other.x - entity.x) ** 2 + (other.y - entity.y) ** 2) ** 0.5 for other in neighbours))

        preference = traits_for(entity.get_component(Genome)).crowd_preference
        if preference < 0:
            negative += 1
        elif preference > 0:
            positive += 1

    n = len(creatures)
    return [
        _mean(neighbour_counts),
        _mean(nearest_distances),
        negative / n if n else 0.0,
        positive / n if n else 0.0,
    ]


def log_features(world: World, tick: int) -> list[float]:
    """Summarise the living population into the fixed feature matrix row."""
    creatures = world.index.get_with(Movable, Genome)

    phenotype_sums = [0] * len(GENE_NAMES)
    allele_sums = [0] * len(GENE_NAMES)
    trait_sums = [0] * len(TRAIT_COLUMNS)
    generations = []

    for entity in creatures:
        phenotypes, alleles, traits = _gene_values(entity.get_component(Genome))
        for i, value in enumerate(phenotypes):
            phenotype_sums[i] += value
        for i, value in enumerate(alleles):
            allele_sums[i] += value
        for i, value in enumerate(traits):
            trait_sums[i] += value

        lineage = entity.get_component(Lineage)
        generations.append(lineage.generation if lineage else 0)

    n = len(creatures)
    if n == 0:
        return [tick, 0] + [0.0] * (
            len(GENE_NAMES) * 2 + 2 + len(TRAIT_COLUMNS) + len(AGGREGATE_COLUMNS)
        )

    row = [tick, n]
    row.extend(value / n for value in phenotype_sums)
    row.extend(value / n for value in allele_sums)
    row.extend([_mean(generations), max(generations)])
    row.extend(value / n for value in trait_sums)
    row.extend(_spatial_values(world, creatures))
    return row


def log_birth_features(event: BirthEvent, world: World, tick: int) -> list[float]:
    """Write the newborn genome and traits as one birth-cohort row."""
    child = event.source
    genome = child.get_component(Genome)
    lineage = child.get_component(Lineage)

    row = [
        tick,
        child.eid,
        event.parent1.eid if event.parent1 else None,
        event.parent2.eid if event.parent2 else None,
        lineage.generation if lineage else 0,
    ]

    if not genome:
        return row + [0.0] * (len(GENE_NAMES) * 2 + len(TRAIT_COLUMNS))

    phenotypes, alleles, traits = _gene_values(genome)
    row.extend(phenotypes)
    row.extend(alleles)
    row.extend(traits)
    return row
