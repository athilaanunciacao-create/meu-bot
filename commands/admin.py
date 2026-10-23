import discord
from discord.ext import commands
from discord import app_commands
from utils.emojis import e
from utils.helpers import success_embed, error_embed, info_embed, load_config
from database import db


class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    admin_group = app_commands.Group(name="admin", description="Comandos administrativos do bot")

    @admin_group.command(name="addadmin", description="Adiciona um admin do bot.")
    @app_commands.describe(membro="Membro a adicionar como admin")
    async def addadmin(self, inter: discord.Interaction, membro: discord.Member):
        config = load_config()
        if str(inter.user.id) != str(config.get("owner_id", "")) and not inter.user.guild_permissions.administrator:
            return await inter.response.send_message(embed=error_embed("Sem permissão", "Apenas o dono pode usar isso."), ephemeral=True)
        db.add_admin(str(membro.id))
        await inter.response.send_message(embed=success_embed("Admin Adicionado", f"{membro.mention} agora é admin do bot."), ephemeral=True)

    @admin_group.command(name="removeadmin", description="Remove um admin do bot.")
    @app_commands.describe(membro="Membro a remover")
    async def removeadmin(self, inter: discord.Interaction, membro: discord.Member):
        config = load_config()
        if str(inter.user.id) != str(config.get("owner_id", "")) and not inter.user.guild_permissions.administrator:
            return await inter.response.send_message(embed=error_embed("Sem permissão", "Apenas o dono pode usar isso."), ephemeral=True)
        db.remove_admin(str(membro.id))
        await inter.response.send_message(embed=success_embed("Admin Removido", f"{membro.mention} foi removido dos admins."), ephemeral=True)

    @admin_group.command(name="listadmins", description="Lista os admins do bot.")
    async def listadmins(self, inter: discord.Interaction):
        admins = db.get_admins()
        if not admins:
            return await inter.response.send_message(embed=info_embed("Admins", "Nenhum admin configurado."), ephemeral=True)
        mencoes = "\n".join(f"<@{uid}>" for uid in admins)
        await inter.response.send_message(embed=info_embed("Admins do Bot", mencoes), ephemeral=True)

    @admin_group.command(name="setcanal", description="Configura canais de log do bot.")
    @app_commands.describe(
        tipo="Tipo do canal",
        canal="Canal a configurar"
    )
    @app_commands.choices(tipo=[
        app_commands.Choice(name="Log Moderação", value="log_mod_id"),
        app_commands.Choice(name="Log Tickets", value="log_ticket_id"),
        app_commands.Choice(name="Log Pedidos", value="log_pedidos_id"),
        app_commands.Choice(name="Boas Vindas", value="boas_vindas_id"),
        app_commands.Choice(name="Loja", value="loja_id"),
    ])
    @app_commands.default_permissions(administrator=True)
    async def setcanal(self, inter: discord.Interaction, tipo: str, canal: discord.TextChannel):
        db.salvar_canal_config(**{tipo: canal.id})
        nomes = {
            "log_mod_id": "Log Moderação",
            "log_ticket_id": "Log Tickets",
            "log_pedidos_id": "Log Pedidos",
            "boas_vindas_id": "Boas Vindas",
            "loja_id": "Loja",
        }
        await inter.response.send_message(
            embed=success_embed("Canal Configurado", f"**{nomes[tipo]}** → {canal.mention}"),
            ephemeral=True
        )

    @app_commands.command(name="painel", description="Abre o painel de controle do bot.")
    @app_commands.default_permissions(administrator=True)
    async def painel(self, inter: discord.Interaction):
        is_admin = db.is_admin(str(inter.user.id))
        if not is_admin and not inter.user.guild_permissions.administrator:
            return await inter.response.send_message(embed=error_embed("Sem permissão", "Você não tem acesso ao painel."), ephemeral=True)

        em = discord.Embed(
            title=f"{e.z0}{e.z1}{e.z2}{e.z3}{e.z4}",
            description=f"Olá **{inter.user.display_name}**! Bem-vindo ao painel de controle.\nUse os botões abaixo para gerenciar o bot.",
            color=0x5865F2
        )
        em.set_thumbnail(url=inter.guild.icon.url if inter.guild.icon else None)

        view = PainelView()
        await inter.response.send_message(embed=em, view=view, ephemeral=True)


class PainelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)

    @discord.ui.button(label="Loja", style=discord.ButtonStyle.grey, emoji="🛒", row=0)
    async def loja(self, inter: discord.Interaction, button: discord.ui.Button):
        produtos = db.get_produtos(apenas_ativos=False)
        em = discord.Embed(title=f"{e.store} Loja", color=0x5865F2)
        if not produtos:
            em.description = "Nenhum produto cadastrado. Use `/loja produto criar`."
        else:
            for p in produtos[:10]:
                status = f"{e.on}" if p["ativo"] else f"{e.off}"
                em.add_field(
                    name=f"{status} [{p['id']}] {p['nome']}",
                    value=f"R$ {p['preco']:.2f} | Estoque: {p['estoque']}",
                    inline=False
                )
        await inter.response.edit_message(embed=em, view=PainelLojaView())

    @discord.ui.button(label="Tickets", style=discord.ButtonStyle.grey, emoji="🎫", row=0)
    async def tickets(self, inter: discord.Interaction, button: discord.ui.Button):
        config = db.get_tickets_config()
        em = discord.Embed(title=f"{e.ticket} Tickets", color=0x5865F2)
        em.add_field(name="Categoria", value=f"<#{config['categoria_id']}>" if config.get("categoria_id") else "Não configurado", inline=True)
        em.add_field(name="Cargo Atendente", value=f"<@&{config['cargo_atendente_id']}>" if config.get("cargo_atendente_id") else "Não definido", inline=True)
        em.add_field(name="Canal Log", value=f"<#{config['canal_log_id']}>" if config.get("canal_log_id") else "Não definido", inline=True)
        em.add_field(name="Max por usuário", value=str(config.get("max_por_usuario", 1)), inline=True)
        em.add_field(name="Mensagem", value=config.get("mensagem_boas_vindas", "Padrão"), inline=False)
        em.description = "Use `/ticket configurar` para editar."
        await inter.response.edit_message(embed=em, view=PainelVoltarView())

    @discord.ui.button(label="Sorteios", style=discord.ButtonStyle.grey, emoji="🎉", row=0)
    async def sorteios(self, inter: discord.Interaction, button: discord.ui.Button):
        giveaways = db.get_giveaways_ativos()
        em = discord.Embed(title=f"{e.giveaway} Sorteios Ativos", color=0x5865F2)
        if not giveaways:
            em.description = "Nenhum sorteio ativo. Use `/giveaway criar`."
        else:
            import json
            for g in giveaways[:10]:
                p = json.loads(g["participantes"])
                em.add_field(
                    name=f"[{g['id']}] {g['premio']}",
                    value=f"Participantes: {len(p)} | Ganhadores: {g['ganhadores']}",
                    inline=False
                )
        await inter.response.edit_message(embed=em, view=PainelVoltarView())

    @discord.ui.button(label="Configurações", style=discord.ButtonStyle.grey, emoji="⚙️", row=1)
    async def configuracoes(self, inter: discord.Interaction, button: discord.ui.Button):
        canais = db.get_canais_config()
        em = discord.Embed(title=f"{e.config} Configurações", color=0x5865F2)
        em.add_field(name="Log Moderação", value=f"<#{canais['log_mod_id']}>" if canais.get("log_mod_id") else "Não definido", inline=True)
        em.add_field(name="Log Tickets", value=f"<#{canais['log_ticket_id']}>" if canais.get("log_ticket_id") else "Não definido", inline=True)
        em.add_field(name="Log Pedidos", value=f"<#{canais['log_pedidos_id']}>" if canais.get("log_pedidos_id") else "Não definido", inline=True)
        em.add_field(name="Boas Vindas", value=f"<#{canais['boas_vindas_id']}>" if canais.get("boas_vindas_id") else "Não definido", inline=True)
        em.description = "Use `/admin setcanal` para configurar os canais."
        await inter.response.edit_message(embed=em, view=PainelVoltarView())


class PainelVoltarView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)

    @discord.ui.button(label="Voltar", style=discord.ButtonStyle.grey, emoji="⬅️")
    async def voltar(self, inter: discord.Interaction, button: discord.ui.Button):
        em = discord.Embed(
            title=f"{e.z0}{e.z1}{e.z2}{e.z3}{e.z4}",
            description=f"Olá **{inter.user.display_name}**! Bem-vindo ao painel de controle.\nUse os botões abaixo para gerenciar o bot.",
            color=0x5865F2
        )
        await inter.response.edit_message(embed=em, view=PainelView())


class PainelLojaView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)

    @discord.ui.button(label="Voltar", style=discord.ButtonStyle.grey, emoji="⬅️")
    async def voltar(self, inter: discord.Interaction, button: discord.ui.Button):
        em = discord.Embed(
            title=f"{e.z0}{e.z1}{e.z2}{e.z3}{e.z4}",
            description=f"Olá **{inter.user.display_name}**! Bem-vindo ao painel de controle.",
            color=0x5865F2
        )
        await inter.response.edit_message(embed=em, view=PainelView())


async def setup(bot):
    await bot.add_cog(Admin(bot))
