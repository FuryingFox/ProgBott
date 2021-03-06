# Discord Packages
from discord.ext import commands

# Bot Utilities
from cogs.utils.db import DB
from cogs.utils.defaults import easy_embed
from cogs.utils.server import Server

import os
import random
import string
import threading

import requests


class Github(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        database = DB(data_dir=self.bot.data_dir)
        database.populate_tables()

    def id_generator(self, size=6, chars=string.ascii_uppercase + string.digits):
        return ''.join(random.choice(chars) for _ in range(size))

    @commands.guild_only()
    @commands.group(name="github")
    async def ghGroup(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @ghGroup.command(name="auth")
    async def auth(self, ctx):
        # First - attempt to localize if the user has already registered.
        random_string = self.id_generator()
        is_user_registered = self.is_user_registered(ctx.author.id, random_string)

        if is_user_registered:
            return await ctx.send(ctx.author.mention + " du er allerede registrert!")

        try:
            discord_id_and_key = "{}:{}".format(ctx.author.id, random_string)
            registration_link = "https://github.com/login/oauth/authorize" \
                                "?client_id={}&redirect_uri={}?params={}".format(
                                    self.bot.settings.github["client_id"],
                                    self.bot.settings.github["callback_uri"], discord_id_and_key
                                )
            await ctx.author.send("Hei! For å verifisere GitHub kontoen din, følg denne lenken: {}."
                                  .format(registration_link))
        except Exception:
            return await ctx.send(ctx.author.mention + " du har ikke på innstillingen for å motta meldinger.")

        return await ctx.send(ctx.author.mention + " sender ny registreringslenke på DM!")

    @ghGroup.command(name="remove")
    async def remove(self, ctx):
        user_mention = "<@{}>: ".format(ctx.author.id)
        conn = DB(data_dir=self.bot.data_dir).connection

        cursor = conn.cursor()

        cursor.execute("DELETE FROM github_users WHERE discord_id={}".format(ctx.author.id))

        conn.commit()

        return await ctx.send(user_mention + "fjernet Githuben din.")

    @ghGroup.command(name="me")
    async def me(self, ctx):
        user = self.get_user(ctx.author.id)

        if user is None:
            return await ctx.send("Du har ikke registrert en bruker enda.")

        (_id, discord_id, auth_token, github_username) = user

        user = requests.get("https://api.github.com/user", headers={
            'Authorization': "token " + auth_token,
            'Accept': 'application/json'
        }).json()

        embed = easy_embed(self, ctx)

        embed.title = user["login"]
        embed.description = user["html_url"]

        embed.set_thumbnail(url=user["avatar_url"])

        embed.add_field(name="Følgere / Følger",
                        value="{} / {}".format(user["followers"], user["following"]), inline=False)
        embed.add_field(name="Biografi", value=user["bio"], inline=False)
        embed.add_field(name="Offentlige repos", value=user["public_repos"], inline=False)

        return await ctx.send(embed=embed)

    def get_user(self, discord_id):
        conn = DB(data_dir=self.bot.data_dir).connection

        cursor = conn.cursor()

        cursor.execute("SELECT * FROM github_users WHERE discord_id={}".format(discord_id))

        rows = cursor.fetchone()

        return rows

    def is_user_registered(self, discord_id, random_string):
        conn = DB(data_dir=self.bot.data_dir).connection

        if conn is None:
            return False

        cursor = conn.cursor()

        cursor.execute("SELECT * FROM github_users WHERE discord_id={}".format(discord_id))

        rows = cursor.fetchone()

        if rows is not None:
            conn.close()
            return True

        cursor.execute("SELECT * FROM pending_users WHERE discord_id={}".format(discord_id))

        row = cursor.fetchone()

        if row is not None:
            cursor.execute("DELETE FROM pending_users WHERE discord_id={}".format(discord_id))

        cursor.execute("INSERT INTO pending_users(discord_id, verification) VALUES(?, ?);", (discord_id, random_string))

        conn.commit()
        conn.close()
        return False


def check_folder(data_dir):
    f = f'{data_dir}/db'
    if not os.path.exists(f):
        os.makedirs(f)


def start_server(bot):
    server = threading.Thread(target=Server, kwargs={'data_dir': bot.data_dir, 'settings': bot.settings.github})
    server.start()


def setup(bot):
    check_folder(bot.data_dir)
    start_server(bot)
    bot.add_cog(Github(bot))
