import asyncio, time
from pyartnet import ArtNetNode
import random

WHITE = [255,255,255,255]
WHITE_DIFF = []
for val in WHITE:
    WHITE_DIFF.append(val / 255)

FADE_MOD = 0.87
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

    def add_universe(self, universe, fixtures, ip, role='slave', log=False):
        self.universes[universe] = {}
        self.universes[universe]['cmd_queue'] = asyncio.Queue()
        self.universes[universe]['role'] = role
        self.universes[universe]['spike'] = asyncio.Event()
        self.universes[universe]['spike'].set()
        self.universes[universe]['rand_spike'] = False
        self.universes[universe]['log'] = log
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

        async def wait_on_fade(vals, fade_time, universe, slaves=None):
            start = time.time()
            if slaves is not None:
                val = max(vals)
                for slave in slaves:
                    slave_queue = self.universes[slave]['cmd_queue']
                    await slave_queue.put(['fade', val, fade_time])
                await asyncio.sleep((start + (fade_time / 1000)) - time.time())
            elif self.universes[universe]['spike'].is_set():
                vals = daytime_adjust(vals)
                channel = self.universes[universe]['channel']
                channel.add_fade(vals, fade_time * FADE_MOD)
                await channel.wait_till_fade_complete()
                if self.universes[universe]['spike'].is_set():
                    fade_took = time.time() - start
                    difference = (fade_time / 1000) / fade_took
                    if fade_time != 0:
                        self.log(universe, "->fade time = %s, took = %s, difference = %s " %
                                 (fade_time/1000, fade_took, difference))
                else:
                    while True:
                        remaining = (fade_time/1000) - (time.time() - start)
                        self.log(universe, "fade finished %s seconds early" % remaining)
                        stop = time.time() + remaining
                        await self.universes[universe]['spike'].wait()
                        remaining = stop - time.time()
                        if remaining > 0.1:
                            self.log(universe, "Restarting fade with %s seconds remaining" % remaining)
                            channel.add_fade(vals, (remaining * 1000) * FADE_MOD)
                            await channel.wait_till_fade_complete()
                            # if not self.universes[universe]['spike'].is_set():
                            #     self.log(universe, "Fade Complete - difference %s" % ((fade_time/1000) - (time.time() - start)))
                            #     break
                        else:
                            self.log(universe, "Fade Complete - difference %s" % ((fade_time/1000) - (time.time() - start)))
                            break
                        # await asyncio.sleep(remaining)
            else:
                vals = daytime_adjust(vals)
                channel = self.universes[universe]['channel']
                remaining = (fade_time / 1000) - (time.time() - start)
                self.log(universe, "fade finished %s seconds early" % remaining)
                stop = time.time() + remaining
                await self.universes[universe]['spike'].wait()
                remaining = stop - time.time()
                if remaining > 0.1:
                    self.log(universe, "Restarting fade with %s seconds remaining" % remaining)
                    channel.add_fade(vals, (remaining * 1000) * FADE_MOD)
                    await channel.wait_till_fade_complete()

        async def fade(universe, channel, addresses, fade_to, fade_time):
            vals = list(channel.get_channel_values())
            for i in range(1, addresses, 4):
                for c in range(0,4):
                    vals[i + c - 1] = int(fade_to * WHITE_DIFF[c])
            await wait_on_fade(vals, fade_time, universe)

        async def pulse(universe, channel, addresses, cmd_queue, role,
                        num_fixtures, rand,fade_top, fade_bottom, fade_time, hold_time):
            num_fixtures = float(num_fixtures)
            selected_fixtures = []
            if num_fixtures != 1.0:
                for i in range(0, addresses, 4):
                    selected_fixtures.append(i)
                selected_fixtures = random.sample(selected_fixtures, int(len(selected_fixtures) * num_fixtures))
                self.log(universe, "channels selected = %s" % selected_fixtures)
            up = True
            while cmd_queue.empty():
                if up is True:
                    if type(fade_top) == list:
                        target = random.randrange(fade_top[0], fade_top[1])
                        self.log(universe, "target = %s" % target)
                    else:
                        target = fade_top
                    if rand is True and num_fixtures != 1.0:
                        selected_fixtures = []
                        for i in range(3, addresses, 4):
                            selected_fixtures.append(i)
                        selected_fixtures = random.sample(selected_fixtures,
                                                          int(len(selected_fixtures) * num_fixtures))
                else:
                    if type(fade_bottom) == list:
                        target = random.randrange(fade_bottom[0], fade_bottom[1])
                    else:
                        target = fade_bottom
                if type(fade_time) == list:
                    new_fade_time = random.uniform(fade_time[0], fade_time[1]) * 1000
                else:
                    new_fade_time = fade_time
                if role == 'slave':
                    vals = list(channel.get_channel_values())
                    for i in range(1, addresses, 4):
                        if num_fixtures == 1.0 or i in selected_fixtures:
                            for c in range(0, 4):
                                vals[i + c - 1] = int(target * WHITE_DIFF[c])
                    await wait_on_fade(vals, new_fade_time, universe)
                else:
                    vals = [target]
                    await wait_on_fade(vals, new_fade_time, universe, slaves=self.slaves)
                if cmd_queue.empty():
                    await asyncio.sleep(hold_time / 1000)
                    up = not up

        async def static_pulse(universe, channel, addresses, cmd_queue, role, static):
            static_vals_all = [
                [
                    [0.055, 234], [0.055, 210], [0.055, 234], [0.055, 204], [0.02, 224],
                    [0.055, 197], [0.055, 221], [0.055, 193], [0.055, 210], [0.055, 199]
                ],
                [
                    [0.055, 224], [0.055, 160], [0.055, 221], [0.055, 193], [0.02, 210],
                    [0.055, 151], [0.055, 234], [0.055, 210], [0.055, 234], [0.055, 197]
                ],
                [
                    [0.055, 210], [0.055, 118], [0.055, 234], [0.055, 168], [0.02, 234],
                    [0.055, 146], [0.055, 224], [0.055, 174], [0.055, 220], [0.055, 109],
                    [0.055, 193], [0.055, 86], [0.055, 190], [0.055, 135], [0.055, 220], [0.055, 105]
                ],
                [
                    [0.055, 234], [0.2, 145], [0.2, 221], [0.2, 149], [0.3, 233],
                    [0.2, 115], [0.3, 224], [0.2, 152], [0.055, 221], [0.055, 156],
                    [0.2, 234], [0.3, 103], [0.1255, 193],
                ],
                [
                    [0.055, 223], [0.2, 167], [0.3, 248], [0.55, 138], [0.2, 234],
                    [0.5, 110], [0.3, 245], [0.3, 129], [0.3, 226], [0.2, 145],
                    [0.3, 245], [0.055, 137], [0.3, 229], [0.5, 166],
                ],
            ]
            static_vals = static_vals_all[static]
            for i in range(len(static_vals)):
                static_vals[i][0] *= 1000
            while cmd_queue.empty():
                for next_val in static_vals:
                    if role == 'slave':
                        vals = list(channel.get_channel_values())
                        for i in range(1, addresses, 4):
                            for c in range(0, 4):
                                vals[i + c - 1] = int(next_val[1] * WHITE_DIFF[c])
                        if not cmd_queue.empty():
                            break
                        else:
                            await wait_on_fade(vals, next_val[0], universe)
                    else:
                        if not cmd_queue.empty():
                            break
                        else:
                            vals = [next_val[1]]
                            await wait_on_fade(vals, next_val[0], universe, slaves=self.slaves)

        async def chase(universe, channel, addresses, cmd_queue,
                        fade_to, fade_bottom, fade_time, hold_time, width):
            increment = int((fade_to - fade_bottom) / width)
            steps = []
            for i in range(width):
                next_step = fade_to - (increment * i)
                if next_step > 255:
                    next_step = 255
                steps.append(next_step)
            pos = 3
            while cmd_queue.empty():
                vals = list(channel.get_channel_values())
                for i in range(width):
                    if pos + (4 * i) <= addresses:
                        vals[pos + (4 * i)] = steps[i]
                await wait_on_fade(vals, fade_time, universe)
                if cmd_queue.empty():
                    time.sleep(hold_time / 1000)
                    vals[pos] = fade_bottom
                if cmd_queue.empty():
                    await wait_on_fade(vals, fade_time, universe)
                    pos += 4
                    if pos > addresses:
                        pos = 3

        async def flicker(universe, channel, addresses, cmd_queue,
                          fade_top, fade_bottom, fade_time, steps):
            if steps > addresses / 4:
                steps = addresses / 4
            increment = int((fade_top - fade_bottom) / steps)
            vals = list(channel.get_channel_values())
            while cmd_queue.empty():
                for i in range(steps):
                    selected_fixtures = []
                    for f in range(1, addresses, 4):
                        selected_fixtures.append(f)
                    selected_fixtures = random.sample(selected_fixtures, int(len(selected_fixtures) / steps))
                    for f in selected_fixtures:
                        for c in range(0, 4):
                            vals[f + c - 1] = int((increment * i) * WHITE_DIFF[c])
                await wait_on_fade(vals, fade_time, universe)

        async def single_listen(universe):
            self.log(universe, " ->STARTING LISTENER")
            cmd_queue = self.universes[universe]['cmd_queue']
            addresses = self.universes[universe]['addresses']
            channel = self.universes[universe]['channel']
            role = self.universes[universe]['role']
            while True:
                new_cmd = await cmd_queue.get()
                self.log(universe, " ->cmd = %s" % new_cmd)
                # Quit
                if new_cmd[0] == 'quit':
                    break
                # Blackout
                if new_cmd[0] == 'blackout':
                    vals = [0] * addresses
                    await wait_on_fade(vals, 0, universe)
                # Hold
                if new_cmd[0] == 'hold':
                    self.universes[universe]['channel'].cancel_fades()
                # Fade
                elif new_cmd[0] == 'fade':
                    fade_to = new_cmd[1]
                    fade_time = new_cmd[2]
                    await fade(universe, channel, addresses, fade_to, fade_time)
                # Pulse
                elif new_cmd[0] == 'pulse':
                    fade_top = new_cmd[1]
                    fade_bottom = new_cmd[2]
                    fade_time = new_cmd[3]
                    hold_time = new_cmd[4]
                    num_fixtures = new_cmd[5]
                    rand = new_cmd[6]
                    await pulse(universe, channel, addresses, cmd_queue, role,
                        num_fixtures, rand,fade_top, fade_bottom, fade_time, hold_time)
                ## Chase
                elif new_cmd[0] == 'chase':
                    fade_to = new_cmd[1]
                    fade_bottom = new_cmd[2]
                    channel.add_fade([fade_bottom] * addresses, 0)
                    await channel.wait_till_fade_complete()
                    fade_time = new_cmd[3]
                    hold_time = new_cmd[4]
                    width = new_cmd[5]
                    await chase(universe, channel, addresses, cmd_queue,
                        fade_to, fade_bottom, fade_time, hold_time, width)

                ## Flicker
                elif new_cmd[0] == 'flicker':
                    fade_top = new_cmd[1]
                    fade_bottom = new_cmd[2]
                    channel.add_fade([fade_bottom] * addresses, 0)
                    await channel.wait_till_fade_complete()
                    fade_time = new_cmd[3]
                    steps = new_cmd[4]
                    await flicker(universe, channel, addresses, cmd_queue,
                            fade_top, fade_bottom, fade_time, steps)

        async def master_listen():
            universe = 'master'
            self.log(universe, " ->STARTING MASTER")
            cmd_queue = self.universes[universe]['cmd_queue']
            role = self.universes[universe]['role']
            while True:
                new_cmd = await cmd_queue.get()
                self.log(universe, " ->cmd = %s" % new_cmd)
                # Quit
                if new_cmd[0] == 'quit':
                    break
                # Blackout
                if new_cmd[0] == 'blackout':
                    for slave in self.slaves:
                        slave_queue = self.universes[slave]['cmd_queue']
                        await slave_queue.put(['blackout'])
                # Hold
                if new_cmd[0] == 'hold':
                    for slave in self.slaves:
                        slave_queue = self.universes[slave]['cmd_queue']
                        await slave_queue.put(['hold'])
                # Fade
                elif new_cmd[0] == 'fade':
                    fade_to = new_cmd[1]
                    fade_time = new_cmd[2]
                    await wait_on_fade([fade_to], fade_time, universe, self.slaves)
                # static
                elif new_cmd[0] == 'static':
                    static = new_cmd[1]
                    await static_pulse(universe, None, None, cmd_queue, role, static)
                # Pulse
                elif new_cmd[0] == 'pulse':
                    fade_top = new_cmd[1]
                    fade_bottom = new_cmd[2]
                    fade_time = new_cmd[3]
                    hold_time = new_cmd[4]
                    num_fixtures = 1.0
                    rand = False
                    await pulse(universe, None, None, cmd_queue, role,
                        num_fixtures, rand, fade_top, fade_bottom, fade_time, hold_time)

        async def main():
            all_listeners = [master_listen()]
            # all_listeners = []
            for universe in self.universes:
                if universe != 'master':
                    all_listeners.append(single_listen(universe))
            await asyncio.gather(*all_listeners)

        self.loop.run_until_complete(main())

    def spike(self, universe, fade_to, fade_time, repeat=1):
        if type(fade_time) != list:
            fade_time *= 1000

        async def spike(u):
            self.log(u, "starting spike")
            self.universes[u]['spike'].clear()
            for n in range(repeat):
                self.universes[u]['channel'].cancel_fades()
                channel = self.universes[u]['channel']
                addresses = self.universes[u]['addresses']
                if type(fade_to) == list:
                    new_fade_to = random.randint(fade_to[0], fade_to[1])
                else:
                    new_fade_to = fade_to
                vals = list(channel.get_channel_values())
                base = max(vals)
                for i in range(1, addresses, 4):
                    for c in range(0, 4):
                        vals[i + c - 1] = int(new_fade_to * WHITE_DIFF[c])
                start = time.time()
                channel.add_fade(vals, (fade_time / 2) * FADE_MOD)
                await channel.wait_till_fade_complete()
                for i in range(0, len(vals)):
                    vals[i] = base
                channel.add_fade(vals, (fade_time / 2) * FADE_MOD)
                await channel.wait_till_fade_complete()
                fade_took = time.time() - start
                self.log(u, "ending spike - took = %s, difference = %s" % (fade_took, (fade_time / 1000) - fade_took))
            self.universes[u]['spike'].set()

        if universe != 'master':
            self.loop.create_task(spike(universe))
        else:
            self.log(universe, "starting spike")
            for slave in self.slaves:
                self.loop.create_task(spike(slave))

    def start_rand_spike(self, universe, fade_top, fade_time, freq_min, freq_max, repeat=1):
        fade_time *= 1000

        async def rand_spike():
            channel = self.universes[universe]['channel']
            new_fade_top = fade_top
            new_repeat = repeat
            while self.universes[universe]['rand_spike']:
                new_wait = random.uniform(freq_min, freq_max)
                await asyncio.sleep(new_wait)
                if self.universes[universe]['rand_spike']:
                    addresses = self.universes[universe]['addresses']
                    old_vals = list(channel.get_channel_values())
                    if type(repeat) == list:
                        new_repeat = random.randint(repeat[0], repeat[1])
                    for i in range(new_repeat):
                        if type(fade_top) == list:
                            new_fade_top = random.randrange(fade_top[0], fade_top[1])
                        vals = [0] * len(old_vals)
                        for i in range(1, addresses, 4):
                            for c in range(0, 4):
                                cur_top = old_vals[i + c - 1]
                                vals[i + c - 1] = cur_top + int(new_fade_top * WHITE_DIFF[c])
                        channel.cancel_fades()
                        self.log(universe, "starting spike")
                        start = time.time()
                        self.universes[universe]['spike'].clear()
                        channel.add_fade(vals, (fade_time / 2) * FADE_MOD)
                        await channel.wait_till_fade_complete()
                        channel.add_fade(vals, (fade_time / 2) * FADE_MOD)
                        await channel.wait_till_fade_complete()
                        self.log(universe, "ending spike, took %s seconds" % (time.time() - start))
                        if i < new_repeat - 1:
                            await asyncio.sleep(0.25)
                    self.universes[universe]['spike'].set()

        if universe != 'master':
            self.universes[universe]['rand_spike'] = True
            self.loop.create_task(rand_spike())
        else:
            self.log(universe, "Master cannot have random spike")

    def stop_rand_spike(self, universe):
        self.universes[universe]['rand_spike'] = False

    def set_slaves(self, slaves):
        if type(slaves) is not list:
            slaves = [slaves]
        self.slaves = slaves

    def blackout(self, universe):
        async def cmd(u):
            await self.universes[u]['cmd_queue'].put(['blackout'])

        self.loop.create_task(cmd(universe))

    def quit(self, universe):
        async def cmd(u):
            await self.universes[u]['cmd_queue'].put(['quit'])

        self.loop.create_task(cmd(universe))

    def hold(self, universe):
        async def cmd(u):
            while not self.universes[u]['cmd_queue'].empty():
                self.universes[u]['cmd_queue'].get_nowait()
                print("Emptying queue")
            await self.universes[u]['cmd_queue'].put(['hold'])

        self.loop.create_task(cmd(universe))

    def fade(self, universe, fade_to, fade_time, sync=False):
        fade_time *= 1000

        async def cmd(u):
            await self.universes[u]['cmd_queue'].put(['fade', fade_to, fade_time, sync])
            self.log(universe, "adding fade to universe %s" % universe)

        self.loop.create_task(cmd(universe))

    def static(self, universe, static):
        async def cmd(u):
            await self.universes[u]['cmd_queue'].put(['static', static])
            self.log(universe, "adding static %s to universe %s" % (universe, static))

        self.loop.create_task(cmd(universe))

    def pulse(self, universe, fade_top, fade_bottom, fade_time, hold_time, fixtures=1.0, rand=False):
        if type(fade_time) != list:
            fade_time *= 1000
        if type(hold_time) != list:
            hold_time *= 1000

        async def cmd(u):
            await self.universes[u]['cmd_queue'].put(
                ['pulse', fade_top, fade_bottom, fade_time, hold_time, fixtures, rand])

        self.loop.create_task(cmd(universe))

    def chase(self, universe, fade_top, fade_bottom, fade_time, hold_time, width=1):
        if type(fade_time) != list:
            fade_time *= 1000
        if type(hold_time) != list:
            hold_time *= 1000

        async def cmd(u):
            await self.universes[u]['cmd_queue'].put(['chase', fade_top, fade_bottom, fade_time, hold_time, width])

        self.loop.create_task(cmd(universe))

    def flicker(self, universe, fade_top, fade_bottom, fade_time, steps):
        if type(fade_time) != list:
            fade_time *= 1000

        async def cmd(u):
            await self.universes[u]['cmd_queue'].put(['flicker', fade_top, fade_bottom, fade_time, steps])

        self.loop.create_task(cmd(universe))