import sqlite3
import json
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "bot.db")

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    c = conn.cursor()

    # Configurações gerais
    c.execute("""
        CREATE TABLE IF NOT EXISTS config (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)

    # Produtos da loja
    c.execute("""
        CREATE TABLE IF NOT EXISTS produtos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            descricao TEXT,
            preco REAL NOT NULL,
            estoque INTEGER DEFAULT 0,
            conteudo TEXT,
            imagem_url TEXT,
            ativo INTEGER DEFAULT 1,
            criado_em TEXT DEFAULT (datetime('now'))
        )
    """)

    # Pedidos / pagamentos
    c.execute("""
        CREATE TABLE IF NOT EXISTS pedidos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            produto_id INTEGER,
            produto_nome TEXT,
            valor REAL NOT NULL,
            status TEXT DEFAULT 'pendente',
            payment_id TEXT,
            criado_em TEXT DEFAULT (datetime('now')),
            pago_em TEXT
        )
    """)

    # Tickets
    c.execute("""
        CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_id TEXT UNIQUE NOT NULL,
            user_id TEXT NOT NULL,
            assunto TEXT,
            status TEXT DEFAULT 'aberto',
            atendente_id TEXT,
            criado_em TEXT DEFAULT (datetime('now')),
            fechado_em TEXT
        )
    """)

    # Config de tickets
    c.execute("""
        CREATE TABLE IF NOT EXISTS tickets_config (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            categoria_id TEXT,
            cargo_atendente_id TEXT,
            canal_log_id TEXT,
            mensagem_boas_vindas TEXT DEFAULT 'Olá {user}, aguarde um atendente!',
            max_por_usuario INTEGER DEFAULT 1
        )
    """)

    # Giveaways
    c.execute("""
        CREATE TABLE IF NOT EXISTS giveaways (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id TEXT UNIQUE,
            channel_id TEXT NOT NULL,
            premio TEXT NOT NULL,
            ganhadores INTEGER DEFAULT 1,
            requisito_cargo_id TEXT,
            status TEXT DEFAULT 'ativo',
            criado_por TEXT NOT NULL,
            termina_em TEXT NOT NULL,
            participantes TEXT DEFAULT '[]',
            ganhadores_ids TEXT DEFAULT '[]',
            criado_em TEXT DEFAULT (datetime('now'))
        )
    """)

    # Permissões do bot (admins)
    c.execute("""
        CREATE TABLE IF NOT EXISTS bot_admins (
            user_id TEXT PRIMARY KEY,
            adicionado_em TEXT DEFAULT (datetime('now'))
        )
    """)

    # Logs de moderação
    c.execute("""
        CREATE TABLE IF NOT EXISTS mod_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo TEXT NOT NULL,
            user_id TEXT NOT NULL,
            moderador_id TEXT NOT NULL,
            motivo TEXT,
            guild_id TEXT,
            criado_em TEXT DEFAULT (datetime('now'))
        )
    """)

    # Canal de logs
    c.execute("""
        CREATE TABLE IF NOT EXISTS canais_config (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            log_mod_id TEXT,
            log_ticket_id TEXT,
            log_pedidos_id TEXT,
            boas_vindas_id TEXT,
            loja_id TEXT
        )
    """)

    conn.commit()
    conn.close()
    print("[DB] Banco de dados inicializado com sucesso.")


# ─── Helpers genéricos ────────────────────────────────────────────────────────

def get_config(key: str, default=None):
    conn = get_conn()
    row = conn.execute("SELECT value FROM config WHERE key = ?", (key,)).fetchone()
    conn.close()
    if row:
        try:
            return json.loads(row["value"])
        except Exception:
            return row["value"]
    return default

def set_config(key: str, value):
    conn = get_conn()
    conn.execute(
        "INSERT INTO config (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, json.dumps(value))
    )
    conn.commit()
    conn.close()


# ─── Produtos ────────────────────────────────────────────────────────────────

def get_produtos(apenas_ativos=True):
    conn = get_conn()
    if apenas_ativos:
        rows = conn.execute("SELECT * FROM produtos WHERE ativo = 1").fetchall()
    else:
        rows = conn.execute("SELECT * FROM produtos").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_produto(produto_id: int):
    conn = get_conn()
    row = conn.execute("SELECT * FROM produtos WHERE id = ?", (produto_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def criar_produto(nome, descricao, preco, estoque, conteudo, imagem_url=None):
    conn = get_conn()
    c = conn.execute(
        "INSERT INTO produtos (nome, descricao, preco, estoque, conteudo, imagem_url) VALUES (?, ?, ?, ?, ?, ?)",
        (nome, descricao, preco, estoque, conteudo, imagem_url)
    )
    conn.commit()
    produto_id = c.lastrowid
    conn.close()
    return produto_id

def atualizar_estoque(produto_id: int, quantidade: int):
    conn = get_conn()
    conn.execute("UPDATE produtos SET estoque = ? WHERE id = ?", (quantidade, produto_id))
    conn.commit()
    conn.close()

def deletar_produto(produto_id: int):
    conn = get_conn()
    conn.execute("UPDATE produtos SET ativo = 0 WHERE id = ?", (produto_id,))
    conn.commit()
    conn.close()


# ─── Pedidos ─────────────────────────────────────────────────────────────────

def criar_pedido(user_id, produto_id, produto_nome, valor):
    conn = get_conn()
    c = conn.execute(
        "INSERT INTO pedidos (user_id, produto_id, produto_nome, valor) VALUES (?, ?, ?, ?)",
        (str(user_id), produto_id, produto_nome, valor)
    )
    conn.commit()
    pedido_id = c.lastrowid
    conn.close()
    return pedido_id

def get_pedido(pedido_id: int):
    conn = get_conn()
    row = conn.execute("SELECT * FROM pedidos WHERE id = ?", (pedido_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def atualizar_pedido_status(pedido_id: int, status: str, pago_em: str = None):
    conn = get_conn()
    if pago_em:
        conn.execute(
            "UPDATE pedidos SET status = ?, pago_em = ? WHERE id = ?",
            (status, pago_em, pedido_id)
        )
    else:
        conn.execute("UPDATE pedidos SET status = ? WHERE id = ?", (status, pedido_id))
    conn.commit()
    conn.close()

def get_pedidos_usuario(user_id: str):
    conn = get_conn()
    rows = conn.execute("SELECT * FROM pedidos WHERE user_id = ? ORDER BY criado_em DESC", (user_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ─── Tickets ──────────────────────────────────────────────────────────────────

def criar_ticket(channel_id, user_id, assunto=None):
    conn = get_conn()
    conn.execute(
        "INSERT OR IGNORE INTO tickets (channel_id, user_id, assunto) VALUES (?, ?, ?)",
        (str(channel_id), str(user_id), assunto)
    )
    conn.commit()
    conn.close()

def get_ticket_por_canal(channel_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM tickets WHERE channel_id = ?", (str(channel_id),)).fetchone()
    conn.close()
    return dict(row) if row else None

def get_tickets_abertos_usuario(user_id):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM tickets WHERE user_id = ? AND status = 'aberto'", (str(user_id),)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def fechar_ticket(channel_id, fechado_em):
    conn = get_conn()
    conn.execute(
        "UPDATE tickets SET status = 'fechado', fechado_em = ? WHERE channel_id = ?",
        (fechado_em, str(channel_id))
    )
    conn.commit()
    conn.close()

def get_tickets_config():
    conn = get_conn()
    row = conn.execute("SELECT * FROM tickets_config WHERE id = 1").fetchone()
    conn.close()
    return dict(row) if row else {}

def salvar_tickets_config(categoria_id=None, cargo_atendente_id=None, canal_log_id=None,
                           mensagem=None, max_por_usuario=None):
    conn = get_conn()
    existing = conn.execute("SELECT id FROM tickets_config WHERE id = 1").fetchone()
    if existing:
        fields = []
        vals = []
        if categoria_id is not None:
            fields.append("categoria_id = ?"); vals.append(str(categoria_id))
        if cargo_atendente_id is not None:
            fields.append("cargo_atendente_id = ?"); vals.append(str(cargo_atendente_id))
        if canal_log_id is not None:
            fields.append("canal_log_id = ?"); vals.append(str(canal_log_id))
        if mensagem is not None:
            fields.append("mensagem_boas_vindas = ?"); vals.append(mensagem)
        if max_por_usuario is not None:
            fields.append("max_por_usuario = ?"); vals.append(max_por_usuario)
        if fields:
            vals.append(1)
            conn.execute(f"UPDATE tickets_config SET {', '.join(fields)} WHERE id = ?", vals)
    else:
        conn.execute(
            "INSERT INTO tickets_config (id, categoria_id, cargo_atendente_id, canal_log_id, mensagem_boas_vindas, max_por_usuario) VALUES (1, ?, ?, ?, ?, ?)",
            (str(categoria_id) if categoria_id else None,
             str(cargo_atendente_id) if cargo_atendente_id else None,
             str(canal_log_id) if canal_log_id else None,
             mensagem or 'Olá {user}, aguarde um atendente!',
             max_por_usuario or 1)
        )
    conn.commit()
    conn.close()


# ─── Giveaways ───────────────────────────────────────────────────────────────

def criar_giveaway(channel_id, premio, ganhadores, criado_por, termina_em, requisito_cargo_id=None):
    conn = get_conn()
    c = conn.execute(
        "INSERT INTO giveaways (channel_id, premio, ganhadores, criado_por, termina_em, requisito_cargo_id) VALUES (?, ?, ?, ?, ?, ?)",
        (str(channel_id), premio, ganhadores, str(criado_por), termina_em, str(requisito_cargo_id) if requisito_cargo_id else None)
    )
    conn.commit()
    gid = c.lastrowid
    conn.close()
    return gid

def get_giveaway(giveaway_id: int):
    conn = get_conn()
    row = conn.execute("SELECT * FROM giveaways WHERE id = ?", (giveaway_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def get_giveaway_por_message(message_id: str):
    conn = get_conn()
    row = conn.execute("SELECT * FROM giveaways WHERE message_id = ?", (str(message_id),)).fetchone()
    conn.close()
    return dict(row) if row else None

def get_giveaways_ativos():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM giveaways WHERE status = 'ativo'").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def atualizar_giveaway_message(giveaway_id: int, message_id: str):
    conn = get_conn()
    conn.execute("UPDATE giveaways SET message_id = ? WHERE id = ?", (str(message_id), giveaway_id))
    conn.commit()
    conn.close()

def atualizar_participantes(giveaway_id: int, participantes: list):
    conn = get_conn()
    conn.execute("UPDATE giveaways SET participantes = ? WHERE id = ?", (json.dumps(participantes), giveaway_id))
    conn.commit()
    conn.close()

def finalizar_giveaway(giveaway_id: int, ganhadores_ids: list):
    conn = get_conn()
    conn.execute(
        "UPDATE giveaways SET status = 'finalizado', ganhadores_ids = ? WHERE id = ?",
        (json.dumps(ganhadores_ids), giveaway_id)
    )
    conn.commit()
    conn.close()


# ─── Admins do Bot ────────────────────────────────────────────────────────────

def is_admin(user_id: str) -> bool:
    conn = get_conn()
    row = conn.execute("SELECT 1 FROM bot_admins WHERE user_id = ?", (str(user_id),)).fetchone()
    conn.close()
    return row is not None

def add_admin(user_id: str):
    conn = get_conn()
    conn.execute("INSERT OR IGNORE INTO bot_admins (user_id) VALUES (?)", (str(user_id),))
    conn.commit()
    conn.close()

def remove_admin(user_id: str):
    conn = get_conn()
    conn.execute("DELETE FROM bot_admins WHERE user_id = ?", (str(user_id),))
    conn.commit()
    conn.close()

def get_admins():
    conn = get_conn()
    rows = conn.execute("SELECT user_id FROM bot_admins").fetchall()
    conn.close()
    return [r["user_id"] for r in rows]


# ─── Canais Config ────────────────────────────────────────────────────────────

def get_canais_config():
    conn = get_conn()
    row = conn.execute("SELECT * FROM canais_config WHERE id = 1").fetchone()
    conn.close()
    return dict(row) if row else {}

def salvar_canal_config(**kwargs):
    conn = get_conn()
    existing = conn.execute("SELECT id FROM canais_config WHERE id = 1").fetchone()
    if existing:
        fields = []
        vals = []
        for k, v in kwargs.items():
            fields.append(f"{k} = ?")
            vals.append(str(v) if v else None)
        if fields:
            vals.append(1)
            conn.execute(f"UPDATE canais_config SET {', '.join(fields)} WHERE id = ?", vals)
    else:
        conn.execute(
            "INSERT INTO canais_config (id) VALUES (1)"
        )
        fields = []
        vals = []
        for k, v in kwargs.items():
            fields.append(f"{k} = ?")
            vals.append(str(v) if v else None)
        if fields:
            vals.append(1)
            conn.execute(f"UPDATE canais_config SET {', '.join(fields)} WHERE id = ?", vals)
    conn.commit()
    conn.close()
