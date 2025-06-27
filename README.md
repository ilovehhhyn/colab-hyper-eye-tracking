# Dual-Computer Eye Gaze Sharing System with Memory Game

This system enables real-time eye gaze data sharing between two computers while participants complete a collaborative memory game. Each computer tracks its user's eye movements and displays both local and remote gaze patterns simultaneously. 

## Overview

The system consists of two symmetric programs (Computer A and Computer B) that:
- Track eye gaze using EyeLink eye trackers
- Share gaze data over UDP network connection
- Run synchronized memory game trials
- Display real-time gaze visualization from both participants

## System Requirements

### Hardware
- 2 computers with EyeLink-compatible eye trackers
- Network connection between computers (Ethernet recommended)
- EyeLink Host PC (IP: 100.1.1.1)

### Software Dependencies
```bash
pip install psychopy pylink numpy pillow
```

### Required Libraries
- `pylink` - EyeLink SDK
- `psychopy` - Stimulus presentation and window management
- `numpy` - Numerical computations
- `socket`, `threading`, `json` - Network communication
- `PIL` - Image processing

## Network Configuration

### IP Addresses
- **Computer A**: 100.1.1.10
- **Computer B**: 100.1.1.11
- **EyeLink Host**: 100.1.1.1
- ##IMPORTANT NOTE: the firewall between the two computers must be turned off, at least for each other. 

### Ports
- **Gaze Data Reception**: 8888 (A), 8889 (B)
- **Gaze Data Transmission**: 8889 (A→B), 8888 (B→A)
- ##IMPORTANT NOTE: the two ports are UDP, not TCP. This is incorporated into the code but just in case the firewall config needs this info. 

### Screen Size 
- Click into Monitor Center in Psychopy software on each computer to make sure that the size of the screen is what EyeLink thinks it is (in calibration)
- If on C19 and C21, and if nothing changed since June 2025, 
Resolution: 2560 x 1440
Width: 59.5
Distance: 89.5

## File Structure


```
project_directory/
├── computer_a_gaze_sharing.py    # Computer A program
├── computer_b_gaze_sharing.py    # Computer B program
├── images/
│   └── fixTarget.bmp            # Custom fixation target
└── results/
    └── [session_folders]/       # Auto-generated result folders
```

## Memory Game Description

### Game Mechanics
- **Grid**: 6×6 grid of colored categories
- **Categories**: 
  - F (Face) - Orange 
  - L (Limbs) - Green  
  - H (House) - Purple
  - C (Car) - Yellow
  - the colors are meaningful only when there's no custom images; if there are custum images, colors won't appear
- **Trials**: 5 trials per session (can be configured)

### Trial Structure
1. **Study Phase** (10 seconds): View complete grid
2. **Recall Phase**: Identify category at marked position
3. **Feedback Phase** (2 seconds): Show correct answer
4. **Break**: Brief pause between trials; need to press SPACE to proceed

### Controls
- **F**: Face category
- **L**: Limbs category  
- **H**: House category
- **C**: Car category
- **SPACE**: Recalibrate eye tracker
- **ESCAPE**: Exit program

## Visual Elements

### Gaze Markers
- **Computer A**: Blue circles with sparkle effects
- **Computer B**: Green circles with sparkle effects
- **Remote Gaze**: Displayed when connection active

### UI Components
- Status bar with connection info and trial progress
- Legend explaining color coding
- Corner decorations for visual appeal
- Real-time network statistics

## Usage Instructions

### 1. Setup
```bash
# Ensure both computers are connected to network
# Verify EyeLink Host PC is accessible at 100.1.1.1
# Run programs simultaneously on both computers
```

### 2. Launch Computer A
```bash
python computer_a_gaze_sharing.py
```
- Enter EDF filename (8 characters max)
- Complete eye tracker calibration
- Wait for Computer B to connect

### 3. Launch Computer B  
```bash
python computer_b_gaze_sharing.py
```
- Enter EDF filename (8 characters max)
- Complete eye tracker calibration
- Programs will automatically sync

### 4. Session Flow
1. **Instructions**: Read startup instructions
2. **Calibration**: Complete eye tracker setup (press ESC twice to quit calibration) 
3. **Memory Game**: Complete 5 trials
4. **Free Sharing**: Continue with open gaze sharing
5. **Exit**: Press ESCAPE to end session

## Data Output

### Files Generated
```
results/[SESSION_ID]/
├── [SESSION_ID].EDF              # EyeLink data file
├── [SESSION_ID]_memory_results.txt # Game performance data
```

### Memory Results Format
```
Trial   Position  Target  Response  Correct  RT
1       15        H       H         True     1.234
2       28        F       L         False    2.156
...
```

### EDF File Contents
- Raw eye tracking data
- Gaze coordinates and timestamps
- Trial markers and events
- Network synchronization messages

## Network Protocol

### Data Packet Structure
```json
{
    "x": 512.34,           # Gaze X coordinate
    "y": 384.67,           # Gaze Y coordinate  
    "valid": true,         # Data validity flag
    "timestamp": 1234567.89, # Unix timestamp
    "computer": "A"        # Source identifier
}
```

### Communication Flow
1. Both programs establish UDP sockets
2. Continuous bidirectional data exchange
3. Real-time gaze coordinate sharing
4. Network error handling and statistics

## Troubleshooting

### Common Issues

**Network Connection Problems**
```bash
# Check IP configuration
ipconfig  # Windows
ifconfig  # Linux/Mac

# Test connectivity
ping 100.1.1.10  # From Computer B
ping 100.1.1.11  # From Computer A
```

**EyeLink Connection Issues**
- Verify EyeLink Host PC is running
- Check network cable connections
- Restart EyeLink Host software if needed
- Use dummy mode for testing: `dummy_mode = True`

**Calibration Problems**
- Ensure proper lighting conditions
- Check participant eye visibility
- Recalibrate using SPACE key during session
- Verify camera positioning

### Error Messages

**"Network setup failed"**
- Check IP addresses in configuration
- Verify no firewall blocking ports 8888/8889
- Ensure no other programs using same ports

**"Could not establish eye tracking"**  
- Programs will switch to dummy mode automatically
- Check EyeLink Host PC connectivity
- Verify EyeLink software is running

**"Data file download error"**
- Check disk space on local computer
- Verify EDF filename is valid (8 chars max)
- Ensure results folder has write permissions

## Configuration Options

### Modifiable Parameters
```python
# Network settings
LOCAL_IP = "100.1.1.10"    # Change for different network
REMOTE_IP = "100.1.1.11"   # Change for different network

# Game settings  
total_trials = 5           # Number of memory trials
grid_size = 6             # Grid dimensions (6x6)

# Display settings
full_screen = True        # Fullscreen vs windowed
use_retina = False        # macOS Retina display support
dummy_mode = False        # Simulation mode for testing
```
- colors, radii of gaze dot is modifiable; so are the decorative_elements.

### Performance Tuning
```python
# Network refresh rate
core.wait(0.008)          # ~120Hz gaze sharing

# Socket timeout
receive_socket.settimeout(0.001)  # 1ms timeout

# Sample rate
"sample_rate 1000"        # 1000Hz eye tracking
```

## Technical Details

### Coordinate System Conversion
```python
# EyeLink to PsychoPy coordinate transformation
gaze_x = (scn_width/2 + 200 - eyelink_x) 
gaze_y = (eyelink_y - scn_height/2 - 800)
```

### Threading Architecture
- **Main Thread**: Display rendering and user interaction
- **Network Thread**: Continuous gaze data reception
- **Shared Variables**: Thread-safe data exchange

### Error Handling
- Automatic fallback to dummy mode
- Network error counting and reporting
- Graceful session termination
- Data backup and recovery

### Data Analysis Considerations
- Synchronize timestamps between computers
- Account for network latency (~1-10ms)
- Validate gaze data quality metrics
- Cross-reference with behavioral data

## Support and Maintenance

### Log Information
- Network statistics (sent/received/errors)
- Gaze validity percentages  
- Session duration and trial performance
- Automatic error logging

### Version Compatibility
- Tested with Python 3.7+
- PsychoPy 3.0+
- EyeLink 1000+ systems
- Windows/Linux/macOS support

## License and Citation

Please cite this software in research publications and ensure compliance with EyeLink SDK licensing requirements.

---

**For technical support or questions, consult the EyeLink documentation or contact your system administrator.**
