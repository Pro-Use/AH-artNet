from threading import Thread
from controller import ControllerConfig
import time

test = ControllerConfig()
test.add_universe(universe=0, fixtures=100)

test.set_slaves([0])

def add_commands():
    # test.blackout('master')
    # ## Fade up all
    # test.fade('master', 100, 10000)
    # test.blackout('master')
    # test.fade('master', 100, 1000)
    test.blackout('master')
    # test.fade('master', 100, 2000)
    # test.blackout('master')
    # test.fade(0, 100, 5000)
    # test.blackout(0)
    # test.fade(0, 100, 1000)
    # test.blackout(0)
    # test.fade(0, 100, 2000)
    # test.blackout(0)
    # test.fade(0, 100, 5000)
    # test.blackout(0)
    # test.fade(0, 100, 1000)
    # test.blackout(0)
    # test.fade(0, 100, 2000)
    # test.blackout(0)
    # test.fade(0, 100, 5000)
    # test.blackout(0)
    # test.fade(0, 100, 1000)
    # test.blackout(0)
    # test.fade(0, 100, 2000)
    # test.blackout(0)
    # test.fade(0, 100, 10000)
    ## Pulse all lights
    test.pulse('master', 112, 0, 5000, 100)
    ##  Pulse half lights
    # test.pulse(0, 255, 1, 600, 200, 0.5)
    ## Random Pulse
    # test.pulse(0, 255, 1, 600, 200, 0.3, True)
    ## Chase
    # test.chase(0, 255, 100, 20, 0)
    ## Chase with width
    #test.chase(0, 255, 100, 2000, 0, 3)
    ## Flicker
    # test.flicker(0, 255, 100, 200, 2)
    # test.flicker(0, 255, 0, 200, 2)
    time.sleep(15)
    test.spike(0, 255, 200)
    #test.start_rand_spike(universe=0, fade_time=200,fade_top=255, freq_min=5, freq_max=8)
    time.sleep(60)
    #test.stop_rand_spike(universe=0)

    for universe in test.universes:
        test.blackout(universe)
        test.quit(universe)


cmd_thread = Thread(target=add_commands)
cmd_thread.start()

test.listen()


# test.simple_fade()