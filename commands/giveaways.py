import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timezone, timedelta
import random
import json
from utils.emojis import e
from utils.helpers import success_embed, error_embed, info_embed
from database import db


def parse_duracao(texto: str) -> int:
    """Converte '1h', '30m', '2d' em segundos"""
    texto = texto.strip().lower()
    if texto.endswith("d"):
        return int(texto[:-1]) * 86400
    elif texto.endswith("h"):
        return int(texto[:-1]) * 3600
    elif texto.endswith("m"):
        return int(texto[:-1]) * 60
    return int(texto)


class ParticipantesView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Participar", style=discord.ButtonStyle.green,
                       emoji="🎉", custom_id="giveaway_participar")
    async def participar(self, inter: discord.Interaction, button: discord.ui.Button):
        giveaway = db.get_giveaway_por_message(str(inter.message.id))
        if not giveaway:
            return await inter.response.send_message("Sorteio não encontrado.", ephemeral=True)

        if giveaway["status"] != "ativo":
            return await inter.response.send_message(
                embed=error_embed("Encerrado", "Este sorteio já foi encerrado."), ephemeral=True
            )

        termina_em = datetime.fromisoformat(giveaway["termina_em"])
        if datetime.now(timezone.utc) > termina_em.replace(tzinfo=timezone.utc):
            return await inter.response.send_message(
                embed=error_embed("Encerrado", "O tempo deste sorteio já expirou."), ephemeral=True
            )

        # Verificar cargo requisito
        if giveaway.get("requisito_cargo_id"):
            cargo = inter.guild.get_role(int(giveaway["requisito_cargo_id"]))
            if cargo and cargo not in inter.user.roles:
                return await inter.response.send_message(
                    embed=error_embed("Sem permissão", f"Você precisa do cargo {cargo.mention} para participar."),
                    ephemeral=True
                )

        participantes = json.loads(giveaway["participantes"])
        uid = str(inter.user.id)

        if uid in participantes:
            participantes.remove(uid)
            db.atualizar_participantes(giveaway["id"], participantes)
            await inter.response.send_message(
                embed=info_embed("Removido", "Você saiu do sorteio."), ephemeral=True
            )
        else:
            participantes.append(uid)
            db.atualizar_participantes(giveaway["id"], participantes)
            await inter.response.send_message(
                embed=success_embed("Inscrito!", f"Você está participando! Total: **{len(participantes)}**"),
                ephemeral=True
            )

        # Atualizar embed
        await atualizar_embed_giveaway(inter.message, giveaway, len(participantes))


async def atualizar_embed_giveaway(message: discord.Message, giveaway: dict, total: int):
    termina_em = datetime.fromisoformat(giveaway["termina_em"])
    ts = int(termina_em.replace(tzinfo=timezone.utc).timestamp())
    em = discord.Embed(
        title=f"{e.giveaway} {giveaway['premio']}",
        color=0xf1c40f
    )
    em.add_field(name=f"{e.clock} Termina", value=f"<t:{ts}:R>", inline=True)
    em.add_field(name=f"{e.trophy} Ganhadores", value=str(giveaway["ganhadores"]), inline=True)
    em.add_field(name=f"{e.members} Participantes", value=str(total), inline=True)
    try:
        await message.edit(embed=em)
    except Exception:
        pass


class Giveaways(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        bot.add_view(ParticipantesView())

    giveaway_group = app_commands.Group(name="giveaway", description="Sistema de sorteios")

    @giveaway_group.command(name="criar", description="Cria um novo sorteio.")
    @app_commands.describe(
        canal="Canal do sorteio",
        premio="O que será sorteado",
        duracao="Duração: 1d, 12h, 30m",
        ganhadores="Quantidade de ganhadores",
        cargo_requisito="Cargo necessário para participar"
    )
    @app_commands.default_permissions(administrator=True)
    async def criar(self, inter: discord.Interaction, canal: discord.TextChannel,
                    premio: str, duracao: str, ganhadores: int = 1,
                    cargo_requisito: discord.Role = None):
        await inter.response.defer(ephemeral=True)
        try:
            segundos = parse_duracao(duracao)
        except ValueError:
            return await inter.followup.send(
                embed=error_embed("Formato inválido", "Use: `1d`, `12h`, `30m`"), ephemeral=True
            )

        termina_em = datetime.now(timezone.utc) + timedelta(seconds=segundos)
        ts = int(termina_em.timestamp())

        gid = db.criar_giveaway(
            channel_id=canal.id,
            premio=premio,
            ganhadores=ganhadores,
            criado_por=inter.user.id,
            termina_em=termina_em.isoformat(),
            requisito_cargo_id=cargo_requisito.id if cargo_requisito else None
        )

        em = discord.Embed(
            title=f"{e.giveaway} {premio}",
            color=0xf1c40f
        )
        em.add_field(name=f"{e.clock} Termina", value=f"<t:{ts}:R>", inline=True)
        em.add_field(name=f"{e.trophy} Ganhadores", value=str(ganhadores), inline=True)
        em.add_field(name=f"{e.members} Participantes", value="0", inline=True)
        if cargo_requisito:
            em.add_field(name=f"{e.role} Requisito", value=cargo_requisito.mention, inline=True)
        em.set_footer(text=f"ID: {gid} • Criado por {inter.user}")

        msg = await canal.send(embed=em, view=ParticipantesView())
        db.atualizar_giveaway_message(gid, msg.id)

        await inter.followup.send(
            embed=success_embed("Sorteio Criado", f"Sorteio criado em {canal.mention}!"),
            ephemeral=True
        )

    @giveaway_group.command(name="encerrar", description="Encerra um sorteio e sorteia os ganhadores.")
    @app_commands.describe(giveaway_id="ID do sorteio")
    @app_commands.default_permissions(administrator=True)
    async def encerrar(self, inter: discord.Interaction, giveaway_id: int):
        await inter.response.defer(ephemeral=True)
        giveaway = db.get_giveaway(giveaway_id)
        if not giveaway:
            return await inter.followup.send(embed=error_embed("Erro", "Sorteio não encontrado."), ephemeral=True)
        if giveaway["status"] != "ativo":
            return await inter.followup.send(embed=error_embed("Erro", "Sorteio já encerrado."), ephemeral=True)

        await self._sortear(inter, giveaway)

    @giveaway_group.command(name="reroll", description="Sorteia novamente os ganhadores.")
    @app_commands.describe(giveaway_id="ID do sorteio")
    @app_commands.default_permissions(administrator=True)
    async def reroll(self, inter: discord.Interaction, giveaway_id: int):
        await inter.response.defer(ephemeral=True)
        giveaway = db.get_giveaway(giveaway_id)
        if not giveaway:
            return await inter.followup.send(embed=error_embed("Erro", "Sorteio não encontrado."), ephemeral=True)

        await self._sortear(inter, giveaway, reroll=True)

    async def _sortear(self, inter: discord.Interaction, giveaway: dict, reroll=False):
        participantes = json.loads(giveaway["participantes"])
        qtd = giveaway["ganhadores"]

        if not participantes:
            return await inter.followup.send(
                embed=error_embed("Sem participantes", "Ninguém participou deste sorteio."), ephemeral=True
            )

        vencedores_ids = random.sample(participantes, min(qtd, len(participantes)))
        db.finalizar_giveaway(giveaway["id"], vencedores_ids)

        canal = inter.guild.get_channel(int(giveaway["channel_id"]))
        mencoes = " ".join(f"<@{uid}>" for uid in vencedores_ids)

        em = discord.Embed(
            title=f"{e.trophy} {'Reroll — ' if reroll else ''}Sorteio Encerrado!",
            description=f"**Prêmio:** {giveaway['premio']}\n\n{e.sparkles} **Ganhador(es):** {mencoes}",
            color=0xf1c40f
        )
        em.set_footer(text=f"ID: {giveaway['id']}")

        if canal:
            await canal.send(embed=em)
            # Tentar editar a mensagem original
            if giveaway.get("message_id"):
                try:
                    msg = await canal.fetch_message(int(giveaway["message_id"]))
                    em_enc = discord.Embed(
                        title=f"🎉 {giveaway['premio']} — ENCERRADO",
                        description=f"**Ganhador(es):** {mencoes}",
                        color=0x95a5a6
                    )
                    await msg.edit(embed=em_enc, view=None)
                except Exception:
                    pass

        await inter.followup.send(
            embed=success_embed("Sorteio Encerrado", f"Ganhadores: {mencoes}"), ephemeral=True
        )

    @giveaway_group.command(name="lista", description="Lista todos os sorteios ativos.")
    @app_commands.default_permissions(administrator=True)
    async def lista(self, inter: discord.Interaction):
        giveaways = db.get_giveaways_ativos()
        if not giveaways:
            return await inter.response.send_message(
                embed=info_embed("Sem sorteios", "Nenhum sorteio ativo no momento."), ephemeral=True
            )
        em = discord.Embed(title=f"{e.giveaway} Sorteios Ativos", color=0xf1c40f)
        for g in giveaways[:10]:
            participantes = json.loads(g["participantes"])
            em.add_field(
                name=f"[{g['id']}] {g['premio']}",
                value=f"Participantes: {len(participantes)} | Ganhadores: {g['ganhadores']} | Termina: {g['termina_em'][:16]}",
                inline=False
            )
        await inter.response.send_message(embed=em, ephemeral=True)

    @commands.Cog.listener()
    async def on_ready(self):
        """Verifica sorteios expirados ao iniciar"""
        import asyncio
        await asyncio.sleep(5)
        await self.verificar_sorteios()

    async def verificar_sorteios(self):
        """Encerra sorteios que já expiraram"""
        giveaways = db.get_giveaways_ativos()
        now = datetime.now(timezone.utc)
        for g in giveaways:
            termina_em = datetime.fromisoformat(g["termina_em"]).replace(tzinfo=timezone.utc)
            if now > termina_em:
                participantes = json.loads(g["participantes"])
                if not participantes:
                    db.finalizar_giveaway(g["id"], [])
                    continue
                qtd = g["ganhadores"]
                vencedores = random.sample(participantes, min(qtd, len(participantes)))
                db.finalizar_giveaway(g["id"], vencedores)

                for guild in self.bot.guilds:
                    canal = guild.get_channel(int(g["channel_id"]))
                    if canal:
                        mencoes = " ".join(f"<@{uid}>" for uid in vencedores)
                        em = discord.Embed(
                            title=f"{e.trophy} Sorteio Encerrado!",
                            description=f"**Prêmio:** {g['premio']}\n\n{e.sparkles} **Ganhador(es):** {mencoes}",
                            color=0xf1c40f
                        )
                        await canal.send(embed=em)


async def setup(bot):
    await bot.add_cog(Giveaways(bot))
