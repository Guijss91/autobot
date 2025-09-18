from flask import Flask, request, jsonify
import requests
import os

app = Flask(__name__)

# Armazenamento da conversation_id (em produção, considere usar Redis ou banco de dados)
conversation_id_storage = {"conversation_id": None}

# Constantes
API_BASE_URL = "https://prisma.defensoria.df.gov.br/api/v1/accounts/2/conversations"
API_TOKEN = "Hv59k9tzjdy6ScRfnnaNz3w3"  # Substitua pelo token real

headers = {
    "api_access_token": API_TOKEN,
    "Content-Type": "application/json"
}

@app.route('/')
def home():
    """Interface simples mostrando os endpoints disponíveis"""
    api_url = request.host_url.rstrip('/')
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Integração Typebot x Chatwoot</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; }}
            .endpoint {{ 
                background-color: #f4f4f4; 
                padding: 10px; 
                margin: 10px 0; 
                border-radius: 5px; 
                font-family: monospace;
            }}
            .status {{ margin-top: 20px; padding: 10px; background-color: #e8f5e8; border-radius: 5px; }}
        </style>
    </head>
    <body>
        <h1>API Endpoints - Integração Typebot x Chatwoot</h1>
        
        <h3>Webhook 1 - Receber evento do Chatwoot:</h3>
        <div class="endpoint">{api_url}/webhook1</div>
        <p><strong>Método:</strong> POST<br>
        <strong>Função:</strong> Recebe dados do Chatwoot e adiciona label "bot_atendendo"</p>
        
        <h3>Webhook 2 - Atendimento humano (Typebot):</h3>
        <div class="endpoint">{api_url}/webhook2</div>
        <p><strong>Método:</strong> POST<br>
        <strong>Função:</strong> Atribui conversa para equipe e altera status para atendimento humano</p>
        
        <div class="status">
            <strong>Status:</strong> Aplicação funcionando ✅<br>
            <strong>Conversation ID armazenada:</strong> {conversation_id_storage.get('conversation_id', 'Nenhuma')}
        </div>
    </body>
    </html>
    """
    return html

@app.route('/webhook1', methods=['POST'])
def webhook1():
    """
    Webhook 1: Recebe evento do Chatwoot
    - Extrai conversation_id dos dados recebidos
    - Salva o conversation_id
    - Adiciona label "bot_atendendo" via API do Chatwoot
    """
    try:
        data = request.json
        if not data:
            return jsonify({"error": "Nenhum dado JSON recebido"}), 400
        
        # Extrai conversation_id dos dados (pode vir como conversation_id ou conversations_id)
        conversation_id = data.get('conversation_id') or data.get('conversations_id')
        
        if not conversation_id:
            return jsonify({
                "error": "conversation_id não encontrado nos dados recebidos",
                "received_data": data
            }), 400

        # Salva o conversation_id
        conversation_id_storage["conversation_id"] = str(conversation_id)

        # Chama API do Chatwoot para adicionar label "bot_atendendo"
        url = f"{API_BASE_URL}/{conversation_id}/labels"
        body = {
            "labels": ["bot_atendendo"]
        }
        
        response = requests.post(url, headers=headers, json=body)
        
        return jsonify({
            "message": "Label 'bot_atendendo' adicionada com sucesso",
            "conversation_id": conversation_id,
            "chatwoot_response_status": response.status_code,
            "chatwoot_response": response.json() if response.content else {}
        }), 200

    except requests.exceptions.RequestException as e:
        return jsonify({
            "error": "Erro na requisição para Chatwoot",
            "details": str(e)
        }), 500
    except Exception as e:
        return jsonify({
            "error": "Erro interno do servidor",
            "details": str(e)
        }), 500

@app.route('/webhook2', methods=['POST'])
def webhook2():
    """
    Webhook 2: Atendimento humano (chamado pelo Typebot)
    - Atribui conversa para equipe (team_id: 6)
    - Altera label para "atribuido_para_agente"
    - Muda status para "pending"
    - Muda status para "open"
    """
    try:
        # Recupera o conversation_id armazenado
        conversation_id = conversation_id_storage.get("conversation_id")
        if not conversation_id:
            return jsonify({
                "error": "Nenhum conversation_id armazenado. Execute webhook1 primeiro."
            }), 400

        results = []

        # 1. Atribuir para equipe
        assign_url = f"{API_BASE_URL}/{conversation_id}/assignments"
        assign_body = {"team_id": 6}
        assign_response = requests.post(assign_url, headers=headers, json=assign_body)
        
        results.append({
            "step": "assign_team",
            "status_code": assign_response.status_code,
            "success": assign_response.status_code == 200
        })

        if assign_response.status_code != 200:
            return jsonify({
                "error": "Falha ao atribuir equipe",
                "conversation_id": conversation_id,
                "results": results
            }), 500

        # 2. Alterar label para "atribuido_para_agente"
        label_url = f"{API_BASE_URL}/{conversation_id}/labels"
        label_body = {"labels": ["atribuido_para_agente"]}
        label_response = requests.post(label_url, headers=headers, json=label_body)
        
        results.append({
            "step": "update_label",
            "status_code": label_response.status_code,
            "success": label_response.status_code == 200
        })

        if label_response.status_code != 200:
            return jsonify({
                "error": "Falha ao atualizar label",
                "conversation_id": conversation_id,
                "results": results
            }), 500

        # 3. Alterar status para "pending"
        toggle_status_url = f"{API_BASE_URL}/{conversation_id}/toggle_status"
        pending_body = {"status": "pending"}
        pending_response = requests.post(toggle_status_url, headers=headers, json=pending_body)
        
        results.append({
            "step": "status_pending",
            "status_code": pending_response.status_code,
            "success": pending_response.status_code == 200
        })

        if pending_response.status_code != 200:
            return jsonify({
                "error": "Falha ao alterar status para pending",
                "conversation_id": conversation_id,
                "results": results
            }), 500

        # 4. Alterar status para "open"
        open_body = {"status": "open"}
        open_response = requests.post(toggle_status_url, headers=headers, json=open_body)
        
        results.append({
            "step": "status_open",
            "status_code": open_response.status_code,
            "success": open_response.status_code == 200
        })

        if open_response.status_code != 200:
            return jsonify({
                "error": "Falha ao alterar status para open",
                "conversation_id": conversation_id,
                "results": results
            }), 500

        return jsonify({
            "message": "Conversa atribuída para equipe e status atualizado com sucesso",
            "conversation_id": conversation_id,
            "results": results
        }), 200

    except requests.exceptions.RequestException as e:
        return jsonify({
            "error": "Erro na requisição para Chatwoot",
            "details": str(e)
        }), 500
    except Exception as e:
        return jsonify({
            "error": "Erro interno do servidor",
            "details": str(e)
        }), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Endpoint para verificar se a aplicação está funcionando"""
    return jsonify({
        "status": "healthy",
        "conversation_id_stored": conversation_id_storage.get("conversation_id") is not None
    }), 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
