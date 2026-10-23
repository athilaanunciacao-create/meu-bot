import discord
from discord.ext import commands, tasks
import json
import os
import asyncio
from database.db import init_db
from utils.emojis import e

# Carregar config
with open("config.json", "r", encoding="utf-8") as f:
    config = json.load(f)

# Token vem da variável de ambiente (seguro para GitHub/Render)
TOKEN = os.environ.get("BOT_TOKEN") or config.get("token", "")
SERVER_ID = int(config["server_id"])

# Intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True


class Bot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix="!",
            intents=intents,
            help_command=None
        )

    async def setup_hook(self):
        # Inicializar banco de dados
        init_db()

        # Carregar extensões
        extensoes = [
            "commands.moderacao",
            "commands.tickets",
            "commands.loja",
            "commands.giveaways",
            "commands.admin",
            "events.eventos",
        ]
        for ext in extensoes:
            try:
                await self.load_extension(ext)
                print(f"[+] {ext} carregado")
            except Exception as ex:
                print(f"[!] Erro ao carregar {ext}: {ex}")

        # Sincronizar slash commands no servidor
        guild = discord.Object(id=SERVER_ID)
        self.tree.copy_global_to(guild=guild)
        synced = await self.tree.sync(guild=guild)
        print(f"[✓] {len(synced)} comandos sincronizados no servidor {SERVER_ID}")

    async def on_ready(self):
        print(f"\n{'='*40}")
        print(f"  Bot online: {self.user}")
        print(f"  ID: {self.user.id}")
        print(f"  Servidores: {len(self.guilds)}")
        print(f"{'='*40}\n")
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="a loja | /painel"
            )
        )
        # Iniciar task de verificação de sorteios
        if not verificar_giveaways.is_running():
            verificar_giveaways.start(self)

    async def on_command_error(self, ctx, error):
        pass

    async def on_app_command_error(self, inter: discord.Interaction, error: discord.app_commands.AppCommandError):
        msg = str(error)
        if "Missing Permissions" in msg:
            msg = "Você não tem permissão para usar este comando."
        elif "Missing Access" in msg:
            msg = "Não tenho permissão para executar essa ação."
        try:
            await inter.response.send_message(
                embed=discord.Embed(description=f"{e.wrong} {msg}", color=0xe74c3c),
                ephemeral=True
            )
        except Exception:
            pass


bot = Bot()


@tasks.loop(minutes=1)
async def verificar_giveaways(bot: Bot):
    """Verifica e encerra sorteios expirados a cada 1 minuto"""
    from database import db
    from datetime import datetime, timezone
    import random, json

    giveaways = db.get_giveaways_ativos()
    now = datetime.now(timezone.utc)

    for g in giveaways:
        try:
            termina_em = datetime.fromisoformat(g["termina_em"]).replace(tzinfo=timezone.utc)
            if now >= termina_em:
                participantes = json.loads(g["participantes"])
                if not participantes:
                    db.finalizar_giveaway(g["id"], [])
                    continue

                qtd = g["ganhadores"]
                vencedores = random.sample(participantes, min(qtd, len(participantes)))
                db.finalizar_giveaway(g["id"], vencedores)

                for guild in bot.guilds:
                    canal = guild.get_channel(int(g["channel_id"]))
                    if canal:
                        mencoes = " ".join(f"<@{uid}>" for uid in vencedores)
                        em = discord.Embed(
                            title=f"{e.trophy} Sorteio Encerrado!",
                            description=f"**Prêmio:** {g['premio']}\n\n{e.sparkles} **Ganhador(es):** {mencoes}",
                            color=0xf1c40f
                        )
                        await canal.send(embed=em)

                        if g.get("message_id"):
                            try:
                                msg = await canal.fetch_message(int(g["message_id"]))
                                em_enc = discord.Embed(
                                    title=f"🎉 {g['premio']} — ENCERRADO",
                                    description=f"**Ganhador(es):** {mencoes}",
                                    color=0x95a5a6
                                )
                                await msg.edit(embed=em_enc, view=None)
                            except Exception:
                                pass
        except Exception as ex:
            print(f"[Giveaway] Erro ao processar sorteio {g['id']}: {ex}")


if __name__ == "__main__":
    bot.run(TOKEN)
