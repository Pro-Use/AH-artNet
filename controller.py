import asyncio, time
from pyartnet import ArtNetNode
import random
from statistics import mean, StatisticsError

WHITE = [255,255,200,255]
WHITE_DIFF = []
for val in WHITE:
    WHITE_DIFF.append(val / 255)

class ControllerConfig:
    def __init__(self):
        # loop = asyncio.get_event_loop()
        # loop.set_debug(True)
        # self.node = ArtNetNode('raspberrypi.local')
        self.node = ArtNetNode('127.0.0.1')
        self.node.start()
        self.universes = {}
        self.loop = asyncio.get_event_loop()
        self.add_universe('master', 1, role='master')
        self.slaves = []

    def add_universe(self, universe, fixtures, role='slave'):
        self.universes[universe] = {}
        self.universes[universe]['cmd_queue'] = asyncio.Queue()
        self.universes[universe]['role'] = role
        self.universes[universe]['spike'] = asyncio.Event()
        self.universes[universe]['spike'].set()
        self.universes[universe]['rand_spike'] = False
        if role == 'slave':
            self.universes[universe]['addresses'] = fixtures * 4
            self.universes[universe]['univ'] = self.node.add_universe(universe)
            self.universes[universe]['channel'] = \
                self.universes[universe]['univ'].add_channel(1,self.universes[universe]['addresses'])
            self.universes[universe]['correction'] = 1
            self.universes[universe]['correction_adj'] = []

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
                channel = self.universes[universe]['channel']
                try:
                    avg = mean(self.universes[universe]['correction_adj'])
                except StatisticsError:
                    avg = 1
                channel.add_fade(vals, fade_time * (self.universes[universe]['correction'] * avg))
                await channel.wait_till_fade_complete()
                if self.universes[universe]['spike'].is_set():
                    fade_took = time.time() - start
                    difference = (fade_time/ 1000) / fade_took
                    if fade_time != 0:
                        print("U:%s ->fade time = %s, took = %s, difference = %s " %
                              (universe, fade_time/1000, fade_took, (fade_time/1000 - fade_took)))
                        if self.universes[universe]['correction'] == 1:
                            self.universes[universe]['correction'] = difference
                        else:
                            self.universes[universe]['correction_adj'].append(difference)
                            if len(self.universes[universe]['correction_adj']) > 20:
                                self.universes[universe]['correction_adj'] = \
                                    self.universes[universe]['correction_adj'][0:20]
                else:
                    remaining = (fade_time/1000) - (time.time() - start)
                    print("fade finished %s seconds early" % remaining)
                    stop = time.time() + remaining
                    await self.universes[universe]['spike'].wait()
                    remaining = stop - time.time()
                    if remaining > 0.1:
                        print("Restarting fade with %s seconds remaining" % remaining)
                        channel.add_fade(vals, (remaining * 1000) * (self.universes[universe]['correction'] * avg))
                        await channel.wait_till_fade_complete()
                    # await asyncio.sleep(remaining)
            else:
                channel = self.universes[universe]['channel']
                try:
                    avg = mean(self.universes[universe]['correction_adj'])
                except StatisticsError:
                    avg = 1
                remaining = (fade_time / 1000) - (time.time() - start)
                print("fade finished %s seconds early" % remaining)
                stop = time.time() + remaining
                await self.universes[universe]['spike'].wait()
                remaining = stop - time.time()
                if remaining > 0.1:
                    print("Restarting fade with %s seconds remaining" % remaining)
                    channel.add_fade(vals, (remaining * 1000) * (self.universes[universe]['correction'] * avg))
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
                print("channels selected = %s" % selected_fixtures)
            up = True
            while cmd_queue.empty():
                if up is True:
                    if type(fade_top) == list:
                        target = random.randrange(fade_top[0], fade_top[1])
                        print("target = %s" % target)
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
                    new_fade_time = random.uniform(fade_time[0], fade_time[1])
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
            print("U:%s ->STARTING LISTENER" % universe)
            cmd_queue =  self.universes[universe]['cmd_queue']
            addresses =  self.universes[universe]['addresses']
            channel = self.universes[universe]['channel']
            role = self.universes[universe]['role']
            while True:
                new_cmd = await cmd_queue.get()
                print("U:%s ->cmd = %s" % (universe, new_cmd))
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
                    # vals = list(channel.get_channel_values())
                    # channel.add_fade(vals, 0)
                    # await channel.wait_till_fade_complete()
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
            print("U:master ->STARTING MASTER")
            universe = 'master'
            cmd_queue = self.universes[universe]['cmd_queue']
            role = self.universes[universe]['role']
            while True:
                new_cmd = await cmd_queue.get()
                print("U:master ->cmd = %s" % new_cmd)
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
                # Pulse
                elif new_cmd[0] == 'pulse':
                    fade_top = new_cmd[1]
                    fade_bottom = new_cmd[2]
                    fade_time = new_cmd[3]
                    hold_time = new_cmd[4]
                    num_fixtures = 1.0
                    rand = False
                    await pulse(universe, None, None, cmd_queue, role,
                        num_fixtures, rand,fade_top, fade_bottom, fade_time, hold_time)

        async def main():
            all_listeners = [master_listen()]
            # all_listeners = []
            for universe in self.universes:
                if universe != 'master':
                    all_listeners.append(single_listen(universe))
            await asyncio.gather(*all_listeners)


        self.loop.run_until_complete(main())


    def spike(self, universe, fade_to, fade_time):
        async def spike():
            print("starting spike")
            self.universes[universe]['spike'].clear()
            self.universes[universe]['channel'].cancel_fades()
            channel = self.universes[universe]['channel']
            addresses = self.universes[universe]['addresses']
            try:
                avg = mean(self.universes[universe]['correction_adj'])
            except StatisticsError:
                avg = 1
            vals = list(channel.get_channel_values())
            base = max(vals)
            for i in range(1, addresses, 4):
                for c in range(0,4):
                    vals[i + c - 1] = int(fade_to * WHITE_DIFF[c])
            channel.add_fade(vals, (fade_time / 2) * (self.universes[universe]['correction'] * avg))
            await channel.wait_till_fade_complete()
            for i in range(0, len(vals)):
                vals[i] = base
            channel.add_fade(vals, (fade_time / 2) * (self.universes[universe]['correction'] * avg))
            await channel.wait_till_fade_complete()
            self.universes[universe]['spike'].set()
            print("ending spike")

        if universe != 'master':
            self.loop.create_task(spike())
        else:
            print("Master cannot have spike")

    def start_rand_spike(self, universe, fade_top, fade_time, freq_min, freq_max, repeat=1):
        async def rand_spike():
            channel = self.universes[universe]['channel']
            new_fade_top = fade_top
            new_repeat = repeat
            while self.universes[universe]['rand_spike']:
                new_wait  = random.uniform(freq_min, freq_max)
                await asyncio.sleep(new_wait)
                if self.universes[universe]['rand_spike']:
                    addresses = self.universes[universe]['addresses']
                    try:
                        avg = mean(self.universes[universe]['correction_adj'])
                    except StatisticsError:
                        avg = 1
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
                        print("starting spike")
                        start = time.time()
                        self.universes[universe]['spike'].clear()
                        channel.add_fade(vals, (fade_time / 2) * (self.universes[universe]['correction'] * avg))
                        await channel.wait_till_fade_complete()
                        channel.add_fade(old_vals, (fade_time / 2) * (self.universes[universe]['correction'] * avg))
                        await channel.wait_till_fade_complete()
                        print("ending spike, took %s seconds" % (time.time() - start))
                        if i < new_repeat - 1:
                            await asyncio.sleep(0.25)
                    self.universes[universe]['spike'].set()

        if universe != 'master':
            self.universes[universe]['rand_spike'] = True
            self.loop.create_task(rand_spike())
        else:
            print("Master cannot have random spike")

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

    def fade(self, universe, fade_to, fade_time, sync=False):
        async def cmd(u):
            await self.universes[u]['cmd_queue'].put(['fade', fade_to, fade_time, sync])
            print("adding fade to universe %s" % universe)

        self.loop.create_task(cmd(universe))

    def pulse(self, universe, fade_top, fade_bottom, fade_time, hold_time, fixtures=1.0, rand=False):
        async def cmd(u):
            await self.universes[u]['cmd_queue'].put(
                ['pulse', fade_top, fade_bottom, fade_time, hold_time, fixtures, rand])

        self.loop.create_task(cmd(universe))

    def chase(self, universe, fade_top, fade_bottom, fade_time, hold_time, width=1):
        async def cmd(u):
            await self.universes[u]['cmd_queue'].put(['chase', fade_top, fade_bottom, fade_time, hold_time, width])

        self.loop.create_task(cmd(universe))

    def flicker(self, universe, fade_top, fade_bottom, fade_time, steps):
        async def cmd(u):
            await self.universes[u]['cmd_queue'].put(['flicker', fade_top, fade_bottom, fade_time, steps])

        self.loop.create_task(cmd(universe))