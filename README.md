# Silver RAG Service

A FastAPI-based service for processing and storing documents with advanced AI capabilities. This service integrates document parsing, file storage, and RAG (Retrieval-Augmented Generation) functionality.

## Features

- Document parsing and OCR using Upstage AI
- Secure document storage in Google Cloud Storage
- RAG capabilities through Dify integration (to be replaced with open source vector DB)
- MySQL database for metadata storage

## Prerequisites

- Python 3.8+
- MySQL Database
- Google Cloud Storage
- Upstage API
- Dify API

## Setup

1. Clone the repository

2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Configure environment variables:
   - Copy `.env.example` to `.env`
   - Update the following variables in `.env`:
     - `DATABASE_URL`: Your MySQL connection string
     - `GOOGLE_CLOUD_CREDENTIALS`: Path to your Google Cloud credentials file
     - `UPSTAGE_API_KEY`: Your Upstage AI API key
     - `DIFY_DATASET_API_KEY`: Your Dify dataset API key
     - `DIFY_DATASET_ID`: Your Dify dataset ID

## Running the Service

### Local Development

```bash
uvicorn app.main:app --reload
```

### Docker

```bash
docker-compose up --build
```

## API Endpoints

The service provides RESTful APIs for document processing:

- `POST /documents`: Upload and process a new document
- `DELETE /documents`: Deletes a document
- Additional endpoints documentation coming soon

## Architecture

The service is built with a modular architecture:

- `app/controllers`: Request handlers and business logic
- `app/services`: External service integrations
- `app/models`: Database models and schemas

## License

This project is proprietary and confidential.
