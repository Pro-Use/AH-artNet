from threading import Thread
from controller import ControllerConfig
from audio_playback import Player
import time

AUDIO_FOLDER = "/run/media/rob/416A-86D3/Anne"

light_ctl = ControllerConfig()
light_ctl.add_universe(universe=0, fixtures=100)

light_ctl.set_slaves([0])

def player_monitor():
    player = Player(folder=AUDIO_FOLDER)
    list_start = 0
    jump = False
    timecodes = [
    [0, light_ctl.pulse, {'universe':'master','fade_top':[50, 80], 'fade_bottom':5, 'fade_time':5500, 'hold_time':10}],
    [0, light_ctl.start_rand_spike, {'universe':0, 'fade_time':200,'fade_top':[10, 30], 'freq_min':0, 'freq_max':10, 'repeat':[1,2]}],
    [248, light_ctl.stop_rand_spike, {'universe':'0'}],
    [250, light_ctl.spike, {'universe':0, 'fade_to':255, 'fade_time':300}]
    ]

    while True:
        for i in range(list_start, len(timecodes)):
            timecode = timecodes[i]
            print("Pos: %s" % player.wait_on_pos(timecode[0]))
            timecode[1](**timecode[2])
        if jump is False:
            list_start = 0
        else:
            for i in range(len(timecodes)):
                timecode = timecodes[i]
                if timecode[0] > jump:
                    list_start = i
                    break

    for universe in light_ctl.universes:
        light_ctl.blackout(universe)
        light_ctl.quit(universe)
    player.terminate()

cmd_thread = Thread(target=player_monitor)
cmd_thread.start()

light_ctl.listen()