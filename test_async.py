import asyncio, time
from threading import Thread
from pyartnet import ArtNetNode

class Ctl:
    def __init__(self, universe):
        self.node = ArtNetNode('127.0.0.1')
        self.node.start()
        self.univ = self.node.add_universe(universe)
        self.channel = self.univ.add_channel(1, 400)
        async def run_test():
            vals = [255] * 400
            self.channel.add_fade(vals, 2000)
            vals = [0] * 400
            self.channel.add_fade(vals, 2000)
