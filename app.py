import os
from flask import Flask, render_template, request, jsonify
import oracledb



app = Flask(__name__)

# Configurações de Ambiente
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_DSN = os.getenv('DB_DSN', 'localhost:1521/xe')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/varrer', methods=['POST'])
def varrer_bots():
    dados = request.json
    id_evento = dados.get('id_evento')

    connection = None
    try:
        connection = oracledb.connect(
            user=DB_USER,
            password=DB_PASSWORD,
            dsn=DB_DSN
        )
        cursor = connection.cursor()

        # Criamos uma variável no Python para receber o valor do PL/SQL
        v_total_removido = cursor.var(int)

        plsql_block = """
        DECLARE
            CURSOR c_bots IS
                SELECT i.ID, u.ID as USU_ID, u.EMAIL
                FROM INSCRICOES i
                JOIN USUARIOS u ON i.USUARIO_ID = u.ID
                WHERE i.STATUS = 'PENDING'
                  AND (u.EMAIL LIKE '%fake.com%' 
                       OR u.EMAIL LIKE '%temp-mail%' 
                       OR u.EMAIL NOT LIKE '%@%');
            
            v_ins_id INSCRICOES.ID%TYPE;
            v_usu_id USUARIOS.ID%TYPE;
            v_email  USUARIOS.EMAIL%TYPE;
            v_cont   NUMBER := 0;
        BEGIN
            OPEN c_bots;
            LOOP
                FETCH c_bots INTO v_ins_id, v_usu_id, v_email;
                EXIT WHEN c_bots%NOTFOUND;

                UPDATE USUARIOS SET SALDO = SALDO - 15 WHERE ID = v_usu_id;
                UPDATE INSCRICOES SET STATUS = 'CANCELLED' WHERE ID = v_ins_id;

                INSERT INTO LOG_AUDITORIA (INSCRICAO_ID, MOTIVO, DATA)
                VALUES (v_ins_id, 'BOT NEUTRALIZADO: ' || v_email, SYSDATE);
                
                v_cont := v_cont + 1;
            END LOOP;
            CLOSE c_bots;
            
            COMMIT;
            
            -- ATRIBUIÇÃO: Passa o valor do contador local para a bind variable do Python
            :out_contagem := v_cont;
        END;
        """
        
        # Executamos passando o parâmetro de saída
        cursor.execute(plsql_block, out_contagem=v_total_removido)
        
        # Pegamos o valor final da variável
        total = v_total_removido.getvalue()
        
        return jsonify({
            "status": "success",
            "message": f"Varredura concluída! {total} bot(s) detectado(s) e neutralizado(s) no sistema.",
            "total": total
        })

    except oracledb.DatabaseError as e:
        error, = e.args
        return jsonify({
            "status": "error",
            "message": f"Erro Oracle: {error.message}"
        }), 500
    
    finally:
        if connection:
            connection.close()

if __name__ == '__main__':
    app.run(debug=True)