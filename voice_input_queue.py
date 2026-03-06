# -*- coding: utf-8 -*-
"""
Voice Input Queue System
Shared queue for voice transcription results to be used as interactive input
Thread-safe implementation compatible with asyncio
"""

import queue
import threading
import time

class VoiceInputQueue:
    """
    Global voice input queue for interactive communication
    Thread-safe and compatible with asyncio event loops
    """
    def __init__(self):
        self.queue = queue.Queue()
        self.waiting_for_input = False
        self.lock = threading.Lock()
    
    def put(self, text: str):
        """Put transcribed text into the queue (thread-safe)"""
        self.queue.put(text)
        print(f"[VoiceQueue] Input received: \"{text}\"")
    
    def get(self, timeout=None) -> str:
        """
        Get transcribed text from the queue (blocking with polling)
        Uses polling to avoid event loop conflicts
        """
        with self.lock:
            self.waiting_for_input = True
        
        try:
            # Use polling with short timeout to avoid blocking event loop
            end_time = time.time() + (timeout if timeout else 300)
            
            while time.time() < end_time:
                try:
                    # Try to get with very short timeout
                    text = self.queue.get(timeout=0.1)
                    return text
                except queue.Empty:
                    # Continue polling
                    continue
            
            # Timeout reached
            print("[Warning] Voice input timeout, returning APPROVE")
            return "APPROVE"
            
        finally:
            with self.lock:
                self.waiting_for_input = False
    
    def is_waiting(self) -> bool:
        """Check if system is waiting for input"""
        with self.lock:
            return self.waiting_for_input
    
    def clear(self):
        """Clear all pending inputs"""
        while not self.queue.empty():
            try:
                self.queue.get_nowait()
            except queue.Empty:
                break

# Global instance
_global_voice_queue = VoiceInputQueue()

def get_voice_input_queue() -> VoiceInputQueue:
    """Get the global voice input queue instance"""
    return _global_voice_queue

def voice_input_func(prompt: str) -> str:
    """
    Input function for UserProxyAgent
    Waits for voice input from the queue using polling to avoid event loop conflicts
    
    Args:
        prompt: The prompt to display to the user
        
    Returns:
        Transcribed voice input text
    """
    print(f"\n{'='*60}")
    print("[Voice Input Required]")
    print(f"{'='*60}")
    print(f"{prompt}")
    print("\n🎤 Press and hold 'c' to speak your response...")
    print("⚡ Press 'B' for quick APPROVE (no recording needed)")
    print("💡 Or say 'APPROVE' to approve and continue")
    print(f"{'='*60}\n")
    
    queue_obj = get_voice_input_queue()
    
    # Use polling-based get to avoid event loop conflicts
    text = queue_obj.get(timeout=300)  # 5 minutes timeout
    return text
