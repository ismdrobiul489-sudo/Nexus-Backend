import logging
from datetime import datetime
from collections import deque
from typing import List, Dict, Any, Optional
import json

class LoggerService:
    MAX_LOGS = 500 # 1:1 Parity with logger.ts
    _logs = deque(maxlen=MAX_LOGS)
    _initialized = False

    @classmethod
    def init(cls):
        """Hooks into standard Python logging to capture all backend events."""
        if cls._initialized:
            return
        
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)
        
        class DequeHandler(logging.Handler):
            def emit(self, record):
                try:
                    msg = self.format(record)
                    cls.log(
                        level=record.levelname.lower() if record.levelname != 'WARNING' else 'warn',
                        message=msg
                    )
                except Exception:
                    self.handleError(record)

        handler = DequeHandler()
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        root_logger.addHandler(handler)

        # ALSO Add Console Handler to see logs in Terminal
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
        
        cls.log('info', 'Logger Service Initialized 🚀 (Console Output Enabled)')
        cls._initialized = True

    @classmethod
    def get_logs(cls, limit: int = 100) -> List[Dict]:
        return list(cls._logs)[:limit]

    @classmethod
    def clear_logs(cls):
        cls._logs.clear()
        cls.log('info', 'Logs Cleared')

    @classmethod
    def info(cls, message: str, data: Any = None, flow_id: str = None, **kwargs):
        log_data = data or kwargs or {}
        if flow_id:
             message = f"[{flow_id}] {message}"
             if isinstance(log_data, dict):
                 log_data["flow_id"] = flow_id
        cls.log('info', message, log_data)

    @classmethod
    def warn(cls, message: str, data: Any = None, flow_id: str = None, **kwargs):
        log_data = data or kwargs or {}
        if flow_id:
             message = f"[{flow_id}] {message}"
             if isinstance(log_data, dict):
                 log_data["flow_id"] = flow_id
        cls.log('warn', message, log_data)

    @classmethod
    def error(cls, message: str, data: Any = None, flow_id: str = None, **kwargs):
        log_data = data or kwargs or {}
        if flow_id:
             message = f"[{flow_id}] {message}"
             if isinstance(log_data, dict):
                 log_data["flow_id"] = flow_id
        cls.log('error', message, log_data)
    
    @classmethod
    def success(cls, message: str, data: Any = None, flow_id: str = None, **kwargs):
        log_data = data or kwargs or {}
        if flow_id:
             message = f"[{flow_id}] {message}"
             if isinstance(log_data, dict):
                 log_data["flow_id"] = flow_id
        cls.log('info', f"✅ {message}", log_data)

    @classmethod
    def log(cls, level: str, message: str, data: Any = None):
        """1:1 Parity Method for logging."""
        # Truncate like logger.ts
        if len(message) > 2000:
            message = message[:2000] + "...[TRUNCATED_BY_LOGGER]"

        entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": level if level in ['info', 'warn', 'error', 'debug'] else 'info',
            "message": message
        }
        if data:
            try:
                entry["data"] = json.loads(json.dumps(data))
            except:
                entry["data"] = "[Unserializable Data]"
        
        cls._logs.appendleft(entry)
        
        # --- CONSOLE OUTPUT ---
        # Print to terminal for visibility during execution
        level_icon = {"info": "ℹ️", "warn": "⚠️", "error": "❌", "debug": "🔍"}.get(level, "📝")
        print(f"{level_icon} [{level.upper()}] {message}")

# Global helpers for parity
def console_log(level: str, message: str, data: Any = None):
    LoggerService.log(level, message, data)
