import os
from whoosh.index import create_in, open_dir, exists_in
from whoosh.fields import Schema, TEXT, KEYWORD, ID
from whoosh.analysis import LanguageAnalyzer
from whoosh.qparser import QueryParser, OrGroup
from whoosh import scoring
from whoosh.highlight import HtmlFormatter

# Directorio del índice Whoosh
INDEX_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "whoosh_index")

# Esquema para indexación de fragmentos
schema = Schema(
    id=ID(stored=True, unique=True),
    folder_id=KEYWORD(stored=True),
    filename=KEYWORD(stored=True),
    text=TEXT(stored=True, analyzer=LanguageAnalyzer("es"))
)

class MarkdownFormatter(HtmlFormatter):
    """Formateador personalizado para convertir resaltados de Whoosh (<strong>) en Markdown (**)."""
    def format(self, fragments, replace=False):
        import re
        html = super().format(fragments, replace)
        # Reemplazar cualquier <strong class="..."> con ** y </strong> con **
        html = re.sub(r"<strong[^>]*>", "**", html)
        return html.replace("</strong>", "**")

def get_whoosh_index():
    if not os.path.exists(INDEX_DIR):
        os.makedirs(INDEX_DIR)
    
    if exists_in(INDEX_DIR):
        return open_dir(INDEX_DIR)
    else:
        return create_in(INDEX_DIR, schema)

def index_document_chunks(folder_id: str, filename: str, chunks: list):
    ix = get_whoosh_index()
    writer = ix.writer()
    
    for idx, chunk in enumerate(chunks):
        chunk_id = f"{folder_id}/{filename}/{idx}"
        # Usamos update_document para asegurar que no se dupliquen si volvemos a subir el mismo archivo
        writer.update_document(
            id=chunk_id,
            folder_id=folder_id,
            filename=filename,
            text=chunk
        )
    
    writer.commit()

def delete_document_index(folder_id: str, filename: str):
    ix = get_whoosh_index()
    writer = ix.writer()
    
    # Eliminar fragmentos pertenecientes a la combinación folder_id y filename
    from whoosh.query import And, Term
    q = And([Term("folder_id", folder_id), Term("filename", filename)])
    writer.delete_by_query(q)
    writer.commit()

def search_keywords(query_str: str, folder_id: str = None, filenames: list = None, limit: int = 20, markdown_highlights: bool = False):
    ix = get_whoosh_index()
    
    # Buscamos usando OrGroup para que priorice coincidencias de todas las palabras (BM25) pero acepte coincidencias parciales
    parser = QueryParser("text", schema=ix.schema, group=OrGroup)
    query = parser.parse(query_str)
    
    from whoosh.query import And, Term, Or
    filter_queries = []
    if folder_id:
        filter_queries.append(Term("folder_id", folder_id))
    if filenames and len(filenames) > 0:
        if len(filenames) == 1:
            filter_queries.append(Term("filename", filenames[0]))
        else:
            filter_queries.append(Or([Term("filename", f) for f in filenames]))
            
    filter_q = None
    if filter_queries:
        if len(filter_queries) == 1:
            filter_q = filter_queries[0]
        else:
            filter_q = And(filter_queries)
            
    results_list = []
    
    with ix.searcher(weighting=scoring.BM25F()) as searcher:
        results = searcher.search(query, limit=limit, filter=filter_q)
        
        # Configurar formateador
        if markdown_highlights:
            results.formatter = MarkdownFormatter()
        else:
            # Para HTML en frontend usaremos la etiqueta <mark> en vez de <b>
            results.formatter = HtmlFormatter(tagname="mark")
            
        for hit in results:
            snippet = hit.highlights("text", top=2)
            results_list.append({
                "filename": hit["filename"],
                "folder_id": hit["folder_id"],
                "text": hit["text"],
                "snippet": snippet or (hit["text"][:200] + "..."),
                "score": hit.score
            })
            
    return results_list
