# Knowledge Base Setup Guide for Communication Coaching

This guide will help you integrate PDF books into your PingPing system so the LLM can use them when coaching communication.

## Overview

The system uses RAGFlow as the knowledge base backend. When users ask about communication, relationships, or coaching topics, the LLM will automatically search your uploaded PDF books and use that information to provide better coaching.

## Step-by-Step Setup

### Step 1: Set Up RAGFlow (if not already done)

1. **Install and run RAGFlow** (if you haven't already)
   - RAGFlow is the knowledge base backend that processes and stores your PDFs
   - Make sure it's running and accessible
   - Note the RAGFlow server URL (e.g., `http://192.168.0.8` or `http://localhost:9380`)

2. **Get your RAGFlow API key**
   - Log into RAGFlow web interface
   - Go to API settings to generate or find your API key
   - Save this key for Step 3

### Step 2: Create Knowledge Base and Upload PDFs via Web Interface

1. **Access the Knowledge Base Management page**
   - Open your browser and go to: `http://localhost:8001/#/knowledge-base-management`
   - (Or use your manager-web URL)

2. **Create a new knowledge base**
   - Click "Add Knowledge Base" or similar button
   - Fill in:
     - **Name**: e.g., "Communication Coaching Books"
     - **Description**: e.g., "PDF books on communication, relationships, and coaching"
     - **RAG Model**: Select an appropriate embedding model (if available)
   - Click "Confirm" to create

3. **Upload your PDF books**
   - After creating the knowledge base, click on it to open the file upload page
   - Click "Upload Document" or similar
   - Select your PDF files (you can upload multiple)
   - Wait for upload to complete
   - **Important**: After upload, you need to **parse** the documents:
     - Find the uploaded files in the list
     - Click "Parse" or "Process" button for each document
     - Wait for parsing to complete (this chunks the PDFs for search)

4. **Get the Dataset ID**
   - After creating the knowledge base, note the **Dataset ID** (also called `datasetId`)
   - You can find it in:
     - The URL when viewing the knowledge base (e.g., `datasetId=abc123`)
     - The knowledge base list table
     - The browser's developer console network tab when creating/loading the knowledge base

### Step 3: Configure pingping-server

1. **Edit the configuration file**
   - Open: `pingping-server/config.yaml`
   - Find the `search_from_ragflow` section (around line 149)

2. **Update the configuration**
   ```yaml
   search_from_ragflow:
     description: "Use this knowledge base to find information from communication coaching books..."
     base_url: "http://YOUR_RAGFLOW_URL"  # Replace with your RAGFlow server URL
     api_key: "YOUR_API_KEY"              # Replace with your RAGFlow API key
     dataset_ids: ["YOUR_DATASET_ID"]     # Replace with your actual dataset ID(s)
   ```

   **Example:**
   ```yaml
   search_from_ragflow:
     description: "Use this knowledge base to find information from communication coaching books..."
     base_url: "http://192.168.0.8"
     api_key: "ragflow-abc123xyz"
     dataset_ids: ["dataset_12345"]
   ```

   **Multiple knowledge bases:**
   If you have multiple knowledge bases with different PDFs, you can list multiple dataset IDs:
   ```yaml
     dataset_ids: ["dataset_12345", "dataset_67890", "dataset_abcde"]
   ```

3. **Restart pingping-server**
   - Stop the current server (Ctrl+C)
   - Start it again: `python3 app.py` (or your startup command)
   - The LLM will now have access to the knowledge base function

### Step 4: Test the Integration

1. **Start a conversation with the LLM**
   - Connect via WebSocket or use the test page
   - Ask a question related to communication coaching, for example:
     - "How can I express my needs without criticizing my partner?"
     - "What are some active listening techniques?"
     - "How do I handle conflict in relationships?"
     - "What does the book say about emotional intelligence?"

2. **Verify knowledge base usage**
   - The LLM should automatically call the `search_from_ragflow` function
   - Check the server logs to see if the function was called
   - The response should reference information from your PDF books

## How It Works

1. **User asks a question** about communication or relationships
2. **LLM recognizes** the topic matches the knowledge base description
3. **LLM calls** `search_from_ragflow` function with the user's question
4. **Function queries RAGFlow** API with the question and dataset IDs
5. **RAGFlow returns** relevant chunks from your PDF books
6. **LLM uses** those chunks to provide an informed, book-based answer

## Troubleshooting

### LLM not using knowledge base
- **Check the function description**: Make sure it clearly describes when to use it
- **Check the system prompt**: The agent prompt should encourage using tools when relevant
- **Verify configuration**: Ensure `base_url`, `api_key`, and `dataset_ids` are correct
- **Check logs**: Look for errors when the function is called

### "RAG接口返回异常" error
- **Verify RAGFlow is running**: Check if you can access the RAGFlow web interface
- **Check API key**: Make sure the API key is correct and has proper permissions
- **Check dataset IDs**: Ensure the dataset IDs exist in RAGFlow
- **Check network**: Ensure pingping-server can reach the RAGFlow server

### Documents not found in search
- **Verify parsing**: Make sure documents were parsed after upload
- **Check dataset ID**: Ensure you're using the correct dataset ID in config
- **Wait for indexing**: After parsing, RAGFlow needs time to index the documents
- **Try different questions**: Some questions might not match the content in your PDFs

### Multiple knowledge bases
If you want to organize different books into separate knowledge bases:
1. Create multiple knowledge bases in the web interface
2. Upload different PDFs to each
3. Get all the dataset IDs
4. Add all IDs to `dataset_ids` in config.yaml:
   ```yaml
   dataset_ids: ["dataset_1", "dataset_2", "dataset_3"]
   ```

## Advanced Configuration

### Customizing when to use knowledge base

You can modify the function description in `pingping-server/plugins_func/functions/search_from_ragflow.py` to be more specific about when the LLM should use it.

### Updating the system prompt

The system prompt in `pingping-server/agent-base-prompt.txt` already includes guidance about using tools. The `<tool_calling>` section mentions that when `search_from_ragflow` is available, the LLM should use it when relevant.

## Next Steps

- Upload more PDF books as you acquire them
- Create specialized knowledge bases for different topics
- Monitor which questions trigger knowledge base searches
- Refine the function description to better match your use case

## Support

If you encounter issues:
1. Check the pingping-server logs for errors
2. Verify RAGFlow is accessible and documents are parsed
3. Test the RAGFlow API directly using curl or Postman
4. Review the configuration values in `config.yaml`

