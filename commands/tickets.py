import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timezone
from utils.emojis import e
from utils.helpers import success_embed, error_embed, info_embed
from database import db


class AbrirTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Abrir Ticket", style=discord.ButtonStyle.blurple,
                       emoji="🎫", custom_id="abrir_ticket_btn")
    async def abrir_ticket(self, inter: discord.Interaction, button: discord.ui.Button):
        config = db.get_tickets_config()
        if not config.get("categoria_id"):
            return await inter.response.send_message(
                embed=error_embed("Tickets não configurados", "Use `/ticket configurar` primeiro."),
                ephemeral=True
            )

        # Verificar limite por usuário
        max_tickets = config.get("max_por_usuario") or 1
        abertos = db.get_tickets_abertos_usuario(inter.user.id)
        if len(abertos) >= max_tickets:
            return await inter.response.send_message(
                embed=error_embed("Limite atingido", f"Você já tem **{len(abertos)}** ticket(s) aberto(s)."),
                ephemeral=True
            )

        await inter.response.defer(ephemeral=True)

        categoria = inter.guild.get_channel(int(config["categoria_id"]))
        if not categoria:
            return await inter.followup.send(embed=error_embed("Erro", "Categoria não encontrada."), ephemeral=True)

        # Permissões do canal
        overwrites = {
            inter.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            inter.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            inter.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        }
        if config.get("cargo_atendente_id"):
            cargo = inter.guild.get_role(int(config["cargo_atendente_id"]))
            if cargo:
                overwrites[cargo] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

        canal = await inter.guild.create_text_channel(
            name=f"ticket-{inter.user.name}",
            category=categoria,
            overwrites=overwrites
        )

        db.criar_ticket(canal.id, inter.user.id, "Suporte Geral")

        msg_bv = (config.get("mensagem_boas_vindas") or "Olá {user}, aguarde um atendente!").replace("{user}", inter.user.mention)

        em = discord.Embed(
            title=f"{e.ticket} Ticket Aberto",
            description=msg_bv,
            color=0x5865F2
        )
        em.set_footer(text=f"Ticket de {inter.user} • {datetime.now().strftime('%d/%m/%Y %H:%M')}")

        await canal.send(
            content=inter.user.mention,
            embed=em,
            view=ControlesTicketView()
        )

        await inter.followup.send(
            embed=success_embed("Ticket Criado", f"Seu ticket foi aberto em {canal.mention}."),
            ephemeral=True
        )


class ControlesTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Fechar Ticket", style=discord.ButtonStyle.red,
                       emoji="🔒", custom_id="fechar_ticket_btn")
    async def fechar(self, inter: discord.Interaction, button: discord.ui.Button):
        ticket = db.get_ticket_por_canal(inter.channel.id)
        if not ticket:
            return await inter.response.send_message(
                embed=error_embed("Erro", "Este não é um canal de ticket válido."), ephemeral=True
            )

        config = db.get_tickets_config()
        # Verificar permissão: dono do ticket ou atendente
        is_dono = str(inter.user.id) == str(ticket["user_id"])
        is_atendente = False
        if config.get("cargo_atendente_id"):
            cargo = inter.guild.get_role(int(config["cargo_atendente_id"]))
            if cargo and cargo in inter.user.roles:
                is_atendente = True
        is_admin = inter.user.guild_permissions.administrator

        if not (is_dono or is_atendente or is_admin):
            return await inter.response.send_message(
                embed=error_embed("Sem permissão", "Apenas o dono do ticket ou atendentes podem fechar."),
                ephemeral=True
            )

        await inter.response.send_message(
            embed=discord.Embed(
                description=f"{e.clock} Fechando ticket em **5 segundos**...",
                color=0xe74c3c
            )
        )

        import asyncio
        await asyncio.sleep(5)

        fechado_em = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        db.fechar_ticket(inter.channel.id, fechado_em)

        # Log
        canais_conf = db.get_canais_config()
        if canais_conf.get("log_ticket_id"):
            log_canal = inter.guild.get_channel(int(canais_conf["log_ticket_id"]))
            if log_canal:
                dono = inter.guild.get_member(int(ticket["user_id"]))
                em_log = discord.Embed(
                    title=f"{e.ticket} Ticket Fechado",
                    color=0xe74c3c
                )
                em_log.add_field(name="Canal", value=inter.channel.name)
                em_log.add_field(name="Dono", value=dono.mention if dono else ticket["user_id"])
                em_log.add_field(name="Fechado por", value=inter.user.mention)
                em_log.add_field(name="Data", value=fechado_em)
                await log_canal.send(embed=em_log)

        await inter.channel.delete(reason=f"Ticket fechado por {inter.user}")


class Tickets(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        bot.add_view(AbrirTicketView())
        bot.add_view(ControlesTicketView())

    ticket_group = app_commands.Group(name="ticket", description="Gerenciamento de tickets")

    @ticket_group.command(name="painel", description="Envia o painel de abertura de tickets no canal.")
    @app_commands.default_permissions(administrator=True)
    async def painel(self, inter: discord.Interaction):
        em = discord.Embed(
            title=f"{e.ticket} Suporte",
            description="Clique no botão abaixo para abrir um ticket e receber atendimento.",
            color=0x5865F2
        )
        em.set_footer(text=inter.guild.name)
        await inter.channel.send(embed=em, view=AbrirTicketView())
        await inter.response.send_message(
            embed=success_embed("Painel Enviado", "Painel de tickets enviado com sucesso."),
            ephemeral=True
        )

    @ticket_group.command(name="configurar", description="Configura o sistema de tickets.")
    @app_commands.describe(
        categoria="Categoria onde os tickets serão criados",
        cargo_atendente="Cargo com acesso aos tickets",
        canal_log="Canal de logs dos tickets",
        mensagem="Mensagem de boas-vindas ({user} = menção)",
        max_por_usuario="Máximo de tickets abertos por usuário"
    )
    @app_commands.default_permissions(administrator=True)
    async def configurar(
        self,
        inter: discord.Interaction,
        categoria: discord.CategoryChannel,
        cargo_atendente: discord.Role = None,
        canal_log: discord.TextChannel = None,
        mensagem: str = None,
        max_por_usuario: int = 1
    ):
        db.salvar_tickets_config(
            categoria_id=categoria.id,
            cargo_atendente_id=cargo_atendente.id if cargo_atendente else None,
            canal_log_id=canal_log.id if canal_log else None,
            mensagem=mensagem,
            max_por_usuario=max_por_usuario
        )
        em = success_embed("Tickets Configurado", "Sistema de tickets atualizado com sucesso!")
        em.add_field(name="Categoria", value=categoria.mention, inline=True)
        em.add_field(name="Cargo Atendente", value=cargo_atendente.mention if cargo_atendente else "Não definido", inline=True)
        em.add_field(name="Log", value=canal_log.mention if canal_log else "Não definido", inline=True)
        em.add_field(name="Max por usuário", value=str(max_por_usuario), inline=True)
        await inter.response.send_message(embed=em, ephemeral=True)

    @ticket_group.command(name="fechar", description="Fecha o ticket atual.")
    @app_commands.describe(motivo="Motivo do fechamento")
    async def fechar(self, inter: discord.Interaction, motivo: str = "Sem motivo"):
        ticket = db.get_ticket_por_canal(inter.channel.id)
        if not ticket:
            return await inter.response.send_message(
                embed=error_embed("Erro", "Use este comando dentro de um canal de ticket."),
                ephemeral=True
            )

        fechado_em = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        db.fechar_ticket(inter.channel.id, fechado_em)

        await inter.response.send_message(
            embed=discord.Embed(
                description=f"{e.lock} Ticket fechado por {inter.user.mention}.\n**Motivo:** {motivo}",
                color=0xe74c3c
            )
        )

        import asyncio
        await asyncio.sleep(3)
        await inter.channel.delete(reason=f"Fechado por {inter.user}: {motivo}")

    @ticket_group.command(name="adicionar", description="Adiciona um membro ao ticket.")
    @app_commands.describe(membro="Membro a adicionar")
    async def adicionar(self, inter: discord.Interaction, membro: discord.Member):
        ticket = db.get_ticket_por_canal(inter.channel.id)
        if not ticket:
            return await inter.response.send_message(
                embed=error_embed("Erro", "Use dentro de um ticket."), ephemeral=True
            )
        await inter.channel.set_permissions(membro, read_messages=True, send_messages=True)
        await inter.response.send_message(
            embed=success_embed("Membro Adicionado", f"{membro.mention} foi adicionado ao ticket.")
        )

    @ticket_group.command(name="remover", description="Remove um membro do ticket.")
    @app_commands.describe(membro="Membro a remover")
    async def remover(self, inter: discord.Interaction, membro: discord.Member):
        ticket = db.get_ticket_por_canal(inter.channel.id)
        if not ticket:
            return await inter.response.send_message(
                embed=error_embed("Erro", "Use dentro de um ticket."), ephemeral=True
            )
        if str(membro.id) == str(ticket["user_id"]):
            return await inter.response.send_message(
                embed=error_embed("Erro", "Não é possível remover o dono do ticket."), ephemeral=True
            )
        await inter.channel.set_permissions(membro, overwrite=None)
        await inter.response.send_message(
            embed=success_embed("Membro Removido", f"{membro.mention} foi removido do ticket.")
        )

    @ticket_group.command(name="renomear", description="Renomeia o canal do ticket.")
    @app_commands.describe(nome="Novo nome")
    async def renomear(self, inter: discord.Interaction, nome: str):
        ticket = db.get_ticket_por_canal(inter.channel.id)
        if not ticket:
            return await inter.response.send_message(
                embed=error_embed("Erro", "Use dentro de um ticket."), ephemeral=True
            )
        await inter.channel.edit(name=nome)
        await inter.response.send_message(
            embed=success_embed("Ticket Renomeado", f"Canal renomeado para **{nome}**."),
            ephemeral=True
        )

    @ticket_group.command(name="info", description="Exibe informações do ticket atual.")
    async def info(self, inter: discord.Interaction):
        ticket = db.get_ticket_por_canal(inter.channel.id)
        if not ticket:
            return await inter.response.send_message(
                embed=error_embed("Erro", "Use dentro de um ticket."), ephemeral=True
            )
        dono = inter.guild.get_member(int(ticket["user_id"]))
        em = info_embed("Informações do Ticket")
        em.add_field(name="ID", value=ticket["id"], inline=True)
        em.add_field(name="Status", value=ticket["status"].capitalize(), inline=True)
        em.add_field(name="Dono", value=dono.mention if dono else ticket["user_id"], inline=True)
        em.add_field(name="Assunto", value=ticket["assunto"] or "Não informado", inline=True)
        em.add_field(name="Aberto em", value=ticket["criado_em"], inline=True)
        await inter.response.send_message(embed=em, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Tickets(bot))
