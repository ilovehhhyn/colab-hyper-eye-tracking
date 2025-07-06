from psychopy import visual, core, event, gui
import random
import numpy as np
import os
import json
import csv
from datetime import datetime

# Game settings
GRID_SIZE = 8
TOTAL_ROUNDS = 20
EASY_ROUNDS = 10
MEDIUM_ROUNDS = 10
DISPLAY_TIME = 5.0

# Category mapping
CATEGORY_MAP = {
    0: 'face',
    1: 'limb',
    2: 'house',
    3: 'car'
}

# Image categories for key mapping
CATEGORIES = {
    'h': 'house',
    'c': 'car', 
    'f': 'face',
    'l': 'limb'
}

class MemoryGame:
    def __init__(self):
        # Create window
        self.win = visual.Window(
            size=[1024, 768],
            fullscr=False,
            color='black',
            units='pix'
        )
        
        # Load conditions from JSON
        self.conditions = self._load_conditions()
        
        # Load all images from stimuli folder
        self.images = self._load_all_images()
        
        # Create gray covers
        self.gray_cover = visual.Rect(self.win, width=80, height=80, fillColor='gray')
        
        # Create question mark
        self.question_mark = visual.TextStim(
            self.win, 
            text='??', 
            color='white', 
            height=30,
            bold=True
        )
        
        # Instructions text
        self.instructions = visual.TextStim(
            self.win,
            text="Memory Game\n\nRemember the images in the grid.\nAfter 5 seconds, recall what's under the ?? marker.\n\nPress:\nH for House\nC for Car\nF for Face\nL for Limb\n\nPress SPACE to start",
            color='white',
            height=30,
            wrapWidth=800
        )
        
        # Score tracking
        self.score = 0
        self.current_round = 0
        
        # Data collection
        self.trial_data = []
        
        # Calculate grid positions
        self.grid_positions = self._calculate_grid_positions()
        
        # Create trial list (randomized order of difficulties)
        self.trials = (['easy'] * EASY_ROUNDS + ['medium'] * MEDIUM_ROUNDS)
        random.shuffle(self.trials)
    
    def _load_conditions(self):
        """Load conditions from conditions.json"""
        try:
            with open('conditions.json', 'r') as f:
                data = json.load(f)
                return data['top_layouts_array_fixed_4']
        except FileNotFoundError:
            print("conditions.json not found. Using default conditions.")
            # Default conditions if file not found
            return [
                [2, 0, 1, 3],
                [3, 2, 0, 1],
                [1, 3, 2, 0],
                [0, 1, 3, 2],
                [3, 1, 2, 0]
            ]
        except Exception as e:
            print(f"Error loading conditions: {e}")
            return [[2, 0, 1, 3]]  # Fallback
    
    def _load_all_images(self):
        """Load all images from stimuli folder"""
        images = {
            'face': [],
            'limb': [],
            'house': [],
            'car': []
        }
        
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
                            img = visual.ImageStim(self.win, image=image_path)
                            images[category_key].append(img)
                        except Exception as e:
                            print(f"Error loading {image_path}: {e}")
            
            # If no images loaded for this category, create colored rectangles
            if not images[category_key]:
                print(f"No images found for {category_key}. Using colored rectangles.")
                colors = {'face': 'yellow', 'limb': 'green', 'house': 'blue', 'car': 'red'}
                for i in range(10):
                    rect = visual.Rect(self.win, width=80, height=80, fillColor=colors[category_key])
                    images[category_key].append(rect)
        
        return images
    
    def _calculate_grid_positions(self):
        """Calculate pixel positions for 8x8 grid"""
        positions = []
        start_x = -280  # Start position for grid
        start_y = 280
        spacing = 80    # Space between grid items
        
        for row in range(GRID_SIZE):
            for col in range(GRID_SIZE):
                x = start_x + col * spacing
                y = start_y - row * spacing
                positions.append((x, y))
        
        return positions
    
    def _create_grid_from_condition(self, condition, difficulty):
        """Create grid from condition array"""
        # condition is a 4-element array representing 2x2 pattern
        # Convert numbers to categories
        condition_categories = [CATEGORY_MAP[num] for num in condition]
        
        # Create grid based on difficulty
        grid_images = []
        grid_image_indices = []  # Track which specific image was used
        
        if difficulty == 'easy':
            # Each position in 2x2 becomes a 4x4 block
            for small_row in range(2):
                for small_col in range(2):
                    category = condition_categories[small_row * 2 + small_col]
                    # Randomly select one image from this category
                    selected_image_idx = random.randint(0, len(self.images[category]) - 1)
                    
                    # Fill 4x4 block with this image
                    for block_row in range(4):
                        for block_col in range(4):
                            grid_images.append(self.images[category][selected_image_idx])
                            grid_image_indices.append((category, selected_image_idx))
        
        else:  # medium
            # Each position in 2x2 becomes a 2x2 block
            # But we need to fill 8x8, so we need 4x4 pattern
            # Repeat the 2x2 pattern to make 4x4
            expanded_condition = []
            for row in range(4):
                for col in range(4):
                    original_idx = (row // 2) * 2 + (col // 2)
                    expanded_condition.append(condition[original_idx])
            
            # Convert to categories
            expanded_categories = [CATEGORY_MAP[num] for num in expanded_condition]
            
            # Now each position becomes a 2x2 block
            for small_row in range(4):
                for small_col in range(4):
                    category = expanded_categories[small_row * 4 + small_col]
                    # Randomly select one image from this category
                    selected_image_idx = random.randint(0, len(self.images[category]) - 1)
                    
                    # Fill 2x2 block with this image
                    for block_row in range(2):
                        for block_col in range(2):
                            grid_images.append(self.images[category][selected_image_idx])
                            grid_image_indices.append((category, selected_image_idx))
        
        return grid_images, grid_image_indices
    
    def _display_grid(self, grid_images):
        """Display the image grid"""
        for i, img in enumerate(grid_images):
            x, y = self.grid_positions[i]
            img.pos = (x, y)
            img.size = (70, 70)  # Slightly smaller than cover
            img.draw()
    
    def _display_covers(self, target_index):
        """Display gray covers over all positions, with ?? over target"""
        for i in range(64):
            x, y = self.grid_positions[i]
            self.gray_cover.pos = (x, y)
            self.gray_cover.draw()
            
            # Draw question mark over target position
            if i == target_index:
                self.question_mark.pos = (x, y - 50)  # Position above the square
                self.question_mark.draw()
    
    def _get_user_response(self):
        """Get user response (no time limit)"""
        response_timer = core.Clock()
        
        while True:
            keys = event.getKeys(keyList=['h', 'c', 'f', 'l', 'escape'])
            if keys:
                if keys[0] == 'escape':
                    core.quit()
                return keys[0], response_timer.getTime()
            core.wait(0.01)
    
    def run_trial(self, difficulty):
        """Run a single trial"""
        # Select random condition
        condition = random.choice(self.conditions)
        
        # Create grid from condition
        grid_images, grid_image_indices = self._create_grid_from_condition(condition, difficulty)
        
        # Choose random target position
        target_index = random.randint(0, 63)
        target_category, target_image_idx = grid_image_indices[target_index]
        
        # Find correct key for target category
        correct_key = None
        for key, category in CATEGORIES.items():
            if category == target_category:
                correct_key = key
                break
        
        # Display images for 5 seconds
        self.win.clearBuffer()
        self._display_grid(grid_images)
        self.win.flip()
        core.wait(DISPLAY_TIME)
        
        # Display covers with question mark
        self.win.clearBuffer()
        self._display_covers(target_index)
        
        # Add instruction text
        instruction_text = visual.TextStim(
            self.win,
            text="What was under the ?? marker?\nH=House, C=Car, F=Face, L=Limb",
            pos=(0, -350),
            color='white',
            height=20
        )
        instruction_text.draw()
        self.win.flip()
        
        # Get response and measure time
        user_response, response_time = self._get_user_response()
        
        # Check if correct
        correct = user_response == correct_key
        if correct:
            self.score += 1
            feedback = "Correct! +1 point"
            feedback_color = 'green'
        else:
            feedback = f"Incorrect. Answer was {correct_key.upper()}"
            feedback_color = 'red'
        
        # Record trial data
        trial_record = {
            'trial': self.current_round,
            'difficulty': difficulty,
            'condition': condition,
            'target_category': target_category,
            'target_image_index': target_image_idx,
            'target_position': target_index,
            'correct_key': correct_key,
            'user_response': user_response,
            'response_time': response_time,
            'correct': correct,
            'timestamp': datetime.now().isoformat()
        }
        self.trial_data.append(trial_record)
        
        # Show feedback
        feedback_text = visual.TextStim(
            self.win,
            text=feedback,
            color=feedback_color,
            height=30
        )
        
        self.win.clearBuffer()
        feedback_text.draw()
        self.win.flip()
        core.wait(1.5)
        
        return correct
    
    def _save_data(self):
        """Save trial data to CSV file"""
        if not self.trial_data:
            return
        
        # Create filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"memory_game_data_{timestamp}.csv"
        
        # Define CSV columns
        fieldnames = [
            'trial', 'difficulty', 'condition', 'target_category', 
            'target_image_index', 'target_position', 'correct_key', 
            'user_response', 'response_time', 'correct', 'timestamp'
        ]
        
        try:
            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(self.trial_data)
            
            print(f"Data saved to {filename}")
            
        except Exception as e:
            print(f"Error saving data: {e}")
    
    def show_instructions(self):
        """Show game instructions"""
        self.win.clearBuffer()
        self.instructions.draw()
        self.win.flip()
        
        # Wait for spacebar
        event.waitKeys(keyList=['space'])
    
    def show_final_score(self):
        """Show final score"""
        score_text = visual.TextStim(
            self.win,
            text=f"Game Complete!\n\nFinal Score: {self.score}/{TOTAL_ROUNDS}\nAccuracy: {(self.score/TOTAL_ROUNDS)*100:.1f}%\n\nData has been saved to CSV file.\n\nPress SPACE to exit",
            color='white',
            height=40,
            wrapWidth=600
        )
        
        self.win.clearBuffer()
        score_text.draw()
        self.win.flip()
        
        event.waitKeys(keyList=['space'])
    
    def run_game(self):
        """Run the complete game"""
        try:
            # Show instructions
            self.show_instructions()
            
            # Run all trials
            for round_num in range(TOTAL_ROUNDS):
                self.current_round = round_num + 1
                difficulty = self.trials[round_num]
                
                # Show round info
                round_text = visual.TextStim(
                    self.win,
                    text=f"Round {self.current_round}/{TOTAL_ROUNDS}\nDifficulty: {difficulty.upper()}\n\nPress SPACE when ready",
                    color='white',
                    height=30
                )
                
                self.win.clearBuffer()
                round_text.draw()
                self.win.flip()
                event.waitKeys(keyList=['space'])
                
                # Run trial
                self.run_trial(difficulty)
                
                # Brief pause between trials
                core.wait(0.5)
            
            # Save data
            self._save_data()
            
            # Show final score
            self.show_final_score()
            
        except Exception as e:
            print(f"Error during game: {e}")
            # Try to save data even if there's an error
            self._save_data()
        finally:
            self.win.close()
            core.quit()

# Run the game
if __name__ == "__main__":
    # Create and run game
    game = MemoryGame()
    game.run_game()
