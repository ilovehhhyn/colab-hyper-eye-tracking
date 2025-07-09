#!/usr/bin/env python3
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

# Network Setup
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

# Game elements
def create_game_elements():
    """Create visual elements for the memory game"""
    global grid_stimuli, grid_covers, question_mark, game_instructions, feedback_text
    
    # Grid setup - 6x6 grid in the center area
    grid_size = 6
    cell_size = 60
    grid_spacing = 70
    
    # Calculate grid position (center of screen, below status bar)
    start_x = -(grid_size - 1) * grid_spacing / 2
    start_y = 100  # Below status bar
    
    grid_stimuli = []
    grid_covers = []
    grid_positions.clear()
    
    # Create image categories
    categories = ['F', 'L', 'H', 'C']  # Face, Limbs, House, Car
    category_colors = {
        'F': 'orange',      # Face
        'L': 'green',       # Limbs  
        'H': 'purple',      # House
        'C': 'yellow'       # Car
    }
    
    # Generate 36 items (9 of each category)
    items = []
    for category in categories:
        for i in range(9):
            items.append(category)
    
    # Shuffle the items
    random.shuffle(items)
    
    # Create grid
    for row in range(grid_size):
        for col in range(grid_size):
            x_pos = start_x + col * grid_spacing
            y_pos = start_y - row * grid_spacing
            
            grid_positions.append((x_pos, y_pos))
            
            # Create stimulus (colored rectangle with letter)
            item_idx = row * grid_size + col
            category = items[item_idx]
            
            stimulus = visual.Rect(win=win, width=cell_size, height=cell_size,
                                 fillColor=category_colors[category], 
                                 lineColor='white', lineWidth=2,
                                 pos=[x_pos, y_pos])
            
            # Add category letter
            text_stim = visual.TextStim(win, text=category, pos=[x_pos, y_pos],
                                      color='black', height=30, bold=True)
            
            grid_stimuli.append({'rect': stimulus, 'text': text_stim, 'category': category})
            
            # Create cover (gray rectangle)
            cover = visual.Rect(win=win, width=cell_size, height=cell_size,
                              fillColor='gray', lineColor='white', lineWidth=2,
                              pos=[x_pos, y_pos])
            grid_covers.append(cover)
    
    # Question mark for recall phase
    question_mark = visual.TextStim(win, text='?', color='red', height=40, bold=True)
    
    # Instructions and feedback
    game_instructions = visual.TextStim(win, text='', pos=[0, -scn_height//2 + 60],
                                      color='white', height=16, wrapWidth=scn_width*0.8)
    
    feedback_text = visual.TextStim(win, text='', pos=[0, -scn_height//2 + 20],
                                  color='white', height=20, bold=True)
    
    print("✓ Game elements created")

# Corner decorations (smaller)
corner_size = 20
corners = []
corner_positions = [
    (-scn_width//2 + corner_size, scn_height//2 - corner_size),
    (scn_width//2 - corner_size, scn_height//2 - corner_size),
    (-scn_width//2 + corner_size, -scn_height//2 + corner_size),
    (scn_width//2 - corner_size, -scn_height//2 + corner_size)
]

colors = ['lightgreen', 'lightblue', 'lightcoral', 'lightyellow']
for i, pos in enumerate(corner_positions):
    corner = visual.Circle(win=win, radius=15, fillColor=colors[i], lineColor='white', lineWidth=2, pos=pos)
    corners.append(corner)

# Legend (smaller)
legend_bg = visual.Rect(win=win, width=250, height=80, 
                       fillColor='darkslategray', lineColor='white', lineWidth=2,
                       pos=[scn_width//2 - 150, -scn_height//2 + 120])

legend_text = visual.TextStim(win, text='Green=B(You) Blue=A(Remote)\nF=Face L=Limbs H=House C=Car', 
                             pos=[scn_width//2 - 150, -scn_height//2 + 120], 
                             color='white', height=12, bold=True)

# Gaze statistics
local_gaze_stats = {
    'total_attempts': 0,
    'samples_received': 0,
    'valid_gaze_data': 0,
    'missing_data': 0,
    'last_valid_gaze': None
}

create_game_elements()
print(f"✓ Visual elements created")

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
                gaze_x = gaze_data[0] - win.size[0]/2 + 50
                gaze_y = win.size[1]/2 - gaze_data[1] + 200
                
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
                
                gaze_x = (scn_width/2 + 200 - remote_gaze_data['x']) 
                gaze_y = (remote_gaze_data['y'] - scn_height/2 - 800)
                
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

def run_memory_trial():
    """Run a single memory trial"""
    global game_state, grid_images, current_trial
    
    current_trial += 1
    target_position = random.randint(0, 35)  # Random position in 6x6 grid
    target_category = grid_stimuli[target_position]['category']
    
    el_tracker.sendMessage(f"TRIAL_{current_trial}_START")
    
    # Study phase (10 seconds)
    game_state = 'study'
    game_instructions.setText(f"Trial {current_trial}/{total_trials}: Study the grid for 10 seconds")
    
    study_start = core.getTime()
    while core.getTime() - study_start < 10.0:
        # Update gaze displays
        update_local_gaze_display()
        update_remote_gaze_display()
        
        win.clearBuffer()
        
        # Draw game grid
        for stim in grid_stimuli:
            stim['rect'].draw()
            stim['text'].draw()
        
        # Draw gaze markers
        local_gaze_marker.draw()
        local_gaze_sparkle1.draw()
        if remote_gaze_data.get('valid', False):
            remote_gaze_marker.draw()
            remote_gaze_sparkle1.draw()
        
        # Draw UI elements
        draw_ui_elements()
        
        time_left = 10.0 - (core.getTime() - study_start)
        game_instructions.setText(f"Trial {current_trial}/{total_trials}: Study the grid - {time_left:.1f}s remaining")
        game_instructions.draw()
        
        win.flip()
        core.wait(0.016)
        
        # Check for escape
        keys = event.getKeys()
        if 'escape' in keys:
            return None
    
    el_tracker.sendMessage(f"TRIAL_{current_trial}_STUDY_END")
    
    # Recall phase
    game_state = 'recall'
    game_instructions.setText(f"What was at the marked position? Press: F=Face, L=Limbs, H=House, C=Car")
    
    # Position question mark
    target_pos = grid_positions[target_position]
    question_mark.setPos(target_pos)
    
    el_tracker.sendMessage(f"TRIAL_{current_trial}_RECALL_START_POS_{target_position}")
    
    response = None
    recall_start = core.getTime()
    
    while response is None:
        # Update gaze displays
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
        local_gaze_sparkle1.draw()
        if remote_gaze_data.get('valid', False):
            remote_gaze_marker.draw()
            remote_gaze_sparkle1.draw()
        
        # Draw UI elements
        draw_ui_elements()
        game_instructions.draw()
        
        win.flip()
        core.wait(0.016)
        
        # Check for response
        keys = event.getKeys()
        if 'f' in keys:
            response = 'F'
        elif 'l' in keys:
            response = 'L'
        elif 'h' in keys:
            response = 'H'
        elif 'c' in keys:
            response = 'C'
        elif 'escape' in keys:
            return None
    
    # Record response
    reaction_time = core.getTime() - recall_start
    correct = (response == target_category)
    
    trial_result = {
        'trial': current_trial,
        'target_position': target_position,
        'target_category': target_category,
        'response': response,
        'correct': correct,
        'reaction_time': reaction_time
    }
    
    trial_results.append(trial_result)
    
    el_tracker.sendMessage(f"TRIAL_{current_trial}_RESPONSE_{response}_CORRECT_{correct}_RT_{reaction_time:.3f}")
    
    # Feedback phase (2 seconds)
    game_state = 'feedback'
    if correct:
        feedback_text.setText(f"Correct! ({reaction_time:.2f}s)")
        feedback_text.setColor('green')
    else:
        feedback_text.setText(f"Incorrect. Answer was {target_category} ({reaction_time:.2f}s)")
        feedback_text.setColor('red')
    
    feedback_start = core.getTime()
    while core.getTime() - feedback_start < 2.0:
        # Update gaze displays
        update_local_gaze_display()
        update_remote_gaze_display()
        
        win.clearBuffer()
        
        # Show correct answer
        grid_stimuli[target_position]['rect'].draw()
        grid_stimuli[target_position]['text'].draw()
        
        # Draw other covers
        for i, cover in enumerate(grid_covers):
            if i != target_position:
                cover.draw()
        
        # Draw gaze markers
        local_gaze_marker.draw()
        local_gaze_sparkle1.draw()
        if remote_gaze_data.get('valid', False):
            remote_gaze_marker.draw()
            remote_gaze_sparkle1.draw()
        
        # Draw UI elements
        draw_ui_elements()
        feedback_text.draw()
        
        win.flip()
        core.wait(0.016)
        
        # Check for escape
        keys = event.getKeys()
        if 'escape' in keys:
            return None
    
    el_tracker.sendMessage(f"TRIAL_{current_trial}_END")
    return trial_result

def draw_ui_elements():
    """Draw status bar, legend, and corners"""
    # Draw corners
    for corner in corners:
        corner.draw()
    
    # Draw status
    status_background.draw()
    local_valid_rate = 100 * local_gaze_stats['valid_gaze_data'] / max(1, local_gaze_stats['total_attempts'])
    remote_age = time.time() - remote_gaze_data.get('timestamp', 0)
    remote_status = "CONNECTED" if remote_age < 0.1 else f"DELAYED"
    
    status_text.setText(
        f"COMPUTER B - MEMORY GAME | Trial {current_trial}/{total_trials} | "
        f"Gaze: {local_valid_rate:.0f}% | Remote: {remote_status} | "
        f"Sent: {network_stats['sent']} Recv: {network_stats['received']}"
    )
    status_text.draw()
    
    # Draw legend
    legend_bg.draw()
    legend_text.draw()

def draw_decorative_elements():
    """Draw all decorative elements"""
    for corner in corners:
        corner.draw()

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
            draw_decorative_elements()
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

def terminate_task():
    global el_tracker, send_socket, receive_socket
    
    print("\nCleaning up...")
    
    # Save game results
    if trial_results:
        results_file = os.path.join(session_folder, f"{session_identifier}_memory_results.txt")
        with open(results_file, 'w') as f:
            f.write("Trial\tPosition\tTarget\tResponse\tCorrect\tRT\n")
            for result in trial_results:
                f.write(f"{result['trial']}\t{result['target_position']}\t{result['target_category']}\t"
                       f"{result['response']}\t{result['correct']}\t{result['reaction_time']:.3f}\n")
        
        correct_count = sum(1 for r in trial_results if r['correct'])
        avg_rt = np.mean([r['reaction_time'] for r in trial_results])
        print(f"✓ Game results saved: {correct_count}/{len(trial_results)} correct, avg RT: {avg_rt:.2f}s")
    
    # Close network sockets
    try:
        send_socket.close()
        receive_socket.close()
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

# Main gaze sharing and game loop
try:
    print("\n6. STARTING GAZE SHARING AND MEMORY GAME SESSION")
    print("-" * 50)
    
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
        el_tracker.sendMessage("GAZE_SHARING_MEMORY_GAME_START")
        print("✓ Recording active - starting gaze sharing and memory game")
        
        # Run memory game trials
        game_state = 'waiting'
        current_trial = 0
        
        # Show game start message
        show_msg(win, f"Memory Game Starting!\n\n{total_trials} trials ahead.\n\nPress any key to start Trial 1", True)
        
        # Run all trials
        for trial_num in range(total_trials):
            result = run_memory_trial()
            if result is None:  # User pressed escape
                break
            
            # Short break between trials (except after last trial)
            if trial_num < total_trials - 1:
                show_msg(win, f"Trial {trial_num + 1} complete.\n\nPress any key for Trial {trial_num + 2}", True)
        
        # Show final results
        if trial_results:
            correct_count = sum(1 for r in trial_results if r['correct'])
            avg_rt = np.mean([r['reaction_time'] for r in trial_results])
            accuracy = 100 * correct_count / len(trial_results)
            
            results_msg = f'Memory Game Complete!\n\n'
            results_msg += f'Results Summary:\n'
            results_msg += f'• Accuracy: {correct_count}/{len(trial_results)} ({accuracy:.1f}%)\n'
            results_msg += f'• Average Response Time: {avg_rt:.2f} seconds\n\n'
            results_msg += f'Trial Details:\n'
            for r in trial_results:
                status = "✓" if r['correct'] else "✗"
                results_msg += f'• Trial {r["trial"]}: {status} {r["target_category"]} → {r["response"]} ({r["reaction_time"]:.2f}s)\n'
            results_msg += f'\nPress any key to continue with free gaze sharing...'
            
            show_msg(win, results_msg)
        
        # Continue with free gaze sharing
        el_tracker.sendMessage("FREE_GAZE_SHARING_START")
        session_start_time = core.getTime()
        
        show_msg(win, "Free gaze sharing mode.\n\nWatch each other's gaze patterns!\n\nPress ESCAPE to exit, SPACE to recalibrate.", True)
        
        while True:
            current_time = core.getTime()
            session_duration = current_time - session_start_time
            
            # Update both local and remote gaze displays
            update_local_gaze_display()
            update_remote_gaze_display()
            
            # Clear and draw
            win.clearBuffer()
            
            # Draw decorative elements
            draw_decorative_elements()
            
            # Draw status background
            status_background.draw()
            
            # Update status text with network information
            local_valid_rate = 100 * local_gaze_stats['valid_gaze_data'] / max(1, local_gaze_stats['total_attempts'])
            remote_age = time.time() - remote_gaze_data.get('timestamp', 0)
            remote_status = "CONNECTED" if remote_age < 0.1 else f"DELAYED ({remote_age:.1f}s)"
            
            status_text.setText(
                f"COMPUTER B - FREE GAZE SHARING | Duration: {session_duration:.1f}s\n"
                f"Local Gaze: {local_valid_rate:.0f}% valid | Remote: {remote_status}\n"
                f"Network: Sent {network_stats['sent']} | Received {network_stats['received']} | Errors {network_stats['errors']}"
            )
            status_text.draw()
            
            # Draw legend
            legend_bg.draw()
            legend_text.draw()
            
            # Draw gaze markers - local (green) and remote (blue)
            local_gaze_marker.draw()
            local_gaze_sparkle1.draw()
            
            # Only draw remote gaze if data is recent
            if remote_gaze_data.get('valid', False) and remote_age < 0.5:
                remote_gaze_marker.draw()
                remote_gaze_sparkle1.draw()
            
            win.flip()
            core.wait(0.008)  # ~120Hz refresh
            
            # Check for controls
            keys = event.getKeys()
            if 'escape' in keys:
                break
            elif 'space' in keys:
                print("Recalibrating...")
                try:
                    el_tracker.doTrackerSetup()
                    el_tracker.exitCalibration()
                    pylink.msecDelay(200)
                    if not el_tracker.isRecording():
                        el_tracker.startRecording(1, 1, 1, 1)
                        pylink.msecDelay(500)
                except Exception as e:
                    print(f"Recalibration error: {e}")
        
        el_tracker.stopRecording()
        el_tracker.sendMessage("GAZE_SHARING_MEMORY_GAME_END")
        print("✓ Gaze sharing and memory game session completed")
        
        # Show final statistics
        session_duration = core.getTime() - session_start_time
        completion_msg = f'Computer B - Session Complete!\n\n'
        
        if trial_results:
            correct_count = sum(1 for r in trial_results if r['correct'])
            avg_rt = np.mean([r['reaction_time'] for r in trial_results])
            completion_msg += f'Memory Game Results:\n'
            completion_msg += f'• Accuracy: {correct_count}/{len(trial_results)} ({100*correct_count/len(trial_results):.1f}%)\n'
            completion_msg += f'• Average RT: {avg_rt:.2f} seconds\n\n'
        
        completion_msg += f'Session Duration: {session_duration:.1f} seconds\n\n'
        completion_msg += f'Local Eye Tracking:\n'
        local_valid_rate = 100 * local_gaze_stats['valid_gaze_data'] / max(1, local_gaze_stats['total_attempts'])
        completion_msg += f'• Valid gaze data: {local_valid_rate:.1f}%\n'
        completion_msg += f'• Total samples: {local_gaze_stats["samples_received"]}\n\n'
        completion_msg += f'Network Communication:\n'
        completion_msg += f'• Data sent to A: {network_stats["sent"]} packets\n'
        completion_msg += f'• Data received from A: {network_stats["received"]} packets\n'
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
