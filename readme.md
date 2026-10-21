# EvoSim

A turn-based, grid-based evolution simulation where creatures with genetics and
biochemistry roam, eat, sleep, reproduce and die. Built with a custom ECS-like
architecture, command-queue system, event bus, A* pathfinding, and
heredity-based genetics.

## Features

- **Entity-Component-System (ECS) backbone** – data and logic cleanly separated
- **Command queue** – sequential actions with priority and emergency interrupts,
  plus `CommandGroup` for multi-step actions
- **Event bus** – side effects (energy cost of movement, eating, sleeping)
  decoupled from commands and systems
- **A\* pathfinding** – multi-step movement with obstacle avoidance and
  automatic replanning
- **Vision system** – each creature perceives nearby entities within a radius
- **Biochemistry** – energy, hunger and health with metabolism, regeneration,
  starvation and death (leaving a corpse)
- **Senescence** – accumulated wear with age lowers vitality, max health and
  fertility, so old age emerges from biochemistry rather than a hard timer
- **Genetics** – `Genome` of `Gene`s with allele dominance, phenotype scaling,
  crossover with clamped mutation, and recombination
- **Centralised phenotype** – every gene scaling and physiology formula lives in
  `traits.py`; systems, commands and tests read the same derived `Traits`
- **Utility-based AI** – decisions pick the highest-utility action
  (eat / sleep / mate / wander) weighted by genetic drives
- **Reproduction** – mating with a lifespan-linked cooldown, offspring recombine
  both genomes and inherit a real generation counter
- **Lineage** – every creature carries `Lineage(generation, parents_eid)`;
  founders start at generation `0`, children get `max(parents) + 1`
- **Plants** – stationary energy sources that grow and drop fruit
- **Modular & extensible** – add components, commands, genes or event handlers
  without touching the core loop

## Architecture Overview

```
Entity
  ├── Movable       (speed, movement_accumulator)
  ├── Biochemistry  (energy, hunger, health, max_health, vitality, age)
  ├── Vision        (radius, visibles)
  ├── CommandQueue  (queue, running)
  ├── State         (current, states)
  ├── Breedable     (fertility, cooldown)
  ├── Render        (symbol, color, is_visible)
  ├── Genome        (genes)
  ├── Lineage       (generation, parents_eid)
  └── … (Eatable, Plant, etc.)

Systems registered in main.py (higher priority runs first):
  - vision_system        – populates Vision.visibles                  (priority 200)
  - decision_system      – utility-based AI, pushes commands         (priority 100)
  - plant_system         – grows plants, spawns fruit                 (priority 75)
  - biochemistry_system  – ageing/wear, metabolism, regeneration, death (priority 70)
  - command_system       – executes the running command               (priority 50)
  - logging_system       – dumps per-entity utilities to logs/        (priority 0)

Communication: Commands → Events → EventBus → handlers.
```

## Quick Start

### Prerequisites

- **Python 3.14+** — the code uses deferred annotation evaluation (PEP 649,
  e.g. `set[Entity]` referenced before `Entity` is defined) and nested-quote
  f-strings (PEP 701, 3.12+).
- No third-party dependencies (standard library only).

### Running

```bash
git clone https://github.com/Mr-Baks/evosim.git
cd evosim
python main.py
```

The console displays a grid:

- `C` – creature
- `P` – plant
- `f` – fruit (food)
- `D` – corpse (food)
- `.` – empty cell

Colors indicate creature lineage (derived from the genome). The demo runs for
1200 ticks and prints per-tick stats (population, food, average speed). The
`logs/` directory receives text dumps; close the terminal to stop.

## Project Structure

```
evosim/
├── main.py           # Entry point: build_simulation(cfg) / main(cfg); import-safe
├── config.py         # SimConfig (Run/Scenario/Balance), TOML + CLI loading
├── entity.py         # Entity, Component base classes and all component types (except Genome)
├── genome.py         # Gene, GeneNames, Genome (heredity, recombination, mutation)
├── traits.py         # Phenotype: gene -> derived Traits + physiology formulas
├── world.py          # World grid, QueryIndex (ECS query engine), spatial queries
├── commands.py       # Command base, CommandQueue, CommandGroup, all commands, A* pathfinding
├── systems.py        # Simulation systems (decision, command, vision, biochemistry, plant, logging)
├── simulation.py     # Main loop, fixed timestep, rendering, system scheduling
├── event_bus.py      # EventBus, event types and default handlers
├── logs/             # Runtime logs (git-ignored): log.txt, error_log.txt, last_tick.txt
└── tests/            # Unit/integration tests
```

## Core Concepts

### Entity-Component-System (ECS)

**Entity** – lightweight container with position `(x, y)` and a set of
components.

**Component** – pure data (dataclass). No logic.

```python
@dataclass
class Biochemistry(Component):
    energy: float = 100
    hunger: float = 100
    health: float = 100
    max_health: float = 100   # scales with vitality
    vitality: float = 1       # 1 at birth, 0 at the end of life
    age: float = 0            # chronological age in ticks
```

**System** – a function that processes all entities having a specific component
combination.

```python
def biochemistry_system(entities: set[Entity], world: World):
    for e in entities:
        bio = e.get_component(Biochemistry)
        bio.energy = max(bio.energy - 1, 0)
        ...
```

**QueryIndex** – maintains inverted indices for fast component lookups and
caches the entity set of every registered system. Because adding or removing
components during iteration would corrupt those caches, structural changes while
the index is locked must go through `world.add_component` /
`world.remove_component` / `world.place_entity` / `world.remove_entity`; they are
queued and applied by `world.flush_pending()` after all systems finish.

### Genome & Genetics

**Gene** – has two alleles and a dominance flag.

- Phenotype = `max(allele1, allele2)` if dominant, else `(allele1 + allele2) / 2`.
- `crossover(gene, mutation_rate=0.05, strength=0.1)` picks each allele from one
  of the two parents and, with probability `mutation_rate`, shifts each allele by
  a uniform value in `[-strength, strength]`, clamped to `[-1, 1]`.

```python
class Gene:
    def __init__(self, name: str, allele1: float, allele2: float, dominant: bool = True): ...
    @property
    def phenotype(self) -> float: ...
    def crossover(self, gene, mutation_rate=0.05, strength=0.1) -> Gene: ...
```

**GeneNames** – predefined genes, raw alleles in `[-1, 1]`. Their scalings and
physiological effects are centralised in `traits.py` (see *Phenotype &
Biochemistry* below); `Genome.get_phenotype` is the low-level primitive those
scalings are built on.

**Genome** – component holding a `dict[str, Gene]`.

```python
genome.get_phenotype(name, scaling=None, default=None, log=False)
```

- Without scaling it returns the raw phenotype (a value in `[-1, 1]`).
- With `scaling=(lo, hi)` it maps the raw `[-1, 1]` phenotype linearly onto
  `[lo, hi]`: `((raw + 1) * (hi - lo) / 2) + lo`.
- With `log=True` it maps **geometrically** instead:
  `lo * (hi / lo) ** ((raw + 1) / 2)`. Use this for multiplicative/scale
  traits (lifespan, metabolism) and the linear form for shapes, fractions
  and offsets.
- Returns `default` (defaults to `None`) when the gene is absent.

```python
genome1.recombine(genome2, mutation_rate=0.1, strength=0.3) -> Genome
```

Recombination crosses every gene present in **both** parents; if the gene sets
differ it raises `ValueError('Different genomes. …')`.

### Lineage & Generations

`Lineage` is a plain component added by `make_creature` and copied to every
child by `create_child`. `MateCommand` then sets:

```python
lineage = child.get_component(Lineage)
lineage.generation = max(parent1.generation, parent2.generation) + 1
lineage.parents_eid = (parent2.eid, parent1.eid)
```

- Founders are generation `0` with `parents_eid is None`.
- A child of generations `2` and `5` becomes generation `6`, never `7`.
- Entities created without `Lineage` (e.g. hand-built test fixtures) are treated
  as generation `0`; `create_child` always gives the child a `Lineage`.
- `Lineage` is **not** a system requirement: `decision_system` works without it,
  so older fixtures and non-creature entities keep working.

Experiments report both the legacy `generation_est` (a births-per-capita rough
estimate) and the real `generation_mean` / `generation_max`.

### Command Queue

Each creature has a `CommandQueue` holding pending commands and one `running`
command.

- **Priority** – higher runs first when emergencies are equal.
- **Emergency** – a new command interrupts the running one if its emergency is
  strictly higher and `is_ready()` returns `True`.
- **Target state** – a string added to `State.states` while the command runs
  (`eat`, `sleep`, `mating`, `idle`). `decision_system` uses it to avoid
  re-issuing an action that is already active.

```python
push_command(entity, world, MoveToTargetCommand(x=10, y=5, emergency=15, target_state='eat'),
                             EatCommand(target_x=10, target_y=5, emergency=16, target_state='eat'),
                             target_state='eat')
```

Passing more than one command to `push_command` wraps them in a `CommandGroup`
that runs them in order. Commands implement:

- `execute(entity, world)` – performs one tick of work
- `is_ready(entity, world)` – can this command run now?
- `on_interruption(entity)` – cleanup when interrupted
- `complete(entity, status)` – marks done, clears the target state

### Event Bus

Decouples side effects from command execution.

```python
# Emit from a command or system
world.event_bus.emit(EatEvent(source=entity, nutrition=20))

# Subscribe (in main.py)
world.event_bus.subscribe(EatEvent, on_eat)

# Handler
def on_eat(event: EatEvent):
    bio = event.source.get_component(Biochemistry)
    if bio: bio.hunger = min(bio.hunger + event.nutrition, 200)
```

Events are queued and dispatched in priority order (highest first) after all
systems run for the tick.

### A\* Pathfinding (`MoveToTargetCommand`)

- Tries a cheap **line-of-sight** shortcut first: if the greedy 8-way line to the
  goal is unobstructed, the entity walks it directly and A\* is skipped.
- Otherwise runs **A\*** with the **octile** heuristic (the exact cost of an
  unobstructed 8-way walk): diagonal cost = `1.414`, cardinal = `1.0`.
- Each search is capped at **400 node expansions** (bounds the worst case in
  open or crowded maps).
- Follows the path one step per unit of `Movable.speed`, accumulating fractional
  speed in `movement_accumulator`.
- On a blocked step the entity does **not** idle: it sidesteps into the free
  neighbour that keeps it closest to the goal, never stepping back onto the cell
  it just left. After **more than 7** blocked steps the command fails.
- Ignores the moving entity itself; treats every other entity as a wall (the
  goal cell may be occupied - that is what triggers a sidestep).

Determinism: neighbours are always scanned in a fixed order and priority-queue
ties are broken by insertion order, so equal states yield equal paths.

```python
def _route(self, world, entity):
    # straight line if clear, otherwise A*
    # returns a list of (x, y) positions excluding the start

def _find_path(self, world, start, ignore_entity=None):
    # A* with octile heuristic, node cap, deterministic tie-break
```

## Components Reference

| Component | Fields | Purpose |
|-----------|--------|---------|
| `State` | `current: str`, `states: set[str]` | Current action + active state set |
| `Render` | `symbol: str`, `color: (r,g,b)`, `is_visible: bool` | Console rendering |
| `Movable` | `speed: float`, `movement_accumulator: float` | Movement (steps accumulate) |
| `Biochemistry` | `energy: float`, `hunger: float`, `health: float`, `max_health: float`, `vitality: float`, `age: float` | Vital stats + ageing |
| `Eatable` | `nutrition: int` | Food value |
| `Breedable` | `fertility: float`, `cooldown: int` | Reproduction (`fertility` defaults to `1`; scaled by vitality each tick) |
| `Vision` | `radius: int`, `visibles: list[Entity]` | Perception |
| `Plant` | `energy: int`, `energy_increase: int`, `fructify_threshold: int`, `fruit_nutrition: int` | Plant growth |
| `Genome` | `genes: dict[str, Gene]` | Heritable genetic data |
| `Lineage` | `generation: int`, `parents_eid: tuple[int, int] \| None` | Generation counter and parent ids (`None` for founders) |

## Systems Reference

| System | Required Components | Priority | Description |
|--------|---------------------|----------|-------------|
| `vision_system` | `Vision` | 200 | Populates `Vision.visibles` with neighbours in radius |
| `decision_system` | `CommandQueue`, `State` | 100 | Utility-based AI; skips entities lacking `Biochemistry`/`Vision`/`Genome` |
| `plant_system` | `Plant` | 75 | Grows energy (cap 150) and drops fruit when above `fructify_threshold` |
| `biochemistry_system` | `CommandQueue`, `Biochemistry` | 70 | Ageing/wear, metabolism, regeneration, starvation → death (guards a missing `Breedable`) |
| `command_system` | `CommandQueue` | 50 | Picks next ready command and executes the running one |
| `logging_system` | `CommandQueue`, `State`, `Biochemistry` | 0 | Writes per-entity state and utilities to `logs/last_tick.txt` |

## Decision Logic (utility-based)

`decision_system` computes four utilities and picks the maximum:

| Action | Utility |
|--------|---------|
| `eat` | `(1 - hunger/200) · clamp(food_in_vision / 3, 0.01, 1) · hunger_drive` |
| `sleep` | `(1 - energy/200) · sleep_drive` |
| `mating` | `((hunger + energy)/400) · clamp(partners_in_vision / 3, 0, 1) · mating_drive · fertility` (`-1` unless energy ≥ `mating_energy_threshold`, hunger ≥ `mating_hunger_threshold` and `cooldown == 0`; `fertility` is treated as `0` below `0.2`) |
| `idle` | `max(0, 0.10·exploration_drive + 0.15·crowd_density·(crowd_aversion - crowd_affinity) + 0.05·starvation·plant_absence·plant_appetence)`, where `starvation = 1 - clamp(hunger/200, 0, 1)`, `crowd_density = clamp(creatures_in_vision/5, 0, 1)`, `plant_absence = 1 - clamp(plants_in_vision/5, 0, 1)`, `crowd_aversion = max(0, -crowd_preference)`, `crowd_affinity = max(0, crowd_preference)`. The terms are deliberately small because `idle` is a fallback: larger weights make creatures wander instead of feeding and breeding |

If the chosen action is already in `State.states`, the entity is left alone
(this prevents re-issuing a command that is already running). Otherwise:

1. **eat** – pick the nearest visible `Eatable`, move to a free cell next to it
   (`MoveToTargetCommand`, emergency 15) and eat (`EatCommand`, emergency 16);
   there is a 30% chance per tick to reconsider. If no reachable food, wander
   with `radius=6`.
2. **sleep** – `ticks = round((200 - energy) / 45)` (or `1` if hunger is `0`),
   `SleepCommand(energy_increase=45, emergency=10)`.
3. **mating** – pick the nearest visible partner, move next to it
   (`MoveToTargetCommand`, emergency 1) and mate (`MateCommand`, emergency 2).
4. **idle** – `WanderCommand(radius=8)`; crowding raises the idle utility when
   `crowd_aversion > 0`, so dense clusters disperse and repeated local mating is
   damped. A starving creature with no plants nearby also wanders more, while
   plant cover and satiety reduce the urge to move.

## Phenotype & Biochemistry (`traits.py`)

Every gene scaling and every physiological formula lives in **one place**,
`traits.py`. `traits_for(genome)` derives a frozen `Traits` object once per
genome and memoises it on the genome itself (a genome is immutable after birth,
so the result is constant for the entity's whole life).

Scaling and formulas are grouped by gene, which makes **pleiotropy** explicit:
`speed` becomes both `traits.speed.locomotion` (body speed) and
`traits.speed.metabolic` (drain multiplier); `wear_resistance` becomes both
`traits.wear_resistance.aging` (lifespan `L`) and `traits.wear_resistance.cooldown`
(reproduction cooldown). Nothing in `systems.py` reads a raw scale any more.

```python
from traits import traits_for

traits = traits_for(genome)                       # derived once, cached on the genome

# --- Ageing: accumulated wear -------------------------------------------------
bio.age += 1
wear = traits.wear(bio.age)                       # wear_resistance plays the role of L
bio.vitality = traits.vitality(bio.age)           # damage = (age / L) ** senescence_shape
bio.max_health = traits.max_health(bio.vitality)
breedable.fertility = traits.effective_fertility(bio.vitality)

# --- Metabolism (when not sleeping) ------------------------------------------
bio.energy = max(bio.energy - traits.energy_drain(bio.vitality), 0)
bio.hunger = max(bio.hunger - traits.hunger_drain(), 0)

# --- Reproduction cooldown ----------------------------------------------------
breedable.cooldown = max(breedable.cooldown - 1, 0)

# --- Starvation / exhaustion reduce health ------------------------------------
if bio.energy == 0: bio.health = max(bio.health - 1, 0)
if bio.hunger == 0: bio.health = max(bio.health - 1, 0)

# --- Regeneration -------------------------------------------------------------
if bio.energy > 60 and bio.hunger > 60 and bio.health < traits.regeneration_threshold * bio.max_health:
    cost = traits.regeneration_cost()
    bio.health += traits.regeneration_gain(bio.vitality)
    bio.energy -= cost
    bio.hunger -= cost

# --- Health is capped by vitality; death is emergent --------------------------
bio.health = min(bio.health, bio.max_health)
if bio.health <= 0:
    push_command(e, world, DeathCommand(emergency=100, corpse_nutrition=50))
```

The base scalings are:

| Gene | Effect | Scale |
|------|--------|-------|
| `metabolism` | `Traits.metabolism` — multiplier in drain and regeneration cost | `(0.01, 2)`, log |
| `speed` | `Traits.speed.locomotion` / `Traits.speed.metabolic` | `(0, 5)` / `(1, 3)` |
| `fertility` | `Traits.fertility` | `(0, 1)` |
| `senescence_shape` | `Traits.senescence_shape` | `(1, 3)` |
| `wear_resistance` | `Traits.wear_resistance.aging` / `.cooldown` | `(180, 700)` log / `(0.001, 300)` log |
| `regeneration_threshold` | `Traits.regeneration_threshold` | `(0, 1)` |
| `regeneration_increase` | `Traits.regeneration_increase` | `(1, 5)` |
| `hunger_drive` … `exploration_drive` | utility weights | `(0, 1)` |
| `crowd_preference` | `Traits.crowd_preference` — negative avoids crowds (raises idle in a crowd), positive prefers them (lowers idle in a crowd) | raw `(-1, 1)` |
| `plant_appetence` | `Traits.plant_appetence` — attraction to plant cover; wander uses `max(0, plant_appetence)` | raw `(-1, 1)` |
| `mating_*_threshold` | minimum stat to mate | `(0, 200)` |
| `color_r/g/b` | offspring colour | `(0, 256)` |

| Formula | Method |
|---------|--------|
| `wear = min(1, age / L)` | `Traits.wear(age)` |
| `vitality = max(0, 1 - wear ** a)` | `Traits.vitality(age)` |
| `max_health = vitality * 100` | `Traits.max_health(vitality)` |
| `energy = metabolism · speed² · (2 - vitality)` | `Traits.energy_drain(vitality)` |
| `hunger = metabolism · speed² · (L / 710)` | `Traits.hunger_drain()` |
| `fertility · min(1, vitality·2) · (1 - a/3)` | `Traits.effective_fertility(vitality)` |
| `regen_increase · metabolism · vitality` | `Traits.regeneration_gain(vitality)` |
| `regen_increase² · metabolism / 2` | `Traits.regeneration_cost()` |

### The ageing model

Ageing is a **Weibull-style accumulated-wear** model, split so that each gene
controls a separate property:

- `wear_resistance` is the characteristic lifespan `L` (scale). Wear is the
  normalised age `age / L`, capped at `1`.
- `senescence_shape` is the Weibull exponent `a` (shape). Damage is
  `wear ** a`, so `a = 1` is linear (no senescence), `a > 1` accelerates late
  in life, and vitality is `1 - damage`.
- `vitality` drives `max_health`, regeneration strength and fertility, so
  ageing is felt through several channels instead of a death flag.
- `age` is **chronological age in ticks** and is never re-scaled by genes, so
  it can be used directly for lifespan and survivorship statistics.
- The formulas above are `Traits` methods, so the code block, the systems and
  the tests all share a single implementation.

Death is not scheduled: as `age` approaches `L`, vitality → 0, `max_health` → 0,
`health` is clamped to 0 and the normal `DeathCommand` path fires (leaving a
corpse). With the default grid you can therefore plot survivorship `l(t)`
against chronological age `t`.

> Trade-off note: `(1 - senescence_shape / 3)` gives a maximum-shape creature
> zero fertility, linking longevity to reproduction. Without such a cost,
> selection drives `wear_resistance` and `senescence_shape` to their bounds and
> ageing disappears.

## Commands Reference

| Command | Emergency (as used in `main.py`/`decision_system`) | Target state | Description |
|---------|-----------------------------------------------------|--------------|-------------|
| `MoveToTargetCommand` | 15 (to food), 1 (to partner), inherits `WanderCommand`'s otherwise | `eat`/`mating`/`idle` | A\* pathfinding to `(x, y)` |
| `EatCommand` | 16 | `eat` | Consume adjacent food |
| `SleepCommand` | 10 | `sleep` | Rest `ticks_to_sleep` ticks, emit `SleepEvent` each tick |
| `MateCommand` | 2 | `mating` | Create offspring with a partner (genome recombination); the child's colour and speed come from `traits_for(child_genome)`, and both cooldowns are set to `100 + traits.wear_resistance.cooldown` |
| `WanderCommand` | 0 (default) | `eat`/`idle` | Random move within `radius`; pushes a `MoveToTargetCommand` |
| `DeathCommand` | 100 | – | Remove entity, optionally leave a corpse, append to `logs/log.txt` |

## Events Reference

| Event | Payload | Default handler effect |
|-------|---------|------------------------|
| `MoveEvent` | `source` | `bio.energy = max(0, bio.energy - 2)` |
| `SleepEvent` | `source`, `energy_increase` (default 30) | `bio.energy = min(bio.energy + energy_increase, 200)` |
| `EatEvent` | `source`, `nutrition` (default 35) | `bio.hunger = min(bio.hunger + nutrition, 200)` |

> `SleepCommand` passes `balance.sleep_energy_increase` (45 by default), so
> sleeping restores more energy than the event default.

## Configuration (`config.py` + `main.py`)

All run parameters live in a frozen `SimConfig` made of three layers, grouped
by how often they change:

| Layer | Purpose | Example fields |
|-------|---------|----------------|
| `RunConfig` | a single run | `seed`, `ticks`, `record_every`, `output_dir`, `headless`, `tickspeed`, `fps` |
| `ScenarioConfig` | initial conditions | `world`, `initial_plants`, `initial_creatures`, `creature_color`, `founder_genes` |
| `BalanceConfig` | world "physics", read by systems via `world.balance` | `mating_energy_cost`, `corpse_nutrition`, utility saturations, ... |

Precedence: **dataclass defaults → TOML file → CLI flags**.

```python
from config import load_config, SimConfig
cfg = load_config("scenario.toml")   # or load_config() for defaults
cfg.run.seed                 # 1
cfg.scenario.world.size      # (100, 40)
cfg.scenario.founder_genes   # ((name, allele1, allele2, dominant), ...)
```

```bash
python main.py --seed 7 --ticks 2000 --headless
python main.py --config scenario.toml --output-dir results/run1
```

`main.build_simulation(cfg)` assembles the world from `cfg` without stepping.
`main.main(cfg)` seeds the RNG from `cfg.run.seed`, then either runs the
interactive loop (`sim.run`) or `run_headless` (no rendering, no wall-clock
pacing). Importing `main` has no side effects. `dump_config(cfg, path)` writes
the effective config next to results for reproducibility.

### System registration in `build_simulation`

```python
sim = Simulation(cfg.run.tickspeed, cfg.run.fps, cfg.scenario.world.size)

# logging/printing run only in interactive mode, skipped when headless
if not cfg.run.headless:
    sim.register_system(frozenset([CommandQueue, State, Biochemistry]), logging_system, priority=0)
    sim.add_on_tick(tick_stats)

# System registration order matters (higher priority runs first)
sim.register_system(frozenset([CommandQueue]), command_system, priority=50)
sim.register_system(frozenset([Vision]), vision_system, priority=200)
sim.register_system(frozenset([CommandQueue, Biochemistry]), biochemistry_system, priority=70)
sim.register_system(frozenset([Plant]), plant_system, priority=75)
sim.register_system(frozenset([CommandQueue, State]), decision_system, priority=100)
```

### Founder genome

The founder is `scenario.founder_genes`, a tuple of
`(name, allele1, allele2, dominant)` — an exact, configurable reproduction of
the genome that used to be hard-coded in `make_creature`. Color genes are
derived from `scenario.creature_color`. `make_food()` spawns a standalone
`Eatable`; `make_plant()` spawns a `Plant` with a random `fructify_threshold`
in `[plant_fructify_min, plant_fructify_max]`.

## Extending the Simulation

### Add a New Action

1. Subclass `Command`, implement `execute()`.
2. Optionally override `is_ready()` and `on_interruption()`.
3. In `decision_system`, push it when its utility wins.

### Add a New Component

1. Create a `@dataclass` inheriting from `Component`.
2. Add it to entities via `entity.add_component(...)` (before indexing) or
   `world.add_component(entity, ...)` (at runtime, while systems run).
3. Create a system processing entities with that component.
4. Register it via `simulation.register_system(frozenset([NewComponent]), system, priority)`.

### Add a New Gene

1. Add a name to `GeneNames` in `genome.py`.
2. Add it to the creature factory in `main.py` with the desired alleles.
3. Add its scaling and effect to `traits.py` (a new `Traits` field or method)
   and read it through `traits_for(genome)` in the relevant system or utility.

### Add a New Event

1. Subclass `Event` (add payload fields).
2. `emit` it from a command or system.
3. Subscribe a handler via `world.event_bus.subscribe(EventType, handler)`.

## Testing

```bash
python -m pytest tests/ -v
```

The suite is deterministic and runs each test in a throwaway working directory
that already contains a `logs/` folder (`tests/conftest.py`). Notable files:

- `tests/test_genome.py` – phenotype, dominance, crossover/mutation, and both
  the linear and **logarithmic** `get_phenotype` scalings.
- `tests/test_aging.py` – the senescence model: age accumulation, wear/vitality
  curves, `max_health` scaling, emergent end-of-life death, and reproductive
  senescence.
- `tests/test_traits.py` – derivation of every gene scaling, pleiotropy (one gene
  driving several effects), memoisation, and the physiology formulas.
- `tests/test_systems.py` – all systems, with biochemistry expectations read from
  the same `traits.py` formulas.
- `tests/test_lineage.py` – founders start at generation `0`, children get
  `max(parents) + 1`, parents' eids are recorded, and lineage is deterministic.

## Current Limitations & Roadmap

- **Basic AI** – stateless utility arbiter (no learning, no memory).
- **No predator/prey** – all creatures are the same species.
- **No sexual selection** – mate choice is nearest-in-vision.
- **No speciation** – a single gene pool.
- **Logging** – appends death/mating lines to `logs/log.txt`, command failures
  to `logs/error_log.txt`, and a per-tick snapshot to `logs/last_tick.txt`. The
  `logs/` directory must exist (a `.gitkeep` is committed).

**Planned:**

- Associative memory (avoid poisonous food, remember locations)
- Predator-prey dynamics with distinct species
- Neural network or GOAP-based AI
- Speciation analysis on top of the lineage tree
- Density-dependent population regulation

## License

MIT License – free to use, modify, and distribute.
