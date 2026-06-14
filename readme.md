# EvoSim

A **turn-based, grid-based evolution simulation** where creatures with basic biochemistry roam, eat, sleep and die. Built with a custom ECS‑like architecture, a command‑queue system, and an event bus for loose coupling.

## Features

- **Entity‑Component‑System (ECS) backbone** – data and logic cleanly separated.
- **Command queue** – creatures perform sequential actions with priority and emergency interrupts.
- **Event bus** – side effects trigger independent systems (e.g., biochemistry updates).
- **Vision system** – each creature perceives nearby entities within a radius.
- **Modular & extensible** – add new components, commands, or event handlers without touching core logic.

## Architecture Overview

```
Entity
  ├── Movable
  ├── Biochemistry (energy, hunger, health)
  ├── Vision
  ├── CommandQueue
  └── … (Eatable, Movable, etc.)

System types:
  - decision_system      – evaluates needs, pushes commands into queue
  - command_system       – executes the current command of each creature
  - vision_system        – populates Vision.visibles set
  - biochemistry_system  – updates hunger/energy/health, triggers death
  - (user-defined systems)

Communication: Events → EventBus → handlers.
```

## Getting Started

### Prerequisites

- Python 3.10 or higher
- Computer
- Internet

### Installation

```bash
git clone https://github.com/mr-baks/evosim.git
cd evosim
```

### Running the simulation

```bash
python main.py
```

The console will display a grid:
- `C` – creature
- `f` – food
- `.` – empty cell

### Controls

The simulation runs automatically. Close the terminal window to stop.

## Customization & Extension

### Adding a new action

1. Subclass `Command` and implement `execute()`.
2. Optionally override `is_ready()` and `on_interruption()`.
3. In `decision_system`, push the new command when conditions are met.

### Adding a new component

1. Create a `@dataclass` inheriting from `Component`.
2. Add it to entities via `entity.add_component(...)`.
3. Create a system that processes entities with that component.
4. Rigister this system via `register_system` function.

### Adding a new event

1. Subclass `Event` (add any payload fields).
2. `emit` the event from somewhere (command, system).
3. Subscribe a handler using `world.event_bus.subscribe(EventClass, handler)`.

## Current Limitations & Roadmap

- **No genetics yet** – all creatures are identical.
- **No reproduction** – population only changes via death.
- **Basic movement AI** – wander + move-to-target + sleep/eat priorities.

**Planned features:**
- Genome with heredity and mutation
- Sexual selection and breeding
- Associative memory (avoid poisonous food)
- Predator-prey dynamics

## License

MIT License – free to use, modify, and distribute.