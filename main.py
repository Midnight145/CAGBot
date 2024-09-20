import asyncio
import json
import sqlite3
import sys
import traceback
import fastapi

import discord

from CAGBot import DNDBot
from modules.errorhandler import TracebackHandler


def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d


with open('config.json') as config_file:
    config = json.load(config_file)
with open('token.txt', 'r') as token:
    TOKEN = token.read().rstrip()


async def get_prefix(bot_, message):
    return config["prefix"]

GUILD_ID = config["server"]

connection = sqlite3.connect(config["database_file"], check_same_thread=False)
connection.row_factory = sqlite3.Row

db = connection.cursor()


intents = discord.Intents.all()

bot = DNDBot(db, connection, config, command_prefix=get_prefix, intents=intents, help_command=None)
DNDBot.instance = bot


@bot.event
async def on_ready():
    print("Logged in")
    for i in bot.all_cogs:
        print("Loading " + i)
        if i in bot.loaded_cogs: continue
        await bot.load_extension(i)
        bot.loaded_cogs.append(i)
    print("All cogs loaded successfully!")


@bot.event
async def on_error(event, *args, **kwargs):
    exc_type, exc_name, exc_traceback = sys.exc_info()
    traceback.print_exc()
    channel = bot.get_channel(config["staff_botspam"])
    err_code = 255
    for i in range(len(bot.traceback) + 1):
        if i in bot.traceback:
            continue
        err_code = i
    original = getattr(exc_traceback, '__cause__', exc_traceback)
    handler = TracebackHandler(err_code, f"{exc_type.__name__}: {str(exc_name)}", original)
    bot.traceback[err_code] = handler
    await channel.send(f"An error occurred in {event}. Error code: {str(err_code)}")


bot.run(TOKEN)