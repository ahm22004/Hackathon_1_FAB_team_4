# README Documentation

## Overview

This project provides an API built with FastAPI that integrates with AWS Bedrock for language model interactions, Git repositories, and Gitpod workspace management. The primary functionalities include:

1. Cloning Git repositories.
2. Detecting project types and generating setup commands using a language model.
3. Interacting with Gitpod to list organizations, workspaces, and manage workspaces.

## Requirements

- Python 3.8+
- FastAPI
- boto3
- requests
- pydantic
- gitpython
- dotenv
- langchain_aws

## Setup

### Install Dependencies

```sh
pip install fastapi boto3 requests pydantic gitpython python-dotenv langchain_aws uvicorn
```

### Environment Variables

Create a `.env` file in the root directory and add the following environment variables:

```
AWS_PROFILE=fab-geekle
API_TOKEN=your_gitpod_api_token
```

### Running the Application

To run the application, use the following command:

```sh
uvicorn main:app --host 0.0.0.0 --port 8000
```

## API Endpoints

### Clone Repository and Generate Setup Commands

**Endpoint**: `/dashboard`

**Method**: `POST`

**Request Body**:

```json
{
  "git_url": "https://github.com/your-repo.git"
}
```

**Response**:

```json
{
  "user_input": "https://github.com/your-repo.git",
  "model_output": "Generated setup instructions",
  "command": "command1 && command2 && command3",
  "typeFound": true
}
```

### Chat LLM

**Endpoint**: `/chat-llm/`

**Method**: `POST`

**Request Body**:

```json
{
  "userID": "user123",
  "requestID": "req123",
  "user_input": "Your question or task",
  "modelID": "anthropic.claude-3-haiku-20240307-v1:0",
  "modelParameter": {
    "temperature": 0.75,
    "max_tokens": 2000,
    "top_p": 0.9
  }
}
```

**Response**:

```json
{
  "user_input": "Your question or task",
  "model_output": "Response from the model",
  "wantsToDraw": false,
  "repository": "https://url-of-github-repo.git"
}
```

### List Organizations

**Endpoint**: `/organizations/`

**Method**: `GET`

**Response**:

```json
{
  "organizations": [...]
}
```

### List Workspaces

**Endpoint**: `/workspaces/`

**Method**: `GET`

**Query Parameter**:

- `organizationId` (required)

**Response**:

```json
{
  "workspaces": [...]
}
```

### Start Workspace

**Endpoint**: `/start-workspace/`

**Method**: `POST`

**Query Parameter**:

- `workspaceId` (required)

**Response**:

```json
{
  "status": "Workspace started"
}
```

### Stop Workspace

**Endpoint**: `/stop-workspace/`

**Method**: `POST`

**Query Parameter**:

- `workspaceId` (required)

**Response**:

```json
{
  "status": "Workspace stopped"
}
```

### Create Workspace

**Endpoint**: `/create-workspace/`

**Method**: `POST`

**Query Parameters**:

- `ownerId` (required)
- `organizationId` (required)

**Request Body**:

```json
{
  "contextUrl": {
    "url": "https://github.com/your-repo.git",
    "workspaceClass": "g1-standard",
    "config": {
      "tasks": [
        {
          "name": "Task name",
          "openMode": "default",
          "command": "command to run"
        }
      ]
    },
    "editor": {
      "name": "code",
      "version": "latest"
    }
  },
  "metadata": {
    "ownerId": "owner123",
    "organizationId": "org123"
  }
}
```

**Response**:

```json
{
  "workspaceId": "new_workspace_id",
  "status": "Workspace created and started"
}
```

### Delete Workspace

**Endpoint**: `/delete-workspace/`

**Method**: `DELETE`

**Query Parameter**:

- `workspaceId` (required)

**Response**:

```json
{
  "status": "Workspace deleted"
}
```

## Additional Information

- Ensure the AWS credentials are properly configured for the `AWS_PROFILE` specified.
- The API_TOKEN should be a valid token for Gitpod API access.

This documentation provides an overview of the available endpoints and their usage. For more detailed information, refer to the source code and the corresponding comments.