#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Optimized Dyadic Study Client (Computer B - IP: 100.1.1.11)
Three-stage task: Dot Display (2s) -> Response -> Feedback (1s)
"""
"""
Computer B - Eye Gaze Data Sharing Program with Memory Game
IP: 100.1.1.11
Receives gaze data from Computer A (100.1.1.10) and sends own gaze data to A
"""

import pylink
import os
import platform
import random
import time
import sys
import numpy as np
import socket
import threading
import json
from psychopy import visual, core, event, monitors, gui
from EyeLinkCoreGraphicsPsychoPy import EyeLinkCoreGraphicsPsychoPy
from PIL import Image
from string import ascii_letters, digits

from psychopy import visual, core, event, data, gui
import socket
import json
import threading
import queue
import time


# Network Configuration
LOCAL_IP = "100.1.1.11"  # Computer B's IP
REMOTE_IP = "100.1.1.10"  # Computer A's IP
GAZE_PORT = 8889
SEND_PORT = 8888

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
print("COMPUTER B - GAZE DATA SHARING WITH COMPUTER A + MEMORY GAME")
print("=" * 60)
print(f"Local IP: {LOCAL_IP}")
print(f"Remote IP: {REMOTE_IP}")

# Set up EDF data file name
edf_fname = 'COMP_B_GAZE'

# Prompt user to specify an EDF data filename
dlg_title = 'Computer B Gaze Sharing - Enter EDF File Name'
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

def setup_network():
    """Setup UDP sockets for sending and receiving gaze data"""
    global send_socket, receive_socket
    
    try:
        # Socket for sending data to Computer A
        send_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        send_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        print(f"✓ Send socket created for {REMOTE_IP}:{SEND_PORT}")
        
        # Socket for receiving data from Computer A
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
    """Send gaze data to Computer A"""
    global network_stats
    
    try:
        data = {
            'x': float(gaze_x),
            'y': float(gaze_y),
            'valid': valid,
            'timestamp': time.time(),
            'computer': 'B'
        }
        
        message = json.dumps(data).encode('utf-8')
        send_socket.sendto(message, (REMOTE_IP, SEND_PORT))
        network_stats['sent'] += 1
        
    except Exception as e:
        network_stats['errors'] += 1
        if network_stats['errors'] % 100 == 0:  # Log every 100th error
            print(f"Send error: {e}")

def receive_gaze_data():
    """Continuously receive gaze data from Computer A"""
    global remote_gaze_data, network_stats
    
    while True:
        try:
            data, addr = receive_socket.recvfrom(1024)
            gaze_info = json.loads(data.decode('utf-8'))
            
            if gaze_info.get('computer') == 'A':
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


class OptimizedDyadUDPClient:
    def __init__(self, client_ip='100.1.1.11', server_ip='100.1.1.10', port=5555):
        """Initialize the optimized UDP client for dyadic communication"""
        self.client_ip = client_ip
        self.server_ip = server_ip
        self.port = port
        self.socket = None
        self.running = False
        self.message_queue = queue.Queue()
        
    def start_client(self):
        """Start the optimized UDP client"""
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
            self.socket.bind((self.client_ip, self.port))
            print(f"Bound to {self.client_ip}:{self.port}")
        except OSError as e:
            print(f"Could not bind to {self.client_ip}:{self.port}: {e}")
            try:
                self.socket.bind(('0.0.0.0', self.port))
                print(f"Successfully bound to 0.0.0.0:{self.port}")
            except OSError as e2:
                print(f"Failed to bind: {e2}")
                raise
        
        self.socket.settimeout(0.01)
        self.running = True
        print(f"Optimized UDP Client started")
        
        # Start receiving thread
        self.receive_thread = threading.Thread(target=self._receive_messages)
        self.receive_thread.daemon = True
        self.receive_thread.start()
        
    def send_message(self, message_type, data=None):
        """Send a UDP message to the server with high precision timing"""
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
            self.socket.sendto(message_bytes, (self.server_ip, self.port))
            return True
        except Exception as e:
            print(f"Error sending message: {e}")
            return False
            
    def _receive_messages(self):
        """Receive UDP messages from server with minimal processing delay"""
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
                
                # Auto-respond to ping with pong
                if message.get('type') == 'ping':
                    self.send_message('pong', {'client_ready': True})
                    
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
            
    def wait_for_message(self, expected_type, timeout=30):
        """Wait for a specific type of message from server"""
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
        self.socket.sendto(message_bytes, (self.server_ip, self.port))
        return timestamp
        
    def close(self):
        """Close the client"""
        self.running = False
        if self.receive_thread:
            self.receive_thread.join(timeout=1)
        if self.socket:
            self.socket.close()

def run_experiment():
    """Run the three-stage task experiment on Computer B"""
    
    # Get participant info
    exp_info = {
        'participant_B_id': '',
        'session': '001',
        'client_ip': '100.1.1.11',
        'server_ip': '100.1.1.10'
    }
    
    dlg = gui.DlgFromDict(dictionary=exp_info, 
                          title='Dyadic Study - Computer B (Client)',
                          order=['participant_B_id', 'session'])
    if not dlg.OK:
        core.quit()
    
    # Initialize UDP client
    client = OptimizedDyadUDPClient(
        client_ip=exp_info['client_ip'],
        server_ip=exp_info['server_ip'],
        port=5555
    )
    
    # Create window
    win = visual.Window(
        size=[800, 600],
        fullscr=False,
        screen=0,
        winType='pyglet',
        allowGUI=True,
        color=[0, 0, 0],
        units='height',
        waitBlanking=False,
        useFBO=False
    )
    
    # Create stimuli
    instructions = visual.TextStim(win, 
        text="Starting client...", height=0.05)
    
    # Dot display stage
    dot = visual.Circle(win, radius=0.08, fillColor='white', pos=(0, 0))
    stage_text = visual.TextStim(win, text="", height=0.04, pos=(0, -0.3))
    
    # Response stage
    response_prompt = visual.TextStim(win, 
        text="Press A or F", height=0.08, pos=(0, 0))
    your_response = visual.TextStim(win, 
        text="", height=0.05, pos=(0, -0.2), color='yellow')
    other_response = visual.TextStim(win, 
        text="", height=0.05, pos=(0, -0.3), color='cyan')
    
    # Feedback stage
    feedback_text = visual.TextStim(win, 
        text="", height=0.1, pos=(0, 0))
    score_text = visual.TextStim(win, 
        text="", height=0.06, pos=(0, -0.2))
    
    # Status indicators
    status_text = visual.TextStim(win, text="", height=0.03, pos=(0, -0.4))
    latency_text = visual.TextStim(win, text="", height=0.03, pos=(0, 0.4), color='green')
    
    # Start client
    instructions.draw()
    win.flip()
    client.start_client()
    
    # Wait for server to start experiment
    instructions.text = "Waiting for Computer A to start experiment..."
    instructions.draw()
    win.flip()
    
    start_msg = client.wait_for_message('start_experiment', timeout=300)
    if not start_msg:
        instructions.text = "No start signal received!"
        instructions.draw()
        win.flip()
        core.wait(3)
        client.close()
        win.close()
        core.quit()
    
    # Send acknowledgment
    client.send_message('ack_start')
    
    # Extract experiment parameters
    n_trials = start_msg['data']['n_trials']
    
    # Main experiment loop
    data_log = []
    total_score = 0
    running = True
    
    while running:
        message = client.get_message(timeout=0.001)
        
        if not message:
            continue
            
        # ========== STAGE 1: DOT DISPLAY ==========
        if message['type'] == 'stage_dot_display':
            print(f"\n=== TRIAL {message['data']['trial_number']} ===")
            print("Stage 1: Dot Display")
            
            # Send sync acknowledgment immediately
            client.precise_sync_send('stage_sync_ack', {
                'stage': 'dot_display'
            })
            
            trial_num = message['data']['trial_number']
            sync_latency = message.get('network_latency', 0)
            
            # Display dot for 2 seconds
            stage_clock = core.Clock()
            while stage_clock.getTime() < 2.0:
                dot.draw()
                stage_text.text = f"Trial {trial_num} - Dot Display"
                stage_text.draw()
                latency_text.text = f"Sync: {sync_latency:.1f}ms"
                latency_text.draw()
                win.flip()
                
                # Check for escape
                keys = event.getKeys(['escape'])
                if 'escape' in keys:
                    running = False
                    break
        
        # ========== STAGE 2: RESPONSE COLLECTION ==========
        elif message['type'] == 'stage_response':
            print("Stage 2: Response Collection")
            
            # Send sync acknowledgment immediately
            client.precise_sync_send('stage_sync_ack', {
                'stage': 'response'
            })
            
            trial_num = message['data']['trial_number']
            
            # Initialize response tracking
            client_response = None
            server_response = None
            client_rt = None
            response_received = {'client': False, 'server': False}
            
            response_clock = core.Clock()
            
            # Collect responses until both respond
            while not (response_received['client'] and response_received['server']):
                # Display response prompt
                response_prompt.draw()
                your_response.text = f"Your response: {client_response if client_response else '...'}"
                other_response.text = f"Other response: {server_response if server_response else '...'}"
                stage_text.text = f"Trial {trial_num} - Waiting for responses"
                
                your_response.draw()
                other_response.draw()
                stage_text.draw()
                win.flip()
                
                # Check for client (this computer) response
                if not response_received['client']:
                    keys = event.getKeys(['a', 'f', 'escape'], timeStamped=response_clock)
                    if keys:
                        key, rt = keys[0]
                        if key == 'escape':
                            running = False
                            break
                        elif key in ['a', 'f']:
                            client_response = key.upper()
                            client_rt = rt
                            response_received['client'] = True
                            
                            # Send response to server
                            client.send_message('response_update', {
                                'responder': 'client',
                                'response': client_response,
                                'rt': client_rt
                            })
                
                # Check for server response messages
                resp_msg = client.get_message(timeout=0.001)
                if resp_msg and resp_msg.get('type') == 'response_update':
                    data = resp_msg['data']
                    if data['responder'] == 'server' and not response_received['server']:
                        server_response = data['response']
                        response_received['server'] = True
        
        # ========== STAGE 3: FEEDBACK ==========
        elif message['type'] == 'stage_feedback':
            print("Stage 3: Feedback")
            
            # Send sync acknowledgment immediately
            client.precise_sync_send('stage_sync_ack', {
                'stage': 'feedback'
            })
            
            trial_num = message['data']['trial_number']
            trial_score = message['data']['trial_score']
            total_score = message['data']['total_score']
            first_responder = message['data']['first_responder']
            first_response = message['data']['first_response']
            
            # Display feedback for 1 second
            feedback_clock = core.Clock()
            while feedback_clock.getTime() < 1.0:
                feedback_text.text = f"+{trial_score}"
                feedback_text.color = 'green' if trial_score > 0 else 'red'
                score_text.text = f"Total Score: {total_score}/{trial_num}"
                stage_text.text = f"First: {first_responder} ({first_response})"
                
                feedback_text.draw()
                score_text.draw()
                stage_text.draw()
                win.flip()
            
            # Log trial data (we'll collect this from the feedback stage)
            trial_log = {
                'trial': trial_num,
                'trial_score': trial_score,
                'total_score': total_score,
                'first_responder': first_responder,
                'first_response': first_response
            }
            data_log.append(trial_log)
        
        # ========== END EXPERIMENT ==========
        elif message['type'] == 'end_experiment':
            running = False
    
    # Save data
    import pandas as pd
    df = pd.DataFrame(data_log)
    filename = f'dyad_client_{exp_info["participant_B_id"]}_{time.strftime("%Y%m%d_%H%M%S")}.csv'
    df.to_csv(filename, index=False)
    
    # Final results
    if data_log:
        final_total_score = data_log[-1]['total_score']
        n_completed_trials = len(data_log)
        final_score_pct = (final_total_score / n_completed_trials) * 100
        
        instructions.text = f"Experiment Complete!\n\nFinal Score: {final_total_score}/{n_completed_trials} ({final_score_pct:.1f}%)\nData saved to {filename}"
    else:
        instructions.text = f"Experiment Complete!\nData saved to {filename}"
    
    instructions.draw()
    win.flip()
    core.wait(5)
    
    # Cleanup
    client.close()
    win.close()
    core.quit()

if __name__ == '__main__':
    run_experiment()
