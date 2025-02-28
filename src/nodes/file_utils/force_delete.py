import os
import shutil
import win32con
import win32api
import win32security
import ntsecuritycon as security
import ctypes
from pathlib import Path
from send2trash import send2trash
import subprocess
import logging

logger = logging.getLogger(__name__)

class ForceDelete:
    @staticmethod
    def _prepare_path(file_path: str | Path) -> str:
        """处理长路径，确保支持超过260字符的路径"""
        path_str = str(file_path)
        
        # 如果已经是扩展路径格式，直接返回
        if path_str.startswith('\\\\?\\'):
            return path_str
            
        # 转换为绝对路径
        abs_path = os.path.abspath(path_str)
        
        # 处理 UNC 路径 (网络路径)
        if abs_path.startswith('\\\\'):
            return '\\\\?\\UNC\\' + abs_path[2:]
            
        # 处理本地路径
        return '\\\\?\\' + abs_path

    @staticmethod
    def _enable_privileges():
        """启用所需的所有权限"""
        privileges = [
            win32security.SE_TAKE_OWNERSHIP_NAME,
            win32security.SE_BACKUP_NAME,
            win32security.SE_RESTORE_NAME,
            win32security.SE_DEBUG_NAME,
            win32security.SE_SECURITY_NAME,
            win32security.SE_SYSTEM_ENVIRONMENT_NAME,
            win32security.SE_CHANGE_NOTIFY_NAME
        ]
        
        token = win32security.OpenProcessToken(
            win32api.GetCurrentProcess(),
            win32con.TOKEN_ADJUST_PRIVILEGES | win32con.TOKEN_QUERY
        )
        
        for privilege in privileges:
            try:
                priv_id = win32security.LookupPrivilegeValue(None, privilege)
                win32security.AdjustTokenPrivileges(
                    token, False, [(priv_id, win32security.SE_PRIVILEGE_ENABLED)]
                )
            except Exception:
                pass

    @staticmethod
    def _clear_attributes(file_path: str) -> bool:
        """完全清除文件属性"""
        try:
            # 使用 attrib 命令清除所有属性
            subprocess.run(['attrib', '-r', '-a', '-s', '-h', '-i', '-x', file_path], 
                         capture_output=True, text=True, check=False)
            
            # 使用 Windows API 设置为普通文件
            kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
            attrs = win32con.FILE_ATTRIBUTE_NORMAL
            kernel32.SetFileAttributesW(file_path, attrs)
            
            # 设置完全访问权限
            try:
                security_info = win32security.GetFileSecurity(
                    file_path, 
                    win32security.DACL_SECURITY_INFORMATION
                )
                dacl = win32security.ACL()
                # 添加完全控制权限
                dacl.AddAccessAllowedAce(
                    win32security.ACL_REVISION,
                    win32con.GENERIC_ALL | win32con.DELETE,
                    win32security.ConvertStringSidToSid("S-1-1-0")  # Everyone
                )
                security_info.SetSecurityDescriptorDacl(1, dacl, 0)
                win32security.SetFileSecurity(
                    file_path,
                    win32security.DACL_SECURITY_INFORMATION,
                    security_info
                )
            except Exception:
                pass
                
            return True
        except Exception as e:
            logger.error(f"清除文件属性失败: {file_path}, 错误: {str(e)}")
            return False

    @staticmethod
    def to_recycle_bin(file_path: str | Path) -> bool:
        """将文件移动到回收站"""
        try:
            file_path = ForceDelete._prepare_path(file_path)
            if not os.path.exists(file_path):
                return True
                
            try:
                send2trash(file_path)
                return True
            except Exception:
                # 如果 send2trash 失败，尝试使用 kernel32 直接删除
                kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
                if kernel32.DeleteFileW(file_path):
                    return True
                return False
        except Exception as e:
            logger.error(f"移动到回收站失败: {file_path}, 错误: {str(e)}")
            return False

    @staticmethod
    def take_ownership(file_path: str | Path) -> bool:
        """获取文件所有权"""
        try:
            file_path = ForceDelete._prepare_path(file_path)
            ForceDelete._enable_privileges()
            
            security_info = win32security.GetFileSecurity(
                file_path, win32security.OWNER_SECURITY_INFORMATION
            )
            
            # 获取当前用户 SID
            token = win32security.OpenProcessToken(
                win32api.GetCurrentProcess(),
                win32con.TOKEN_QUERY
            )
            user_sid = win32security.GetTokenInformation(
                token, win32security.TokenUser
            )[0]
            
            # 设置新的所有者和完全控制权限
            security_info.SetSecurityDescriptorOwner(user_sid, True)
            win32security.SetFileSecurity(
                file_path, 
                win32security.OWNER_SECURITY_INFORMATION | 
                win32security.DACL_SECURITY_INFORMATION,
                security_info
            )
            
            return True
        except Exception as e:
            logger.error(f"获取文件所有权失败: {file_path}, 错误: {str(e)}")
            return False

    @staticmethod
    def force_delete(file_path: str | Path) -> bool:
        """强制删除文件"""
        try:
            file_path = ForceDelete._prepare_path(file_path)
            if not os.path.exists(file_path):
                return True

            ForceDelete._enable_privileges()
            
            # 清除所有文件属性和权限
            ForceDelete._clear_attributes(file_path)

            # 获取所有权
            ForceDelete.take_ownership(file_path)

            # 尝试直接删除
            try:
                if os.path.isfile(file_path):
                    os.unlink(file_path)
                else:
                    shutil.rmtree(file_path)
                return True
            except Exception:
                pass

            # 使用 kernel32 API 强制删除
            kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
            if kernel32.DeleteFileW(file_path):
                return True

            # 使用 cmd 强制删除
            try:
                # 使用 /F /A: 参数强制删除所有属性的文件
                subprocess.run(['cmd', '/c', f'del /F /S /Q /A: "{file_path}"'], 
                             capture_output=True, check=False)
                if not os.path.exists(file_path):
                    return True
            except Exception:
                pass

            return False
        except Exception as e:
            logger.error(f"强制删除失败: {file_path}, 错误: {str(e)}")
            return False

    @staticmethod
    def safe_delete(file_path: str | Path, force: bool = True) -> bool:
        """
        删除文件，默认使用强制删除
        Args:
            file_path: 文件路径
            force: 是否使用强制删除，默认为True
        """
        try:
            file_path = Path(file_path)
            if not file_path.exists():
                return True

            if force:
                return ForceDelete.force_delete(file_path)
            else:
                return ForceDelete.to_recycle_bin(file_path)
        except Exception as e:
            logger.error(f"删除失败: {file_path}, 错误: {str(e)}")
            return False 