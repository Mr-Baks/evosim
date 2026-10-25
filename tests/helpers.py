"""Shared helpers for building test creatures.

Since the genetics integration, creature logic (biochemistry, decision
utilities) derives its behaviour from a Genome component. Tests create
deterministic genomes with known gene values here.

``default_genes`` returns a genome whose *derived* traits are documented
below, so tests can assert against a stable baseline. Ageing genes are
chosen so that senescence is negligible at a single tick of age, keeping
the older metabolism/reproduction tests meaningful.
"""
from genome import Gene, GeneNames, Genome


def default_genes(**overrides) -> Genome:
    """A deterministic gene set with predictable derived traits.

    Deriving values (same for both alleles, dominant) means the phenotype
    equals the given gene value exactly. Defaults map to:

        metabolism      = 0.0   -> 0.01 * (2 / 0.01) ** 0.5      (~0.1414 energy/weight)
        speed           = 0.0   -> (1, 3)  -> 2
        senescence_shape= -1.0  -> (1, 3)  -> 1   (linear wear, a = 1)
        wear_resistance = 1.0   -> (180, 700) log -> 700 (slow ageing)
        regeneration_threshold = -1.0 -> (0, 1) -> 0 (regeneration disabled)
        reproduction cooldown (MateCommand scaling (0.001, 300)) = 100 + 300 = 400
        crowd_preference = -0.5 -> aversion 0.5 (prefers open space)
        plant_appetence = 0.5 -> attraction 0.5 (prefers plant cover)
        food_appetence = 0.5 -> attraction 0.5 (prefers food when hungry)

    Override individual genes via keyword arguments, e.g.:

        default_genes(hunger_drive=1.0, sleep_drive=0.5)

    or pass derived gene names with their ``GeneNames`` constants to stay
    independent of the string literals.
    """
    values = {
        GeneNames.SPEED: 0.0,
        GeneNames.METABOLISM: 0.0,
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
        GeneNames.SENESCENCE_SHAPE: -1.0,
        GeneNames.WEAR_RESISTANCE: 1.0,
        GeneNames.REGENERATION_THRESHOLD: -1.0,
        GeneNames.REGENERATION_INCREASE: -1.0,
        GeneNames.CROWD_PREFERENCE: -0.5,
        GeneNames.PLANT_APPETENCE: 0.5,
        GeneNames.FOOD_APPETENCE: 0.5,
        GeneNames.VISION_RADIUS: 0.76,
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
