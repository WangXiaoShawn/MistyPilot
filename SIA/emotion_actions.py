# -*- coding: utf-8 -*-
### 删除所有 loop 的单次动作版本
import time                             ### time for sleeps
import json                             ### for config loading
import os                               ### for path operations
from .CUBS_Misty_Only_Raw_Actions import Robot            ### your Misty wrapper

# Global configuration cache
_config_cache = None

def get_misty_ip(config_path: str = "./MistyPilot_config.json") -> str:
    """
    Get Misty robot IP from config file.
    
    Parameters:
        config_path: Path to the configuration JSON file
        
    Returns:
        str: Misty robot IP address
    """
    global _config_cache
    if _config_cache is None:
        # Handle relative path from the module location
        if not os.path.isabs(config_path):
            # Get the directory of this file
            current_dir = os.path.dirname(os.path.abspath(__file__))
            # Go up one level to project root
            project_root = os.path.dirname(current_dir)
            config_path = os.path.join(project_root, os.path.basename(config_path))
        
        with open(config_path, 'r', encoding='utf-8') as f:
            _config_cache = json.load(f)
    
    return _config_cache.get("misty_ip", "127.0.0.1")

def perform_neutral_action(misty_ip, pause_before_reset=1.0):
    """
    中立/无情感 (Neutral): 
    第九个动作，作为所有情绪的基准。
    """
    misty = Robot(misty_ip)
    try:
        # 直接调用你类中定义的 return_to_normal 逻辑
        misty.change_led(red=255, green=255, blue=255)
        misty.emotion_DefaultContent()
        misty.move_arms(leftArmPosition=90, rightArmPosition=90, duration=0.5)
        misty.move_head(pitch=0, yaw=0, roll=0, duration=0.5)
        time.sleep(pause_before_reset)
    finally:
        misty.return_to_normal()
        

def perform_arousal_action(misty_ip, pause_before_reset=1.0):
    """
    激动（Arousal）：一次性表达，去掉循环
    """
    misty = Robot(misty_ip)             ### 实例化
    try:
        misty.emotion_Amazement(alpha=1.0)                                              ### 表情
        misty.transition_led(255, 255, 0, 255, 50, 0, transition_type="Breathe", time_ms=500)  ### LED
        misty.move_head(0, -30, 0)         
        misty.drive_time(linearVelocity=40, angularVelocity=0, timeMs=200) ### 
        time.sleep(0.2)
        misty.move_arms(leftArmPosition=-45, rightArmPosition=-45,
                        leftArmVelocity=100, rightArmVelocity=100,
                        duration=0.5, units="degrees")  
        misty.drive_time(linearVelocity=40, angularVelocity=0, timeMs=200) 
        time.sleep(0.15)
        ### 双臂上举一次                                                                 ### 缓冲
        time.sleep(pause_before_reset*0.7)                                                   ### 停留
    finally:
        misty.return_to_normal()                                                         ### 复位

def perform_contentment_action(misty_ip: str, pause_before_reset: float = 1.0) -> None:
    """
    满足（Contentment）：极简一次性表达（无循环、低动量、无底盘移动）
    """
    misty = Robot(misty_ip)  ### 实例化
    try:
        misty.emotion_Admiration(alpha=1.0)  ### 表情：满足/安稳
        misty.transition_led(180, 220, 255, 255, 255, 255,
                             transition_type="Breathe", time_ms=1500)  ### LED：淡蓝↔白 慢呼吸

        misty.move_arms(leftArmPosition=35, rightArmPosition=45,
                        leftArmVelocity=28, rightArmVelocity=30,
                        duration=0.9, units="degrees")  ### 双臂张开一次（开放但不夸张）

        misty.move_head(pitch=-10, roll=0, yaw=0,
                        velocity=30, duration=0.8, units="degrees")  ### 头部轻仰，正向注视
        time.sleep(0.9)  ### 缓冲（略大于 duration）
        time.sleep(pause_before_reset*0.7)  ### 停留后准备复位
    finally:### 缓冲
        misty.return_to_normal()  ### 统一复位（表情/LED/电机状态）

def perform_depression_action(misty_ip: str, pause_before_reset: float = 1.0) -> None:
    """
    抑郁（Depression）：极简一次性表达（无循环、无多余等待、无底盘移动）
    核心信号：悲伤脸 + 手臂自然下垂 + 低头且避开直视
    """
    misty = Robot(misty_ip)                                   ### 实例化
    try:
        misty.emotion_Grief(alpha=1.0)                        ### 面部：悲伤/哀伤

        misty.move_arms(leftArmPosition=30, rightArmPosition=30,
                        leftArmVelocity=20, rightArmVelocity=20,
                        duration=0.9, units="degrees")        ### 手臂：自然下垂到位（轻、慢）

        misty.move_head(0,0,0)  ### 头部：低头 + 侧避视线

        time.sleep(pause_before_reset*0.7)                        ### 停留后准备复位（只保留这一次等待）
    finally:
        misty.return_to_normal()                                                  ### 统一复位

def perform_excitement_action(misty_ip: str, pause_before_reset: float = 1.0) -> None:
    """
    兴奋（Excitement）：去掉所有循环，保留一轮“手臂交替 + 晃头 + 轻驱动”
    """
    misty = Robot(misty_ip)            ### 实例化
    try:
        misty.emotion_Amazement(alpha=1.0)                                          ### 开场表情
        misty.transition_led(255, 0, 0, 100, 0, 0, transition_type="Blink", time_ms=200)  ### LED

        misty.emotion_Joy2(alpha=1.0)                                               ### 兴奋表情一次
        misty.move_arms(leftArmPosition=-70, rightArmPosition=40,                   ### 交替 1
                        leftArmVelocity=100, rightArmVelocity=100,
                        duration=0.25, units="degrees")
        time.sleep(0.25)
        misty.move_arms(leftArmPosition=40, rightArmPosition=-70,                   ### 交替 2
                        leftArmVelocity=100, rightArmVelocity=100,
                        duration=0.25, units="degrees")
        time.sleep(0.25)

        misty.move_arms(leftArmPosition=0, rightArmPosition=0,                      ### 回中立
                        leftArmVelocity=80, rightArmVelocity=80,
                        duration=0.4, units="degrees")

        misty.move_head(pitch=0, roll=-20, yaw=0,                                   ### 晃头一次
                        velocity=80, duration=0.4, units="degrees")
        misty.drive_time(linearVelocity=40, angularVelocity=0, timeMs=150)          ### 轻驱动
        time.sleep(0.45)
        misty.move_head(pitch=0, roll=0, yaw=0,
                        velocity=80, duration=0.35, units="degrees")

        misty.emotion_Amazement(alpha=1.0)                                          ### 收尾表情
        time.sleep(pause_before_reset*0.7)
    finally:
        misty.return_to_normal()                                                    ### 复位

def perform_misery_action(misty_ip: str, pause_before_reset: float = 1.0) -> None:
    """
    “Misery”版本（原设计是高举+摇头）：删除循环，仅左右各一次
    """
    misty = Robot(misty_ip)            ### 实例化
    try:
        misty.emotion_Sadness(alpha=1.0)                                              ### 开场表情
        misty.transition_led(255, 0, 0, 100, 0, 0, transition_type="Blink", time_ms=200)  ### LED

        misty.move_arms(leftArmPosition=-29, rightArmPosition=-29,                 ### 双臂到顶一次
                        leftArmVelocity=100, rightArmVelocity=100,
                        duration=0.6, units="degrees")
        time.sleep(0.7)

        misty.move_head(0, -20, 0)                                                ### 左侧一次
        time.sleep(0.30)
        misty.move_head(0, 0, 0)
        time.sleep(0.30)
        misty.move_head(0, 20, 0)                                                 ### 右侧一次
        time.sleep(0.30)
        misty.move_head(0, 0, 0)
        time.sleep(0.30)

        misty.emotion_Fear(alpha=1.0)                                             ### 收尾表情
        time.sleep(pause_before_reset*0.7)
    finally:
        misty.return_to_normal()                                                   ### 复位

        
def perform_pleasure_action(misty_ip: str, pause_before_reset: float = 1.0) -> None:
    """
    愉悦（Pleasure）：极简一次性表达（无循环、无多余等待、低动量）
    核心信号：爱意表情 + 柔和LED呼吸 + 头微仰 + 双臂小幅上举
    """
    misty = Robot(misty_ip)  ### 实例化
    try:
        misty.emotion_Love(alpha=1.0)  ### 表情：愉悦/喜爱
        misty.transition_led(255, 140, 180, 255, 200, 80,
                             transition_type="Breathe", time_ms=1200)  ### LED：柔粉↔暖黄
        misty.drive_time(linearVelocity=20, angularVelocity=0, timeMs=250)         ### 轻微前冲
        time.sleep(0.3)
        misty.drive_time(linearVelocity=0, angularVelocity=-6, timeMs=800) 
        time.sleep(0.3)
        misty.move_head(pitch=-6, roll=0, yaw=0,
                        velocity=35, duration=0.8, units="degrees")  ### 头：微仰正视（友好）
        misty.move_arms(leftArmPosition=-20, rightArmPosition=20,
                        leftArmVelocity=35, rightArmVelocity=35,
                        duration=0.8, units="degrees")  ### 手臂：小幅上举（开放）
        time.sleep(0.8)
        misty.drive_time(linearVelocity=20, angularVelocity=0, timeMs=250)         ### 轻微前冲
        time.sleep(0.3)
        misty.drive_time(linearVelocity=0, angularVelocity=-6, timeMs=800) 
        time.sleep(pause_before_reset*0.7)  ### 停留后复位（仅保留这一处等待）
    finally:
        misty.return_to_normal()  ### 统一复位（表情/头/臂/LED）
def perform_sleepiness_action(misty_ip: str, pause_before_reset: float = 1.0) -> None:
    """
    困倦（Sleepiness）：极简一次性表达（内联常量，去掉参数块）
    """
    misty = Robot(misty_ip)  ### 实例化
    try:
        misty.emotion_Sleepy(alpha=1.0)  ### 表情
        misty.transition_led(20, 40, 80, 0, 0, 0,
                             transition_type="Breathe", time_ms=1800)  ### LED：深蓝↔黑 慢呼吸

        misty.move_arms(leftArmPosition=35, rightArmPosition=34,
                        leftArmVelocity=25, rightArmVelocity=25,
                        duration=1.0, units="degrees")  ### 手臂下垂一次
        time.sleep(1.0)

        misty.move_head(pitch=20, roll=0, yaw=0,
                        velocity=22, duration=1.2, units="degrees")  ### 低头到基线
        time.sleep(1.2)

        misty.move_head(5, 0, 0)   ### 单次更低一点
        time.sleep(0.9)
        misty.move_head(0, 0, 0)   ### 回基线
        time.sleep(0.9)

        misty.move_head(5, 0, 0)   ### 收尾更“困”
        misty.emotion_SleepingZZZ(alpha=1.0)  ### 熟睡表情
        time.sleep(pause_before_reset*0.7)  ### 注意：确保 pause_before_reset >= 1
    finally:
        misty.return_to_normal()


def perform_distress_action(misty_ip: str, pause_before_reset: float = 1.0) -> None:
    """
    焦灼/痛苦（Distress）：极简一次性表达（无循环）
    顺序：关切表情 → 双臂上举 → 头到基线 → 双臂再扩张 → 头微下 → 手臂回高举 → 头回更轻
    """
    misty = Robot(misty_ip)
    try:
        misty.emotion_ApprehensionConcerned(alpha=1.0)
        misty.transition_led(255, 140, 0, 180, 0, 0, transition_type="Blink", time_ms=260)

        misty.move_arms(leftArmPosition=-29, rightArmPosition=-29,
                        leftArmVelocity=70, rightArmVelocity=70,
                        duration=0.6, units="degrees")
        time.sleep(0.15)  # 0.6 + 0.15

        misty.move_head(pitch=10, roll=0, yaw=0,
                        velocity=30, duration=0.7, units="degrees")
        time.sleep(0.15)  # 0.7 + 0.15

        misty.move_arms(leftArmPosition=-40, rightArmPosition=-40,
                        leftArmVelocity=70, rightArmVelocity=70,
                        duration=0.35, units="degrees")
        time.sleep(0.15)  # 0.35 + 0.15

        misty.move_head(pitch=12, roll=0, yaw=0,
                        velocity=30, duration=0.6, units="degrees")
        time.sleep(0.15)  # 0.6 + 0.15

        misty.move_arms(leftArmPosition=-29, rightArmPosition=-29,
                        leftArmVelocity=70, rightArmVelocity=70,
                        duration=0.35, units="degrees")
        time.sleep(0.15)  # 0.35 + 0.15

        misty.move_head(pitch=8, roll=0, yaw=0,
                        velocity=30, duration=0.6, units="degrees")
        time.sleep(0.15)  # 0.6 + 0.15

        time.sleep(pause_before_reset*0.7)
    finally:
        misty.return_to_normal()

if __name__ == "__main__":
    # Automatically load Misty IP from config file
    try:
        misty_ip = get_misty_ip()
        print(f"Loaded Misty IP from config: {misty_ip}")
        
        # Test one emotion action
        print("Performing neutral action...")
        perform_neutral_action(misty_ip, pause_before_reset=1.5)
        print("Action completed!")

        
    except FileNotFoundError:
        print("Error: MistyPilot_config.json not found!")
        print("Please make sure the config file exists in the project root directory.")
    except KeyError:
        print("Error: 'misty_ip' not found in config file!")
    except Exception as e:
        print(f"Error: {e}")