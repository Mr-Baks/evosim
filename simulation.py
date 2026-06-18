from entity import * 
from world import World
import time


class Simulation:
    def __init__(self, tickspeed: int, fps: int, world_size: tuple[int, int], background_sym: str = '.'):
        self.tickspeed = tickspeed
        self.fps = fps
        self.background_sym = background_sym
        self.world = World(width=world_size[0], height=world_size[1])
        self.systems: list[tuple[int, frozenset[type[Component]], callable]] = []
        self.on_tick_callbacks: list[callable] = []

    def register_system(self, required_components: frozenset[type[Component]], system: callable, priority: int = 0) -> None:
        for i, (p, _, _) in enumerate(self.systems):
            if priority > p:
                self.systems.insert(i, (priority, required_components, system))
                self.world.index.register_system(required_components)
                return
        self.systems.append((priority, required_components, system))
        self.world.index.register_system(required_components)

    def handle_systems(self) -> None:
        self.world.index.locked = True
        for _, req_comps, system in self.systems:
            system(self.world.index.systems_cache[req_comps], self.world)
        self.world.index.locked = False
        self.world.index.flush_pending()

    def add_on_tick(self, callback: callable) -> None:
        self.on_tick_callbacks.append(callback)
        
    def render(self) -> list[list[str]]: 
        screen = [[self.background_sym for _ in range(self.world.width)] for _ in range(self.world.height)]
        renderables = self.world.index.get_with(Render)

        for e in renderables:
            render: Render = e.get_component(Render)
            if not render.is_visible: break
            r, g, b = render.color
            screen[e.y][e.x] = f'\033[38;2;{r};{g};{b}m{render.symbol}\033[0m'

        return screen

    def print_scene(self):
        out = ''
        for line in self.render():
            out += ''.join(line) + '\n'
        print(out)

    def run(self):
        last_time = time.time()
        accumulator = 0.0
        tick_duration = 1.0 / self.tickspeed
        frame_duration = 1.0 / self.fps

        self.is_running = True

        while self.is_running:
            now = time.time()
            dt = now - last_time
            last_time = now

            if dt > 0.25:
                dt = 0.25

            accumulator += dt

            while accumulator >= tick_duration:
                self.handle_systems()
                self.world.event_bus.dispatch()
                accumulator -= tick_duration

                for c in self.on_tick_callbacks:
                    c(self)

            self.print_scene()
            elapsed = time.time() - now
            sleep_time = frame_duration - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

