class TelegramBotService:
    def __init__(self, bot):
        self.bot = bot

    async def send_message(self, user_id, text):
        await self.bot.send_message(chat_id=user_id, text=text)
        return True

    async def new_user(self, user_id):
        await self.bot.send_message(chat_id=user_id, text='Welcome to our bot')