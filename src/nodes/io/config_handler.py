import os
import json
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class ConfigHandler:
    """配置文件处理类"""
    
    def __init__(self, config_path: str):
        """
        初始化配置处理器
        
        Args:
            config_path: 配置文件路径
        """
        self.config_path = config_path
        self.config = {}
        self.load_config()
        
    def load_config(self) -> Dict:
        """
        加载配置文件
        
        Returns:
            Dict: 配置字典
        """
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    self.config = json.load(f)
                logger.info(f"成功加载配置文件: {self.config_path}")
            else:
                logger.warning(f"配置文件不存在: {self.config_path}")
                self.config = {}
        except Exception as e:
            logger.error(f"加载配置文件失败: {e}")
            self.config = {}
        return self.config
        
    def save_config(self, config: Optional[Dict] = None) -> bool:
        """
        保存配置到文件
        
        Args:
            config: 要保存的配置字典，如果为None则保存当前配置
            
        Returns:
            bool: 是否保存成功
        """
        try:
            if config is not None:
                self.config = config
                
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
            logger.info(f"成功保存配置文件: {self.config_path}")
            return True
            
        except Exception as e:
            logger.error(f"保存配置文件失败: {e}")
            return False
            
    def get_value(self, key: str, default: Any = None) -> Any:
        """
        获取配置值
        
        Args:
            key: 配置键
            default: 默认值
            
        Returns:
            Any: 配置值
        """
        return self.config.get(key, default)
        
    def set_value(self, key: str, value: Any, auto_save: bool = True) -> bool:
        """
        设置配置值
        
        Args:
            key: 配置键
            value: 配置值
            auto_save: 是否自动保存到文件
            
        Returns:
            bool: 是否设置成功
        """
        try:
            self.config[key] = value
            if auto_save:
                return self.save_config()
            return True
        except Exception as e:
            logger.error(f"设置配置值失败: {e}")
            return False
            
    def update_config(self, new_config: Dict, auto_save: bool = True) -> bool:
        """
        更新配置
        
        Args:
            new_config: 新的配置字典
            auto_save: 是否自动保存到文件
            
        Returns:
            bool: 是否更新成功
        """
        try:
            self.config.update(new_config)
            if auto_save:
                return self.save_config()
            return True
        except Exception as e:
            logger.error(f"更新配置失败: {e}")
            return False
            
    def delete_key(self, key: str, auto_save: bool = True) -> bool:
        """
        删除配置项
        
        Args:
            key: 要删除的配置键
            auto_save: 是否自动保存到文件
            
        Returns:
            bool: 是否删除成功
        """
        try:
            if key in self.config:
                del self.config[key]
                if auto_save:
                    return self.save_config()
            return True
        except Exception as e:
            logger.error(f"删除配置项失败: {e}")
            return False 