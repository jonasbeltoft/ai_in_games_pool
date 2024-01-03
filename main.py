import pygame
import pymunk
import pymunk.pygame_util
import math
import numpy as np
from collections import defaultdict

# common
TITLE = "Pool Game"
SCREEN_WIDTH = 1200
SCREEN_HEIGHT = 678
BOTTOM_PANEL = 50
BACKGROUND_COLOR = (50, 50, 50)
TEXT_COLOR = (255, 255, 255)

# ball data
MAX_BALL = 17
BALL_MASS = 5
BALL_ELASTICITY = 0.8
BALL_DIAMETER = 36

# wall data
FRICTION = 1000
CUSHION_ELASTICITY = 0.6
POCKET_DIAMETER = 70

# shooting data
MAX_FORCE = 10000
FORCE_STEP = 100

# power bar
BAR_WIDTH = 10
BAR_HEIGHT = 20
BAR_SENSTIVITY = 1000
BAR_COLOR = (255, 0, 0)

# create six pockets on table
POCKETS = [(55, 63), (592, 48), (1134, 64), (55, 616), (592, 629), (1134, 616)]

# create pool table cushions
CUSHIONS = [
    [(88, 56), (109, 77), (555, 77), (564, 56)],
    [(621, 56), (630, 77), (1081, 77), (1102, 56)],
    [(89, 621), (110, 600), (556, 600), (564, 621)],
    [(622, 621), (630, 600), (1081, 600), (1102, 621)],
    [(56, 96), (77, 117), (77, 560), (56, 581)],
    [(1143, 96), (1122, 117), (1122, 560), (1143, 581)],
]

# initilize the modules
pygame.init()

# fonts
font = pygame.font.SysFont("Lato", 30)
large_font = pygame.font.SysFont("Lato", 60)

# clock
FPS = 120
clock = pygame.time.Clock()

# game window
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT + BOTTOM_PANEL))
pygame.display.set_caption(TITLE)

# pymunk space
space = pymunk.Space()
static_body = space.static_body
draw_options = pymunk.pygame_util.DrawOptions(screen)

# game variables
lives = 3
force = 0
force_direction = 1
game_running = True
cue_ball_potted = False
taking_shot = True
powering_up = False
potted_balls = []

# load images
cue_image = pygame.image.load("assets/images/cue.png").convert_alpha()
table_image = pygame.image.load("assets/images/table.png").convert_alpha()
ball_images = []
for i in range(1, MAX_BALL):
    ball_image = pygame.image.load(f"assets/images/ball_{i}.png").convert_alpha()
    ball_images.append(ball_image)


# function for outputting text onto the screen
def draw_text(text, font, text_col, x, y):
    screen.blit(font.render(text, True, text_col), (x, y))


# function for creating balls
def create_ball(radius, pos):
    body = pymunk.Body()
    body.position = pos
    shape = pymunk.Circle(body, radius)
    shape.mass = BALL_MASS
    shape.elasticity = BALL_ELASTICITY
    # use pivot joint to add friction
    pivot = pymunk.PivotJoint(static_body, body, (0, 0), (0, 0))
    pivot.max_bias = 0  # disable joint correction
    pivot.max_force = FRICTION  # emulate linear friction
    space.add(body, shape, pivot)
    return shape


# setup game balls
balls = []
rows = 5

# potting balls
for col in range(5):
    for row in range(rows):
        balls.append(
            create_ball(
                BALL_DIAMETER / 2,
                (
                    250 + col * (BALL_DIAMETER + 1),
                    267 + row * (BALL_DIAMETER + 1) + col * BALL_DIAMETER / 2,
                ),
            )
        )
    rows -= 1

# cue ball
pos = (888, SCREEN_HEIGHT / 2)
cue_ball = create_ball(BALL_DIAMETER / 2, pos)
balls.append(cue_ball)


# function for creating cushions
def create_cushion(poly_dims):
    body = pymunk.Body(body_type=pymunk.Body.STATIC)
    # body.position = (0, 0)
    shape = pymunk.Poly(body, poly_dims)
    shape.elasticity = CUSHION_ELASTICITY
    space.add(body, shape)


for cushion in CUSHIONS:
    create_cushion(cushion)


# create pool cue
class Cue:
    def __init__(self, pos):
        self.original_image = cue_image
        self.angle = 0
        self.image = pygame.transform.rotate(self.original_image, self.angle)
        self.rect = self.image.get_rect()
        self.rect.center = pos

    def update(self, angle):
        self.angle = math.degrees(angle)

    def draw(self, surface):
        self.image = pygame.transform.rotate(self.original_image, self.angle)
        surface.blit(
            self.image,
            (
                self.rect.centerx - self.image.get_width() / 2,
                self.rect.centery - self.image.get_height() / 2,
            ),
        )


cue = Cue(balls[-1].body.position)

# create power bars to show how hard the cue ball will be hit
power_bar = pygame.Surface((BAR_WIDTH, BAR_HEIGHT))
power_bar.fill(BAR_COLOR)


# MCTS AI CODE

def angle_between_points(point1, point2):
        return math.atan2(point2[1] - point1[1], point2[0] - point1[0])

def angle_difference(angle1, angle2):
    return abs((angle1 - angle2 + math.pi) % (2 * math.pi) - math.pi)

def can_reach_target(current_ball, target_ball, other_balls):
    
    a = current_ball.body.position[1] - target_ball.body.position[1]
    b = target_ball.body.position[0] - current_ball.body.position[0]
    c = (current_ball.body.position[0] - target_ball.body.position[0]) * current_ball.body.position[1] + (target_ball.body.position[1] - current_ball.body.position[1]) * current_ball.body.position[0]
    
    for ball in other_balls:
        if ball == target_ball:
            continue
        
        dist = ((abs(a * ball.body.position[0] + b * ball.body.position[1] + c)) / math.sqrt(a * a + b * b))
        
        if dist <= BALL_DIAMETER / 2:
            return False
    
    # Check if the target ball can reach at least one pocket
    target_angle = angle_between_points(current_ball.body.position, target_ball.body.position)
    for pocket in POCKETS:
        pocket_angle = angle_between_points(target_ball.body.position, pocket)
        if angle_difference(target_angle, pocket_angle) > math.pi / 2:
            continue

        a = target_ball.body.position[1] - pocket[1]
        b = pocket[0] - target_ball.body.position[0]
        c = (target_ball.body.position[0] - pocket[0]) * target_ball.body.position[1] + (pocket[1] - target_ball.body.position[1]) * target_ball.body.position[0]

        isClear = True
        for ball in other_balls:
            if ball == target_ball:
                continue
            
            dist = ((abs(a * ball.body.position[0] + b * ball.body.position[1] + c)) / math.sqrt(a * a + b * b))
            
            if dist <= BALL_DIAMETER / 2:
                isClear = False
                
        if isClear: return True
        
    return True

class MonteCarloTreeSearchNode():
    def __init__(self, state, parent=None, parent_action=None):
        self.state = state
        self.parent = parent
        self.parent_action = parent_action
        self.children = []
        self._number_of_visits = 0
        self._results = defaultdict(int)
        self._results[1] = 0
        self._results[-1] = 0
        self._untried_actions = None
        self._untried_actions = self.untried_actions()
        return
    
    def untried_actions(self):
        self._untried_actions = self.get_legal_actions()
        return self._untried_actions
    
    def q(self):
        wins = self._results[1]
        loses = self._results[-1]
        return wins - loses

    def n(self):
        return self._number_of_visits

    def expand(self):
	
        self._untried_actions.pop(0)
        next_state = self.move(0)
        child_node = MonteCarloTreeSearchNode(
            next_state, parent=self, parent_action=0)

        self.children.append(child_node)
        return child_node
    
    def is_terminal_node(self):
        return self.is_game_over()

    def rollout(self):
        current_rollout_state = self.state
        
        while not self.is_game_over(state = current_rollout_state):
            
            possible_moves = self.get_legal_actions(state = current_rollout_state)
            
            # If no balls can be hole'd then consider it a failed attempt
            if len(possible_moves) == 0:
                break
            
            action = self.rollout_policy(possible_moves)
            current_rollout_state = self.move(action, state = current_rollout_state)
        return self.game_result(state = current_rollout_state)
    
    def backpropagate(self, result):
        self._number_of_visits += 1.
        self._results[result] += 1.
        if self.parent:
            self.parent.backpropagate(result)
            
    def is_fully_expanded(self):
        return len(self._untried_actions) == 0

    def best_child(self, c_param=0.1):
        choices_weights = [(c.q() / c.n()) + c_param * np.sqrt((2 * np.log(self.n()) / c.n())) for c in self.children]
        return self.children[np.argmax(choices_weights)]
    
    def rollout_policy(self, possible_moves):
        # Chose the closest valid ball
        closest = 99999
        chosen = 0
        for i, ball in enumerate(possible_moves):
            dist = ball.body.position.get_distance(self.state[-1].body.position)
            if dist < closest:
                closest = dist
                chosen = i
                
        return chosen
    
    def _tree_policy(self):
        current_node = self
        while not current_node.is_terminal_node():
            
            if not current_node.is_fully_expanded():
                return current_node.expand()
            else:
                current_node = current_node.best_child()
        return current_node
    
    def best_action(self):
        simulation_no = 100
        
        for i in range(simulation_no):
            
            v = self._tree_policy()
            reward = v.rollout()
            v.backpropagate(reward)
        
        return self.best_child(c_param=0.)
    
    # Action is an index in the state list for the ball to shoot at
    # Since only the cue_ball can be shot from, we change it's body.position to the position of the chosen action
    
    def get_legal_actions(self, state = None): 
        '''
        Modify according to your game or
        needs. Constructs a list of all
        possible actions from current state.
        Returns a list.
        '''
        # This function should calculate and return each ball in state, that could be hole'd by 1 action
        # This will be the bulk of the actual computation
        if state == None:
            state = self.state
        
        current_ball = state[-1]
        actions = [target for target in state[:-1] if can_reach_target(current_ball, target, state[:-1])]
        if len(actions) == 0:
            return [state[0]]
        else:
            return actions
    
    def is_game_over(self, state = None):
        '''
        Modify according to your game or 
        needs. It is the game over condition
        and depends on your game. Returns
        true or false
        '''
        # Returns wether or not only the cue_ball is left
        # Lives have not been implemented in the logic (yet)
        if state == None:
            state = self.state
            
        return len(state) <= 1
        
    def game_result(self, state = None):
        '''
        Modify according to your game or 
        needs. Returns 1 or 0 or -1 depending
        on your state corresponding to win,
        tie or a loss.
        '''
        if state == None:
            state = self.state
            
        if len(state) > 1:
            return 0
        if len(state) == 1:
            return 1
        if len(state) < 1:
            return -1
        
    def move(self,action, state = None):
        '''
        Modify according to your game or 
        needs. Changes the state of your 
        board with a new value. For a normal
        Tic Tac Toe game, it can be a 3 by 3
        array with all the elements of array
        being 0 initially. 0 means the board 
        position is empty. If you place x in
        row 2 column 3, then it would be some 
        thing like board[2][3] = 1, where 1
        represents that x is placed. Returns 
        the new state after making a move.
        '''
        if state == None:
            state = self.state
        # Set the cue_ball position to the selected ball
        # This is wildly inaccurate, and could be improved by calculating approximate landing after rolling
        state[-1] = state[action]
        
        # Remove the selected ball. We assume it has been hole'd
        state.pop(action)
        
        return state
    
# END OF AI CODE

# game loop
game_on = True

while game_on:
    clock.tick(FPS)
    space.step(1 / FPS)

    # fill background
    screen.fill(BACKGROUND_COLOR)

    # draw pool table
    screen.blit(table_image, (0, 0))

    # check if any balls have been potted
    for i, ball in enumerate(balls):
        for pocket in POCKETS:
            if (
                math.sqrt(
                    (abs(ball.body.position[0] - pocket[0]) ** 2)
                    + (abs(ball.body.position[1] - pocket[1]) ** 2)
                )
                <= POCKET_DIAMETER / 2
            ):
                ball.body.position = (-444, -444)
                ball.body.velocity = (0.0, 0.0)
                # check if the potted ball was the cue ball
                if i == len(balls) - 1:
                    lives -= 1
                    cue_ball_potted = True
                else:
                    space.remove(ball.body)
                    balls.remove(ball)
                    potted_balls.append(ball_images[i])
                    ball_images.pop(i)

    # draw pool balls
    for i, ball in enumerate(balls):
        screen.blit(
            ball_images[i],
            (ball.body.position[0] - ball.radius, ball.body.position[1] - ball.radius),
        )

    taking_shot = True

    # check if all the balls have stopped moving
    for ball in balls:
        if int(ball.body.velocity[0]) != 0 or int(ball.body.velocity[1]) != 0:
            taking_shot = False

    # draw pool cue
    if taking_shot and game_running:
        if cue_ball_potted:
            # reposition cue ball
            balls[-1].body.position = (888, SCREEN_HEIGHT / 2)
            cue_ball_potted = False
        # calculate pool cue angle
        cue.rect.center = balls[-1].body.position
        # mouse_pos = pygame.mouse.get_pos()
        # cue_angle = math.degrees(
        #     math.atan2(
        #         -(balls[-1].body.position[1] - mouse_pos[1]),
        #         balls[-1].body.position[0] - mouse_pos[0],
        #     )
        # )
        
        # Calculate angle to shoot with AI
        
        root = MonteCarloTreeSearchNode(state = balls[:])
        selected_node = root.best_action()
        
        target = selected_node.state[-1]
        
        # Re-calculate which pocket to aim for
        valid_pockets = []
        target_angle = angle_between_points(balls[-1].body.position, target.body.position)
        for pocket in POCKETS:
            pocket_angle = angle_between_points(target.body.position, pocket)
            if angle_difference(target_angle, pocket_angle) > math.pi / 2:
                continue

            a = target.body.position[1] - pocket[1]
            b = pocket[0] - target.body.position[0]
            c = (target.body.position[0] - pocket[0]) * target.body.position[1] + (pocket[1] - target.body.position[1]) * target.body.position[0]

            isClear = True
            for ball in balls:
                if ball == target:
                    continue
                
                dist = ((abs(a * ball.body.position[0] + b * ball.body.position[1] + c)) / math.sqrt(a * a + b * b))
                
                if dist <= BALL_DIAMETER / 2:
                    isClear = False
                    
            if isClear: valid_pockets.append(pocket)
        
        closest = 99999
        chosen = 0
        for j, pocket in enumerate(valid_pockets):
            dist = pymunk.Vec2d(pocket[0], pocket[1]).get_distance(target.body.position)
            if dist < closest:
                closest = dist
                chosen = j
        
        target_pos = (target.body.position[0], target.body.position[1])
        if len(valid_pockets) != 0:
            chosen_pocket = valid_pockets[chosen]
            angle = angle_between_points(chosen_pocket, target_pos)
            x = (BALL_DIAMETER / 2) * math.cos(angle)
            y = (BALL_DIAMETER / 2) * math.sin(angle)
            
            target_pos = target_pos[0]+x, target_pos[1]+y
            
            
        print(valid_pockets)
        cue_angle = angle_between_points(balls[-1].body.position, target_pos)
        
        print(cue_angle)
        
        cue.update(cue_angle)
        cue.draw(screen)
        
        # Hardcoded to always shoot at 75% of max force
        balls[-1].body.apply_impulse_at_local_point(
            (
                MAX_FORCE * 0.75 * math.cos(cue_angle),
                MAX_FORCE * 0.75 * math.sin(cue_angle),
            ),
            (0, 0),
        )

    # power up pool cue
    # if powering_up and game_running:
    #     force += FORCE_STEP * force_direction
    #     if force >= MAX_FORCE or force <= 0:
    #         force_direction *= -1
    #     # draw power bars
    #     for adjustment in range(math.ceil(force / BAR_SENSTIVITY)):
    #         screen.blit(
    #             power_bar,
    #             (
    #                 balls[-1].body.position[0] - 70 + adjustment * 15,
    #                 balls[-1].body.position[1] + 30,
    #             ),
    #         )
    # elif not powering_up and taking_shot:
    #     balls[-1].body.apply_impulse_at_local_point(
    #         (
    #             force * -math.cos(math.radians(cue_angle)),
    #             force * math.sin(math.radians(cue_angle)),
    #         ),
    #         (0, 0),
    #     )
    #     force = 0
    #     force_direction = 1

    # draw bottom panel
    pygame.draw.rect(
        screen, BACKGROUND_COLOR, (0, SCREEN_HEIGHT, SCREEN_WIDTH, BOTTOM_PANEL)
    )

    # draw potted balls in bottom panel
    for i, ball in enumerate(potted_balls):
        screen.blit(ball, (10 + (i * 50), SCREEN_HEIGHT + 10))

    # draw lives
    draw_text(
        f"LIVES: {str(lives)}", font, TEXT_COLOR, SCREEN_WIDTH - 200, SCREEN_HEIGHT + 10
    )

    # check for game over
    if lives <= 0:
        draw_text(
            "GAME OVER",
            large_font,
            TEXT_COLOR,
            SCREEN_WIDTH / 2 - 160,
            SCREEN_HEIGHT / 2 - 100,
        )
        game_running = False

    # check if all balls are potted
    if len(balls) == 1:
        draw_text(
            "YOU WIN",
            large_font,
            TEXT_COLOR,
            SCREEN_WIDTH / 2 - 160,
            SCREEN_HEIGHT / 2 - 100,
        )
        game_running = False

    # event handler
    for event in pygame.event.get():
        if event.type == pygame.MOUSEBUTTONDOWN and taking_shot:
            powering_up = True
        if event.type == pygame.MOUSEBUTTONUP and taking_shot:
            powering_up = False
        if event.type == pygame.QUIT:
            game_on = False

    # space.debug_draw(draw_options)
    pygame.display.update()

pygame.quit()
