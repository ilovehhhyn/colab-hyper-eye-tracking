#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Optimized Dyadic Study Server (Computer A - IP: 100.1.1.10)
Three-stage task: Dot Display (2s) -> Response -> Feedback (1s)
"""
"""
Computer A - Eye Gaze Data Sharing Program with Memory Game
IP: 100.1.1.10
Receives gaze data from Computer B (100.1.1.11) and sends own gaze data to B
"""
import pylink
import os
import platform
import random
import sys
import numpy as np
from EyeLinkCoreGraphicsPsychoPy import EyeLinkCoreGraphicsPsychoPy
from PIL import Image
from string import ascii_letters, digits
from psychopy import visual, core, event, data, monitors, gui
import socket
import json
import threading
import queue
import time
import struct


# Network Configuration
LOCAL_IP = "100.1.1.10"  # Computer A's IP
REMOTE_IP = "100.1.1.11"  # Computer B's IP
GAZE_PORT = 8888
SEND_PORT = 8889


# Global variables
el_tracker = None
win = None
remote_gaze_data = {'x': 0, 'y': 0, 'valid': False, 'timestamp': 0}
network_stats = {'sent': 0, 'received': 0, 'errors': 0}

# Game variables
game_state = 'waiting'  # 'waiting', 'study', 'recall', 'feedback'
current_trial = 0
total_trials = 5
grid_images = []
grid_positions = []
trial_results = []

# Game variables
current_round = 0
total_rounds = 10
grid_layout = []  # Will store the 8x8 grid layout

game_sync_data = {'round': 0, 'target_pos': 0, 'grid_seed': 0, 'responses': {}}
player_scores = {'A': 0, 'B': 0}

local_gaze_stats = {
    'total_attempts': 0,
    'samples_received': 0,
    'valid_gaze_data': 0,
    'missing_data': 0,
    'last_valid_gaze': (0, 0)
}

# Game sockets
game_send_socket = None
game_receive_socket = None

# Image and condition variables
images = {
    'face': [],
    'limb': [],
    'house': [],
    'car': []
}
conditions = {}

# Category mapping (consistent with Computer A)
CATEGORY_MAP = {
    0: 'face',
    1: 'limb', 
    2: 'house',
    3: 'car'
}

# Switch to the script folder
script_path = os.path.dirname(sys.argv[0])
if len(script_path) != 0:
    os.chdir(script_path)

# Show only critical log message in the PsychoPy console
from psychopy import logging
logging.console.setLevel(logging.CRITICAL)

# Configuration variables
use_retina = False
dummy_mode = False
full_screen = True


print("=" * 60)
print("COMPUTER A - GAZE DATA SHARING WITH COMPUTER B + MEMORY GAME")
print("=" * 60)
print(f"Local IP: {LOCAL_IP}")
print(f"Remote IP: {REMOTE_IP}")

# Set up EDF data file name
edf_fname = 'COMP_A_GAZE'

# Prompt user to specify an EDF data filename
dlg_title = 'Computer A Gaze Sharing - Enter EDF File Name'
dlg_prompt = 'Please enter a file name with 8 or fewer characters\n[letters, numbers, and underscore].'

while True:
    dlg = gui.Dlg(dlg_title)
    dlg.addText(dlg_prompt)
    dlg.addField('File Name:', edf_fname)
    ok_data = dlg.show()
    if dlg.OK:
        print('EDF data filename: {}'.format(ok_data[0]))
    else:
        print('user cancelled')
        core.quit()
        sys.exit()

    tmp_str = dlg.data[0]
    edf_fname = tmp_str.rstrip().split('.')[0]

    allowed_char = ascii_letters + digits + '_'
    if not all([c in allowed_char for c in edf_fname]):
        print('ERROR: Invalid EDF filename')
    elif len(edf_fname) > 8:
        print('ERROR: EDF filename should not exceed 8 characters')
    else:
        break

# Set up folders
results_folder = 'results'
if not os.path.exists(results_folder):
    os.makedirs(results_folder)

time_str = time.strftime("_%Y_%m_%d_%H_%M", time.localtime())
session_identifier = edf_fname + time_str
session_folder = os.path.join(results_folder, session_identifier)
if not os.path.exists(session_folder):
    os.makedirs(session_folder)
  
# Network Setup
def setup_network():
    """Setup UDP sockets for sending and receiving gaze data"""
    global send_socket, receive_socket
    
    try:
        # Socket for sending data to Computer B
        send_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        send_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        print(f"✓ Send socket created for {REMOTE_IP}:{SEND_PORT}")
        
        # Socket for receiving data from Computer B
        receive_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        receive_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        receive_socket.bind((LOCAL_IP, GAZE_PORT))
        receive_socket.settimeout(0.001)  # Non-blocking with short timeout
        print(f"✓ Receive socket bound to {LOCAL_IP}:{GAZE_PORT}")
        
        return True
    except Exception as e:
        print(f"✗ Network setup failed: {e}")
        return False

def send_gaze_data(gaze_x, gaze_y, valid=True):
    """Send gaze data to Computer B"""
    global network_stats
    
    try:
        data = {
            'x': float(gaze_x),
            'y': float(gaze_y),
            'valid': valid,
            'timestamp': time.time(),
            'computer': 'A'
        }
        
        message = json.dumps(data).encode('utf-8')
        send_socket.sendto(message, (REMOTE_IP, SEND_PORT))
        network_stats['sent'] += 1
        
    except Exception as e:
        network_stats['errors'] += 1
        if network_stats['errors'] % 100 == 0:  # Log every 100th error
            print(f"Send error: {e}")

def receive_gaze_data():
    """Continuously receive gaze data from Computer B"""
    global remote_gaze_data, network_stats
    
    while True:
        try:
            data, addr = receive_socket.recvfrom(1024)
            gaze_info = json.loads(data.decode('utf-8'))
            
            if gaze_info.get('computer') == 'B':
                remote_gaze_data.update(gaze_info)
                network_stats['received'] += 1
                
        except socket.timeout:
            continue
        except Exception as e:
            network_stats['errors'] += 1
            if network_stats['errors'] % 100 == 0:
                print(f"Receive error: {e}")
            time.sleep(0.001)

# Start network setup
if not setup_network():
    print("Failed to setup network. Exiting...")
    sys.exit()

# Start receiving thread
receive_thread = threading.Thread(target=receive_gaze_data, daemon=True)
receive_thread.start()
print("✓ Network communication started")

# Connect to EyeLink
print("\n1. CONNECTING TO EYELINK")
print("-" * 30)
if dummy_mode:
    el_tracker = pylink.EyeLink(None)
    print("Running in DUMMY mode")
else:
    try:
        el_tracker = pylink.EyeLink("100.1.1.1")
        print("✓ Connected to EyeLink Host at 100.1.1.1")
        
        if el_tracker.isConnected():
            try:
                version = el_tracker.getTrackerVersionString()
                print(f"✓ Tracker version: {version}")
            except:
                print("⚠️  Could not get version string")
    except RuntimeError as error:
        print('ERROR:', error)
        print('Switching to dummy mode...')
        dummy_mode = True
        el_tracker = pylink.EyeLink(None)


# Open EDF file
edf_file = edf_fname + ".EDF"
try:
    el_tracker.openDataFile(edf_file)
    print(f"✓ Data file opened: {edf_file}")
except RuntimeError as err:
    print('ERROR:', err)
    if el_tracker.isConnected():
        el_tracker.close()
    core.quit()
    sys.exit()

# Configure tracker
print("\n2. CONFIGURING TRACKER")
print("-" * 25)
el_tracker.setOfflineMode()
pylink.msecDelay(100)

commands = [
    "clear_screen 0",
    "sample_rate 1000",
    "link_sample_data = LEFT,RIGHT,GAZE,HREF,RAW,AREA,HTARGET,GAZERES,BUTTON,STATUS,INPUT",
    "link_event_filter = LEFT,RIGHT,FIXATION,SACCADE,BLINK,MESSAGE,BUTTON,INPUT",
    "file_sample_data = LEFT,RIGHT,GAZE,HREF,RAW,AREA,HTARGET,GAZERES,BUTTON,STATUS,INPUT", 
    "file_event_filter = LEFT,RIGHT,FIXATION,SACCADE,BLINK,MESSAGE,BUTTON,INPUT",
    "recording_parse_type = GAZE",
    "saccade_velocity_threshold = 30",
    "saccade_acceleration_threshold = 9500",
    "calibration_type = HV9"
]

for cmd in commands:
    el_tracker.sendCommand(cmd)
    pylink.msecDelay(10)

print("✓ Tracker configured for shared gaze recording")

# Set up display
print("\n3. SETTING UP DISPLAY")
print("-" * 25)
mon = monitors.Monitor('myMonitor', width=53.0, distance=70.0)
win = visual.Window(fullscr=full_screen, monitor=mon, winType='pyglet', units='pix', color=[0, 0, 0])

scn_width, scn_height = win.size
print(f"✓ Window: {scn_width} x {scn_height}")

if 'Darwin' in platform.system() and use_retina:
    scn_width = int(scn_width/2.0)
    scn_height = int(scn_height/2.0)

# Configure EyeLink graphics
el_coords = "screen_pixel_coords = 0 0 %d %d" % (scn_width - 1, scn_height - 1)
el_tracker.sendCommand(el_coords)
print(f"✓ Screen coordinates: {el_coords}")

genv = EyeLinkCoreGraphicsPsychoPy(el_tracker, win)
foreground_color = (-1, -1, -1)
background_color = win.color
genv.setCalibrationColors(foreground_color, background_color)

if os.path.exists('images/fixTarget.bmp'):
    genv.setTargetType('picture')
    genv.setPictureTarget(os.path.join('images', 'fixTarget.bmp'))

genv.setCalibrationSounds('', '', '')

if use_retina:
    genv.fixMacRetinaDisplay()

pylink.openGraphicsEx(genv)
print("✓ Graphics environment ready")

# Create visual elements
print("\n4. CREATING VISUAL ELEMENTS")
print("-" * 30)

# Local gaze marker (Computer B's own gaze) - Green theme
local_gaze_marker = visual.Circle(win=win, radius=20, fillColor='limegreen', lineColor='darkgreen', lineWidth=2)
local_gaze_sparkle1 = visual.Circle(win=win, radius=15, fillColor='lightgreen', lineColor='white', lineWidth=1)

# Remote gaze marker (Computer A's gaze) - Blue theme
remote_gaze_marker = visual.Circle(win=win, radius=20, fillColor='deepskyblue', lineColor='navy', lineWidth=2)
remote_gaze_sparkle1 = visual.Circle(win=win, radius=15, fillColor='lightblue', lineColor='white', lineWidth=1)

# Status display (smaller to make room for game)
status_background = visual.Rect(win=win, width=scn_width*0.9, height=60, 
                               fillColor='darkgreen', lineColor='lightgreen', lineWidth=2,
                               pos=[0, scn_height//2 - 40])
status_text = visual.TextStim(win, text='', pos=[0, scn_height//2 - 40], color='lightgreen', 
                             height=12, bold=True)



def update_local_gaze_display():
    """Update local gaze marker based on own eye tracking data"""
    global local_gaze_stats
    
    local_gaze_stats['total_attempts'] += 1
    
    sample = None
    try:
        sample = el_tracker.getNewestSample()
    except Exception as e:
        pass
    
    if sample is not None:
        local_gaze_stats['samples_received'] += 1
        
        gaze_data = None
        
        # Try right eye first, then left eye
        if sample.isRightSample():
            try:
                gaze_data = sample.getRightEye().getGaze()
            except:
                pass
        elif sample.isLeftSample():
            try:
                gaze_data = sample.getLeftEye().getGaze()
            except:
                pass
        
        if gaze_data and gaze_data[0] != pylink.MISSING_DATA and gaze_data[1] != pylink.MISSING_DATA:
            local_gaze_stats['valid_gaze_data'] += 1
            local_gaze_stats['last_valid_gaze'] = gaze_data
            
            try:
                # Convert from EyeLink coordinates to PsychoPy coordinates
                gaze_x = - ( gaze_data[0] - scn_width/2 + 50)
                gaze_y = - (scn_height/2 - gaze_data[1] + 200)
                
                if abs(gaze_x) <= scn_width/2 and abs(gaze_y) <= scn_height/2:
                    # Update local marker positions
                    local_gaze_marker.setPos([gaze_x, gaze_y])
                    
                    # Animate sparkles
                    sparkle_time = core.getTime()
                    sparkle_offset1 = 15 * np.sin(sparkle_time * 3)
                    sparkle_offset2 = 10 * np.cos(sparkle_time * 4)
                    
                    local_gaze_sparkle1.setPos([gaze_x + sparkle_offset1, gaze_y + sparkle_offset2])
                    
                    # Send gaze data to Computer A
                    send_gaze_data(gaze_data[0], gaze_data[1], True)
                    
            except Exception as e:
                pass
        else:
            local_gaze_stats['missing_data'] += 1
            # Send invalid data to Computer A
            send_gaze_data(0, 0, False)

def update_remote_gaze_display():
    """Update remote gaze marker based on received data from Computer A"""
    global remote_gaze_data
    
    if remote_gaze_data.get('valid', False):
        # Check if data is recent (within last 100ms)
        if True: # time.time() - remote_gaze_data.get('timestamp', 0) < 0.1:
            try:
                # Convert from EyeLink coordinates to PsychoPy coordinates
                

                gaze_x = ( 1.2* remote_gaze_data['x'] - scn_width/2 + 400 - 60) 
                gaze_y = (scn_height/2- 1.2 *remote_gaze_data['y']  + 200 -25 )

                
                if True: #abs(gaze_x) <= scn_width/2 and abs(gaze_y) <= scn_height/2:
                    # Update remote marker positions
                    remote_gaze_marker.setPos([gaze_x, gaze_y])
                    
                    # Animate sparkles differently from local
                    sparkle_time = core.getTime()
                    sparkle_offset1 = 12 * np.cos(sparkle_time * 3.5)
                    sparkle_offset2 = 8 * np.sin(sparkle_time * 4.5)
                    
                    remote_gaze_sparkle1.setPos([gaze_x + sparkle_offset1, gaze_y + sparkle_offset2])
                    
            except Exception as e:
                pass


# Call this function after creating the existing visual elements and before starting the main loop

def draw_ui_elements():
    """Draw status bar, legend, and corners"""
    # Draw corners
    for corner in corners:
        corner.draw()
    
    # Draw status
    status_background.draw()
    remote_age = time.time() - remote_gaze_data.get('timestamp', 0)
    remote_status = "CONNECTED" if remote_age < 0.1 else f"DELAYED"
    
    status_text.setText(
        f"COMPUTER A - MEMORY GAME | Trial {current_trial}/{total_trials} | "
        f"Sent: {network_stats['sent']} Recv: {network_stats['received']}"
    )
    status_text.draw()
    
    # Draw legend
    legend_bg.draw()
    legend_text.draw()

# Add these missing UI elements after the existing visual elements creation
def create_missing_ui_elements():
    """Create missing UI elements that are referenced but not defined"""
    global game_instructions, question_mark, feedback_text, legend_bg, legend_text, corners
    
    # Game instructions text
    game_instructions = visual.TextStim(win, text='', pos=[0, -scn_height//2 + 100],
                                       color='white', height=18, bold=True, wrapWidth=scn_width*0.9)
    
    # Question mark for recall phase
    question_mark = visual.TextStim(win, text='?', pos=[0, 0], color='red', 
                                   height=48, bold=True)
    
    # Feedback text
    feedback_text = visual.TextStim(win, text='', pos=[0, -scn_height//2 + 50],
                                   color='white', height=24, bold=True)
    
    # Legend background and text
    legend_bg = visual.Rect(win=win, width=300, height=120, 
                           fillColor='darkblue', lineColor='lightblue', lineWidth=2,
                           pos=[scn_width//2 - 170, -scn_height//2 + 80])
    
    legend_text = visual.TextStim(win, text='GREEN: Your gaze\nBLUE: Partner gaze\nF=Face L=Limb\nH=House C=Car',
                                 pos=[scn_width//2 - 170, -scn_height//2 + 80],
                                 color='lightblue', height=12, bold=True)
    
    # Corner decorations
    corner_size = 30
    corners = []
    corner_positions = [
        [-scn_width//2 + corner_size//2, scn_height//2 - corner_size//2],  # Top-left
        [scn_width//2 - corner_size//2, scn_height//2 - corner_size//2],   # Top-right
        [-scn_width//2 + corner_size//2, -scn_height//2 + corner_size//2], # Bottom-left
        [scn_width//2 - corner_size//2, -scn_height//2 + corner_size//2]   # Bottom-right
    ]
    
    for pos in corner_positions:
        corner = visual.Rect(win=win, width=corner_size, height=corner_size,
                           fillColor='gold', lineColor='orange', lineWidth=2,
                           pos=pos)
        corners.append(corner)
      

def clear_screen(win):
    win.clearBuffer()
    win.flip()

def show_msg(win, text, wait_for_keypress=True):
    msg_background = visual.Rect(win, width=scn_width*0.7, height=scn_height*0.6, 
                                fillColor='lightcyan', lineColor='darkgreen', lineWidth=5)
    msg = visual.TextStim(win, text, color='darkgreen', wrapWidth=scn_width*0.6, 
                         height=22, bold=True)
    
    clear_screen(win)
    
    if wait_for_keypress:
        start_time = core.getTime()
        while True:
            current_time = core.getTime()
            pulse = 0.95 + 0.05 * np.sin((current_time - start_time) * 3)
            msg_background.setSize([scn_width*0.7*pulse, scn_height*0.6*pulse])
            
            win.clearBuffer()

            msg_background.draw()
            msg.draw()
            win.flip()
            core.wait(0.016)
            
            keys = event.getKeys()
            if keys:
                break
    else:
        msg_background.draw()
        msg.draw()
        win.flip()
    
    clear_screen(win)

# Show instructions
task_msg = 'Computer B - Gaze Data Sharing + Memory Game\n\n'
task_msg += 'This program will:\n'
task_msg += '• Track your eye gaze (green markers)\n'
task_msg += '• Send your gaze data to Computer A\n'
task_msg += '• Receive and display Computer A\'s gaze (blue markers)\n'
task_msg += '• Run a memory game with 5 trials\n\n'
task_msg += 'Memory Game Instructions:\n'
task_msg += '• Study a 6x6 grid of images for 10 seconds\n'
task_msg += '• Recall what was at a marked position\n'
task_msg += '• Press F=Face, L=Limbs, H=House, C=Car\n\n'
task_msg += 'Network Configuration:\n'
task_msg += f'• Local IP: {LOCAL_IP}\n'
task_msg += f'• Remote IP: {REMOTE_IP}\n'
task_msg += f'• Ports: {GAZE_PORT}/{SEND_PORT}\n\n'
task_msg += 'Controls:\n'
task_msg += '• SPACE = Recalibrate eye tracker\n'
task_msg += '• ESCAPE = Exit program\n\n'
if dummy_mode:
    task_msg += 'DUMMY MODE: Simulated eye tracking\n'
task_msg += 'Press ENTER to begin calibration'

show_msg(win, task_msg)

# Calibration
print("\n5. CALIBRATION")
print("-" * 15)
if not dummy_mode:
    try:
        print("Starting calibration...")
        el_tracker.doTrackerSetup()
        print("✓ Calibration completed")
        
        el_tracker.exitCalibration()
        el_tracker.setOfflineMode()
        pylink.msecDelay(500)
        
        win.winHandle.activate()
        win.flip()
        event.clearEvents()
        
    except RuntimeError as err:
        print('Calibration ERROR:', err)
        el_tracker.exitCalibration()
        win.winHandle.activate()
        win.flip()

show_msg(win, "Calibration complete!\n\nStarting gaze sharing and memory game session.\n\nPress any key to begin.")

print('we got here')
class OptimizedDyadUDPServer:
    def __init__(self, server_ip='100.1.1.10', client_ip='100.1.1.11', port=5555):
        """Initialize the optimized UDP server for dyadic communication"""
        self.server_ip = server_ip
        self.client_ip = client_ip
        self.port = port
        self.socket = None
        self.running = False
        self.message_queue = queue.Queue()
        
    def start_server(self):
        """Start the optimized UDP server"""
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        
        # UDP optimizations for low latency
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 65536)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 65536)
        
        # Platform-specific optimizations
        try:
            self.socket.setsockopt(socket.IPPROTO_UDP, socket.UDP_CORK, 0)
        except (AttributeError, OSError):
            pass
        
        try:
            self.socket.setsockopt(socket.IPPROTO_IP, socket.IP_DONTFRAG, 1)
        except (AttributeError, OSError):
            pass
        
        # Bind to address
        try:
            self.socket.bind((self.server_ip, self.port))
            print(f"Bound to {self.server_ip}:{self.port}")
        except OSError as e:
            print(f"Could not bind to {self.server_ip}:{self.port}: {e}")
            try:
                self.socket.bind(('0.0.0.0', self.port))
                print(f"Successfully bound to 0.0.0.0:{self.port}")
            except OSError as e2:
                print(f"Failed to bind: {e2}")
                raise
        
        self.socket.settimeout(0.01)
        self.running = True
        print(f"Optimized UDP Server started")
        
        # Start receiving thread
        self.receive_thread = threading.Thread(target=self._receive_messages)
        self.receive_thread.daemon = True
        self.receive_thread.start()
        
        # Send initial ping
        self.send_message('ping', {'server_ready': True})
        
    def send_message(self, message_type, data=None):
        """Send a UDP message to the client with high precision timing"""
        if not self.socket:
            return False
            
        timestamp = time.perf_counter()
        message = {
            'type': message_type,
            'timestamp': timestamp,
            'data': data
        }
        
        try:
            message_json = json.dumps(message, separators=(',', ':'))
            message_bytes = message_json.encode('utf-8')
            self.socket.sendto(message_bytes, (self.client_ip, self.port))
            return True
        except Exception as e:
            print(f"Error sending message: {e}")
            return False
            
    def _receive_messages(self):
        """Receive UDP messages from client with minimal processing delay"""
        while self.running:
            try:
                data, addr = self.socket.recvfrom(1024)
                receipt_time = time.perf_counter()
                
                message = json.loads(data.decode('utf-8'))
                message['sender_addr'] = addr
                message['receipt_time'] = receipt_time
                
                if 'timestamp' in message:
                    network_latency = (receipt_time - message['timestamp']) * 1000
                    message['network_latency'] = network_latency
                
                self.message_queue.put(message)
                
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    print(f"Error receiving message: {e}")
                    
    def get_message(self, timeout=0):
        """Get a message from the queue"""
        try:
            return self.message_queue.get(timeout=timeout)
        except queue.Empty:
            return None
            
    def wait_for_response(self, expected_type, timeout=5):
        """Wait for a specific type of response from client"""
        start_time = time.perf_counter()
        while time.perf_counter() - start_time < timeout:
            message = self.get_message(timeout=0.001)
            if message and message.get('type') == expected_type:
                return message
        return None
        
    def precise_sync_send(self, message_type, data=None):
        """Send message with precise timing for synchronization"""
        timestamp = time.perf_counter()
        message = {
            'type': message_type,
            'timestamp': timestamp,
            'data': data
        }
        message_bytes = json.dumps(message, separators=(',', ':')).encode('utf-8')
        self.socket.sendto(message_bytes, (self.client_ip, self.port))
        return timestamp
        
    def close(self):
        """Close the server"""
        self.running = False
        if self.receive_thread:
            self.receive_thread.join(timeout=1)
        if self.socket:
            self.socket.close()

def run_integrated_experiment():
    """Run three-stage task integrated with gaze sharing"""
    global current_trial, total_trials, game_state
    
    # Fix the typo first
    print('we got here')
    
    # Get experiment parameters
    exp_info = {
        'participant_A_id': '',
        'session': '001',
        'n_trials': 10
    }
    
    dlg = gui.DlgFromDict(dictionary=exp_info, 
                          title='Integrated Gaze Sharing + Three-Stage Task',
                          order=['participant_A_id', 'session', 'n_trials'])
    if not dlg.OK:
        terminate_task()
        return
    
    # Create missing UI elements for gaze sharing
    create_missing_ui_elements()
    
    # Initialize three-stage task UDP server (separate from gaze sharing)
    task_server = OptimizedDyadUDPServer(
        server_ip=LOCAL_IP,
        client_ip=REMOTE_IP,
        port=5555  # Different from gaze sharing ports
    )
    
    # Start recording
    el_tracker.startRecording(1, 1, 1, 1)
    
    # Create three-stage task visual elements
    dot = visual.Circle(win, radius=40, fillColor='white', pos=(0, 0))
    stage_text = visual.TextStim(win, text="", height=24, pos=(0, -200), color='white', bold=True)
    response_prompt = visual.TextStim(win, text="Press A or F", height=32, pos=(0, 0), color='yellow', bold=True)
    your_response = visual.TextStim(win, text="", height=20, pos=(0, -100), color='yellow')
    other_response = visual.TextStim(win, text="", height=20, pos=(0, -130), color='cyan')
    feedback_text = visual.TextStim(win, text="", height=48, pos=(0, 0), bold=True)
    score_text = visual.TextStim(win, text="", height=24, pos=(0, -160), color='white')
    
    # Start task server and wait for client
    show_msg(win, "Starting three-stage task server...\nWaiting for Computer B to connect...", False)
    task_server.start_server()
    
    # Wait for client connection with gaze sharing active
    client_ready = False
    timeout_clock = core.Clock()
    
    while not client_ready and timeout_clock.getTime() < 60:
        # Update gaze sharing while waiting
        update_local_gaze_display()
        update_remote_gaze_display()
        
        # Draw gaze markers
        win.clearBuffer()
        local_gaze_marker.draw()
        local_gaze_sparkle1.draw()
        remote_gaze_marker.draw() 
        remote_gaze_sparkle1.draw()
        draw_ui_elements()
        
        # Add connection status
        status_text.setText(f"Waiting for Computer B... {timeout_clock.getTime():.0f}s")
        status_text.draw()
        win.flip()
        
        # Check for client connection
        if time.perf_counter() % 0.1 < 0.01:
            task_server.precise_sync_send('ping', {'server_ready': True})
        
        message = task_server.get_message(timeout=0.001)
        if message and message.get('type') == 'pong':
            client_ready = True
            
        # Allow escape
        keys = event.getKeys(['escape'])
        if 'escape' in keys:
            terminate_task()
            return
    
    if not client_ready:
        show_msg(win, "Connection timeout! Computer B did not respond.", True)
        terminate_task()
        return
    
    show_msg(win, "Connected to Computer B!\n\nStarting three-stage task with gaze sharing.\n\nPress any key to begin trials.")
    
    # Send start signal
    task_server.precise_sync_send('start_experiment', {'n_trials': exp_info['n_trials']})
    ack = task_server.wait_for_response('ack_start', timeout=3)
    
    # Main experiment loop
    n_trials = exp_info['n_trials']
    total_trials = n_trials
    data_log = []
    total_score = 0
    
    for trial_num in range(n_trials):
        current_trial = trial_num + 1
        print(f"\n=== TRIAL {current_trial} ===")
        
        # ========== STAGE 1: DOT DISPLAY ==========
        game_state = 'dot_display'
        task_server.precise_sync_send('stage_dot_display', {
            'trial_number': current_trial,
            'stage': 'dot_display'
        })
        
        sync_ack = task_server.wait_for_response('stage_sync_ack', timeout=1)
        
        # Display dot for 2 seconds WITH gaze sharing
        stage_clock = core.Clock()
        while stage_clock.getTime() < 2.0:
            # Update gaze sharing
            update_local_gaze_display()
            update_remote_gaze_display()
            
            # Draw everything
            win.clearBuffer()
            
            # Draw gaze markers (always visible)
            local_gaze_marker.draw()
            local_gaze_sparkle1.draw()
            remote_gaze_marker.draw()
            remote_gaze_sparkle1.draw()
            
            # Draw three-stage task elements
            dot.draw()
            stage_text.setText(f"Trial {current_trial} - Dot Display ({2.0 - stage_clock.getTime():.1f}s)")
            stage_text.draw()
            
            # Draw UI
            draw_ui_elements()
            win.flip()
            
            keys = event.getKeys(['escape'])
            if 'escape' in keys:
                task_server.send_message('end_experiment')
                terminate_task()
                return
        
        # ========== STAGE 2: RESPONSE COLLECTION ==========
        game_state = 'response'
        task_server.precise_sync_send('stage_response', {
            'trial_number': current_trial,
            'stage': 'response'
        })
        
        sync_ack = task_server.wait_for_response('stage_sync_ack', timeout=1)
        
        # Response collection WITH gaze sharing
        server_response = None
        client_response = None
        server_rt = None
        first_responder = None
        first_response = None
        
        response_clock = core.Clock()
        response_received = {'server': False, 'client': False}
        
        while not (response_received['server'] and response_received['client']):
            # Update gaze sharing
            update_local_gaze_display()
            update_remote_gaze_display()
            
            # Draw everything
            win.clearBuffer()
            
            # Draw gaze markers
            local_gaze_marker.draw()
            local_gaze_sparkle1.draw()
            remote_gaze_marker.draw()
            remote_gaze_sparkle1.draw()
            
            # Draw response stage elements
            response_prompt.draw()
            your_response.setText(f"Your response: {server_response or '...'}")
            other_response.setText(f"Other response: {client_response or '...'}")
            stage_text.setText(f"Trial {current_trial} - Waiting for responses")
            
            your_response.draw()
            other_response.draw()
            stage_text.draw()
            
            # Draw UI
            draw_ui_elements()
            win.flip()
            
            # Check for server response
            if not response_received['server']:
                keys = event.getKeys(['a', 'f', 'escape'], timeStamped=response_clock)
                if keys:
                    key, rt = keys[0]
                    if key == 'escape':
                        task_server.send_message('end_experiment')
                        terminate_task()
                        return
                    elif key in ['a', 'f']:
                        server_response = key.upper()
                        server_rt = rt
                        response_received['server'] = True
                        
                        if first_responder is None:
                            first_responder = 'server'
                            first_response = server_response
                        
                        task_server.send_message('response_update', {
                            'responder': 'server',
                            'response': server_response,
                            'rt': server_rt
                        })
            
            # Check for client response
            message = task_server.get_message(timeout=0.001)
            if message and message.get('type') == 'response_update':
                data = message['data']
                if data['responder'] == 'client' and not response_received['client']:
                    client_response = data['response']
                    response_received['client'] = True
                    
                    if first_responder is None:
                        first_responder = 'client'
                        first_response = client_response
        
        # ========== STAGE 3: FEEDBACK ==========
        game_state = 'feedback'
        trial_score = 1 if first_response == 'A' else 0
        total_score += trial_score
        
        task_server.precise_sync_send('stage_feedback', {
            'trial_number': current_trial,
            'trial_score': trial_score,
            'total_score': total_score,
            'first_responder': first_responder,
            'first_response': first_response
        })
        
        sync_ack = task_server.wait_for_response('stage_sync_ack', timeout=1)
        
        # Display feedback for 1 second WITH gaze sharing
        feedback_clock = core.Clock()
        while feedback_clock.getTime() < 1.0:
            # Update gaze sharing
            update_local_gaze_display()
            update_remote_gaze_display()
            
            # Draw everything
            win.clearBuffer()
            
            # Draw gaze markers
            local_gaze_marker.draw()
            local_gaze_sparkle1.draw()
            remote_gaze_marker.draw()
            remote_gaze_sparkle1.draw()
            
            # Draw feedback
            feedback_text.setText(f"+{trial_score}")
            feedback_text.setColor('green' if trial_score > 0 else 'red')
            score_text.setText(f"Total Score: {total_score}/{current_trial}")
            stage_text.setText(f"First: {first_responder} ({first_response})")
            
            feedback_text.draw()
            score_text.draw()
            stage_text.draw()
            
            # Draw UI
            draw_ui_elements()
            win.flip()
        
        # Log data
        trial_log = {
            'trial': current_trial,
            'server_response': server_response,
            'server_rt': server_rt,
            'client_response': client_response,
            'first_responder': first_responder,
            'first_response': first_response,
            'trial_score': trial_score,
            'total_score': total_score
        }
        data_log.append(trial_log)
        
        # Brief inter-trial with gaze sharing
        inter_trial_clock = core.Clock()
        while inter_trial_clock.getTime() < 0.5:
            update_local_gaze_display()
            update_remote_gaze_display()
            
            win.clearBuffer()
            local_gaze_marker.draw()
            local_gaze_sparkle1.draw()
            remote_gaze_marker.draw()
            remote_gaze_sparkle1.draw()
            draw_ui_elements()
            win.flip()
    
    # End experiment
    task_server.send_message('end_experiment')
    game_state = 'complete'
    
    # Save data
    import pandas as pd
    df = pd.DataFrame(data_log)
    filename = f'integrated_server_{exp_info["participant_A_id"]}_{time.strftime("%Y%m%d_%H%M%S")}.csv'
    df.to_csv(filename, index=False)
    
    final_score_pct = (total_score / n_trials) * 100
    show_msg(win, f"Experiment Complete!\n\nFinal Score: {total_score}/{n_trials} ({final_score_pct:.1f}%)\nData saved to {filename}")
    
    task_server.close()
    terminate_task()

# Replace the original call
if __name__ == '__main__':
    run_integrated_experiment()
