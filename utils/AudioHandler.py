from typing import Callable
from threading import Thread, Condition
from random import choice
from enum import Enum

import os
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"

# Hide prompt first then import mixer
from pygame import mixer

class AudioType(Enum):
    POSITIVE = 1
    NEGATIVE = 2
    MAX_REACHED = 3
    CLOSE_WIN = 4

class AudioHandler():
    """ Handles all the audio for the Game, you can change the different sounds/music and play too """
    __custom_sound = None
    __voice_thread = None
    __stop_condition = Condition()
    __stop_custom_condition = Condition()

    __music_paused = False

    __background_music_level: float = 1.0

    def __init__(self, root_path_to_audio: str):
        mixer.pre_init(44100, -16, 5, 2048*3)
        mixer.init()

        mixer.music.load(f"{root_path_to_audio}/music/bgsong_reduced.mp3")
        self.__losing = f"{root_path_to_audio}/effects/negative/loss.wav"
        self.__winning = f"{root_path_to_audio}/effects/positive/win.wav"

        self.__channel_logic = mixer.Channel(1)
        self.__channel_custom = mixer.Channel(2)
        self.__channel_voice = mixer.Channel(3)
        self.__channel_custom_now1 = mixer.Channel(4)
        self.__channel_custom_now2 = mixer.Channel(5)

        self.__channel_voice.set_volume(0.3)

        self.path_to_audio = root_path_to_audio
        self.__custom_sound_callback = None
        self.__custom_sound_thread = None

    def __del__(self):
        mixer.quit()
        self.stop_end_voice()
        self.stop_custom_sound()

    def play_custom_sound(self, music_sound_level=0.5):
        """ Play the custom sound you set using set_custom_sound, you can set the number of loops if you wish """
        if self.__custom_sound is not None:
            
            if self.__channel_custom.get_busy():
                self.stop_custom_sound()

            self.__custom_sound_thread = Thread(
                target=self.__custom_sound_event, args=(self.__stop_custom_condition, music_sound_level))
            self.__custom_sound_thread.start()
        else:
            raise Exception(
                "Custom sound not set, please use set_custom_sound first before playing!")
    
    def play_custom_sound_now(self, filename: str, directory: str, channel: int, volume=1.0) -> float:
        """Play a custom sound right now without the overhead, just play it!

        Args:
            filename (str): The file name with ending
            directory (str): An absolute directory path without the ending slash
            channel (int): 1 or 2 depending which one you want to play
        Returns:
            The audio clip length in seconds
        """
        if not (channel == 1 or channel == 2):
            print(f"Choose 1 or 2 for the channel! cannot play {filename}")
            return
        ch = self.__channel_custom_now1 if channel == 1 else self.__channel_custom_now2
        sound = mixer.Sound(f"{directory}/{filename}")
        ch.stop()
        ch.set_volume(volume)
        ch.play(sound)
        return sound.get_length()

    def set_custom_sound(self, filename: str, ended_callback: Callable[[None], None] = None, directory: str = None):
        """ Sets the custom sound, if a new one is set the old one will be stopped.
        
        If it's in another directory other than 'extras' then set the parameter
        """
        self.stop_custom_sound()

        if directory is not None:
            self.__custom_sound = mixer.Sound(f"{directory}/{filename}")
        else:
            self.__custom_sound = mixer.Sound(f"{self.path_to_audio}/effects/extras/{filename}")
        self.__custom_sound_callback = ended_callback

    def play_winning_sound(self, run_end_voice: bool = False, points: int = None, feedback_type: AudioType = AudioType.POSITIVE, intro_volume=1.0):
        """ Play the winning fanfare, you can run the optional end voice aftter the winning sound has been played! """
        if mixer.music.get_busy:
            mixer.music.fadeout(500)
        if not run_end_voice:
            sound = mixer.Sound(self.__winning)
            self.__channel_logic.set_volume(intro_volume)
            self.__channel_logic.play(sound)
        else:
            if points is None:
                raise Exception(
                    "If you want the end voice, you should specify the number of points as well!")
            self.stop_end_voice()
            self.__play_winning_ending(points, feedback_type == AudioType.MAX_REACHED)
    
    def change_winning_sound(self, filename: str, directory: str = None):
        """ Sets the new winning sound, if the new sound is located in another directory than the default one, you set the second parameter """
        self.__channel_logic.stop()

        if directory is not None:
            self.__winning = f"{directory}/{filename}"
        else:
            self.__winning = f"{self.path_to_audio}/{filename}"

    def play_losing_sound(self, run_end_voice: bool = True, close_call: bool = False, intro_volume=1.0):
        """ Play the losing trudelutt, it will give a motivational feedback if you were close to winning etc """
        if mixer.music.get_busy:
            mixer.music.fadeout(500)
        
        if not run_end_voice:
            sound = mixer.Sound(self.__losing)
            self.__channel_logic.set_volume(intro_volume)
            self.__channel_logic.play(sound)
        else:
            self.__play_losing_ending(close_call)

    def change_losing_sound(self, filename: str, directory=None):
        """ Change the losing trudelutt, a new directory can be specified if the sound is located somewhere else"""
        self.__channel_logic.stop()
        
        if directory is None:
            self.__losing = f"{self.path_to_audio}/{filename}"
        else:
            self.__losing = f"{directory}/{filename}"

    def play_background_music(self, restart=False, loops=-1):
        """ Starts playing the background music, if its running already it will restart"""
        if restart:
            mixer.music.stop()
            self.__music_paused = False
        if self.__music_paused:
            mixer.music.unpause()
            self.__music_paused = False
        else:
            mixer.music.play(loops=loops, fade_ms=200)

    def change_background_music_volume(self, level: float):
        """ The volume that the background music will play at, its a relative value, 1.0 being the normal """
        mixer.music.set_volume(level)
        self.__background_music_level = level

    def change_ending_volume(self, level: float):
        self.__channel_voice.set_volume(level)
    
    def change_custom_volume(self, level:float):
        self.__channel_custom.set_volume(level)

    def pause_background_music(self):
        mixer.music.pause()
        self.__music_paused = True

    def stop_background_music(self):
        """ Stop playing the background music, no fadeout here"""
        if mixer.music.get_busy() or self.__music_paused:
            mixer.music.stop()
            self.__music_paused = False
    
    def background_music_is_playing(self):
        return mixer.music.get_busy()
    
    def custom_sound_playing(self) -> bool:
        """Return if the default custom sound is playing

        Returns:
            bool: If its playing
        """
        return self.__channel_custom.get_busy()
    
    def custom_now_sound_playing(self, channel: int) -> bool:
        """Returns if the extra custom channels are currently playing or not

        Args:
            channel (int): 1 or 2

        Returns:
            bool: If its playing
        """
        if not (channel == 1 or channel == 2):
            print(f"Choose 1 or 2 for the channel!")
            return False
        return self.__channel_custom_now1.get_busy() if channel == 1 else self.__channel_custom_now2.get_busy()

    def change_background_music(self, filename: str, new_directory_path=None):
        """ Change the background music! Can be an mp3-file as well"""
        if mixer.music.get_busy():
            mixer.music.stop()

        mixer.music.unload()
        path = ""

        if new_directory_path is not None:
            path += new_directory_path
        else:
            path += self.path_to_audio
        
        mixer.music.load(f"{path}/{filename}")
        mixer.music.set_volume(self.__background_music_level)

    def stop_end_voice(self):
        """ Stops the end voice if its running """
        if self.__voice_thread is not None and self.__voice_thread.is_alive():
            self.__stop_condition.acquire()
            self.__stop_condition.notify()
            self.__stop_condition.release()
            self.__voice_thread.join()

    def stop_custom_sound(self):
        """ Stops the custom sound """
        if self.__custom_sound_thread is not None and self.__custom_sound_thread.is_alive():
            self.__stop_custom_condition.acquire()
            self.__stop_custom_condition.notify()
            self.__stop_custom_condition.release()
            
            # Joins on itself sometimes, depending if you have a long callback, should fix this later
            #self.__custom_sound_thread.join()
        # Also stop the custom now sounds
        self.__channel_custom_now2.stop()
        self.__channel_custom_now1.stop()

    def play_please_leave_room(self, last_statement=False, volume=1.0):
        """Notify the team that they should leave the room!

        Args:
            last_statement (bool, optional): Tell them for the last time or not. Defaults to False.
        """
        self.__channel_logic.stop()
        path = f"{self.path_to_audio}/effects/"
        path += "leave_the_room.wav" if not last_statement else "please_exit.wav"
        sound = mixer.Sound(path)
        self.__channel_logic.set_volume(volume)
        self.__channel_logic.play(sound)

    def stop_all_music_and_sound(self):
        """ Stop all sounds and music"""
        self.stop_end_voice()
        self.stop_custom_sound()
        # Stop the mixer.music module and then stop all playback on all channels
        self.stop_background_music()
        mixer.stop()
    
    def __play_losing_ending(self, close_call: bool):
        sound_list = []
        feedback_finder = self.FeedbackFinder()

        if close_call:
            sound_list.append(mixer.Sound(
                f"{self.path_to_audio}/effects/negative/{feedback_finder.get_close_call_feedback()}"))
        else:
            sound_list.append(mixer.Sound(
                f"{self.path_to_audio}/effects/negative/{feedback_finder.get_random_feedback(False)}"))

        sound_list.append(mixer.Sound(self.__losing))

        self.__voice_thread = Thread(target=self.__end_voice_task, args=(
            sound_list, self.__stop_condition))
        self.__voice_thread.start()

    def __play_winning_ending(self, points: int, max_points: bool):
        sound_list = []
        point_alternatives = [50, 100, 200, 300, 400, 500]
        feedback_finder = self.FeedbackFinder()

        # We pop from last position, so when we append, we append from backwards
        sound_list.append(mixer.Sound(
            f"{self.path_to_audio}/effects/points/points.wav"))

        if points in point_alternatives:
            sound_list.append(mixer.Sound(
                f"{self.path_to_audio}/effects/points/{points}.wav"))
        else:
            raise Exception(f"The parameter {points} points does not exist")
        
        if max_points:
            sound_list.append(mixer.Sound(
                f"{self.path_to_audio}/effects/you_got.wav"))
            sound_list.append(mixer.Sound(
                f"{self.path_to_audio}/effects/positive/{feedback_finder.get_max_points_feedback()}"))
        else:
            sound_list.append(mixer.Sound(
                f"{self.path_to_audio}/effects/you_reached.wav"))
            sound_list.append(mixer.Sound(
                f"{self.path_to_audio}/effects/positive/{feedback_finder.get_random_feedback(True)}"))

        
        sound_list.append(mixer.Sound(self.__winning))
        
        self.__voice_thread = Thread(target=self.__end_voice_task, args=(
            sound_list, self.__stop_condition))
        self.__voice_thread.start()

    def __end_voice_task(self, slist: list, cond: Condition):
        """ Task for the thread to run a list with sounds (like a queue) """
        cond.acquire()
        keep_running = True
        # Check if we should run the winning fanfare first!
        # if fanfare:
        #     self.__channel_logic.play(self.__winning)
        #     exit_early = cond.wait(self.__winning.get_length())
        #     if exit_early:
        #         keep_running = False
        #         self.__channel_logic.stop()

        # Next we play the voice with all the clips
        while len(slist) != 0 and keep_running:
            s = slist.pop()
            self.__channel_voice.queue(s)
            exit_early = cond.wait(s.get_length())
            if exit_early:
                keep_running = False
                self.__channel_voice.stop()

        cond.release()

    def __custom_sound_event(self, cond: Condition, music_level: float):
        cond.acquire()
        old_music_level = mixer.music.get_volume()
        mixer.music.set_volume(music_level)
        self.__channel_custom.play(self.__custom_sound)
        exit_early = cond.wait(self.__custom_sound.get_length())
        mixer.music.set_volume(old_music_level)
        if exit_early:
            self.__channel_custom.stop()
        elif self.__custom_sound_callback is not None:
            self.__custom_sound_callback()

        cond.release()

    class FeedbackFinder:

        __max_points_list = ['wow.wav', 'splendid.wav', 'nailed_it.wav']
        __positive_list = ['congratulations.wav', 'good_job.wav', 'great_teamwork.wav', 'great_work.wav', 'well_played.wav']
        __negative_list = ['better_luck_next_time.wav', 'come_on.wav', 'lets_try_again.wav']
        __close_list = ['so_close.wav']

        def get_random_feedback(self, positive: bool):
            if positive:
                return choice(self.__positive_list)
            else:
                return choice(self.__negative_list)

        def get_close_call_feedback(self):
            return choice(self.__close_list)

        def get_max_points_feedback(self):
            return choice(self.__max_points_list)

    