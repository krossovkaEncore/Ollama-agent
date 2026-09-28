import asyncio
import base64
import subprocess
from typing import Callable

import aiohttp

from config import MODELS, SYSTEM_PROMPT


OLLAMA_HOST = "http://127.0.0.1:11434"


class Brain:

    def __init__(self, msg: Callable | None = None):
        self.msg = msg
        self.process = None

    async def log(self, text: str):
        print(f"[BRAIN] {text}")

        if self.msg:
            result = self.msg(text)

            if asyncio.iscoroutine(result):
                await result

    async def is_running(self):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(OLLAMA_HOST) as response:
                    return response.status == 200

        except aiohttp.ClientError:
            return False

    async def start_ollama(self):
        if await self.is_running():
            await self.log("Ollama уже запущена.")
            return True

        await self.log("Запуск Ollama...")

        self.process = await asyncio.create_subprocess_exec(
            "ollama",
            "serve",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )

        for _ in range(30):
            if await self.is_running():
                await self.log("Ollama успешно запущена.")
                return True

            await asyncio.sleep(1)

        await self.log("Не удалось запустить Ollama.")

        if self.process:
            self.process.terminate()
            await self.process.wait()
            self.process = None

        return False

    async def stop_ollama(self):
        if not await self.is_running():
            await self.log("Ollama уже остановлена.")
            return

        await self.log("Остановка Ollama...")

        if self.process:
            self.process.terminate()

            try:
                await asyncio.wait_for(
                    self.process.wait(),
                    timeout=5
                )
            except asyncio.TimeoutError:
                self.process.kill()
                await self.process.wait()

            self.process = None

        else:
            subprocess.run(
                ["taskkill", "/IM", "ollama.exe", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

        await self.log("Ollama остановлена.")

    async def get_models(self):
        process = await asyncio.create_subprocess_exec(
            "ollama",
            "list",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        stdout, _ = await process.communicate()

        if process.returncode != 0:
            return []

        models = []

        for line in stdout.decode("utf-8", errors="ignore").splitlines()[1:]:
            if line.strip():
                models.append(line.split()[0])

        return models

    async def sync_models(self):
        required_models = set(MODELS.values())

        await self.log("Проверка установленных моделей...")

        installed_models = await self.get_models()

        for model in required_models:
            if model in installed_models:
                await self.log(f"Модель уже установлена: {model}")
                continue

            await self.log(f"Скачивание модели: {model}")

            process = await asyncio.create_subprocess_exec(
                "ollama",
                "pull",
                model,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )

            while True:
                line = await process.stdout.readline()

                if not line:
                    break

                text = line.decode(
                    "utf-8",
                    errors="ignore"
                ).strip()

                if text:
                    await self.log(text)

            await process.wait()

            if process.returncode != 0:
                await self.log(
                    f"Ошибка скачивания модели: {model}"
                )
                return False

            await self.log(
                f"Модель успешно установлена: {model}"
            )

        for model in installed_models:
            if model not in required_models:
                await self.log(
                    f"Удаление лишней модели: {model}"
                )

                process = await asyncio.create_subprocess_exec(
                    "ollama",
                    "rm",
                    model,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                )

                await process.wait()

                if process.returncode == 0:
                    await self.log(
                        f"Модель удалена: {model}"
                    )
                else:
                    await self.log(
                        f"Не удалось удалить: {model}"
                    )

        await self.log("Синхронизация моделей завершена.")

        return True

    async def start(self):
        await self.log("Инициализация Brain...")

        if not await self.start_ollama():
            return False

        if not await self.sync_models():
            return False

        await self.log("Brain готов к работе.")

        return True

    async def stop(self):
        await self.log("Завершение работы Brain...")

        await self.stop_ollama()

        await self.log("Brain остановлен.")

    async def sendToAi(
        self,
        request: str,
        image: bytes | None = None
    ):
        if image is not None:
            model = MODELS["vision"]

            await self.log(
                f"Выбрана Vision-модель: {model}"
            )

        else:
            model = MODELS["text"]

            await self.log(
                f"Выбрана текстовая модель: {model}"
            )

        prompt = (
            f"{SYSTEM_PROMPT}\n\n"
            f"Запрос пользователя:\n"
            f"{request}"
        )

        data = {
            "model": model,
            "prompt": prompt,
            "stream": False,
        }

        if image is not None:
            data["images"] = [
                base64.b64encode(image).decode("utf-8")
            ]

        await self.log(
            f"Отправка запроса в {model}..."
        )

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{OLLAMA_HOST}/api/generate",
                json=data
            ) as response:

                if response.status != 200:
                    error = await response.text()

                    await self.log(
                        f"Ошибка Ollama: {error}"
                    )

                    return None

                result = await response.json()

        await self.log("Ответ от модели получен.")

        return result.get("response")