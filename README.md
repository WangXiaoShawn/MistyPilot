# MistyPilot

An intelligent robot control system based on AutoGen, specifically designed for Misty robots. This system uses a multi-agent architecture that integrates sensor processing, emotional expression, and voice interaction capabilities.

## 📋 Project Overview

MistyPilot is a multimodal robot control system with the following core features:

- **Multi-Agent Architecture**: Agent collaboration system based on AutoGen 0.5+ framework
- **Sensor Processing**: Real-time processing support for touch sensors and bump sensors
- **Emotional Expression**: Emotion recognition and corresponding action expression capabilities
- **Voice Interaction**: Natural language interaction integrated with OpenAI TTS
- **Vector Memory**: Store and retrieve robot behavior memory using ChromaDB

## 🏗️ System Architecture

### Core Components

1. **PIA (Process Intelligence Agent)** - Process Intelligence Agent
2. **SIA (Speech Intelligence Agent)** - Speech Intelligence Agent
3. **Misty_Call_Back_Func** - Callback function module 


## 🚀 Quick Start

### Prerequisites

- Python 3.8 or higher
- Misty robot (accessible via network)
- OpenAI API key

### Installation Steps

1. **Clone the Repository**
```bash
git clone <your-repository-url>
cd MistyPilot
```

2. **Set Up Python Virtual Environment (Recommended)**
```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate
```

3. **Install Dependencies**

Install all required dependencies from the requirements.txt file:
```bash
pip install -r requirements.txt
```

If you encounter any installation issues, try upgrading pip first:
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

**Alternative Installation Methods:**

For individual package installation:
```bash
# Core AutoGen packages
pip install autogen-agentchat>=0.5.0
pip install autogen-core>=0.5.0 
pip install autogen-ext>=0.5.0

# Other essential packages
pip install openai>=1.0.0
pip install pydantic>=2.0.0
pip install typing-extensions>=4.0.0
pip install requests>=2.28.0
pip install websocket-client>=1.6.0
pip install chromadb>=0.4.0
pip install mutagen>=1.47.0
```

4. **Configure the System**

Copy the configuration template and add your credentials:
```bash
cp MistyPilot_config.template.json MistyPilot_config.json
```

Then edit the `MistyPilot_config.json` file with your specific settings:
```json
{
    "misty_ip": "YOUR_MISTY_ROBOT_IP",
    "openai_api_key": "YOUR_OPENAI_API_KEY",
    "llm_model": "gpt-5-nano-2025-08-07",
    "stronger_model_name": "gpt-5-2025-08-07",
    "retries": 1,
    "threshold": 0.4,
    "store_dir": "./misty_emotion_action_speaking_store",
    "log_dir": "./logs",
    "reg_path": "./misty_proc_registry.json",
    "CB_SUMMARY_JSON_dir": "./cb_functions_summary.json",
    "collection": "text-embedding-3-large"
}
```

⚠️ **Security Note**: Never commit the actual `MistyPilot_config.json` file to version control. It contains sensitive API keys.

### Running the System

1. **Start the Main Program**
```bash
python MistyPilot.py
```

2. **System Initialization**
The system will automatically perform the following upon startup:
- Reset temporary state files
- Restore process state from registry
- Process callback function summaries
- Initialize agent teams

## 💡 Usage Examples

### Basic Interactions

```python
import asyncio
from MistyPilot import misty_pilot

# Emotional interaction example
await misty_pilot(task="Touch my head and show happiness")

# Sensor interaction example  
await misty_pilot(task="I touch your left front bumper, show surprise")

# Language interaction example
await misty_pilot(task="Tell me an interesting story")
```

### Agent Routing Rules

The system automatically selects the appropriate agent based on task type:

- **MistyEmotionSpeakingAgent_SOM**: Handles language-only tasks (storytelling, dialogue, greetings, emotional expressions, etc.)
- **MistySensorAgent_SOM**: Handles tasks involving physical interactions with Misty (touching, bumping, sensor events, etc.)

## 📁 Project Structure

```
MistyPilot/
├── MistyPilot.py                 # Main program entry point
├── MistyPilot_config.json        # Configuration file
├── requirements.txt              # Dependencies list
├── README.md                     # Project documentation
├── PIA/                         # Process Intelligence Agent
│   ├── MistySensorAgent.py      # Sensor agent
│   ├── Misty_Process_Scheduler.py
│   ├── Misty_Process_Worker.py
│   └── ...
├── SIA/                         # Speech Intelligence Agent
│   ├── MistyEmotionSpeakingAgent.py
│   ├── misty_emotion_speech.py
│   └── ...
├── Misty_Call_Back_Func/        # Callback function module
├── logs/                        # Log files
├── emotion_action_speaking_memory/ # Emotional action memory
└── ICRA_EXP/                    # Experiment-related files
```

## ⚙️ Configuration

### Main Configuration Parameters

- `misty_ip`: IP address of the Misty robot
- `openai_api_key`: OpenAI API key (for speech synthesis and language models)
- `llm_model`: Name of the language model to use
- `stronger_model_name`: Stronger model for complex reasoning
- `threshold`: Emotional judgment threshold
- `store_dir`: Vector database storage directory
- `log_dir`: Log files directory

### Sensor Configuration

Supported sensor types:
- **TouchSensor**: Touch sensors (Chin, Scruff, HeadRight, HeadLeft, HeadBack, HeadFront)
- **BumpSensor**: Bump sensors (bfl, bfr, brl, brr)

## 🔧 Advanced Features

### 1. Memory System
- Store robot behavior and interaction memory using ChromaDB
- Support semantic-based memory retrieval
- Automatically record emotional states and corresponding actions

### 2. Multi-Process Management
- Dynamic process scheduling and management
- Asynchronous processing of sensor events
- Process state persistence and recovery

### 3. Emotional Expression
- Multiple predefined emotional states (happy, sad, surprised, fearful, angry, disgusted)
- Corresponding actions and voice expressions
- Contextual memory of emotional states

## 🐛 Troubleshooting

### Common Issues

1. **Failed to Connect to Misty Robot**
   - Check if the robot IP address is correct
   - Ensure the robot and computer are on the same network
   - Verify that the robot's API service is enabled

2. **OpenAI API Errors**
   - Verify that the API key is valid
   - Check network connection and API quota
   - Confirm that the model name being used is correct

3. **Dependency Installation Issues**
   - Ensure Python version compatibility (3.8+)
   - Use virtual environment to avoid package conflicts
   - Check if the system has necessary compilation tools

### Log Viewing

System logs are stored in the `logs/` directory:
```bash
# View sensor logs
tail -f logs/misty_TouchSensor_*.log
tail -f logs/misty_BumpSensor_*.log
```
## 📞 Contact
xwang277@buffalo.edu
