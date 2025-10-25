"""Document indexing utilities"""

from typing import List
from langchain.schema import Document

from RAG.vectorstore.pgvector_store import PgVectorStore
from RAG.core.logger import get_logger


logger = get_logger(__name__)


class DocumentIndexer:
    """
    Document indexer for batch indexing with progress logging.
    """
    
    def __init__(
        self,
        vectorstore: PgVectorStore,
        batch_size: int = 100
    ):
        """
        Initialize document indexer.
        
        Args:
            vectorstore: PgVector store instance
            batch_size: Number of documents to process in each batch
        """
        self.vectorstore = vectorstore
        self.batch_size = batch_size
        logger.info(f"Initialized DocumentIndexer (batch_size={batch_size})")
    
    def index_documents(
        self,
        documents: List[Document],
        skip_duplicates: bool = True
    ) -> dict:
        """
        Index documents with progress logging.
        
        Args:
            documents: List of documents to index
            skip_duplicates: Whether to skip duplicate documents
        
        Returns:
            Dictionary with indexing statistics
        """
        total = len(documents)
        logger.info(f"Starting indexing of {total} documents")
        
        indexed_count = 0
        failed_count = 0
        skipped_count = 0
        
        try:
            # Index in batches
            for i in range(0, total, self.batch_size):
                batch = documents[i:i+self.batch_size]
                batch_num = i // self.batch_size + 1
                total_batches = (total + self.batch_size - 1) // self.batch_size
                
                logger.info(f"Processing batch {batch_num}/{total_batches} ({len(batch)} documents)")
                
                try:
                    doc_ids = self.vectorstore.add_documents(batch, batch_size=len(batch))
                    indexed_count += len(doc_ids)
                    
                    # Log progress
                    progress = (i + len(batch)) / total * 100
                    logger.info(f"Progress: {progress:.1f}% ({i + len(batch)}/{total} documents)")
                    
                except Exception as e:
                    logger.error(f"Failed to index batch {batch_num}: {e}")
                    failed_count += len(batch)
                    continue
            
            # Log summary
            logger.info("=" * 60)
            logger.info("Indexing Summary:")
            logger.info(f"  Total documents: {total}")
            logger.info(f"  Successfully indexed: {indexed_count}")
            logger.info(f"  Failed: {failed_count}")
            logger.info(f"  Skipped: {skipped_count}")
            logger.info("=" * 60)
            
            return {
                "total": total,
                "indexed": indexed_count,
                "failed": failed_count,
                "skipped": skipped_count
            }
        
        except Exception as e:
            logger.error(f"Indexing failed: {e}")
            raise

    
    def index_from_csv(
        self,
        csv_path: str,
        bank_name: str = None,
        product_type: str = None
    ) -> dict:
        """
        Load and index documents from CSV file.
        
        Args:
            csv_path: Path to CSV file
            bank_name: Optional bank name filter
            product_type: Optional product type filter
        
        Returns:
            Dictionary with indexing statistics
        """
        from RAG.ingestion.load_csv import load_bank_data_filtered
        
        logger.info(f"Loading documents from {csv_path}")
        
        if bank_name or product_type:
            documents = load_bank_data_filtered(csv_path, bank_name, product_type)
        else:
            from RAG.ingestion.load_csv import load_bank_data
            documents = load_bank_data(csv_path)
        
        logger.info(f"Loaded {len(documents)} documents")
        
        return self.index_documents(documents)
