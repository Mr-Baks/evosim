import random
from typing import Optional
from entity import Component


class Gene:
    def __init__(self, name: str, allele1: float, allele2: float, dominance: float = 1):
        self.name = name
        self.allele1 = allele1
        self.allele2 = allele2
        self.dominance = dominance

    @property
    def phenotype(self) -> float:
        a_min, a_max = sorted((self.allele1, self.allele2))
        return a_max * self.dominance + a_min * (1 - self.dominance)

    def crossover(self, gene: Gene, mutation_rate: float = 0.05, strength: float = 0.1) -> Gene:
        a1 = self.allele1 if random.random() < 0.5 else self.allele2
        a2 = gene.allele1 if random.random() < 0.5 else gene.allele2

        if random.random() < mutation_rate:
            a1 = max(-1, min(1, a1 + random.uniform(-strength, strength)))

        if random.random() < mutation_rate:
            a2 = max(-1, min(1, a2 + random.uniform(-strength, strength)))

        if self.dominance != gene.dominance:
            raise ValueError("Dominance must be a locus-level constant")

        return Gene(self.name, a1, a2, self.dominance)

class GeneNames:
    SPEED = 'speed'
    METABOLISM = 'metabolism'
    COLOR_R = 'color_r'
    COLOR_G = 'color_g'
    COLOR_B = 'color_b'
    HUNGER_DRIVE = 'hunger_drive'
    SLEEP_DRIVE = 'sleep_drive'
    MATING_DRIVE = 'mating_drive'
    EXPLORATION_DRIVE = 'exploration_drive'
    MATING_HUNGER_THRESHOLD = 'mating_hunger_threshold'
    MATING_ENERGY_THRESHOLD = 'mating_energy_threshold'
    FERTILITY = 'fertility'
    SENESCENCE_SHAPE = 'senescence_shape'
    WEAR_RESISTANCE = 'wear_resistance'
    REGENERATION_THRESHOLD = 'regeneration_threshold'
    REGENERATION_INCREASE = 'regeneration_increase'
    CROWD_PREFERENCE = 'crowd_preference'
    PLANT_APPETENCE = 'plant_appetence'
    FOOD_APPETENCE = 'food_appetence'
    VISION_RADIUS = 'vision_radius'

class Genome(Component):
    def __init__(self, genes: Optional[list[Gene]] = None):
        self.genes: dict[str, Gene] = {}

        if genes:
            for g in genes:
                self.genes[g.name] = g

    def add_gene(self, gene: Gene) -> None:
        self.genes[gene.name] = gene

    def remove_gene(self, name: str) -> Optional[Gene]:
        if name in self.genes:
            return self.genes.pop(name)
        return None

    def get_phenotype(self, name: str, scaling: tuple[float, float] | None = None, default: float = None, log: bool = False) -> float | None:
        if name in self.genes:
            raw_phenotype = self.genes[name].phenotype
            if scaling is None: 
                return raw_phenotype
            
            smin, smax = scaling
            if log:
                phenotype = smin * (smax / smin) ** ((raw_phenotype + 1) / 2)
            else:
                phenotype = ((raw_phenotype + 1) * (smax - smin) / 2) + smin

            return phenotype
        return default

    def recombine(self, genome: Genome, mutation_rate: float = 0.1, strength: float = 0.3) -> Genome:
        genes = []
        gene_names = sorted(set(self.genes.keys()).union(set(genome.genes.keys())))

        for name in gene_names:
            gene1 = self.genes.get(name)
            gene2 = genome.genes.get(name)

            if not gene1 or not gene2:
                raise ValueError(f'Different genomes. Gene {name} not in genome of both parents.')
            
            genes.append(gene1.crossover(gene2, mutation_rate=mutation_rate, strength=strength))

        return Genome(genes)
