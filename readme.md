# EvoSim

A turn-based, grid-based evolution simulation where creatures with genetics and biochemistry roam, eat, sleep, reproduce and die. Built with a custom ECS-like architecture, command-queue system, event bus, A* pathfinding, and heredity-based genetics.

## Features

- **Entity-Component-System (ECS) backbone** – data and logic cleanly separated
- **Command queue** – creatures perform sequential actions with priority and emergency interrupts
- **Event bus** – side effects trigger independent systems (biochemistry updates, movement costs)
- **A* pathfinding** – multi-step movement with obstacle avoidance and replanning
- **Vision system** – each creature perceives nearby entities within radius
- **Biochemistry** – energy, hunger, health with sleep/eat mechanics
- **Genetics** – Genome with genes (speed, metabolism, color, thresholds), dominance, recombination, and mutation
- **Reproduction** – mating with cooldown, offspring inherit mixed genes via crossover
- **Plants** – stationary energy sources that grow and produce fruit
- **Modular & extensible** – add new components, commands, or event handlers without touching core logic

## Architecture Overview

```
Entity
  ├── Movable
  ├── Biochemistry (energy, hunger, health)
  ├── Vision
  ├── CommandQueue
  ├── State (current + state stack)
  ├── Breedable (fertility, cooldown)
  ├── Render (symbol, color, visibility)
  ├── Genome (heritable genes)
  └── … (Eatable, Plant, etc.)

System types (run in priority order):
  - decision_system      – evaluates needs, pushes commands into queue (priority 100)
  - vision_system        – populates Vision.visibles set (priority 80)
  - plant_system         – grows plants, spawns fruit (priority 75)
  - biochemistry_system  – updates hunger/energy/health, triggers death (priority 70)
  - command_system       – executes the current command of each creature (priority 50)
  - (user-defined systems)

Communication: Events → EventBus → handlers.
```

## Quick Start

### Prerequisites
- Python 3.10+

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

Colors indicate creature lineage (derived from genome). Close the terminal to stop.

## Project Structure

```
evosim/
├── main.py           # Entry point, world setup, system registration, creature/plant spawning
├── entity.py         # Entity, Component base classes, all component types (except Genome)
├── genome.py         # Gene, GeneNames, Genome component (heredity, recombination, mutation)
├── world.py          # World grid, QueryIndex (ECS query engine), spatial queries
├── commands.py       # Command base, CommandQueue, all command implementations, A* pathfinding
├── systems.py        # All simulation systems (decision, command, vision, biochemistry, plant)
├── simulation.py     # Main loop, fixed timestep, rendering, system scheduling
├── event_bus.py      # EventBus, Event types, default handlers
├── log.txt           # Death/mating logs (appended during simulation)
└── tests/            # Unit/integration tests
```

## Core Concepts

### Entity-Component-System (ECS)

**Entity** – lightweight container with position (x, y) and a set of components.

**Component** – pure data (dataclass). No logic.
```python
@dataclass
class Biochemistry(Component):
    energy: int = 100
    hunger: int = 100
    health: int = 100
```

**System** – function that processes all entities having a specific component combination.
```python
def biochemistry_system(entities: set[Entity], world: World):
    for e in entities:
        bio = e.get_component(Biochemistry)
        bio.energy = max(bio.energy - 1, 0)
        ...
```

**QueryIndex** – maintains inverted indices for O(1) component lookups and caches system entity sets. Handles deferred addition/removal during system execution.

### Genome & Genetics

**Gene** – has two alleles and a dominance flag. Phenotype = max(alleles) if dominant, else mean.
```python
class Gene:
    def __init__(self, name: str, allele1: float, allele2: float, dominant: bool = True):
        ...
    @property
    def phenotype(self) -> float: ...

    def crossover(self, gene, mutation_rate=0.05, strength=0.1) -> Gene: ...
```

**GeneNames** – predefined genes:
| Name | Purpose |
|------|---------|
| `speed` | Movement speed modifier |
| `metabolism` | Energy drain rate modifier |
| `color_r`, `color_g`, `color_b` | Color inheritance |
| `hunger_threshold` | Hunger level triggering food-seeking |
| `energy_threshold` | Energy level triggering sleep |

**Genome** – Component holding a dict of Genes. Supports recombination:
```python
genome1.recombine(genome2, mutation_rate=0.1, strength=0.3) -> Genome
```
Offspring inherit genes from both parents with crossover and mutation. Phenotypes drive behavior (see `biochemistry_system`, `decision_system`).

### Command Queue

Each creature has a `CommandQueue` holding pending commands and one `running` command.

- **Priority** – higher runs first when emergencies equal
- **Emergency** – can interrupt a running command if higher and `is_ready()`
- **Target state** – tracks what the creature is doing (`seeking_food`, `eating`, `sleeping`, `wandering`, `seeking_partner`, `breeding`)

```python
push_command(entity, world, MoveToTargetCommand(x=10, y=5, emergency=50, target_state='seeking_food'))
push_command(entity, world, EatCommand(target_x=10, target_y=5, emergency=51, target_state='eating'))
```

Commands implement:
- `execute(entity, world)` – performs one tick of work
- `is_ready(entity, world)` – can this command run now?
- `on_interruption(entity)` – cleanup when interrupted
- `complete(entity, status)` – marks done, clears state

### Event Bus

Decouples side effects from command execution.

```python
# Emit from command/system
world.event_bus.emit(EatEvent(source=entity, nutrition=20))

# Subscribe (typically in main.py)
world.event_bus.subscribe(EatEvent, on_eat)

# Handler
def on_eat(event: EatEvent):
    bio = event.source.get_component(Biochemistry)
    if bio: bio.hunger = min(bio.hunger + event.nutrition, 200)
```

Events are queued and dispatched in priority order after all systems run each tick.

### A* Pathfinding (`MoveToTargetCommand`)

- Computes full path on first tick or when blocked
- Follows path step-by-step each tick
- Replans after 3 failed attempts (dynamic obstacles)
- Diagonal cost = 1.414, cardinal = 1.0
- Ignores the moving entity itself; treats other entities as walls

```python
def _find_path(self, world, start, ignore_entity=None):
    # Standard A* with Manhattan heuristic
    # Returns list of (x, y) positions excluding start
```

## Components Reference

| Component | Fields | Purpose |
|-----------|--------|---------|
| `State` | `current: str`, `states: set[str]` | Current action + state stack |
| `Render` | `symbol: str`, `color: (r,g,b)`, `is_visible: bool` | Console rendering |
| `Movable` | `speed: float`, `movement_accumulator: float` | Movement capability |
| `Biochemistry` | `energy: int`, `hunger: int`, `health: int` | Vital stats |
| `Eatable` | `nutrition: int` | Food value |
| `Breedable` | `fertility: int`, `cooldown: int` | Reproduction |
| `Vision` | `radius: int`, `visibles: set[Entity]` | Perception |
| `Plant` | `energy: int`, `energy_increase: int`, `fructify_threshold: int`, `fruit_nutrition: int` | Plant growth |
| `Genome` | `genes: dict[str, Gene]` | Heritable genetic data |

## Systems Reference

| System | Required Components | Priority | Description |
|--------|---------------------|----------|-------------|
| `decision_system` | `CommandQueue`, `State`, `Vision`, `Biochemistry`, `Genome` | 100 | AI: evaluates needs using genome thresholds, pushes commands |
| `vision_system` | `Vision` | 80 | Populates visible entities |
| `plant_system` | `Plant` | 75 | Growth, fruit spawning |
| `biochemistry_system` | `Biochemistry`, `CommandQueue`, `Genome` | 70 | Metabolism (gene-driven), death detection |
| `command_system` | `CommandQueue` | 50 | Executes running command |

### Decision Logic (priority order, genome-driven)

1. **Energy < energy_threshold** → sleep (ticks = (200 - energy) / 15, min 1)
2. **Hunger < hunger_threshold** → seek food → move to adjacent cell → eat; fallback: wander with radius 8
3. **Energy > 70 & Hunger > 70 & cooldown=0** → seek partner → mate
4. **Idle** → wander (radius 4)

Thresholds are derived from genome:
```python
energy_threshold = genome.get_phenotype('energy_threshold') * 100 + 100  # default 70
hunger_threshold = genome.get_phenotype('hunger_threshold') * 100 + 100  # default 70
```

### Biochemistry (gene-driven)

```python
metabolism = genome.get_phenotype('metabolism', 0.0)
speed      = genome.get_phenotype('speed', 0.0)

# Energy drain when not sleeping
bio.energy -= (1 + metabolism) * (1 + abs(speed))
# Hunger drain
bio.hunger -= 0.5 + speed
```

## Commands Reference

| Command | Emergency | Target State | Description |
|---------|-----------|--------------|-------------|
| `MoveToTargetCommand` | variable | variable | A* pathfinding to (x,y) |
| `EatCommand` | 51 | `eating` | Consume adjacent food |
| `SleepCommand` | 60 | `sleeping` | Rest N ticks, gain energy/tick |
| `DeathCommand` | 100 | – | Remove entity, optional corpse (logs to log.txt) |
| `WanderCommand` | 49/0 | `wandering`/`seeking_*` | Random move within radius → pushes MoveToTargetCommand |
| `MateCommand` | 16 | `breeding` | Create offspring with partner (genome recombination) |

## Events Reference

| Event | Payload | Default Handler Effect |
|-------|---------|------------------------|
| `MoveEvent` | source | `bio.energy -= 2` |
| `SleepEvent` | source, `energy_increase` (default 15) | `bio.energy += energy_increase` (max 200) |
| `EatEvent` | source, `nutrition` | `bio.hunger += nutrition` (max 200) |

## Configuration (main.py)

```python
s = Simulation(10, 10, (180, 30), background_sym='.')

# System registration order matters (higher priority runs first)
s.register_system(frozenset([CommandQueue]), command_system, priority=50)
s.register_system(frozenset([Vision]), vision_system, priority=80)
s.register_system(frozenset([Biochemistry, CommandQueue]), biochemistry_system, priority=70)
s.register_system(frozenset([Plant]), plant_system, priority=75)
s.register_system(frozenset([CommandQueue, State]), decision_system, priority=100)

# Event handlers
s.world.event_bus.subscribe(EatEvent, on_eat)
s.world.event_bus.subscribe(SleepEvent, on_sleep)
s.world.event_bus.subscribe(MoveEvent, on_move)

# Per-tick callbacks
s.add_on_tick(tick_stats)

s.run()
```

### Creature Factory (main.py)

```python
def make_creature(x, y, world, color=(80, 120, 200)):
    genes = []
    genes.append(Gene(GeneNames.SPEED, 0.3, 0.3, dominant=False))
    genes.append(Gene(GeneNames.ENERGY_THRESHOLD, -0.3, -0.3))
    genes.append(Gene(GeneNames.HUNGER_THRESHOLD, -0.3, -0.3))
    genes.append(Gene(GeneNames.COLOR_R, (color[0] - 128) / 128, -1))
    genes.append(Gene(GeneNames.COLOR_G, (color[1] - 128) / 128, -1))
    genes.append(Gene(GeneNames.COLOR_B, (color[2] - 128) / 128, -1))
    genes.append(Gene(GeneNames.METABOLISM, 0.1, 0.2, dominant=False))
    e = Entity().add_component(Movable()).add_component(Biochemistry()).add_component(Vision(8)).add_component(CommandQueue()).add_component(State()).add_component(Breedable(cooldown=0)).add_component(Render(symbol='C', color=color)).add_component(Genome(genes))
    world.place_entity(e, x, y)
```

## Extending the Simulation

### Add a New Action
1. Subclass `Command`, implement `execute()`
2. Optionally override `is_ready()` and `on_interruption()`
3. In `decision_system`, push when conditions met

### Add a New Component
1. Create `@dataclass` inheriting from `Component`
2. Add to entities via `entity.add_component(...)`
3. Create a system processing entities with that component
4. Register via `simulation.register_system(frozenset([NewComponent]), system, priority)`

### Add a New Gene
1. Add name to `GeneNames` in `genome.py`
2. Add to creature factory in `main.py` with desired alleles
3. Use `_get_genome_phenotype(entity, GeneNames.NEW_GENE, default)` in systems

### Add a New Event
1. Subclass `Event` (add payload fields)
2. `emit` from command/system
3. Subscribe handler via `world.event_bus.subscribe(EventType, handler)`

## Testing

```bash
python -m pytest tests/ -v
```

## Current Limitations & Roadmap

- **Basic AI** – fixed priority decision tree (no learning, no memory)
- **No predator/prey** – all creatures same species
- **No sexual selection** – random mate choice within vision
- **No speciation** – single gene pool
- **Limited logging** – only death/mating to log.txt

**Planned:**
- Associative memory (avoid poisonous food, remember locations)
- Predator-prey dynamics with distinct species
- Neural network or GOAP-based AI
- Speciation and population statistics
- Config file for simulation parameters

## License

MIT License – free to use, modify, and distribute.