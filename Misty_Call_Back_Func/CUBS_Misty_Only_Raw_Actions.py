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
    def sound_Acceptance(self, volume: int = None) -> Response:
        '''
        Play the acceptance emotion sound.
        
        Parameters:
            volume (int): Volume level (0-100), default is None.
        
        Returns:
            Response: The response object after playing the audio.
        '''
        return self.play_audio(fileName="s_Acceptance.wav", volume=volume)

    def sound_Amazement(self, volume: int = None) -> Response:
        '''
        Play the amazement emotion sound.
        
        Parameters:
            volume (int): Volume level (0-100), default is None.
        
        Returns:
            Response: The response object after playing the audio.
        '''
        return self.play_audio(fileName="s_Amazement.wav", volume=volume)

    def sound_Amazement2(self, volume: int = None) -> Response:
        '''
        Play the amazement emotion sound with medium intensity.
        
        Parameters:
            volume (int): Volume level (0-100), default is None.
        
        Returns:
            Response: The response object after playing the audio.
        '''
        return self.play_audio(fileName="s_Amazement2.wav", volume=volume)

    def sound_Anger(self, volume: int = None) -> Response:
        '''
        Play the anger emotion sound.
        
        Parameters:
            volume (int): Volume level (0-100), default is None.
        
        Returns:
            Response: The response object after playing the audio.
        '''
        return self.play_audio(fileName="s_Anger.wav", volume=volume)

    def sound_Anger2(self, volume: int = None) -> Response:
        '''
        Play the anger emotion sound with medium intensity.
        
        Parameters:
            volume (int): Volume level (0-100), default is None.
        
        Returns:
            Response: The response object after playing the audio.
        '''
        return self.play_audio(fileName="s_Anger2.wav", volume=volume)

    def sound_Anger3(self, volume: int = None) -> Response:
        '''
        Play the anger emotion sound with high intensity.
        
        Parameters:
            volume (int): Volume level (0-100), default is None.
        
        Returns:
            Response: The response object after playing the audio.
        '''
        return self.play_audio(fileName="s_Anger3.wav", volume=volume)

    def sound_Anger4(self, volume: int = None) -> Response:
        '''
        Play the anger emotion sound with very high intensity.
        
        Parameters:
            volume (int): Volume level (0-100), default is None.
        
        Returns:
            Response: The response object after playing the audio.
        '''
        return self.play_audio(fileName="s_Anger4.wav", volume=volume)

    def sound_Annoyance(self, volume: int = None) -> Response:
        '''
        Play the annoyance emotion sound.
        
        Parameters:
            volume (int): Volume level (0-100), default is None.
        
        Returns:
            Response: The response object after playing the audio.
        '''
        return self.play_audio(fileName="s_Annoyance.wav", volume=volume)

    def sound_Annoyance2(self, volume: int = None) -> Response:
        '''
        Play the annoyance emotion sound with medium intensity.
        
        Parameters:
            volume (int): Volume level (0-100), default is None.
        
        Returns:
            Response: The response object after playing the audio.
        '''
        return self.play_audio(fileName="s_Annoyance2.wav", volume=volume)

    def sound_Annoyance3(self, volume: int = None) -> Response:
        '''
        Play the annoyance emotion sound with high intensity.
        
        Parameters:
            volume (int): Volume level (0-100), default is None.
        
        Returns:
            Response: The response object after playing the audio.
        '''
        return self.play_audio(fileName="s_Annoyance3.wav", volume=volume)

    def sound_Annoyance4(self, volume: int = None) -> Response:
        '''
        Play the annoyance emotion sound with very high intensity.
        
        Parameters:
            volume (int): Volume level (0-100), default is None.
        
        Returns:
            Response: The response object after playing the audio.
        '''
        return self.play_audio(fileName="s_Annoyance4.wav", volume=volume)

    def sound_Awe(self, volume: int = None) -> Response:
        '''
        Play the awe emotion sound.
        
        Parameters:
            volume (int): Volume level (0-100), default is None.
        
        Returns:
            Response: The response object after playing the audio.
        '''
        return self.play_audio(fileName="s_Awe.wav", volume=volume)

    def sound_Awe2(self, volume: int = None) -> Response:
        '''
        Play the awe emotion sound with medium intensity.
        
        Parameters:
            volume (int): Volume level (0-100), default is None.
        
        Returns:
            Response: The response object after playing the audio.
        '''
        return self.play_audio(fileName="s_Awe2.wav", volume=volume)

    def sound_Awe3(self, volume: int = None) -> Response:
        '''
        Play the awe emotion sound with high intensity.
        
        Parameters:
            volume (int): Volume level (0-100), default is None.
        
        Returns:
            Response: The response object after playing the audio.
        '''
        return self.play_audio(fileName="s_Awe3.wav", volume=volume)

    def sound_Boredom(self, volume: int = None) -> Response:
        '''
        Play the boredom emotion sound.
        
        Parameters:
            volume (int): Volume level (0-100), default is None.
        
        Returns:
            Response: The response object after playing the audio.
        '''
        return self.play_audio(fileName="s_Boredom.wav", volume=volume)

    def sound_Disapproval(self, volume: int = None) -> Response:
        '''
        Play the disapproval emotion sound.
        
        Parameters:
            volume (int): Volume level (0-100), default is None.
        
        Returns:
            Response: The response object after playing the audio.
        '''
        return self.play_audio(fileName="s_Disapproval.wav", volume=volume)

    def sound_Disgust(self, volume: int = None) -> Response:
        '''
        Play the disgust emotion sound.
        
        Parameters:
            volume (int): Volume level (0-100), default is None.
        
        Returns:
            Response: The response object after playing the audio.
        '''
        return self.play_audio(fileName="s_Disgust.wav", volume=volume)

    def sound_Disgust2(self, volume: int = None) -> Response:
        '''
        Play the disgust emotion sound with medium intensity.
        
        Parameters:
            volume (int): Volume level (0-100), default is None.
        
        Returns:
            Response: The response object after playing the audio.
        '''
        return self.play_audio(fileName="s_Disgust2.wav", volume=volume)

    def sound_Disgust3(self, volume: int = None) -> Response:
        '''
        Play the disgust emotion sound with high intensity.
        
        Parameters:
            volume (int): Volume level (0-100), default is None.
        
        Returns:
            Response: The response object after playing the audio.
        '''
        return self.play_audio(fileName="s_Disgust3.wav", volume=volume)

    def sound_DisorientedConfused(self, volume: int = None) -> Response:
        '''
        Play the disoriented confused sound.
        
        Parameters:
            volume (int): Volume level (0-100), default is None.
        
        Returns:
            Response: The response object after playing the audio.
        '''
        return self.play_audio(fileName="s_DisorientedConfused.wav", volume=volume)

    def sound_DisorientedConfused2(self, volume: int = None) -> Response:
        '''
        Play the disoriented confused sound with medium intensity.
        
        Parameters:
            volume (int): Volume level (0-100), default is None.
        
        Returns:
            Response: The response object after playing the audio.
        '''
        return self.play_audio(fileName="s_DisorientedConfused2.wav", volume=volume)

    def sound_DisorientedConfused3(self, volume: int = None) -> Response:
        '''
        Play the disoriented confused sound with high intensity.
        
        Parameters:
            volume (int): Volume level (0-100), default is None.
        
        Returns:
            Response: The response object after playing the audio.
        '''
        return self.play_audio(fileName="s_DisorientedConfused3.wav", volume=volume)

    def sound_DisorientedConfused4(self, volume: int = None) -> Response:
        '''
        Play the disoriented confused sound with very high intensity.
        
        Parameters:
            volume (int): Volume level (0-100), default is None.
        
        Returns:
            Response: The response object after playing the audio.
        '''
        return self.play_audio(fileName="s_DisorientedConfused4.wav", volume=volume)

    def sound_DisorientedConfused5(self, volume: int = None) -> Response:
        '''
        Play the disoriented confused sound with extremely high intensity.
        
        Parameters:
            volume (int): Volume level (0-100), default is None.
        
        Returns:
            Response: The response object after playing the audio.
        '''
        return self.play_audio(fileName="s_DisorientedConfused5.wav", volume=volume)

    def sound_DisorientedConfused6(self, volume: int = None) -> Response:
        '''
        Play the disoriented confused sound with maximum intensity.
        
        Parameters:
            volume (int): Volume level (0-100), default is None.
        
        Returns:
            Response: The response object after playing the audio.
        '''
        return self.play_audio(fileName="s_DisorientedConfused6.wav", volume=volume)

    def sound_Distraction(self, volume: int = None) -> Response:
        '''
        Play the distraction emotion sound.
        
        Parameters:
            volume (int): Volume level (0-100), default is None.
        
        Returns:
            Response: The response object after playing the audio.
        '''
        return self.play_audio(fileName="s_Distraction.wav", volume=volume)

    def sound_Ecstacy(self, volume: int = None) -> Response:
        '''
        Play the ecstacy emotion sound.
        
        Parameters:
            volume (int): Volume level (0-100), default is None.
        
        Returns:
            Response: The response object after playing the audio.
        '''
        return self.play_audio(fileName="s_Ecstacy.wav", volume=volume)

    def sound_Ecstacy2(self, volume: int = None) -> Response:
        '''
        Play the ecstacy emotion sound with medium intensity.
        
        Parameters:
            volume (int): Volume level (0-100), default is None.
        
        Returns:
            Response: The response object after playing the audio.
        '''
        return self.play_audio(fileName="s_Ecstacy2.wav", volume=volume)

    def sound_Fear(self, volume: int = None) -> Response:
        '''
        Play the fear emotion sound.
        
        Parameters:
            volume (int): Volume level (0-100), default is None.
        
        Returns:
            Response: The response object after playing the audio.
        '''
        return self.play_audio(fileName="s_Fear.wav", volume=volume)

    def sound_Grief(self, volume: int = None) -> Response:
        '''
        Play the grief emotion sound.
        
        Parameters:
            volume (int): Volume level (0-100), default is None.
        
        Returns:
            Response: The response object after playing the audio.
        '''
        return self.play_audio(fileName="s_Grief.wav", volume=volume)

    def sound_Grief2(self, volume: int = None) -> Response:
        '''
        Play the grief emotion sound with medium intensity.
        
        Parameters:
            volume (int): Volume level (0-100), default is None.
        
        Returns:
            Response: The response object after playing the audio.
        '''
        return self.play_audio(fileName="s_Grief2.wav", volume=volume)

    def sound_Grief3(self, volume: int = None) -> Response:
        '''
        Play the grief emotion sound with high intensity.
        
        Parameters:
            volume (int): Volume level (0-100), default is None.
        
        Returns:
            Response: The response object after playing the audio.
        '''
        return self.play_audio(fileName="s_Grief3.wav", volume=volume)

    def sound_Grief4(self, volume: int = None) -> Response:
        '''
        Play the grief emotion sound with very high intensity.
        
        Parameters:
            volume (int): Volume level (0-100), default is None.
        
        Returns:
            Response: The response object after playing the audio.
        '''
        return self.play_audio(fileName="s_Grief4.wav", volume=volume)

    def sound_Joy(self, volume: int = None) -> Response:
        '''
        Play the joy emotion sound.
        
        Parameters:
            volume (int): Volume level (0-100), default is None.
        
        Returns:
            Response: The response object after playing the audio.
        '''
        return self.play_audio(fileName="s_Joy.wav", volume=volume)

    def sound_Joy2(self, volume: int = None) -> Response:
        '''
        Play the joy emotion sound with medium intensity.
        
        Parameters:
            volume (int): Volume level (0-100), default is None.
        
        Returns:
            Response: The response object after playing the audio.
        '''
        return self.play_audio(fileName="s_Joy2.wav", volume=volume)

    def sound_Joy3(self, volume: int = None) -> Response:
        '''
        Play the joy emotion sound with high intensity.
        
        Parameters:
            volume (int): Volume level (0-100), default is None.
        
        Returns:
            Response: The response object after playing the audio.
        '''
        return self.play_audio(fileName="s_Joy3.wav", volume=volume)

    def sound_Joy4(self, volume: int = None) -> Response:
        '''
        Play the joy emotion sound with very high intensity.
        
        Parameters:
            volume (int): Volume level (0-100), default is None.
        
        Returns:
            Response: The response object after playing the audio.
        '''
        return self.play_audio(fileName="s_Joy4.wav", volume=volume)

    def sound_Loathing(self, volume: int = None) -> Response:
        '''
        Play the loathing emotion sound.
        
        Parameters:
            volume (int): Volume level (0-100), default is None.
        
        Returns:
            Response: The response object after playing the audio.
        '''
        return self.play_audio(fileName="s_Loathing.wav", volume=volume)

    def sound_Love(self, volume: int = None) -> Response:
        '''
        Play the love emotion sound.
        
        Parameters:
            volume (int): Volume level (0-100), default is None.
        
        Returns:
            Response: The response object after playing the audio.
        '''
        return self.play_audio(fileName="s_Love.wav", volume=volume)

    def sound_PhraseByeBye(self, volume: int = None) -> Response:
        '''
        Play the 'bye bye' phrase sound.
        
        Parameters:
            volume (int): Volume level (0-100), default is None.
        
        Returns:
            Response: The response object after playing the audio.
        '''
        return self.play_audio(fileName="s_PhraseByeBye.wav", volume=volume)

    def sound_PhraseEvilAhHa(self, volume: int = None) -> Response:
        '''
        Play the 'evil ah ha' phrase sound.
        
        Parameters:
            volume (int): Volume level (0-100), default is None.
        
        Returns:
            Response: The response object after playing the audio.
        '''
        return self.play_audio(fileName="s_PhraseEvilAhHa.wav", volume=volume)

    def sound_PhraseHello(self, volume: int = None) -> Response:
        '''
        Play the 'hello' phrase sound.
        
        Parameters:
            volume (int): Volume level (0-100), default is None.
        
        Returns:
            Response: The response object after playing the audio.
        '''
        return self.play_audio(fileName="s_PhraseHello.wav", volume=volume)

    def sound_PhraseNoNoNo(self, volume: int = None) -> Response:
        '''
        Play the 'no no no' phrase sound.
        
        Parameters:
            volume (int): Volume level (0-100), default is None.
        
        Returns:
            Response: The response object after playing the audio.
        '''
        return self.play_audio(fileName="s_PhraseNoNoNo.wav", volume=volume)

    def sound_PhraseOopsy(self, volume: int = None) -> Response:
        '''
        Play the 'oopsy' phrase sound.
        
        Parameters:
            volume (int): Volume level (0-100), default is None.
        
        Returns:
            Response: The response object after playing the audio.
        '''
        return self.play_audio(fileName="s_PhraseOopsy.wav", volume=volume)

    def sound_PhraseOwOwOw(self, volume: int = None) -> Response:
        '''
        Play the 'ow ow ow' phrase sound.
        
        Parameters:
            volume (int): Volume level (0-100), default is None.
        
        Returns:
            Response: The response object after playing the audio.
        '''
        return self.play_audio(fileName="s_PhraseOwOwOw.wav", volume=volume)

    def sound_PhraseOwwww(self, volume: int = None) -> Response:
        '''
        Play the 'owwww' phrase sound.
        
        Parameters:
            volume (int): Volume level (0-100), default is None.
        
        Returns:
            Response: The response object after playing the audio.
        '''
        return self.play_audio(fileName="s_PhraseOwwww.wav", volume=volume)
    
    def sound_PhraseUhOh(self, volume: int = None) -> Response:
        '''
        Play the 'uh oh' phrase sound.
        
        Parameters:
            volume (int): Volume level (0-100), default is None.
        
        Returns:
            Response: The response object after playing the audio.
        '''
        return self.play_audio(fileName="s_PhraseUhOh.wav", volume=volume)
    def sound_Rage(self, volume: int = None) -> Response:
        '''
        Play a sound expressing rage emotion.
        
        Parameters:
            volume (int): Optional volume level (0-100).
        
        Returns:
            Response: The response object after playing the audio.
        '''
        return self.play_audio(fileName="s_Rage.wav", volume=volume)

    def sound_Sadness(self, volume: int = None) -> Response:
        '''
        Play a sound expressing mild sadness (intensity level 1).
        
        Parameters:
            volume (int): Optional volume level (0-100).
        
        Returns:
            Response: The response object after playing the audio.
        '''
        return self.play_audio(fileName="s_Sadness.wav", volume=volume)

    def sound_Sadness2(self, volume: int = None) -> Response:
        '''
        Play a sound expressing moderate sadness (intensity level 2).
        
        Parameters:
            volume (int): Optional volume level (0-100).
        
        Returns:
            Response: The response object after playing the audio.
        '''
        return self.play_audio(fileName="s_Sadness2.wav", volume=volume)

    def sound_Sadness3(self, volume: int = None) -> Response:
        '''
        Play a sound expressing strong sadness (intensity level 3).
        
        Parameters:
            volume (int): Optional volume level (0-100).
        
        Returns:
            Response: The response object after playing the audio.
        '''
        return self.play_audio(fileName="s_Sadness3.wav", volume=volume)

    def sound_Sadness4(self, volume: int = None) -> Response:
        '''
        Play a sound expressing intense sadness (intensity level 4).
        
        Parameters:
            volume (int): Optional volume level (0-100).
        
        Returns:
            Response: The response object after playing the audio.
        '''
        return self.play_audio(fileName="s_Sadness4.wav", volume=volume)

    def sound_Sadness5(self, volume: int = None) -> Response:
        '''
        Play a sound expressing extreme sadness (intensity level 5).
        
        Parameters:
            volume (int): Optional volume level (0-100).
        
        Returns:
            Response: The response object after playing the audio.
        '''
        return self.play_audio(fileName="s_Sadness5.wav", volume=volume)

    def sound_Sadness6(self, volume: int = None) -> Response:
        '''
        Play a sound expressing maximum intensity sadness (intensity level 6).
        
        Parameters:
            volume (int): Optional volume level (0-100).
        
        Returns:
            Response: The response object after playing the audio.
        '''
        return self.play_audio(fileName="s_Sadness6.wav", volume=volume)

    def sound_Sadness7(self, volume: int = None) -> Response:
        '''
        Play a sound expressing ultimate intensity sadness (intensity level 7).
        
        Parameters:
            volume (int): Optional volume level (0-100).
        
        Returns:
            Response: The response object after playing the audio.
        '''
        return self.play_audio(fileName="s_Sadness7.wav", volume=volume)

    def sound_Sleepy(self, volume: int = None) -> Response:
        '''
        Play a mild sleepy state sound (intensity level 1).
        
        Parameters:
            volume (int): Optional volume level (0-100).
        
        Returns:
            Response: The response object after playing the audio.
        '''
        return self.play_audio(fileName="s_Sleepy.wav", volume=volume)

    def sound_Sleepy2(self, volume: int = None) -> Response:
        '''
        Play a moderate sleepy state sound (intensity level 2).
        
        Parameters:
            volume (int): Optional volume level (0-100).
        
        Returns:
            Response: The response object after playing the audio.
        '''
        return self.play_audio(fileName="s_Sleepy2.wav", volume=volume)

    def sound_Sleepy3(self, volume: int = None) -> Response:
        '''
        Play a deep sleepy state sound (intensity level 3).
        
        Parameters:
            volume (int): Optional volume level (0-100).
        
        Returns:
            Response: The response object after playing the audio.
        '''
        return self.play_audio(fileName="s_Sleepy3.wav", volume=volume)

    def sound_Sleepy4(self, volume: int = None) -> Response:
        '''
        Play a very deep sleepy state sound (intensity level 4).
        
        Parameters:
            volume (int): Optional volume level (0-100).
        
        Returns:
            Response: The response object after playing the audio.
        '''
        return self.play_audio(fileName="s_Sleepy4.wav", volume=volume)

    def sound_SleepySnore(self, volume: int = None) -> Response:
        '''
        Play a snoring sound effect during sleep.
        
        Parameters:
            volume (int): Optional volume level (0-100).
        
        Returns:
            Response: The response object after playing the audio.
        '''
        return self.play_audio(fileName="s_SleepySnore.wav", volume=volume)

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
   
