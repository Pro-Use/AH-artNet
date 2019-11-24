import asyncio, time
from pyartnet import ArtNetNode
import random

WHITE = [255,255,255,255]
WHITE_DIFF = []
for val in WHITE:
    WHITE_DIFF.append(val / 255)

FPS = 30
INTERVAL = 1 / FPS
day_mode = False

def daytime_adjust(fades):
    if day_mode:
        for i in range(len(fades)):
            fades[i] = int(((fades[i] / 255) * 196) + 59)
    return fades


class ControllerConfig:
    def __init__(self):
        # loop = asyncio.get_event_loop()
        # loop.set_debug(True)
        self.nodes = {}
        self.universes = {}
        self.loop = asyncio.get_event_loop()
        self.add_universe('master', 1, role='master', ip=None, log=True)
        self.slaves = []


    def add_universe(self, universe, fixtures, ip, role='slave', log=False, all_vals=[[0, 0]]):
        self.universes[universe] = {}
        self.universes[universe]['cmd_queue'] = asyncio.Queue()
        self.universes[universe]['role'] = role
        self.universes[universe]['processing'] = asyncio.Event()
        self.universes[universe]['processing'].set()
        self.universes[universe]['all_vals'] = all_vals
        if role == 'slave':
            if ip in self.nodes.keys():
                node = self.nodes[ip]
            else:
                node = ArtNetNode(ip, max_fps=120)
                node.start()
            self.universes[universe]['addresses'] = fixtures * 4
            self.universes[universe]['univ'] = node.add_universe(universe)
            self.universes[universe]['channel'] = \
                self.universes[universe]['univ'].add_channel(1, self.universes[universe]['addresses'])

    def log(self, universe, msg):
        if self.universes[universe]['log']:
            print("%s: %s" % (universe, msg))


    def listen(self):

        async def fade(universe, channel, addresses, fade_to):
            if self.universes[universe]['processing'].isSet():
                self.universes[universe]['processing'].clear()
                vals = list(channel.get_channel_values())
                for i in range(1, addresses, 4):
                    for c in range(0,4):
                        vals[i + c - 1] = int(fade_to * WHITE_DIFF[c])
                vals = daytime_adjust(vals)
                channel = self.universes[universe]['channel']
                channel.add_fade(vals, 0)
                await channel.wait_till_fade_complete()
                self.universes[universe]['processing'].set()


        async def single_listen(universe):
            self.log(universe, " ->STARTING LISTENER")
            cmd_queue = self.universes[universe]['cmd_queue']
            addresses = self.universes[universe]['addresses']
            channel = self.universes[universe]['channel']
            all_vals = self.universes[universe]['all_vals']
            while True:
                new_cmd = await cmd_queue.get()
                self.log(universe, " ->cmd = %s" % new_cmd)
                # Fade
                if new_cmd[0] == 'start':
                    start_frame = new_cmd[1]
                    for val in all_vals:
                        start = time.time()

                if new_cmd[0] == 'fade':
                    fade_to = new_cmd[1]
                    await fade(universe, channel, addresses, fade_to)


        async def main():
            all_listeners = []
            for universe in self.universes:
                if universe != 'master':
                    all_listeners.append(single_listen(universe))
            await asyncio.gather(*all_listeners)

        self.loop.run_until_complete(main())

