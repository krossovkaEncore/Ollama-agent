import asyncio

from telebot import AsyncTeleBot
from telebot.types import Message

from brain import Brain
from config import TELEGRAM_TOKEN


bot = AsyncTeleBot(TELEGRAM_TOKEN)


async def msg(text: str):
    print(f"[BRAIN] {text}")


brain = Brain(msg)


@bot.message_handler(commands=["start"])
async def start_command(message: Message):
    await bot.send_message(
        message.chat.id,
        "Привет! Я готов к работе."
    )


@bot.message_handler(commands=["help"])
async def help_command(message: Message):
    await bot.send_message(
        message.chat.id,
        "Просто отправь мне сообщение или изображение."
    )


@bot.message_handler(
    content_types=["text"]
)
async def text_handler(message: Message):
    try:
        response = await brain.sendToAi(
            message.text
        )

        if response:
            await bot.send_message(
                message.chat.id,
                response
            )
        else:
            await bot.send_message(
                message.chat.id,
                "Не удалось получить ответ от модели."
            )

    except Exception as error:
        print(f"[ERROR] {error}")

        await bot.send_message(
            message.chat.id,
            "Произошла ошибка при обработке запроса."
        )


@bot.message_handler(
    content_types=["photo"]
)
async def photo_handler(message: Message):
    try:
        await bot.send_message(
            message.chat.id,
            "Получаю изображение..."
        )

        photo = message.photo[-1]

        file_info = await bot.get_file(photo.file_id)
        image = await bot.download_file(
            file_info.file_path
        )

        response = await brain.sendToAi(
            message.caption or "Опиши это изображение.",
            image=image
        )

        if response:
            await bot.send_message(
                message.chat.id,
                response
            )
        else:
            await bot.send_message(
                message.chat.id,
                "Не удалось обработать изображение."
            )

    except Exception as error:
        print(f"[ERROR] {error}")

        await bot.send_message(
            message.chat.id,
            "Произошла ошибка при обработке изображения."
        )


async def main():
    if not await brain.start():
        print("Не удалось запустить Brain.")
        return

    print("Bot started.")

    try:
        await bot.infinity_polling()

    finally:
        await brain.stop()


if __name__ == "__main__":
    asyncio.run(main())