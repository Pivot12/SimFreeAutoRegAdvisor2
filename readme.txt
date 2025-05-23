# SimFreeAutoRegAdvisor2

SimFreeAutoRegAdvisor2 is an AI agent that takes user queries about automotive regulations in simple language and returns highly accurate answers by referencing actual regulatory documents. The agent uses the Firecrawl API to access and parse regulatory websites, processes the information with the Cerebras API and Llama Scout model, and provides reliable, cited answers.

## Features

- **Natural Language Interface**: Ask questions about automotive regulations in plain English
- **Accurate Sourcing**: Only references official regulatory documents
- **Global Coverage**: Accesses regulatory information from major automotive markets worldwide
- **RAG Architecture**: Uses Retrieval Augmented Generation to ensure factual accuracy
- **Learning Capability**: Improves over time by tracking successful searches
- **Model Context Protocol (MCP)**: Robust against API and model changes
- **Diagnostics Logging**: Captures usage statistics for analysis

## Installation

1. Clone this repository:
   ```bash
   git clone https://github.com/Pivot12/SimFreeAutoRegAdvisor2.git
   cd SimFreeAutoRegAdvisor2
   ```

2. Create a virtual environment and install dependencies:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. Set up API keys:
   - Create a `.env` file in the root directory with the following content:
     ```
     FIRECRAWL_API_KEY=your_firecrawl_api_key
     CEREBRAS_API_KEY=your_cerebras_api_key
     ```
   - Alternatively, set up the Streamlit secrets:
     - Create a `.streamlit/secrets.toml` file with:
       ```toml
       firecrawl_api_key = "your_firecrawl_api_key"
       cerebras_api_key = "your_cerebras_api_key"
       ```

## Usage

Run the Streamlit app:
```bash
streamlit run app.py
```

Then open your browser to the URL shown in the terminal (usually http://localhost:8501).

## Deployment to Streamlit Cloud

1. Push this repository to GitHub.

2. Go to [Streamlit Cloud](https://streamlit.io/cloud) and sign in with your GitHub account.

3. Click "New app" and select this repository.

4. In the app settings, add your API keys as secrets:
   - firecrawl_api_key
   - cerebras_api_key

5. Deploy the app.

## Model Context Protocol (MCP) Integration

This app uses Model Context Protocol (MCP) to interact with AI models, providing a standardized interface that's robust against API changes. The MCP implementation enables:

- **Stability**: Maintain functionality even if the underlying APIs change
- **Flexibility**: Easily switch between different AI models
- **Extensibility**: Add new data sources or tools without major code changes

To configure MCP settings, edit the variables in `config.py`:
```python
MCP_ENABLED = True
MCP_PORT = 3000
MCP_HOST = "localhost"
```

## Learning Capability

The agent improves over time by:

1. Tracking which regulatory websites provide the most useful information
2. Recognizing patterns in user queries
3. Caching successful search strategies
4. Prioritizing sources based on historical success rates

The learning data is stored in `data/learning_cache.json`.

## Logging and Analytics

Usage statistics are logged to `data/log_data.csv`, capturing:

- User queries and responses
- Response times
- Topics of regulation
- Success rates
- Number of sources referenced

This data can be analyzed to improve the agent and understand user needs better.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- [Firecrawl API](https://www.firecrawl.dev/) for web crawling capabilities
- [Cerebras API](https://www.cerebras.ai/) and Llama Scout model for natural language processing
- [Streamlit](https://streamlit.io/) for the web interface
- [Model Context Protocol](https://www.anthropic.com/news/model-context-protocol) for the standardized AI interface
