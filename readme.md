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
- **Genetics** – `Genome` of `Gene`s with allele dominance, phenotype scaling,
  crossover with clamped mutation, and recombination
- **Utility-based AI** – decisions pick the highest-utility action
  (eat / sleep / mate / wander) weighted by genetic drives
- **Reproduction** – mating with cooldown, offspring recombine both genomes
- **Plants** – stationary energy sources that grow and drop fruit
- **Modular & extensible** – add components, commands, genes or event handlers
  without touching the core loop

## Architecture Overview

```
Entity
  ├── Movable       (speed, movement_accumulator)
  ├── Biochemistry  (energy, hunger, health)
  ├── Vision        (radius, visibles)
  ├── CommandQueue  (queue, running)
  ├── State         (current, states)
  ├── Breedable     (fertility, cooldown)
  ├── Render        (symbol, color, is_visible)
  ├── Genome        (genes)
  └── … (Eatable, Plant, etc.)

Systems registered in main.py (higher priority runs first):
  - vision_system        – populates Vision.visibles                  (priority 200)
  - decision_system      – utility-based AI, pushes commands         (priority 100)
  - plant_system         – grows plants, spawns fruit                 (priority 75)
  - biochemistry_system  – metabolism, regeneration, death            (priority 70)
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
├── main.py           # Entry point: world setup, system registration, spawning, tick stats
├── entity.py         # Entity, Component base classes and all component types (except Genome)
├── genome.py         # Gene, GeneNames, Genome (heredity, recombination, mutation)
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
    energy: int = 100
    hunger: int = 100
    health: int = 100
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

**GeneNames** – predefined genes. Values are raw alleles in `[-1, 1]`; systems
usually rescale them via `Genome.get_phenotype`:

| Name | Usage | Scale |
|------|-------|-------|
| `speed` | Energy/hunger drain rate (`biochemistry_system`) and, via `create_child`, `Movable.speed` | raw for metabolism; `(0, 5)` for movement |
| `metabolism` | Multiplier in metabolism, drain, regen and healing | raw |
| `hunger_drive` | Weight of the `eat` utility | `(0, 1)` |
| `sleep_drive` | Weight of the `sleep` utility | `(0, 1)` |
| `mating_drive` | Weight of the `mating` utility | `(0, 1)` |
| `exploration_drive` | Weight of the `idle`/wander utility | `(0, 1)` |
| `mating_energy_threshold` | Minimum energy required to mate | `(0, 200)` |
| `mating_hunger_threshold` | Minimum hunger required to mate | `(0, 200)` |
| `fertility` | Offspring `Breedable.fertility` | `(0, 1)` |
| `color_r`, `color_g`, `color_b` | Offspring render colour | `(0, 256)` |

**Genome** – component holding a `dict[str, Gene]`.

```python
genome.get_phenotype(name, scaling=(None, None), default=None)
```

- Without scaling (or with a `None` bound) it returns the raw phenotype.
- With `scaling=(lo, hi)` it maps the raw `[-1, 1]` phenotype linearly onto
  `[lo, hi]`: `((raw + 1) * (hi - lo) / 2) + lo`.
- Returns `default` when the gene is absent.

```python
genome1.recombine(genome2, mutation_rate=0.1, strength=0.3) -> Genome
```

Recombination crosses every gene present in **both** parents; if the gene sets
differ it raises `ValueError('Different genomes. …')`.

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

- Computes the full path on the first tick, or after being blocked.
- Follows the path one step per unit of `Movable.speed`, accumulating fractional
  speed in `movement_accumulator`.
- On a blocked step, replans; after **more than 7** failed steps the command
  fails.
- Diagonal cost = `1.414`, cardinal = `1.0`.
- Ignores the moving entity itself; treats every other entity as a wall (the
  goal cell may be occupied).

```python
def _find_path(self, world, start, ignore_entity=None):
    # Standard A* with Manhattan heuristic
    # Returns a list of (x, y) positions excluding the start
```

## Components Reference

| Component | Fields | Purpose |
|-----------|--------|---------|
| `State` | `current: str`, `states: set[str]` | Current action + active state set |
| `Render` | `symbol: str`, `color: (r,g,b)`, `is_visible: bool` | Console rendering |
| `Movable` | `speed: float`, `movement_accumulator: float` | Movement (steps accumulate) |
| `Biochemistry` | `energy: int`, `hunger: int`, `health: int` | Vital stats |
| `Eatable` | `nutrition: int` | Food value |
| `Breedable` | `fertility: float`, `cooldown: int` | Reproduction (`fertility` defaults to `100`, but offspring receive a value in `[0, 1]`) |
| `Vision` | `radius: int`, `visibles: set[Entity]` | Perception |
| `Plant` | `energy: int`, `energy_increase: int`, `fructify_threshold: int`, `fruit_nutrition: int` | Plant growth |
| `Genome` | `genes: dict[str, Gene]` | Heritable genetic data |

## Systems Reference

| System | Required Components | Priority | Description |
|--------|---------------------|----------|-------------|
| `vision_system` | `Vision` | 200 | Populates `Vision.visibles` with neighbours in radius |
| `decision_system` | `CommandQueue`, `State` | 100 | Utility-based AI; skips entities lacking `Biochemistry`/`Vision`/`Genome` |
| `plant_system` | `Plant` | 75 | Grows energy (cap 180) and drops fruit when above `fructify_threshold` |
| `biochemistry_system` | `CommandQueue`, `Biochemistry` | 70 | Metabolism, regeneration, starvation → death |
| `command_system` | `CommandQueue` | 50 | Picks next ready command and executes the running one |
| `logging_system` | `CommandQueue`, `State`, `Biochemistry` | 0 | Writes per-entity state and utilities to `logs/last_tick.txt` |

## Decision Logic (utility-based)

`decision_system` computes four utilities and picks the maximum:

| Action | Utility |
|--------|---------|
| `eat` | `(1 - hunger/200) · clamp(food_in_vision / 3, 0.01, 1) · hunger_drive` |
| `sleep` | `(1 - energy/200) · sleep_drive` |
| `mating` | `((hunger + energy)/400) · clamp(partners_in_vision / 3, 0, 1) · mating_drive · fertility` (`-1` unless energy ≥ `mating_energy_threshold`, hunger ≥ `mating_hunger_threshold` and `cooldown == 0`; `fertility` is treated as `0` below `0.2`) |
| `idle` | `(1 - (hunger+energy)/400) · (1 - clamp(plants_in_vision / 5, 0, 1)) · exploration_drive · (1 - max(creatures_in_vision / 5, 0.01))` |

If the chosen action is already in `State.states`, the entity is left alone
(this prevents re-issuing a command that is already running). Otherwise:

1. **eat** – pick the nearest visible `Eatable`, move to a free cell next to it
   (`MoveToTargetCommand`, emergency 15) and eat (`EatCommand`, emergency 16);
   there is a 30% chance per tick to reconsider. If no reachable food, wander
   with `radius=6`.
2. **sleep** – `ticks = round((200 - energy) / 50)` (or `1` if hunger is `0`),
   `SleepCommand(energy_increase=50, emergency=10)`.
3. **mating** – pick the nearest visible partner, move next to it
   (`MoveToTargetCommand`, emergency 1) and mate (`MateCommand`, emergency 2).
4. **idle** – `WanderCommand(radius=8)`.

## Biochemistry (gene-driven)

```python
metabolism = genome.get_phenotype(GeneNames.METABOLISM)
speed      = genome.get_phenotype(GeneNames.SPEED)

# Energy/hunger drain when not sleeping
bio.energy = max(bio.energy - (1 + metabolism) * (2 + speed) ** 2, 0)
bio.hunger = max(bio.hunger - (1 + metabolism) * (2 + speed) ** 2 / 4, 0)

# Breedable cooldown ticks down each step
breedable.cooldown = max(breedable.cooldown - 1, 0)

# Starvation / exhaustion reduce health; death leaves a corpse
if bio.energy == 0: bio.health = max(bio.health - 1, 0)
if bio.hunger == 0: bio.health = max(bio.health - 1, 0)
if bio.health == 0: push_command(e, world, DeathCommand(emergency=100, corpse_nutrition=50))

# Regeneration
if bio.energy > 60 and bio.hunger > 60 and bio.health < 80:
    bio.health += 5 * (1 + metabolism)
    bio.energy -= 5
    bio.hunger -= 5
```

## Commands Reference

| Command | Emergency (as used in `main.py`/`decision_system`) | Target state | Description |
|---------|-----------------------------------------------------|--------------|-------------|
| `MoveToTargetCommand` | 15 (to food), 1 (to partner), inherits `WanderCommand`'s otherwise | `eat`/`mating`/`idle` | A\* pathfinding to `(x, y)` |
| `EatCommand` | 16 | `eat` | Consume adjacent food |
| `SleepCommand` | 10 | `sleep` | Rest `ticks_to_sleep` ticks, emit `SleepEvent` each tick |
| `MateCommand` | 2 | `mating` | Create offspring with a partner (genome recombination) |
| `WanderCommand` | 0 (default) | `eat`/`idle` | Random move within `radius`; pushes a `MoveToTargetCommand` |
| `DeathCommand` | 100 | – | Remove entity, optionally leave a corpse, append to `logs/log.txt` |

## Events Reference

| Event | Payload | Default handler effect |
|-------|---------|------------------------|
| `MoveEvent` | `source` | `bio.energy = max(0, bio.energy - 2)` |
| `SleepEvent` | `source`, `energy_increase` (default 30) | `bio.energy = min(bio.energy + energy_increase, 200)` |
| `EatEvent` | `source`, `nutrition` (default 35) | `bio.hunger = min(bio.hunger + nutrition, 200)` |

> `SleepCommand` passes `energy_increase=50`, so sleeping restores more energy
> than the event default.

## Configuration (main.py)

```python
s = Simulation(10, 10, (100, 40), background_sym='.')

# Event handlers
s.world.event_bus.subscribe(EatEvent, on_eat)
s.world.event_bus.subscribe(SleepEvent, on_sleep)
s.world.event_bus.subscribe(MoveEvent, on_move)

# System registration order matters (higher priority runs first)
s.register_system(frozenset([CommandQueue, State, Biochemistry]), logging_system, priority=0)
s.register_system(frozenset([CommandQueue]), command_system, priority=50)
s.register_system(frozenset([Vision]), vision_system, priority=200)
s.register_system(frozenset([CommandQueue, Biochemistry]), biochemistry_system, priority=70)
s.register_system(frozenset([Plant]), plant_system, priority=75)
s.register_system(frozenset([CommandQueue, State]), decision_system, priority=100)

# Per-tick callback
s.add_on_tick(tick_stats)

# Seed the world, then run for a fixed number of ticks
for _ in range(120): make_plant(random.randint(0, s.world.width - 1), ..., s.world)
for _ in range(40):  make_creature(random.randint(0, s.world.width - 1), ..., s.world)

s.run(target_tick=1200)
```

### Creature Factory (main.py)

```python
def make_creature(x, y, world, color=(80, 120, 200)):
    genes = [
        Gene(GeneNames.SPEED, -0.6, -0.6, dominant=False),
        Gene(GeneNames.HUNGER_DRIVE, 0.5, 0.5),
        Gene(GeneNames.SLEEP_DRIVE, 0.5, 0.5),
        Gene(GeneNames.EXPLORATION_DRIVE, 0.5, 0.5),
        Gene(GeneNames.COLOR_R, (color[0] - 128) / 128, -1, dominant=False),
        Gene(GeneNames.COLOR_G, (color[1] - 128) / 128, -1, dominant=False),
        Gene(GeneNames.COLOR_B, (color[2] - 128) / 128, -1, dominant=False),
        Gene(GeneNames.METABOLISM, 0.1, 0.2, dominant=False),
        Gene(GeneNames.MATING_DRIVE, 1, 1),
        Gene(GeneNames.MATING_ENERGY_THRESHOLD, -0.2, -0.2),
        Gene(GeneNames.MATING_HUNGER_THRESHOLD, -0.2, -0.2),
        Gene(GeneNames.FERTILITY, -0.5, -0.5),
    ]
    e = (Entity()
         .add_component(Movable())
         .add_component(Biochemistry())
         .add_component(Vision(8))
         .add_component(CommandQueue())
         .add_component(State())
         .add_component(Breedable())
         .add_component(Render(symbol='C', color=color))
         .add_component(Genome(genes)))
    world.place_entity(e, x, y)
```

`make_food()` spawns a standalone `Eatable`, `make_plant()` spawns a `Plant`
with a random `fructify_threshold` in `[70, 90]`.

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
3. Read it with `genome.get_phenotype(GeneNames.NEW_GENE, scaling, default)` in
   the relevant utility/system.

### Add a New Event

1. Subclass `Event` (add payload fields).
2. `emit` it from a command or system.
3. Subscribe a handler via `world.event_bus.subscribe(EventType, handler)`.

## Testing

```bash
python -m pytest tests/ -v
```

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
- Speciation and population statistics
- Config file for simulation parameters

## License

MIT License – free to use, modify, and distribute.
