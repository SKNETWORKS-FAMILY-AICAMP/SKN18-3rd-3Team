"""CSV data loading utilities"""

import pandas as pd
from typing import List
from langchain.schema import Document

from rag.core.logger import get_logger


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
        - 조항내용: Clause content (used as page_content)
    """
    logger.info(f"Loading bank data from {csv_path}")
    
    try:
        # Read CSV
        df = pd.read_csv(csv_path)
        logger.info(f"Loaded {len(df)} rows from CSV")
        
        # Convert to Document objects
        documents = []
        skipped = 0
        
        for idx, row in df.iterrows():
            # Use 조항내용 as the main content (fallback to context or text)
            content = row.get("조항내용", row.get("context", row.get("text", "")))
            
            # Skip if content is empty, NaN, or None
            if pd.isna(content) or not str(content).strip():
                skipped += 1
                logger.debug(f"Skipping row {idx}: empty content")
                continue
            
            # Convert to string and strip
            content = str(content).strip()
            
            # Skip if content is too short (less than 10 characters)
            if len(content) < 10:
                skipped += 1
                logger.debug(f"Skipping row {idx}: content too short ({len(content)} chars)")
                continue
            
            # Build metadata (handle NaN values)
            metadata = {
                "chunk_id": str(row.get("chunk_id", "")) if pd.notna(row.get("chunk_id")) else "",
                "doc_id": str(row.get("doc_id", "")) if pd.notna(row.get("doc_id")) else "",
                "은행명": str(row.get("은행명", "")) if pd.notna(row.get("은행명")) else "",
                "상품종류": str(row.get("상품종류", "")) if pd.notna(row.get("상품종류")) else "",
                "상품이름": str(row.get("상품이름", "")) if pd.notna(row.get("상품이름")) else "",
                "조항": str(row.get("조항", "")) if pd.notna(row.get("조항")) else "",
                "조항이름": str(row.get("조항이름", "")) if pd.notna(row.get("조항이름")) else ""
            }
            
            # Create Document
            doc = Document(
                page_content=content,
                metadata=metadata
            )
            documents.append(doc)
        
        logger.info(f"Created {len(documents)} Document objects (skipped {skipped} invalid rows)")
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
        skipped = 0
        
        for idx, row in df.iterrows():
            # Use 조항내용 as the main content (fallback to context or text)
            content = row.get("조항내용", row.get("context", row.get("text", "")))
            
            # Skip if content is empty, NaN, or None
            if pd.isna(content) or not str(content).strip():
                skipped += 1
                continue
            
            # Convert to string and strip
            content = str(content).strip()
            
            # Skip if content is too short
            if len(content) < 10:
                skipped += 1
                continue
            
            # Build metadata (handle NaN values)
            metadata = {
                "chunk_id": str(row.get("chunk_id", "")) if pd.notna(row.get("chunk_id")) else "",
                "doc_id": str(row.get("doc_id", "")) if pd.notna(row.get("doc_id")) else "",
                "은행명": str(row.get("은행명", "")) if pd.notna(row.get("은행명")) else "",
                "상품종류": str(row.get("상품종류", "")) if pd.notna(row.get("상품종류")) else "",
                "상품이름": str(row.get("상품이름", "")) if pd.notna(row.get("상품이름")) else "",
                "조항": str(row.get("조항", "")) if pd.notna(row.get("조항")) else "",
                "조항이름": str(row.get("조항이름", "")) if pd.notna(row.get("조항이름")) else ""
            }
            
            doc = Document(page_content=content, metadata=metadata)
            documents.append(doc)
        
        logger.info(f"Created {len(documents)} valid documents (skipped {skipped} invalid rows)")
        return documents
    
    except Exception as e:
        logger.error(f"Failed to load filtered data: {e}")
        raise
