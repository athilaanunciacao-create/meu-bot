import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timezone
from utils.emojis import e
from utils.helpers import success_embed, error_embed, info_embed, load_config
from database import db


class ConfirmarCompraView(discord.ui.View):
    def __init__(self, produto: dict, usuario: discord.Member):
        super().__init__(timeout=300)
        self.produto = produto
        self.usuario = usuario

    @discord.ui.button(label="Pagar com PIX", style=discord.ButtonStyle.green, emoji="💰")
    async def pagar_pix(self, inter: discord.Interaction, button: discord.ui.Button):
        if inter.user.id != self.usuario.id:
            return await inter.response.send_message("Este painel não é seu.", ephemeral=True)

        config = load_config()
        pix = config.get("pix", {})

        if not pix.get("enabled") or not pix.get("chave"):
            return await inter.response.send_message(
                embed=error_embed("PIX não configurado", "Entre em contato com o suporte."),
                ephemeral=True
            )

        pedido_id = db.criar_pedido(
            inter.user.id,
            self.produto["id"],
            self.produto["nome"],
            self.produto["preco"]
        )

        em = discord.Embed(
            title=f"{e.pix} Pagamento PIX",
            description=f"Realize o pagamento para receber seu produto.",
            color=0x00b894
        )
        em.add_field(name=f"{e.cart} Produto", value=self.produto["nome"], inline=True)
        em.add_field(name=f"{e.dollar} Valor", value=f"R$ {self.produto['preco']:.2f}", inline=True)
        em.add_field(name=f"{e.receipt} Pedido", value=f"#{pedido_id}", inline=True)
        em.add_field(
            name=f"{e.pix} Chave PIX ({pix.get('tipo', 'chave_aleatoria')})",
            value=f"```{pix['chave']}```",
            inline=False
        )
        em.add_field(
            name=f"{e.information} Como pagar",
            value=(
                "**1.** Abra seu banco/app de pagamento\n"
                "**2.** Copie a chave PIX acima\n"
                "**3.** Realize o pagamento do valor exato\n"
                "**4.** Clique em **'Já Paguei'** abaixo\n"
                f"**5.** Envie o comprovante neste canal"
            ),
            inline=False
        )
        em.set_footer(text=f"Pedido #{pedido_id} • {inter.user}")

        await inter.response.edit_message(embed=em, view=ComprovanteView(pedido_id, self.produto, inter.user))

    @discord.ui.button(label="Cancelar", style=discord.ButtonStyle.red, emoji="✖️")
    async def cancelar(self, inter: discord.Interaction, button: discord.ui.Button):
        if inter.user.id != self.usuario.id:
            return await inter.response.send_message("Este painel não é seu.", ephemeral=True)
        await inter.response.edit_message(
            embed=error_embed("Compra Cancelada", "Você cancelou a compra."),
            view=None
        )


class ComprovanteView(discord.ui.View):
    def __init__(self, pedido_id: int, produto: dict, usuario: discord.Member):
        super().__init__(timeout=600)
        self.pedido_id = pedido_id
        self.produto = produto
        self.usuario = usuario

    @discord.ui.button(label="Já Paguei", style=discord.ButtonStyle.green, emoji="✅")
    async def ja_paguei(self, inter: discord.Interaction, button: discord.ui.Button):
        if inter.user.id != self.usuario.id:
            return await inter.response.send_message("Este painel não é seu.", ephemeral=True)

        em = discord.Embed(
            title=f"{e.clock} Aguardando Confirmação",
            description=(
                f"Seu pagamento do pedido **#{self.pedido_id}** está sendo analisado.\n\n"
                f"**Envie o comprovante neste canal.** Um administrador irá confirmar e entregar seu produto."
            ),
            color=0xf39c12
        )
        em.set_footer(text=f"Pedido #{self.pedido_id}")
        await inter.response.edit_message(embed=em, view=None)

        # Notificar admins
        admins = db.get_admins()
        canais_conf = db.get_canais_config()
        canal_log_id = canais_conf.get("log_pedidos_id")
        if canal_log_id:
            canal_log = inter.guild.get_channel(int(canal_log_id))
            if canal_log:
                em_log = discord.Embed(
                    title=f"{e.receipt} Novo Pagamento Pendente",
                    color=0xf39c12
                )
                em_log.add_field(name="Pedido", value=f"#{self.pedido_id}", inline=True)
                em_log.add_field(name="Usuário", value=inter.user.mention, inline=True)
                em_log.add_field(name="Produto", value=self.produto["nome"], inline=True)
                em_log.add_field(name="Valor", value=f"R$ {self.produto['preco']:.2f}", inline=True)
                await canal_log.send(embed=em_log)


class Loja(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    loja_group = app_commands.Group(name="loja", description="Sistema de loja")
    produto_group = app_commands.Group(name="produto", description="Gerenciamento de produtos", parent=loja_group)

    @loja_group.command(name="ver", description="Exibe os produtos disponíveis na loja.")
    async def ver(self, inter: discord.Interaction):
        produtos = db.get_produtos()
        if not produtos:
            return await inter.response.send_message(
                embed=info_embed("Loja Vazia", "Nenhum produto disponível no momento."),
                ephemeral=True
            )

        em = discord.Embed(
            title=f"{e.store} Loja",
            description="Selecione um produto abaixo para comprar.",
            color=0x5865F2
        )
        for p in produtos[:25]:
            estoque_txt = f"Estoque: {p['estoque']}" if p["estoque"] > 0 else "⚠️ Sem estoque"
            em.add_field(
                name=f"{e.cart} {p['nome']} — R$ {p['preco']:.2f}",
                value=f"{p['descricao'] or 'Sem descrição'}\n`{estoque_txt}`",
                inline=False
            )

        view = SelecionarProdutoView(produtos, inter.user)
        await inter.response.send_message(embed=em, view=view, ephemeral=True)

    @produto_group.command(name="criar", description="Cria um novo produto na loja.")
    @app_commands.describe(
        nome="Nome do produto",
        preco="Preço em reais",
        estoque="Quantidade em estoque",
        descricao="Descrição do produto",
        conteudo="Conteúdo entregue após compra"
    )
    @app_commands.default_permissions(administrator=True)
    async def criar(self, inter: discord.Interaction, nome: str, preco: float,
                    estoque: int = 0, descricao: str = None, conteudo: str = None):
        pid = db.criar_produto(nome, descricao, preco, estoque, conteudo)
        em = success_embed("Produto Criado", f"Produto **{nome}** criado com sucesso!")
        em.add_field(name="ID", value=str(pid), inline=True)
        em.add_field(name="Preço", value=f"R$ {preco:.2f}", inline=True)
        em.add_field(name="Estoque", value=str(estoque), inline=True)
        await inter.response.send_message(embed=em, ephemeral=True)

    @produto_group.command(name="listar", description="Lista todos os produtos cadastrados.")
    @app_commands.default_permissions(administrator=True)
    async def listar(self, inter: discord.Interaction):
        produtos = db.get_produtos(apenas_ativos=False)
        if not produtos:
            return await inter.response.send_message(
                embed=info_embed("Sem produtos", "Nenhum produto cadastrado."), ephemeral=True
            )
        em = discord.Embed(title=f"{e.folder} Produtos Cadastrados", color=0x5865F2)
        for p in produtos[:25]:
            status = f"{e.on}" if p["ativo"] else f"{e.off}"
            em.add_field(
                name=f"{status} [{p['id']}] {p['nome']}",
                value=f"R$ {p['preco']:.2f} | Estoque: {p['estoque']}",
                inline=False
            )
        await inter.response.send_message(embed=em, ephemeral=True)

    @produto_group.command(name="deletar", description="Desativa um produto da loja.")
    @app_commands.describe(produto_id="ID do produto")
    @app_commands.default_permissions(administrator=True)
    async def deletar(self, inter: discord.Interaction, produto_id: int):
        p = db.get_produto(produto_id)
        if not p:
            return await inter.response.send_message(
                embed=error_embed("Erro", "Produto não encontrado."), ephemeral=True
            )
        db.deletar_produto(produto_id)
        await inter.response.send_message(
            embed=success_embed("Produto Removido", f"Produto **{p['nome']}** desativado."),
            ephemeral=True
        )

    @produto_group.command(name="estoque", description="Atualiza o estoque de um produto.")
    @app_commands.describe(produto_id="ID do produto", quantidade="Nova quantidade")
    @app_commands.default_permissions(administrator=True)
    async def estoque(self, inter: discord.Interaction, produto_id: int, quantidade: int):
        p = db.get_produto(produto_id)
        if not p:
            return await inter.response.send_message(
                embed=error_embed("Erro", "Produto não encontrado."), ephemeral=True
            )
        db.atualizar_estoque(produto_id, quantidade)
        await inter.response.send_message(
            embed=success_embed("Estoque Atualizado", f"**{p['nome']}** agora tem **{quantidade}** unidades."),
            ephemeral=True
        )

    @loja_group.command(name="entregar", description="Entrega um pedido manualmente.")
    @app_commands.describe(pedido_id="ID do pedido")
    @app_commands.default_permissions(administrator=True)
    async def entregar(self, inter: discord.Interaction, pedido_id: int):
        pedido = db.get_pedido(pedido_id)
        if not pedido:
            return await inter.response.send_message(
                embed=error_embed("Erro", "Pedido não encontrado."), ephemeral=True
            )

        produto = db.get_produto(pedido["produto_id"]) if pedido.get("produto_id") else None
        conteudo = produto["conteudo"] if produto and produto.get("conteudo") else "Sem conteúdo registrado."

        usuario = inter.guild.get_member(int(pedido["user_id"]))
        if not usuario:
            return await inter.response.send_message(
                embed=error_embed("Erro", "Usuário não encontrado no servidor."), ephemeral=True
            )

        try:
            em_dm = discord.Embed(
                title=f"{e.gift} Produto Entregue!",
                description=f"Seu pedido **#{pedido_id}** foi confirmado e entregue.",
                color=0x00b894
            )
            em_dm.add_field(name=f"{e.cart} Produto", value=pedido["produto_nome"], inline=True)
            em_dm.add_field(name=f"{e.dollar} Valor", value=f"R$ {pedido['valor']:.2f}", inline=True)
            em_dm.add_field(name=f"{e.receipt} Conteúdo", value=f"```{conteudo}```", inline=False)
            await usuario.send(embed=em_dm)
        except discord.Forbidden:
            pass

        pago_em = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        db.atualizar_pedido_status(pedido_id, "entregue", pago_em)

        if produto and produto.get("estoque", 0) > 0:
            db.atualizar_estoque(produto["id"], produto["estoque"] - 1)

        await inter.response.send_message(
            embed=success_embed("Pedido Entregue", f"Pedido **#{pedido_id}** entregue para {usuario.mention}."),
            ephemeral=True
        )

    @loja_group.command(name="pedidos", description="Lista seus pedidos.")
    async def pedidos(self, inter: discord.Interaction):
        pedidos = db.get_pedidos_usuario(str(inter.user.id))
        if not pedidos:
            return await inter.response.send_message(
                embed=info_embed("Sem pedidos", "Você não tem pedidos registrados."), ephemeral=True
            )
        em = discord.Embed(title=f"{e.receipt} Seus Pedidos", color=0x5865F2)
        for p in pedidos[:10]:
            status_emoji = e.correct if p["status"] == "entregue" else e.clock
            em.add_field(
                name=f"{status_emoji} Pedido #{p['id']} — {p['produto_nome']}",
                value=f"Valor: R$ {p['valor']:.2f} | Status: {p['status'].capitalize()} | {p['criado_em'][:10]}",
                inline=False
            )
        await inter.response.send_message(embed=em, ephemeral=True)


class SelecionarProdutoView(discord.ui.View):
    def __init__(self, produtos: list, usuario: discord.Member):
        super().__init__(timeout=120)
        self.usuario = usuario
        options = [
            discord.SelectOption(
                label=f"{p['nome']} — R$ {p['preco']:.2f}",
                value=str(p["id"]),
                description=p["descricao"][:100] if p["descricao"] else "Sem descrição",
                emoji="🛒"
            )
            for p in produtos[:25]
        ]
        select = discord.ui.Select(placeholder="Selecione um produto...", options=options)
        select.callback = self.select_callback
        self.add_item(select)

    async def select_callback(self, inter: discord.Interaction):
        if inter.user.id != self.usuario.id:
            return await inter.response.send_message("Este painel não é seu.", ephemeral=True)

        produto_id = int(inter.data["values"][0])
        produto = db.get_produto(produto_id)

        if not produto:
            return await inter.response.send_message(
                embed=error_embed("Erro", "Produto não encontrado."), ephemeral=True
            )
        if produto["estoque"] <= 0:
            return await inter.response.send_message(
                embed=error_embed("Sem Estoque", "Este produto está sem estoque no momento."), ephemeral=True
            )

        em = discord.Embed(
            title=f"{e.cart} Confirmar Compra",
            description=f"Você está prestes a comprar **{produto['nome']}**.",
            color=0x5865F2
        )
        em.add_field(name=f"{e.dollar} Preço", value=f"R$ {produto['preco']:.2f}", inline=True)
        em.add_field(name=f"{e.cardbox} Estoque", value=str(produto["estoque"]), inline=True)
        if produto.get("descricao"):
            em.add_field(name=f"{e.information} Descrição", value=produto["descricao"], inline=False)

        await inter.response.edit_message(embed=em, view=ConfirmarCompraView(produto, inter.user))


async def setup(bot):
    await bot.add_cog(Loja(bot))
