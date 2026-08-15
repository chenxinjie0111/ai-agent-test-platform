"""
统一日志系统：整个项目的日志入口。

用法（其他文件里）：
    from app.utils.logger import get_logger
    logger = get_logger(__name__)     # __name__ 是当前模块名
    logger.info("开始运行评测")
    logger.error(f"LLM 调用失败: {e}")

为什么用 get_logger(__name__) 而不是 logging.getLogger()：
  __name__ 是 Python 自动变量，值是当前模块的导入路径（如 "app.agent.agent"）。
  用它做 logger 名字，日志里就能看到"是哪个模块输出的这条日志"——排查问题时非常关键。
"""

import logging
import sys
from pathlib import Path

from app.utils.config import BASE_DIR


def get_logger(name: str) -> logging.Logger:
    """
    获取一个配置好的 logger。

    配置内容：
      1. 终端输出：INFO 及以上级别，格式简洁（时间 + 级别 + 模块 + 消息）
      2. 文件输出：DEBUG 及以上级别，写入 logs/app.log
      3. 防止重复添加 handler（多次调用不会重复输出）

    参数:
        name: 通常传 __name__（当前模块名）
    """
    logger = logging.getLogger(name)

    # 如果已经配置过（有 handler），直接返回，不重复配置
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    # ---- 格式 ----
    # 终端格式：简洁，只显示时间+级别+模块名+消息
    console_format = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    # 文件格式：详细，包含完整日期
    file_format = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s (%(filename)s:%(lineno)d): %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # ---- 终端 Handler ----
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)     # 终端只显示 INFO 及以上
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)

    # ---- 文件 Handler ----
    # 日志文件放在项目根目录的 logs/ 下
    log_dir = BASE_DIR / "logs"
    log_dir.mkdir(exist_ok=True)
    file_handler = logging.FileHandler(
        log_dir / "app.log", encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)        # 文件记录所有级别（含 DEBUG）
    file_handler.setFormatter(file_format)
    logger.addHandler(file_handler)

    # 防止日志向父 logger 传播（避免重复输出）
    logger.propagate = False

    return logger
