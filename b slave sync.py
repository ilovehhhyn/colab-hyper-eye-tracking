#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Dyadic Study Client (Computer B - IP: 100.1.1.11)
This script runs on Computer B and uses UDP for low-latency communication
"""

from psychopy import visual, core, event, data, gui
import socket
import json
import threading
import queue
import time

class DyadUDPClient:
    def __init__(self, client_ip='100.1.1.11', server_ip='100.1.1.10', port=5555):
        """Initialize the UDP client for dyadic communication"""
        self.client_ip = client_ip
        self.server_ip = server_ip
        self.port = port
        self.socket = None
        self.running = False
        self.message_queue = queue.Queue()
        
    def start_client(self):
        """Start the UDP client"""
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        # Try binding to specific IP first, then fall back to 0.0.0.0
        try:
            self.socket.bind((self.client_ip, self.port))
            print(f"Bound to {self.client_ip}:{self.port}")
        except OSError as e:
            print(f"Could not bind to {self.client_ip}:{self.port}: {e}")
            print("Trying to bind to 0.0.0.0 (all interfaces)...")
            try:
                self.socket.bind(('0.0.0.0', self.port))
                print(f"Successfully bound to 0.0.0.0:{self.port}")
            except OSError as e2:
                print(f"Failed to bind: {e2}")
                raise
        
        self.socket.settimeout(0.1)  # Non-blocking with short timeout
        
        self.running = True
        print(f"UDP Client started on {self.client_ip}:{self.port}")
        print(f"Will communicate with server at {self.server_ip}:{self.port}")
        
        # Start receiving thread
        self.receive_thread = threading.Thread(target=self._receive_messages)
        self.receive_thread.daemon = True
        self.receive_thread.start()
        
    def send_message(self, message_type, data=None):
        """Send a UDP message to the server"""
        if not self.socket:
            return False
            
        message = {
            'type': message_type,
            'timestamp': time.time(),
            'data': data
        }
        
        try:
            message_json = json.dumps(message)
            self.socket.sendto(message_json.encode('utf-8'), (self.server_ip, self.port))
            return True
        except Exception as e:
            print(f"Error sending message: {e}")
            return False
            
    def _receive_messages(self):
        """Receive UDP messages from server (runs in separate thread)"""
        while self.running:
            try:
                data, addr = self.socket.recvfrom(4096)
                message = json.loads(data.decode('utf-8'))
                message['sender_addr'] = addr
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
        start_time = time.time()
        while time.time() - start_time < timeout:
            message = self.get_message(timeout=0.1)
            if message and message.get('type') == expected_type:
                return message
        return None
        
    def close(self):
        """Close the client"""
        self.running = False
        if self.receive_thread:
            self.receive_thread.join(timeout=1)
        if self.socket:
            self.socket.close()

# Main experiment code
def run_experiment():
    """Run the client-side experiment on Computer B"""
    
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
    client = DyadUDPClient(
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
        units='height'
    )
    
    # Create stimuli
    instructions = visual.TextStim(win, 
        text="Starting UDP client...",
        height=0.05)
    
    trial_text = visual.TextStim(win,
        text="",
        height=0.1)
    
    sync_dot = visual.Circle(win,
        radius=0.05,
        fillColor='blue',
        pos=(0.4, 0.4))
    
    status_text = visual.TextStim(win,
        text="",
        height=0.03,
        pos=(0, -0.4))
    
    # Start client
    instructions.draw()
    win.flip()
    client.start_client()
    
    # Update display
    instructions.text = "Waiting for Computer A to start experiment..."
    instructions.draw()
    win.flip()
    
    # Wait for start signal
    start_msg = client.wait_for_message('start_experiment', timeout=300)
    if not start_msg:
        instructions.text = "No start signal received. Check connection."
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
    sync_offset = time.time() - start_msg['data']['sync_time']
    
    # Main experiment loop
    trial_clock = core.Clock()
    data_log = []
    running = True
    
    while running:
        # Wait for messages
        message = client.get_message(timeout=0.1)
        
        if not message:
            continue
            
        if message['type'] == 'trial_sync':
            # Acknowledge sync immediately
            client.send_message('sync_ack')
            
            # Extract trial info
            trial_data = message['data']
            trial_num = trial_data['trial_number']
            sync_time = trial_data['sync_timestamp']
            
            # Calculate sync latency
            current_time = time.time()
            latency = (current_time - sync_time) * 1000
            
            # Reset trial clock
            trial_clock.reset()
            
            # Display trial
            trial_text.text = f"Trial {trial_num}"
            trial_text.draw()
            sync_dot.draw()
            
            # Show sync status
            status_text.text = f"Sync OK (latency: {latency:.1f}ms)"
            status_text.draw()
            
            win.flip()
            
            # Collect response
            keys = event.waitKeys(maxWait=3.0, keyList=['left', 'right', 'escape'], 
                                timeStamped=trial_clock)
            
            response = None
            rt = None
            
            if keys:
                response, rt = keys[0]
                if response == 'escape':
                    running = False
                    break
            
            # Send response to server
            client.send_message('client_response', {
                'response': response,
                'rt': rt
            })
            
            # Log trial data
            trial_log = {
                'trial': trial_num,
                'sync_time': sync_time,
                'sync_latency': latency,
                'response': response,
                'rt': rt
            }
            data_log.append(trial_log)
            
            # Clear screen for ITI
            win.flip()
            
        elif message['type'] == 'server_response':
            # Store server's response if needed
            pass
            
        elif message['type'] == 'end_experiment':
            running = False
    
    # Save data
    import pandas as pd
    df = pd.DataFrame(data_log)
    filename = f'dyad_computerB_{exp_info["participant_B_id"]}_{time.strftime("%Y%m%d_%H%M%S")}.csv'
    df.to_csv(filename, index=False)
    
    # Goodbye message
    instructions.text = f"Experiment complete!\nData saved to {filename}"
    instructions.draw()
    win.flip()
    core.wait(3)
    
    # Cleanup
    client.close()
    win.close()
    core.quit()

if __name__ == '__main__':
    run_experiment()
