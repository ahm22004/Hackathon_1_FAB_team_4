import logging
import os
from logging import getLogger


from fastapi import APIRouter,FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from langchain_aws import ChatBedrock
from pydantic import BaseModel, Field
from user_session import ChatSession, ChatSessionManager

import boto3
import requests
from dotenv import load_dotenv
from typing import List, Optional
import git
import tempfile

# Load environment variables from .env file
load_dotenv()
API_TOKEN = os.environ["API_TOKEN"]

logging.basicConfig(level=logging.INFO)
logger = getLogger(__name__)
app = FastAPI()
router = APIRouter()

#os.environ["AWS_PROFILE"] = "fab-geekle"
origins = [
    "*",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# fix the region_name -> us-west-2
bedrock = boto3.client(service_name="bedrock-runtime", region_name="us-west-2")
session_manager = ChatSessionManager()


# Function to read the content of a file
def read_file_content(repo_name, filename):
    with open(os.path.join(repo_name, filename), 'r') as file:
        return file.read()


def get_response_from_llm(
        input_prompt: str,
        project_type: str,
        file_content: str,
        model_id: str,
        bedrock_client: boto3.client,
):
    logger.info(f"Getting response from LLM with model_id: {model_id}")
    logger.info(f"Input prompt: {input_prompt}")
    processed_prompt = generate_prompt_for_command(
        project_type, file_content
    )
    logger.info(f"Processed prompt: {processed_prompt}")
    print(processed_prompt)
    llm = ChatBedrock(
        model_id=model_id, client=bedrock_client, model_kwargs={
            "temperature": 0.75,
            "max_tokens": 2000,
            "top_p": 0.9,
        }
    )
    response = llm.invoke(processed_prompt)
    content = response.content
    original_response = content
    logger.info(f"Response from LLM: {content}")
    # print(content)
    return content


def generate_prompt_for_command(
        project_type: str, file_content: str
):
    prompt = f"""
        The project type is {project_type}. Create bash  commands to  install and execute the project based on the 
        following file content: {file_content}
        only provide the commands  and nothing else
        Format: 
        command1 && command2 && command3 && command3
        """
    return prompt


def determine_project_type_and_instructions(files, repo_name):
    project_files = {
        'package.json': 'Node.js',
        'requirements.txt': 'Python',
        'pom.xml': 'Java (Maven)',
        'build.gradle': 'Java (Gradle)',
        'Gemfile': 'Ruby on Rails',
        'composer.json': 'PHP',
        'go.mod': 'Go',
        'Cargo.toml': 'Rust',
        'bun.lockb': 'Bun',
        'Package.swift': 'Swift',
        'NuGet.config': 'C# (NuGet)',
        'mix.exs': 'Elixir (Mix)',
        'Makefile': 'Make',
        # Add more file types and project types as needed
    }

    for filename, project_type in project_files.items():
        if filename in files:
            file_content = read_file_content(repo_name, filename)
            return project_type, file_content

    return "Unknown", ""


# Function to clone repository and list files
def clone_and_list_files(repo_url, temp_dir):
    repo_name = repo_url.split("/")[-1].replace(".git", "")
    print(f"Temp dir: {temp_dir.name}")
    repo_name_dir = os.path.join(temp_dir.name, repo_name)

    if not os.path.exists(repo_name_dir):
        os.makedirs(repo_name_dir)

    try:
        ## delete repository
        repo = git.Repo.clone_from(repo_url, repo_name_dir)
        print(f"Repository cloned to {repo_name_dir}")
    except Exception as e:
        print(f"Error cloning repository: {e}")
        return []

    # List files in the repository
    files_list = []
    for root, dirs, files in os.walk(repo_name_dir):
        for file in files:
            files_list.append(os.path.relpath(os.path.join(root, file), repo_name_dir))

    ## return files_list
    return repo_name_dir, files_list


@router.post("/dashboard")
async def generate_graph(request: Request):
    # try:
    request = await request.json();
    print("Raw request body:", request)
    repo_url = request.get("git_url");

    # file saved into temp dir location

    temp_dir = tempfile.TemporaryDirectory()
    repo_name, files = clone_and_list_files(repo_url, temp_dir)
    project_type, file_content = determine_project_type_and_instructions(files, repo_name)
    processed_prompt = generate_prompt_for_command(project_type, file_content)
    if project_type == "Unknown":
        instructions = "#!/bin/bash\n# The project type could not be determined automatically. Please check the repository's README file for setup instructions."
        return {
            "user_input": repo_url,
            "model_output": instructions,
            "command": "",
            "typeFound": False

        }

    else:

        llm = ChatBedrock(
            model_id="anthropic.claude-3-haiku-20240307-v1:0", client=bedrock, model_kwargs={
                "temperature": 0.75,
                "max_tokens": 2000,
                "top_p": 0.9,
            }
        )
        # Generate instructions using bedrock
        instructions = llm.invoke(processed_prompt)
    print(instructions)
    # cleaning up temporary files
    temp_dir.cleanup();
    return {
        "user_input": repo_url,
        "command": instructions.content,
        "typeFound": True,
        "model_output": instructions
    }


app.include_router(router)


class ModelKWArgs(BaseModel):
    modelParameter: dict = {
        "temperature": 0.75,
        "max_tokens": 2000,
        "top_p": 0.9,
    }


class RequestModel(ModelKWArgs):
    userID: str
    requestID: str
    user_input: str
    modelID: str = "anthropic.claude-3-haiku-20240307-v1:0"


class MermaidRequest(BaseModel):
    userID: str


def chat_llm_no_stream(request: RequestModel, chat_session: ChatSession) -> dict:
    chat_model = ChatBedrock(
        model_id=request.modelID,
        client=bedrock,
        model_kwargs=request.modelParameter,
        streaming=True,
    )
    text_input = request.user_input
    if len(chat_session.chats) == 0:
        initial_context = """
             
        I will now give you my question or task, and you can ask me subsequent questions one by one.

        Please format your output in HTML and provide public GitHub repo links with a 4-line max summary of what each repo does. 
        Please format the output in HTML without adding any \n characters.
        Here's an example of how the output should look:
        <ol>
          <li>
            <a href="github link 1">https://url-of-github-1.git</a>
            <p>Repo 1 does X. It is useful for Y.</p>
          </li>
          <li>
            <a href="github link 2">https://url-of-github-2.git<</a>
            <p>Repo 2 does A. It is designed to B.</p>
          </li>
          <li>
            <a href="github link 3">https://url-of-github-3.git<</a>
            <p>Repo 3 does M. It helps in N.</p>
          </li>
        </ol>
        Do suggest 1 to 4 public repos that implement my question.
        
        Provide the links always.
        
        Ask the user which option they prefer. Format in html as below:
        <p>Which option do you prefer?</p>
        
        Only ask the question and do not number your questions.
        """
        text_input = initial_context + text_input
    else:
        text_input = f"""
            Given the following conversation of chatbot and user:
            {chat_session.str_chat()}
            Proceed with new user response: "{text_input}"
            Respond immediately with a repository URL if you found one. Ensure the GitHub link provided ends with '.git'.
        """

    response = chat_model.invoke(text_input)
    logger.info(f"Task created for user: {request.userID}")
    logger.info(f"User chat history: {chat_session.chats}")

    response_content = response.content
    git_url = next((line.strip() for line in response_content.split() if line.strip().endswith('.git')), None)
    chat_session.add_chat(request.user_input, response_content)
    return {
        "user_input": request.user_input,
        "model_output": response_content,
        "wantsToDraw": False,
        "repository": git_url
    }


@app.post("/chat-llm/")
def chat_llm(request: RequestModel):
    chat_session = session_manager.get_session(request.userID)
    try:
        response = chat_llm_no_stream(request, chat_session)
        chat_session.user_id = request.userID
        chat_session.request_id = request.requestID
        chat_session.model_id = request.modelID
        chat_session.model_kwargs = request.modelParameter
        return response
    except Exception as e:
        logger.error(f"Error generating detailed solution: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Error generating detailed solution: {str(e)}"
        )


# List organizations from an user
@app.get("/organizations/")
def list_organizations():
    headers = {
        'Authorization': f'Bearer {API_TOKEN}',
        'Content-Type': 'application/json'
    }

    response = requests.post('https://api.gitpod.io/gitpod.v1.OrganizationService/ListOrganizations', headers=headers, json={})

    if response.status_code == 200:
        return response.json()
    else:
        raise HTTPException(status_code=response.status_code, detail=response.text)

@app.get("/workspaces/")
def list_workspaces(organizationId: str = Query(..., description="The organization ID")):
    headers = {
        'Authorization': f'Bearer {API_TOKEN}',
        'Content-Type': 'application/json'
    }

    payload = {
        "organizationId": organizationId
    }

    response = requests.post('https://api.gitpod.io/gitpod.v1.WorkspaceService/ListWorkspaces', headers=headers, json=payload)

    if response.status_code == 200:
        return response.json()
    else:
        raise HTTPException(status_code=response.status_code, detail=response.text)

# Start a workspace
@app.post("/start-workspace/")
def start_workspace(workspaceId: str = Query(..., description="The workspace ID")):
    headers = {
        'Authorization': f'Bearer {API_TOKEN}',
        'Content-Type': 'application/json'
    }

    payload = {
        "workspaceId": workspaceId
    }

    response = requests.post('https://api.gitpod.io/gitpod.v1.WorkspaceService/StartWorkspace', headers=headers, json=payload)

    if response.status_code == 200:
        return response.json()
    else:
        raise HTTPException(status_code=response.status_code, detail=response.text)

# Stop a workspace
@app.post("/stop-workspace/")
def stop_workspace(workspaceId: str = Query(..., description="The workspace ID")):
    headers = {
        'Authorization': f'Bearer {API_TOKEN}',
        'Content-Type': 'application/json'
    }

    payload = {
        "workspaceId": workspaceId
    }

    response = requests.post('https://api.gitpod.io/gitpod.v1.WorkspaceService/StopWorkspace', headers=headers, json=payload)

    if response.status_code == 200:
        return response.json()
    else:
        raise HTTPException(status_code=response.status_code, detail=response.text)

class Task(BaseModel):
    name: str
    openMode: str
    command: str

class Config(BaseModel):
    tasks: List[Task]

class Editor(BaseModel):
    name: str
    version: str

class ContextUrl(BaseModel):
    url: str
    workspaceClass: str = "g1-standard"
    config: Optional[Config]
    editor: Editor = Field(default_factory=lambda: Editor(name="code", version="latest"))

class Metadata(BaseModel):
    ownerId: str
    organizationId: str

class WorkspaceRequest(BaseModel):
    contextUrl: ContextUrl
    metadata: Metadata

# Create a new Workspace with github repository
@app.post("/create-workspace/")
def create_workspace(
        request: WorkspaceRequest,
        ownerId: str = Query(..., description="The owner ID"),
        organizationId: str = Query(..., description="The organization ID")):
    headers = {
        'Authorization': f'Bearer {API_TOKEN}',
        'Content-Type': 'application/json'
    }

    payload = {
        "contextUrl": {
            "url": request.contextUrl.url,
            "workspaceClass": request.contextUrl.workspaceClass,
            "editor": {
                "name": request.contextUrl.editor.name,
                "version": request.contextUrl.editor.version
            }
        },
        "metadata": {
            "ownerId": ownerId,
            "organizationId": organizationId
        }
    }

    # Include tasks if provided
    if request.contextUrl.config and request.contextUrl.config.tasks:
        payload["contextUrl"]["config"] = {
            "tasks": [{"name": task.name, "openMode": task.openMode, "command": task.command} for task in request.contextUrl.config.tasks]
        }

    response = requests.post('https://api.gitpod.io/gitpod.v1.WorkspaceService/CreateAndStartWorkspace', headers=headers, json=payload)

    if response.status_code == 200:
        return response.json()
    else:
        raise HTTPException(status_code=response.status_code, detail=response.text)

# Delete a workspace
@app.delete("/delete-workspace/")
def delete_workspace(workspaceId: str = Query(..., description="The workspace ID")):
    headers = {
        'Authorization': f'Bearer {API_TOKEN}',
        'Content-Type': 'application/json'
    }

    payload = {
        "workspaceId": workspaceId
    }

    response = requests.post('https://api.gitpod.io/gitpod.v1.WorkspaceService/DeleteWorkspace', headers=headers, json=payload)

    if response.status_code == 200:
        return response.json()
    else:
        raise HTTPException(status_code=response.status_code, detail=response.text)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
