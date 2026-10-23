import discord
from discord.ext import commands
from utils.emojis import e
from database import db


class Eventos(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        canais = db.get_canais_config()
        if not canais.get("boas_vindas_id"):
            return
        canal = member.guild.get_channel(int(canais["boas_vindas_id"]))
        if not canal:
            return
        em = discord.Embed(
            title=f"{e.heart} Bem-vindo(a)!",
            description=f"Olá {member.mention}, seja bem-vindo(a) ao **{member.guild.name}**!\nAgora somos **{member.guild.member_count}** membros.",
            color=0x2ecc71
        )
        em.set_thumbnail(url=member.display_avatar.url)
        em.set_footer(text=f"ID: {member.id}")
        await canal.send(embed=em)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        canais = db.get_canais_config()
        if not canais.get("boas_vindas_id"):
            return
        canal = member.guild.get_channel(int(canais["boas_vindas_id"]))
        if not canal:
            return
        em = discord.Embed(
            title=f"{e.warn} Membro saiu",
            description=f"**{member}** deixou o servidor.\nAgora somos **{member.guild.member_count}** membros.",
            color=0xe74c3c
        )
        em.set_thumbnail(url=member.display_avatar.url)
        await canal.send(embed=em)

    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user: discord.User):
        canais = db.get_canais_config()
        if not canais.get("log_mod_id"):
            return
        canal = guild.get_channel(int(canais["log_mod_id"]))
        if not canal:
            return
        em = discord.Embed(title=f"{e.ban} Membro Banido", color=0xe74c3c)
        em.add_field(name="Usuário", value=f"{user} (`{user.id}`)")
        em.set_thumbnail(url=user.display_avatar.url)
        await canal.send(embed=em)

    @commands.Cog.listener()
    async def on_member_unban(self, guild: discord.Guild, user: discord.User):
        canais = db.get_canais_config()
        if not canais.get("log_mod_id"):
            return
        canal = guild.get_channel(int(canais["log_mod_id"]))
        if not canal:
            return
        em = discord.Embed(title=f"{e.unlock} Membro Desbanido", color=0x2ecc71)
        em.add_field(name="Usuário", value=f"{user} (`{user.id}`)")
        await canal.send(embed=em)

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if message.author.bot:
            return
        canais = db.get_canais_config()
        if not canais.get("log_mod_id"):
            return
        canal = message.guild.get_channel(int(canais["log_mod_id"])) if message.guild else None
        if not canal:
            return
        em = discord.Embed(title=f"{e.delete} Mensagem Deletada", color=0xe74c3c)
        em.add_field(name="Autor", value=message.author.mention, inline=True)
        em.add_field(name="Canal", value=message.channel.mention, inline=True)
        em.add_field(name="Conteúdo", value=message.content[:1000] or "*(sem texto)*", inline=False)
        await canal.send(embed=em)

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if before.author.bot or before.content == after.content:
            return
        canais = db.get_canais_config()
        if not canais.get("log_mod_id"):
            return
        canal = before.guild.get_channel(int(canais["log_mod_id"])) if before.guild else None
        if not canal:
            return
        em = discord.Embed(title=f"{e.edit} Mensagem Editada", color=0xf39c12)
        em.add_field(name="Autor", value=before.author.mention, inline=True)
        em.add_field(name="Canal", value=before.channel.mention, inline=True)
        em.add_field(name="Antes", value=before.content[:500] or "*(vazio)*", inline=False)
        em.add_field(name="Depois", value=after.content[:500] or "*(vazio)*", inline=False)
        await canal.send(embed=em)


async def setup(bot):
    await bot.add_cog(Eventos(bot))
