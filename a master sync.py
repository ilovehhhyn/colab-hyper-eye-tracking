#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Dyadic Study Server (Computer A - IP: 100.1.1.10)
This script runs on Computer A and uses UDP for low-latency communication
"""

from psychopy import visual, core, event, data, gui
import socket
import json
import threading
import queue
import time

class DyadUDPServer:
    def __init__(self, server_ip='100.1.1.10', client_ip='100.1.1.11', port=5555):
        """Initialize the UDP server for dyadic communication"""
        self.server_ip = server_ip
        self.client_ip = client_ip
        self.port = port
        self.socket = None
        self.running = False
        self.message_queue = queue.Queue()
        
    def start_server(self):
        """Start the UDP server"""
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        # Try binding to specific IP first, then fall back to 0.0.0.0
        try:
            self.socket.bind((self.server_ip, self.port))
            print(f"Bound to {self.server_ip}:{self.port}")
        except OSError as e:
            print(f"Could not bind to {self.server_ip}:{self.port}: {e}")
            print("Trying to bind to 0.0.0.0 (all interfaces)...")
            try:
                self.socket.bind(('0.0.0.0', self.port))
                print(f"Successfully bound to 0.0.0.0:{self.port}")
            except OSError as e2:
                print(f"Failed to bind: {e2}")
                raise
        
        self.socket.settimeout(0.1)  # Non-blocking with short timeout
        
        self.running = True
        print(f"UDP Server started on {self.server_ip}:{self.port}")
        print(f"Will communicate with client at {self.client_ip}:{self.port}")
        
        # Start receiving thread
        self.receive_thread = threading.Thread(target=self._receive_messages)
        self.receive_thread.daemon = True
        self.receive_thread.start()
        
        # Send initial ping to client
        self.send_message('ping', {'server_ready': True})
        
    def send_message(self, message_type, data=None):
        """Send a UDP message to the client"""
        if not self.socket:
            return False
            
        message = {
            'type': message_type,
            'timestamp': time.time(),
            'data': data
        }
        
        try:
            message_json = json.dumps(message)
            self.socket.sendto(message_json.encode('utf-8'), (self.client_ip, self.port))
            print(f"Sent {message_type} to {self.client_ip}:{self.port}")
            return True
        except Exception as e:
            print(f"Error sending message: {e}")
            return False
            
    def _receive_messages(self):
        """Receive UDP messages from client (runs in separate thread)"""
        while self.running:
            try:
                data, addr = self.socket.recvfrom(4096)
                message = json.loads(data.decode('utf-8'))
                message['sender_addr'] = addr
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
        start_time = time.time()
        while time.time() - start_time < timeout:
            message = self.get_message(timeout=0.1)
            if message and message.get('type') == expected_type:
                return message
        return None
        
    def close(self):
        """Close the server"""
        self.running = False
        if self.receive_thread:
            self.receive_thread.join(timeout=1)
        if self.socket:
            self.socket.close()

# Main experiment code
def run_experiment():
    """Run the server-side experiment on Computer A"""
    
    # Get participant info
    exp_info = {
        'participant_A_id': '',
        'session': '001',
        'server_ip': '100.1.1.10',
        'client_ip': '100.1.1.11'
    }
    
    dlg = gui.DlgFromDict(dictionary=exp_info, 
                          title='Dyadic Study - Computer A (Server)',
                          order=['participant_A_id', 'session'])
    if not dlg.OK:
        core.quit()
    
    # Initialize UDP server
    server = DyadUDPServer(
        server_ip=exp_info['server_ip'],
        client_ip=exp_info['client_ip'],
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
        text="Starting UDP server...",
        height=0.05)
    
    trial_text = visual.TextStim(win,
        text="",
        height=0.1)
    
    sync_dot = visual.Circle(win,
        radius=0.05,
        fillColor='green',
        pos=(0.4, 0.4))
    
    status_text = visual.TextStim(win,
        text="",
        height=0.03,
        pos=(0, -0.4))
    
    # Start server
    instructions.draw()
    win.flip()
    server.start_server()
    
    # Wait for client ping response
    instructions.text = "Waiting for Computer B to connect..."
    instructions.draw()
    win.flip()
    
    # Send pings repeatedly until we get a response
    client_ready = False
    timeout_clock = core.Clock()
    last_ping = 0
    
    while not client_ready and timeout_clock.getTime() < 60:
        # Send ping every second
        if time.time() - last_ping > 1.0:
            server.send_message('ping', {'server_ready': True})
            last_ping = time.time()
        
        instructions.text = f"Waiting for Computer B... ({60 - int(timeout_clock.getTime())}s)\nSending pings to {exp_info['client_ip']}"
        instructions.draw()
        win.flip()
        
        # Check for client messages
        message = server.get_message(timeout=0.1)
        if message and message.get('type') == 'pong':
            client_ready = True
    
    if not client_ready:
        instructions.text = "Connection timeout. Please check network settings."
        instructions.draw()
        win.flip()
        core.wait(3)
        server.close()
        win.close()
        core.quit()
    
    # Connection established
    instructions.text = "Computer B connected! Press SPACE to start experiment"
    instructions.draw()
    win.flip()
    
    # Wait for experimenter to start
    event.waitKeys(keyList=['space'])
    
    # Send start signal
    server.send_message('start_experiment', {
        'n_trials': 10,
        'sync_time': time.time()
    })
    
    # Wait for acknowledgment
    ack = server.wait_for_response('ack_start', timeout=3)
    if not ack:
        print("Warning: No acknowledgment from client")
    
    # Run trials
    n_trials = 10
    trial_clock = core.Clock()
    data_log = []
    
    for trial_num in range(n_trials):
        # Send trial sync signal
        trial_sync_time = time.time()
        trial_data = {
            'trial_number': trial_num + 1,
            'sync_timestamp': trial_sync_time
        }
        server.send_message('trial_sync', trial_data)
        
        # Wait for client sync acknowledgment
        sync_ack = server.wait_for_response('sync_ack', timeout=1)
        
        # Reset trial clock after sync
        trial_clock.reset()
        
        # Display trial
        trial_text.text = f"Trial {trial_num + 1}"
        trial_text.draw()
        sync_dot.draw()
        
        # Show sync status
        if sync_ack:
            latency = (sync_ack['timestamp'] - trial_sync_time) * 1000
            status_text.text = f"Sync OK (latency: {latency:.1f}ms)"
        else:
            status_text.text = "Sync warning"
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
                break
                
            # Send response to client
            server.send_message('server_response', {
                'response': response,
                'rt': rt
            })
        
        # Wait for client response
        client_resp = server.wait_for_response('client_response', timeout=3)
        
        # Log trial data
        trial_log = {
            'trial': trial_num + 1,
            'sync_time': trial_sync_time,
            'server_response': response,
            'server_rt': rt,
            'client_response': client_resp['data']['response'] if client_resp else None,
            'client_rt': client_resp['data']['rt'] if client_resp else None,
            'sync_latency': latency if sync_ack else None
        }
        data_log.append(trial_log)
        
        # Brief ITI
        win.flip()
        core.wait(0.5)
    
    # End experiment
    server.send_message('end_experiment')
    
    # Save data
    import pandas as pd
    df = pd.DataFrame(data_log)
    filename = f'dyad_computerA_{exp_info["participant_A_id"]}_{time.strftime("%Y%m%d_%H%M%S")}.csv'
    df.to_csv(filename, index=False)
    
    # Goodbye message
    instructions.text = f"Experiment complete!\nData saved to {filename}"
    instructions.draw()
    win.flip()
    core.wait(3)
    
    # Cleanup
    server.close()
    win.close()
    core.quit()

if __name__ == '__main__':
    run_experiment()
