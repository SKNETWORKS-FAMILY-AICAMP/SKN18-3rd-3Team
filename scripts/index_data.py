"""Script to index bank data into vector store"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from rag.core.config import get_config
from rag.core.logger import get_logger
from rag.db.connection import DatabaseConnection
from rag.db.repo import DocumentRepository
from rag.embeddings.openai_embed import OpenAIEmbeddings
from rag.vectorstore.pgvector_store import PgVectorStore
from rag.ingestion.indexer import DocumentIndexer
from rag.ingestion.load_csv import load_bank_data


logger = get_logger(__name__)


def main(file_path):
    """Main indexing function"""
    logger.info("=" * 60)
    logger.info("Starting Bank Data Indexing")
    logger.info("=" * 60)
    
    try:
        # Load configuration
        logger.info("Loading configuration...")
        config = get_config()
        
        # Initialize database connection
        logger.info("Connecting to database...")
        db = DatabaseConnection(config.DB_URL)
        
        # Check database health
        if not db.health_check():
            logger.error("Database health check failed!")
            return 1
        logger.info("Database connection healthy")
        
        # Initialize repository and create tables
        logger.info("Creating database tables...")
        repo = DocumentRepository(db)
        repo.create_tables()
        
        # Initialize embeddings
        logger.info(f"Initializing embeddings ({config.EMBED_MODEL})...")
        embeddings = OpenAIEmbeddings(
            model=config.EMBED_MODEL,
            api_key=config.OPENAI_API_KEY,
            timeout=config.OPENAI_TIMEOUT
        )
        
        # Initialize vector store
        logger.info("Initializing vector store...")
        vectorstore = PgVectorStore(
            connection=db,
            embeddings=embeddings
        )
        
        # Initialize indexer
        logger.info("Initializing indexer...")
        indexer = DocumentIndexer(vectorstore, batch_size=50)
        
        # Load documents from CSV
        # file_path 파라미터가 있으면 사용, 없으면 기본 경로 시도
        if file_path:
            csv_path = file_path
        else:
            # 여러 CSV 파일 경로 시도
            csv_paths = [
                "data/final_embedding_data_v7.csv.csv",
                "data/final_embedding_data_v4.csv"
            ]
            
            csv_path = None
            for path in csv_paths:
                if os.path.exists(path):
                    csv_path = path
                    break
            
            if not csv_path:
                logger.error(f"CSV 파일을 찾을 수 없습니다! 확인한 경로: {csv_paths}")
                return 1
        
        logger.info(f"Loading documents from {csv_path}...")
        documents = load_bank_data(csv_path)
        logger.info(f"Loaded {len(documents)} documents")
        
        # Index documents
        logger.info("Starting indexing process...")
        stats = indexer.index_documents(documents)
        
        # Print final statistics
        logger.info("=" * 60)
        logger.info("Indexing Complete!")
        logger.info(f"Total documents: {stats['total']}")
        logger.info(f"Successfully indexed: {stats['indexed']}")
        logger.info(f"Failed: {stats['failed']}")
        logger.info(f"Skipped: {stats['skipped']}")
        logger.info("=" * 60)
        
        # Verify document count
        doc_count = repo.get_document_count()
        logger.info(f"Total documents in database: {doc_count}")
        
        return 0
    
    except Exception as e:
        logger.error(f"Indexing failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    file_path = "data/final_embedding_data_v4.csv"
    exit_code = main(file_path)
    sys.exit(exit_code)
