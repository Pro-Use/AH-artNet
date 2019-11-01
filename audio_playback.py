import mpv
import glob
import os
from threading import Event


def my_log(loglevel, component, message):
    print('[{}] {}: {}'.format(loglevel, component, message))

class Player:
    def __init__(self, folder, log=True):
        if log is True:
            mpv_args = {'log_handler':my_log,}
        else:
            mpv_args = {}
        video_files = glob.glob(os.path.join(folder, '*.wav'))
        self.player = mpv.MPV(loop_file='inf', **mpv_args)
        self.player.play(video_files[0])
        self.duration = self.player.duration
        self.player.wait_for_property('time-pos', lambda val: val is not None)
        self.seek_event = Event()

    def wait_on_pos(self, timecode):
        self.player.wait_for_property('time-pos', lambda val: val > timecode)
        return self.player.time_pos


    def terminate(self):
        self.player.terminate()