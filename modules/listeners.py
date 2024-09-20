import asyncio

import discord
from discord.ext import commands
import re


class Listeners(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.user_id == self.bot.user.id:
            return

        channel = self.bot.get_channel(payload.channel_id)
        if channel.guild is not None:
            return

        if payload.emoji.name == "❌" or payload.emoji.name == "✖":
            message = await self.bot.get_channel(payload.channel_id).fetch_message(payload.message_id)
            await message.delete()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.thread is not None and len(message.attachments):
            regex = None
            if message.thread.parent_id == 1276234389004484672:
                regex = self.bot.config["template_regex"]

            elif message.thread.parent_id == 1277315286424485991:
                regex = self.bot.config["npc_regex"]

            if regex is None:
                return
            if re.fullmatch(regex, message.content) and len(message.attachments):
                return
            await message.thread.delete()
            try:
                await message.author.send("Template matching failed. Please make sure that you used the template. If you think there was an issue, contact either Meg or Ryan.")
                await message.author.send("Content of your post for editing: \n```\n" + message.content + "\n```")
            except discord.Forbidden:
                await (self.bot.get_channel(self.bot.config["staff_botspam"])).send(f"{message.author.mention}: Template matching for your character failed. Please make sure that you used the template. If you think there was an issue, contact either Meg or Ryan.")
                await (self.bot.get_channel(self.bot.config["staff_botspam"])).send("Content of your post for editing: \n```\n" + message.content + "\n```")



async def setup(bot):
    await bot.add_cog(Listeners(bot))
