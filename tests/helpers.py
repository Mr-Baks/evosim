"""Shared helpers for building test creatures.

Since the genetics integration, creature logic (biochemistry, decision
utilities) derives its behaviour from a Genome component. Tests create
deterministic genomes with known gene values here.
"""
from genome import Gene, GeneNames, Genome


def default_genes(**overrides) -> Genome:
    """A deterministic gene set with neutral phenotype values.

    Deriving values (same for both alleles, dominant) means the phenotype
    equals the given gene value exactly:
        metabolism=0, speed=0     -> energy decay  (1+0)*(2+0)**2 = 4 / tick,
                                     hunger decay  4/4 = 1 / tick
        drive value v             -> drive factor (v + 1) / 2
    Override individual genes via keyword arguments, e.g.:

        default_genes(hunger_drive=1.0, sleep_drive=0.5)
    """
    values = {
        GeneNames.SPEED: 0.0,
        GeneNames.METABOLISM: 0.0,
        GeneNames.HUNGER_THRESHOLD: 0.0,
        GeneNames.ENERGY_THRESHOLD: 0.0,
        GeneNames.HUNGER_DRIVE: 0.5,
        GeneNames.SLEEP_DRIVE: 0.0,
        GeneNames.MATING_DRIVE: 0.5,
        GeneNames.EXPLORATION_DRIVE: 0.5,
        GeneNames.COLOR_R: 0.0,
        GeneNames.COLOR_G: 0.0,
        GeneNames.COLOR_B: 0.0,
        GeneNames.MATING_HUNGER_THRESHOLD: -1.0,
        GeneNames.MATING_ENERGY_THRESHOLD: -1.0,
        GeneNames.FERTILITY: 0.5,
    }
    values.update(overrides)
    return Genome([Gene(name, value, value) for name, value in values.items()])


def make_decision_random_deterministic(monkeypatch, value: float = 1.0) -> None:
    """Stubs systems.random so decision_system's 'reconsider the action'
    gate (random.random() > 0.3 before pushing an eat command) always fires.
    Use in tests that must deterministically reach the food."""
    import types

    import systems

    monkeypatch.setattr(systems, 'random', types.SimpleNamespace(random=lambda: value))
