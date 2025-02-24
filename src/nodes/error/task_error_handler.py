import functools
import asyncio
import concurrent.futures
from typing import Callable, Any, Optional
from nodes.record.logger_config import setup_logger

config = {
    'script_name': 'task_error_handler',
    "console_enabled": False,
}
logger, _ = setup_logger(config)

def handle_task_exception(func: Callable) -> Callable:
    """
    装饰器：处理任务执行过程中的异常
    
    Args:
        func: 要装饰的函数
        
    Returns:
        装饰后的函数
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except concurrent.futures.CancelledError:
            logger.error(f"任务被取消: {func.__name__}")
            raise
        except Exception as e:
            logger.error(f"任务执行出错 {func.__name__}: {str(e)}")
            raise
    return wrapper

def setup_task_exception_handler(loop: Optional[asyncio.AbstractEventLoop] = None) -> None:
    """
    设置全局任务异常处理器
    
    Args:
        loop: 可选的事件循环实例
    """
    def handle_exception(loop: asyncio.AbstractEventLoop, context: dict) -> None:
        exception = context.get('exception')
        if exception:
            logger.error(f"未处理的任务异常: {str(exception)}")
        else:
            logger.error(f"未处理的任务错误: {context['message']}")
            
    if loop is None:
        loop = asyncio.get_event_loop()
    loop.set_exception_handler(handle_exception)

def create_monitored_task(coro: Any, *, name: Optional[str] = None) -> asyncio.Task:
    """
    创建一个受监控的任务
    
    Args:
        coro: 协程对象
        name: 可选的任务名称
        
    Returns:
        asyncio.Task: 创建的任务
    """
    task = asyncio.create_task(coro, name=name)
    
    def _handle_task_result(task: asyncio.Task) -> None:
        try:
            task.result()
        except asyncio.CancelledError:
            logger.info(f"任务 {task.get_name()} 已取消")
        except Exception as e:
            logger.error(f"任务 {task.get_name()} 执行失败: {str(e)}")
            
    task.add_done_callback(_handle_task_result)
    return task 