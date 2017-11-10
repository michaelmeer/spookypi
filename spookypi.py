#!/usr/bin/env python3
import serial
import alsaaudio
import audioop
import sys
import math
import wave
import time
import blinkt
import argparse
import os
import os.path
import random
from collections import deque

directory = "/home/pi/projects/spooky_pumpkin_pie/ressources/"
distance_trigger_limit = 300
wait_after_sound = 2

device = alsaaudio.PCM(device='default', mode=alsaaudio.PCM_NORMAL)
device.setchannels(1)                          # Mono
device.setrate(8000)                        # 8000 Hz
device.setformat(alsaaudio.PCM_FORMAT_S16_LE)  # 16 bit little endian
device.setperiodsize(500)

lo = 2000
hi = 32000

log_lo = math.log(lo)
log_hi = math.log(hi)


class ColorProvider(object):
    def __init__(self, jitteryness=0):
        self.jitteryness = jitteryness
        self.r, self.g, self.b = self.random_color()
        print("ColorProvider initialized", self.r, self.g, self.b)

    def random_color(self):
        color_choices = [[True, False, False],
                         [False, True, False],
                         [False, False, True],
                         [True, True, False],
                         [True, False, True],
                         [False, True, True],
                         [True, True, True]]

        return random.choice(color_choices)

    def color_component(self, color_enabled):
        if color_enabled:
            if self.jitteryness > 0:
                return 255 - random.randrange(self.jitteryness)
            else:
                return 255
        else:
            if self.jitteryness > 0:
                return random.randrange(self.jitteryness)
            else:
                return 0

    def give_color(self):
        r = self.color_component(self.r)
        g = self.color_component(self.g)
        b = self.color_component(self.b)
        return (r, g, b)


def play_sound(filename):
    color_provider = ColorProvider(20)

    f = wave.open(filename, 'rb')

    periodsize = int(f.getframerate() / 16)
    print("framerate: %f, periodsize: %f" % (f.getframerate(), periodsize))
    data = f.readframes(periodsize)

    period_length = 1 / 16
    counter = 1

    next_timestamp = time.time()

    while data:
        if time.time() >= next_timestamp:
            device.write(data)
            next_timestamp = time.time() + period_length
            # transform data to logarithmic scale
            vu = (math.log(float(max(audioop.max(data, 2), 1)))-log_lo)/(log_hi-log_lo)
            volume = (min(max(int(vu*100), 0), 100))
            print("%i: %f" % (counter, volume))
            r, g, b = color_provider.give_color()
            blinkt.set_all(r, g, b, brightness=volume/200.0)
            blinkt.show()
            counter += 1
            data = f.readframes(periodsize)
    f.close()
    blinkt.clear()
    blinkt.show()


def print_status_message(distance):
    max_distance = 550
    left_part = distance // 10
    right_part = max_distance // 10 - left_part
    status_message='{:03} {}{}'.format(distance, '#' * left_part, '.' * right_part)
    print(status_message)


class SoundfileProvider(object):
    def __init__(self, directory):
        print("SoundfileProvider for directory", directory)
        files = [os.path.join(directory, f) for f in os.listdir(directory) if os.path.isfile(os.path.join(directory, f))]
        self.wav_files = [f for f in files if f.lower().endswith(".wav")]
        self.wav_files.sort()
        for counter, file in enumerate(self.wav_files, 1):
            print(' - %i: %s' % (counter, file))
        self.last_played_files = deque(maxlen=3)

    def get_next_file(self):
        chosen_file = random.choice(self.wav_files)
        if chosen_file in self.last_played_files:
            result = self.get_next_file()
        else:
            self.last_played_files.append(chosen_file)
            result = chosen_file
        print('Next file %s, last couple played files %s' % (chosen_file, self.last_played_files))
        return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--soundfile", help="immediately start playing soundfile and quit afterwards")
    parser.add_argument("--no_sound", action='store_true')
    args = parser.parse_args()

    if args.soundfile:
        play_sound(args.soundfile)
        return

    soundfile_provider = SoundfileProvider(directory)

    try:
        with serial.Serial('/dev/ttyACM0', 9600, timeout=1) as ser:
            print(ser)
            while True:
                line_bytes = ser.readline()   # read a '\n' terminated line
                line_string = line_bytes.decode("utf-8")
                line_string = line_string.strip()
                distance = int(line_string)
                print_status_message(distance)
                if distance < distance_trigger_limit:
                    if not args.no_sound:
                        play_sound(soundfile_provider.get_next_file())
                        print('done with sound, now waiting for {} seconds'.format(wait_after_sound))
                        timestamp = time.time()
                        wait_until_timestamp = timestamp + wait_after_sound
                        while time.time() < wait_until_timestamp:
                            line_bytes = ser.readline()
                        print('done waiting')
                    else:
                        print('triggered, but not playing sound !!!!')
    except KeyboardInterrupt:
        blinkt.clear()
        blinkt.show()
        print("Done! Bye...")

if __name__ == "__main__":
    main()
