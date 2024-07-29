import logging
import os
import subprocess
from logging import getLogger

import boto3
from fastapi import FastAPI, APIRouter, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from langchain_aws import ChatBedrock
from pydantic import BaseModel
from user_session import ChatSession, ChatSessionManager

logging.basicConfig(level=logging.INFO)
logger = getLogger(__name__)
app = FastAPI()
router = APIRouter()

os.environ["AWS_PROFILE"] = "fab-geekle"
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


class ModelKWArgs(BaseModel):
    modelParameter: dict = {
        "temperature": 0.75,
        "max_tokens": 2000,
        "top_p": 0.9,
    }


session_manager = ChatSessionManager()


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
        The project type is {project_type}. Create a bash script to install and execute the project based on the following file content:
        {file_content}
        Only provide the bash script, no other content.
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
def clone_and_list_files(repo_url):
    repo_name = repo_url.split("/")[-1].replace(".git", "")
    if os.path.exists(repo_name):
        subprocess.run(["rm", "-rf", repo_name])
    subprocess.run(["git", "clone", repo_url])
    files = os.listdir(repo_name)
    return repo_name, files


# Function to read the content of a file
def read_file_content(repo_name, filename):
    with open(os.path.join(repo_name, filename), 'r') as file:
        return file.read()


@router.post("/dashboard")
async def generate_graph(request: Request):
    # try:
    request = await request.json();
    print("Raw request body:", request)
    repo_url = request.get("git_url");
    repo_name, files = clone_and_list_files(repo_url)
    project_type, file_content = determine_project_type_and_instructions(files, repo_name)
    processed_prompt = generate_prompt_for_command(project_type, file_content)
    if project_type == "Unknown":
        instructions = "#!/bin/bash\n# The project type could not be determined automatically. Please check the repository's README file for setup instructions."
    else:

        llm = ChatBedrock(
            model_id="anthropic.claude-3-haiku-20240307-v1:0", client=bedrock, model_kwargs={
                "temperature": 0.75,
                "max_tokens": 2000,
                "top_p": 0.9,
            }
        )
        # Generate instructions using LangChain
        instructions = llm.invoke(processed_prompt)
    print(instructions)

    return instructions
app.include_router(router)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
