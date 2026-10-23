import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timezone
from utils.emojis import e
from utils.helpers import success_embed, error_embed, info_embed, load_config
from database import db


class Moderacao(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="banir", description="Bane um membro do servidor.")
    @app_commands.describe(membro="Membro a ser banido", motivo="Motivo do banimento")
    @app_commands.default_permissions(ban_members=True)
    async def banir(self, inter: discord.Interaction, membro: discord.Member, motivo: str = "Não informado"):
        if membro.id == inter.guild.owner_id:
            return await inter.response.send_message(embed=error_embed("Erro", "Não é possível banir o dono do servidor."), ephemeral=True)
        if inter.user.top_role <= membro.top_role and inter.user.id != inter.guild.owner_id:
            return await inter.response.send_message(embed=error_embed("Erro", "Você não pode banir alguém com cargo igual ou superior ao seu."), ephemeral=True)
        try:
            await membro.ban(reason=f"{motivo} | Banido por {inter.user}")
            db.mod_logs if False else None
            await inter.response.send_message(embed=success_embed("Membro Banido", f"{e.ban} **{membro}** foi banido.\n**Motivo:** {motivo}"))
        except Exception as ex:
            await inter.response.send_message(embed=error_embed("Erro", f"Não foi possível banir: {ex}"), ephemeral=True)

    @app_commands.command(name="desbanir", description="Remove o banimento de um usuário.")
    @app_commands.describe(usuario_id="ID do usuário a desbanir", motivo="Motivo")
    @app_commands.default_permissions(ban_members=True)
    async def desbanir(self, inter: discord.Interaction, usuario_id: str, motivo: str = "Não informado"):
        try:
            user = await self.bot.fetch_user(int(usuario_id))
            await inter.guild.unban(user, reason=motivo)
            await inter.response.send_message(embed=success_embed("Membro Desbanido", f"{e.unlock} **{user}** foi desbanido.\n**Motivo:** {motivo}"))
        except discord.NotFound:
            await inter.response.send_message(embed=error_embed("Erro", "Usuário não encontrado ou não está banido."), ephemeral=True)
        except Exception as ex:
            await inter.response.send_message(embed=error_embed("Erro", str(ex)), ephemeral=True)

    @app_commands.command(name="expulsar", description="Expulsa um membro do servidor.")
    @app_commands.describe(membro="Membro a ser expulso", motivo="Motivo")
    @app_commands.default_permissions(kick_members=True)
    async def expulsar(self, inter: discord.Interaction, membro: discord.Member, motivo: str = "Não informado"):
        if membro.id == inter.guild.owner_id:
            return await inter.response.send_message(embed=error_embed("Erro", "Não é possível expulsar o dono."), ephemeral=True)
        if inter.user.top_role <= membro.top_role and inter.user.id != inter.guild.owner_id:
            return await inter.response.send_message(embed=error_embed("Erro", "Cargo insuficiente."), ephemeral=True)
        try:
            await membro.kick(reason=f"{motivo} | Por {inter.user}")
            await inter.response.send_message(embed=success_embed("Membro Expulso", f"{e.hammer} **{membro}** foi expulso.\n**Motivo:** {motivo}"))
        except Exception as ex:
            await inter.response.send_message(embed=error_embed("Erro", str(ex)), ephemeral=True)

    @app_commands.command(name="silenciar", description="Silencia um membro por um período.")
    @app_commands.describe(membro="Membro", minutos="Duração em minutos (máx 40320)", motivo="Motivo")
    @app_commands.default_permissions(moderate_members=True)
    async def silenciar(self, inter: discord.Interaction, membro: discord.Member, minutos: int = 10, motivo: str = "Não informado"):
        import datetime as dt
        if minutos < 1 or minutos > 40320:
            return await inter.response.send_message(embed=error_embed("Erro", "Duração entre 1 e 40320 minutos."), ephemeral=True)
        try:
            until = discord.utils.utcnow() + dt.timedelta(minutes=minutos)
            await membro.timeout(until, reason=motivo)
            await inter.response.send_message(embed=success_embed("Membro Silenciado", f"{e.lock} **{membro}** silenciado por **{minutos} min**.\n**Motivo:** {motivo}"))
        except Exception as ex:
            await inter.response.send_message(embed=error_embed("Erro", str(ex)), ephemeral=True)

    @app_commands.command(name="dessilenciar", description="Remove o silêncio de um membro.")
    @app_commands.describe(membro="Membro")
    @app_commands.default_permissions(moderate_members=True)
    async def dessilenciar(self, inter: discord.Interaction, membro: discord.Member):
        try:
            await membro.timeout(None)
            await inter.response.send_message(embed=success_embed("Silêncio Removido", f"{e.unlock} **{membro}** pode falar novamente."))
        except Exception as ex:
            await inter.response.send_message(embed=error_embed("Erro", str(ex)), ephemeral=True)

    @app_commands.command(name="limpar", description="Apaga mensagens do canal.")
    @app_commands.describe(quantidade="Quantidade de mensagens (1-100)")
    @app_commands.default_permissions(manage_messages=True)
    async def limpar(self, inter: discord.Interaction, quantidade: int = 10):
        if quantidade < 1 or quantidade > 100:
            return await inter.response.send_message(embed=error_embed("Erro", "Entre 1 e 100 mensagens."), ephemeral=True)
        await inter.response.defer(ephemeral=True)
        deleted = await inter.channel.purge(limit=quantidade)
        await inter.followup.send(embed=success_embed("Mensagens Apagadas", f"{e.delete} **{len(deleted)}** mensagens removidas."), ephemeral=True)

    @app_commands.command(name="lock", description="Trava o canal para membros.")
    @app_commands.default_permissions(manage_channels=True)
    async def lock(self, inter: discord.Interaction):
        overwrite = inter.channel.overwrites_for(inter.guild.default_role)
        overwrite.send_messages = False
        await inter.channel.set_permissions(inter.guild.default_role, overwrite=overwrite)
        await inter.response.send_message(embed=success_embed("Canal Travado", f"{e.lock} Este canal foi bloqueado."))

    @app_commands.command(name="unlock", description="Destrava o canal para membros.")
    @app_commands.default_permissions(manage_channels=True)
    async def unlock(self, inter: discord.Interaction):
        overwrite = inter.channel.overwrites_for(inter.guild.default_role)
        overwrite.send_messages = True
        await inter.channel.set_permissions(inter.guild.default_role, overwrite=overwrite)
        await inter.response.send_message(embed=success_embed("Canal Destravado", f"{e.unlock} Este canal foi desbloqueado."))

    @app_commands.command(name="nuke", description="Recria o canal apagando todas as mensagens.")
    @app_commands.default_permissions(manage_channels=True)
    async def nuke(self, inter: discord.Interaction):
        canal = inter.channel
        novo = await canal.clone(reason=f"Nuke por {inter.user}")
        await canal.delete()
        await novo.send(embed=success_embed("Canal Nukado", f"{e.fire} Canal recriado por {inter.user.mention}."))

    @app_commands.command(name="falar", description="Faz o bot enviar uma mensagem em um canal.")
    @app_commands.describe(canal="Canal destino", mensagem="Mensagem a enviar")
    @app_commands.default_permissions(administrator=True)
    async def falar(self, inter: discord.Interaction, canal: discord.TextChannel, mensagem: str):
        await canal.send(mensagem)
        await inter.response.send_message(embed=success_embed("Mensagem Enviada", f"Mensagem enviada em {canal.mention}."), ephemeral=True)

    @app_commands.command(name="perfil", description="Exibe informações de um membro.")
    @app_commands.describe(membro="Membro (deixe vazio para ver o seu)")
    async def perfil(self, inter: discord.Interaction, membro: discord.Member = None):
        membro = membro or inter.user
        criado_em = membro.created_at.strftime("%d/%m/%Y")
        entrou_em = membro.joined_at.strftime("%d/%m/%Y") if membro.joined_at else "?"
        cargos = [r.mention for r in reversed(membro.roles) if r != inter.guild.default_role]
        em = discord.Embed(
            title=f"{e.member} Perfil de {membro.display_name}",
            color=membro.color if membro.color.value else 0x5865F2
        )
        em.set_thumbnail(url=membro.display_avatar.url)
        em.add_field(name=f"{e.information} ID", value=membro.id, inline=True)
        em.add_field(name=f"{e.calendar} Conta criada", value=criado_em, inline=True)
        em.add_field(name=f"{e.clock} Entrou em", value=entrou_em, inline=True)
        em.add_field(name=f"{e.role} Cargos ({len(cargos)})", value=" ".join(cargos[:10]) if cargos else "Nenhum", inline=False)
        await inter.response.send_message(embed=em)

    @app_commands.command(name="botinfo", description="Informações sobre o bot.")
    async def botinfo(self, inter: discord.Interaction):
        import psutil, platform
        cpu = psutil.cpu_percent()
        ram = psutil.virtual_memory()
        em = discord.Embed(title=f"{e.robot} Informações do Bot", color=0x5865F2)
        em.add_field(name=f"{e.members} Servidores", value=len(self.bot.guilds), inline=True)
        em.add_field(name=f"{e.member} Usuários", value=sum(g.member_count for g in self.bot.guilds), inline=True)
        em.add_field(name=f"{e.chart} CPU", value=f"{cpu}%", inline=True)
        em.add_field(name=f"{e.bulb} RAM", value=f"{ram.percent}%", inline=True)
        em.add_field(name=f"{e.python} Python", value=platform.python_version(), inline=True)
        em.set_thumbnail(url=self.bot.user.display_avatar.url)
        await inter.response.send_message(embed=em)


async def setup(bot):
    await bot.add_cog(Moderacao(bot))
