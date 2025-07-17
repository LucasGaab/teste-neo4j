# app.py - Servidor de backend com Flask e Neo4j para o Sistema de Biblioteca

# --- 1. IMPORTAÇÕES ---
# Todas as bibliotecas necessárias para o projeto
from flask import Flask, request, jsonify, send_from_directory
from neo4j import GraphDatabase
from dotenv import load_dotenv
import os
from flask_cors import CORS
import atexit

# --- 2. CONFIGURAÇÃO INICIAL DO APP ---
# Carrega variáveis de ambiente do arquivo .env (para teste local)
load_dotenv()

# Cria a aplicação Flask e aponta para a pasta do frontend
# Este é um dos passos cruciais: ele diz ao Python onde encontrar seu index.html
app = Flask(__name__, static_folder='../frontend')

# Habilita CORS para permitir que o frontend (no navegador) se comunique com esta API
CORS(app)

# --- 3. CONEXÃO COM O BANCO DE DADOS NEO4J ---
# Lê as credenciais das variáveis de ambiente que você configurou no Railway
NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

driver = None
try:
    # Tenta estabelecer a conexão
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))
    # Verifica se a conexão é válida
    driver.verify_connectivity()
    print(">>> Conexão com Neo4j estabelecida com sucesso.")
except Exception as e:
    # Se a conexão falhar, imprime um erro claro no log.
    # Este é um ponto comum de falha no deploy.
    print(f">>> ERRO CRÍTICO: Não foi possível conectar ao Neo4j. Verifique as variáveis de ambiente. Erro: {e}")

# Garante que a conexão com o banco seja fechada ao encerrar o app
@atexit.register
def close_db():
    if driver:
        driver.close()
        print(">>> Conexão com Neo4j fechada.")


# --- 4. ROTA PRINCIPAL PARA SERVIR O FRONTEND ---
# Esta é a rota que resolve o erro "404 Not Found"
# Quando alguém acessa a URL principal (ex: seu-site.up.railway.app/), esta função é chamada.
@app.route('/')
def serve_frontend():
    # A função envia o arquivo 'index.html' da pasta 'frontend' para o navegador do usuário
    return send_from_directory(app.static_folder, 'index.html')


# --- 5. ROTAS DA API ---
# Todo o seu código de API continua abaixo, sem alterações.

@app.route('/api/recommendations', methods=['GET'])
def get_recommendations():
    if not driver:
        return jsonify({"error": "Banco de dados não conectado."}), 503

    genre = request.args.get('genre')
    author = request.args.get('author')

    if not genre:
        return jsonify({"error": "O parâmetro 'genre' é obrigatório."}), 400

    if author and author.lower() not in ['qualquer', '', 'any']:
        query = """
            MATCH (l:Livro)-[:TEM_GENERO]->(g:Genero)
            WHERE toLower(g.nome) CONTAINS toLower($genre)
            WITH l, g
            MATCH (a:Autor)-[:ESCREVEU]->(l)
            WHERE toLower(a.nome) CONTAINS toLower($author)
            RETURN l.titulo AS title, a.nome AS author, g.nome AS genre, l.ano AS year, l.paginas AS pages
            LIMIT 10
        """
        params = {"genre": genre, "author": author}
    else:
        query = """
            MATCH (l:Livro)-[:TEM_GENERO]->(g:Genero)
            WHERE toLower(g.nome) CONTAINS toLower($genre)
            OPTIONAL MATCH (a:Autor)-[:ESCREVEU]->(l)
            RETURN l.titulo AS title, a.nome AS author, g.nome AS genre, l.ano AS year, l.paginas AS pages
            LIMIT 10
        """
        params = {"genre": genre}

    try:
        with driver.session() as session:
            result = session.run(query, params)
            recommendations = [
                {
                    "title": record["title"],
                    "author": record["author"] if record["author"] else "Desconhecido",
                    "genre": record["genre"],
                    "year": record["year"] if record["year"] else "N/A",
                    "pages": record["pages"] if record["pages"] else "N/A"
                } for record in result
            ]
            return jsonify(recommendations), 200
    except Exception as e:
        print(f"Erro ao executar consulta Cypher: {e}")
        return jsonify({"error": "Erro interno do servidor ao buscar recomendações."}), 500


@app.route('/api/debug/all_data', methods=['GET'])
def debug_all_data():
    if not driver:
        return jsonify({"error": "Banco de dados não conectado."}), 503
    
    try:
        with driver.session() as session:
            query = """
            MATCH (l:Livro)
            OPTIONAL MATCH (a:Autor)-[:ESCREVEU]->(l)
            OPTIONAL MATCH (l)-[:TEM_GENERO]->(g:Genero)
            OPTIONAL MATCH (l)-[:PUBLICADO_POR]->(p:Editora)
            RETURN l.titulo AS title, 
                   collect(DISTINCT a.nome) AS authors,
                   collect(DISTINCT g.nome) AS genres,
                   collect(DISTINCT p.nome) AS publishers,
                   l.ano AS year,
                   l.paginas AS pages
            ORDER BY l.titulo
            """
            result = session.run(query)
            data = [
                {
                    "title": record["title"],
                    "authors": [a for a in record["authors"] if a],
                    "genres": [g for g in record["genres"] if g],
                    "publishers": [p for p in record["publishers"] if p],
                    "year": record["year"],
                    "pages": record["pages"]
                } for record in result
            ]
            return jsonify({"total_books": len(data), "books": data}), 200
    except Exception as e:
        print(f"Erro ao buscar dados para debug: {e}")
        return jsonify({"error": f"Erro ao buscar dados: {str(e)}"}), 500


@app.route('/api/genres', methods=['GET'])
def get_genres():
    if not driver:
        return jsonify({"error": "Banco de dados não conectado."}), 503
    
    try:
        with driver.session() as session:
            result = session.run("MATCH (g:Genero) RETURN g.nome AS genre ORDER BY g.nome")
            genres = [record["genre"] for record in result]
            return jsonify(genres), 200
    except Exception as e:
        print(f"Erro ao buscar gêneros: {e}")
        return jsonify({"error": f"Erro ao buscar gêneros: {str(e)}"}), 500


@app.route('/api/authors', methods=['GET'])
def get_authors():
    if not driver:
        return jsonify({"error": "Banco de dados não conectado."}), 503
    
    try:
        with driver.session() as session:
            result = session.run("MATCH (a:Autor) RETURN a.nome AS author ORDER BY a.nome")
            authors = [record["author"] for record in result]
            return jsonify(authors), 200
    except Exception as e:
        print(f"Erro ao buscar autores: {e}")
        return jsonify({"error": f"Erro ao buscar autores: {str(e)}"}), 500


@app.route('/api/cypher', methods=['POST'])
def execute_cypher_query():
    if not driver:
        return jsonify({"error": "Banco de dados não conectado."}), 503
    
    data = request.get_json()
    query = data.get('query')
    params = data.get('params', {})

    if not query:
        return jsonify({"error": "A consulta Cypher é obrigatória."}), 400

    try:
        with driver.session() as session:
            result = session.run(query, params)
            try:
                records = [record.data() for record in result]
            except Exception:
                summary = result.consume()
                records = [{"summary": summary.counters.__dict__}]
            return jsonify(records), 200
    except Exception as e:
        return jsonify({"error": f"Erro ao executar consulta Cypher: {str(e)}"}), 500


@app.route('/api/clear_database', methods=['POST'])
def clear_database_endpoint():
    if not driver:
        return jsonify({"error": "Banco de dados não conectado."}), 503
    try:
        with driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")
        return jsonify({"message": "Banco de dados limpo com sucesso!"}), 200
    except Exception as e:
        print(f"Erro ao limpar o banco de dados: {e}")
        return jsonify({"error": f"Erro ao limpar o banco de dados: {str(e)}"}), 500


@app.route('/api/test_connection', methods=['GET'])
def test_connection_endpoint():
    if not driver:
        return jsonify({"status": "disconnected", "message": "Driver Neo4j não inicializado."}), 503
    
    try:
        driver.verify_connectivity()
        return jsonify({"status": "connected", "message": "Conexão com Neo4j estabelecida."}), 200
    except Exception as e:
        return jsonify({"status": "disconnected", "message": f"Erro na conexão com Neo4j: {str(e)}"}), 500


@app.route('/api/add_book', methods=['POST'])
def add_book():
    if not driver:
        return jsonify({"error": "Banco de dados não conectado."}), 503

    data = request.get_json()
    title = data.get('title')
    author_name = data.get('author')
    genres_str = data.get('genres', '')
    publisher_name = data.get('publisher')
    year = data.get('year')
    pages = data.get('pages')

    if not all([title, author_name, genres_str]):
        return jsonify({"error": "Título, autor e pelo menos um gênero são obrigatórios."}), 400

    genres = [g.strip() for g in genres_str.split(',') if g.strip()]

    try:
        with driver.session() as session:
            tx = session.begin_transaction()
            try:
                tx.run("MERGE (a:Autor {nome: $author_name})", {"author_name": author_name})

                if publisher_name:
                    tx.run("MERGE (p:Editora {nome: $publisher_name})", {"publisher_name": publisher_name})

                book_props = {}
                if year: book_props["ano"] = int(year)
                if pages: book_props["paginas"] = int(pages)
                tx.run("MERGE (l:Livro {titulo: $title}) SET l += $props", {"title": title, "props": book_props})

                tx.run("MATCH (a:Autor {nome: $author_name}) MATCH (l:Livro {titulo: $title}) MERGE (a)-[:ESCREVEU]->(l)",
                       {"author_name": author_name, "title": title})

                for genre_name in genres:
                    tx.run("""
                        MATCH (l:Livro {titulo: $title})
                        MERGE (g:Genero {nome: $genre_name})
                        MERGE (l)-[:TEM_GENERO]->(g)
                    """, {"title": title, "genre_name": genre_name})

                if publisher_name:
                    tx.run("""
                        MATCH (l:Livro {titulo: $title})
                        MATCH (p:Editora {nome: $publisher_name})
                        MERGE (l)-[:PUBLICADO_POR]->(p)
                    """, {"title": title, "publisher_name": publisher_name})
                
                tx.commit()
            except Exception as e:
                tx.rollback()
                raise e

        return jsonify({"message": f"Livro '{title}' adicionado/atualizado com sucesso!"}), 201
    except Exception as e:
        print(f"Erro ao adicionar livro: {e}")
        return jsonify({"error": f"Erro interno do servidor ao adicionar livro: {str(e)}"}), 500


# Ponto de entrada para execução local (não é usado pelo Railway)
if __name__ == '__main__':
    app.run(debug=True, port=5000)
