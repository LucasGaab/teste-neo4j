# app.py - Servidor de backend com Flask e Neo4j para o Sistema de Biblioteca

# ADIÇÃO 1/3: Importar a função 'send_from_directory'
from flask import Flask, request, jsonify, send_from_directory
from neo4j import GraphDatabase
from dotenv import load_dotenv
import os
from flask_cors import CORS
import atexit

# Carrega variáveis de ambiente do arquivo .env
load_dotenv()

# ADIÇÃO 2/3: Modificar a criação do app para ele encontrar a pasta do frontend
app = Flask(__name__, static_folder='../frontend')
CORS(app) # Habilita CORS para todas as rotas da aplicação

# Configurações do Neo4j
NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

# Inicializa o driver do Neo4j
driver = None 
try:
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))
    driver.verify_connectivity()
    print("Conexão com Neo4j estabelecida com sucesso.")
except Exception as e:
    print(f"Erro ao conectar ao Neo4j: {e}")

# Função para fechar a conexão com o banco de dados ao encerrar a aplicação
@atexit.register
def close_db():
    if driver:
        driver.close()
        print("Conexão com Neo4j fechada.")


# --- ROTA PRINCIPAL PARA SERVIR O FRONTEND ---

# ADIÇÃO 3/3: Esta rota entrega o seu arquivo index.html para o navegador
@app.route('/')
def serve_frontend():
    return send_from_directory(app.static_folder, 'index.html')


# --- SUAS ROTAS DE API ORIGINAIS (TUDO ABAIXO ESTÁ IGUAL AO SEU CÓDIGO) ---

# Endpoint de recomendação de livros
@app.route('/api/recommendations', methods=['GET'])
def get_recommendations():
    if not driver:
        return jsonify({"error": "Banco de dados não conectado."}), 500

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
            recommendations = []
            
            for record in result:
                book = {
                    "title": record["title"],
                    "author": record["author"] if record["author"] is not None else "Desconhecido",
                    "genre": record["genre"],
                    "year": record["year"] if record["year"] is not None else "N/A",
                    "pages": record["pages"] if record["pages"] is not None else "N/A"
                }
                recommendations.append(book)
            
            return jsonify(recommendations), 200
    except Exception as e:
        print(f"Erro ao executar consulta Cypher: {e}")
        return jsonify({"error": "Erro interno do servidor ao buscar recomendações."}), 500

# ENDPOINT: Listar todos os dados para debug
@app.route('/api/debug/all_data', methods=['GET'])
def debug_all_data():
    if not driver:
        return jsonify({"error": "Banco de dados não conectado."}), 500
    
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
            
            data = []
            for record in result:
                data.append({
                    "title": record["title"],
                    "authors": [a for a in record["authors"] if a is not None],
                    "genres": [g for g in record["genres"] if g is not None],
                    "publishers": [p for p in record["publishers"] if p is not None],
                    "year": record["year"],
                    "pages": record["pages"]
                })
            
            return jsonify({
                "total_books": len(data),
                "books": data
            }), 200
    except Exception as e:
        print(f"Erro ao buscar dados para debug: {e}")
        return jsonify({"error": f"Erro ao buscar dados: {str(e)}"}), 500

# ENDPOINT: Listar gêneros disponíveis
@app.route('/api/genres', methods=['GET'])
def get_genres():
    if not driver:
        return jsonify({"error": "Banco de dados não conectado."}), 500
    
    try:
        with driver.session() as session:
            query = "MATCH (g:Genero) RETURN g.nome AS genre ORDER BY g.nome"
            result = session.run(query)
            genres = [record["genre"] for record in result]
            return jsonify(genres), 200
    except Exception as e:
        print(f"Erro ao buscar gêneros: {e}")
        return jsonify({"error": f"Erro ao buscar gêneros: {str(e)}"}), 500

# ENDPOINT: Listar autores disponíveis
@app.route('/api/authors', methods=['GET'])
def get_authors():
    if not driver:
        return jsonify({"error": "Banco de dados não conectado."}), 500
    
    try:
        with driver.session() as session:
            query = "MATCH (a:Autor) RETURN a.nome AS author ORDER BY a.nome"
            result = session.run(query)
            authors = [record["author"] for record in result]
            return jsonify(authors), 200
    except Exception as e:
        print(f"Erro ao buscar autores: {e}")
        return jsonify({"error": f"Erro ao buscar autores: {str(e)}"}), 500

# ENDPOINT: Executar consulta Cypher arbitrária
@app.route('/api/cypher', methods=['POST'])
def execute_cypher_query():
    if not driver:
        return jsonify({"error": "Banco de dados não conectado."}), 500
    
    data = request.get_json()
    query = data.get('query')
    params = data.get('params', {})

    if not query:
        return jsonify({"error": "A consulta Cypher é obrigatória."}), 400

    try:
        with driver.session() as session:
            result = session.run(query, params)
            records = []
            try:
                for record in result:
                    records.append(record.data())
            except Exception:
                summary = result.consume()
                records.append(summary.counters.__dict__)
            return jsonify(records), 200
    except Exception as e:
        return jsonify({"error": f"Erro ao executar consulta Cypher: {str(e)}"}), 500

# Funções auxiliares para contagem de nós
def get_node_count(label):
    if not driver: return 0
    try:
        with driver.session() as session:
            result = session.run(f"MATCH (n:{label}) RETURN count(n) AS count")
            return result.single()["count"]
    except Exception as e:
        print(f"Erro ao contar nós {label}: {e}")
        return 0

@app.route('/api/stats/total_authors', methods=['GET'])
def total_authors():
    return jsonify({"count": get_node_count("Autor")})

@app.route('/api/stats/total_books', methods=['GET'])
def total_books():
    return jsonify({"count": get_node_count("Livro")})

@app.route('/api/stats/total_genres', methods=['GET'])
def total_genres():
    return jsonify({"count": get_node_count("Genero")})

@app.route('/api/stats/total_publishers', methods=['GET'])
def total_publishers():
    return jsonify({"count": get_node_count("Editora")})

@app.route('/api/stats/most_productive_authors', methods=['GET'])
def most_productive_authors():
    if not driver: return jsonify([])
    try:
        with driver.session() as session:
            query = """
            MATCH (a:Autor)-[:ESCREVEU]->(l:Livro)
            RETURN a.nome AS author, count(l) AS bookCount
            ORDER BY bookCount DESC LIMIT 3
            """
            result = session.run(query)
            return jsonify([record.data() for record in result]), 200
    except Exception as e:
        print(f"Erro ao buscar autores mais produtivos: {e}")
        return jsonify({"error": f"Erro ao buscar autores mais produtivos: {str(e)}"}), 500

@app.route('/api/stats/most_popular_genres', methods=['GET'])
def most_popular_genres():
    if not driver: return jsonify([])
    try:
        with driver.session() as session:
            query = """
            MATCH (g:Genero)<-[:TEM_GENERO]-(l:Livro)
            RETURN g.nome AS genre, count(l) AS bookCount
            ORDER BY bookCount DESC LIMIT 3
            """
            result = session.run(query)
            return jsonify([record.data() for record in result]), 200
    except Exception as e:
        print(f"Erro ao buscar gêneros mais populares: {e}")
        return jsonify({"error": f"Erro ao buscar gêneros mais populares: {str(e)}"}), 500

# ENDPOINT: Limpar Banco de Dados
@app.route('/api/clear_database', methods=['POST'])
def clear_database_endpoint():
    if not driver:
        return jsonify({"error": "Banco de dados não conectado."}), 500
    try:
        with driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")
        return jsonify({"message": "Banco de dados limpo com sucesso!"}), 200
    except Exception as e:
        print(f"Erro ao limpar o banco de dados: {e}")
        return jsonify({"error": f"Erro ao limpar o banco de dados: {str(e)}"}), 500

# ENDPOINT: Testar Conexão
@app.route('/api/test_connection', methods=['GET'])
def test_connection_endpoint():
    if driver:
        try:
            driver.verify_connectivity()
            return jsonify({"status": "connected", "message": "Conexão com Neo4j estabelecida."}), 200
        except Exception as e:
            return jsonify({"status": "disconnected", "message": f"Erro na conexão com Neo4j: {str(e)}"}), 500
    else:
        return jsonify({"status": "disconnected", "message": "Driver Neo4j não inicializado."}), 500

# ENDPOINT: Adicionar Livro
@app.route('/api/add_book', methods=['POST'])
def add_book():
    if not driver:
        return jsonify({"error": "Banco de dados não conectado."}), 500

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
            session.run("""
                MERGE (a:Autor {nome: $author_name})
                MERGE (l:Livro {titulo: $title})
                ON CREATE SET l.ano = $year, l.paginas = $pages
                MERGE (a)-[:ESCREVEU]->(l)
                FOREACH (genre_name IN $genres |
                    MERGE (g:Genero {nome: genre_name})
                    MERGE (l)-[:TEM_GENERO]->(g)
                )
                WITH l, $publisher_name AS publisher_name
                WHERE publisher_name IS NOT NULL AND publisher_name <> ''
                MERGE (p:Editora {nome: publisher_name})
                MERGE (l)-[:PUBLICADO_POR]->(p)
            """, {
                "author_name": author_name,
                "title": title,
                "year": int(year) if year else None,
                "pages": int(pages) if pages else None,
                "genres": genres,
                "publisher_name": publisher_name
            })
        return jsonify({"message": f"Livro '{title}' adicionado/atualizado com sucesso!"}), 201
    except Exception as e:
        print(f"Erro ao adicionar livro: {e}")
        return jsonify({"error": f"Erro interno do servidor ao adicionar livro: {str(e)}"}), 500

# Ponto de entrada para execução local
if __name__ == '__main__':
    app.run(debug=True, port=5000)