import json
from typing import Any

import aiohttp
from loguru import logger

from core.ConfigProvider import OpenAI


class OpenAIAPI:
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {OpenAI.APIKey}"
    }

    data = {
        "model": "gpt-4o",
        "max_tokens": 1000,
        "temperature": 0.7,
    }

    @classmethod
    async def call_openai_api(cls, context: str) -> str:
        cls.data["messages"] = [{"role": "user", "content": context}]

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(url="https://" if OpenAI.Https else "http://"
                                                                    + OpenAI.BaseUrl + "/v1/chat/completions",
                                        headers=cls.headers,
                                        json=cls.data) as response:
                    result = await response.json()

                    if response.status == 200:
                        return result["choices"][0]["message"]["content"][1]["text"].get("content", "未响应任何值").strip()
                        # return result["choices"][0]["message"]["content"].strip()
                    else:
                        return f"请求失败: {result.get('error', {}).get('message', '未知错误')}"
            except Exception as e:
                logger.error(f"请求出错: {e}")
                return f"请求出错: {str(e)}"

    @classmethod
    async def call_openai_api_stream(cls, context: str):
        cls.data["messages"] = [{"role": "user", "content": context}]
        cls.data["stream"] = True
        full_response = ""

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(url="https://" if OpenAI.Https else "http://"
                                                                    + OpenAI.BaseUrl, headers=cls.headers,
                                        data=json.dumps(cls.data)) as response:
                    if response.status == 200:
                        async for line in response.content:
                            line = line.decode('utf-8').strip()

                            if line.startswith("data: "):
                                line_content = line.split("data: ")[1].strip()
                                if line_content == "[DONE]":
                                    break
                                try:
                                    json_content = json.loads(line_content)
                                    delta = json_content.get("choices", [{}])[0].get("delta", {}).get("content", "")
                                    if delta:
                                        full_response += delta
                                        yield full_response
                                except json.JSONDecodeError:
                                    logger.warning(f"无法解析JSON: {line_content}")
                                    continue
                    else:
                        result = await response.json()
                        logger.error(f"请求失败: {result.get('error', {}).get('message', '未知错误')}")
            except Exception as e:
                logger.error(f"请求出错: {str(e)}")


class ResponseReader:
    def __init__(self, generator):
        self.generator = generator
        self.current_response = ""
        self.last_position = 0

    async def read(self) -> Any | None:
        try:
            self.current_response = await self.generator.__anext__()
        except StopAsyncIteration:
            return None

        new_content = self.current_response[self.last_position:]
        self.last_position = len(self.current_response)
        return new_content

    def get_sentences(self, content) -> tuple[list[str], str]:
        end_chars = ['。', '！', '？', '.', '?', '!']
        sentences = []
        start = 0

        for idx, char in enumerate(content):
            if char in end_chars:
                sentences.append(content[start:idx + 1].strip())
                start = idx + 1

        return sentences, content[start:]


async def main():
    context = "写一篇200字的故事"
    generator = OpenAIAPI.call_openai_api_stream(context=context)
    reader = ResponseReader(generator)
    collected_content = ""

    while True:
        part = await reader.read()
        if not part:
            break

        collected_content += part
        sentences, collected_content = reader.get_sentences(collected_content)

        for sentence in sentences:
            logger.debug(sentence)


if __name__ == '__main__':
    import asyncio

    asyncio.run(main())
