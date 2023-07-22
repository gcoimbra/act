#!/bin/env python3
import os
import platform
import psutil
import subprocess
import time
from pynput import mouse
import threading
import time

mouse_activity_detected = False

def check_cpu_load(threshold):
    cpu_load_per_core = psutil.cpu_percent(interval=1, percpu=True)
    print('MAX CPU',max(cpu_load_per_core))
    return any(core >= threshold for core in cpu_load_per_core)

def check_disk_activity(threshold):
    disk_io = psutil.disk_io_counters()
    read_bytes = disk_io.read_bytes
    write_bytes = disk_io.write_bytes
    time.sleep(1)
    new_disk_io = psutil.disk_io_counters()
    new_read_bytes = new_disk_io.read_bytes
    new_write_bytes = new_disk_io.write_bytes

    read_speed = (new_read_bytes - read_bytes) / 1024
    write_speed = (new_write_bytes - write_bytes) / 1024
    print('DISK read_speed', read_speed, 'write speed', write_speed)
    return read_speed >= threshold or write_speed >= threshold

    
def check_gpu_activity(threshold):
    gpu_check_command = "radeontop -b 01 -t 50 -d - -l 1 | rg -o  -p --color never \"gpu ([0-9,\.]*)\"  | cut -b 7-"
    output = subprocess.check_output(gpu_check_command, shell=True)
    gpu_activity = float(output.strip())
    print('GPU', gpu_activity)
    return gpu_activity >= threshold

def check_network_activity(threshold):
    net_io = psutil.net_io_counters()
    sent_bytes = net_io.bytes_sent
    recv_bytes = net_io.bytes_recv
    time.sleep(1)
    new_net_io = psutil.net_io_counters()
    new_sent_bytes = new_net_io.bytes_sent
    new_recv_bytes = new_net_io.bytes_recv

    sent_speed = (new_sent_bytes - sent_bytes) / 1024
    recv_speed = (new_recv_bytes - recv_bytes) / 1024
    print('NETWORK sent_speed', sent_speed, 'recv_speed', recv_speed)
    return sent_speed >= threshold or recv_speed >= threshold

from statistics import median
def check_sustained_activity(check_func, threshold, duration):
    sustained_duration = 0
    activity = []
    for _ in range(duration):
        activity.append(check_func(threshold))
        time.sleep(1)

    return median(activity) > threshold


def on_move(x, y):
    global mouse_activity_detected
    mouse_activity_detected = True

def on_click(x, y, button, pressed):
    global mouse_activity_detected
    mouse_activity_detected = True

def on_scroll(x, y, dx, dy):
    global mouse_activity_detected
    mouse_activity_detected = True

def mouse_listener(stop_event):
    with mouse.Listener(on_move=on_move, on_click=on_click, on_scroll=on_scroll) as listener:
        while not stop_event.is_set():
            listener.join(0.1)

def check_mouse_activity(timeout):
    global mouse_activity_detected
    mouse_activity_detected = False
    stop_event = threading.Event()
    listener_thread = threading.Thread(target=mouse_listener, args=(stop_event,))
    listener_thread.start()
    time.sleep(timeout)

    stop_event.set()
    listener_thread.join(1)
    return mouse_activity_detected


def is_xfce_presentation_mode():
    try:
        command = "xfconf-query -c xfce4-power-manager -p /xfce4-power-manager/presentation-mode"
        output = subprocess.check_output(command, shell=True, text=True)
        presentation_mode = output.strip().lower() == "true"
        return presentation_mode
    except subprocess.CalledProcessError:
        print("Error: Failed to query Xfce presentation mode")
        return False

import os
def main():
    cpu_median_usage_threshold = 50
    gpu_median_usage_threshold = 50
    disk_median_usage_threshold = 1000  # in KB/s
    network_threshold = 1000  # in KB/s
    sustained_duration = 10  # in seconds

    timeout_mouse_activity = 60
    loop_delay = 120
    while True:
        sustained_cpu = check_sustained_activity(check_cpu_load, cpu_median_usage_threshold, sustained_duration)
        sustained_gpu = check_sustained_activity(check_gpu_activity, gpu_median_usage_threshold, sustained_duration)

        sustained_max_disk = check_sustained_activity(check_disk_activity, disk_median_usage_threshold, sustained_duration)
        sustained_max_network = check_sustained_activity(check_network_activity, network_threshold, sustained_duration)
        mouse_activity = check_mouse_activity(timeout_mouse_activity)
        presentation_mode = is_xfce_presentation_mode()
        
        if not (sustained_cpu or sustained_max_disk or sustained_max_network or sustained_gpu or mouse_activity or presentation_mode):
            print('Suspending system to RAM...')
            os.system('sudo /usr/local/sbin/suspend_unvramfs')
            time.sleep(5)  # Adjust this delay based on your requirements
        else:
            reasons = []
            if sustained_cpu:
                reasons.append("at least one CPU core is at maximum")
            if sustained_gpu:
                reasons.append("GPU activity is at maximum")
            if sustained_max_disk:
                reasons.append("sustained disk activity")
            if sustained_max_network:
                reasons.append("sustained network activity")
            if mouse_activity:
                reasons.append("mouse_activity")
            if presentation_mode:
                reasons.append("presentation mode")

            msg = "Computer didn't suspend because: " + ', '.join(reasons)
            print(msg)
            os.system(f"logger \"{msg}\"")
            time.sleep(loop_delay)  # Adjust this delay based on your requirements

if __name__ == '__main__':
    main()
