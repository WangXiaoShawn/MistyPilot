import json
import threading
import websocket
import re
import sys
from typing import Optional, Callable, Dict, Any
from random import randint
from requests import Response
import _thread as thread
from time import sleep
from RobotCommands import RobotCommands
import os
from pydub import AudioSegment
from pydub.playback import _play_with_simpleaudio



## inference https://docs.mistyrobotics.com/misty-ii/web-api/api-reference/#playaudio
class Robot(RobotCommands): # 继承与command
    def __init__(self, ip='127.0.0.1'):
        self.ip = ip
    def move_arms(self, 
              leftArmPosition: float = None, 
              rightArmPosition: float = None, 
              leftArmVelocity: float = None, 
              rightArmVelocity: float = None, 
              duration: float = None, 
              units: str = None) -> Response:
        '''
        Moves one or both of Misty's arms to the specified positions.

        Parameters:
        - leftArmPosition (float, optional): The target position for Misty's left arm.
        - At 0 degrees, the arm points forward along Misty's X-axis (this ).
        - At +90 degrees, the arm points downward.
        - At -90 degrees, the arm points upward (limited to -29 degrees).
        Defaults to None (no movement for the left arm).
        - rightArmPosition (float, optional): The target position for Misty's right arm.
        Similar to `leftArmPosition`. Defaults to None (no movement for the right arm).
        - leftArmVelocity (float, optional): The speed for moving Misty's left arm, 
        in the range 0 to 100. Defaults to None (uses default speed).
        - rightArmVelocity (float, optional): The speed for moving Misty's right arm, 
        in the range 0 to 100. Defaults to None (uses default speed).
        - duration (float, optional): The duration in seconds for the arm movement. 
        Defaults to None (robot determines duration automatically).
        - units (str, optional): The unit for the position values. 
        Can be 'degrees', 'radians', or 'position'. Defaults to None (assumes degrees).

        Returns:
        - Response: The HTTP response from Misty's API.

        Example Usage:
        # Move arms to neutral position (both arms forward, 0 degrees)
        misty.move_arms(leftArmPosition=0, rightArmPosition=0)

        # Move arms down (maximum downward position: 90 degrees)
        misty.move_arms(leftArmPosition=90, rightArmPosition=90)

        # Move arms up (maximum upward position: -29 degrees)
        misty.move_arms(leftArmPosition=-29, rightArmPosition=-29)

        # Move left arm up (-29 degrees) and right arm down (90 degrees)
        misty.move_arms(leftArmPosition=-29, rightArmPosition=90)

        # Move right arm up (-29 degrees) and left arm down (90 degrees)
        misty.move_arms(leftArmPosition=90, rightArmPosition=-29)

        # Move arms to a middle position (45 degrees down)
        misty.move_arms(leftArmPosition=45, rightArmPosition=45)

        # Move arms to a half-up position (-15 degrees)
        misty.move_arms(leftArmPosition=-15, rightArmPosition=-15)

        # Move only left arm up (-29 degrees), keeping the right arm unchanged
        misty.move_arms(leftArmPosition=-29, rightArmPosition=None)

        # Move only right arm down (90 degrees), keeping the left arm unchanged
        misty.move_arms(leftArmPosition=None, rightArmPosition=90)

   
        
        '''
        json = {
            "leftArmPosition": leftArmPosition,
            "rightArmPosition": rightArmPosition,
            "leftArmVelocity": leftArmVelocity,
            "rightArmVelocity": rightArmVelocity,
            "duration": duration,
            "units": units
        }
        return self.post_request("arms/set", json=json)
    
    def move_head(self, 
              pitch: float = None, 
              roll: float = None, 
              yaw: float = None, 
              velocity: float = None, 
              duration: float = None, 
              units: str = None) -> Response:
        '''
        Moves Misty's head to a new position along its pitch, roll, and yaw axes.

        Parameters:
        - pitch (float, optional): Value that determines the up or down position of Misty's head movement.
        - Range:
            - Degrees: -40 (up) to 26 (down)
            - Position: -5 (up) to 5 (down)
            - Radians: -0.1662 (up) to 0.6094 (down)
        Defaults to None (no movement in pitch).
        
        - roll (float, optional): Value that determines the tilt ("ear" to "shoulder") of Misty's head.
        - Range:
            - Degrees: -40 (left) to 40 (right)
            - Position: -5 (left) to 5 (right)
            - Radians: -0.75 (left) to 0.75 (right)
        Defaults to None (no movement in roll).
        
        - yaw (float, optional): Value that determines the left to right turn position of Misty's head.
        - Range:
            - Degrees: -81 (right) to 81 (left)
            - Position: -5 (right) to 5 (left)
            - Radians: -1.57 (right) to 1.57 (left)
        Defaults to None (no movement in yaw).
        
        - velocity (float, optional): The percentage of max velocity that indicates how quickly Misty should move her head.
        - Range: 0 to 100
        - Defaults to 10.

        - duration (float, optional): Time (in seconds) Misty takes to move her head from its current position to its new position.
        Defaults to None (robot determines duration automatically).

        - units (str, optional): A string value of "degrees", "radians", or "position" that determines which unit to use in moving Misty's head.
        Defaults to "degrees".

        Returns:
        - Response: The HTTP response from Misty's API.

        Example Usage:
        # Look straight ahead (default neutral position)
        misty.move_head(pitch=0, yaw=0, roll=0, units="degrees", duration=2.0)

        # Look up (maximum upward tilt)
        misty.move_head(pitch=-40, yaw=0, roll=0, units="degrees", duration=2.0)

        # Look down (maximum downward tilt)
        misty.move_head(pitch=26, yaw=0, roll=0, units="degrees", duration=2.0)

        # Look left (maximum left rotation)
        misty.move_head(pitch=0, yaw=81, roll=0, units="degrees", duration=2.0)

        # Look right (maximum right rotation)
        misty.move_head(pitch=0, yaw=-81, roll=0, units="degrees", duration=2.0)

        # Look up-left (combining upward tilt and left rotation)
        misty.move_head(pitch=-40, yaw=81, roll=0, units="degrees", duration=2.0)

        # Look up-right (combining upward tilt and right rotation)
        misty.move_head(pitch=-40, yaw=-81, roll=0, units="degrees", duration=2.0)

        # Look down-left (combining downward tilt and left rotation)
        misty.move_head(pitch=26, yaw=81, roll=0, units="degrees", duration=2.0)

        # Look down-right (combining downward tilt and right rotation)
        misty.move_head(pitch=26, yaw=-81, roll=0, units="degrees", duration=2.0)
        '''
        json = {
            "pitch": pitch,
            "roll": roll,
            "yaw": yaw,
            "velocity": velocity,
            "duration": duration,
            "units": units
        }
        return self.post_request("head", json=json)
    
    def change_led(self, red: int = 0, green: int = 0, blue: int = 0):
        '''
        Changes the color of the LED light on Misty.

        Parameters:
        - red (int): Red color intensity (0-255).
        - green (int): Green color intensity (0-255).
        - blue (int): Blue color intensity (0-255).
        
        Example Usage:
        misty.change_led(255, 0, 0)  # Set LED to red
        misty.change_led(0, 255, 0)  # Set LED to green
        misty.change_led(0, 0, 255)  # Set LED to blue
        '''
        json = {"red": red, "green": green, "blue": blue}
        return self.post_request("led", json=json)
    
    def transition_led(self, 
                       red: int, green: int, blue: int, 
                       red2: int, green2: int, blue2: int, 
                       transition_type: str = "Breathe", 
                       time_ms: float = 500):
        '''
        Sets Misty's LED to transition between two colors.

        **Parameters:**
        - red, green, blue (int): **First color** in RGB format (0-255).
        - red2, green2, blue2 (int): **Second color** in RGB format (0-255).
        - transition_type (str): LED transition mode, supports:
          
          **"Blink"** - LED **flashes rapidly** between the two colors.
          
          **"Breathe"** - LED **smoothly fades** between the colors, like a breathing effect.
          
          **"TransitOnce"** - LED **gradually changes from the first to the second color**, then stays in the second color.

        - time_ms (int): Duration (in milliseconds) for each transition (must be >3).

        **Returns:**
        - requests.Response: HTTP response object.

        Example Usage:
        - **LED blinks between red and blue (Blink mode)**:
          misty.transition_led(255, 0, 0, 0, 0, 255, "Blink", 500)

        - **LED smoothly fades between green and yellow (Breathe mode)**:
        
          misty.transition_led(0, 255, 0, 255, 255, 0, "Breathe", 1000)

        - **LED transitions once from white to black and stays black (TransitOnce mode)**:
          misty.transition_led(255, 255, 255, 0, 0, 0, "TransitOnce", 1500)
        
        '''
        if transition_type not in ["Blink", "Breathe", "TransitOnce"]:
            raise ValueError("transition_type must be 'Blink', 'Breathe', or 'TransitOnce'")

        if time_ms <= 3:
            raise ValueError("time_ms must be greater than 3 milliseconds")

        json = {
            "red": red, "green": green, "blue": blue,
            "red2": red2, "green2": green2, "blue2": blue2,
            "transitionType": transition_type,
            "timeMs": time_ms
        }
        return self.post_request("led/transition", json=json)
    def emotion_Admiration(self, alpha: float = 1.0, layer: str = "default", isURL: bool = False) -> Response:
        '''
        Display an admiration expression on the Misty robot.
        
        Parameters:
            alpha (float): Image transparency, default is 1.0.
            layer (str): Display layer, default is "default".
            isURL (bool): Specifies whether fileName is a URL, default is False.
        
        Returns:
            Response: The response object after displaying the image.
        '''
        return self.display_image(fileName="e_Admiration.jpg", alpha=alpha, layer=layer, isURL=isURL)

    def emotion_Aggressiveness(self, alpha: float = 1.0, layer: str = "default", isURL: bool = False) -> Response:
        '''
        Display an aggressiveness expression on the Misty robot.
        
        Parameters:
            alpha (float): Image transparency, default is 1.0.
            layer (str): Display layer, default is "default".
            isURL (bool): Specifies whether fileName is a URL, default is False.
        
        Returns:
            Response: The response object after displaying the image.
        '''
        return self.display_image(fileName="e_Aggressiveness.jpg", alpha=alpha, layer=layer, isURL=isURL)

    def emotion_Amazement(self, alpha: float = 1.0, layer: str = "default", isURL: bool = False) -> Response:
        '''
        Display an amazement expression on the Misty robot.
        
        Parameters:
            alpha (float): Image transparency, default is 1.0.
            layer (str): Display layer, default is "default".
            isURL (bool): Specifies whether fileName is a URL, default is False.
        
        Returns:
            Response: The response object after displaying the image.
        '''
        return self.display_image(fileName="e_Amazement.jpg", alpha=alpha, layer=layer, isURL=isURL)
    
    def emotion_Anger(self, alpha: float = 1.0, layer: str = "default", isURL: bool = False) -> Response:
        '''
        Display an anger expression on the Misty robot.
        
        Parameters:
            alpha (float): Image transparency, default is 1.0.
            layer (str): Display layer, default is "default".
            isURL (bool): Specifies whether fileName is a URL, default is False.
        
        Returns:
            Response: The response object after displaying the image.
        '''
        return self.display_image(fileName="e_Anger.jpg", alpha=alpha, layer=layer, isURL=isURL)

    def emotion_ApprehensionConcerned(self, alpha: float = 1.0, layer: str = "default", isURL: bool = False) -> Response:
        '''
        Display an apprehension and concerned expression on the Misty robot.
        
        Parameters:
            alpha (float): Image transparency, default is 1.0.
            layer (str): Display layer, default is "default".
            isURL (bool): Specifies whether fileName is a URL, default is False.
        
        Returns:
            Response: The response object after displaying the image.
        '''
        return self.display_image(fileName="e_ApprehensionConcerned.jpg", alpha=alpha, layer=layer, isURL=isURL)
    
    def emotion_Contempt(self, alpha: float = 1.0, layer: str = "default", isURL: bool = False) -> Response:
        '''
        Display a contempt expression on the Misty robot.
        
        Parameters:
            alpha (float): Image transparency, default is 1.0.
            layer (str): Display layer, default is "default".
            isURL (bool): Specifies whether fileName is a URL, default is False.
        
        Returns:
            Response: The response object after displaying the image.
        '''
        return self.display_image(fileName="e_Contempt.jpg", alpha=alpha, layer=layer, isURL=isURL)

    def emotion_ContentLeft(self, alpha: float = 1.0, layer: str = "default", isURL: bool = False) -> Response:
        '''
        Display a content expression on the left side of the Misty robot.
        
        Parameters:
            alpha (float): Image transparency, default is 1.0.
            layer (str): Display layer, default is "default".
            isURL (bool): Specifies whether fileName is a URL, default is False.
        
        Returns:
            Response: The response object after displaying the image.
        '''
        return self.display_image(fileName="e_ContentLeft.jpg", alpha=alpha, layer=layer, isURL=isURL)

    def emotion_ContentRight(self, alpha: float = 1.0, layer: str = "default", isURL: bool = False) -> Response:
        '''
        Display a content expression on the right side of the Misty robot.
        
        Parameters:
            alpha (float): Image transparency, default is 1.0.
            layer (str): Display layer, default is "default".
            isURL (bool): Specifies whether fileName is a URL, default is False.
        
        Returns:
            Response: The response object after displaying the image.
        '''
        return self.display_image(fileName="e_ContentRight.jpg", alpha=alpha, layer=layer, isURL=isURL)

    def emotion_DefaultContent(self, alpha: float = 1.0, layer: str = "default", isURL: bool = False) -> Response:
        '''
        Display the default expression on the Misty robot.
        
        Parameters:
            alpha (float): Image transparency, default is 1.0.
            layer (str): Display layer, default is "default".
            isURL (bool): Specifies whether fileName is a URL, default is False.
        
        Returns:
            Response: The response object after displaying the image.
        '''
        return self.display_image(fileName="e_DefaultContent.jpg", alpha=alpha, layer=layer, isURL=isURL)

    def emotion_Disgust(self, alpha: float = 1.0, layer: str = "default", isURL: bool = False) -> Response:
        '''
        Display a disgust expression on the Misty robot.
        
        Parameters:
            alpha (float): Image transparency, default is 1.0.
            layer (str): Display layer, default is "default".
            isURL (bool): Specifies whether fileName is a URL, default is False.
        
        Returns:
            Response: The response object after displaying the image.
        '''
        return self.display_image(fileName="e_Disgust.jpg", alpha=alpha, layer=layer, isURL=isURL)

    def emotion_Disoriented(self, alpha: float = 1.0, layer: str = "default", isURL: bool = False) -> Response:
        '''
        Display a disoriented expression on the Misty robot.
        
        Parameters:
            alpha (float): Image transparency, default is 1.0.
            layer (str): Display layer, default is "default".
            isURL (bool): Specifies whether fileName is a URL, default is False.
        
        Returns:
            Response: The response object after displaying the image.
        '''
        return self.display_image(fileName="e_Disoriented.jpg", alpha=alpha, layer=layer, isURL=isURL)

    def emotion_EcstacyHilarious(self, alpha: float = 1.0, layer: str = "default", isURL: bool = False) -> Response:
        '''
        Display a hilarious ecstasy expression on the Misty robot.
        
        Parameters:
            alpha (float): Image transparency, default is 1.0.
            layer (str): Display layer, default is "default".
            isURL (bool): Specifies whether fileName is a URL, default is False.
        
        Returns:
            Response: The response object after displaying the image.
        '''
        return self.display_image(fileName="e_EcstacyHilarious.jpg", alpha=alpha, layer=layer, isURL=isURL)

    def emotion_EcstacyStarryEyed(self, alpha: float = 1.0, layer: str = "default", isURL: bool = False) -> Response:
        '''
        Display a starry-eyed ecstasy expression on the Misty robot.
        
        Parameters:
            alpha (float): Image transparency, default is 1.0.
            layer (str): Display layer, default is "default".
            isURL (bool): Specifies whether fileName is a URL, default is False.
        
        Returns:
            Response: The response object after displaying the image.
        '''
        return self.display_image(fileName="e_EcstacyStarryEyed.jpg", alpha=alpha, layer=layer, isURL=isURL)

    def emotion_Fear(self, alpha: float = 1.0, layer: str = "default", isURL: bool = False) -> Response:
        '''
        Display a fear expression on the Misty robot.
        
        Parameters:
            alpha (float): Image transparency, default is 1.0.
            layer (str): Display layer, default is "default".
            isURL (bool): Specifies whether fileName is a URL, default is False.
        
        Returns:
            Response: The response object after displaying the image.
        '''
        return self.display_image(fileName="e_Fear.jpg", alpha=alpha, layer=layer, isURL=isURL)

    def emotion_Grief(self, alpha: float = 1.0, layer: str = "default", isURL: bool = False) -> Response:
        '''
        Display a grief expression on the Misty robot.
        
        Parameters:
            alpha (float): Image transparency, default is 1.0.
            layer (str): Display layer, default is "default".
            isURL (bool): Specifies whether fileName is a URL, default is False.
        
        Returns:
            Response: The response object after displaying the image.
        '''
        return self.display_image(fileName="e_Grief.jpg", alpha=alpha, layer=layer, isURL=isURL)

    def emotion_Joy(self, alpha: float = 1.0, layer: str = "default", isURL: bool = False) -> Response:
        '''
        Display a joy expression on the Misty robot.
        
        Parameters:
            alpha (float): Image transparency, default is 1.0.
            layer (str): Display layer, default is "default".
            isURL (bool): Specifies whether fileName is a URL, default is False.
        
        Returns:
            Response: The response object after displaying the image.
        '''
        return self.display_image(fileName="e_Joy.jpg", alpha=alpha, layer=layer, isURL=isURL)

    def emotion_Joy2(self, alpha: float = 1.0, layer: str = "default", isURL: bool = False) -> Response:
        '''
        Display a more intense joy expression on the Misty robot.
        
        Parameters:
            alpha (float): Image transparency, default is 1.0.
            layer (str): Display layer, default is "default".
            isURL (bool): Specifies whether fileName is a URL, default is False.
        
        Returns:
            Response: The response object after displaying the image.
        '''
        return self.display_image(fileName="e_Joy2.jpg", alpha=alpha, layer=layer, isURL=isURL)

    def emotion_JoyGoofy(self, alpha: float = 1.0, layer: str = "default", isURL: bool = False) -> Response:
        '''
        Display a goofy joy expression on the Misty robot.
        
        Parameters:
            alpha (float): Image transparency, default is 1.0.
            layer (str): Display layer, default is "default".
            isURL (bool): Specifies whether fileName is a URL, default is False.
        
        Returns:
            Response: The response object after displaying the image.
        '''
        return self.display_image(fileName="e_JoyGoofy.jpg", alpha=alpha, layer=layer, isURL=isURL)

    def emotion_JoyGoofy2(self, alpha: float = 1.0, layer: str = "default", isURL: bool = False) -> Response:
        '''
        Display a more intense goofy joy expression on the Misty robot.
        
        Parameters:
            alpha (float): Image transparency, default is 1.0.
            layer (str): Display layer, default is "default".
            isURL (bool): Specifies whether fileName is a URL, default is False.
        
        Returns:
            Response: The response object after displaying the image.
        '''
        return self.display_image(fileName="e_JoyGoofy2.jpg", alpha=alpha, layer=layer, isURL=isURL)

    def emotion_JoyGoofy3(self, alpha: float = 1.0, layer: str = "default", isURL: bool = False) -> Response:
        '''
        Display an even more intense goofy joy expression on the Misty robot.
        
        Parameters:
            alpha (float): Image transparency, default is 1.0.
            layer (str): Display layer, default is "default".
            isURL (bool): Specifies whether fileName is a URL, default is False.
        
        Returns:
            Response: The response object after displaying the image.
        '''
        return self.display_image(fileName="e_JoyGoofy3.jpg", alpha=alpha, layer=layer, isURL=isURL)

    def emotion_Love(self, alpha: float = 1.0, layer: str = "default", isURL: bool = False) -> Response:
        '''
        Display a love expression on the Misty robot.
        
        Parameters:
            alpha (float): Image transparency, default is 1.0.
            layer (str): Display layer, default is "default".
            isURL (bool): Specifies whether fileName is a URL, default is False.
        
        Returns:
            Response: The response object after displaying the image.
        '''
        return self.display_image(fileName="e_Love.jpg", alpha=alpha, layer=layer, isURL=isURL)

    def emotion_Rage(self, alpha: float = 1.0, layer: str = "default", isURL: bool = False) -> Response:
        '''
        Display an rage expression on the Misty robot.
        
        Parameters:
            alpha (float): Image transparency, default is 1.0.
            layer (str): Display layer, default is "default".
            isURL (bool): Specifies whether fileName is a URL, default is False.
        
        Returns:
            Response: The response object after displaying the image.
        '''
        return self.display_image(fileName="e_Rage.jpg", alpha=alpha, layer=layer, isURL=isURL)

    def emotion_Rage2(self, alpha: float = 1.0, layer: str = "default", isURL: bool = False) -> Response:
        '''
        Display a more intense rage expression on the Misty robot.
        
        Parameters:
            alpha (float): Image transparency, default is 1.0.
            layer (str): Display layer, default is "default".
            isURL (bool): Specifies whether fileName is a URL, default is False.
        
        Returns:
            Response: The response object after displaying the image.
        '''
        return self.display_image(fileName="e_Rage2.jpg", alpha=alpha, layer=layer, isURL=isURL)

    def emotion_Rage3(self, alpha: float = 1.0, layer: str = "default", isURL: bool = False) -> Response:
        '''
        Display an even more intense rage expression on the Misty robot.
        
        Parameters:
            alpha (float): Image transparency, default is 1.0.
            layer (str): Display layer, default is "default".
            isURL (bool): Specifies whether fileName is a URL, default is False.
        
        Returns:
            Response: The response object after displaying the image.
        '''
        return self.display_image(fileName="e_Rage3.jpg", alpha=alpha, layer=layer, isURL=isURL)

    def emotion_Rage4(self, alpha: float = 1.0, layer: str = "default", isURL: bool = False) -> Response:
        '''
        Display the most intense rage expression on the Misty robot.
        
        Parameters:
            alpha (float): Image transparency, default is 1.0.
            layer (str): Display layer, default is "default".
            isURL (bool): Specifies whether fileName is a URL, default is False.
        
        Returns:
            Response: The response object after displaying the image.
        '''
        return self.display_image(fileName="e_Rage4.jpg", alpha=alpha, layer=layer, isURL=isURL)

    def emotion_RemorseShame(self, alpha: float = 1.0, layer: str = "default", isURL: bool = False) -> Response:
        '''
        Display a remorse and shame expression on the Misty robot.
        
        Parameters:
            alpha (float): Image transparency, default is 1.0.
            layer (str): Display layer, default is "default".
            isURL (bool): Specifies whether fileName is a URL, default is False.
        
        Returns:
            Response: The response object after displaying the image.
        '''
        return self.display_image(fileName="e_RemorseShame.jpg", alpha=alpha, layer=layer, isURL=isURL)

    def emotion_Sadness(self, alpha: float = 1.0, layer: str = "default", isURL: bool = False) -> Response:
        '''
        Display a sadness expression on the Misty robot.
        
        Parameters:
            alpha (float): Image transparency, default is 1.0.
            layer (str): Display layer, default is "default".
            isURL (bool): Specifies whether fileName is a URL, default is False.
        
        Returns:
            Response: The response object after displaying the image.
        '''
        return self.display_image(fileName="e_Sadness.jpg", alpha=alpha, layer=layer, isURL=isURL)

    def emotion_Sleeping(self, alpha: float = 1.0, layer: str = "default", isURL: bool = False) -> Response:
        '''
        Display a sleeping expression on the Misty robot.
        
        Parameters:
            alpha (float): Image transparency, default is 1.0.
            layer (str): Display layer, default is "default".
            isURL (bool): Specifies whether fileName is a URL, default is False.
        
        Returns:
            Response: The response object after displaying the image.
        '''
        return self.display_image(fileName="e_Sleeping.jpg", alpha=alpha, layer=layer, isURL=isURL)

    def emotion_SleepingZZZ(self, alpha: float = 1.0, layer: str = "default", isURL: bool = False) -> Response:
        '''
        Display a sleeping expression with "ZZZ" indicator on the Misty robot.
        
        Parameters:
            alpha (float): Image transparency, default is 1.0.
            layer (str): Display layer, default is "default".
            isURL (bool): Specifies whether fileName is a URL, default is False.
        
        Returns:
            Response: The response object after displaying the image.
        '''
        return self.display_image(fileName="e_SleepingZZZ.jpg", alpha=alpha, layer=layer, isURL=isURL)

    def emotion_Sleepy(self, alpha: float = 1.0, layer: str = "default", isURL: bool = False) -> Response:
        '''
        Display a sleepy expression on the Misty robot.
        
        Parameters:
            alpha (float): Image transparency, default is 1.0.
            layer (str): Display layer, default is "default".
            isURL (bool): Specifies whether fileName is a URL, default is False.
        
        Returns:
            Response: The response object after displaying the image.
        '''
        return self.display_image(fileName="e_Sleepy.jpg", alpha=alpha, layer=layer, isURL=isURL)

    def emotion_Sleepy2(self, alpha: float = 1.0, layer: str = "default", isURL: bool = False) -> Response:
        '''
        Display a more intense sleepy expression on the Misty robot.
        
        Parameters:
            alpha (float): Image transparency, default is 1.0.
            layer (str): Display layer, default is "default".
            isURL (bool): Specifies whether fileName is a URL, default is False.
        
        Returns:
            Response: The response object after displaying the image.
        '''
        return self.display_image(fileName="e_Sleepy2.jpg", alpha=alpha, layer=layer, isURL=isURL)

    def emotion_Sleepy3(self, alpha: float = 1.0, layer: str = "default", isURL: bool = False) -> Response:
        '''
        Display an even more intense sleepy expression on the Misty robot.
        
        Parameters:
            alpha (float): Image transparency, default is 1.0.
            layer (str): Display layer, default is "default".
            isURL (bool): Specifies whether fileName is a URL, default is False.
        
        Returns:
            Response: The response object after displaying the image.
        '''
        return self.display_image(fileName="e_Sleepy3.jpg", alpha=alpha, layer=layer, isURL=isURL)

    def emotion_Sleepy4(self, alpha: float = 1.0, layer: str = "default", isURL: bool = False) -> Response:
        '''
        Display the most intense sleepy expression on the Misty robot.
        
        Parameters:
            alpha (float): Image transparency, default is 1.0.
            layer (str): Display layer, default is "default".
            isURL (bool): Specifies whether fileName is a URL, default is False.
        
        Returns:
            Response: The response object after displaying the image.
        '''
        return self.display_image(fileName="e_Sleepy4.jpg", alpha=alpha, layer=layer, isURL=isURL)

    def emotion_Surprise(self, alpha: float = 1.0, layer: str = "default", isURL: bool = False) -> Response:
        '''
        Display a surprise expression on the Misty robot.
        
        Parameters:
            alpha (float): Image transparency, default is 1.0.
            layer (str): Display layer, default is "default".
            isURL (bool): Specifies whether fileName is a URL, default is False.
        
        Returns:
            Response: The response object after displaying the image.
        '''
        return self.display_image(fileName="e_Surprise.jpg", alpha=alpha, layer=layer, isURL=isURL)

    def emotion_Terror(self, alpha: float = 1.0, layer: str = "default", isURL: bool = False) -> Response:
        '''
        Display a terror expression on the Misty robot.
        
        Parameters:
            alpha (float): Image transparency, default is 1.0.
            layer (str): Display layer, default is "default".
            isURL (bool): Specifies whether fileName is a URL, default is False.
        
        Returns:
            Response: The response object after displaying the image.
        '''
        return self.display_image(fileName="e_Terror.jpg", alpha=alpha, layer=layer, isURL=isURL)

    def emotion_Terror2(self, alpha: float = 1.0, layer: str = "default", isURL: bool = False) -> Response:
        '''
        Display a more intense terror expression on the Misty robot.
        
        Parameters:
            alpha (float): Image transparency, default is 1.0.
            layer (str): Display layer, default is "default".
            isURL (bool): Specifies whether fileName is a URL, default is False.
        
        Returns:
            Response: The response object after displaying the image.
        '''
        return self.display_image(fileName="e_Terror2.jpg", alpha=alpha, layer=layer, isURL=isURL)

    def emotion_TerrorLeft(self, alpha: float = 1.0, layer: str = "default", isURL: bool = False) -> Response:
        '''
        Display a terror expression on the left side of the Misty robot.
        
        Parameters:
            alpha (float): Image transparency, default is 1.0.
            layer (str): Display layer, default is "default".
            isURL (bool): Specifies whether fileName is a URL, default is False.
        
        Returns:
            Response: The response object after displaying the image.
        '''
        return self.display_image(fileName="e_TerrorLeft.jpg", alpha=alpha, layer=layer, isURL=isURL)

    def emotion_TerrorRight(self, alpha: float = 1.0, layer: str = "default", isURL: bool = False) -> Response:
        '''
        Display a terror expression on the right side of the Misty robot.
        
        Parameters:
            alpha (float): Image transparency, default is 1.0.
            layer (str): Display layer, default is "default".
            isURL (bool): Specifies whether fileName is a URL, default is False.
        
        Returns:
            Response: The response object after displaying the image.
        '''
        return self.display_image(fileName="e_TerrorRight.jpg", alpha=alpha, layer=layer, isURL=isURL)
    def return_to_normal(self):
            '''
            Restore Misty to a neutral state.

            This function resets Misty's LED color, facial expression, arm position, and head orientation 
            to a neutral state.

            Parameters:
                None

            Returns:
                None
            '''
            # Set Misty's LED to a neutral color (e.g., white).
            self.change_led(red=255, green=255, blue=255)

            # Display Misty's default content expression.
            self.emotion_DefaultContent()

            # Relax Misty's arms to a neutral position.
            # self.move_arms(leftArmPosition=0, rightArmPosition=0, duration=0.5)
            self.move_arms(leftArmPosition=90, rightArmPosition=90, duration=0.5)


            # Center Misty's head to look straight ahead.
            self.move_head(pitch=0, yaw=0, roll=0, duration=0.5)

    def play_local_mp3(self, file_path: str) -> bool:
        '''
        Play a local MP3 file using afplay (macOS native player).
        Direct playback without pydub/ffmpeg processing to avoid process leaks.
        
        Parameters:
            file_path (str): The absolute or relative path to the MP3 file.
        
        Returns:
            bool: True if playback succeeded, False if failed.
        
        Example Usage:
            robot.play_local_mp3("./MistySpeaking/angry.mp3")
            robot.play_local_mp3("/full/path/to/sound.mp3")
        '''
        try:
            import subprocess
            
            # Check if file exists
            if not os.path.exists(file_path):
                print(f"[ERROR] File not found: {file_path}")
                return False
            
            # Play audio directly using afplay (no pydub/ffmpeg processing)
            print(f"[INFO] Playing audio: {file_path}")
            result = subprocess.run(
                ['afplay', file_path],
                timeout=40,  # 40秒超时保护
                capture_output=True,
                text=True,
                check=False
            )
            
            # Check result
            if result.returncode != 0:
                print(f"[WARN] afplay exit code: {result.returncode}")
                if result.stderr:
                    print(f"[WARN] afplay stderr: {result.stderr.strip()}")
            
            # Small buffer to ensure clean finish
            sleep(0.15)
            
            print(f"[INFO] Playback completed: {file_path}")
            return result.returncode == 0
            
        except subprocess.TimeoutExpired:
            print(f"[ERROR] Playback timeout after 40s")
            return False
        except Exception as e:
            print(f"[ERROR] Failed to play MP3: {e}")
            return False
   
