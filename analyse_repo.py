
from fastapi import FastAPI, APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse
from langchain_openai import OpenAI
import json

import os
import subprocess
from langchain_core.runnables.base import RunnableSequence
from langchain.prompts import PromptTemplate

import logging
import os
from logging import getLogger

logging.basicConfig(level=logging.INFO)
logger = getLogger(__name__)


# Define the FastAPI app
app = FastAPI()

# Define the prompt to request only the bash script
prompt = PromptTemplate(
    input_variables=["project_type", "file_content"],
    template="""
    The project type is {project_type}. Create a bash script to install and execute the project based on the following file content:
    {file_content}
    Only provide the bash script, no other content.
    """
)

model = OpenAI(api_key="sk-proj-ZqBvL23iceVFDeFlJiSET3BlbkFJP5nUGumADbvL1eIyBqNJ")


chain = RunnableSequence(prompt | model)

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

# Function to determine project type and generate instructions
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

router = APIRouter()

@router.get("/")
async def redirect_root_to_docs():
    return RedirectResponse("/docs")

@router.post("/dashboard")
async def generate_graph(request: Request):
    # try:
        request = await request.json();
        print("Raw request body:", request)
        repo_url = request.get("git_url");
        repo_name, files = clone_and_list_files(repo_url)
        project_type, file_content = determine_project_type_and_instructions(files, repo_name)

        if project_type == "Unknown":
            instructions = "#!/bin/bash\n# The project type could not be determined automatically. Please check the repository's README file for setup instructions."
        else:
            # Generate instructions using LangChain
            instructions = chain.invoke({"project_type": project_type, "file_content": file_content})


        print(instructions)

        return instructions

    # except Exception as e:
    #         logger.error(f"Error generating detailed solution: {str(e)}")
    #         raise HTTPException(
    #             status_code=500, detail=f"Error generating detailed solution: {str(e)}"
    #         )


# Include the router in the app
app.include_router(router)

# Run the server
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)