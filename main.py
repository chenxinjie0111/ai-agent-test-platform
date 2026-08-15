"""
阶段一验证入口

运行方式python main.py
"""

from app.llm.client import LLMClient

def print_result(result):
    print(f"  是否成功   : {'是' if result.success else '否'}")
    print(f"  回答内容   : {result.answer[:100] if result.answer else '(无)'}")
    print(f"  响应时间   : {result.response_time} 秒")
    print(f"  Token 消耗 : 输入 {result.prompt_tokens} / "
          f"输出 {result.completion_tokens} / 总计 {result.total_tokens}")
    if not result.success:
        print(f"  错误类型   : {result.error_type}")
        print(f"  错误信息   : {result.error}")


if __name__ == "__main__":
    client = LLMClient()
    # ---- 场景 1：正常调用（智能办公助手角色）----
    print("=" * 60)
    print("场景 1：正常调用")
    print("=" * 60)
    result = client.ask("用一句话介绍你能帮员工做什么？")
    print_result(result)

    # ---- 场景 2：自定义 system prompt ----
    print("\n" + "=" * 60)
    print("场景 2：自定义 system prompt（限制回答格式）")
    print("=" * 60)
    result = client.ask(
        "12345 乘以 678 等于多少？",
        system_prompt="你是一个计算器，只输出最终数字，不要任何解释和单位。",
    )
    print_result(result)

    # ---- 场景 3：异常处理（故意用不存在的地址）----
    print("\n" + "=" * 60)
    print("场景 3：异常处理（故意用不存在的地址）")
    print("=" * 60)
    bad_client = LLMClient(base_url="https://api.this-url-does-not-exist.com")
    result = bad_client.ask("这条消息发不出去")
    print_result(result)
    print("\n  关键验证点：程序没有崩溃，而是返回了 success=False 的结构化结果！")
