#!/usr/bin/env python3
"""
Computer A - Eye Gaze Data Sharing Program with Competitive Memory Game
IP: 100.1.1.10
Receives gaze data from Computer B (100.1.1.11) and sends own gaze data to B
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

# Network Configuration
LOCAL_IP = "100.1.1.10"  # Computer A's IP
REMOTE_IP = "100.1.1.11"  # Computer B's IP
GAZE_PORT = 8888
SEND_PORT = 8889
GAME_PORT = 8890  # New port for game synchronization

# Global variables
el_tracker = None
win = None
remote_gaze_data = {'x': 0, 'y': 0, 'valid': False, 'timestamp': 0}
network_stats = {'sent': 0, 'received': 0, 'errors': 0}

# Game variables
game_state = 'waiting'
current_round = 0
total_rounds = 10
grid_layout = []  # Will store the 8x8 grid layout
grid_positions = []
trial_results = []
game_sync_data = {'round': 0, 'target_pos': 0, 'grid_seed': 0, 'responses': {}}
player_scores = {'A': 0, 'B': 0}

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

# Category mapping (consistent with second code)
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
print("COMPUTER A - COMPETITIVE MEMORY GAME WITH GAZE SHARING")
print("=" * 60)
print(f"Local IP: {LOCAL_IP}")
print(f"Remote IP: {REMOTE_IP}")

# Set up EDF data file name
edf_fname = 'COMP_A_COMPET'

# Prompt user to specify an EDF data filename
dlg_title = 'Computer A Competitive Game - Enter EDF File Name'
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

# Load conditions from JSON file
def load_conditions():
    """Load conditions from dyad_conditions.json"""
    global conditions
    try:
        with open('dyad_conditions.json', 'r') as f:
            data = json.load(f)
            conditions = {
                'medium': data['top_layouts_array_fixed_16'],  # 16-element arrays (4x4 patterns)
                'hard': data['top_layouts_array_fixed_64']     # 64-element arrays (8x8 patterns)
            }
        print("✓ Conditions loaded from dyad_conditions.json")
    except FileNotFoundError:
        print("dyad_conditions.json not found. Using default conditions.")
        # Default conditions if file not found
        conditions = {
            'medium': [[2, 0, 1, 3, 2, 3, 0, 1, 3, 1, 2, 1, 0, 2, 0, 3]],  # 16-element default
            'hard': [[1, 3, 2, 3, 0, 2, 1, 0] * 8]  # 64-element default (repeated pattern)
        }
    except Exception as e:
        print(f"Error loading conditions: {e}")
        conditions = {
            'medium': [[2, 0, 1, 3, 2, 3, 0, 1, 3, 1, 2, 1, 0, 2, 0, 3]],
            'hard': [[1, 3, 2, 3, 0, 2, 1, 0] * 8]
        }

def load_all_images():
    """Load all images from stimuli folder"""
    global images
    
    stimuli_path = 'stimuli'
    
    # Try to load images from each category
    for category in ['faces', 'limbs', 'houses', 'cars']:
        category_key = category[:-1]  # Remove 's' to get singular
        if category == 'cars':
            category_key = 'car'
        
        folder_path = os.path.join(stimuli_path, category)
        
        if os.path.exists(folder_path):
            for i in range(1, 11):  # Load 10 images per category
                image_name = f"{category_key}-{i}.jpg"
                image_path = os.path.join(folder_path, image_name)
                
                if os.path.exists(image_path):
                    try:
                        # Don't create ImageStim here, just store the path
                        images[category_key].append(image_path)
                    except Exception as e:
                        print(f"Error loading {image_path}: {e}")
        
        # If no images loaded for this category, create placeholder paths
        if not images[category_key]:
            print(f"No images found for {category_key}. Will use colored rectangles.")
            # Add placeholder entries
            for i in range(10):
                images[category_key].append(f"placeholder_{category_key}_{i}")
    
    print("✓ Image paths loaded")

# Load conditions and images at startup
load_conditions()
load_all_images()

# Network Setup
def setup_network():
    """Setup UDP sockets for sending and receiving gaze data and game sync"""
    global send_socket, receive_socket, game_send_socket, game_receive_socket
    
    try:
        # Gaze data sockets
        send_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        send_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        print(f"✓ Gaze send socket created for {REMOTE_IP}:{SEND_PORT}")
        
        receive_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        receive_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        receive_socket.bind((LOCAL_IP, GAZE_PORT))
        receive_socket.settimeout(0.001)
        print(f"✓ Gaze receive socket bound to {LOCAL_IP}:{GAZE_PORT}")
        
        # Game synchronization sockets
        game_send_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        game_send_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        print(f"✓ Game send socket created for {REMOTE_IP}:{GAME_PORT}")
        
        game_receive_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        game_receive_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        game_receive_socket.bind((LOCAL_IP, GAME_PORT + 1))
        game_receive_socket.settimeout(0.001)
        print(f"✓ Game receive socket bound to {LOCAL_IP}:{GAME_PORT + 1}")
        
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

def send_game_data(data_type, data):
    """Send game synchronization data to Computer B"""
    try:
        message = {
            'type': data_type,
            'data': data,
            'timestamp': time.time(),
            'from': 'A'
        }
        
        encoded = json.dumps(message).encode('utf-8')
        game_send_socket.sendto(encoded, (REMOTE_IP, GAME_PORT))
        
    except Exception as e:
        print(f"Game send error: {e}")

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
            time.sleep(0.001)

def receive_game_data():
    """Continuously receive game synchronization data"""
    global game_sync_data
    
    while True:
        try:
            data, addr = game_receive_socket.recvfrom(1024)
            message = json.loads(data.decode('utf-8'))
            
            if message.get('from') == 'B':
                if message['type'] == 'response':
                    game_sync_data['responses']['B'] = message['data']
                elif message['type'] == 'ready':
                    game_sync_data['b_ready'] = True
                    
        except socket.timeout:
            continue
        except Exception as e:
            time.sleep(0.001)

# Start network setup
if not setup_network():
    print("Failed to setup network. Exiting...")
    sys.exit()

# Start receiving threads
receive_thread = threading.Thread(target=receive_gaze_data, daemon=True)
receive_thread.start()

game_receive_thread = threading.Thread(target=receive_game_data, daemon=True)
game_receive_thread.start()

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

print("✓ Tracker configured for competitive game recording")

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

# Gaze markers (smaller, less prominent)
local_gaze_marker = visual.Circle(win=win, radius=8, fillColor='blue', lineColor='white', lineWidth=1)
remote_gaze_marker = visual.Circle(win=win, radius=8, fillColor='red', lineColor='white', lineWidth=1)

# Game grid elements
def create_grid_from_condition(condition, difficulty):
    """Create grid from condition array using actual images"""
    global grid_stimuli, grid_covers, grid_positions, question_mark, score_text, timer_text
    
    # Grid setup - 8x8 physical grid
    physical_grid_size = 8
    cell_size = 70
    grid_spacing = 80
    
    # Calculate grid position (center of screen)
    start_x = -(physical_grid_size - 1) * grid_spacing / 2
    start_y = (physical_grid_size - 1) * grid_spacing / 2
    
    grid_stimuli = []
    grid_covers = []
    grid_positions.clear()
    
    # Convert condition to categories
    if difficulty == 'medium':
        # condition is a 16-element array representing 4x4 pattern
        condition_categories = [CATEGORY_MAP[num] for num in condition]
        
        # Each position in 4x4 becomes a 2x2 block in 8x8
        for med_row in range(4):
            for med_col in range(4):
                category = condition_categories[med_row * 4 + med_col]
                # Randomly select one image from this category
                selected_image_idx = random.randint(0, len(images[category]) - 1)
                
                # Fill 2x2 block with this image
                for block_row in range(2):
                    for block_col in range(2):
                        row = med_row * 2 + block_row
                        col = med_col * 2 + block_col
                        x_pos = start_x + col * grid_spacing
                        y_pos = start_y - row * grid_spacing
                        
                        grid_positions.append((x_pos, y_pos))
                        
                        # Create stimulus
                        if images[category][selected_image_idx].startswith('placeholder_'):
                            # Use colored rectangle
                            category_colors = {
                                'face': 'orange',
                                'limb': 'green', 
                                'house': 'purple',
                                'car': 'yellow'
                            }
                            stimulus = visual.Rect(win=win, width=cell_size, height=cell_size,
                                                 fillColor=category_colors[category], 
                                                 lineColor='white', lineWidth=2,
                                                 pos=[x_pos, y_pos])
                            
                            text_stim = visual.TextStim(win, text=category[0].upper(), pos=[x_pos, y_pos],
                                                      color='black', height=24, bold=True)
                            
                            grid_stimuli.append({'rect': stimulus, 'text': text_stim, 'category': category, 'image_type': 'rect'})
                        else:
                            # Use actual image
                            img_stim = visual.ImageStim(win, image=images[category][selected_image_idx],
                                                      pos=[x_pos, y_pos], size=(cell_size, cell_size))
                            
                            grid_stimuli.append({'image': img_stim, 'category': category, 'image_type': 'image'})
                        
                        # Create cover
                        cover = visual.Rect(win=win, width=cell_size, height=cell_size,
                                          fillColor='gray', lineColor='white', lineWidth=2,
                                          pos=[x_pos, y_pos])
                        grid_covers.append(cover)
    
    else:  # hard difficulty - use 64-element array directly for 8x8 grid
        condition_categories = [CATEGORY_MAP[num] for num in condition]
        
        for row in range(physical_grid_size):
            for col in range(physical_grid_size):
                x_pos = start_x + col * grid_spacing
                y_pos = start_y - row * grid_spacing
                
                grid_positions.append((x_pos, y_pos))
                
                idx = row * physical_grid_size + col
                category = condition_categories[idx]
                selected_image_idx = random.randint(0, len(images[category]) - 1)
                
                # Create stimulus
                if images[category][selected_image_idx].startswith('placeholder_'):
                    # Use colored rectangle
                    category_colors = {
                        'face': 'orange',
                        'limb': 'green', 
                        'house': 'purple',
                        'car': 'yellow'
                    }
                    stimulus = visual.Rect(win=win, width=cell_size, height=cell_size,
                                         fillColor=category_colors[category], 
                                         lineColor='white', lineWidth=2,
                                         pos=[x_pos, y_pos])
                    
                    text_stim = visual.TextStim(win, text=category[0].upper(), pos=[x_pos, y_pos],
                                              color='black', height=24, bold=True)
                    
                    grid_stimuli.append({'rect': stimulus, 'text': text_stim, 'category': category, 'image_type': 'rect'})
                else:
                    # Use actual image
                    img_stim = visual.ImageStim(win, image=images[category][selected_image_idx],
                                              pos=[x_pos, y_pos], size=(cell_size, cell_size))
                    
                    grid_stimuli.append({'image': img_stim, 'category': category, 'image_type': 'image'})
                
                # Create cover
                cover = visual.Rect(win=win, width=cell_size, height=cell_size,
                                  fillColor='gray', lineColor='white', lineWidth=2,
                                  pos=[x_pos, y_pos])
                grid_covers.append(cover)
    
    # Question mark for recall phase
    question_mark = visual.TextStim(win, text='??', color='red', height=30, bold=True)
    
    # Score and timer displays
    score_text = visual.TextStim(win, text='', pos=[0, scn_height//2 - 30],
                               color='white', height=20, bold=True)
    
    timer_text = visual.TextStim(win, text='', pos=[0, scn_height//2 - 60],
                               color='yellow', height=24, bold=True)
    
    print(f"✓ Game grid created ({difficulty} difficulty)")

# Gaze statistics
local_gaze_stats = {
    'total_attempts': 0,
    'samples_received': 0,
    'valid_gaze_data': 0,
    'missing_data': 0,
    'last_valid_gaze': None
}

def update_local_gaze_display():
    """Update local gaze marker based on own eye tracking data using corrected formula"""
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
                # Use the corrected formula provided
                gaze_x = (1.2 * gaze_data[0] - scn_width/2 + 400 - 60)
                gaze_y = (scn_height/2 - 1.2 * gaze_data[1] + 200 - 25)
                
                if abs(gaze_x) <= scn_width/2 and abs(gaze_y) <= scn_height/2:
                    local_gaze_marker.setPos([gaze_x, gaze_y])
                    send_gaze_data(gaze_data[0], gaze_data[1], True)
                    
            except Exception as e:
                pass
        else:
            local_gaze_stats['missing_data'] += 1
            send_gaze_data(0, 0, False)

def update_remote_gaze_display():
    """Update remote gaze marker based on received data from Computer B"""
    global remote_gaze_data
    
    if remote_gaze_data.get('valid', False):
        if time.time() - remote_gaze_data.get('timestamp', 0) < 0.1:
            try:
                # Use the same corrected formula for consistency
                gaze_x = (1.2 * remote_gaze_data['x'] - scn_width/2 + 400 - 60)
                gaze_y = (scn_height/2 - 1.2 * remote_gaze_data['y'] + 200 - 25)
                
                if abs(gaze_x) <= scn_width/2 and abs(gaze_y) <= scn_height/2:
                    remote_gaze_marker.setPos([gaze_x, gaze_y])
                    
            except Exception as e:
                pass

def run_competitive_round():
    """Run a single competitive round with predetermined conditions"""
    global game_state, current_round, game_sync_data, player_scores
    
    current_round += 1
    
    # Computer A generates the game parameters (as master)
    difficulty = 'medium' if current_round <= 5 else 'hard'  # First 5 rounds medium, rest hard
    condition = random.choice(conditions[difficulty])
    target_position = random.randint(0, 63)  # 64 physical positions
    
    game_sync_data = {
        'round': current_round,
        'target_pos': target_position,
        'condition': condition,
        'difficulty': difficulty,
        'responses': {}
    }
    
    # Send game parameters to Computer B
    send_game_data('round_start', {
        'round': current_round,
        'target_pos': target_position,
        'condition': condition,
        'difficulty': difficulty
    })
    
    # Create grid with condition
    create_grid_from_condition(condition, difficulty)
    target_category = grid_stimuli[target_position]['category']
    
    el_tracker.sendMessage(f"ROUND_{current_round}_START_TARGET_{target_position}_CATEGORY_{target_category}_DIFFICULTY_{difficulty}")
    
    # Study phase (5 seconds)
    game_state = 'study'
    study_start = core.getTime()
    
    while core.getTime() - study_start < 5.0:
        update_local_gaze_display()
        update_remote_gaze_display()
        
        win.clearBuffer()
        
        # Draw game grid
        for stim in grid_stimuli:
            if stim['image_type'] == 'rect':
                stim['rect'].draw()
                stim['text'].draw()
            else:
                stim['image'].draw()
        
        # Draw gaze markers (small and unobtrusive)
        local_gaze_marker.draw()
        if remote_gaze_data.get('valid', False):
            remote_gaze_marker.draw()
        
        # Draw timer
        time_left = 5.0 - (core.getTime() - study_start)
        timer_text.setText(f"Study Time: {time_left:.1f}s")
        timer_text.draw()
        
        # Draw score
        score_text.setText(f"Round {current_round}/{total_rounds} | Team Score: {player_scores['A']}")
        score_text.draw()
        
        win.flip()
        core.wait(0.016)
        
        # Check for escape
        keys = event.getKeys()
        if 'escape' in keys:
            return None
    
    el_tracker.sendMessage(f"ROUND_{current_round}_STUDY_END")
    
    # Recall phase (no time limit - wait for responses)
    game_state = 'recall'
    target_pos = grid_positions[target_position]
    question_mark.setPos([target_pos[0], target_pos[1] + 50])
    
    el_tracker.sendMessage(f"ROUND_{current_round}_RECALL_START")
    
    response = None
    response_time = None
    recall_start = core.getTime()
    
    # No time limit - wait for user response
    while response is None:
        update_local_gaze_display()
        update_remote_gaze_display()
        
        win.clearBuffer()
        
        # Draw covered grid
        for cover in grid_covers:
            cover.draw()
        
        # Draw question mark
        question_mark.draw()
        
        # Draw gaze markers
        local_gaze_marker.draw()
        if remote_gaze_data.get('valid', False):
            remote_gaze_marker.draw()
        
        # Draw instructions
        instruction_text = visual.TextStim(win, text='H=House  C=Car  F=Face  L=Limb', 
                                         pos=[0, -scn_height//2 + 30], color='white', height=16)
        instruction_text.draw()
        
        # Draw score
        score_text.setText(f"Round {current_round}/{total_rounds} | Team Score: {player_scores['A']}")
        score_text.draw()
        
        win.flip()
        core.wait(0.016)
        
        # Check for response
        keys = event.getKeys()
        if 'h' in keys:
            response = 'house'
            response_time = core.getTime() - recall_start
        elif 'c' in keys:
            response = 'car'
            response_time = core.getTime() - recall_start
        elif 'f' in keys:
            response = 'face'
            response_time = core.getTime() - recall_start
        elif 'l' in keys:
            response = 'limb'
            response_time = core.getTime() - recall_start
        elif 'escape' in keys:
            return None
    
    # Record our response
    if response:
        game_sync_data['responses']['A'] = {
            'answer': response,
            'time': response_time,
            'timestamp': time.time()
        }
        send_game_data('response', game_sync_data['responses']['A'])
        el_tracker.sendMessage(f"ROUND_{current_round}_RESPONSE_A_{response}_{response_time:.3f}")
    
    # Wait for both responses or timeout
    wait_start = time.time()
    while time.time() - wait_start < 3.0:  # Wait up to 3 seconds for other player
        if 'B' in game_sync_data['responses']:
            break
        time.sleep(0.01)
    
    # Determine winner and scoring - CORRECTED LOGIC
    a_response = game_sync_data['responses'].get('A')
    b_response = game_sync_data['responses'].get('B')
    
    round_result = {
        'round': current_round,
        'target_position': target_position,
        'target_category': target_category,
        'difficulty': difficulty,
        'condition': condition,
        'a_response': a_response,
        'b_response': b_response,
        'winner': None,
        'points_awarded': 0
    }
    
    # Collaborative scoring: first player to respond determines the outcome for BOTH players
    first_player = None
    first_response = None
    
    if a_response and b_response:
        # Both players responded - check who answered first
        if a_response['time'] < b_response['time']:
            first_player = 'A'
            first_response = a_response['answer']
        else:
            first_player = 'B'
            first_response = b_response['answer']
    elif a_response and not b_response:
        # Only A responded
        first_player = 'A'
        first_response = a_response['answer']
    elif b_response and not a_response:
        # Only B responded
        first_player = 'B'
        first_response = b_response['answer']
    
    # Check if the first responder was correct
    if first_response == target_category:
        # First responder was correct - both players get +1 point
        player_scores['A'] += 1
        player_scores['B'] += 1
        round_result['winner'] = f'Team (Player {first_player} first)'
        round_result['points_awarded'] = 1
    else:
        # First responder was incorrect - both players get 0 points
        round_result['winner'] = f'Team failed (Player {first_player} first, wrong answer)'
        round_result['points_awarded'] = 0
    
    trial_results.append(round_result)
    
    # Show feedback (3 seconds)
    game_state = 'feedback'
    feedback_start = core.getTime()
    
    while core.getTime() - feedback_start < 3.0:
        update_local_gaze_display()
        update_remote_gaze_display()
        
        win.clearBuffer()
        
        # Show correct answer
        if grid_stimuli[target_position]['image_type'] == 'rect':
            grid_stimuli[target_position]['rect'].draw()
            grid_stimuli[target_position]['text'].draw()
        else:
            grid_stimuli[target_position]['image'].draw()
        
        # Draw other covers
        for i, cover in enumerate(grid_covers):
            if i != target_position:
                cover.draw()
        
        # Draw gaze markers
        local_gaze_marker.draw()
        if remote_gaze_data.get('valid', False):
            remote_gaze_marker.draw()
        
        # Draw feedback
        if round_result['points_awarded'] > 0:
            feedback_msg = f"{round_result['winner']} - Correct! +1 point for both players"
            feedback_color = 'green'
        else:
            feedback_msg = f"{round_result['winner']} - No points this round"
            feedback_color = 'red'
        
        feedback_text = visual.TextStim(win, text=feedback_msg, pos=[0, -scn_height//2 + 60],
                                      color=feedback_color, height=20, bold=True)
        feedback_text.draw()
        
        # Draw score
        score_text.setText(f"Round {current_round}/{total_rounds} | Team Score: {player_scores['A']}")
        score_text.draw()
        
        win.flip()
        core.wait(0.016)
        
        # Check for escape
        keys = event.getKeys()
        if 'escape' in keys:
            return None
    
    el_tracker.sendMessage(f"ROUND_{current_round}_END")
    
    # Clear responses for next round
    game_sync_data['responses'] = {}
    
    return round_result

def clear_screen(win):
    win.clearBuffer()
    win.flip()

def show_msg(win, text, wait_for_keypress=True):
    msg = visual.TextStim(win, text, color='white', wrapWidth=scn_width*0.8, 
                         height=24, bold=True)
    
    clear_screen(win)
    
    if wait_for_keypress:
        while True:
            win.clearBuffer()
            msg.draw()
            win.flip()
            core.wait(0.016)
            
            keys = event.getKeys()
            if keys:
                break
    else:
        msg.draw()
        win.flip()
    
    clear_screen(win)

def terminate_task():
    global el_tracker, send_socket, receive_socket, game_send_socket, game_receive_socket
    
    print("\nCleaning up...")
    
    # Save game results
    if trial_results:
        results_file = os.path.join(session_folder, f"{session_identifier}_competitive_results.txt")
        with open(results_file, 'w') as f:
            f.write("Round\tDifficulty\tPosition\tTarget\tA_Response\tA_Time\tB_Response\tB_Time\tWinner\tPoints\n")
            for result in trial_results:
                a_resp = result['a_response']['answer'] if result['a_response'] else 'None'
                a_time = result['a_response']['time'] if result['a_response'] else 'None'
                b_resp = result['b_response']['answer'] if result['b_response'] else 'None'
                b_time = result['b_response']['time'] if result['b_response'] else 'None'
                
                f.write(f"{result['round']}\t{result['difficulty']}\t{result['target_position']}\t{result['target_category']}\t"
                       f"{a_resp}\t{a_time}\t{b_resp}\t{b_time}\t{result['winner']}\t{result['points_awarded']}\n")
        
        print(f"✓ Game results saved: Team Score={player_scores['A']} (both players have same score)")
    
    # Close network sockets
    try:
        send_socket.close()
        receive_socket.close()
        game_send_socket.close()
        game_receive_socket.close()
        print("✓ Network sockets closed")
    except:
        pass
    
    if el_tracker and el_tracker.isConnected():
        try:
            if el_tracker.isRecording():
                el_tracker.stopRecording()
            el_tracker.setOfflineMode()
            el_tracker.sendCommand('clear_screen 0')
            pylink.msecDelay(500)
            el_tracker.closeDataFile()
            
            # Download EDF file
            local_edf = os.path.join(session_folder, session_identifier + '.EDF')
            try:
                el_tracker.receiveDataFile(edf_file, local_edf)
                print(f"✓ Data file saved: {local_edf}")
            except RuntimeError as error:
                print('Data file download error:', error)
            
            el_tracker.close()
        except Exception as e:
            print(f"Cleanup error: {e}")
    
    # Print final statistics
    if local_gaze_stats['total_attempts'] > 0:
        valid_rate = 100 * local_gaze_stats['valid_gaze_data'] / local_gaze_stats['total_attempts']
        print(f"\nFinal Statistics:")
        print(f"  Local gaze valid: {local_gaze_stats['valid_gaze_data']}/{local_gaze_stats['total_attempts']} ({valid_rate:.1f}%)")
        print(f"  Network sent: {network_stats['sent']}")
        print(f"  Network received: {network_stats['received']}")
        print(f"  Network errors: {network_stats['errors']}")
    
    win.close()
    core.quit()
    sys.exit()

# Show instructions
task_msg = 'Computer A - Collaborative Memory Game\n\n'
task_msg += 'Two-Player Collaborative Rules:\n'
task_msg += '• Study grid for 5 seconds\n'
task_msg += '• Recall what was at marked position\n'
task_msg += '• Press H=House, C=Car, F=Face, L=Limb\n'
task_msg += '• NO TIME LIMIT for responses\n'
task_msg += '• First player to respond determines team outcome:\n'
task_msg += '  - If first responder is CORRECT: +1 point for BOTH players\n'
task_msg += '  - If first responder is WRONG: 0 points for BOTH players\n'
task_msg += '• Second player response is ignored\n'
task_msg += '• Medium difficulty (first 5 rounds): 4x4 logical patterns\n'
task_msg += '• Hard difficulty (last 5 rounds): 8x8 unique patterns\n'
task_msg += f'• {total_rounds} rounds total\n\n'
task_msg += 'Network Configuration:\n'
task_msg += f'• Local IP: {LOCAL_IP}\n'
task_msg += f'• Remote IP: {REMOTE_IP}\n\n'
task_msg += 'Controls:\n'
task_msg += '• SPACE = Recalibrate eye tracker\n'
task_msg += '• ESCAPE = Exit program\n\n'
if dummy_mode:
    task_msg += 'DUMMY MODE: Simulated eye tracking\n'
task_msg += 'Press any key to begin calibration'

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

show_msg(win, "Calibration complete!\n\nAs Computer A, you are the game master.\n\nPress any key when both computers are ready to start the game.")

# Send ready signal
send_game_data('ready', {'computer': 'A'})

# Main competitive game loop
try:
    print("\n6. STARTING COMPETITIVE MEMORY GAME")
    print("-" * 40)
    
    # Start recording
    recording_success = False
    for attempt in range(3):
        print(f"Recording attempt {attempt + 1}:")
        
        el_tracker.setOfflineMode()
        pylink.msecDelay(100)
        
        error = el_tracker.startRecording(1, 1, 1, 1)
        
        if error == 0:
            pylink.msecDelay(300)
            
            for i in range(10):
                sample = el_tracker.getNewestSample()
                if sample is not None:
                    recording_success = True
                    break
                pylink.msecDelay(10)
            
            if recording_success:
                break
    
    if recording_success:
        el_tracker.sendMessage("COMPETITIVE_MEMORY_GAME_START")
        print("✓ Recording active - starting competitive memory game")
        
        # Show game start message
        show_msg(win, f"Collaborative Memory Game Starting!\n\n{total_rounds} rounds ahead.\n\nWork together! First correct answer = +1 for both!\n\nPress any key to start Round 1", True)
        
        # Run all rounds
        for round_num in range(total_rounds):
            result = run_competitive_round()
            if result is None:  # User pressed escape
                break
            
            # Wait for player to be ready for next round (except after last round)
            if round_num < total_rounds - 1:
                show_msg(win, f"Round {round_num + 1} complete.\n\nTeam Score: {player_scores['A']} points\n\nPress any key when ready for Round {round_num + 2}", True)
        
        # Show final results
        if trial_results:
            results_msg = f'Collaborative Memory Game Complete!\n\n'
            results_msg += f'Final Team Score: {player_scores["A"]} points\n'
            results_msg += f'(Both players have the same score)\n\n'
            
            success_rate = (player_scores['A'] / total_rounds) * 100
            results_msg += f'Success Rate: {success_rate:.1f}%\n\n'
            
            # Show round-by-round results
            results_msg += 'Round Summary:\n'
            for r in trial_results:
                status = "✓" if r['points_awarded'] > 0 else "✗"
                results_msg += f'• Round {r["round"]} ({r["difficulty"]}): {r["target_category"]} - {status}\n'
            
            results_msg += f'\nPress any key to exit...'
            
            show_msg(win, results_msg)
        
        el_tracker.stopRecording()
        el_tracker.sendMessage("COMPETITIVE_MEMORY_GAME_END")
        print("✓ Competitive memory game completed")
        
        # Show final statistics
        completion_msg = f'Computer A - Collaborative Game Complete!\n\n'
        completion_msg += f'Final Team Score: {player_scores["A"]} points\n\n'
        completion_msg += f'Local Eye Tracking:\n'
        local_valid_rate = 100 * local_gaze_stats['valid_gaze_data'] / max(1, local_gaze_stats['total_attempts'])
        completion_msg += f'• Valid gaze data: {local_valid_rate:.1f}%\n'
        completion_msg += f'• Total samples: {local_gaze_stats["samples_received"]}\n\n'
        completion_msg += f'Network Communication:\n'
        completion_msg += f'• Data sent to B: {network_stats["sent"]} packets\n'
        completion_msg += f'• Data received from B: {network_stats["received"]} packets\n'
        completion_msg += f'• Network errors: {network_stats["errors"]}\n\n'
        completion_msg += f'Data saved to EDF file\n\n'
        completion_msg += f'Press any key to exit'
        
        show_msg(win, completion_msg)
        
    else:
        print("✗ Failed to establish eye tracking")
        show_msg(win, "Could not establish eye tracking\nPress any key to exit")

except KeyboardInterrupt:
    print("Session interrupted by user")
except Exception as e:
    print(f"Session error: {e}")
    import traceback
    traceback.print_exc()

finally:
    terminate_task()
