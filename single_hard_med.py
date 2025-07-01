from psychopy import visual, core, event, gui
import random
import numpy as np
import os

# Game settings
GRID_SIZE = 8
TOTAL_ROUNDS = 20
HARD_ROUNDS = 10
MEDIUM_ROUNDS = 10
DISPLAY_TIME = 5.0
RESPONSE_TIME = 5.0

# Image categories
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
        
        # Load images (you'll need to place these in the same directory)
        self.images = {}
        try:
            self.images['house'] = visual.ImageStim(self.win, image='house.jpeg')
            self.images['car'] = visual.ImageStim(self.win, image='car.jpeg')
            self.images['face'] = visual.ImageStim(self.win, image='face.jpeg')
            self.images['limb'] = visual.ImageStim(self.win, image='limb.jpeg')
        except:
            # If images not found, create colored rectangles as placeholders
            print("Image files not found. Using colored rectangles as placeholders.")
            self.images['house'] = visual.Rect(self.win, width=80, height=80, fillColor='blue')
            self.images['car'] = visual.Rect(self.win, width=80, height=80, fillColor='red')
            self.images['face'] = visual.Rect(self.win, width=80, height=80, fillColor='yellow')
            self.images['limb'] = visual.Rect(self.win, width=80, height=80, fillColor='green')
        
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
        
        # Calculate grid positions
        self.grid_positions = self._calculate_grid_positions()
        
        # Create trial list (randomized order of difficulties)
        self.trials = (['hard'] * HARD_ROUNDS + ['medium'] * MEDIUM_ROUNDS)
        random.shuffle(self.trials)
    
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
    
    def _create_hard_grid(self):
        """Create hard difficulty grid - random distribution"""
        # Create list with 16 of each image type
        grid_images = []
        for category in CATEGORIES.values():
            grid_images.extend([category] * 16)
        
        # Shuffle randomly
        random.shuffle(grid_images)
        return grid_images
    
    def _create_medium_grid(self):
        """Create medium difficulty grid - 2x2 blocks of same image"""
        grid_images = [''] * 64
        
        # Create 4x4 pattern where each 2x2 block has same image
        categories_list = list(CATEGORIES.values())
        
        # Assign categories to 4x4 grid
        small_grid = []
        for i in range(16):
            small_grid.append(categories_list[i % 4])
        random.shuffle(small_grid)
        
        # Expand 4x4 to 8x8 where each cell becomes a 2x2 block
        for small_row in range(4):
            for small_col in range(4):
                category = small_grid[small_row * 4 + small_col]
                
                # Fill corresponding 2x2 block in 8x8 grid
                for block_row in range(2):
                    for block_col in range(2):
                        big_row = small_row * 2 + block_row
                        big_col = small_col * 2 + block_col
                        grid_images[big_row * 8 + big_col] = category
        
        return grid_images
    
    def _display_grid(self, grid_images):
        """Display the image grid"""
        for i, category in enumerate(grid_images):
            x, y = self.grid_positions[i]
            img = self.images[category]
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
        """Get user response within time limit"""
        response_timer = core.Clock()
        keys = []
        
        while response_timer.getTime() < RESPONSE_TIME:
            keys = event.getKeys(keyList=['h', 'c', 'f', 'l', 'escape'])
            if keys:
                if keys[0] == 'escape':
                    core.quit()
                return keys[0]
            core.wait(0.01)
        
        return None  # No response within time limit
    
    def run_trial(self, difficulty):
        """Run a single trial"""
        # Create grid based on difficulty
        if difficulty == 'hard':
            grid_images = self._create_hard_grid()
        else:
            grid_images = self._create_medium_grid()
        
        # Choose random target position
        target_index = random.randint(0, 63)
        target_category = grid_images[target_index]
        
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
        
        # Get response
        user_response = self._get_user_response()
        
        # Check if correct
        if user_response == correct_key:
            self.score += 1
            feedback = "Correct! +1 point"
            feedback_color = 'green'
        elif user_response is None:
            feedback = "Time's up! No response"
            feedback_color = 'red'
        else:
            feedback = f"Incorrect. Answer was {correct_key.upper()}"
            feedback_color = 'red'
        
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
        
        return user_response == correct_key
    
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
            text=f"Game Complete!\n\nFinal Score: {self.score}/{TOTAL_ROUNDS}\nAccuracy: {(self.score/TOTAL_ROUNDS)*100:.1f}%\n\nPress SPACE to exit",
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
            
            # Show final score
            self.show_final_score()
            
        except Exception as e:
            print(f"Error during game: {e}")
        finally:
            self.win.close()
            core.quit()

# Run the game
if __name__ == "__main__":
    # Create and run game
    game = MemoryGame()
    game.run_game()
