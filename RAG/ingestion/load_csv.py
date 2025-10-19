"""CSV data loading utilities"""

import pandas as pd
from typing import List
from langchain.schema import Document

from RAG.core.logger import get_logger


logger = get_logger(__name__)


def load_bank_data(csv_path: str) -> List[Document]:
    """
    Load bank data from CSV file and convert to Document objects.
    
    Args:
        csv_path: Path to CSV file
    
    Returns:
        List of LangChain Document objects
    
    Expected CSV columns:
        - chunk_id: Chunk identifier
        - doc_id: Document identifier
        - 은행명: Bank name (우리은행 or 국민은행)
        - 상품종류: Product type (대출 or 예적금)
        - 상품이름: Product name
        - 조항: Clause number
        - 조항이름: Clause name
        - text: Original text
        - context: Processed context text (used as page_content)
    """
    logger.info(f"Loading bank data from {csv_path}")
    
    try:
        # Read CSV
        df = pd.read_csv(csv_path)
        logger.info(f"Loaded {len(df)} rows from CSV")
        
        # Convert to Document objects
        documents = []
        for idx, row in df.iterrows():
            # Use context as the main content
            content = row.get("context", row.get("text", ""))
            
            # Build metadata
            metadata = {
                "chunk_id": str(row.get("chunk_id", "")),
                "doc_id": str(row.get("doc_id", "")),
                "은행명": str(row.get("은행명", "")),
                "상품종류": str(row.get("상품종류", "")),
                "상품이름": str(row.get("상품이름", "")),
                "조항": str(row.get("조항", "")),
                "조항이름": str(row.get("조항이름", ""))
            }
            
            # Create Document
            doc = Document(
                page_content=content,
                metadata=metadata
            )
            documents.append(doc)
        
        logger.info(f"Created {len(documents)} Document objects")
        return documents
    
    except FileNotFoundError:
        logger.error(f"CSV file not found: {csv_path}")
        raise
    except Exception as e:
        logger.error(f"Failed to load CSV: {e}")
        raise


def load_bank_data_filtered(
    csv_path: str,
    bank_name: str = None,
    product_type: str = None
) -> List[Document]:
    """
    Load bank data with filters.
    
    Args:
        csv_path: Path to CSV file
        bank_name: Filter by bank name (optional)
        product_type: Filter by product type (optional)
    
    Returns:
        List of filtered Document objects
    """
    logger.info(f"Loading filtered bank data (bank={bank_name}, product={product_type})")
    
    try:
        df = pd.read_csv(csv_path)
        
        # Apply filters
        if bank_name:
            df = df[df["은행명"] == bank_name]
        if product_type:
            df = df[df["상품종류"] == product_type]
        
        logger.info(f"Filtered to {len(df)} rows")
        
        # Convert to documents
        documents = []
        for idx, row in df.iterrows():
            content = row.get("context", row.get("text", ""))
            
            metadata = {
                "chunk_id": str(row.get("chunk_id", "")),
                "doc_id": str(row.get("doc_id", "")),
                "은행명": str(row.get("은행명", "")),
                "상품종류": str(row.get("상품종류", "")),
                "상품이름": str(row.get("상품이름", "")),
                "조항": str(row.get("조항", "")),
                "조항이름": str(row.get("조항이름", ""))
            }
            
            doc = Document(page_content=content, metadata=metadata)
            documents.append(doc)
        
        return documents
    
    except Exception as e:
        logger.error(f"Failed to load filtered data: {e}")
        raise
