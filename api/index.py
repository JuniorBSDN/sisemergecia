from flask import Flask, request, jsonify
from flask_cors import CORS
import psycopg2
from psycopg2.extras import RealDictCursor
import os

app = Flask(__name__)
CORS(app)


# Conexão com Vercel Postgres / Local
def get_db():
    return psycopg2.connect(
        host=os.getenv('DB_HOST'),
        port=os.getenv('DB_PORT', '5432'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASS'),
        dbname=os.getenv('DB_NAME'),
        sslmode='require' if os.getenv('DB_HOST') != 'localhost' else 'prefer'
    )


# 1. LOGIN (Ref: index.html)
@app.route('/api/auth_prestador', methods=['POST'])
def auth():
    d = request.json
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    # Busca por CPF e Senha na tabela 'prestadores'
    cur.execute("SELECT cpf, nome, funcao FROM prestadores WHERE cpf = %s AND senha_acesso = %s AND ativo = TRUE",
                (d['cpf'], d['senha']))
    user = cur.fetchone()
    conn.close()
    if user:
        return jsonify({"user": user}), 200
    return jsonify({"error": "Credenciais Inválidas"}), 401


# 2. RECEPÇÃO (Ref: recepcao.html)
@app.route('/api/pacientes', methods=['POST', 'GET'])
def gerenciar_pacientes():
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    if request.method == 'POST':
        d = request.json
        cur.execute("""
            INSERT INTO pacientes (cns, nome, nome_mae, data_nascimento, cpf) 
            VALUES (%s, %s, %s, %s, %s) ON CONFLICT (cns) DO UPDATE SET nome = EXCLUDED.nome
        """, (d['cns'], d['nome'], d['nome_mae'], d['nascimento'], d.get('cpf')))
        conn.commit()
        conn.close()
        return jsonify({"status": "sucesso"}), 201

    # Lista pacientes para busca/sugestão
    cur.execute("SELECT * FROM pacientes ORDER BY nome ASC LIMIT 50")
    pacientes = cur.fetchall()
    conn.close()
    return jsonify(pacientes)


# 3. FILA DE ESPERA (Ref: recepcao.html / triagem.html)
@app.route('/api/pacientes_fila_triagem', methods=['GET'])
def fila_triagem():
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    # Pacientes que ainda não possuem atendimento iniciado hoje (simplificado)
    cur.execute("""
        SELECT p.cns, p.nome, p.nome_mae, p.data_nascimento, p.criado_em 
        FROM pacientes p 
        WHERE p.cns NOT IN (SELECT paciente_cns FROM atendimentos WHERE status_fluxo = 'AGUARDANDO_MEDICO')
        ORDER BY p.criado_em ASC
    """)
    fila = cur.fetchall()
    conn.close()
    return jsonify(fila)


# 4. TRIAGEM (Ref: triagem.html)
@app.route('/api/atendimentos', methods=['POST'])
def salvar_triagem():
    d = request.json
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO atendimentos (
                paciente_cns, pa, glicemia, temperatura, spo2, fc, 
                queixa_principal, classificacao_risco, cor_risco, status_fluxo
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'AGUARDANDO_MEDICO')
        """, (
            d['cns'], d['pa'], d['glicemia'], d['temp'], d['spo2'],
            d['fc'], d['queixa'], d['risco'], d['cor']
        ))
        conn.commit()
        return jsonify({"status": "Triagem salva com sucesso"}), 200
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()


# 5. GESTOR (Ref: gestor.html)
@app.route('/api/prestadores', methods=['POST', 'GET'])
def gerenciar_prestadores():
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    if request.method == 'POST':
        d = request.json
        cur.execute("""
            INSERT INTO prestadores (cpf, nome, funcao, conselho, registro_profissional, senha_acesso)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (d['cpf'], d['nome'], d['funcao'], d['conselho'], d['registro'], d['senha']))
        conn.commit()
        conn.close()
        return jsonify({"status": "Prestador criado"}), 201

    cur.execute("SELECT cpf, nome, funcao, ativo FROM prestadores")
    prestadores = cur.fetchall()
    conn.close()
    return jsonify(prestadores)


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)