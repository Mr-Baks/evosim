# EvoSim

A turn-based, grid-based evolution simulation where creatures with basic biochemistry roam, eat, sleep, reproduce and die. Built with a custom ECS-like architecture, command-queue system, event bus, and A* pathfinding.

## Features

- **Entity-Component-System (ECS) backbone** – data and logic cleanly separated
- **Command queue** – creatures perform sequential actions with priority and emergency interrupts
- **Event bus** – side effects trigger independent systems (biochemistry updates, movement costs)
- **A* pathfinding** – multi-step movement with obstacle avoidance and replanning
- **Vision system** – each creature perceives nearby entities within radius
- **Biochemistry** – energy, hunger, health with sleep/eat mechanics
- **Reproduction** – mating with cooldown, offspring inherit mixed traits
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
  └── … (Eatable, Plant, etc.)

System types (run in priority order):
  - decision_system      – evaluates needs, pushes commands into queue
  - command_system       – executes the current command of each creature
  - vision_system        – populates Vision.visibles set
  - biochemistry_system  – updates hunger/energy/health, triggers death
  - plant_system         – grows plants, spawns fruit
  - (user-defined systems)

Communication: Events → EventBus → handlers.
```

## Quick Start

### Prerequisites
- Python 3.10+
- Computer

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
- `.` – empty cell

Colors indicate creature lineage. Close the terminal to stop.

## Project Structure

```
evosim/
├── main.py           # Entry point, world setup, system registration
├── entity.py         # Entity, Component base classes, all component types
├── world.py          # World grid, QueryIndex (ECS query engine), spatial queries
├── commands.py       # Command base, CommandQueue, all command implementations, A* pathfinding
├── systems.py        # All simulation systems (decision, command, vision, biochemistry, plant)
├── simulation.py     # Main loop, fixed timestep, rendering, system scheduling
├── event_bus.py      # EventBus, Event types, default handlers
└── tests/            # 156 unit/integration tests
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

**QueryIndex** – maintains inverted indices for O(1) component lookups and caches system entity sets.

### Command Queue

Each creature has a `CommandQueue` holding pending commands and one `running` command.

- **Priority** – higher runs first when emergencies equal
- **Emergency** – can interrupt a running command if higher and `is_ready()`
- **Target state** – tracks what the creature is doing (`seeking_food`, `eating`, `sleeping`, `wandering`)

```python
push_command(entity, world, MoveToTargetCommand(x=10, y=5, emergency=80, target_state='seeking_food'))
push_command(entity, world, EatCommand(target_x=10, target_y=5, emergency=81, target_state='eating'))
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

## Systems Reference

| System | Required Components | Priority | Description |
|--------|---------------------|----------|-------------|
| `decision_system` | `CommandQueue`, `State`, `Vision`, `Biochemistry` | 100 | AI: evaluates needs, pushes commands |
| `vision_system` | `Vision` | 80 | Populates visible entities |
| `biochemistry_system` | `CommandQueue`, `Biochemistry` | 70 | Metabolism, death detection |
| `plant_system` | `Plant` | 75 | Growth, fruit spawning |
| `command_system` | `CommandQueue` | 50 | Executes running command |

### Decision Logic (priority order)

1. **Hunger < 40** → seek food → move to adjacent cell → eat
2. **Energy < 55** → sleep (2 ticks, +15 energy/tick)
3. **Energy > 70 & Hunger > 70 & cooldown=0** → seek partner → mate
4. **Idle** → wander

## Commands Reference

| Command | Emergency | Target State | Description |
|---------|-----------|--------------|-------------|
| `MoveToTargetCommand` | variable | variable | A* pathfinding to (x,y) |
| `EatCommand` | 81 | `eating` | Consume adjacent food |
| `SleepCommand` | 20 | `sleeping` | Rest N ticks, gain energy |
| `DeathCommand` | 100 | – | Remove entity, optional corpse |
| `WanderCommand` | 79/0 | `wandering`/`seeking_*` | Random move within radius |
| `MateCommand` | 16 | `breeding` | Create offspring with partner |

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

### Add a New Event
1. Subclass `Event` (add payload fields)
2. `emit` from command/system
3. Subscribe handler via `world.event_bus.subscribe(EventType, handler)`

## Configuration (main.py)

```python
s = Simulation(tickspeed=10, fps=10, world_size=(200, 30))

# System registration order matters (higher priority runs first)
s.register_system(frozenset([CommandQueue]), command_system, priority=50)
s.register_system(frozenset([Vision]), vision_system, priority=80)
s.register_system(frozenset([CommandQueue, Biochemistry]), biochemistry_system, priority=70)
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

## Testing

```bash
python -m pytest tests/ -v
# 156 tests covering all components, commands, systems, event bus, world queries, simulation loop
```

## Current Limitations & Roadmap

- **No genetics** – all creatures identical; offspring inherit mixed colors only
- **No evolution** – no mutation, selection pressure, or heredity
- **Basic AI** – fixed priority decision tree
- **No predator/prey** – all creatures same species
- **No memory** – creatures don't learn

**Planned:**
- Genome with heredity and mutation
- Sexual selection and breeding preferences
- Associative memory (avoid poisonous food)
- Predator-prey dynamics
- Neural network or GOAP-based AI

## License

MIT License – free to use, modify, and distribute.