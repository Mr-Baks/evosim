from abc import ABC
import random
from typing import Optional
from entity import Component


class Gene:
    def __init__(self, name: str, allele1: float, allele2: float, dominant: bool = True):
        self.name = name
        self.allele1 = allele1
        self.allele2 = allele2
        self.dominant = dominant

    @property
    def phenotype(self) -> float:
        if self.dominant:
            return max(self.allele1, self.allele2)
        else: 
            return (self.allele1 + self.allele2) / 2

    def crossover(self, gene: Gene, mutation_rate: float = 0.05, strength: float = 0.1) -> Gene:
        a1 = self.allele1 if random.random() < 0.5 else gene.allele1
        a2 = self.allele2 if random.random() < 0.5 else gene.allele2

        if random.random() < mutation_rate:
            a1 = max(-1, min(1, a1 + random.uniform(-strength, strength)))
            a2 = max(-1, min(1, a2 + random.uniform(-strength, strength)))

        return Gene(self.name, a1, a2, self.dominant)

class GeneNames:
    SPEED = 'speed'
    METABOLISM = 'metabolism'
    COLOR_R = 'color_r'
    COLOR_G = 'color_g'
    COLOR_B = 'color_b'
    HUNGER_THRESHOLD = 'hunger_threshold'
    ENERGY_THRESHOLD = 'energy_threshold'

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

    def get_phenotype(self, name: str) -> Optional[float]:
        if name in self.genes:
            return self.genes[name].phenotype
        return None

    def recombine(self, genome: Genome, mutation_rate: float = 0.1, strength: float = 0.3) -> Genome:
        genes = []

        for name in self.genes:
            genes.append(self.genes[name].crossover(genome.genes[name], mutation_rate=mutation_rate, strength=strength))

        return Genome(genes)
    

