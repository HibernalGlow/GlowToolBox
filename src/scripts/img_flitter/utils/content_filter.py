from services.logging_service import LoggingService

class ContentFilter:
    """内容过滤类"""
    @staticmethod
    def should_process_file(file_path, params):
        """判断文件是否需要处理"""
        LoggingService.info(f'\n开始检查文件是否需要处理: {file_path}')
        if params['exclude_paths']:
            for exclude_path in params['exclude_paths']:
                if exclude_path in file_path:
                    LoggingService.info(f'文件在排除路径中 (排除关键词: {exclude_path})')
                    return False
        LoggingService.info('文件通过所有检查，将进行处理')
        return True 