# PDF Processing Guide for RAG Search

This guide explains how PDFs are processed into searchable segments (chunks) for RAG (Retrieval Augmented Generation) search in the PingPing system.

## Overview

The system uses **RAGFlow** as the backend to automatically process PDFs into searchable segments. The process involves:
1. **Upload**: PDF files are uploaded to a knowledge base
2. **Parse**: Documents are parsed and automatically chunked into segments
3. **Index**: Chunks are indexed for semantic search
4. **Search**: When users ask questions, relevant chunks are retrieved and used by the LLM

## Automatic Processing via Web Interface

### Step 1: Upload PDF

1. Go to the Knowledge Base Management page: `http://localhost:8001/#/knowledge-base-management`
2. Click on your knowledge base (or create a new one)
3. Click "Upload Document"
4. Select your PDF file(s)
5. Wait for upload to complete

**Note**: At this stage, the PDF is uploaded but **not yet processed** into searchable chunks.

### Step 2: Parse Documents (This Creates the Chunks)

After uploading, you **must parse** each document to create searchable segments:

1. Find your uploaded PDF in the document list
2. Check the document status - it should show as "Uploaded" or "Pending"
3. Click the **"Parse"** or **"Process"** button for each document
4. Wait for parsing to complete (this may take a few minutes for large PDFs)
5. The status will change to "Parsed" or "Completed" when done

**What happens during parsing:**
- RAGFlow extracts text from the PDF
- The text is automatically chunked into segments (typically 200-500 tokens each)
- Each chunk is embedded using the embedding model configured for the knowledge base
- Chunks are indexed for semantic search

## Chunking Methods

RAGFlow supports different chunking methods. You can specify the chunking method when uploading:

### Available Chunk Methods

The system supports passing a `chunk_method` parameter. Common methods include:

- **`naive`**: Simple text splitting by size
- **`book`**: Optimized for book-like documents (preserves chapter/section structure)
- **`paper`**: Optimized for academic papers (preserves citations and references)
- **`manual`**: Manual chunking (if supported)
- **`qa`**: Question-answer pair extraction (if the PDF contains Q&A format)

### How to Specify Chunk Method

Currently, the chunk method can be specified through:
1. **API calls** (if you're using the API directly)
2. **RAGFlow web interface** (when configuring the dataset)

The web interface may not expose chunk method selection directly, but RAGFlow will use a default method (usually `book` for PDFs) that works well for most cases.

## Parser Configuration

You can also configure the parser with `parser_config`:

```json
{
  "chunk_token_count": 512,      // Target tokens per chunk
  "layout_recognize": true,       // Use layout recognition for better structure
  "table_extract": true,         // Extract tables separately
  "image_extract": false,        // Extract images (if needed)
  "page_mode": "single"          // or "double" for two-column layouts
}
```

## Understanding Chunks

### What is a Chunk?

A chunk is a segment of text from your PDF that:
- Contains 200-500 tokens (roughly 150-400 words)
- Preserves semantic meaning (doesn't cut sentences in the middle)
- May overlap slightly with adjacent chunks for better context
- Is embedded as a vector for semantic search

### How Chunks are Used

When a user asks a question:
1. The question is embedded as a vector
2. RAGFlow searches for the most similar chunk vectors
3. Top 3-5 chunks are retrieved
4. These chunks are sent to the LLM as context
5. The LLM uses this context to answer the question

## Manual Processing (Advanced)

If you need more control, you can use the API directly:

### Upload with Custom Chunk Method

```bash
curl -X POST "http://YOUR_RAGFLOW_URL/api/v1/datasets/DATASET_ID/documents" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -F "file=@your_book.pdf" \
  -F "name=Communication Book" \
  -F "chunk_method=book"
```

### Parse Documents

```bash
curl -X POST "http://YOUR_RAGFLOW_URL/api/v1/datasets/DATASET_ID/chunks" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "document_ids": ["DOCUMENT_ID_1", "DOCUMENT_ID_2"]
  }'
```

### View Chunks

To see how your PDF was chunked:

```bash
curl -X GET "http://YOUR_RAGFLOW_URL/api/v1/datasets/DATASET_ID/documents/DOCUMENT_ID/chunks?page=1&page_size=10" \
  -H "Authorization: Bearer YOUR_API_KEY"
```

Or use the web interface:
1. Go to your knowledge base
2. Click on a parsed document
3. View the chunks list to see how it was segmented

## Best Practices

### 1. Document Quality
- Use **text-based PDFs** (not scanned images) for best results
- If you have scanned PDFs, use OCR to convert them to text first
- Ensure PDFs are not password-protected

### 2. Document Size
- Large PDFs (100+ pages) may take longer to parse
- Consider splitting very large books into multiple documents
- Typical parsing time: 1-2 minutes per 50 pages

### 3. Chunk Size
- Default chunk size (512 tokens) works well for most cases
- Smaller chunks (256 tokens) = more precise but may lose context
- Larger chunks (1024 tokens) = more context but may include irrelevant info

### 4. Multiple Documents
- Upload all your PDF books to the same knowledge base
- Each document is chunked independently
- All chunks are searchable together when you query

### 5. Testing
- After parsing, test with sample questions
- Check if relevant chunks are being retrieved
- Adjust chunk method or parser config if needed

## Troubleshooting

### Documents Not Parsing

**Problem**: Document stays in "Uploaded" status and never parses.

**Solutions**:
- Check RAGFlow server logs for errors
- Verify the PDF is not corrupted
- Try re-uploading the document
- Check if RAGFlow has enough resources (memory/CPU)

### Poor Search Results

**Problem**: Queries don't return relevant chunks.

**Solutions**:
- Verify documents were fully parsed (check status)
- Try different chunk methods (if available)
- Check if the embedding model is appropriate for your language
- Ensure PDF text extraction worked (check chunks in RAGFlow interface)

### Parsing Takes Too Long

**Problem**: Documents take hours to parse.

**Solutions**:
- Check RAGFlow server resources (CPU, memory, disk)
- Split large PDFs into smaller documents
- Consider using a more powerful server for RAGFlow

### Chunks Are Too Small/Large

**Problem**: Chunks don't contain enough context or contain too much.

**Solutions**:
- Adjust `chunk_token_count` in parser_config (if supported)
- Use a different chunk_method (e.g., `book` preserves more structure)
- Contact RAGFlow documentation for advanced configuration

## Verification

After processing, verify your PDFs are searchable:

1. **Check chunk count**: View the document details to see how many chunks were created
2. **Test search**: Use the RAGFlow interface to test search queries
3. **Check chunk quality**: Review a few chunks to ensure they make sense
4. **Test with LLM**: Ask the LLM a question that should be answered by your PDFs

## Example: Processing a Communication Book

1. **Upload**: `Nonviolent_Communication.pdf` (200 pages)
2. **Parse**: Click "Parse" button, wait ~5 minutes
3. **Result**: 
   - Document parsed into ~400 chunks
   - Each chunk contains 1-2 paragraphs
   - Chunks preserve chapter/section structure
4. **Test**: Ask "How do I express needs without criticism?"
5. **Expected**: LLM retrieves relevant chunks and answers based on the book

## Next Steps

- Monitor search quality and adjust as needed
- Add more PDFs to expand your knowledge base
- Experiment with different chunk methods for different document types
- Review retrieved chunks periodically to ensure quality

## Additional Resources

- RAGFlow Documentation: Check RAGFlow's official docs for latest chunking options
- Embedding Models: The embedding model affects search quality - ensure it's appropriate for your language
- Vector Database: RAGFlow uses a vector database to store chunks - ensure it has enough capacity

