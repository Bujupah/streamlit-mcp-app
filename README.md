# MCP Streamlit Chat

This project is a Streamlit chat application that connects to an Ollama LLM backend and multiple MCP (Model-as-a-Service) servers. The application allows the LLM to discover and call tools from the connected MCP servers.

## Project Structure

- `/app`: Contains the Streamlit UI code.
- `/core`: Holds the core logic for the chatbot and the Ollama LLM wrapper.
- `/mcp`: Includes the MCP client and tool registry.
- `/mcp_servers`: Includes the MCP servers.
- `/config`: Manages application settings and server configurations.
- `dummy_server.py`: An example MCP server for demonstration.
- `uv.toml`: The project's dependency management file.

## Setup and Installation

This project uses `uv` for dependency management.

1.  **Install `uv`**:
    If you don't have `uv` installed, you can install it with pip:
    ```bash
    pip install uv
    ```

2.  **Create a virtual environment and install dependencies**:
    ```bash
    uv venv
    uv sync
    ```

## How to Run the Application

1.  **Start the Ollama service**:
    Make sure you have Ollama installed and running. You can pull a model like `llama3` to get started:
    ```bash
    ollama pull llama3
    ```

2.  **Run the dummy MCP server**:
    In a separate terminal, run the dummy MCP server:
    ```bash
    uv run python mcp_servers/dummy_server.py
    ```
    This will start a server on `http://localhost:3000` with an `add` tool.

3.  **Run the Streamlit application**:
    In another terminal, run the Streamlit app:
    ```bash
    uv run streamlit run app/main.py
    ```
    The application will be available at `http://localhost:8501`.

## How to Use the Application

1.  **Open the Streamlit app** in your browser.
2.  On the sidebar, you can **enable or disable MCP servers**. The `dummy_server` should be enabled by default.
3.  Click **"Refresh Tools"** to discover tools from the enabled servers. The available tools will be displayed in the sidebar.
4.  **Chat with the model**. Try asking it to perform a task that requires a tool, for example:
    > "What is 5 + 7?"

    The model should call the `dummy_server-add` tool and provide the correct answer.
