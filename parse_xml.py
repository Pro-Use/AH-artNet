
import xml.etree.ElementTree as ET
import datetime

tree = ET.parse('tate_nov24_v3.xml')
root = tree.getroot()
keyframes = root[0][0][0][4]
start = 0.0

for i in range(len(keyframes) - 1):
    keyframe = keyframes[i]
    next_keyframe = keyframes[i + 1]
    seconds = float(keyframe[0].text) / 30
    seconds_to = float(next_keyframe[0].text) / 30
    fade_time = seconds_to - seconds
    timecode = datetime.timedelta(seconds=seconds)
    h, m, s = str(timecode).split(":")
    timecode = "%s:%0.2f" % (m, float(s))
    print("['%s', light_ctl.fade, {'universe': 'master', 'fade_to': %s, 'fade_time': %s}]," %
          (timecode, next_keyframe[1].text, fade_time))
