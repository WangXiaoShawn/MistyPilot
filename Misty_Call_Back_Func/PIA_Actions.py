
import time, threading                                  ### 基础计时与并行
from typing import Optional                             ### 类型注解
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from CUBS_Misty_Only_Raw_Actions import Robot  
from typing import Optional, Literal                     ### 类型注解


def perform_rage(misty_ip: str, api_key: Optional[str] = None) -> None:
    """
    - Rage4 表情 + 红灯快速闪烁 + 怒吼音效
    - 并行：双臂交替上下 & 头部左右大幅摇（含轻微前倾的攻击性姿态）
    - move_* 不传 duration，由系统自行计算
    - 子动作仅在本函数内部定义，不对外复用
    """
    misty = Robot(misty_ip)                                ### construct robot
    try:                                                   ### ensure cleanup
        misty.emotion_Rage4(alpha=1.0)                    ### face: Rage4
        misty.transition_led(255, 0, 0, 80, 0, 0,         ### LED: red ↔ dark red blink
                             transition_type="Blink",
                             time_ms=150)                  ### fast blink             ### fallback

        def _arms_alternate_loop():                       ### inner: arms alternate
            cycles = 4                                    ### cycles
            pause = 0.25                                  ### pause per step
            for _ in range(cycles):                       ### loop
                misty.move_arms(leftArmPosition=-29, rightArmPosition=90,
                                leftArmVelocity=100, rightArmVelocity=100,
                                units="degrees")          ### left up, right down
                time.sleep(pause)                         ### dwell
                misty.move_arms(leftArmPosition=90, rightArmPosition=-29,
                                leftArmVelocity=100, rightArmVelocity=100,
                                units="degrees")          ### left down, right up
                time.sleep(pause)                         ### dwell

        def _head_left_right():                           ### inner: head L↔R
            yaw_deg  = 78                                 ### yaw amplitude (≤81 safe)
            pitch_deg = 10                                ### slight forward tilt
            cycles   = 4                                  ### cycles
            pause    = 0.30                               ### dwell
            amp = max(0.0, min(abs(yaw_deg), 81.0))       ### clamp yaw
            pit = max(-40.0, min(pitch_deg, 26.0))        ### clamp pitch
            for _ in range(cycles):                       ### loop
                misty.move_head(pitch=pit, roll=0, yaw=+amp,
                                velocity=100, units="degrees")  ### look left
                time.sleep(pause)                         ### dwell
                misty.move_head(pitch=pit, roll=0, yaw=-amp,
                                velocity=100, units="degrees")  ### look right
                time.sleep(pause)                         ### dwell
            misty.move_head(pitch=0, roll=0, yaw=0,
                            velocity=100, units="degrees")      ### recenter

        t1 = threading.Thread(target=_arms_alternate_loop)      ### thread: arms
        t2 = threading.Thread(target=_head_left_right)           ### thread: head
        t1.start(); t2.start()                                   ### start both
        t1.join(); t2.join()                                     ### wait both
        time.sleep(5)                                          ### settle
    finally:
        misty.return_to_normal()    ### 你的 Robot 封装

def perform_happy(misty_ip: str, api_key: Optional[str] = None) -> None:
    """
    - Love 表情 + LED 黄↔白呼吸 + 欢呼音效
    - 并行：手臂交替挥动 & 头部纯 yaw 小颤抖（无点头/无侧倾）
    - move_* 不传 duration，由系统自行计算
    - 子动作在本函数内部定义，不对外复用
    """
    misty = Robot(misty_ip)                              ### 构造机器人
    try:                                                 ### 保护块：异常也会做收尾
        misty.emotion_Love(alpha=1.0)                    ### 面部：爱心/恋爱表情
        misty.transition_led(255,215,0, 255,255,255,     ### LED：金黄↔白 呼吸
                              transition_type="Breathe", time_ms=700)  ### 柔和过渡
      

        def _arms_wave_alternate():                      ### 内部子动作：双臂交替挥动
            cycles = 4                                   ### 循环次数
            pause = 0.22                                 ### 每步停留
            for _ in range(cycles):                      ### 循环
                misty.move_arms(leftArmPosition=-29, rightArmPosition=60,
                                leftArmVelocity=100, rightArmVelocity=90,
                                units="degrees")         ### 左上右半下
                time.sleep(pause)                        ### 短停
                misty.move_arms(leftArmPosition=60, rightArmPosition=-29,
                                leftArmVelocity=90, rightArmVelocity=100,
                                units="degrees")         ### 左半下右上
                time.sleep(pause)                        ### 短停
            misty.move_arms(leftArmPosition=-10, rightArmPosition=-10,
                            leftArmVelocity=80, rightArmVelocity=80,
                            units="degrees")             ### 收个小弹跳

        def _head_yaw_shiver():                          ### 内部子动作：仅左右小颤抖（纯 yaw）
            yaw_deg = 10.0                               ### 目标幅度（度）
            cycles = 8                                 ### 往返次数
            pause = 0.10                                 ### 每步停留
            velocity = 100                               ### 头部速度百分比
            amp = max(3.0, min(abs(yaw_deg), 18.0))      ### 幅度夹紧 3°~18°（安全/可见）
            for _ in range(cycles):                      ### 快速往返
                misty.move_head(pitch=0, roll=0, yaw=+amp,
                                velocity=velocity, units="degrees")  ### 向一侧摆
                time.sleep(pause)                        ### 短停
                misty.move_head(pitch=0, roll=0, yaw=-amp,
                                velocity=velocity, units="degrees")  ### 反向摆
                time.sleep(pause)                        ### 短停
            misty.move_head(pitch=0, roll=0, yaw=0,
                            velocity=velocity, units="degrees")      ### 回中

        t1 = threading.Thread(target=_arms_wave_alternate)           ### 线程1：手臂
        t2 = threading.Thread(target=_head_yaw_shiver)                ### 线程2：头部
        t1.start(); t2.start()                                        ### 启动并行
        t1.join(); t2.join()                                          ### 等待结束
        time.sleep(5)                                               ### 稍作停留
    finally:
        misty.return_to_normal()                           
        
        

def perform_sad(misty_ip: str, api_key: Optional[str] = None) -> None:
    """
    - 面部：Sadness 表情；LED：蓝↔暗蓝呼吸；声音：Sadness3（降级 Sadness）
    - 并行：手臂下垂状态下的小幅左右交替；头部保持下视，仅做左右慢摆（无点头、无侧倾）
    - move_* 不传 duration，由底层自行计算；内部子动作仅在本函数里定义
    """
    misty = Robot(misty_ip)                                    ### 构造机器人
    try:                                                       ### 异常保护
        misty.emotion_Sadness(alpha=1.0)                       ### 表情：伤心
        misty.transition_led(0, 120, 255, 0, 0, 40,            ### LED：蓝↔暗蓝 呼吸
                             transition_type="Breathe", 
                             time_ms=900)                      ### 柔和、偏慢                                 ### 没音效就静默

        def _arms_sad_swing():                                 ### 子动作1：手臂小幅交替（整体下垂）
            cycles = 4                                         ### 循环次数
            pause = 0.35                                       ### 每步停留
            for _ in range(cycles):                            ### 循环
                misty.move_arms(leftArmPosition=85,            ### 左臂稍抬（仍接近下垂）
                                rightArmPosition=90,           ### 右臂完全下垂
                                leftArmVelocity=45, 
                                rightArmVelocity=45,
                                units="degrees")               ### 使用角度制
                time.sleep(pause)                              ### 短停
                misty.move_arms(leftArmPosition=90,            ### 左臂下垂
                                rightArmPosition=85,           ### 右臂稍抬
                                leftArmVelocity=45, 
                                rightArmVelocity=45,
                                units="degrees")               ### 使用角度制
                time.sleep(pause)                              ### 短停
            misty.move_arms(leftArmPosition=90,                ### 收尾：两臂都回到下垂
                            rightArmPosition=90,
                            leftArmVelocity=40, 
                            rightArmVelocity=40,
                            units="degrees")                   ### 使用角度制

        def _head_sad_sway():                                  ### 子动作2：头部下视并左右慢摆（无点头/侧倾）
            yaw = 8.0                                          ### 左右摆幅（度）
            pitch_down = 18.0                                  ### 下视角（度，正值=下）
            cycles = 4                                         ### 往返次数
            pause = 0.35                                       ### 每步停留
            velocity = 60                                      ### 速度偏慢
            yaw = max(3.0, min(yaw, 18.0))                     ### 限幅 3°~18°
            pitch = max(-40.0, min(pitch_down, 26.0))          ### 下视角限幅
            misty.move_head(pitch=pitch, roll=0, yaw=0,        ### 先落到下视中位
                            velocity=velocity, units="degrees")### 仅传速度与单位
            for _ in range(cycles):                            ### 循环左右摆
                misty.move_head(pitch=pitch, roll=0, yaw=+yaw,
                                velocity=velocity, units="degrees")  ### 向左
                time.sleep(pause)                              ### 短停
                misty.move_head(pitch=pitch, roll=0, yaw=-yaw,
                                velocity=velocity, units="degrees")  ### 向右
                time.sleep(pause)                              ### 短停
            misty.move_head(pitch=0, roll=0, yaw=0,            ### 复位到正中
                            velocity=velocity, units="degrees")### 仅调头部

        t1 = threading.Thread(target=_arms_sad_swing)          ### 线程1：手臂
        t2 = threading.Thread(target=_head_sad_sway)           ### 线程2：头部
        t1.start(); t2.start()                                 ### 并行启动
        t1.join(); t2.join()                                   ### 等待结束
        time.sleep(4)                                        ### 稍作停留
    finally:
        misty.return_to_normal()   ### 统一还原（表情/灯/手/头）
        
# -*- coding: utf-8 -*-
### 恐惧 / 惊讶 / 厌恶 —— 单函数封装版（内部并行动作，move_* 不传 duration）
import time, threading                                           ### 计时与并行 ###
from typing import Optional                                      ### 类型注解 ###
from CUBS_Misty_Only_Raw_Actions import Robot                    ### 你的 Robot 封装 ###

def perform_fear(misty_ip: str, api_key: Optional[str] = None) -> None:
    """
    恐惧（Fear）：
      - 表情：Fear；LED：蓝青↔深蓝 呼吸；声音：Fear（降级 DisorientedConfused*）
      - 并行：双臂轻微“发抖” + 头部轻微左右快速小颤抖（纯 yaw，保持轻微下视）
    """
    misty = Robot(misty_ip)                                      ### 构造机器人 ###
    try:                                                         ### 保护块 ###
        misty.emotion_Fear(alpha=1.0)                            ### 面部：恐惧 ###
        misty.transition_led(0, 170, 255, 0, 60, 120,            ### LED：蓝青↔深蓝 呼吸 ###
                             transition_type="Breathe", time_ms=500)  ### 呼吸稍快 ###
        try:
            misty.sound_Fear(volume=90)                          ### 恐惧音效 ###
        except Exception:
            try:
                misty.sound_DisorientedConfused4(volume=80)      ### 降级：迷惘/慌张 ###
            except Exception:
                pass                                             ### 无音效则静默 ###

        def _arms_fear_tremble():                                ### 子动作1：手臂颤抖 ###
            cycles, pause = 10, 0.09                             ### 频率略快 ###
            a1, a2 = -22, -16                                    ### 上臂两档（-29~-10 安全可见）###
            for _ in range(cycles):                               ### 循环 ###
                misty.move_arms(leftArmPosition=a1, rightArmPosition=a2,
                                leftArmVelocity=100, rightArmVelocity=100,
                                units="degrees")                  ### 档位1 ###
                time.sleep(pause)                                 ### 短停 ###
                misty.move_arms(leftArmPosition=a2, rightArmPosition=a1,
                                leftArmVelocity=100, rightArmVelocity=100,
                                units="degrees")                  ### 档位2（交错）###
                time.sleep(pause)                                 ### 短停 ###
            misty.move_arms(leftArmPosition=-20, rightArmPosition=-20,
                            leftArmVelocity=80, rightArmVelocity=80,
                            units="degrees")                      ### 收敛到中等上举 ###

        def _head_fear_shiver():                                  ### 子动作2：头部小颤抖（纯 yaw）###
            yaw_deg, pitch_down = 8.0, 10.0                       ### 左右幅度 & 下视角 ###
            cycles, pause, velocity = 16, 0.08, 100               ### 次数多、频率快 ###
            amp = max(3.0, min(abs(yaw_deg), 18.0))               ### 限幅 ###
            pitch = max(-40.0, min(pitch_down, 26.0))             ### 限幅 ###
            misty.move_head(pitch=pitch, roll=0, yaw=0,
                            velocity=velocity, units="degrees")    ### 先落下视中位 ###
            for _ in range(cycles):                                ### 快速往返 ###
                misty.move_head(pitch=pitch, roll=0, yaw=+amp,
                                velocity=velocity, units="degrees")### 左 ###
                time.sleep(pause)                                  ### 停 ###
                misty.move_head(pitch=pitch, roll=0, yaw=-amp,
                                velocity=velocity, units="degrees")### 右 ###
                time.sleep(pause)                                  ### 停 ###
            misty.move_head(pitch=0, roll=0, yaw=0,
                            velocity=velocity, units="degrees")    ### 回中 ###

        t1 = threading.Thread(target=_arms_fear_tremble)           ### 线程：手臂 ###
        t2 = threading.Thread(target=_head_fear_shiver)            ### 线程：头部 ###
        t1.start(); t2.start()                                     ### 并行启动 ###
        t1.join(); t2.join()                                       ### 等待结束 ###
        time.sleep(4)                                            ### 稍停 ###
    finally:
        misty.return_to_normal()                                    ### 统一复位 ###


def perform_surprise(misty_ip: str, api_key: Optional[str] = None) -> None:
    """
    惊讶（Surprise）：
      - 表情：Surprise；LED：白↔青 快速闪烁；声音：Amazement2（降级 Awe2 / PhraseUhOh）
      - 并行：双臂“猛地抬起/半落”循环 + 头部快速大幅左右查看（轻微抬头）
    """
    misty = Robot(misty_ip)                                       ### 构造机器人 ###
    try:                                                          ### 保护块 ###
        misty.emotion_Surprise(alpha=1.0)                         ### 面部：惊讶 ###
        misty.transition_led(255, 255, 255, 0, 220, 255,          ### LED：白↔青 速闪 ###
                             transition_type="Blink", time_ms=180) ### 瞬时反应感 ###
                ### 回退短语 ###

        def _arms_surprise_burst():                               ### 子动作1：双臂骤抬循环 ###
            cycles, pause_up, pause_dn = 3, 0.18, 0.20            ### 次数与停顿 ###
            for _ in range(cycles):                                ### 循环 ###
                misty.move_arms(leftArmPosition=-25, rightArmPosition=-25,
                                leftArmVelocity=100, rightArmVelocity=100,
                                units="degrees")                   ### 同步迅速上举 ###
                time.sleep(pause_up)                               ### 短停 ###
                misty.move_arms(leftArmPosition=45, rightArmPosition=45,
                                leftArmVelocity=90, rightArmVelocity=90,
                                units="degrees")                   ### 半落，保持张开感 ###
                time.sleep(pause_dn)                               ### 短停 ###
            misty.move_arms(leftArmPosition=-15, rightArmPosition=-15,
                            leftArmVelocity=80, rightArmVelocity=80,
                            units="degrees")                       ### 收尾：略上举待机 ###

        def _head_surprise_scan():                                ### 子动作2：快速大幅左右看 ###
            yaw_deg, pitch_up = 35.0, -8.0                        ### 大幅左右 + 轻微抬头 ###
            cycles, pause, velocity = 3, 0.18, 100                ### 反应性强 ###
            amp = max(10.0, min(abs(yaw_deg), 45.0))              ### 限幅（惊讶更大）###
            pitch = max(-40.0, min(pitch_up, 26.0))               ### 限幅 ###
            misty.move_head(pitch=pitch, roll=0, yaw=0,
                            velocity=velocity, units="degrees")    ### 抬头中位 ###
            for _ in range(cycles):                                ### 循环 ###
                misty.move_head(pitch=pitch, roll=0, yaw=+amp,
                                velocity=velocity, units="degrees")### 快看左 ###
                time.sleep(pause)                                  ### 停 ###
                misty.move_head(pitch=pitch, roll=0, yaw=-amp,
                                velocity=velocity, units="degrees")### 快看右 ###
                time.sleep(pause)                                  ### 停 ###
            misty.move_head(pitch=0, roll=0, yaw=0,
                            velocity=velocity, units="degrees")    ### 回中 ###

        t1 = threading.Thread(target=_arms_surprise_burst)         ### 线程：手臂 ###
        t2 = threading.Thread(target=_head_surprise_scan)          ### 线程：头部 ###
        t1.start(); t2.start()                                     ### 并行启动 ###
        t1.join(); t2.join()                                       ### 等待结束 ###
        time.sleep(4)                                            ### 稍停 ###
    finally:
        misty.return_to_normal()                                    ### 统一复位 ###


def perform_disgust(misty_ip: str, api_key: Optional[str] = None) -> None:
    """
    厌恶（Disgust）：
      - 表情：Disgust；LED：绿↔橄榄绿 呼吸；声音：Disgust3（降级 Disgust2/Disgust）
      - 并行：单臂/双臂交替“甩开”小动作 + 头部带轻微侧倾的“别开脸”（yaw+roll）
    """
    misty = Robot(misty_ip)                                       ### 构造机器人 ###
    try:                                                          ### 保护块 ###
        misty.emotion_Disgust(alpha=1.0)                          ### 面部：厌恶 ###
        misty.transition_led(0, 180, 0, 60, 90, 0,                ### LED：绿↔橄榄绿 呼吸 ###
                             transition_type="Breathe", time_ms=800)### 稍慢、嫌弃感 ###                                     ### 静默 ###

        def _arms_disgust_flick():                                ### 子动作1：甩开/拨开 ###
            cycles, pause = 4, 0.28                               ### 次数与停顿 ###
            for _ in range(cycles):                                ### 循环 ###
                misty.move_arms(leftArmPosition=70, rightArmPosition=85,
                                leftArmVelocity=90, rightArmVelocity=90,
                                units="degrees")                   ### 左略外摆，右下垂 ###
                time.sleep(pause)                                  ### 停 ###
                misty.move_arms(leftArmPosition=85, rightArmPosition=70,
                                leftArmVelocity=90, rightArmVelocity=90,
                                units="degrees")                   ### 交换（像拨开）###
                time.sleep(pause)                                  ### 停 ###
            misty.move_arms(leftArmPosition=90, rightArmPosition=90,
                            leftArmVelocity=80, rightArmVelocity=80,
                            units="degrees")                       ### 收尾：双臂下垂 ###

        def _head_disgust_turnaway():                              ### 子动作2：别开脸（yaw+roll）###
            yaw_deg, roll_deg, pitch_hold = 20.0, 10.0, 5.0        ### 转头幅度/侧倾/微低头 ###
            cycles, pause, velocity = 3, 0.28, 70                  ### 慢一些，嫌弃 ###
            yaw = max(8.0, min(abs(yaw_deg), 30.0))                ### 限幅 ###
            roll = max(5.0, min(abs(roll_deg), 15.0))              ### 限幅 ###
            pitch = max(-40.0, min(pitch_hold, 26.0))              ### 限幅 ###
            for _ in range(cycles):                                 ### 循环 ###
                misty.move_head(pitch=pitch, roll=+roll, yaw=+yaw,
                                velocity=velocity, units="degrees") ### 左侧别脸 ###
                time.sleep(pause)                                   ### 停 ###
                misty.move_head(pitch=pitch, roll=-roll, yaw=-yaw,
                                velocity=velocity, units="degrees") ### 右侧别脸 ###
                time.sleep(pause)                                   ### 停 ###
            misty.move_head(pitch=0, roll=0, yaw=0,
                            velocity=velocity, units="degrees")     ### 回中 ###

        t1 = threading.Thread(target=_arms_disgust_flick)           ### 线程：手臂 ###
        t2 = threading.Thread(target=_head_disgust_turnaway)        ### 线程：头部 ###
        t1.start(); t2.start()                                      ### 并行启动 ###
        t1.join(); t2.join()                                        ### 等待结束 ###
        time.sleep(4)                                             ### 稍停 ###
    finally:
        misty.return_to_normal()    
        
def perform_wave_once_right(misty_ip: str, api_key: Optional[str] = None) -> None:
    """右手高举一次（最大幅度上举 → 停留2s → 略放），伴随头部右看"""
    misty = Robot(misty_ip)               ### 构造机器人
    try:
        # --- 头部先朝右 ---
        misty.move_head(pitch=0, roll=0, yaw=12, velocity=95, units="degrees")
        time.sleep(0.2)

        # --- 右手最大幅度上举 ---
        misty.move_arms(leftArmPosition=90,        ### 左臂保持下垂
                        rightArmPosition=-29,      ### -29° 是 Misty 右臂最大安全上举角度
                        leftArmVelocity=60,
                        rightArmVelocity=100,
                        units="degrees")
        time.sleep(2.0)                 ### 在最高点停留 2 秒

        # --- 右手略放，形成挥手 ---
        misty.move_arms(leftArmPosition=90,
                        rightArmPosition=-10,      ### 放下一些但仍抬着
                        leftArmVelocity=60,
                        rightArmVelocity=90,
                        units="degrees")
        time.sleep(0.3)

        # --- 头部回正，手臂友好待机 ---
        misty.move_head(pitch=0, roll=0, yaw=0, velocity=95, units="degrees")
        misty.move_arms(leftArmPosition=90,
                        rightArmPosition=-15,      ### 右臂保持略上举，表示友好
                        leftArmVelocity=70,
                        rightArmVelocity=80,
                        units="degrees")
        time.sleep(0.3)
    finally:
        misty.return_to_normal()      ### 统一复位（表情/灯/手/头）




def perform_take_photo_wave_once_right(misty_ip: str, api_key: Optional[str] = None) -> None:
    """右手高举一次（最大幅度上举 → 停留2s → 略放），伴随头部右看"""
    misty = Robot(misty_ip)               ### 构造机器人
    try:
        # --- 头部先朝右 ---
  

        # --- 右手最大幅度上举 ---
        misty.move_arms(leftArmPosition=90,        ### 左臂保持下垂
                        rightArmPosition=-29,      ### -29° 是 Misty 右臂最大安全上举角度
                        leftArmVelocity=60,
                        rightArmVelocity=100,
                        units="degrees")
        time.sleep(2.0)                 ### 在最高点停留 2 秒

        # --- 右手略放，形成挥手 ---
        misty.move_arms(leftArmPosition=90,
                        rightArmPosition=-10,      ### 放下一些但仍抬着
                        leftArmVelocity=60,
                        rightArmVelocity=90,
                        units="degrees")
        time.sleep(0.3)

        # --- 头部回正，手臂友好待机 ---
        misty.move_head(pitch=0, roll=0, yaw=0, velocity=95, units="degrees")
        misty.move_arms(leftArmPosition=90,
                        rightArmPosition=-15,      ### 右臂保持略上举，表示友好
                        leftArmVelocity=70,
                        rightArmVelocity=80,
                        units="degrees")
        time.sleep(0.3)
    finally:
        misty.return_to_normal()      ### 统一复位（表情/灯/手/头）


