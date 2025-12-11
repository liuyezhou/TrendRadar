import asyncio
import json
import os 
import openai
import requests
from contextlib import AsyncExitStack
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport
import traceback

MCP_CMD = ["-m", "mcp_server.server", "--transport", "stdio"]
WEBHOOK_URL = os.environ["FEISHU_OUTSIDE_WEBHOOK_URL"]
PROMPT = "查询昨日新闻并总结"

if WEBHOOK_URL is None or len(WEBHOOK_URL) == 0:
    print("WEBHOOK_URL not set!")
    exit(1)

def send_by_webhook(message: str):
    headers = {
        "Content-Type": "application/json"
    }
    data = {
        "msg_type": "text",
        "content": {
            "text": message,
        }
    }
    response = requests.post(WEBHOOK_URL, headers=headers, json=data)
    records = response.json()
    return records


class MCPClient:
    def __init__(self, verbose=True):
        """
        初始化 MCP 客户端。
        设置异步上下文管理器、OpenAI 客户端、模型路径和 MCP 会话。
        """
        self.exit_stack = AsyncExitStack()
        self.llm_client = openai.OpenAI(
                base_url="http://vllm:8000/v1", # LLM 服务器的基础 URL
                api_key="vllm", # API 密钥，这里使用 vllm 作为占位符
        )
        self.model = "Qwen/Qwen3-30B-A3B-Instruct-2507" # 使用的 LLM 模型路径
        self.session = None      # MCP 会话，用于与 MCP 服务器通信
        self.verbose = verbose

    async def connect_to_mcp_server_io(self):
        """
        连接到 MCP 服务器并列出可用工具。
        通过标准 I/O 启动 MCP 服务器，并建立客户端会话。
        """
        # 定义 MCP 服务器的启动参数
        server_params = StdioServerParameters(
            command="python", # 启动服务器的命令
            args=MCP_CMD,    # 服务器脚本路径作为参数
            env=os.environ  # 环境变量
        )

        # 启动 MCP 服务器并建立通信通道
        # stdio_client 用于通过标准 I/O 连接到服务器
        stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
        self.stdio, self.write = stdio_transport # 获取标准输入和输出流
        # 创建 MCP 客户端会话
        self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.write))
        response = await self.session.initialize() # 初始化会话
        # 列出 MCP 服务器上注册的所有工具
        response = await self.session.list_tools()
        tools = response.tools
        if self.verbose:
            print("\n已连接到服务器，支持以下工具:", [tool.name for tool in tools])  

    async def connect_to_mcp_server_http(self, mcp_server_url):
        """
        连接到 MCP 服务器并列出可用工具。
        通过标准 I/O 启动 MCP 服务器，并建立客户端会话。
        """
        transport = StreamableHttpTransport(url=mcp_server_url)
        # 使用上下文管理器创建客户端会话
        async with Client(transport) as client:
            if self.verbose:
                print(f"成功连接到MCP服务: {mcp_server_url}")
            
            # 发送ping请求测试服务连通性
            await client.ping()
            if self.verbose:
                print("服务心跳检测成功")
            # 获取服务端注册的所有工具
            tools = await client.list_tools()
            tool_names = [tool.name for tool in tools]
            if self.verbose:
                print(f"可用工具列表: {', '.join(tool_names)}")


    def ping_llm_server(self):
        """
        向 LLM 服务器发送 ping 请求，检查其是否正常运行。
        发送一个简单的查询并打印响应。
        """
        messages = [{"role": "user", "content": "你是谁"}] # 测试消息
        try:
            # 调用 LLM 客户端的聊天完成 API
            response = self.llm_client.chat.completions.create(
                model=self.model,
                messages=messages
            )
            print(response.choices[0].message.content) # 打印 LLM 的回复
            return response.choices[0].message.content # 返回回复内容
        
        except Exception as e:
            # 捕获并打印连接或请求错误
            print(f"Error: {str(e)}\n{traceback.format_exc()}")

        
    async def chat(self, query: str) -> str:
        """
        使用大模型处理查询并调用可用的 MCP 工具 (Function Calling)。
        根据 LLM 的响应决定是直接回复还是调用工具。
        """
        messages = [{"role": "user", "content": query}] # 初始用户查询消息
        
        # 获取 MCP 服务器上所有可用的工具
        response = await self.session.list_tools()
        tools = response.tools
        
        # 将 MCP 工具信息转换为 OpenAI API 期望的工具格式 (Function Calling)
        available_tools =  [{
            "type": "function",
            "function": {
                "name": tool.name, # 工具名称
                "description": tool.description, # 工具描述
                "parameters": { # 工具参数的 JSON Schema 定义
                    "type": tool.inputSchema.get("type", "object"),
                    "properties": {
                        prop_name: prop_def 
                        for prop_name, prop_def in tool.inputSchema["properties"].items()
                    },
                    "required": tool.inputSchema.get("required", [])
                }
            }
        } for tool in tools]

        # 第一次调用 LLM：将用户查询和可用工具传递给模型
        # 模型会决定是直接回答还是调用某个工具
        response = self.llm_client.chat.completions.create(
            model=self.model,            
            messages=messages,
            tools=available_tools, # 传递可用工具列表
            tool_choice="auto",  # 允许模型自动选择是否调用工具
        )
        
        # 处理 LLM 返回的内容
        content = response.choices[0]
        if content.finish_reason == "tool_calls":
            # 如果 LLM 决定调用工具
            tool_call = content.message.tool_calls[0] # 获取第一个工具调用信息
            tool_name = tool_call.function.name # 获取工具名称
            tool_args = json.loads(tool_call.function.arguments) # 解析工具参数 (JSON 字符串转 Python 字典)
            
            # 执行工具：通过 MCP 会话调用指定的工具
            if self.verbose:
                print(f"\n\n[Calling tool {tool_name} with args {tool_args}]\n\n")
            result = await self.session.call_tool(tool_name, tool_args)
            if self.verbose:
                print(f"[Tool {tool_name} returned {result}]\n\n")

            # 将模型返回的工具调用信息和工具执行结果都添加到消息历史中
            messages.append(content.message.model_dump()) # 添加模型建议的工具调用消息
            messages.append({
                "role": "tool", # 角色为 'tool' 表示这是工具的输出
                "content": result.content[0].text, # 工具执行的实际结果
                "tool_call_id": tool_call.id, # 关联到之前的工具调用 ID
            })
            
            # 第二次调用 LLM：将完整的消息历史（包括工具调用和结果）返回给模型
            # 模型会根据工具执行结果生成最终的回复
            response = self.llm_client.chat.completions.create(
                model=self.model,
                messages=messages,
            )
            return response.choices[0].message.content # 返回最终的 LLM 回复
            
        # 如果 LLM 没有调用工具，则直接返回其生成的文本内容
        return content.message.content
    
    async def chat_loop(self):
        """
        命令行聊天循环。
        允许用户持续输入查询，并显示 AI 助手的回复。
        """
        print("\nmcp client is running...\n")

        while True:
            try:
                query = input("\nuser: ").strip() # 获取用户输入
                if query.lower() == 'quit': # 输入 'quit' 退出循环
                    break
                
                response = await self.chat(query)  # 发送用户输入到 LLM API 进行处理
                print(f"\nai assistant: {response}") # 打印 AI 助手的回复

            except Exception as e:
                # 捕获并打印聊天过程中的错误
                print(f"\nerror: {str(e)}\n{traceback.format_exc()}") # 修正：使用 traceback.format_exc() 获取完整的错误信息

    async def cleanup(self):
        """
        清理资源。
        关闭异步上下文管理器，确保所有资源被正确释放。
        """
        await self.exit_stack.aclose()

async def main():
    """
    主函数，程序的入口点。
    处理命令行参数，初始化 MCP 客户端，连接服务器，运行聊天循环，并进行清理。
    """
    client = MCPClient() # 创建 MCPClient 实例
    try:
        # 连接到 MCP 服务器
        await client.connect_to_mcp_server_io()
        # 检查 LLM 服务器连接
        client.ping_llm_server()
        # 启动聊天循环
        await client.chat_loop()
    finally:
        # 确保在程序退出前执行清理操作
        await client.cleanup()

async def summary():
    client = MCPClient(False) # 创建 MCPClient 实例
    try:
        # 连接到 MCP 服务器
        await client.connect_to_mcp_server_io()
        # 检查 LLM 服务器连接
        client.ping_llm_server()
        report = await client.chat(PROMPT)
    finally:
        # 确保在程序退出前执行清理操作
        await client.cleanup()
    return report

if __name__ == "__main__":
    # import sys
    report = asyncio.run(summary()) # 运行异步主函数
    print(send_by_webhook(report))
    print("Agent finished, exiting...")
