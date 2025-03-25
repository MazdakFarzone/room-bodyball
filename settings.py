import os
from enum import Enum

class Team(Enum):
    TEAM1 = 1
    TEAM2 = 2

class PINS:
    """ All pins """
    p1 = 4
    p2 = 17
    p3 = 27
    p4 = 23
    p5 = 24
    p6 = 25

    photocells_list = [{'pin': p1, 'team': Team.TEAM1}, {'pin': p2, 'team': Team.TEAM1}, {'pin': p3, 'team': Team.TEAM1},
                       {'pin': p4, 'team': Team.TEAM2}, {'pin': p5, 'team': Team.TEAM2}, {'pin': p6, 'team': Team.TEAM2}]

class Audio:
    path = f"{os.path.dirname(os.path.realpath(__file__))}{os.path.sep}extras"
    ready_go = "readygo-loud3.wav"
    team1_score = "team1.wav"
    team2_score = "team2.wav"
    sudden_death = "sudden_death.wav"
    team1_won = "team1_won_finish.mp3"
    team2_won = "team2_won_finish.mp3"

class GameSettings:
    debug_mode = False
    game_time = 300