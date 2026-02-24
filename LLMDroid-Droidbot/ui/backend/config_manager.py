"""
Config Manager - Read/Write config.json
"""
import os
import json
from typing import Dict, Any, Optional


class ConfigManager:
    def __init__(self, config_path: str):
        self.config_path = config_path
        self._config: Dict[str, Any] = {}
        self._load_config()
        
    def _load_config(self):
        """Load configuration from file"""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    self._config = json.load(f)
        except Exception as e:
            print(f"Error loading config: {e}")
            self._config = {}
    
    def _save_config(self):
        """Save configuration to file"""
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self._config, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving config: {e}")
    
    def get_config(self) -> Dict[str, Any]:
        """Get current configuration"""
        self._load_config()  # Reload to get latest
        
        # Return safe subset for UI
        return {
            "app_name": self._config.get("AppName", ""),
            "description": self._config.get("Description", ""),
            "model": self._config.get("Model", ""),
            "base_url": self._config.get("BaseUrl", ""),
            "total_method": self._config.get("TotalMethod", 0),
            "tag": self._config.get("Tag", ""),
            "apk_path": self._config.get("ClassFilePath", ""),
            "use_coverage": self._config.get("use_code_coverage", ""),
            "login_credentials_count": len(self._config.get("LoginCredentials", [])),
            "register_form_count": len(self._config.get("RegisterFormData", []))
        }
    
    def update_config(self, updates: Dict[str, Any]):
        """Update configuration with provided values"""
        self._load_config()  # Reload latest
        
        # Map UI field names to config field names
        field_mapping = {
            "app_name": "AppName",
            "description": "Description",
            "api_key": "ApiKey",
            "model": "Model",
            "base_url": "BaseUrl",
            "total_method": "TotalMethod",
            "tag": "Tag",
            "apk_path": "ClassFilePath"
        }
        
        for ui_field, value in updates.items():
            if ui_field in field_mapping:
                config_field = field_mapping[ui_field]
                self._config[config_field] = value
        
        self._save_config()
    
    def get_raw_config(self) -> Dict[str, Any]:
        """Get raw configuration (for advanced users)"""
        self._load_config()
        return self._config
    
    def set_raw_config(self, config: Dict[str, Any]):
        """Set raw configuration (for advanced users)"""
        self._config = config
        self._save_config()
