import asyncio
import datetime
import os
from math import ceil
import aiohttp
import discord
from discord.ext import commands


class Cooldown:
    def __init__(self, cid, channel, cooldown):
        self.cid = cid
        self.channel = channel
        self.cooldown = cooldown

    async def run(self):
        counter = self.cooldown
        for i in range(counter):
            await asyncio.sleep(1)
            self.cooldown -= 1


class Character(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.db.execute(
            'CREATE TABLE IF NOT EXISTS "characters" ( "id" INTEGER PRIMARY KEY, "name" TEXT, "pronouns" TEXT, "race" TEXT, '
            '"classes" TEXT, "description" TEXT, "demeanor" TEXT, "info" TEXT, "image" TEXT, "wiki" TEXT, "owner" '
            'INTEGER)')
        self.bot.db.execute("CREATE TABLE IF NOT EXISTS prefixes (id INTEGER PRIMARY KEY, cid INTEGER, prefix TEXT)")
        self.bot.connection.commit()
        self.api = "https://api.midnight.wtf/images/{}"
        self.help_str = """
Command Reference
-----------------

Character Management:
    >create - Interactive prompt to create a character. Each response will time out after 1 minute, in which case you will have to restart the command.
    >delete <id> - Delete a character. You must be the owner of the character to delete it.
    >edit <id> <field> <value> - Edit a character. Valid fields are: "name", "pronouns", "race", "classes", "description", "demeanor", "image", and "wiki". You must be the owner of the character to edit it.
    
    >add_prefix <id> <prefix> - Add a prefix to a character. This prefix will be used to trigger the character. For example, if you add the prefix "!" to a character, you can trigger it by sending "!<message>" in any channel the bot can see.
    >remove_prefix <id> <prefix> - Remove a prefix from a character. You must be the owner of the character to remove a prefix.

    >list - List all of your characters. This will also show character ids, used in other commands.    
    >view <id> - View a character's information. This will show all information about the character, including the owner and wiki link.
    
    >proxy <prefix> - Proxy as a character in the current channel. This will allow you to send messages as the character without needing to use a prefix. Starting a message with '[' will disable proxying for that message.
    >unproxy <prefix> - Unproxy as a character in the current channel. This will disable proxying for the character in the current channel.
    
Reactions:
    ✖ - Delete a proxied message. You must be the owner of the character to delete it.
    📝 - Edit a proxied message. You must be the owner of the character to edit it. 
    📋 - View the character's information.
    ❔ - View this help message.
"""
        self.cooldowns: dict[int, list] = {}

    @commands.command(aliases=['cc', 'create'])
    async def create_character(self, context: commands.Context, name: str = None,
                               image: str = None, *, info: str = None):
        if name is None:
            return await self.create_char_dynamic(context)
        if len(context.message.attachments) > 0:
            info = image + (info if info is not None else "")
            image = context.message.attachments[0].url

        self.bot.db.execute("INSERT INTO characters (name, owner, info, image) VALUES (?, ?, ?, ?)",
                            (name, context.author.id, info, image))
        self.bot.connection.commit()
        cid = self.bot.db.lastrowid
        await self.update_image(cid, image)
        await context.send("Character created!")

    async def create_char_dynamic(self, context: commands.Context):
        try:
            await context.send("Enter character name:")
            name_message = await self.bot.wait_for("message", check=lambda m: m.author == context.author, timeout=120)
            await context.send("Enter character pronouns:")
            pronouns_message = await self.bot.wait_for("message", check=lambda m: m.author == context.author,
                                                       timeout=120)
            await context.send("Enter character race")
            race_message = await self.bot.wait_for("message", check=lambda m: m.author == context.author, timeout=120)
            await context.send("Enter character class(es):")
            classes_message = await self.bot.wait_for("message", check=lambda m: m.author == context.author,
                                                      timeout=120)
            await context.send("Enter character physical appearance:")
            description_message = await self.bot.wait_for("message", check=lambda m: m.author == context.author,
                                                          timeout=120)
            await context.send("Enter character demeanor:")
            demeanor_message = await self.bot.wait_for("message", check=lambda m: m.author == context.author,
                                                       timeout=120)
            await context.send("Enter character image:")
            image_message = await self.bot.wait_for("message", check=lambda m: m.author == context.author, timeout=120)
            await context.send("Enter character wiki link (enter 'none' to skip):")
            wiki_message = await self.bot.wait_for("message", check=lambda m: m.author == context.author, timeout=120)
        except asyncio.TimeoutError:
            await context.send("Timed out!")
            return

        if wiki_message.content.lower() == "none":
            wiki_message.content = ""

        name = name_message.content
        pronouns = pronouns_message.content
        race = race_message.content
        classes = classes_message.content
        description = description_message.content
        demeanor = demeanor_message.content

        if image_message.attachments:
            image = image_message.attachments[0].url
        else:
            image = image_message.content

        # info = info_message.content
        wiki = wiki_message.content

        self.bot.db.execute("INSERT INTO characters (name, pronouns, race, classes, description, demeanor, owner, "
                            "info, image, wiki) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                            (name, pronouns, race, classes, description, demeanor, context.author.id, "", image, wiki))
        self.bot.connection.commit()
        embed = discord.Embed(
            title=f"Character Created",
            description=f"Name: {name}",
            color=discord.Color.gold(),
            timestamp=datetime.datetime.utcnow()
        )
        embed.set_image(url=image)
        cid = self.bot.db.lastrowid
        await self.update_image(cid, image)

        await context.send(embed=embed)
        await context.send(f"Character created with character id {cid}, run `>add_prefix` to add a prefix to "
                           f"this character!")

    @commands.command(aliases=['dc', 'delete'])
    async def delete_character(self, context: commands.Context, cid: int):
        character = self.bot.db.execute("SELECT * FROM characters WHERE id = ?", (cid,)).fetchone()
        if character["owner"] != context.author.id:
            await context.send("You do not own this character!")
            return
        self.bot.db.execute("DELETE FROM characters WHERE id = ?", (cid,))
        self.bot.db.execute("DELETE FROM prefixes WHERE cid = ?", (cid,))
        self.bot.connection.commit()
        path = f"images/{cid}.png"
        if os.path.exists(path):
            os.remove(path)
        await context.send("Character deleted!")

    @commands.command(aliases=['ec', 'edit'])
    async def edit_character(self, context: commands.Context, cid: int, field: str = None, *, value: str = None):
        fields = ["name", "pronouns", "race", "classes", "description", "demeanor", "image", "wiki"]
        if field is None:
            await context.send(f"Available fields: {', '.join(fields)}")
            return
        if field not in fields:
            await context.send(f"Available fields: {', '.join(fields)}")
            return
        if field == "image":
            if len(context.message.attachments) > 0:
                value = context.message.attachments[0].url
            await self.update_image(cid, value)
        character = self.bot.db.execute("SELECT * FROM characters WHERE id = ?", (cid,)).fetchone()
        if character["owner"] != context.author.id:
            await context.send("You do not own this character!")
            return
        self.bot.db.execute(f"UPDATE characters SET {field} = ? WHERE id = ?", (value, cid))
        self.bot.connection.commit()
        await context.send("Character updated!")

    @commands.command(aliases=['view'])
    async def view_character(self, context: commands.Context, cid: int):
        character = self.bot.db.execute("SELECT * FROM characters WHERE id = ?", (cid,)).fetchone()
        if character is None:
            await context.send("Character not found!")
            return
        embed = self.__generate_character_embed(character)

        await context.send(embed=embed)

    @commands.command(aliases=['lc', 'list'])
    async def list_characters(self, context: commands.Context):
        chars = self.bot.db.execute("SELECT * FROM characters WHERE owner = ?", (context.author.id,)).fetchall()

        if len(chars) == 0:
            await context.send("You have no characters!")
            return
        embeds = []
        embed_count = ceil(len(chars) / 25)
        for i in range(embed_count):
            embed = discord.Embed(
                title="Your characters",
                color=discord.Color.gold()
            )
            for char in chars[i * 25:(i + 1) * 25]:
                embed.add_field(name=char["name"], value=f"ID: {char['id']}", inline=False)
            embeds.append(embed)
        if len(embeds) > 10:
            await context.send(embeds=embeds[0:10])
            for i in range(len(embeds) // 10):
                await context.send(embeds=embeds[i * 10:(i + 1) * 10])
        else:
            await context.send(embeds=embeds)

    @commands.command(aliases=['ap'])
    async def add_prefix(self, context: commands.Context, cid: int = None, prefix: str = None):
        if cid is None:
            return await self.add_prefix_dynamic(context)
        if prefix is None:
            return await self.add_prefix_dynamic(context, cid)
        character = self.bot.db.execute("SELECT * FROM characters WHERE id = ?", (cid,)).fetchone()
        if character["owner"] != context.author.id:
            await context.send("You do not own this character!")
            return
        self.bot.db.execute("INSERT INTO prefixes (cid, prefix) VALUES (?, ?)", (cid, prefix))
        self.bot.connection.commit()
        await context.send("Prefix added!")

    async def add_prefix_dynamic(self, context, cid: int = None):
        prefix = self.__fetch_prefix(context, cid)
        self.bot.db.execute("INSERT INTO prefixes (cid, prefix) VALUES (?, ?)", (cid, prefix))
        self.bot.connection.commit()
        await context.send("Prefix added!")

    @commands.command(aliases=['rp', 'dp', 'delete_prefix'])
    async def remove_prefix(self, context: commands.Context, cid: int = None, prefix: str = None):
        if cid is None:
            return await self.remove_prefix_dynamic(context)
        if prefix is None:
            return await self.remove_prefix_dynamic(context, cid)
        character = self.bot.db.execute("SELECT * FROM characters WHERE id = ?", (cid,)).fetchone()
        if character["owner"] != context.author.id:
            await context.send("You do not own this character!")
            return
        self.bot.db.execute("DELETE FROM prefixes WHERE cid = ? AND prefix = ?", (cid, prefix))
        self.bot.connection.commit()
        await context.send("Prefix removed!")

    async def remove_prefix_dynamic(self, context, cid: int = None):
        prefix = await self.__fetch_prefix(context, cid)
        if prefix is None:
            return
        self.bot.db.execute("DELETE FROM prefixes WHERE cid = ? AND prefix = ?", (cid, prefix))
        self.bot.connection.commit()
        await context.send("Prefix removed!")

    async def __fetch_prefix(self, context: commands.Context, cid: int = None):
        try:
            if cid is None:
                await context.send("Enter character id:")
                cid_message = await self.bot.wait_for("message", check=lambda m: m.author == context.author,
                                                      timeout=120)
                cid = int(cid_message.content)
                character = self.bot.db.execute("SELECT * FROM characters WHERE id = ?", (cid,)).fetchone()
                if character["owner"] != context.author.id:
                    await context.send("You do not own this character!")
                    return None
            await context.send("Enter prefix:")
            prefix_message = await self.bot.wait_for("message", check=lambda m: m.author == context.author, timeout=120)
            return prefix_message.content
        except asyncio.TimeoutError:
            await context.send("Timed out!")
            return None

    @commands.command()
    async def help(self, context: commands.Context):
        await context.send(self.help_str)

    @commands.command(aliases=["allow_channel"])
    async def whitelist_channel(self, context: commands.Context, channel: discord.TextChannel, cooldown: int = 0):
        info = self.bot.db.execute("SELECT * FROM channels WHERE id = ?", (channel.id,)).fetchone()
        if info is None:
            self.bot.db.execute("INSERT INTO channels (id, whitelisted, cooldown, type) VALUES (?, ?, ?, ?)",
                                (channel.id, 1, cooldown, "text"))
            info = self.bot.db.execute("SELECT * FROM channels WHERE id = ?", (channel.id,)).fetchone()
        elif info["whitelisted"] == 1:
            await context.send("Channel already whitelisted!")
            return
        elif info["whitelisted"] == 0:
            self.bot.db.execute("UPDATE channels SET whitelisted = ?, cooldown = ? WHERE id = ?", (1, cooldown, channel.id))
        self.bot.connection.commit()
        await context.send("Channel whitelisted!")

    @commands.command(aliases=["deny_channel"])
    async def blacklist_channel(self, context: commands.Context, channel: discord.TextChannel):
        info = self.bot.db.execute("SELECT * FROM channels WHERE id = ?", (channel.id,)).fetchone()
        if info is None:
            self.bot.db.execute("INSERT INTO channels (id, whitelisted, cooldown, type) VALUES (?, ?, ?, ?)",
                                (channel.id, 0, 0, "text"))
        if info["whitelisted"] == 0:
            await context.send("Channel already blacklisted!")
            return
        else:
            self.bot.db.execute("UPDATE channels SET whitelisted = ?, cooldown = ? WHERE id = ?", (0, 0, channel.id))
        self.bot.connection.commit()
        await context.send("Channel blacklisted!")

    @commands.command(aliases=["allow_category"])
    async def whitelist_category(self, context: commands.Context, category: discord.CategoryChannel):
        info = self.bot.db.execute("SELECT * FROM channels WHERE id = ?", (category.id,)).fetchone()
        if info is None:
            self.bot.db.execute("INSERT INTO channels (id, whitelisted, cooldown, type) VALUES (?, ?, ?, ?)",
                                (category.id, 1, 0, "category"))
        if info["whitelisted"] == 1:
            await context.send("Category already whitelisted!")
            return
        else:
            self.bot.db.execute("UPDATE channels SET whitelisted = ?, cooldown = ? WHERE id = ?", (1, 0, category.id))
        self.bot.connection.commit()
        await context.send("Category whitelisted!")

    @commands.command(aliases=["deny_category"])
    async def blacklist_category(self, context: commands.Context, category: discord.CategoryChannel):
        info = self.bot.db.execute("SELECT * FROM channels WHERE id = ?", (category.id,)).fetchone()
        if info is None:
            self.bot.db.execute("INSERT INTO channels (id, whitelisted, cooldown, type) VALUES (?, ?, ?, ?)",
                                (category.id, 0, 0, "category"))
        if info["whitelisted"] == 0:
            await context.send("Category already blacklisted!")
            return
        else:
            self.bot.db.execute("UPDATE channels SET whitelisted = ?, cooldown = ? WHERE id = ?", (0, 0, category.id))
        self.bot.connection.commit()
        await context.send("Category blacklisted!")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or message.guild is None or message.content[0] == '[' or message.content[0] == self.bot.config["prefix"]:
            return
        if isinstance(message.channel, discord.Thread):
            channel = message.channel.parent
        else:
            channel = message.channel

        char = self.handle_proxied_message(message)
        if char is None:
            char, found_prefix = self.fetch_char_info(message.content, message.author.id)
            if char is None or found_prefix is None:
                return
            full_message = message.content[len(found_prefix['prefix']):]
        else:
            full_message = message.content

        if len(full_message) == 0:
            await message.delete()

        if cooldown := self.get_channel_cooldown(channel.id, channel.category_id) is None:
            return  # channel is blacklisted
        if self.get_character_cooldown(char["id"], message.channel):
            await message.delete()
            await message.channel.send(f"This character is on cooldown! Please wait {cooldown} seconds")


        webhook = await self.create_webhook(channel)
        await self.send_message(webhook, message, char, full_message)
        await self.set_cooldown(cooldown, message.channel, char["id"])

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.user_id == self.bot.user.id:
            return

        channel = self.bot.get_channel(payload.channel_id)
        if isinstance(channel, discord.Thread):
            true_channel = channel.parent
            thread = True
        else:
            true_channel = channel
            thread = False
        if channel.guild is None:
            return

        webhook = None
        for i in await true_channel.webhooks():
            if i.user.id == self.bot.user.id:
                webhook = i
                break
        try:
            message = await webhook.fetch_message(payload.message_id, thread=channel if thread else discord.utils.MISSING)
        except (discord.NotFound, AttributeError):
            return
        if message.webhook_id != webhook.id:
            return
        message: discord.WebhookMessage

        character = self.bot.db.execute("SELECT * FROM characters WHERE name = ?",
                                        (message.author.display_name,)).fetchone()
        if character is None:
            return
        if payload.emoji.name == "✖":
            if not payload.user_id == character["owner"]:
                await message.remove_reaction(payload.emoji, payload.member)
                return
            await message.delete()
            return
        elif payload.emoji.name == "📝":
            if not payload.user_id == character["owner"]:
                await message.remove_reaction(payload.emoji, payload.member)
                return
            to_delete = await message.channel.send("Enter new message content:")
            try:
                msg = await self.bot.wait_for("message", check=lambda m: m.author == payload.member, timeout=120)
                await message.edit(content=msg.content)
                await msg.delete()
            except asyncio.TimeoutError:
                await message.channel.send("Timed out!")
            finally:
                await to_delete.delete()
                await message.remove_reaction(payload.emoji, payload.member)

        elif payload.emoji.name == "📋":
            member = self.bot.get_user(payload.user_id)
            await message.remove_reaction(payload.emoji, member)
            embed = self.__generate_character_embed(character)
            await member.send(embed=embed)
            await message.remove_reaction(payload.emoji, payload.member)

        elif payload.emoji.name == "❔":
            member = self.bot.get_user(payload.user_id)
            await member.send(self.help_str)

            await message.remove_reaction(payload.emoji, payload.member)

    def fetch_char_info(self, content, author):
        prefixes = self.bot.db.execute("SELECT * FROM prefixes").fetchall()
        found_prefix = None
        found_prefixes = [i for i in prefixes if content.startswith(i["prefix"])]
        char = None
        for prefix in found_prefixes:
            potential_cid = prefix["cid"]
            tmp = self.bot.db.execute("SELECT * FROM characters WHERE id = ?", (potential_cid,)).fetchone()
            if tmp["owner"] != author:
                continue
            else:
                found_prefix = prefix
                char = tmp
        return char, found_prefix

    @staticmethod
    async def update_image(cid, image):
        async with aiohttp.ClientSession() as session:
            async with session.get(image) as resp:
                if resp.status != 200:
                    return False
                with open(f"images/{cid}.png", "wb") as f:
                    f.write(await resp.read())

    def __generate_character_embed(self, character):
        embed = discord.Embed(
            title=f"Info for {character['name']}",
            color=discord.Color.gold(),
            timestamp=datetime.datetime.utcnow()
        )
        embed.add_field(name="Pronouns", value=character["pronouns"])
        embed.add_field(name="Race", value=character["race"])
        embed.add_field(name="Class(es)", value=character["classes"])
        embed.add_field(name="Physical Appearance", value=character["description"])
        embed.add_field(name="Demeanor", value=character["demeanor"])
        embed.add_field(name="Wiki", value=character["wiki"])
        embed.add_field(name="Player", value=f"<@{character['owner']}>")
        embed.set_image(url=self.api.format(character["id"]))
        return embed

    @commands.command()
    async def proxy(self, context: commands.Context, prefix: str):
        char, found_prefix = self.fetch_char_info(prefix, context.author.id)
        if char is None or found_prefix is None:
            to_delete = await context.send("Character not found!")
            await asyncio.sleep(3)
            await to_delete.delete()
            return
        channel = context.channel.id
        thread = 0
        if isinstance(context.channel, discord.Thread):
            channel = context.channel.parent.id
            thread = context.channel.id

        resp = self.bot.db.execute("SELECT * FROM proxies WHERE user_id = ? AND channel = ? AND thread = ?", (context.author.id, channel, thread)).fetchone()
        if resp is not None:
            to_delete = await context.send("You are already proxied in this channel!")
            await asyncio.sleep(3)
            await to_delete.delete()

        self.bot.db.execute("INSERT INTO proxies (user_id, cid, channel, thread) VALUES (?, ?, ?, ?)", (context.author.id, char['id'], channel, thread))
        self.bot.connection.commit()
        to_delete = await context.send("Character proxied!")
        await asyncio.sleep(3)
        await to_delete.delete()

    @commands.command()
    async def unproxy(self, context: commands.Context, prefix: str):
        char, found_prefix = self.fetch_char_info(prefix, context.author.id)
        if char is None or found_prefix is None:
            to_delete = await context.send("Character not found!")
            await asyncio.sleep(3)
            await to_delete.delete()
            return
        channel = context.channel.id
        thread = 0
        if isinstance(context.channel, discord.Thread):
            channel = context.channel.parent.id
            thread = context.channel.id

        self.bot.db.execute("DELETE FROM proxies WHERE user_id = ? AND cid = ? AND channel = ? AND thread = ?", (context.author.id, char['id'], channel, thread))
        self.bot.connection.commit()
        to_delete = await context.send("Character unproxied!")
        await asyncio.sleep(3)
        await to_delete.delete()

    def handle_proxied_message(self, message: discord.Message) -> bool:
        if isinstance(message.channel, discord.Thread):
            channel = message.channel.parent.id
        else:
            channel = message.channel.id
        resp = self.bot.db.execute("SELECT thread, cid FROM proxies WHERE user_id = ? AND channel = ?", (message.author.id,channel)).fetchall()
        for i in resp:
            if i["thread"] == message.channel.id:
                char = self.bot.db.execute("SELECT * FROM characters WHERE id = ?", (i["cid"],)).fetchone()

                return char

    def get_channel_cooldown(self, channel_id, category_id):
        channel_info = self.bot.db.execute(
            "SELECT * FROM channels WHERE id = ? AND whitelisted = 1", (channel_id,)).fetchone()
        category_info = None
        if not channel_info and category_id:
            category_info = self.bot.db.execute(
                "SELECT * FROM channels WHERE id = ? AND whitelisted = 1", (category_id,)).fetchone()
            if not category_info:
                return
        if not channel_info and not category_info:
            return

        cooldown = channel_info["cooldown"] if channel_info is not None else category_info["cooldown"]
        return cooldown

    def get_character_cooldown(self, cid: int, channel: discord.TextChannel):
        if cid in self.cooldowns:
            for i in self.cooldowns[cid]:
                if i.channel == channel:
                    if i.cooldown <= 0:
                        self.cooldowns[cid].remove(i)
                        return False
                    else:
                        return True

    async def send_message(self, webhook: discord.Webhook, message: discord.Message, char: dict, content: str):
        kwargs = {
            "username": char["name"],
            "avatar_url": self.api.format(char["id"]),
            "content": content,
            "wait": True
        }

        if message.reference is not None:
            message_reference = await message.channel.fetch_message(message.reference.message_id)
            jump_url = message_reference.jump_url
            kwargs["content"] += f"\n\n[Replied message]({jump_url})"
        if isinstance(message.channel, discord.Thread):
            kwargs["thread"] = message.channel
        await message.delete()
        msg = await webhook.send(**kwargs)
        await msg.add_reaction("✖")
        await msg.add_reaction("❔")
        await msg.add_reaction("📝")
        await msg.add_reaction("📋")

    async def create_webhook(self, channel):
        webhooks = await channel.webhooks()
        for i in webhooks:
            if i.user.id == self.bot.user.id:
                webhook = i
                break
        else:
            webhook = await channel.create_webhook(name="hook")

        return webhook

    async def set_cooldown(self, cooldown, channel, cid):
        if cooldown > 0:
            if cid not in self.cooldowns:
                self.cooldowns[cid] = []

            cooldown_obj = Cooldown(cid, channel, cooldown)
            self.cooldowns[cid].append(cooldown_obj)
            task = asyncio.create_task(self.cooldowns[cid][-1].run())
            task.set_name(f"Cooldown for {cid} in {channel.id}")
            task.add_done_callback(lambda _: self.cooldowns[cid].remove(cooldown_obj))

async def setup(bot):
    await bot.add_cog(Character(bot))
